"""
Derive optimal IPL inn2 sigmoid parameters from 2026 training data.

The inn2 resource_win_prob sigmoid:
    effective_midpoint = rrr_midpoint + rrr_midpoint_slope * overs_bowled
    base_prob = 1 / (1 + exp(rrr_beta * (rrr - effective_midpoint)))

Current params (v4 derived):
    rrr_midpoint=8.56, rrr_midpoint_slope=0.134, rrr_beta=0.598

This script:
1. Loads ipl_features_latest (282k rows) → inn2 slice
2. Audits ECE of current resource_win_prob vs actual outcome
3. Re-derives optimal (midpoint, slope, beta) minimising Brier
4. Shows over-by-over midpoint estimates from data
5. Prints recommended FormatConfig.ipl() update

Usage:
    python scripts/derive_ipl_sigmoid_params.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.optimize import minimize, minimize_scalar
from sklearn.metrics import brier_score_loss, log_loss

EPS = 1e-7

FEATURES_PATH = Path("data/ipl_features_latest/training.parquet")
CURRENT = {"midpoint": 8.56, "slope": 0.134, "beta": 0.598}


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def compute_resource_win_prob(rrr: np.ndarray, overs_bowled: np.ndarray,
                               midpoint: float, slope: float, beta: float) -> np.ndarray:
    """Chase team win probability from RRR sigmoid."""
    effective_mid = midpoint + slope * overs_bowled
    exponent = beta * (rrr - effective_mid)
    return 1.0 / (1.0 + np.exp(np.clip(exponent, -700, 700)))


def ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error (uniform bins)."""
    bins = np.linspace(0, 1, n_bins + 1)
    ece_val = 0.0
    n = len(y_true)
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if mask.sum() == 0:
            continue
        ece_val += (mask.sum() / n) * abs(y_prob[mask].mean() - y_true[mask].mean())
    return ece_val


def metrics(y, p):
    p = np.clip(p, EPS, 1 - EPS)
    return float(brier_score_loss(y, p)), float(ece(y, p))


