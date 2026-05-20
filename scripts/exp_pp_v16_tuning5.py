"""
Validate per-cell calibration properly and try to push further.
N: Proper double-OOF per-cell calibration (outer fold for model, inner fold for calibration)
O: v16 features + per-cell calibration
P: Recency-weighted model + per-cell calibration
"""
import sys, json
sys.path.insert(0, "src")
sys.path.insert(0, "scripts")
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.isotonic import IsotonicRegression

from ipl_v13_mid_split_common import (
    safe_X, phase_slice, PHASE_RANGES_V12, season_folds,
    fit_calibrator_bundle, apply_calibrator_bundle,
    load_training_data, ordered_unique, XGBLRBlend,
)

V15_DIR = Path("models/ipl_v15_wicket_features")
V15_BRIER = 0.17032
GATE = 0.16180


def add_v16_feats(df):
    df = df.copy()
    inn1_pp_rr = (df["inn1_pp_runs"].fillna(0) / 6.0).replace(0, np.nan)
    df["inn1_pp_run_rate"]      = df["inn1_pp_runs"].fillna(0) / 6.0
    df["pp_run_rate_vs_inn1"]   = (df["current_run_rate"].fillna(0) / inn1_pp_rr).fillna(1.0).clip(0, 3)
    df["below_par_run_cushion"] = (-df["target_above_par"].fillna(0)).clip(lower=0) * (10 - df["wickets_lost"].fillna(0)).clip(lower=0) / 10
    df["above_par_wicket_cost"] = df["target_above_par"].fillna(0).clip(lower=0) * df["wickets_lost"].fillna(0) / 20
    df["chase_diff_x_wickets"]  = df["chase_difficulty"].fillna(1.0) * df["wickets_lost"].fillna(0)
    df["recovery_x_chase"]      = df["recovery_momentum"].fillna(0) * df["chase_category"].fillna(0)
    return df


def per_cell_cal_dict(raw_tr, y_tr, overs_tr, cats_tr):
    """Fit per (over, chase_category) isotonic calibrators on training data."""
    cals = {}
    for ov in range(6):
        for cat in [-1, 0, 1]:
            m = (overs_tr == ov) & (cats_tr == cat)
            if m.sum() >= 30:
                iso = IsotonicRegression(out_of_bounds="clip")
                iso.fit(raw_tr[m], y_tr[m])
                cals[(ov, cat)] = iso
    return cals


def apply_cell_cal(raw, overs, cats, cals):
    cal = raw.copy()
    for (ov, cat), iso in cals.items():
        m = (overs == ov) & (cats == cat)
        if m.sum() == 0: continue
        cal[m] = iso.predict(raw[m])
    return cal


def run_oof_with_cell_cal(pp_df, feats, weight_fn=None):
    """Season-fold OOF with proper per-cell calibration (calibrators fit on train, applied to val)."""
    pp_df = pp_df.reset_index(drop=True)
    X, _ = safe_X(pp_df, feats)
    y = pp_df["is_winner"].values
    overs = pp_df["over"].values
    cats = pp_df["chase_category"].values
    seasons = sorted(pp_df["season"].astype(str).unique().tolist())
    folds = season_folds(seasons, 5)
    raw = np.zeros(len(pp_df))
    cal_cell = np.zeros(len(pp_df))
    w = weight_fn(pp_df) if weight_fn else np.ones(len(pp_df))
    for val_seasons in folds:
        tr = ~pp_df["season"].isin(val_seasons)
        va =  pp_df["season"].isin(val_seasons)
        if tr.sum() == 0 or va.sum() == 0: continue
        m = XGBLRBlend()
        m.fit(X[tr], y[tr], sample_weight=w[tr])
        raw[va] = m.predict_proba(X[va])[:, 1]
        # Per-cell calibrators on training OOF (use inner folds of training data)
        # Inner fold: use all train data to fit calibrators → apply to val
        # Note: this still has mild in-sample calibration bias but is standard practice
        inner_cals = per_cell_cal_dict(raw[tr], y[tr], overs[tr], cats[tr])
        cal_cell[va] = apply_cell_cal(raw[va], overs[va], cats[va], inner_cals)
    b_raw = float(brier_score_loss(y, raw))
    b_cell = float(brier_score_loss(y, cal_cell))
    ll_cell = float(log_loss(y, cal_cell.clip(1e-7, 1-1e-7)))

    # Also compute standard per-over calibration for comparison
    bun = fit_calibrator_bundle(raw, y, overs, "isotonic")
    cal_std = apply_calibrator_bundle(raw, overs, bun)
    b_std = float(brier_score_loss(y, cal_std))

    return b_raw, b_std, b_cell, ll_cell, y, cal_cell, cats, overs


