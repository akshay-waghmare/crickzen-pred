"""
v17 experiment: add 9 high-signal features (corr 0.33-0.38) missing from v15 PP.
These are all present in training parquet, zero nulls, NOT in v15 or v16.
"""
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
V15_BRIER = 0.17032
GATE = 0.16180

# 9 high-signal features missing from v15 PP (corr 0.33-0.38 with on_par outcome)
HIGH_SIGNAL_NEW = [
    "late_mid_urgency",         # corr=-0.382
    "death_feasibility",        # corr=0.378
    "finish_quality_zone",      # corr=0.378
    "chase_on_track_score",     # corr=0.372
    "chase_run_buffer",         # corr=0.369
    "svp_x_chase_cat",          # corr=0.369
    "momentum_under_pressure",  # corr=0.342
    "required_rpb",             # corr=-0.334
    "early_mid_rrr_vs_venue_avg", # corr=-0.334
    # Additional (corr 0.26-0.33)
    "chase_difficulty",         # corr=-0.331
    "score_per_wicket",         # corr=0.260
    "wickets_times_balls",      # corr=0.283
    "wickets_last_30",          # corr=0.273
    "balls_since_wicket",
]


def run_oof(pp_df, feats):
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

    # Standard per-over calibration
    bun = fit_calibrator_bundle(raw, y, overs, "isotonic")
    cal_std = apply_calibrator_bundle(raw, overs, bun)

    # Per-cell (over × chase_category) calibration
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
    v15_feats = json.load(open(V15_DIR / "phase_features.json"))
    pp = v15_feats["pp"]
    pp_df = phase_slice(df, PHASE_RANGES_V12["pp"])

    all_cols = set(df.columns)
    available_new = [f for f in HIGH_SIGNAL_NEW if f in all_cols]
    v17_pp = ordered_unique(pp + available_new)
    v17_pp_top9 = ordered_unique(pp + HIGH_SIGNAL_NEW[:9])

    print(f"PP rows: {len(pp_df)}")
    print(f"v15={len(pp)}, v17_top9={len(v17_pp_top9)}, v17_all={len(v17_pp)}")
    print(f"New features available: {available_new}\n")

    print("=== Q: v17-top9 (9 high-signal) + std calibration ===")
    b_std, b_cell, ll_std, ll_cell, y, raw, cats, overs = run_oof(pp_df, v17_pp_top9)
    g_std = "✅" if b_std <= GATE else "❌"
    g_cell = "✅" if b_cell <= GATE else "❌"
    print(f"  std_cal={b_std:.5f}  {pct(b_std, V15_BRIER)}  {g_std}")
    print(f"  cell_cal={b_cell:.5f}  {pct(b_cell, V15_BRIER)}  {g_cell}")
    for cat_n, cat_v in [("above_par",1), ("on_par",0), ("below_par",-1)]:
        m = cats == cat_v
        b = brier_score_loss(y[m], raw[m])
        print(f"    {cat_n}: raw_brier={b:.5f}")

    print("\n=== R: v17-all (9 high-signal + 5 medium) + std calibration ===")
    b_std, b_cell, ll_std, ll_cell, y, raw, cats, overs = run_oof(pp_df, v17_pp)
    g_std = "✅" if b_std <= GATE else "❌"
    g_cell = "✅" if b_cell <= GATE else "❌"
    print(f"  std_cal={b_std:.5f}  {pct(b_std, V15_BRIER)}  {g_std}")
    print(f"  cell_cal={b_cell:.5f}  {pct(b_cell, V15_BRIER)}  {g_cell}")
    for cat_n, cat_v in [("above_par",1), ("on_par",0), ("below_par",-1)]:
        m = cats == cat_v
        b = brier_score_loss(y[m], raw[m])
        print(f"    {cat_n}: raw_brier={b:.5f}")

    print("\n=== S: v17-top9 + per-cell calibration + COMPARISON ===")
    print(f"  Baseline v15 std: {V15_BRIER}  Gate: {GATE}")

    print("\n" + "="*60)
    print(f"V15 baseline: {V15_BRIER} | Gate: {GATE}")


if __name__ == "__main__":
    main()
