"""
IPL v12 vs v14 — Calibration Curve & Confidence Bucket Analysis
================================================================
OOS only (train<2025, test=2025+2026). Shows:
  - Confidence buckets: 0.50-0.60, 0.60-0.70, 0.70-0.80, 0.80+
    (symmetric: also mirrors 0.20-0.30, 0.30-0.40, 0.40-0.50 from the favourite's perspective)
  - Full calibration curve (10 uniform bins) per phase
  - ECE per bucket + mean calibration error

Usage:
    python scripts/ipl_v12_v14_calibration_curve.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ipl_v13_mid_split_common import (  # noqa: E402
    CAL_METHODS_V12,
    PHASE_RANGES_V12,
    apply_calibrator_bundle,
    fit_calibrator_bundle,
    load_training_data,
    load_v12_features,
    oof_phase_predictions,
    ordered_unique,
    phase_slice,
    safe_X,
)
from build_ipl_v14_pitch_features import add_pitch_features  # noqa: E402
from bbl_pipeline.training.blend_model import XGBLRBlend

PP_PITCH_FEATURES    = ["pp_score_vs_venue", "pp_wkts_vs_venue", "death_rr_vs_venue", "death_wkts_vs_venue"]
MID_PITCH_FEATURES   = ["pp_wkts_vs_venue"]
DEATH_PITCH_FEATURES = ["inn1_pp_wickets", "mid_avg_boundary18_vs_venue", "avg_boundary18_vs_venue"]

CONFIDENCE_BUCKETS = [
    (0.50, 0.60, "50-60%"),
    (0.60, 0.70, "60-70%"),
    (0.70, 0.80, "70-80%"),
    (0.80, 1.01, "80%+  "),
]

CAL_BINS_10 = np.linspace(0.0, 1.0, 11)   # 10 uniform bins


def run_oos(df: pd.DataFrame, phase_feats: dict) -> dict[str, dict]:
    """Return {phase: {raw, cal, y, over}} for OOS test set (>=2025)."""
    train_s = {s for s in df["season"].unique() if s < "2025"}
    test_s  = {s for s in df["season"].unique() if s >= "2025"}
    results: dict[str, dict] = {}

    for phase, over_range in PHASE_RANGES_V12.items():
        pf    = phase_slice(df, over_range)
        pf_tr = pf[pf["season"].isin(train_s)].copy().reset_index(drop=True)
        pf_te = pf[pf["season"].isin(test_s)].copy().reset_index(drop=True)
        if pf_te.empty:
            continue

        oof    = oof_phase_predictions(pf_tr, phase_feats[phase])
        bundle = fit_calibrator_bundle(oof["raw"], oof["y"], oof["over"], CAL_METHODS_V12[phase])

        X_tr, _ = safe_X(pf_tr, phase_feats[phase])
        X_te, _ = safe_X(pf_te, phase_feats[phase])
        y_tr    = pf_tr["is_winner"].values
        y_te    = pf_te["is_winner"].values.astype(float)
        over_te = pf_te["over"].values.astype(int)

        mdl = XGBLRBlend()
        mdl.fit(X_tr, y_tr)
        raw = mdl.predict_proba(X_te)[:, 1]
        cal = apply_calibrator_bundle(raw, over_te, bundle)

        results[phase] = {"raw": raw, "cal": cal, "y": y_te, "over": over_te}
    return results


def combine_phases(res: dict) -> dict:
    all_raw = np.concatenate([res[p]["raw"] for p in res])
    all_cal = np.concatenate([res[p]["cal"] for p in res])
    all_y   = np.concatenate([res[p]["y"]   for p in res])
    return {"raw": all_raw, "cal": all_cal, "y": all_y}


def confidence_bucket_table(
    v12_res: dict, v14_res: dict, label: str
) -> pd.DataFrame:
    """Symmetric bucket analysis: fold predictions so p always represents favourite."""
    rows = []
    phases = list(PHASE_RANGES_V12.keys()) + ["overall"]

    for phase in phases:
        if phase == "overall":
            r12 = combine_phases(v12_res)
            r14 = combine_phases(v14_res)
        else:
            if phase not in v12_res:
                continue
            r12 = v12_res[phase]
            r14 = v14_res[phase]

        y = r12["y"]

        # Symmetric: map each prediction to "favourite perspective"
        # p_fav = max(p, 1-p); actual_fav = 1 if winner == favourite else 0
        for model_label, preds in [("v12", r12["cal"]), ("v14", r14["cal"])]:
            p_fav  = np.where(preds >= 0.5, preds, 1.0 - preds)
            y_fav  = np.where(preds >= 0.5, y, 1.0 - y)

            for lo, hi, bucket_label in CONFIDENCE_BUCKETS:
                mask = (p_fav >= lo) & (p_fav < hi)
                if mask.sum() == 0:
                    continue
                mean_pred   = float(p_fav[mask].mean())
                actual_wr   = float(y_fav[mask].mean())
                cal_error   = abs(mean_pred - actual_wr)
                n           = int(mask.sum())
                rows.append({
                    "split": label,
                    "phase": phase.upper(),
                    "model": model_label,
                    "bucket": bucket_label,
                    "n": n,
                    "mean_pred": round(mean_pred, 4),
                    "actual_wr": round(actual_wr, 4),
                    "cal_error": round(cal_error, 4),
                    "over_under": "over" if mean_pred > actual_wr else "under",
                })
    return pd.DataFrame(rows)


def calibration_curve_table(
    v12_res: dict, v14_res: dict, label: str, n_bins: int = 10
) -> pd.DataFrame:
    rows = []
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    phases = list(PHASE_RANGES_V12.keys()) + ["overall"]

    for phase in phases:
        if phase == "overall":
            r12 = combine_phases(v12_res)
            r14 = combine_phases(v14_res)
        else:
            if phase not in v12_res:
                continue
            r12 = v12_res[phase]
            r14 = v14_res[phase]

        y = r12["y"]
        for model_label, preds in [("v12", r12["cal"]), ("v14", r14["cal"])]:
            for lo, hi in zip(bins[:-1], bins[1:]):
                mask = (preds >= lo) & (preds < hi)
                if mask.sum() == 0:
                    continue
                rows.append({
                    "split": label,
                    "phase": phase.upper(),
                    "model": model_label,
                    "bin_lo": round(float(lo), 2),
                    "bin_hi": round(float(hi), 2),
                    "n": int(mask.sum()),
                    "mean_pred": round(float(preds[mask].mean()), 4),
                    "actual_wr": round(float(y[mask].mean()), 4),
                    "cal_error": round(abs(float(preds[mask].mean()) - float(y[mask].mean())), 4),
                })
    return pd.DataFrame(rows)


def print_bucket_table(df: pd.DataFrame, phase: str) -> None:
    sub = df[df["phase"] == phase.upper()].copy()
    if sub.empty:
        return
    print(f"\n  ── {phase.upper()} ──")
    hdr = f"  {'Bucket':<8} {'n_v12':>7} {'n_v14':>7} | {'v12 pred':>9} {'v12 act':>9} {'v12 err':>9} | {'v14 pred':>9} {'v14 act':>9} {'v14 err':>9} | {'Δerr':>8}"
    print(hdr)
    print("  " + "-" * 90)
    for bucket_label in [b[2] for b in CONFIDENCE_BUCKETS]:
        r12 = sub[(sub["model"] == "v12") & (sub["bucket"] == bucket_label)]
        r14 = sub[(sub["model"] == "v14") & (sub["bucket"] == bucket_label)]
        if r12.empty and r14.empty:
            continue
        n12  = int(r12["n"].values[0]) if not r12.empty else 0
        n14  = int(r14["n"].values[0]) if not r14.empty else 0
        p12  = r12["mean_pred"].values[0] if not r12.empty else float("nan")
        a12  = r12["actual_wr"].values[0] if not r12.empty else float("nan")
        e12  = r12["cal_error"].values[0]  if not r12.empty else float("nan")
        p14  = r14["mean_pred"].values[0] if not r14.empty else float("nan")
        a14  = r14["actual_wr"].values[0] if not r14.empty else float("nan")
        e14  = r14["cal_error"].values[0]  if not r14.empty else float("nan")
        delta = e14 - e12
        flag = "✅" if delta < -0.005 else ("⚠️" if delta > 0.005 else "  ")
        print(f"  {bucket_label:<8} {n12:>7} {n14:>7} | {p12:>9.4f} {a12:>9.4f} {e12:>9.4f} | {p14:>9.4f} {a14:>9.4f} {e14:>9.4f} | {delta:>+8.4f} {flag}")


def main() -> None:
    print("Loading data + building pitch features...")
    df = load_training_data()
    df = add_pitch_features(df)
    v12_feats = load_v12_features()
    v14_feats = {
        "pp":    ordered_unique(v12_feats["pp"]    + PP_PITCH_FEATURES),
        "mid":   ordered_unique(v12_feats["mid"]   + MID_PITCH_FEATURES),
        "death": ordered_unique(v12_feats["death"] + DEATH_PITCH_FEATURES),
    }

    print("Running OOS for v12 ...")
    oos_v12 = run_oos(df, v12_feats)
    print("Running OOS for v14 ...")
    oos_v14 = run_oos(df, v14_feats)

    bucket_df = confidence_bucket_table(oos_v12, oos_v14, "OOS")
    curve_df  = calibration_curve_table(oos_v12, oos_v14, "OOS")

    # ── Print bucket tables ──
    print(f"\n{'=' * 100}")
    print("  CONFIDENCE BUCKET ANALYSIS — OOS (test: 2025+2026)  |  symmetric (favourite-perspective)")
    print(f"{'=' * 100}")
    print("  Columns: n = # balls in bucket | pred = mean model prob | act = actual win rate | err = |pred-act|")
    print("  Δerr = v14_err - v12_err   (negative = v14 better calibrated in this bucket)")

    for phase in ["OVERALL", "PP", "MID", "DEATH"]:
        print_bucket_table(bucket_df, phase)

    # ── Print calibration curve (10-bin) ──
    print(f"\n{'=' * 100}")
    print("  CALIBRATION CURVE — OOS — OVERALL (10 uniform bins 0→1)")
    print(f"{'=' * 100}")
    print(f"  {'Bin':<12} {'n_v12':>7} {'n_v14':>7} | {'v12 pred':>9} {'v12 act':>9} {'v12 err':>9} | {'v14 pred':>9} {'v14 act':>9} {'v14 err':>9}")
    print("  " + "-" * 85)
    ov = curve_df[(curve_df["phase"] == "OVERALL") & (curve_df["split"] == "OOS")]
    for (lo, hi), grp in ov.groupby(["bin_lo", "bin_hi"]):
        r12 = grp[grp["model"] == "v12"]
        r14 = grp[grp["model"] == "v14"]
        if r12.empty and r14.empty:
            continue
        n12 = int(r12["n"].values[0]) if not r12.empty else 0
        n14 = int(r14["n"].values[0]) if not r14.empty else 0
        p12 = r12["mean_pred"].values[0] if not r12.empty else float("nan")
        a12 = r12["actual_wr"].values[0]  if not r12.empty else float("nan")
        e12 = r12["cal_error"].values[0]  if not r12.empty else float("nan")
        p14 = r14["mean_pred"].values[0] if not r14.empty else float("nan")
        a14 = r14["actual_wr"].values[0]  if not r14.empty else float("nan")
        e14 = r14["cal_error"].values[0]  if not r14.empty else float("nan")
        print(f"  {lo:.1f}–{hi:.1f}      {n12:>7} {n14:>7} | {p12:>9.4f} {a12:>9.4f} {e12:>9.4f} | {p14:>9.4f} {a14:>9.4f} {e14:>9.4f}")

    # ── Save ──
    out_dir = Path("models/ipl_v14_pitch_features")
    bucket_df.to_csv(out_dir / "v12_v14_bucket_calibration.csv", index=False)
    curve_df.to_csv(out_dir  / "v12_v14_calibration_curve.csv",  index=False)
    print(f"\n  Saved: {out_dir}/v12_v14_bucket_calibration.csv")
    print(f"  Saved: {out_dir}/v12_v14_calibration_curve.csv")


if __name__ == "__main__":
    main()