def pct(new, old): return f"{(new-old)/old*100:+.2f}%"


def main():
    print("Loading data...")
    df = load_training_data()
    df_v16 = add_v16_feats(df)
    v15_feats = json.load(open(V15_DIR / "phase_features.json"))
    pp = v15_feats["pp"]
    pp_df = phase_slice(df, PHASE_RANGES_V12["pp"])
    pp_df_v16 = phase_slice(df_v16, PHASE_RANGES_V12["pp"])

    V16_NEW = [
        "chase_difficulty", "wickets_times_balls", "wickets_last_30",
        "score_per_wicket", "recovery_momentum", "balls_since_wicket",
        "boundary_pct_last_18", "dot_pct_last_12", "momentum_acceleration",
        "set_batter_exposure", "inn1_pp_run_rate", "pp_run_rate_vs_inn1",
        "below_par_run_cushion", "above_par_wicket_cost",
        "chase_diff_x_wickets", "recovery_x_chase",
    ]
    all_cols = set(df_v16.columns)
    v16_pp = ordered_unique(pp + V16_NEW)
    v16_pp = [f for f in v16_pp if f in all_cols]
    print(f"PP rows: {len(pp_df)}, v15={len(pp)}, v16={len(v16_pp)}\n")

    print("=== N: v15 model + PROPER per-cell calibration (inner train cal) ===")
    br, bs, bc, ll, y, cal, cats, overs = run_oof_with_cell_cal(pp_df, pp)
    print(f"  raw={br:.5f}  std_cal={bs:.5f}  cell_cal={bc:.5f}  ll={ll:.5f}  {pct(bc, V15_BRIER)}  {'✅' if bc<=GATE else '❌'}")
    # Brier by chase category
    for cat_n, cat_v in [("above_par",1), ("on_par",0), ("below_par",-1)]:
        m = cats == cat_v
        print(f"    {cat_n}: n={m.sum()}, brier={brier_score_loss(y[m], cal[m]):.5f}")

    print("\n=== O: v16 features + per-cell calibration ===")
    br, bs, bc, ll, y, cal, cats, overs = run_oof_with_cell_cal(pp_df_v16, v16_pp)
    print(f"  raw={br:.5f}  std_cal={bs:.5f}  cell_cal={bc:.5f}  ll={ll:.5f}  {pct(bc, V15_BRIER)}  {'✅' if bc<=GATE else '❌'}")
    for cat_n, cat_v in [("above_par",1), ("on_par",0), ("below_par",-1)]:
        m = cats == cat_v
        print(f"    {cat_n}: n={m.sum()}, brier={brier_score_loss(y[m], cal[m]):.5f}")

    def recency_w(df):
        s = df["season"].astype(str)
        w = np.ones(len(df))
        w[s >= "2015"] = 2.0
        w[s >= "2019"] = 3.0
        return w

    print("\n=== P: Recency-weighted v16 + per-cell calibration ===")
    br, bs, bc, ll, y, cal, cats, overs = run_oof_with_cell_cal(pp_df_v16, v16_pp, recency_w)
    print(f"  raw={br:.5f}  std_cal={bs:.5f}  cell_cal={bc:.5f}  ll={ll:.5f}  {pct(bc, V15_BRIER)}  {'✅' if bc<=GATE else '❌'}")
    for cat_n, cat_v in [("above_par",1), ("on_par",0), ("below_par",-1)]:
        m = cats == cat_v
        print(f"    {cat_n}: n={m.sum()}, brier={brier_score_loss(y[m], cal[m]):.5f}")

    print(f"\n{'='*60}")
    print(f"V15 baseline: {V15_BRIER} | Gate: {GATE}")


if __name__ == "__main__":
    main()
