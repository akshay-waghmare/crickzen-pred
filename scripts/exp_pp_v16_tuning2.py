"""Try pure XGBoost and calibration-by-chase-category experiments."""
import sys, json, pickle
sys.path.insert(0, "src")
sys.path.insert(0, "scripts")
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.isotonic import IsotonicRegression
from xgboost import XGBClassifier

from ipl_v13_mid_split_common import (
    safe_X, phase_slice, PHASE_RANGES_V12, season_folds,
    fit_calibrator_bundle, apply_calibrator_bundle, CAL_METHODS_V12,
    load_training_data, ordered_unique, XGBLRBlend,
)

V15_DIR = Path("models/ipl_v15_wicket_features")
V15_PP_BRIER_CAL = 0.17032
GATE = 0.16180


def add_v16_feats(df):
    inn1_pp_rr = (df["inn1_pp_runs"].fillna(0) / 6.0).replace(0, np.nan)
    df = df.copy()
    df["inn1_pp_run_rate"]      = df["inn1_pp_runs"].fillna(0) / 6.0
    df["pp_run_rate_vs_inn1"]   = (df["current_run_rate"].fillna(0) / inn1_pp_rr).fillna(1.0).clip(0, 3)
    df["below_par_run_cushion"] = (-df["target_above_par"].fillna(0)).clip(lower=0) * (10 - df["wickets_lost"].fillna(0)).clip(lower=0) / 10
    df["above_par_wicket_cost"] = df["target_above_par"].fillna(0).clip(lower=0) * df["wickets_lost"].fillna(0) / 20
    df["chase_diff_x_wickets"]  = df["chase_difficulty"].fillna(1.0) * df["wickets_lost"].fillna(0)
    df["recovery_x_chase"]      = df["recovery_momentum"].fillna(0) * df["chase_category"].fillna(0)
    return df


def run_oof_xgb(pp_df, feats, xgb_params):
    """Season-fold OOF with pure XGBoost."""
    pp_df = pp_df.reset_index(drop=True)
    X, avail = safe_X(pp_df, feats)
    y = pp_df["is_winner"].values
    overs = pp_df["over"].values
    seasons = sorted(pp_df["season"].astype(str).unique().tolist())
    folds = season_folds(seasons, 5)
    raw = np.zeros(len(pp_df))
    for val_seasons in folds:
        tr = ~pp_df["season"].isin(val_seasons)
        va =  pp_df["season"].isin(val_seasons)
        if tr.sum() == 0 or va.sum() == 0:
            continue
        m = XGBClassifier(**xgb_params)
        m.fit(X[tr], y[tr])
        raw[va] = m.predict_proba(X[va])[:, 1]
    bun = fit_calibrator_bundle(raw, y, overs, "isotonic")
    cal = apply_calibrator_bundle(raw, overs, bun)
    return raw, y, overs, bun, float(brier_score_loss(y, raw)), float(brier_score_loss(y, cal)), float(log_loss(y, cal.clip(1e-7, 1-1e-7)))


def run_oof_chase_calibrated(pp_df, feats):
    """v16 model + per-chase-category calibration on top."""
    pp_df = pp_df.reset_index(drop=True)
    X, avail = safe_X(pp_df, feats)
    y = pp_df["is_winner"].values
    overs = pp_df["over"].values
    seasons = sorted(pp_df["season"].astype(str).unique().tolist())
    folds = season_folds(seasons, 5)

    raw = np.zeros(len(pp_df))
    # First pass: standard OOF
    for val_seasons in folds:
        tr = ~pp_df["season"].isin(val_seasons)
        va =  pp_df["season"].isin(val_seasons)
        if tr.sum() == 0 or va.sum() == 0:
            continue
        m = XGBLRBlend()
        m.fit(X[tr], y[tr])
        raw[va] = m.predict_proba(X[va])[:, 1]

    # Second pass: calibrate per chase_category using another OOF loop
    cat_col = pp_df["chase_category"].values
    cal_final = np.zeros(len(pp_df))
    for val_seasons in folds:
        tr = ~pp_df["season"].isin(val_seasons)
        va =  pp_df["season"].isin(val_seasons)
        if tr.sum() == 0 or va.sum() == 0:
            continue
        # Fit per-category calibrators on train OOF predictions
        cat_cals = {}
        for cat in [-1, 0, 1]:
            cat_tr = tr & (cat_col == cat)
            if cat_tr.sum() >= 50:
                iso = IsotonicRegression(out_of_bounds="clip")
                iso.fit(raw[cat_tr], y[cat_tr])
                cat_cals[cat] = iso
        # Apply to val
        va_idx = np.where(va)[0]
        for idx in va_idx:
            cat = cat_col[idx]
            if cat in cat_cals:
                cal_final[idx] = cat_cals[cat].predict([raw[idx]])[0]
            else:
                cal_final[idx] = raw[idx]

    b_cal = float(brier_score_loss(y, cal_final))
    ll_cal = float(log_loss(y, cal_final.clip(1e-7, 1-1e-7)))
    return b_cal, ll_cal


