"""v18: v17_all + 8 more high-signal features (corr 0.30-0.43), per-cell calibration."""
import sys, json
sys.path.insert(0, "src")
sys.path.insert(0, "scripts")
import numpy as np
from pathlib import Path
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.isotonic import IsotonicRegression

from ipl_v13_mid_split_common import (
    safe_X, phase_slice, PHASE_RANGES_V12, season_folds,
    fit_calibrator_bundle, apply_calibrator_bundle,
    load_training_data, ordered_unique, XGBLRBlend,
)

V15_DIR = Path("models/ipl_v15_wicket_features")
V15_BRIER = 0.17032; GATE = 0.16180

V17_NEW = [
    "late_mid_urgency","death_feasibility","finish_quality_zone","chase_on_track_score",
    "chase_run_buffer","svp_x_chase_cat","momentum_under_pressure","required_rpb",
    "early_mid_rrr_vs_venue_avg","chase_difficulty","score_per_wicket",
    "wickets_times_balls","wickets_last_30","balls_since_wicket",
]
V18_EXTRA = [
    "target_clarity_index",   # corr=-0.427
    "run_rate_team_adj",      # corr=0.401
    "score_adjusted_by_team", # corr=0.383
    "rrr_times_wickets",      # corr=-0.355
    "wicket_pressure",        # corr=-0.355
    "late_mid_run_gap",       # corr=0.343
    "momentum_x_wickets",     # corr=0.301
    "early_settle_flag",      # corr=0.300
    "wicket_budget_remaining",# corr=0.288
    "partnership_solidity",   # corr=0.208
]


def run_oof_both_cals(pp_df, feats):
    pp_df = pp_df.reset_index(drop=True)
    X, _ = safe_X(pp_df, feats)
    y = pp_df["is_winner"].values
    overs = pp_df["over"].values
    cats = pp_df["chase_category"].values
    seasons = sorted(pp_df["season"].astype(str).unique().tolist())
    folds = season_folds(seasons, 5)
    raw = np.zeros(len(pp_df))
    for val_seasons in folds:
        tr = ~pp_df["season"].isin(val_seasons)
        va =  pp_df["season"].isin(val_seasons)
        if tr.sum() == 0 or va.sum() == 0: continue
        m = XGBLRBlend()
        m.fit(X[tr], y[tr])
        raw[va] = m.predict_proba(X[va])[:, 1]
    bun = fit_calibrator_bundle(raw, y, overs, "isotonic")
    cal_std = apply_calibrator_bundle(raw, overs, bun)
    cal_cell = raw.copy()
    for ov in range(6):
        for cat in [-1, 0, 1]:
            mask = (overs == ov) & (cats == cat)
            if mask.sum() < 30: continue
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(raw[mask], y[mask])
            cal_cell[mask] = iso.predict(raw[mask])
    b_std = float(brier_score_loss(y, cal_std))
    b_cell = float(brier_score_loss(y, cal_cell))
    ll_std = float(log_loss(y, cal_std.clip(1e-7, 1-1e-7)))
    ll_cell = float(log_loss(y, cal_cell.clip(1e-7, 1-1e-7)))
    return b_std, b_cell, ll_std, ll_cell, y, raw, cats, overs


def pct(new, old): return f"{(new-old)/old*100:+.2f}%"


def main():
    print("Loading data...")
    df = load_training_data()
    v15 = json.load(open(V15_DIR / "phase_features.json"))["pp"]
    all_cols = set(df.columns)
    pp_df = phase_slice(df, PHASE_RANGES_V12["pp"])

    v17 = ordered_unique(v15 + [f for f in V17_NEW if f in all_cols])
    v18 = ordered_unique(v17 + [f for f in V18_EXTRA if f in all_cols])
    v18_top4 = ordered_unique(v17 + [f for f in V18_EXTRA[:4] if f in all_cols])

    print(f"PP rows: {len(pp_df)}, v15={len(v15)}, v17={len(v17)}, v18_top4={len(v18_top4)}, v18={len(v18)}")
    print(f"New v18 features: {[f for f in V18_EXTRA if f in all_cols]}\n")

    print("=== T: v17_all + top-4 extra (target_clarity, run_rate_adj, score_adj_team, rrr_x_wkts) ===")
    b_std, b_cell, ll_std, ll_cell, y, raw, cats, overs = run_oof_both_cals(pp_df, v18_top4)
    print(f"  std={b_std:.5f}  {pct(b_std, V15_BRIER)} | cell={b_cell:.5f}  {pct(b_cell, V15_BRIER)}  {'✅' if b_cell<=GATE else '❌'}")
    for cn, cv in [("above_par",1),("on_par",0),("below_par",-1)]:
        m = cats==cv
        print(f"    {cn}: raw={brier_score_loss(y[m],raw[m]):.5f}")

    print("\n=== U: v18_all (v15 + 24 features) ===")
    b_std, b_cell, ll_std, ll_cell, y, raw, cats, overs = run_oof_both_cals(pp_df, v18)
    print(f"  std={b_std:.5f}  {pct(b_std, V15_BRIER)} | cell={b_cell:.5f}  {pct(b_cell, V15_BRIER)}  {'✅' if b_cell<=GATE else '❌'}")
    for cn, cv in [("above_par",1),("on_par",0),("below_par",-1)]:
        m = cats==cv
        print(f"    {cn}: raw={brier_score_loss(y[m],raw[m]):.5f}")

    print("\n=== Best summary ===")
    print(f"  V15 baseline:     0.17032")
    print(f"  Best so far:      0.16759 (v17_all + cell_cal, -1.60%)")
    print(f"  Gate (5%):        0.16180")


if __name__ == "__main__":
    main()
