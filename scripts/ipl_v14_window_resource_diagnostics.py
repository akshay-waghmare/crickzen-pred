"""Diagnose where window-guarded resource hurts v14.

Runs phase-level variants and saves row-level OOS predictions so regressions can
be sliced by phase window and target bucket.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbl_pipeline.training.blend_model import XGBLRBlend  # noqa: E402
from ipl_v13_mid_split_common import (  # noqa: E402
    CAL_METHODS_V12,
    PHASE_RANGES_V12,
    apply_calibrator_bundle,
    fit_calibrator_bundle,
    oof_phase_predictions,
    ordered_unique,
    phase_slice,
    safe_X,
)
from ipl_v14_window_guarded_resource_experiment import (  # noqa: E402
    WINDOW_RESOURCE,
    WINDOW_RESOURCE_DELTA,
    add_window_guarded_resource,
)
from ipl_v15_context_resource_experiment import build_v14_features, print_table  # noqa: E402
from ipl_resource_baseline_v2_experiment import prepare_data  # noqa: E402


OUT_DIR = Path("models/ipl_v14_window_guarded_resource")
PRED_PATH = OUT_DIR / "diagnostic_oos_predictions.csv"
METRIC_PATH = OUT_DIR / "diagnostic_segment_metrics.csv"
SUMMARY_PATH = OUT_DIR / "diagnostic_variant_summary.csv"


def replace_resource(features: list[str]) -> list[str]:
    return ordered_unique([
        WINDOW_RESOURCE if feature == "resource_win_prob" else feature
        for feature in features
    ])


def add_delta(features: list[str]) -> list[str]:
    return ordered_unique(features + [WINDOW_RESOURCE_DELTA])


def build_variants(v14: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    return {
        "v14_original": v14,
        "replace_all": {phase: replace_resource(features) for phase, features in v14.items()},
        "replace_pp_only": {
            "pp": replace_resource(v14["pp"]),
            "mid": v14["mid"],
            "death": v14["death"],
        },
        "replace_mid_only": {
            "pp": v14["pp"],
            "mid": replace_resource(v14["mid"]),
            "death": v14["death"],
        },
        "delta_all": {phase: add_delta(features) for phase, features in v14.items()},
        "delta_pp_only": {
            "pp": add_delta(v14["pp"]),
            "mid": v14["mid"],
            "death": v14["death"],
        },
        "delta_mid_only": {
            "pp": v14["pp"],
            "mid": add_delta(v14["mid"]),
            "death": v14["death"],
        },
    }


def metric_dict(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    pred = np.clip(np.asarray(pred, dtype=float), 1e-7, 1.0 - 1e-7)
    return {
        "brier": float(brier_score_loss(y, pred)),
        "logloss": float(log_loss(y, pred, labels=[0, 1])),
        "mean_pred": float(pred.mean()),
        "actual_wr": float(np.asarray(y, dtype=float).mean()),
        "gap_pp": float((pred.mean() - np.asarray(y, dtype=float).mean()) * 100.0),
    }


def evaluate_variant(df: pd.DataFrame, version: str, features_by_phase: dict[str, list[str]]) -> pd.DataFrame:
    train_seasons = {season for season in sorted(df["season"].unique()) if season < "2025"}
    test_seasons = {season for season in sorted(df["season"].unique()) if season >= "2025"}
    parts = []
    for phase, over_range in PHASE_RANGES_V12.items():
        pf = phase_slice(df, over_range)
        train_df = pf[pf["season"].isin(train_seasons)].copy().reset_index(drop=True)
        test_df = pf[pf["season"].isin(test_seasons)].copy().reset_index(drop=True)
        features = features_by_phase[phase]
        train_oof = oof_phase_predictions(train_df, features)
        bundle = fit_calibrator_bundle(
            train_oof["raw"],
            train_oof["y"],
            train_oof["over"],
            CAL_METHODS_V12[phase],
        )
        x_train, _ = safe_X(train_df, features)
        x_test, _ = safe_X(test_df, features)
        model = XGBLRBlend()
        model.fit(x_train, train_df["is_winner"].values)
        raw = model.predict_proba(x_test)[:, 1]
        cal = apply_calibrator_bundle(raw, test_df["over"].values.astype(int), bundle)
        out = test_df[
            [
                "match_id",
                "season",
                "over",
                "ball",
                "is_winner",
                "target_above_par",
                "resource_win_prob",
                WINDOW_RESOURCE,
                WINDOW_RESOURCE_DELTA,
            ]
        ].copy()
        out["phase"] = phase
        out["version"] = version
        out["raw_pred"] = raw
        out["cal_pred"] = cal
        parts.append(out)
    return pd.concat(parts, ignore_index=True)


def segment_metrics(pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    pred = pred.copy()
    pred["target_bucket"] = np.select(
        [pred["target_above_par"] < -20.0, pred["target_above_par"] > 20.0],
        ["below_par_easy", "above_par_hard"],
        default="par",
    )
    segments = {
        "overall": pd.Series(True, index=pred.index),
        "pp_0_6": pred["over"].between(0, 6),
        "early_mid_7_12": pred["over"].between(7, 12),
        "late_mid_13_15": pred["over"].between(13, 15),
        "full_mid_7_15": pred["over"].between(7, 15),
        "death_16_20": pred["over"].between(16, 20),
    }
    for version, version_df in pred.groupby("version"):
        for segment, mask in segments.items():
            sub = version_df[mask.loc[version_df.index]]
            if len(sub) == 0:
                continue
            metrics = metric_dict(sub["is_winner"].values, sub["cal_pred"].values)
            rows.append({"version": version, "segment": segment, "target_bucket": "all", "n": len(sub), **metrics})
            for bucket, bucket_df in sub.groupby("target_bucket"):
                if len(bucket_df) < 30:
                    continue
                metrics = metric_dict(bucket_df["is_winner"].values, bucket_df["cal_pred"].values)
                rows.append(
                    {
                        "version": version,
                        "segment": segment,
                        "target_bucket": bucket,
                        "n": len(bucket_df),
                        **metrics,
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Preparing data with window-guarded resource...")
    df = prepare_data()
    df, _ = add_window_guarded_resource(df)
    v14 = build_v14_features()
    variants = build_variants(v14)

    predictions = []
    for version, features in variants.items():
        print(f"Evaluating {version}...")
        predictions.append(evaluate_variant(df, version, features))

    pred_df = pd.concat(predictions, ignore_index=True)
    metrics_df = segment_metrics(pred_df)
    summary = metrics_df[
        (metrics_df["segment"] == "overall")
        & (metrics_df["target_bucket"] == "all")
    ].sort_values(["brier", "logloss"])

    pred_df.to_csv(PRED_PATH, index=False)
    metrics_df.to_csv(METRIC_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)

    print_table(summary, "Variant summary")
    focus = metrics_df[
        metrics_df["segment"].isin(["pp_0_6", "early_mid_7_12", "late_mid_13_15", "full_mid_7_15", "death_16_20"])
        & metrics_df["target_bucket"].isin(["all", "par", "above_par_hard", "below_par_easy"])
    ].sort_values(["segment", "target_bucket", "brier"])
    print_table(focus, "Diagnostic segment metrics")
    print(f"\nSaved diagnostics to {OUT_DIR}")


if __name__ == "__main__":
    main()