def main():
    print("Loading features...")
    df = pd.read_parquet(FEATURES_PATH)
    print(f"Total rows: {len(df):,}")

    # Inn2 only, with required_run_rate defined
    inn2 = df[
        (df["innings"] == 2) &
        df["required_run_rate"].notna() &
        df["overs_remaining"].notna() &
        df["resource_win_prob"].notna() &
        (df["required_run_rate"] > 0) &
        (df["required_run_rate"] < 50)
    ].copy()
    print(f"Inn2 rows (valid RRR): {len(inn2):,}\n")

    if "winner" not in inn2.columns:
        print("ERROR: 'winner' column not found. Need outcome data.")
        return

    # Derive outcome: did the batting team (chasing) win?
    # 'winner' = team name; 'batting_team' = current batting team
    # Chase team wins when batting_team == winner
    inn2["chaser_won"] = (inn2["batting_team"] == inn2["winner"]).astype(int)
    print(f"Chase win rate: {inn2['chaser_won'].mean():.3f} ({inn2['chaser_won'].sum()}/{len(inn2)} balls)")

    # Overs bowled in inn2
    inn2["overs_bowled_inn2"] = 20.0 - inn2["overs_remaining"].clip(0, 20)

    # Derive phase from boolean flags if 'phase' column absent
    if "phase" not in inn2.columns:
        inn2["phase"] = np.select(
            [inn2["is_powerplay"].astype(bool),
             inn2["is_death_overs"].astype(bool)],
            ["powerplay", "death"],
            default="middle"
        )

    y     = inn2["chaser_won"].values
    rrr   = inn2["required_run_rate"].values
    ob    = inn2["overs_bowled_inn2"].values
    p_cur = inn2["resource_win_prob"].values   # already computed with current params

    # ── Section 1: ECE of current resource_win_prob ─────────────────────
    print("=" * 60)
    print("SECTION 1: Current resource_win_prob calibration audit")
    print("=" * 60)
    b_cur, e_cur = metrics(y, p_cur)
    print(f"  Current Brier = {b_cur:.4f}   ECE = {e_cur:.4f}\n")

    print("  Calibration curve (resource_win_prob buckets):")
    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
    inn2["bkt"] = pd.cut(inn2["resource_win_prob"], bins=bins)
    for bkt, grp in inn2.groupby("bkt", observed=True):
        if len(grp) < 50: continue
        actual = grp["chaser_won"].mean()
        pred   = grp["resource_win_prob"].mean()
        bias   = pred - actual
        print(f"    {str(bkt):<14}  n={len(grp):>6}  pred={pred:.3f}  actual={actual:.3f}  bias={bias:+.3f}")

    print()

    # ── Section 2: Over-by-over crossing RRR ─────────────────────────────
    print("=" * 60)
    print("SECTION 2: Empirical 50%-crossing RRR per over")
    print("  (The RRR where P(chase wins) = 50% based on actual data)")
    print("=" * 60)
    print(f"  {'Over':>5}  {'n':>6}  {'Cross_RRR_data':>14}  {'Curr_midpoint':>13}  {'Diff':>6}")
    crossings = []
    for ov in range(0, 20):
        seg = inn2[(inn2["overs_bowled_inn2"] >= ov) & (inn2["overs_bowled_inn2"] < ov + 1)]
        if len(seg) < 30:
            continue
        # Sort by RRR and find crossing point via logistic fit
        sorted_rrr = np.sort(seg["required_run_rate"].values)
        # Simple: find median RRR among winning chases vs losing chases
        won  = seg.loc[seg["chaser_won"] == 1, "required_run_rate"]
        lost = seg.loc[seg["chaser_won"] == 0, "required_run_rate"]
        if len(won) < 10 or len(lost) < 10:
            continue
        # Midpoint estimate: average of median(won) and median(lost)
        cross_est = (won.median() + lost.median()) / 2
        curr_mid  = CURRENT["midpoint"] + CURRENT["slope"] * ov
        diff      = cross_est - curr_mid
        crossings.append({"over": ov, "cross_rrr": cross_est, "curr_mid": curr_mid})
        print(f"  {ov+1:>5}  {len(seg):>6}  {cross_est:>14.2f}  {curr_mid:>13.2f}  {diff:>+6.2f}")

    # Fit linear regression on crossings
    if len(crossings) >= 5:
        cx = pd.DataFrame(crossings)
        from numpy.polynomial import polynomial as P
        coeffs = np.polyfit(cx["over"], cx["cross_rrr"], 1)
        slope_emp, intercept_emp = coeffs[0], coeffs[1]
        print(f"\n  Empirical fit: midpoint = {intercept_emp:.2f} + {slope_emp:.3f} × over")
        print(f"  Current:       midpoint = {CURRENT['midpoint']:.2f} + {CURRENT['slope']:.3f} × over")
        print(f"  Diff: intercept {intercept_emp - CURRENT['midpoint']:+.2f}, slope {slope_emp - CURRENT['slope']:+.3f}")
    print()

    # ── Section 3: Optimise (midpoint, slope, beta) ───────────────────────
    print("=" * 60)
    print("SECTION 3: Optimise sigmoid params (full dataset, Brier)")
    print("=" * 60)

    def brier_from_params(params):
        mid, slp, beta = params
        if beta < 0.1 or beta > 5.0 or mid < 5 or mid > 15 or slp < -0.5 or slp > 1.0:
            return 1.0
        p = compute_resource_win_prob(rrr, ob, mid, slp, beta)
        return brier_score_loss(y, np.clip(p, EPS, 1 - EPS))

    # Grid search for good starting point
    best = (CURRENT["midpoint"], CURRENT["slope"], CURRENT["beta"], 1.0)
    for mid0 in np.arange(7.0, 11.5, 0.5):
        for slp0 in [0.0, 0.05, 0.10, 0.15, 0.20, 0.25]:
            for beta0 in [0.3, 0.5, 0.7, 1.0, 1.2]:
                v = brier_from_params([mid0, slp0, beta0])
                if v < best[3]:
                    best = (mid0, slp0, beta0, v)

    print(f"  Grid best: mid={best[0]:.2f} slp={best[1]:.3f} beta={best[2]:.3f}  Brier={best[3]:.5f}")

    result = minimize(brier_from_params, x0=[best[0], best[1], best[2]],
                      method="Nelder-Mead",
                      options={"xatol": 1e-5, "fatol": 1e-6, "maxiter": 5000})
    opt_mid, opt_slp, opt_beta = result.x
    opt_mid  = float(np.clip(opt_mid,  5.0, 15.0))
    opt_slp  = float(np.clip(opt_slp,  -0.5, 1.0))
    opt_beta = float(np.clip(opt_beta, 0.1,  5.0))

    p_opt = compute_resource_win_prob(rrr, ob, opt_mid, opt_slp, opt_beta)
    b_opt, e_opt = metrics(y, p_opt)
    print(f"\n  OPTIMISED: mid={opt_mid:.3f}  slope={opt_slp:.4f}  beta={opt_beta:.3f}")
    print(f"    Brier {b_cur:.5f} → {b_opt:.5f}  ({(b_opt-b_cur)/b_cur*100:+.2f}%)")
    print(f"    ECE   {e_cur:.5f} → {e_opt:.5f}\n")

    # ── Section 4: Per-phase ECE (current vs optimised) ───────────────────
    print("=" * 60)
    print("SECTION 4: Phase-wise ECE (current vs optimised)")
    print("=" * 60)
    inn2["p_opt"] = compute_resource_win_prob(rrr, ob, opt_mid, opt_slp, opt_beta)
    for phase in ["powerplay", "middle", "death"]:
        seg = inn2[inn2["phase"] == phase]
        if len(seg) < 50: continue
        b_c, e_c = metrics(seg["chaser_won"].values, seg["resource_win_prob"].values)
        b_o, e_o = metrics(seg["chaser_won"].values, seg["p_opt"].values)
        print(f"  {phase:10s}  n={len(seg):>6}")
        print(f"    Current:  Brier={b_c:.4f}  ECE={e_c:.4f}")
        print(f"    Optimised: Brier={b_o:.4f}  ECE={e_o:.4f}  ({(b_o-b_c)/b_c*100:+.2f}%)")
    print()

    # ── Section 5: SQI / inn1 parameters check ────────────────────────────
    inn1 = df[df["innings"] == 1].copy()
    if "winner" in inn1.columns and "batting_team" in inn1.columns:
        inn1["bat_first_won"] = (inn1["batting_team"] == inn1["winner"]).astype(int)
        print("=" * 60)
        print("SECTION 5: Inn1 resource_win_prob calibration check")
        print("=" * 60)
        b_i1, e_i1 = metrics(inn1["bat_first_won"].values, inn1["resource_win_prob"].values)
        print(f"  Inn1 Brier={b_i1:.4f}  ECE={e_i1:.4f}")
        print(f"  Inn1 mean resource_win_prob: {inn1['resource_win_prob'].mean():.3f}")
        print(f"  Inn1 actual bat-first win rate: {inn1['bat_first_won'].mean():.3f}")
        avg_target = df[df["innings"] == 2]["required_run_rate"].count()
        if "target" in df.columns:
            targets = df[df["innings"] == 2]["target"].dropna()
            print(f"\n  2026 IPL target distribution:")
            print(f"    Mean target: {targets.mean():.1f}")
            print(f"    Median:      {targets.median():.1f}")
            print(f"    >180:        {(targets > 180).sum()} ({(targets > 180).mean()*100:.1f}%)")
            print(f"    >200:        {(targets > 200).sum()} ({(targets > 200).mean()*100:.1f}%)")
        print()

    # ── Summary + Recommended update ─────────────────────────────────────
    print("=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    print(f"\nCurrent FormatConfig.ipl() sigmoid params:")
    print(f"  rrr_midpoint       = {CURRENT['midpoint']}")
    print(f"  rrr_midpoint_slope = {CURRENT['slope']}")
    print(f"  rrr_beta           = {CURRENT['beta']}")
    if b_opt < b_cur - 0.0005:
        print(f"\nRecommended update (Brier improvement: {(b_opt-b_cur)/b_cur*100:+.2f}%):")
        print(f"  rrr_midpoint       = {opt_mid:.3f}")
        print(f"  rrr_midpoint_slope = {opt_slp:.4f}")
        print(f"  rrr_beta           = {opt_beta:.3f}")
        print("\nAdd these to FormatConfig.ipl() in src/bbl_pipeline/features/format_config.py")
        print("Then re-run: bbl-pipeline process + retrain (features change, needs re-training)")
    else:
        print(f"\nCurrent params are near-optimal (improvement only {(b_opt-b_cur)/b_cur*100:+.2f}%).")
        print("The calibration bias is likely a model-level issue, not just the sigmoid.")
    
    # Additional check: what midpoints match the data crossings
    if crossings:
        cx = pd.DataFrame(crossings)
        print(f"\nPer-over crossing RRR summary:")
        print(f"  Data midpoints start at: {cx.iloc[0]['cross_rrr']:.2f}")
        print(f"  Data midpoints at over 10: {cx[cx['over']==9]['cross_rrr'].values}")
        print(f"  Data midpoints at over 15: {cx[cx['over']==14]['cross_rrr'].values}")
        print(f"  Current model over  1 midpoint: {CURRENT['midpoint'] + CURRENT['slope']*0:.2f}")
        print(f"  Current model over 10 midpoint: {CURRENT['midpoint'] + CURRENT['slope']*9:.2f}")
        print(f"  Current model over 15 midpoint: {CURRENT['midpoint'] + CURRENT['slope']*14:.2f}")


if __name__ == "__main__":
    main()
