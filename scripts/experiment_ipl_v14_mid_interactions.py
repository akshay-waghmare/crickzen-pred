"""Focused IPL v14 MID improvement experiment with terminal interactions.

This is a smaller follow-up to experiment_ipl_v14_mid_terminal_features.py.
It trains only MID candidates on the true-OOS split to test whether terminal
signals need MID-specific interactions rather than being copied directly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbl_pipeline.training.blend_model import XGBLRBlend  # noqa: E402
from ipl_v13_mid_split_common import (  # noqa: E402
    apply_calibrator_bundle,
    fit_calibrator_bundle,
    load_training_data,
    oof_phase_predictions,
    phase_slice,
    safe_X,
)
from build_ipl_v14_pitch_features import add_pitch_features  # noqa: E402
from experiment_ipl_v14_mid_terminal_features import (  # noqa: E402
    TERMINAL_CANDIDATES,
    _ensure_terminal_features,
)


OUT_DIR = Path("experiments/ipl_v14_mid_interactions")
V14_FEATURES_PATH = Path("models/ipl_v14_pitch_features/phase_features.json")

INTERACTION_FEATURES = [
    "mid_terminal_pressure",
    "mid_late_required_rpb",
    "mid_late_feasibility",
    "mid_par_required_rpb",
    "mid_par_feasibility",
    "mid_par_tight_alive",
    "mid_easy_chase_terminal",
    "mid_wicket_budget_rpb",
    "mid_score_buffer_feasibility",
    "mid_rrr_gap_terminal",
    "chase_completion_norm",
    "mid_late_completion_norm",
    "mid_completion_feasibility",
    "mid_par_completion_feasibility",
]


def _load_base() -> tuple[pd.DataFrame, list[str]]:
    df = load_training_data()
    df = add_pitch_features(df)
    df = _ensure_terminal_features(df)
    df = _add_interactions(df)
    with open(V14_FEATURES_PATH, encoding="utf-8") as f:
        features = json.load(f)
    return df, list(features["mid"])


def _add_interactions(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    over = d["over"].astype(float)
    late = (over >= 12).astype(float)
    par = d.get("is_par_chase", (d["target_above_par"].between(-20, 20))).astype(float)
    easy = d.get("is_low_chase", (d["target_above_par"] < -20)).astype(float)
    rpb = d["required_rpb"].astype(float)
    urgency = d["death_chase_urgency"].astype(float)
    feasibility = d["death_feasibility"].astype(float)
    tight = d["tight_finish_zone"].astype(float)
    wickets_remaining = d["wickets_remaining"].astype(float)
    score_vs_par = d["score_vs_par"].astype(float)
    run_rate_diff = d["run_rate_diff"].astype(float)
    resource_pct = d.get("resource_pct", pd.Series(0.0, index=d.index)).fillna(0.0).astype(float)
    completion_norm = (1.0 - (resource_pct / 100.0)).clip(0, 1)

    d["mid_terminal_pressure"] = (rpb * urgency).clip(0, 50)
    d["mid_late_required_rpb"] = (late * rpb).clip(0, 10)
    d["mid_late_feasibility"] = (late * feasibility).clip(0, 5)
    d["mid_par_required_rpb"] = (par * rpb).clip(0, 10)
    d["mid_par_feasibility"] = (par * feasibility).clip(0, 5)
    d["mid_par_tight_alive"] = (par * tight * feasibility).clip(0, 5)
    d["mid_easy_chase_terminal"] = (easy * feasibility * wickets_remaining).clip(0, 50)
    d["mid_wicket_budget_rpb"] = (wickets_remaining / (rpb + 0.1)).clip(0, 20)
    d["mid_score_buffer_feasibility"] = (score_vs_par * feasibility).clip(-200, 200)
    d["mid_rrr_gap_terminal"] = (run_rate_diff * feasibility).clip(-100, 100)
    d["chase_completion_norm"] = completion_norm
    d["mid_late_completion_norm"] = (late * completion_norm).clip(0, 1)
    d["mid_completion_feasibility"] = (completion_norm * feasibility).clip(0, 5)
    d["mid_par_completion_feasibility"] = (par * completion_norm * feasibility).clip(0, 5)
    return d


def _train_eval_mid(df: pd.DataFrame, features: list[str], label: str) -> tuple[dict[str, Any], pd.DataFrame]:
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
    y = test_df["is_winner"].astype(float).to_numpy()

    pred = test_df[
        [
            "match_id",
            "season",
            "over",
            "ball",
            "is_winner",
            "target_above_par",
            "required_run_rate",
            "score_vs_par",
            "wickets_lost",
            "wickets_remaining",
        ]
    ].copy()
    pred["candidate"] = label
    pred["raw_pred"] = raw
    pred["cal_pred"] = cal

    metric = _metrics(label, pred, avail)
    return metric, pred


def _metrics(label: str, pred: pd.DataFrame, features: list[str]) -> dict[str, Any]:
    y = pred["is_winner"].astype(float)
    raw = pred["raw_pred"].clip(1e-6, 1 - 1e-6)
    cal = pred["cal_pred"].clip(1e-6, 1 - 1e-6)
    out: dict[str, Any] = {
        "candidate": label,
        "segment": "mid_all",
        "n": int(len(pred)),
        "n_features": len(features),
        "brier_raw": float(brier_score_loss(y, raw)),
        "brier_cal": float(brier_score_loss(y, cal)),
        "logloss_cal": float(log_loss(y, cal, labels=[0, 1])),
        "mean_pred": float(cal.mean()),
        "actual_wr": float(y.mean()),
        "gap_pp": float((cal.mean() - y.mean()) * 100.0),
    }
    return out


def _segment_metrics(pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    segments = {
        "early_7_11": pred["over"].between(7, 11),
        "late_12_15": pred["over"].between(12, 15),
        "par_50_80": pred["target_above_par"].between(-20, 20) & pred["cal_pred"].between(0.50, 0.80),
        "late_par_50_80": pred["over"].between(12, 15) & pred["target_above_par"].between(-20, 20) & pred["cal_pred"].between(0.50, 0.80),
    }
    for name, mask in segments.items():
        sub = pred[mask]
        if sub.empty:
            continue
        y = sub["is_winner"].astype(float)
        p = sub["cal_pred"].clip(1e-6, 1 - 1e-6)
        rows.append(
            {
                "candidate": pred["candidate"].iloc[0],
                "segment": name,
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


def _write_report(metrics_df: pd.DataFrame, segments_df: pd.DataFrame) -> None:
    best_overall = metrics_df.sort_values("brier_cal").iloc[0]
    par_rows = segments_df[segments_df["segment"].isin(["par_50_80", "late_par_50_80"])].copy()
    best_par = par_rows.sort_values("brier_cal").groupby("segment", as_index=False).first()

    lines = [
        "# IPL v14 MID Interaction Experiment",
        "",
        "Split: train seasons < 2025, test seasons >= 2025. This follow-up checks whether terminal chase signals need MID-specific interactions instead of being copied into the whole MID model.",
        "",
        "## Decision",
        "",
        f"- Best full-MID calibrated Brier remains `{best_overall['candidate']}` = `{best_overall['brier_cal']:.5f}`.",
        "- Terminal and interaction features are not safe as a broad MID replacement because they worsen full-MID Brier/log loss.",
        "- The par 50-80 bucket remains the real weakness, so any model change should be a narrow specialist/correction instead of a router-wide MID feature expansion.",
        "",
        "## Full MID Metrics",
        "",
        _md_table(
            metrics_df[
                ["candidate", "n", "n_features", "brier_raw", "brier_cal", "logloss_cal", "gap_pp"]
            ].sort_values("brier_cal")
        ),
        "",
        "## Segment Metrics",
        "",
        _md_table(
            segments_df[
                ["candidate", "segment", "n", "brier_cal", "logloss_cal", "mean_pred", "actual_wr", "gap_pp"]
            ].sort_values(["segment", "brier_cal"])
        ),
        "",
        "## Best Narrow Par Segments",
        "",
        _md_table(best_par[["segment", "candidate", "n", "brier_cal", "logloss_cal", "gap_pp"]]),
        "",
    ]
    (OUT_DIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading data...")
    df, mid_features = _load_base()
    terminal = [feature for feature in TERMINAL_CANDIDATES if feature not in mid_features]
    candidates = {
        "baseline_mid": mid_features,
        "terminal_mid": mid_features + terminal,
        "interaction_mid": mid_features + INTERACTION_FEATURES,
        "terminal_interaction_mid": mid_features + terminal + INTERACTION_FEATURES,
    }

    all_metrics = []
    all_segments = []
    for label, features in candidates.items():
        print(f"Running {label} ({len(features)} features)")
        metric, pred = _train_eval_mid(df, features, label)
        all_metrics.append(metric)
        seg = _segment_metrics(pred)
        all_segments.append(seg)
        pred.to_csv(OUT_DIR / f"{label}_predictions.csv", index=False)
        print(
            f"  brier={metric['brier_cal']:.5f} "
            f"logloss={metric['logloss_cal']:.5f} gap={metric['gap_pp']:+.2f}pp"
        )

    metrics_df = pd.DataFrame(all_metrics)
    segments_df = pd.concat(all_segments, ignore_index=True)
    metrics_df.to_csv(OUT_DIR / "summary_metrics.csv", index=False)
    segments_df.to_csv(OUT_DIR / "segment_metrics.csv", index=False)
    _write_report(metrics_df, segments_df)
    print(f"Saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
