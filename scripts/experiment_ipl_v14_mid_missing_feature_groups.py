"""Test feature groups missing from the IPL v14 MID router.

This is narrower than the terminal-feature experiment:
  - v14_death_gap: features present in v14 DEATH but not v14 MID.
  - v7_gap: important v7 features missing from v14 MID.
  - combined gaps.

Split is intentionally conservative: train seasons < 2025, test seasons >= 2025.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbl_pipeline.training.blend_model import XGBLRBlend  # noqa: E402
from build_ipl_v14_pitch_features import add_pitch_features  # noqa: E402
from experiment_ipl_v14_mid_terminal_features import _ensure_terminal_features  # noqa: E402
from ipl_v13_mid_split_common import (  # noqa: E402
    apply_calibrator_bundle,
    fit_calibrator_bundle,
    load_training_data,
    oof_phase_predictions,
    phase_slice,
    safe_X,
)


OUT_DIR = Path("experiments/ipl_v14_mid_missing_feature_groups")
V14_FEATURES_PATH = Path("models/ipl_v14_pitch_features/phase_features.json")
V7_MODEL_PATH = Path("models/ipl_v7/champion_model.joblib")


def _load() -> tuple[pd.DataFrame, dict[str, list[str]], list[str]]:
    df = load_training_data()
    df = add_pitch_features(df)
    df = _ensure_terminal_features(df)
    with open(V14_FEATURES_PATH, encoding="utf-8") as f:
        v14_features = json.load(f)
    v7_model = joblib.load(V7_MODEL_PATH)
    return df, v14_features, list(v7_model.selected_features_)


def _feature_groups(df: pd.DataFrame, v14_features: dict[str, list[str]], v7_features: list[str]) -> dict[str, list[str]]:
    mid = list(v14_features["mid"])
    death_gap = [feature for feature in v14_features["death"] if feature not in mid and feature in df.columns]
    v7_gap = [feature for feature in v7_features if feature not in mid and feature in df.columns]

    # Exclude pure phase flag leakage/noise for a MID-only model.
    v7_gap = [feature for feature in v7_gap if feature != "is_powerplay"]

    return {
        "baseline_mid": mid,
        "death_gap_mid": mid + death_gap,
        "v7_gap_mid": mid + v7_gap,
        "death_plus_v7_gap_mid": mid + death_gap + [feature for feature in v7_gap if feature not in death_gap],
    }


def _train_eval(df: pd.DataFrame, features: list[str], label: str) -> tuple[dict[str, Any], pd.DataFrame]:
    mid = phase_slice(df, (7, 15))
    train_df = mid[mid["season"].astype(str) < "2025"].copy().reset_index(drop=True)
    test_df = mid[mid["season"].astype(str) >= "2025"].copy().reset_index(drop=True)

    train_oof = oof_phase_predictions(train_df, features)
    bundle = fit_calibrator_bundle(train_oof["raw"], train_oof["y"], train_oof["over"], "platt")
    X_train, avail = safe_X(train_df, features)
    X_test, _ = safe_X(test_df, features)
    model = XGBLRBlend()
    model.fit(X_train, train_df["is_winner"].values)
    raw = model.predict_proba(X_test)[:, 1]
    cal = apply_calibrator_bundle(raw, test_df["over"].values.astype(int), bundle)

    pred = test_df[
        [
            "match_id",
            "season",
            "over",
            "ball",
            "is_winner",
            "target_above_par",
            "required_run_rate",
            "current_run_rate",
            "score_vs_par",
            "wickets_lost",
            "wickets_remaining",
        ]
    ].copy()
    pred["candidate"] = label
    pred["raw_pred"] = raw
    pred["cal_pred"] = cal
    return _metrics(label, pred, avail), pred


def _metrics(label: str, pred: pd.DataFrame, features: list[str]) -> dict[str, Any]:
    y = pred["is_winner"].astype(float)
    raw = pred["raw_pred"].clip(1e-6, 1 - 1e-6)
    cal = pred["cal_pred"].clip(1e-6, 1 - 1e-6)
    return {
        "candidate": label,
        "n": int(len(pred)),
        "n_features": int(len(features)),
        "brier_raw": float(brier_score_loss(y, raw)),
        "brier_cal": float(brier_score_loss(y, cal)),
        "logloss_cal": float(log_loss(y, cal, labels=[0, 1])),
        "mean_pred": float(cal.mean()),
        "actual_wr": float(y.mean()),
        "gap_pp": float((cal.mean() - y.mean()) * 100.0),
    }


def _segment_metrics(pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    segments = {
        "early_7_11": pred["over"].between(7, 11),
        "late_12_15": pred["over"].between(12, 15),
        "par_50_80": pred["target_above_par"].between(-20, 20) & pred["cal_pred"].between(0.50, 0.80),
        "late_par_50_80": pred["over"].between(12, 15)
        & pred["target_above_par"].between(-20, 20)
        & pred["cal_pred"].between(0.50, 0.80),
    }
    for segment, mask in segments.items():
        sub = pred[mask]
        if sub.empty:
            continue
        y = sub["is_winner"].astype(float)
        p = sub["cal_pred"].clip(1e-6, 1 - 1e-6)
        rows.append(
            {
                "candidate": pred["candidate"].iloc[0],
                "segment": segment,
                "n": int(len(sub)),
                "brier_cal": float(brier_score_loss(y, p)),
                "logloss_cal": float(log_loss(y, p, labels=[0, 1])),
                "mean_pred": float(p.mean()),
                "actual_wr": float(y.mean()),
                "gap_pp": float((p.mean() - y.mean()) * 100.0),
            }
        )
    return pd.DataFrame(rows)


def _md_table(df: pd.DataFrame) -> str:
    rows = df.copy()
    for col in rows.columns:
        if pd.api.types.is_float_dtype(rows[col]):
            rows[col] = rows[col].map(lambda value: "" if pd.isna(value) else f"{value:.5f}")
    headers = [str(col) for col in rows.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in rows.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in rows.columns) + " |")
    return "\n".join(lines)


def _write_report(metrics_df: pd.DataFrame, segments_df: pd.DataFrame, groups: dict[str, list[str]], mid_base: list[str]) -> None:
    best = metrics_df.sort_values("brier_cal").iloc[0]
    gap_rows = []
    for label, features in groups.items():
        if label == "baseline_mid":
            continue
        gap_rows.append(
            {
                "candidate": label,
                "added_count": len([feature for feature in features if feature not in mid_base]),
                "added_features": ", ".join([feature for feature in features if feature not in mid_base]),
            }
        )

    lines = [
        "# IPL v14 MID Missing Feature Groups",
        "",
        "Split: train seasons < 2025, test seasons >= 2025.",
        "",
        "## Decision",
        "",
        f"- Best full-MID calibrated Brier: `{best['candidate']}` = `{best['brier_cal']:.5f}`.",
        "- This tests the actual v14 DEATH-not-MID gap and the important v7 features missing from v14 MID.",
        "",
        "## Full MID Metrics",
        "",
        _md_table(metrics_df.sort_values("brier_cal")),
        "",
        "## Segment Metrics",
        "",
        _md_table(segments_df.sort_values(["segment", "brier_cal"])),
        "",
        "## Added Feature Groups",
        "",
        _md_table(pd.DataFrame(gap_rows)),
        "",
    ]
    (OUT_DIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading data...")
    df, v14_features, v7_features = _load()
    groups = _feature_groups(df, v14_features, v7_features)
    (OUT_DIR / "feature_groups.json").write_text(json.dumps(groups, indent=2), encoding="utf-8")

    all_metrics = []
    all_segments = []
    for label, features in groups.items():
        print(f"Running {label} ({len(features)} requested features)")
        metric, pred = _train_eval(df, features, label)
        all_metrics.append(metric)
        all_segments.append(_segment_metrics(pred))
        pred.to_csv(OUT_DIR / f"{label}_predictions.csv", index=False)
        print(
            f"  brier={metric['brier_cal']:.5f} "
            f"logloss={metric['logloss_cal']:.5f} gap={metric['gap_pp']:+.2f}pp"
        )

    metrics_df = pd.DataFrame(all_metrics)
    segments_df = pd.concat(all_segments, ignore_index=True)
    metrics_df.to_csv(OUT_DIR / "summary_metrics.csv", index=False)
    segments_df.to_csv(OUT_DIR / "segment_metrics.csv", index=False)
    _write_report(metrics_df, segments_df, groups, v14_features["mid"])
    print(f"Saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
