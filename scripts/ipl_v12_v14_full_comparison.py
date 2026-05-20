"""
IPL v12 vs v14 Full Comparison
================================
Generates a comprehensive OOS and OOF comparison between v12 and v14 with:
  - Brier Score, Log Loss, ECE (10-bin)
  - Per phase (PP, MID, DEATH) and overall
  - OOF (in-sample 5-fold) and OOS (train<2025, test>=2025) splits

Usage:
    python scripts/ipl_v12_v14_full_comparison.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ipl_v13_mid_split_common import (  # noqa: E402
    CAL_METHODS_V12,
    PHASE_RANGES_V12,
    apply_calibrator_bundle,
    evaluate_oos,
    fit_calibrator_bundle,
    load_training_data,
    load_v12_features,
    oof_phase_predictions,
    ordered_unique,
    phase_slice,
)
from build_ipl_v14_pitch_features import add_pitch_features  # noqa: E402

PP_PITCH_FEATURES = ["pp_score_vs_venue", "pp_wkts_vs_venue", "death_rr_vs_venue", "death_wkts_vs_venue"]
MID_PITCH_FEATURES = ["pp_wkts_vs_venue"]
DEATH_PITCH_FEATURES = ["inn1_pp_wickets", "mid_avg_boundary18_vs_venue", "avg_boundary18_vs_venue"]


def ece(y_true: np.ndarray, y_pred: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error (uniform-width bins)."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece_val = 0.0
    n = len(y_true)
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (y_pred >= lo) & (y_pred < hi)
        if mask.sum() == 0:
            continue
        frac_pos = float(y_true[mask].mean())
        mean_pred = float(y_pred[mask].mean())
        ece_val += (mask.sum() / n) * abs(frac_pos - mean_pred)
    return float(ece_val)


def metrics(y: np.ndarray, preds: np.ndarray) -> dict[str, float]:
    preds = np.clip(preds, 1e-7, 1 - 1e-7)
    return {
        "brier": round(float(brier_score_loss(y, preds)), 5),
        "logloss": round(float(log_loss(y, preds)), 5),
        "ece": round(float(ece(y, preds)), 5),
        "n": int(len(y)),
    }


def oos_full(df: pd.DataFrame, phase_ranges, phase_features, cal_methods):
    """Like evaluate_oos but returns raw/cal arrays per phase for metric computation."""
    train_seasons = {s for s in sorted(df["season"].unique()) if s < "2025"}
    test_seasons = {s for s in sorted(df["season"].unique()) if s >= "2025"}
    results = {}

    for phase, over_range in phase_ranges.items():
        pf = phase_slice(df, over_range)
        pf_tr = pf[pf["season"].isin(train_seasons)].copy().reset_index(drop=True)
        pf_te = pf[pf["season"].isin(test_seasons)].copy().reset_index(drop=True)
        if pf_te.empty:
            continue

        from ipl_v13_mid_split_common import safe_X, XGBLRBlend  # noqa
        from bbl_pipeline.training.blend_model import XGBLRBlend as _M  # noqa

        train_oof = oof_phase_predictions(pf_tr, phase_features[phase])
        bundle = fit_calibrator_bundle(
            train_oof["raw"], train_oof["y"], train_oof["over"], cal_methods[phase]
        )
        X_tr, avail = safe_X(pf_tr, phase_features[phase])
        X_te, _ = safe_X(pf_te, phase_features[phase])
        y_tr = pf_tr["is_winner"].values
        y_te = pf_te["is_winner"].values.astype(float)
        over_te = pf_te["over"].values.astype(int)

        model = _M()
        model.fit(X_tr, y_tr)
        raw_te = model.predict_proba(X_te)[:, 1]
        cal_te = apply_calibrator_bundle(raw_te, over_te, bundle)

        results[phase] = {
            "raw": raw_te,
            "cal": cal_te,
            "y": y_te,
            "over": over_te,
        }
    return results, sorted(train_seasons), sorted(test_seasons)


def oof_full(df: pd.DataFrame, phase_ranges, phase_features, cal_methods):
    """OOF 5-fold cross-validation - returns raw/cal arrays per phase."""
    results = {}
    for phase, over_range in phase_ranges.items():
        pf = phase_slice(df, over_range)
        oof = oof_phase_predictions(pf, phase_features[phase])
        bundle = fit_calibrator_bundle(oof["raw"], oof["y"], oof["over"], cal_methods[phase])
        cal = apply_calibrator_bundle(oof["raw"], oof["over"], bundle)
        results[phase] = {
            "raw": oof["raw"],
            "cal": cal,
            "y": oof["y"],
            "over": oof["over"],
        }
    return results


def build_comparison_table(v12_res, v14_res, split_label):
    rows = []
    all_v12_raw, all_v12_cal, all_v14_raw, all_v14_cal, all_y = [], [], [], [], []

    for phase in ["pp", "mid", "death"]:
        if phase not in v12_res or phase not in v14_res:
            continue
        r12, r14 = v12_res[phase], v14_res[phase]
        y = r12["y"]
        m12_raw = metrics(y, r12["raw"])
        m12_cal = metrics(y, r12["cal"])
        m14_raw = metrics(y, r14["raw"])
        m14_cal = metrics(y, r14["cal"])

        def pct(new, old):
            return f"{(new - old) / old * 100:+.2f}%" if old else "n/a"

        rows.append({
            "split": split_label,
            "phase": phase.upper(),
            "n": m12_cal["n"],
            # v12
            "v12_brier_raw": m12_raw["brier"],
            "v12_brier_cal": m12_cal["brier"],
            "v12_logloss_cal": m12_cal["logloss"],
            "v12_ece_cal": m12_cal["ece"],
            # v14
            "v14_brier_raw": m14_raw["brier"],
            "v14_brier_cal": m14_cal["brier"],
            "v14_logloss_cal": m14_cal["logloss"],
            "v14_ece_cal": m14_cal["ece"],
            # deltas
            "delta_brier": pct(m14_cal["brier"], m12_cal["brier"]),
            "delta_logloss": pct(m14_cal["logloss"], m12_cal["logloss"]),
            "delta_ece": pct(m14_cal["ece"], m12_cal["ece"]) if m12_cal["ece"] > 0 else "n/a",
        })

        all_v12_raw.extend(r12["raw"]); all_v12_cal.extend(r12["cal"])
        all_v14_raw.extend(r14["raw"]); all_v14_cal.extend(r14["cal"])
        all_y.extend(y)

    y_all = np.array(all_y)
    mo12 = metrics(y_all, np.array(all_v12_cal))
    mo14 = metrics(y_all, np.array(all_v14_cal))
    mo12r = metrics(y_all, np.array(all_v12_raw))
    mo14r = metrics(y_all, np.array(all_v14_raw))

    def pct(new, old):
        return f"{(new - old) / old * 100:+.2f}%" if old else "n/a"

    rows.append({
        "split": split_label,
        "phase": "OVERALL",
        "n": len(y_all),
        "v12_brier_raw": mo12r["brier"],
        "v12_brier_cal": mo12["brier"],
        "v12_logloss_cal": mo12["logloss"],
        "v12_ece_cal": mo12["ece"],
        "v14_brier_raw": mo14r["brier"],
        "v14_brier_cal": mo14["brier"],
        "v14_logloss_cal": mo14["logloss"],
        "v14_ece_cal": mo14["ece"],
        "delta_brier": pct(mo14["brier"], mo12["brier"]),
        "delta_logloss": pct(mo14["logloss"], mo12["logloss"]),
        "delta_ece": pct(mo14["ece"], mo12["ece"]) if mo12["ece"] > 0 else "n/a",
    })
    return pd.DataFrame(rows)


def print_table(df: pd.DataFrame, title: str) -> None:
    print(f"\n{'=' * 110}")
    print(f"  {title}")
    print(f"{'=' * 110}")
    hdr = f"{'Phase':<8} {'n':>7} | {'v12_brier':>10} {'v14_brier':>10} {'Δbrier':>9} | {'v12_ll':>9} {'v14_ll':>9} {'Δll':>9} | {'v12_ece':>8} {'v14_ece':>8} {'Δece':>9}"
    print(hdr)
    print("-" * 110)
    for _, row in df.iterrows():
        print(
            f"{row['phase']:<8} {int(row['n']):>7} | "
            f"{row['v12_brier_cal']:>10.5f} {row['v14_brier_cal']:>10.5f} {row['delta_brier']:>9} | "
            f"{row['v12_logloss_cal']:>9.5f} {row['v14_logloss_cal']:>9.5f} {row['delta_logloss']:>9} | "
            f"{row['v12_ece_cal']:>8.5f} {row['v14_ece_cal']:>8.5f} {row['delta_ece']:>9}"
        )


def main() -> None:
    print("Loading IPL inn2 data with v14 pitch features...")
    df = load_training_data()
    df = add_pitch_features(df)
    v12_feats = load_v12_features()
    v14_feats = {
        "pp": ordered_unique(v12_feats["pp"] + PP_PITCH_FEATURES),
        "mid": ordered_unique(v12_feats["mid"] + MID_PITCH_FEATURES),
        "death": ordered_unique(v12_feats["death"] + DEATH_PITCH_FEATURES),
    }
    print(f"  Total rows: {len(df):,}")

    # ---- OOF ----
    print("\nRunning OOF 5-fold for v12 and v14 (this takes a few minutes)...")
    oof_v12 = oof_full(df, PHASE_RANGES_V12, v12_feats, CAL_METHODS_V12)
    oof_v14 = oof_full(df, PHASE_RANGES_V12, v14_feats, CAL_METHODS_V12)
    oof_table = build_comparison_table(oof_v12, oof_v14, "OOF")

    # ---- OOS ----
    print("\nRunning OOS evaluation (train<2025, test>=2025)...")
    oos_v12, train_s, test_s = oos_full(df, PHASE_RANGES_V12, v12_feats, CAL_METHODS_V12)
    oos_v14, _, _ = oos_full(df, PHASE_RANGES_V12, v14_feats, CAL_METHODS_V12)
    oos_table = build_comparison_table(oos_v12, oos_v14, "OOS")

    print(f"\n  Train seasons: {train_s}")
    print(f"  Test seasons : {test_s}")

    # ---- Print ----
    print_table(oof_table, "OOF 5-FOLD (all IPL data, cross-validated) — calibrated metrics")
    print_table(oos_table, f"OOS (train<2025, test={test_s}) — calibrated metrics")

    # ---- Save ----
    out_dir = Path("models/ipl_v14_pitch_features")
    combined = pd.concat([oof_table, oos_table], ignore_index=True)
    out = out_dir / "v12_v14_full_comparison.csv"
    combined.to_csv(out, index=False)
    print(f"\n  Saved: {out}")

    # ---- Summary ----
    oos_overall = oos_table[oos_table["phase"] == "OVERALL"].iloc[0]
    oof_overall = oof_table[oof_table["phase"] == "OVERALL"].iloc[0]
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"  OOF overall  → Brier {oof_overall['delta_brier']}  LogLoss {oof_overall['delta_logloss']}  ECE {oof_overall['delta_ece']}")
    print(f"  OOS overall  → Brier {oos_overall['delta_brier']}  LogLoss {oos_overall['delta_logloss']}  ECE {oos_overall['delta_ece']}")


if __name__ == "__main__":
    main()
