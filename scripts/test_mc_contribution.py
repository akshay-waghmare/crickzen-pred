"""
Test whether MC simulation adds independent signal to improve market predictions.

MC uses simulation-based evaluation (resource_win_prob) which is fundamentally
different from the ML model (feature-based XGBLogRegEnsemble). If MC provides
orthogonal signal, blending MC+market could beat market alone.

Usage:
    python scripts/test_mc_contribution.py
"""
import sys, warnings, time
warnings.filterwarnings("ignore")
sys.path.insert(0, "src")

import pandas as pd
import numpy as np
import joblib
from scipy.optimize import minimize_scalar, minimize
from pathlib import Path

from bbl_pipeline.simulation.state import MatchState
from bbl_pipeline.simulation.engine import simulate


def brier_score(y_true, y_pred):
    return np.mean((y_true - y_pred) ** 2)


def log_loss(y_true, y_pred):
    eps = 1e-7
    p = np.clip(y_pred, eps, 1 - eps)
    return -np.mean(y_true * np.log(p) + (1 - y_true) * np.log(1 - p))


def blend_brier(alpha, y_true, p1, p2):
    """Brier score for alpha*p1 + (1-alpha)*p2."""
    return brier_score(y_true, alpha * p1 + (1 - alpha) * p2)


def main():
    print("=" * 70)
    print("MC CONTRIBUTION TEST: Does MC simulation add value over market?")
    print("=" * 70)

    # Load live data
    live = pd.read_parquet("data/ipl_model_vs_market.parquet")
    print(f"\nLoaded {len(live)} observations from {live['event_id'].nunique()} matches")

    # Fix missing targets for inn2 from inn1 max scores
    inn1_totals = live[live["innings"] == 1].groupby("event_id")["runs"].max()
    for eid, total in inn1_totals.items():
        mask = (live["event_id"] == eid) & (live["innings"] == 2) & (live["target"].isna())
        live.loc[mask, "target"] = total + 1

    # Mark which rows we can score with MC
    can_score = (live["innings"] == 1) | (live["target"].notna())
    scorable = live[can_score].copy()
    print(f"Scorable with MC: {len(scorable)} / {len(live)} ({len(live)-len(scorable)} skipped - no target)")

    # Load MC calibrator
    mc_cal = joblib.load("models/ipl_v2/mc_calibrators_innings.pkl")
    print(f"MC calibrator: {type(mc_cal).__name__}")
    print(mc_cal.summary())

    # Score observations with MC simulation
    print(f"\nRunning MC simulation on {len(scorable)} observations (1000 sims, horizon=6)...")
    mc_probs_raw = []
    mc_stds = []
    start_total = time.time()

    for idx, (_, row) in enumerate(scorable.iterrows()):
        over = int(row["over"])
        balls_bowled = over * 6  # approximate
        balls_remaining = 120 - balls_bowled

        if balls_remaining <= 0:
            balls_remaining = 1

        target = int(row["target"]) if pd.notna(row["target"]) and row["innings"] == 2 else None

        bowling_team = row["team2"] if row["batting_team"] == row["team1"] else row["team1"]

        state = MatchState(
            innings=int(row["innings"]),
            score=int(row["runs"]),
            wickets_lost=int(row["wickets"]),
            balls_remaining=balls_remaining,
            target_runs=target,
            batting_team=row["batting_team"],
            bowling_team=bowling_team,
            league="ipl",
        )

        result = simulate(state, horizon=6, n_simulations=1000, model_dir="models/t20_male_v2")

        # MC returns P(batting_team wins) — convert to P(team1 wins)
        if row["batting_team"] == row["team1"]:
            mc_p_t1 = result.mean_prob
        else:
            mc_p_t1 = 1 - result.mean_prob

        mc_probs_raw.append(mc_p_t1)
        mc_stds.append(result.std_prob)

        if (idx + 1) % 50 == 0:
            elapsed = time.time() - start_total
            rate = (idx + 1) / elapsed
            remaining = (len(scorable) - idx - 1) / rate
            print(f"  {idx+1}/{len(scorable)} done ({elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining)")

    total_time = time.time() - start_total
    print(f"MC simulation complete: {total_time:.1f}s ({total_time/len(scorable)*1000:.0f}ms/obs)")

    scorable["mc_raw_p_t1"] = mc_probs_raw
    scorable["mc_std"] = mc_stds

    # Apply MC calibrator (Platt scaling)
    mc_probs_cal = []
    for _, row in scorable.iterrows():
        inn = int(row["innings"])
        raw_p = row["mc_raw_p_t1"]
        cal_p = mc_cal.calibrate(raw_p, inn)
        mc_probs_cal.append(cal_p)

    scorable["mc_cal_p_t1"] = mc_probs_cal

    # Also load holdout model predictions if available
    oos_path = Path("data/ipl_oos_validation_2026.parquet")
    if oos_path.exists():
        oos = pd.read_parquet(oos_path)
        # Merge holdout predictions
        # OOS was saved with same index ordering
        scorable = scorable.merge(
            oos[["holdout_raw_p_t1", "holdout_platt_p_t1"]],
            left_index=True,
            right_index=True,
            how="left",
        )
        has_holdout = True
    else:
        has_holdout = False

    # =========================================================================
    # ANALYSIS
    # =========================================================================
    y = scorable["actual_t1_wins"].values
    market = scorable["market_p_t1"].values
    mc_raw = scorable["mc_raw_p_t1"].values
    mc_cal = scorable["mc_cal_p_t1"].values

    print("\n" + "=" * 70)
    print("OVERALL RESULTS")
    print("=" * 70)

    results = {
        "Market": market,
        "MC Raw": mc_raw,
        "MC Calibrated": mc_cal,
    }
    if has_holdout:
        results["ML Holdout Raw"] = scorable["holdout_raw_p_t1"].dropna().values
        results["ML Holdout+Platt"] = scorable["holdout_platt_p_t1"].dropna().values

    print(f"\n{'Method':<25} {'Brier':>8} {'LogLoss':>8} {'vs Market':>10}")
    print("-" * 55)
    for name, preds in results.items():
        mask = ~np.isnan(preds) if isinstance(preds, np.ndarray) else np.ones(len(preds), dtype=bool)
        y_sub = y[:len(preds)][mask] if len(preds) < len(y) else y[mask]
        p_sub = preds[mask]
        b = brier_score(y_sub, p_sub)
        ll = log_loss(y_sub, p_sub)
        m_b = brier_score(y_sub, market[:len(preds)][mask] if len(preds) < len(y) else market[mask])
        delta = (b - m_b) / m_b * 100
        print(f"{name:<25} {b:.4f}   {ll:.4f}   {delta:+.1f}%")

    # Blending: MC + Market
    print("\n" + "=" * 70)
    print("BLENDING: MC + MARKET")
    print("=" * 70)

    for mc_name, mc_p in [("MC Raw", mc_raw), ("MC Calibrated", mc_cal)]:
        res = minimize_scalar(
            lambda a: brier_score(y, a * mc_p + (1 - a) * market),
            bounds=(0, 1),
            method="bounded",
        )
        alpha = res.x
        blend_p = alpha * mc_p + (1 - alpha) * market
        b_blend = brier_score(y, blend_p)
        b_market = brier_score(y, market)
        b_mc = brier_score(y, mc_p)
        print(f"\n{mc_name} + Market:")
        print(f"  Optimal alpha = {alpha:.3f} ({alpha*100:.1f}% MC, {(1-alpha)*100:.1f}% market)")
        print(f"  Blend Brier = {b_blend:.4f} (Market: {b_market:.4f}, MC: {b_mc:.4f})")
        delta = (b_blend - b_market) / b_market * 100
        print(f"  vs Market: {delta:+.2f}%")

    # Triple blend: MC + ML + Market
    if has_holdout:
        print("\n" + "=" * 70)
        print("TRIPLE BLEND: MC + ML + MARKET")
        print("=" * 70)

        holdout_platt = scorable["holdout_platt_p_t1"].values
        valid = ~np.isnan(holdout_platt)
        y_v = y[valid]
        market_v = market[valid]
        mc_cal_v = mc_cal[valid]
        ml_v = holdout_platt[valid]

        def triple_brier(params):
            a, b = params
            c = 1 - a - b
            if c < 0 or a < 0 or b < 0:
                return 1.0
            blend = a * mc_cal_v + b * ml_v + c * market_v
            return brier_score(y_v, blend)

        from scipy.optimize import minimize as opt_minimize
        best = opt_minimize(triple_brier, [0.1, 0.1], bounds=[(0, 1), (0, 1)], method="L-BFGS-B")
        a_mc, a_ml = best.x
        a_mkt = 1 - a_mc - a_ml

        print(f"  Optimal weights: MC={a_mc:.3f}, ML={a_ml:.3f}, Market={a_mkt:.3f}")
        blend_p = a_mc * mc_cal_v + a_ml * ml_v + a_mkt * market_v
        b_triple = brier_score(y_v, blend_p)
        b_mkt = brier_score(y_v, market_v)
        print(f"  Triple Blend Brier = {b_triple:.4f} (Market: {b_mkt:.4f})")
        delta = (b_triple - b_mkt) / b_mkt * 100
        print(f"  vs Market: {delta:+.2f}%")

    # Phase breakdown: MC vs Market
    print("\n" + "=" * 70)
    print("PHASE BREAKDOWN: MC vs MARKET")
    print("=" * 70)

    for (inn, phase), grp in scorable.groupby(["innings", "phase"]):
        y_g = grp["actual_t1_wins"].values
        m_g = grp["market_p_t1"].values
        mc_g = grp["mc_cal_p_t1"].values

        if len(grp) < 5:
            continue

        b_m = brier_score(y_g, m_g)
        b_mc = brier_score(y_g, mc_g)
        delta = (b_mc - b_m) / b_m * 100

        # Optimal blend
        res = minimize_scalar(
            lambda a: brier_score(y_g, a * mc_g + (1 - a) * m_g),
            bounds=(0, 1),
            method="bounded",
        )
        alpha = res.x
        b_blend = brier_score(y_g, alpha * mc_g + (1 - alpha) * m_g)
        d_blend = (b_blend - b_m) / b_m * 100

        print(f"Inn{inn} {phase:>8} (n={len(grp):>3}): MC={b_mc:.4f} Mkt={b_m:.4f} ({delta:+.1f}%)  Blend(a={alpha:.2f}): {b_blend:.4f} ({d_blend:+.1f}%)")

    # MC uncertainty analysis
    print("\n" + "=" * 70)
    print("MC UNCERTAINTY ANALYSIS")
    print("=" * 70)

    scorable["mc_error"] = (scorable["actual_t1_wins"] - scorable["mc_cal_p_t1"]).abs()
    scorable["market_error"] = (scorable["actual_t1_wins"] - scorable["market_p_t1"]).abs()

    # Where MC is confident (low std) vs uncertain (high std)
    median_std = scorable["mc_std"].median()
    low_unc = scorable[scorable["mc_std"] <= median_std]
    high_unc = scorable[scorable["mc_std"] > median_std]

    print(f"\nMC std median: {median_std:.4f}")
    print(f"Low uncertainty ({len(low_unc)} obs): MC Brier={brier_score(low_unc['actual_t1_wins'], low_unc['mc_cal_p_t1']):.4f}, Market Brier={brier_score(low_unc['actual_t1_wins'], low_unc['market_p_t1']):.4f}")
    print(f"High uncertainty ({len(high_unc)} obs): MC Brier={brier_score(high_unc['actual_t1_wins'], high_unc['mc_cal_p_t1']):.4f}, Market Brier={brier_score(high_unc['actual_t1_wins'], high_unc['market_p_t1']):.4f}")

    # MC disagreement with market — when they disagree most, who is right?
    scorable["mc_market_diff"] = (scorable["mc_cal_p_t1"] - scorable["market_p_t1"]).abs()
    median_diff = scorable["mc_market_diff"].median()
    agree = scorable[scorable["mc_market_diff"] <= median_diff]
    disagree = scorable[scorable["mc_market_diff"] > median_diff]

    print(f"\nMC-Market disagreement median: {median_diff:.4f}")
    print(f"Agreement region ({len(agree)} obs): MC Brier={brier_score(agree['actual_t1_wins'], agree['mc_cal_p_t1']):.4f}, Market Brier={brier_score(agree['actual_t1_wins'], agree['market_p_t1']):.4f}")
    print(f"Disagreement region ({len(disagree)} obs): MC Brier={brier_score(disagree['actual_t1_wins'], disagree['mc_cal_p_t1']):.4f}, Market Brier={brier_score(disagree['actual_t1_wins'], disagree['market_p_t1']):.4f}")

    # Save results
    output_path = "data/ipl_mc_contribution_test.parquet"
    scorable.to_parquet(output_path)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
