#!/usr/bin/env python3
"""
Train Inn2 Phase×Target-Category calibrators.

Runs 5-fold time-series OOF on the trained model, then fits 9 isotonic
calibrators (3 phases × 3 target categories) on the OOF predictions.

Phases:   PP (overs 1-6), Mid (overs 7-15), Death (overs 16-20)
Target:   below_par (<-15 vs par), on_par (-15 to +15), above_par (>+15)

Usage:
    python scripts/train_phase_target_calibrators.py \\
        --model-dir models/ipl_v6 \\
        --input-file data/ipl_features_latest/training.parquet

Output:
    {model-dir}/phase_target_calibrators.pkl
"""

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bbl_pipeline.training.trainer import XGBLogRegEnsemble
from bbl_pipeline.training.evaluation import TimeSeriesCalibrationSplit


PHASE_BINS = [0, 6, 15, 20]
PHASE_LABELS = ["PP", "Mid", "Death"]
TARGET_BINS = [-9999, -15, 15, 9999]
TARGET_LABELS = ["below_par", "on_par", "above_par"]


def _apply_per_over_cal(probs: np.ndarray, overs: pd.Series, innings: pd.Series, iso_dict: dict) -> np.ndarray:
    """Apply per-over isotonic calibrators if available, else return raw probs."""
    result = probs.copy()
    for idx, (p, ov, inn) in enumerate(zip(probs, overs, innings)):
        key = f"inn{int(inn)}_over{int(ov)}"
        cal = iso_dict.get(key)
        if cal is not None:
            result[idx] = float(cal.transform([[p]]).flatten()[0])
    return np.clip(result, 1e-6, 1 - 1e-6)


def main():
    parser = argparse.ArgumentParser(description="Train Inn2 Phase×Target calibrators")
    parser.add_argument("--model-dir", required=True, help="Model directory (e.g. models/ipl_v6)")
    parser.add_argument("--input-file", required=True, help="Training parquet")
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--target-below", type=float, default=-15.0, help="below_par threshold (vs par)")
    parser.add_argument("--target-above", type=float, default=15.0, help="above_par threshold (vs par)")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    model_path = model_dir / "champion_model.joblib"
    iso_path = model_dir / "isotonic_calibrator.pkl"

    print(f"Loading model from {model_path}")
    model: XGBLogRegEnsemble = joblib.load(model_path)
    iso_dict = {}
    if iso_path.exists():
        iso_data = joblib.load(iso_path)
        iso_dict = iso_data.get("per_over_calibrators", {})
        print(f"Loaded {len(iso_dict)} per-over calibrators")

    print(f"Loading features from {args.input_file}")
    df = pd.read_parquet(args.input_file)

    # Keep only inn2 rows for calibration
    inn2 = df[df.innings == 2].copy()
    top_feats = model.TOP_FEATURES

    # Phase label
    inn2["_phase"] = pd.cut(inn2["over"], bins=PHASE_BINS, labels=PHASE_LABELS)

    # Target category label
    inn2["_tgt_cat"] = pd.cut(
        inn2["target_above_par"], bins=TARGET_BINS, labels=TARGET_LABELS
    )

    print(f"\nInn2 distribution:")
    print(inn2.groupby(["_phase", "_tgt_cat"], observed=True).size().unstack(fill_value=0))

    # 5-fold time-series OOF
    splitter = TimeSeriesCalibrationSplit(n_splits=args.n_splits)
    X_full = inn2[top_feats]
    y_full = inn2["is_winner"].values

    oof_probs = np.full(len(inn2), np.nan)
    oof_cal_probs = np.full(len(inn2), np.nan)
    inn2_idx = inn2.index

    for fold, (train_idx, _, test_idx) in enumerate(splitter.split(X_full)):
        X_tr, y_tr = X_full.iloc[train_idx], y_full[train_idx]
        X_te = X_full.iloc[test_idx]

        fold_model = XGBLogRegEnsemble(
            xgb_weight=model.xgb_weight,
            n_features=model.n_features,
        )
        fold_model.fit(X_tr, y_tr)
        raw = fold_model.predict_proba(X_te)[:, 1]
        oof_probs[test_idx] = raw

        # Apply per-over calibration
        te_df = inn2.iloc[test_idx]
        cal = _apply_per_over_cal(raw, te_df["over"], te_df["innings"], iso_dict)
        oof_cal_probs[test_idx] = cal

        print(f"  Fold {fold+1}: n_test={len(test_idx)}, Brier_raw={brier_score_loss(y_full[test_idx], raw):.4f}")

    valid = ~np.isnan(oof_cal_probs)
    print(f"\nOOF overall: Brier_raw={brier_score_loss(y_full[valid], oof_probs[valid]):.4f} "
          f"Brier_perover_cal={brier_score_loss(y_full[valid], oof_cal_probs[valid]):.4f}")

    # Fit 9 isotonic calibrators: phase × target_cat
    calibrators = {}
    results = []
    inn2_valid = inn2[valid].copy()
    oof_cal_valid = oof_cal_probs[valid]
    y_valid = y_full[valid]

    for phase in PHASE_LABELS:
        for tcat in TARGET_LABELS:
            mask = (inn2_valid["_phase"] == phase) & (inn2_valid["_tgt_cat"] == tcat)
            seg_y = y_valid[mask.values]
            seg_p = oof_cal_valid[mask.values]
            n = mask.sum()

            if n < 100:
                print(f"  SKIP {phase}×{tcat}: n={n} (too few samples)")
                continue

            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(seg_p, seg_y)
            seg_cal = np.clip(iso.predict(seg_p), 1e-6, 1 - 1e-6)

            b_before = brier_score_loss(seg_y, seg_p)
            b_after = brier_score_loss(seg_y, seg_cal)
            bias_before = (seg_p - seg_y).mean()
            bias_after = (seg_cal - seg_y).mean()

            key = f"{phase}_{tcat}"
            calibrators[key] = iso
            results.append({
                "phase": phase, "tgt_cat": tcat, "n": n,
                "brier_before": round(b_before, 4), "brier_after": round(b_after, 4),
                "improvement_pct": round((b_after - b_before) / b_before * 100, 2),
                "bias_before": round(bias_before, 4), "bias_after": round(bias_after, 4),
            })
            print(f"  {phase:5s}x{tcat:9s} n={n:5d}: Brier {b_before:.4f}->{b_after:.4f} "
                  f"({(b_after-b_before)/b_before*100:+.1f}%)  bias {bias_before:+.4f}->{bias_after:+.4f}")

    results_df = pd.DataFrame(results)
    print(f"\nSummary:\n{results_df.to_string(index=False)}")

    # Save
    out = {
        "calibrators": calibrators,
        "phases": PHASE_LABELS,
        "target_cats": TARGET_LABELS,
        "target_below_threshold": args.target_below,
        "target_above_threshold": args.target_above,
        "phase_bins": PHASE_BINS,
        "target_bins": TARGET_BINS,
        "results": results,
    }
    out_path = model_dir / "phase_target_calibrators.pkl"
    joblib.dump(out, out_path)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
