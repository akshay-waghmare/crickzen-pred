"""IPL v14 MID-router EDA and terminal-chase feature experiment.

Goal:
  1. Diagnose where the current v14 MID model is slow/under-confident.
  2. Test whether death-style terminal chase features help the MID model.
  3. Test whether splitting MID into early/late models helps.

The experiment uses the same conservative true-OOS split as v14:
train seasons < 2025, test seasons >= 2025.
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
    CAL_METHODS_V12,
    apply_calibrator_bundle,
    fit_calibrator_bundle,
    load_training_data,
    oof_phase_predictions,
    phase_slice,
    safe_X,
)
from build_ipl_v14_pitch_features import add_pitch_features  # noqa: E402


OUT_DIR = Path("experiments/ipl_v14_mid_terminal_features")
V14_FEATURES_PATH = Path("models/ipl_v14_pitch_features/phase_features.json")

BASE_PHASE_RANGES = {
    "pp": (1, 6),
    "mid": (7, 15),
    "death": (16, 20),
}
SPLIT_PHASE_RANGES = {
    "pp": (1, 6),
    "early_mid": (7, 11),
    "late_mid": (12, 15),
    "death": (16, 20),
}

TERMINAL_CANDIDATES = [
    "required_rpb",
    "balls_remaining",
    "runs_per_wkt_rem",
    "chase_completion",
    "death_chase_urgency",
    "death_feasibility",
    "tight_finish_zone",
]


def _ensure_terminal_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    rrr = d.get("required_run_rate", pd.Series(8.0, index=d.index)).fillna(8.0).clip(0, 50)
    crr = d.get("current_run_rate", pd.Series(8.0, index=d.index)).fillna(8.0).clip(0.1, 40)
    wickets_lost = d.get("wickets_lost", pd.Series(0.0, index=d.index)).fillna(0.0)
    wickets_remaining = d.get("wickets_remaining", 10.0 - wickets_lost).fillna(10.0 - wickets_lost).clip(0, 10)
    overs_remaining = d.get("overs_remaining", pd.Series(0.0, index=d.index)).fillna(0.0).clip(0, 20)
    balls_remaining = d.get("balls_remaining", overs_remaining * 6.0).fillna(overs_remaining * 6.0).clip(0, 120)
    score_vs_par = d.get("score_vs_par", pd.Series(0.0, index=d.index)).fillna(0.0)
    over = d.get("over", pd.Series(0.0, index=d.index)).fillna(0.0)

    d["wickets_remaining"] = wickets_remaining
    d["balls_remaining"] = balls_remaining
    d["required_rpb"] = (rrr / 6.0).clip(0, 10)
    d["runs_per_wkt_rem"] = (
        rrr * balls_remaining.clip(1, 120) / 6.0 / wickets_remaining.replace(0, 0.5)
    ).clip(0, 200)
    d["chase_completion"] = (1.0 - d.get("resource_pct", pd.Series(1.0, index=d.index)).fillna(1.0)).clip(0, 1)
    d["death_chase_urgency"] = (rrr / crr.replace(0, np.nan)).fillna(2.0).clip(0.5, 10)
    d["death_feasibility"] = (wickets_remaining / rrr.replace(0, np.nan)).fillna(1.0).clip(0, 5)
    d["tight_finish_zone"] = ((score_vs_par.abs() < 20.0) & (over >= 12)).astype(float)
    return d


def _load_data_and_features() -> tuple[pd.DataFrame, dict[str, list[str]]]:
    df = load_training_data()
    df = add_pitch_features(df)
    df = _ensure_terminal_features(df)
    with open(V14_FEATURES_PATH, encoding="utf-8") as f:
        features = json.load(f)
    return df, features


def _train_predict_phase(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    features: list[str],
    cal_method: str,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    train_oof = oof_phase_predictions(train_df, features)
    bundle = fit_calibrator_bundle(
        train_oof["raw"],
        train_oof["y"],
        train_oof["over"],
        cal_method,
    )

    X_train, avail = safe_X(train_df, features)
    X_test, _ = safe_X(test_df, features)
    y_train = train_df["is_winner"].values
    model = XGBLRBlend()
    model.fit(X_train, y_train)
    raw = model.predict_proba(X_test)[:, 1]
    cal = apply_calibrator_bundle(raw, test_df["over"].values.astype(int), bundle)
    return raw, cal, avail


def _evaluate_candidate(
    df: pd.DataFrame,
    phase_ranges: dict[str, tuple[int, int]],
    feature_sets: dict[str, list[str]],
    cal_methods: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    predictions: list[pd.DataFrame] = []

    for phase, over_range in phase_ranges.items():
        pf = phase_slice(df, over_range)
        train_df = pf[pf["season"].astype(str) < "2025"].copy().reset_index(drop=True)
        test_df = pf[pf["season"].astype(str) >= "2025"].copy().reset_index(drop=True)
        if train_df.empty or test_df.empty:
            continue
        raw, cal, avail = _train_predict_phase(
            train_df,
            test_df,
            feature_sets[phase],
            cal_methods.get(phase, "platt"),
        )
        y = test_df["is_winner"].astype(float).to_numpy()
        rows.append(
            {
                "phase": phase,
                "n": int(len(y)),
                "n_features": len(avail),
                "brier_raw": float(brier_score_loss(y, raw)),
                "brier_cal": float(brier_score_loss(y, cal)),
                "logloss_raw": float(log_loss(y, np.clip(raw, 1e-6, 1 - 1e-6), labels=[0, 1])),
                "logloss_cal": float(log_loss(y, np.clip(cal, 1e-6, 1 - 1e-6), labels=[0, 1])),
                "mean_pred_cal": float(np.mean(cal)),
                "actual_wr": float(np.mean(y)),
                "gap_pp_cal": float((np.mean(cal) - np.mean(y)) * 100.0),
            }
        )
        out = test_df[
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
                "resource_win_prob",
            ]
        ].copy()
        out["phase"] = phase
        out["raw_pred"] = raw
        out["cal_pred"] = cal
        predictions.append(out)

    pred_df = pd.concat(predictions, ignore_index=True)
    metric_df = pd.DataFrame(rows)
    overall = {
        "phase": "overall",
        "n": int(len(pred_df)),
        "n_features": np.nan,
        "brier_raw": float(brier_score_loss(pred_df["is_winner"], pred_df["raw_pred"])),
        "brier_cal": float(brier_score_loss(pred_df["is_winner"], pred_df["cal_pred"])),
        "logloss_raw": float(log_loss(pred_df["is_winner"], np.clip(pred_df["raw_pred"], 1e-6, 1 - 1e-6), labels=[0, 1])),
        "logloss_cal": float(log_loss(pred_df["is_winner"], np.clip(pred_df["cal_pred"], 1e-6, 1 - 1e-6), labels=[0, 1])),
        "mean_pred_cal": float(pred_df["cal_pred"].mean()),
        "actual_wr": float(pred_df["is_winner"].mean()),
        "gap_pp_cal": float((pred_df["cal_pred"].mean() - pred_df["is_winner"].mean()) * 100.0),
    }
    metric_df = pd.concat([metric_df, pd.DataFrame([overall])], ignore_index=True)
    return metric_df, pred_df


def _bucket_label(values: pd.Series, bins: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(values, bins=bins, labels=labels, include_lowest=True, right=False).astype(str)


def _build_eda(pred_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mid = pred_df[pred_df["phase"].isin(["mid", "early_mid", "late_mid"])].copy()
    mid["prob_bin"] = _bucket_label(
        mid["cal_pred"],
        [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01],
        ["00-10", "10-20", "20-30", "30-40", "40-50", "50-60", "60-70", "70-80", "80-90", "90-100"],
    )
    mid["chase_type"] = np.select(
        [mid["target_above_par"] < -20, mid["target_above_par"] > 20],
        ["low", "high"],
        default="par",
    )
    by_over = (
        mid.groupby(["phase", "over"], dropna=False)
        .agg(
            n=("is_winner", "size"),
            mean_pred=("cal_pred", "mean"),
            actual_wr=("is_winner", "mean"),
            brier=("cal_pred", lambda p: brier_score_loss(mid.loc[p.index, "is_winner"], p)),
            target_above_par=("target_above_par", "mean"),
            required_run_rate=("required_run_rate", "mean"),
        )
        .reset_index()
    )
    by_over["gap_pp"] = (by_over["mean_pred"] - by_over["actual_wr"]) * 100.0

    by_bucket = (
        mid.groupby(["phase", "chase_type", "prob_bin"], dropna=False)
        .agg(
            n=("is_winner", "size"),
            mean_pred=("cal_pred", "mean"),
            actual_wr=("is_winner", "mean"),
        )
        .reset_index()
    )
    by_bucket = by_bucket[by_bucket["n"] > 0].copy()
    by_bucket["gap_pp"] = (by_bucket["mean_pred"] - by_bucket["actual_wr"]) * 100.0
    return by_over, by_bucket


def _feature_sets(v14_features: dict[str, list[str]]) -> dict[str, tuple[dict[str, tuple[int, int]], dict[str, list[str]], dict[str, str]]]:
    base_mid = list(v14_features["mid"])
    terminal = [feature for feature in TERMINAL_CANDIDATES if feature not in base_mid]
    mid_plus_terminal = base_mid + terminal

    base_sets = {phase: list(features) for phase, features in v14_features.items()}
    terminal_sets = {phase: list(features) for phase, features in v14_features.items()}
    terminal_sets["mid"] = mid_plus_terminal

    split_same = {
        "pp": list(v14_features["pp"]),
        "early_mid": base_mid,
        "late_mid": base_mid,
        "death": list(v14_features["death"]),
    }
    split_late_terminal = {
        "pp": list(v14_features["pp"]),
        "early_mid": base_mid,
        "late_mid": mid_plus_terminal,
        "death": list(v14_features["death"]),
    }
    split_both_terminal = {
        "pp": list(v14_features["pp"]),
        "early_mid": mid_plus_terminal,
        "late_mid": mid_plus_terminal,
        "death": list(v14_features["death"]),
    }
    return {
        "v14_baseline": (BASE_PHASE_RANGES, base_sets, CAL_METHODS_V12),
        "single_mid_terminal": (BASE_PHASE_RANGES, terminal_sets, CAL_METHODS_V12),
        "split_same_features": (
            SPLIT_PHASE_RANGES,
            split_same,
            {"pp": "isotonic", "early_mid": "platt", "late_mid": "platt", "death": "isotonic"},
        ),
        "split_late_terminal": (
            SPLIT_PHASE_RANGES,
            split_late_terminal,
            {"pp": "isotonic", "early_mid": "platt", "late_mid": "platt", "death": "isotonic"},
        ),
        "split_both_terminal": (
            SPLIT_PHASE_RANGES,
            split_both_terminal,
            {"pp": "isotonic", "early_mid": "platt", "late_mid": "platt", "death": "isotonic"},
        ),
    }


def _terminal_feature_eda(df: pd.DataFrame, mid_features: list[str]) -> pd.DataFrame:
    rows = []
    mid = phase_slice(df, (7, 15))
    y = mid["is_winner"]
    for feature in TERMINAL_CANDIDATES:
        if feature not in mid.columns:
            continue
        rows.append(
            {
                "feature": feature,
                "in_current_mid": feature in mid_features,
                "mean": float(mid[feature].mean()),
                "std": float(mid[feature].std(ddof=0)),
                "corr_all_mid": float(mid[feature].corr(y)),
                "corr_early_mid": float(mid[mid["over"].between(7, 11)][feature].corr(mid[mid["over"].between(7, 11)]["is_winner"])),
                "corr_late_mid": float(mid[mid["over"].between(12, 15)][feature].corr(mid[mid["over"].between(12, 15)]["is_winner"])),
            }
        )
    out = pd.DataFrame(rows)
    out["abs_corr_late"] = out["corr_late_mid"].abs()
    return out.sort_values(["abs_corr_late", "feature"], ascending=[False, True]).reset_index(drop=True)


def _write_report(summary: pd.DataFrame, terminal_eda: pd.DataFrame) -> None:
    best = summary[summary["phase"].eq("overall")].sort_values("brier_cal").iloc[0]
    mid_summary = summary[summary["phase"].isin(["mid", "early_mid", "late_mid"])].copy()

    def md_table(df: pd.DataFrame) -> str:
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

    lines = [
        "# IPL v14 MID Terminal-Feature Experiment",
        "",
        "Split: train seasons < 2025, test seasons >= 2025.",
        "",
        "## Best Candidate",
        "",
        f"- Best overall calibrated Brier: `{best['candidate']}` = `{best['brier_cal']:.5f}`.",
        "",
        "## Overall Metrics",
        "",
        md_table(
            summary[summary["phase"].eq("overall")][
                ["candidate", "n", "brier_raw", "brier_cal", "logloss_cal", "gap_pp_cal"]
            ].sort_values("brier_cal")
        ),
        "",
        "## MID Metrics",
        "",
        md_table(
            mid_summary[
                ["candidate", "phase", "n", "n_features", "brier_raw", "brier_cal", "logloss_cal", "gap_pp_cal"]
            ].sort_values(["candidate", "phase"])
        ),
        "",
        "## Terminal Feature EDA",
        "",
        md_table(terminal_eda),
        "",
    ]
    (OUT_DIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading IPL v14 training data...")
    df, v14_features = _load_data_and_features()
    print(f"Rows: {len(df):,}; seasons: {sorted(df['season'].astype(str).unique())}")

    terminal_eda = _terminal_feature_eda(df, v14_features["mid"])
    terminal_eda.to_csv(OUT_DIR / "terminal_feature_eda.csv", index=False)

    all_metrics = []
    for name, (phase_ranges, feature_sets, cal_methods) in _feature_sets(v14_features).items():
        print(f"\nRunning candidate: {name}")
        metrics, pred_df = _evaluate_candidate(df, phase_ranges, feature_sets, cal_methods)
        metrics.insert(0, "candidate", name)
        pred_df.insert(0, "candidate", name)
        metrics.to_csv(OUT_DIR / f"{name}_metrics.csv", index=False)
        pred_df.to_csv(OUT_DIR / f"{name}_predictions.csv", index=False)
        by_over, by_bucket = _build_eda(pred_df)
        by_over.to_csv(OUT_DIR / f"{name}_mid_by_over.csv", index=False)
        by_bucket.to_csv(OUT_DIR / f"{name}_mid_by_bucket.csv", index=False)
        all_metrics.append(metrics)
        overall = metrics[metrics["phase"].eq("overall")].iloc[0]
        print(
            f"  overall brier_cal={overall['brier_cal']:.5f} "
            f"logloss_cal={overall['logloss_cal']:.5f} gap={overall['gap_pp_cal']:+.2f}pp"
        )

    summary = pd.concat(all_metrics, ignore_index=True)
    summary.to_csv(OUT_DIR / "summary_metrics.csv", index=False)
    _write_report(summary, terminal_eda)
    print(f"\nSaved experiment artifacts to {OUT_DIR}")


if __name__ == "__main__":
    main()