def pct(new, old):
    return f"{(new-old)/old*100:+.2f}%"


def main():
    print("Loading data...")
    df = load_training_data()
    df = add_v16_feats(df)

    v15_feats = json.load(open(V15_DIR / "phase_features.json"))
    V16_NEW = [
        "chase_difficulty", "wickets_times_balls", "wickets_last_30",
        "score_per_wicket", "recovery_momentum", "balls_since_wicket",
        "boundary_pct_last_18", "dot_pct_last_12", "momentum_acceleration",
        "set_batter_exposure", "inn1_pp_run_rate", "pp_run_rate_vs_inn1",
        "below_par_run_cushion", "above_par_wicket_cost",
        "chase_diff_x_wickets", "recovery_x_chase",
    ]
    all_cols = set(df.columns)
    v16_pp = ordered_unique(v15_feats["pp"] + V16_NEW)
    v16_pp = [f for f in v16_pp if f in all_cols]
    pp_df = phase_slice(df, PHASE_RANGES_V12["pp"])
    print(f"PP rows: {len(pp_df)}, v16 features: {len(v16_pp)}\n")

    xgb_params = dict(
        n_estimators=500, max_depth=5, learning_rate=0.02,
        subsample=0.8, colsample_bytree=0.9, min_child_weight=8,
        reg_alpha=0.3, reg_lambda=1.0, tree_method="hist",
        eval_metric="logloss", n_jobs=-1, verbosity=0, random_state=42,
    )

    print("=== D: Pure XGBoost, v16 features ===")
    _, y_d, ov_d, _, br_d, bc_d, ll_d = run_oof_xgb(pp_df, v16_pp, xgb_params)
    g = "✅" if bc_d <= GATE else "❌"
    print(f"  raw={br_d:.5f}  cal={bc_d:.5f}  ll={ll_d:.5f}  {pct(bc_d,V15_PP_BRIER_CAL)}  {g}")

    print("\n=== E: v16 features + per-chase-category calibration ===")
    bc_e, ll_e = run_oof_chase_calibrated(pp_df, v16_pp)
    g = "✅" if bc_e <= GATE else "❌"
    print(f"  cal={bc_e:.5f}  ll={ll_e:.5f}  {pct(bc_e,V15_PP_BRIER_CAL)}  {g}")

    print("\n=== F: Pure XGB, v15 features only ===")
    _, _, _, _, br_f, bc_f, ll_f = run_oof_xgb(pp_df, v15_feats["pp"], xgb_params)
    g = "✅" if bc_f <= GATE else "❌"
    print(f"  raw={br_f:.5f}  cal={bc_f:.5f}  ll={ll_f:.5f}  {pct(bc_f,V15_PP_BRIER_CAL)}  {g}")

    print("\n" + "="*55)
    print(f"V15 baseline: 0.17032 | Gate: {GATE} (5% better)")
    best = min((bc_d, "D-XGB-v16"), (bc_e, "E-chase-cal"), (bc_f, "F-XGB-v15"))
    print(f"Best result: {best[1]} => cal={best[0]:.5f}  {pct(best[0],V15_PP_BRIER_CAL)}")


if __name__ == "__main__":
    main()
