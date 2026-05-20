"""
EDA: Do below-par / on-par / above-par chases need different sigmoid functions?

Hypothesis: The same RRR at different target difficulties has different win-prob implications.
  - Below-par (easy) chase at RRR=8: team is in control, high win prob
  - Above-par (hard) chase at RRR=8: team is struggling, lower win prob
  - Current model uses ONE sigmoid for all → may be systematically wrong

Analysis:
1. Stratify all inn2 balls by target_category (below/on/above par)
2. Fit separate sigmoid (midpoint, slope, beta) per category
3. Show calibration curve per category (current vs category-specific)
4. Recommend: update FormatConfig OR add target_category as a feature multiplier

Usage:
    python scripts/eda_stratified_sigmoid.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.optimize import minimize
from scipy.stats import pearsonr
from sklearn.metrics import brier_score_loss

EPS = 1e-7
FEATURES_PATH = Path("data/ipl_features_latest/training.parquet")
PAR_SCORE = 173.45  # IPL par from FormatConfig


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -700, 700)))


def compute_rwp(rrr, ob, mid, slp, beta):
    """Chasing team win prob from RRR sigmoid."""
    eff_mid = mid + slp * ob
    return sigmoid(-beta * (rrr - eff_mid))


def brier(y, p):
    return float(brier_score_loss(y, np.clip(p, EPS, 1 - EPS)))


def ece_score(y, p, n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    score, n = 0.0, len(y)
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (p >= lo) & (p < hi)
        if mask.sum() == 0: continue
        score += (mask.sum() / n) * abs(p[mask].mean() - y[mask].mean())
    return float(score)


def fit_sigmoid(rrr, ob, y, init=(8.56, 0.134, 0.598)):
    """Fit (midpoint, slope, beta) minimising Brier."""
    def loss(params):
        mid, slp, beta = params
        if beta < 0.05 or beta > 5 or mid < 4 or mid > 16 or abs(slp) > 1: return 1.0
        return brier(y, compute_rwp(rrr, ob, mid, slp, beta))

    best = (init[0], init[1], init[2], 1.0)
    for m in np.arange(7.0, 12.5, 0.5):
        for s in [0.0, 0.05, 0.10, 0.15, 0.20]:
            for b in [0.3, 0.5, 0.7, 1.0, 1.3]:
                v = loss([m, s, b])
                if v < best[3]: best = (m, s, b, v)

    res = minimize(loss, x0=[best[0], best[1], best[2]], method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-6, "maxiter": 3000})
    m, s, b = res.x
    return float(np.clip(m, 4, 16)), float(np.clip(s, -1, 1)), float(np.clip(b, 0.05, 5))


def calibration_table(y, p, label="", n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (p >= lo) & (p < hi)
        if mask.sum() < 10: continue
        rows.append({
            "bucket": f"({lo:.1f},{hi:.1f}]",
            "n": mask.sum(),
            "pred": p[mask].mean(),
            "actual": y[mask].mean(),
            "bias": p[mask].mean() - y[mask].mean(),
        })
    return pd.DataFrame(rows)


def main():
    print("Loading features...")
    df = pd.read_parquet(FEATURES_PATH)

    inn2 = df[
        (df["innings"] == 2) &
        df["required_run_rate"].notna() &
        df["overs_remaining"].notna() &
        df["resource_win_prob"].notna() &
        (df["required_run_rate"] > 0) &
        (df["required_run_rate"] < 50)
    ].copy()

    inn2["chaser_won"] = (inn2["batting_team"] == inn2["winner"]).astype(int)
    inn2["overs_bowled"] = (20.0 - inn2["overs_remaining"]).clip(0, 20)

    # Derive phase from boolean flags
    if "phase" not in inn2.columns:
        inn2["phase"] = np.select(
            [inn2["is_powerplay"].astype(bool),
             inn2["is_death_overs"].astype(bool)],
            ["powerplay", "death"],
            default="middle"
        )

    # ── Derive target categoryfrom target_above_par if available ─────────
    if "target_above_par" in inn2.columns:
        inn2["target_above_par_val"] = inn2["target_above_par"]
    elif "target" in inn2.columns:
        inn2["target_above_par_val"] = inn2["target"] - PAR_SCORE
    else:
        # Estimate: at start of inn2, required_run_rate * 20 ≈ target
        # Use the per-match target from the first ball of inn2
        target_map = inn2[inn2["overs_bowled"] < 0.5].groupby("match_id")["required_run_rate"].first() * 20
        inn2["target_est"] = inn2["match_id"].map(target_map)
        inn2["target_above_par_val"] = inn2["target_est"] - PAR_SCORE

    # Categorise
    BELOW_PAR  = -15   # target < par - 15
    ABOVE_PAR  =  15   # target > par + 15
    inn2["target_cat"] = pd.cut(
        inn2["target_above_par_val"],
        bins=[-999, BELOW_PAR, ABOVE_PAR, 999],
        labels=["below_par", "on_par", "above_par"]
    )
    print(f"\nInn2 rows: {len(inn2):,}")
    print(inn2["target_cat"].value_counts().to_string())
    print()

    CURR = {"mid": 8.56, "slp": 0.134, "beta": 0.598}
    y_all  = inn2["chaser_won"].values
    rrr_all = inn2["required_run_rate"].values
    ob_all  = inn2["overs_bowled"].values
    p_curr  = inn2["resource_win_prob"].values

    print("\n" + "=" * 70)
    print("SECTION 1: Overall inn2 calibration (current single sigmoid)")
    print("=" * 70)
    b0 = brier(y_all, p_curr)
    e0 = ece_score(y_all, p_curr)
    print(f"  Brier={b0:.5f}  ECE={e0:.5f}")

    # ── Section 2: Per-category calibration with CURRENT sigmoid ─────────
    print("\n" + "=" * 70)
    print("SECTION 2: Per target_category calibration — CURRENT sigmoid")
    print("=" * 70)
    for cat in ["below_par", "on_par", "above_par"]:
        seg = inn2[inn2["target_cat"] == cat]
        if len(seg) < 100: continue
        y_c  = seg["chaser_won"].values
        p_c  = seg["resource_win_prob"].values
        bc   = brier(y_c, p_c)
        ec   = ece_score(y_c, p_c)
        cr   = seg["required_run_rate"].mean()
        print(f"\n  {cat.upper()} (n={len(seg):,}, mean_RRR={cr:.2f}, chase_win_rate={y_c.mean():.3f})")
        print(f"    Brier={bc:.5f}  ECE={ec:.5f}")
        # Calibration curve
        tbl = calibration_table(y_c, p_c, n_bins=8)
        for _, row in tbl.iterrows():
            print(f"      {row['bucket']:<14}  n={int(row['n']):>5}  pred={row['pred']:.3f}  actual={row['actual']:.3f}  bias={row['bias']:+.3f}")

    # ── Section 3: Fit separate sigmoid per category ───────────────────────
    print("\n" + "=" * 70)
    print("SECTION 3: Fit separate sigmoid per target_category")
    print("=" * 70)
    cat_params = {}
    for cat in ["below_par", "on_par", "above_par"]:
        seg = inn2[inn2["target_cat"] == cat]
        if len(seg) < 200:
            print(f"  {cat}: SKIP (only {len(seg)} rows)")
            continue
        y_c   = seg["chaser_won"].values
        rrr_c = seg["required_run_rate"].values
        ob_c  = seg["overs_bowled"].values
        m, s, b = fit_sigmoid(rrr_c, ob_c, y_c)
        p_new = compute_rwp(rrr_c, ob_c, m, s, b)
        b_new = brier(y_c, p_new)
        b_old = brier(y_c, seg["resource_win_prob"].values)
        cat_params[cat] = {"mid": m, "slope": s, "beta": b}
        print(f"\n  {cat.upper()} (n={len(seg):,}):")
        print(f"    Single sigmoid:   Brier={b_old:.5f}")
        print(f"    Category sigmoid: Brier={b_new:.5f}  ({(b_new-b_old)/b_old*100:+.2f}%)")
        print(f"    Params: midpoint={m:.3f}  slope={s:.4f}  beta={b:.3f}")
        # Example probabilities at key RRR values (over 10)
        ob_ex = 10.0
        for rrr_ex in [6.0, 7.0, 8.0, 9.0, 10.0, 12.0]:
            p_old_ex = compute_rwp(np.array([rrr_ex]), np.array([ob_ex]),
                                   CURR["mid"], CURR["slp"], CURR["beta"])[0]
            p_new_ex = compute_rwp(np.array([rrr_ex]), np.array([ob_ex]), m, s, b)[0]
            print(f"      RRR={rrr_ex:.0f}@ov10: curr={p_old_ex:.3f}  cat={p_new_ex:.3f}  diff={p_new_ex-p_old_ex:+.3f}")

    # ── Section 4: Combined Brier — stratified vs single ─────────────────
    print("\n" + "=" * 70)
    print("SECTION 4: Stratified sigmoid vs single sigmoid (overall Brier)")
    print("=" * 70)
    inn2["p_stratified"] = inn2["resource_win_prob"].copy()
    for cat, params in cat_params.items():
        mask = inn2["target_cat"] == cat
        inn2.loc[mask, "p_stratified"] = compute_rwp(
            inn2.loc[mask, "required_run_rate"].values,
            inn2.loc[mask, "overs_bowled"].values,
            params["mid"], params["slope"], params["beta"]
        )
    b_strat = brier(y_all, inn2["p_stratified"].values)
    e_strat = ece_score(y_all, inn2["p_stratified"].values)
    print(f"  Single sigmoid:     Brier={b0:.5f}  ECE={e0:.5f}")
    print(f"  Stratified sigmoid: Brier={b_strat:.5f}  ECE={e_strat:.5f}  ({(b_strat-b0)/b0*100:+.2f}% Brier)")

    # ── Section 5: RRR midpoint shift by target_cat ───────────────────────
    print("\n" + "=" * 70)
    print("SECTION 5: Midpoint shift summary (what changes per category)")
    print("=" * 70)
    print(f"  {'Category':<12}  {'midpoint':>9}  {'slope':>8}  {'beta':>7}  {'vs_curr_mid':>12}")
    for cat, p in cat_params.items():
        diff = p["mid"] - CURR["mid"]
        print(f"  {cat:<12}  {p['mid']:>9.3f}  {p['slope']:>8.4f}  {p['beta']:>7.3f}  {diff:>+12.3f}")
    print(f"  {'CURRENT':<12}  {CURR['mid']:>9.3f}  {CURR['slp']:>8.4f}  {CURR['beta']:>7.3f}  {'(baseline)':>12}")

    # ── Section 6: Phase × category deep dive ────────────────────────────
    print("\n" + "=" * 70)
    print("SECTION 6: Phase × target_category — where is the gap largest?")
    print("=" * 70)
    rows = []
    for cat in ["below_par", "on_par", "above_par"]:
        for phase in ["powerplay", "middle", "death"]:
            seg = inn2[(inn2["target_cat"] == cat) & (inn2["phase"] == phase)]
            if len(seg) < 50: continue
            y_s = seg["chaser_won"].values
            p_s = seg["resource_win_prob"].values
            bc  = brier(y_s, p_s)
            bias = p_s.mean() - y_s.mean()
            rows.append({"category": cat, "phase": phase, "n": len(seg),
                         "brier": bc, "bias": bias,
                         "chase_wr": y_s.mean(), "pred_mean": p_s.mean()})
    tbl = pd.DataFrame(rows)
    print(tbl.to_string(index=False, float_format="{:.4f}".format))

    # ── Section 7: Chase difficulty × target correlation ─────────────────
    print("\n" + "=" * 70)
    print("SECTION 7: High-target underestimation check")
    print("  (model bias as function of target_above_par)")
    print("=" * 70)
    inn2["bias"] = inn2["resource_win_prob"] - inn2["chaser_won"]
    tgt_bins = pd.cut(inn2["target_above_par_val"], bins=[-999, -20, -5, 5, 20, 999],
                      labels=["<-20", "-20→-5", "-5→5", "5→20", ">20"])
    inn2["tgt_bin"] = tgt_bins
    summary = inn2.groupby("tgt_bin", observed=True).agg(
        n=("bias", "count"),
        mean_bias=("bias", "mean"),
        brier=("bias", lambda x: brier_score_loss(
            inn2.loc[x.index, "chaser_won"], inn2.loc[x.index, "resource_win_prob"])),
        chase_wr=("chaser_won", "mean"),
        pred_mean=("resource_win_prob", "mean"),
    ).reset_index()
    print(summary.to_string(index=False, float_format="{:.4f}".format))

    # ── Final recommendation ───────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    improvement = (b_strat - b0) / b0 * 100
    if improvement < -1.0:
        print(f"\n✅ WORTH IMPLEMENTING: Stratified sigmoid improves Brier by {improvement:.2f}%")
        print("\nApproach A — Recommended (lightweight, no retraining needed):")
        print("  Add `rrr_midpoint_by_target_cat` dict to FormatConfig.ipl()")
        print("  In calculator.py: look up midpoint offset by target_cat at feature-compute time")
        print("  resource_win_prob becomes target-category-aware → better input feature")
        print("\nApproach B (full retrain needed):")
        print("  Add `target_cat` as a feature input to the model alongside resource_win_prob")
        print("  XGBoost will learn the interaction automatically")
        print("\nCategory parameters to encode:")
        for cat, p in cat_params.items():
            print(f"  {cat}: mid={p['mid']:.3f}, slope={p['slope']:.4f}, beta={p['beta']:.3f}")
    else:
        print(f"\n⚠ Limited improvement ({improvement:.2f}%). Other factors dominate.")
        print("  Consider: separate model for inn2 or better carryover features.")


if __name__ == "__main__":
    main()
