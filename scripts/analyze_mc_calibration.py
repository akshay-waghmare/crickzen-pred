"""
MC Engine Calibration Analysis — RAW vs CALIBRATED comparison.

Backtests the MC simulation engine on historical T20I matches and computes
Brier, ECE, and LogLoss for every combination of innings and phase,
comparing raw (uncalibrated) and Platt-calibrated outputs side by side.

Usage:
    python scripts/analyze_mc_calibration.py \
        --json-dir t20_international_male \
        --model-dir models/t20_international_male_v1 \
        --league t20i \
        --max-matches 300

    # Parallel mode (default: all cores - 1)
    python scripts/analyze_mc_calibration.py \
        --json-dir t20_international_male \
        --model-dir models/t20_international_male_v1 \
        --league t20i \
        --max-matches 300 \
        --workers 6
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

import numpy as np

from bbl_pipeline.simulation.engine import (
    simulate_one_over,
    _MC_CALIBRATOR_CACHE,
)
from bbl_pipeline.simulation.state import MatchState as SimMatchState
from bbl_pipeline.calibration.mc_calibrator import MCCalibrator, InningsMCCalibrators


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def _count_legal(delivery: dict) -> int:
    extras = delivery.get("extras", {})
    if "wides" in extras or "noballs" in extras:
        return 0
    return 1


def _get_phase(balls_remaining: int, total_balls: int = 120) -> str:
    balls_bowled = total_balls - balls_remaining
    overs_bowled = balls_bowled / 6.0
    if overs_bowled < 6:
        return "powerplay"
    elif overs_bowled < 15:
        return "middle"
    else:
        return "death"


def _ece(preds: np.ndarray, actuals: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (preds >= lo) & (preds < hi)
        if mask.sum() == 0:
            continue
        ece += mask.sum() * abs(preds[mask].mean() - actuals[mask].mean())
    return float(ece / len(preds)) if len(preds) > 0 else 0.0


def _brier(preds: np.ndarray, actuals: np.ndarray) -> float:
    return float(np.mean((preds - actuals) ** 2))


def _logloss(preds: np.ndarray, actuals: np.ndarray, eps: float = 1e-7) -> float:
    p = np.clip(preds, eps, 1 - eps)
    return float(-np.mean(actuals * np.log(p) + (1 - actuals) * np.log(1 - p)))


# ──────────────────────────────────────────────────────────
# Collect predictions per match
# ──────────────────────────────────────────────────────────

def collect_match_predictions(
    filepath: str,
    league: str,
    model_dir: str,
    n_sims: int = 300,
    calibrator: MCCalibrator | InningsMCCalibrators | None = None,
) -> list[dict]:
    """Run MC at every over-end in BOTH innings and return predictions.

    Each prediction dict includes both ``pred_raw`` (uncalibrated engine mean)
    and ``pred_cal`` (Platt-calibrated).  The engine is run with the cache set
    to ``None`` so that no calibrator is applied inside ``simulate_one_over``.
    The Platt calibrator is applied *externally* here for the ``pred_cal``
    column so we get both values from the same raw simulation.
    """
    with open(filepath) as f:
        data = json.load(f)

    info = data["info"]
    outcome = info.get("outcome", {})
    innings_data = data.get("innings", [])
    if len(innings_data) < 2:
        return []

    winner = outcome.get("winner")
    teams = info.get("teams", [])
    if not winner or winner not in teams:
        return []

    # First innings team
    inn1_team = innings_data[0]["team"]
    inn1_other = [t for t in teams if t != inn1_team][0]
    inn1_won = 1 if winner == inn1_team else 0

    # Second innings
    inn2_team = innings_data[1]["team"]
    inn2_other = [t for t in teams if t != inn2_team][0]
    inn2_won = 1 if winner == inn2_team else 0

    target_info = innings_data[1].get("target", {})
    target_overs = target_info.get("overs", 20)
    target_runs = target_info.get("runs")
    if target_runs is None:
        return []

    total_balls = target_overs * 6
    if total_balls < 6 or total_balls > 120 or total_balls % 6 != 0:
        return []

    results = []

    # ── INNINGS 1 ──
    score, wickets, legal_balls = 0, 0, 0
    for ov in innings_data[0].get("overs", []):
        for d in ov["deliveries"]:
            score += d["runs"]["total"]
            if d.get("wickets"):
                wickets += 1
            legal_balls += _count_legal(d)

            balls_remaining = max(0, total_balls - legal_balls)
            if legal_balls % 6 == 0 and balls_remaining > 0:
                try:
                    state = SimMatchState(
                        innings=1,
                        score=score,
                        wickets_lost=min(wickets, 9),
                        balls_remaining=balls_remaining,
                        target_runs=None,
                        batting_team=inn1_team,
                        bowling_team=inn1_other,
                        league=league,
                        total_balls=total_balls,
                    )
                    # Disable in-engine calibrator to get raw mean
                    _MC_CALIBRATOR_CACHE[model_dir] = None
                    res = simulate_one_over(state, n_simulations=n_sims, model_dir=model_dir)
                    raw_prob = res.mean_prob
                    if isinstance(calibrator, InningsMCCalibrators):
                        cal_prob = calibrator.calibrate(raw_prob, innings=1)
                    elif calibrator:
                        cal_prob = calibrator.calibrate(raw_prob)
                    else:
                        cal_prob = raw_prob
                    phase = _get_phase(balls_remaining, total_balls)
                    results.append({
                        "innings": 1,
                        "phase": phase,
                        "over": legal_balls // 6,
                        "pred_raw": raw_prob,
                        "pred_cal": cal_prob,
                        "actual": inn1_won,
                        "batting_team": inn1_team,
                        "bowling_team": inn1_other,
                        "score": score,
                        "wickets": wickets,
                        "balls_remaining": balls_remaining,
                    })
                except Exception:
                    pass

    # ── INNINGS 2 ──
    score, wickets, legal_balls = 0, 0, 0
    for ov in innings_data[1].get("overs", []):
        for d in ov["deliveries"]:
            score += d["runs"]["total"]
            if d.get("wickets"):
                wickets += 1
            legal_balls += _count_legal(d)

            balls_remaining = max(0, total_balls - legal_balls)
            if legal_balls % 6 == 0 and balls_remaining > 0 and score < target_runs:
                try:
                    state = SimMatchState(
                        innings=2,
                        score=score,
                        wickets_lost=min(wickets, 9),
                        balls_remaining=balls_remaining,
                        target_runs=target_runs,
                        batting_team=inn2_team,
                        bowling_team=inn2_other,
                        league=league,
                        total_balls=total_balls,
                    )
                    # Disable in-engine calibrator to get raw mean
                    _MC_CALIBRATOR_CACHE[model_dir] = None
                    res = simulate_one_over(state, n_simulations=n_sims, model_dir=model_dir)
                    raw_prob = res.mean_prob
                    if isinstance(calibrator, InningsMCCalibrators):
                        cal_prob = calibrator.calibrate(raw_prob, innings=2)
                    elif calibrator:
                        cal_prob = calibrator.calibrate(raw_prob)
                    else:
                        cal_prob = raw_prob
                    phase = _get_phase(balls_remaining, total_balls)
                    results.append({
                        "innings": 2,
                        "phase": phase,
                        "over": legal_balls // 6,
                        "pred_raw": raw_prob,
                        "pred_cal": cal_prob,
                        "actual": inn2_won,
                        "batting_team": inn2_team,
                        "bowling_team": inn2_other,
                        "score": score,
                        "wickets": wickets,
                        "balls_remaining": balls_remaining,
                    })
                except Exception:
                    pass

    return results


# ──────────────────────────────────────────────────────────
# Main analysis
# ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MC Engine Calibration Analysis")
    parser.add_argument("--json-dir", required=True, help="Directory with Cricsheet JSONs")
    parser.add_argument("--model-dir", required=True, help="Model directory with mc_calibrator.pkl")
    parser.add_argument("--league", default="t20i")
    parser.add_argument("--max-matches", type=int, default=200)
    parser.add_argument("--n-sims", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=0,
                        help="Number of parallel workers. 0=auto (cores-1), 1=sequential")
    args = parser.parse_args()

    np.random.seed(args.seed)

    # Determine worker count
    n_workers = args.workers if args.workers > 0 else max(1, os.cpu_count() - 1)

    # Load calibrator externally — prefer innings-specific over legacy single
    innings_cal_path = Path(args.model_dir) / "mc_calibrators_innings.pkl"
    cal_path = Path(args.model_dir) / "mc_calibrator.pkl"
    calibrator = None
    if innings_cal_path.exists():
        calibrator = InningsMCCalibrators.load(str(innings_cal_path))
        print(f"  Loaded innings-specific MC calibrators from {innings_cal_path}")
        print(f"  Inn1 Platt: coef={calibrator.inn1.model.coef_[0][0]:.4f}, intercept={calibrator.inn1.model.intercept_[0]:.4f}")
        print(f"  Inn2 Platt: coef={calibrator.inn2.model.coef_[0][0]:.4f}, intercept={calibrator.inn2.model.intercept_[0]:.4f}")
    elif cal_path.exists():
        calibrator = MCCalibrator.load(str(cal_path))
        print(f"  Loaded legacy MC calibrator from {cal_path}")
        print(f"  Platt params: coef={calibrator.model.coef_[0][0]:.4f}, "
              f"intercept={calibrator.model.intercept_[0]:.4f}")
    else:
        print(f"  WARNING: No MC calibrator found — calibrated = raw")

    # Find valid matches
    all_json = sorted(glob.glob(f"{args.json_dir}/*.json"))
    valid = []
    for f in all_json:
        with open(f) as fh:
            d = json.load(fh)
        if d.get("info", {}).get("outcome", {}).get("winner") and len(d.get("innings", [])) >= 2:
            valid.append(f)

    selected = valid[: args.max_matches]
    print(f"\n{'='*70}")
    print(f"  MC Engine Calibration Analysis")
    print(f"{'='*70}")
    print(f"  JSON dir:      {args.json_dir}")
    print(f"  Model dir:     {args.model_dir}")
    print(f"  League:        {args.league}")
    print(f"  Available:     {len(valid)} matches")
    print(f"  Selected:      {len(selected)} matches")
    print(f"  MC sims/point: {args.n_sims}")
    print(f"  Workers:       {n_workers}" + (" (sequential)" if n_workers == 1 else f" (parallel)"))
    print(f"{'='*70}\n")

    # Collect predictions — parallel or sequential
    all_results = []
    t0 = time.time()

    if n_workers > 1:
        # ── Parallel collection ──
        # Calibrator and args are pickled and sent to workers.
        # Each worker gets its own engine cache, avoiding contention.
        completed = 0
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = {
                executor.submit(
                    collect_match_predictions,
                    fp,
                    args.league,
                    args.model_dir,
                    args.n_sims,
                    calibrator,
                ): fp
                for fp in selected
            }
            for future in as_completed(futures):
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as e:
                    print(f"  WARN: Match failed: {e}")
                completed += 1
                if completed % 25 == 0:
                    elapsed = time.time() - t0
                    print(f"  [{completed}/{len(selected)}] {len(all_results)} predictions | {elapsed:.0f}s")
    else:
        # ── Sequential collection ──
        for i, fp in enumerate(selected):
            results = collect_match_predictions(fp, args.league, args.model_dir, args.n_sims, calibrator)
            all_results.extend(results)
            if (i + 1) % 25 == 0:
                elapsed = time.time() - t0
                print(f"  [{i+1}/{len(selected)}] {len(all_results)} predictions | {elapsed:.0f}s")

    elapsed_total = time.time() - t0
    print(f"\n  Collection done: {len(all_results)} predictions from {len(selected)} matches ({elapsed_total:.0f}s)\n")

    if len(all_results) < 30:
        print("  Too few predictions for analysis.")
        return

    # ── Team verification ──
    print(f"{'='*70}")
    print(f"  TEAM VERIFICATION")
    print(f"{'='*70}")
    inn1 = [r for r in all_results if r["innings"] == 1]
    inn2 = [r for r in all_results if r["innings"] == 2]
    print(f"  Innings 1: {len(inn1)} predictions")
    print(f"    Batting team won (actual=1): {sum(r['actual'] for r in inn1)}/{len(inn1)} = {np.mean([r['actual'] for r in inn1]):.3f}")
    print(f"    Mean pred RAW (batting):     {np.mean([r['pred_raw'] for r in inn1]):.3f}")
    print(f"    Mean pred CAL (batting):     {np.mean([r['pred_cal'] for r in inn1]):.3f}")
    print(f"  Innings 2: {len(inn2)} predictions")
    print(f"    Batting team won (actual=1): {sum(r['actual'] for r in inn2)}/{len(inn2)} = {np.mean([r['actual'] for r in inn2]):.3f}")
    print(f"    Mean pred RAW (batting):     {np.mean([r['pred_raw'] for r in inn2]):.3f}")
    print(f"    Mean pred CAL (batting):     {np.mean([r['pred_cal'] for r in inn2]):.3f}")
    print()

    # ── Helper for side-by-side table ──
    def _print_comparison(label: str, subset: list[dict]):
        if not subset:
            return
        p_raw = np.array([r["pred_raw"] for r in subset])
        p_cal = np.array([r["pred_cal"] for r in subset])
        acts = np.array([r["actual"] for r in subset])
        b_raw, b_cal = _brier(p_raw, acts), _brier(p_cal, acts)
        e_raw, e_cal = _ece(p_raw, acts), _ece(p_cal, acts)
        l_raw, l_cal = _logloss(p_raw, acts), _logloss(p_cal, acts)
        b_delta = b_cal - b_raw
        e_delta = e_cal - e_raw
        l_delta = l_cal - l_raw
        return (label, len(subset),
                b_raw, b_cal, b_delta,
                e_raw, e_cal, e_delta,
                l_raw, l_cal, l_delta,
                p_raw.mean(), p_cal.mean(), acts.mean())

    # ── Overall ──
    print(f"{'='*80}")
    print(f"  RAW vs CALIBRATED COMPARISON")
    print(f"{'='*80}")
    header = (f"  {'Segment':<20} {'N':>5} "
              f"{'Brier_R':>8} {'Brier_C':>8} {'Δ':>7} "
              f"{'ECE_R':>8} {'ECE_C':>8} {'Δ':>7} "
              f"{'LL_R':>8} {'LL_C':>8} {'Δ':>7}")
    sep = "  " + "-" * 105
    print(header)
    print(sep)

    # Gather rows
    rows = []
    # Overall
    row = _print_comparison("OVERALL", all_results)
    if row:
        rows.append(row)

    # By innings
    for inn in [1, 2]:
        subset = [r for r in all_results if r["innings"] == inn]
        row = _print_comparison(f"Inn {inn}", subset)
        if row:
            rows.append(row)

    # Separator
    rows.append(None)

    # By innings x phase
    for inn in [1, 2]:
        for phase in ["powerplay", "middle", "death"]:
            subset = [r for r in all_results if r["innings"] == inn and r["phase"] == phase]
            row = _print_comparison(f"Inn{inn}_{phase}", subset)
            if row:
                rows.append(row)

    for row in rows:
        if row is None:
            print(sep)
            continue
        label, n, br, bc, bd, er, ec, ed, lr, lc, ld, mpr, mpc, ma = row
        print(f"  {label:<20} {n:>5} "
              f"{br:>8.4f} {bc:>8.4f} {bd:>+7.4f} "
              f"{er:>8.4f} {ec:>8.4f} {ed:>+7.4f} "
              f"{lr:>8.4f} {lc:>8.4f} {ld:>+7.4f}")
    print()

    # ── Mean Pred vs Mean Actual ──
    print(f"{'='*80}")
    print(f"  MEAN PREDICTION vs ACTUAL (bias check)")
    print(f"{'='*80}")
    print(f"  {'Segment':<20} {'N':>5} {'MeanPred_R':>10} {'MeanPred_C':>10} {'MeanActual':>10} {'Gap_R':>8} {'Gap_C':>8}")
    print("  " + "-" * 80)

    bias_segments = [("OVERALL", all_results)]
    for inn in [1, 2]:
        bias_segments.append((f"Inn {inn}", [r for r in all_results if r["innings"] == inn]))
    for inn in [1, 2]:
        for phase in ["powerplay", "middle", "death"]:
            bias_segments.append(
                (f"Inn{inn}_{phase}", [r for r in all_results if r["innings"] == inn and r["phase"] == phase]))

    for label, subset in bias_segments:
        if not subset:
            continue
        mpr = np.mean([r["pred_raw"] for r in subset])
        mpc = np.mean([r["pred_cal"] for r in subset])
        ma = np.mean([r["actual"] for r in subset])
        print(f"  {label:<20} {len(subset):>5} {mpr:>10.4f} {mpc:>10.4f} {ma:>10.4f} {mpr-ma:>+8.4f} {mpc-ma:>+8.4f}")
    print()

    # ── Per-Over breakdown (calibrated) ──
    print(f"{'='*70}")
    print(f"  PER-OVER METRICS (calibrated)")
    print(f"{'='*70}")
    print(f"  {'Over':<8} {'Inn':>4} {'Phase':<10} {'Brier_R':>8} {'Brier_C':>8} {'ECE_C':>8} {'MeanP_C':>9} {'MeanAct':>9} {'N':>6}")
    print(f"  {'---'*22}")
    for inn in [1, 2]:
        for over_num in range(1, 21):
            subset = [r for r in all_results if r["innings"] == inn and r["over"] == over_num]
            if not subset or len(subset) < 5:
                continue
            p_raw = np.array([r["pred_raw"] for r in subset])
            p_cal = np.array([r["pred_cal"] for r in subset])
            a = np.array([r["actual"] for r in subset])
            phase = _get_phase(120 - over_num * 6, 120)
            print(f"  {over_num:<8} {inn:>4} {phase:<10} "
                  f"{_brier(p_raw,a):>8.4f} {_brier(p_cal,a):>8.4f} {_ece(p_cal,a):>8.4f} "
                  f"{p_cal.mean():>9.4f} {a.mean():>9.4f} {len(p_cal):>6}")
        if inn == 1:
            print(f"  {'---'*22}")
    print()

    # ── Reliability diagram (calibrated, 10 bins) ──
    preds_cal = np.array([r["pred_cal"] for r in all_results])
    preds_raw = np.array([r["pred_raw"] for r in all_results])
    acts_all = np.array([r["actual"] for r in all_results])

    print(f"{'='*80}")
    print(f"  RELIABILITY DIAGRAM (10 bins) — Raw vs Calibrated")
    print(f"{'='*80}")
    print(f"  {'Bin':<12} {'MeanP_R':>9} {'MeanP_C':>9} {'MeanAct':>9} {'Gap_R':>8} {'Gap_C':>8} {'N':>6}")
    print(f"  {'---'*20}")
    bin_edges = np.linspace(0, 1, 11)
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        # Use calibrated bins for bucketing
        mask = (preds_cal >= lo) & (preds_cal < hi)
        if mask.sum() < 3:
            continue
        mpr = preds_raw[mask].mean()
        mpc = preds_cal[mask].mean()
        ma = acts_all[mask].mean()
        print(f"  {lo:.1f}-{hi:.1f}     {mpr:>9.4f} {mpc:>9.4f} {ma:>9.4f} {mpr-ma:>+8.4f} {mpc-ma:>+8.4f} {mask.sum():>6}")
    print()

    # ── Summary judgment ──
    print(f"{'='*70}")
    print(f"  CALIBRATION IMPACT SUMMARY")
    print(f"{'='*70}")
    overall_br = _brier(preds_raw, acts_all)
    overall_bc = _brier(preds_cal, acts_all)
    overall_er = _ece(preds_raw, acts_all)
    overall_ec = _ece(preds_cal, acts_all)
    overall_lr = _logloss(preds_raw, acts_all)
    overall_lc = _logloss(preds_cal, acts_all)

    print(f"  {'Metric':<10} {'Raw':>10} {'Calibrated':>12} {'Change':>10}")
    print(f"  {'-'*45}")
    print(f"  {'Brier':<10} {overall_br:>10.4f} {overall_bc:>12.4f} {overall_bc - overall_br:>+10.4f}")
    print(f"  {'ECE':<10} {overall_er:>10.4f} {overall_ec:>12.4f} {overall_ec - overall_er:>+10.4f}")
    print(f"  {'LogLoss':<10} {overall_lr:>10.4f} {overall_lc:>12.4f} {overall_lc - overall_lr:>+10.4f}")
    print()

    # Inn-specific impact
    for inn in [1, 2]:
        subset = [r for r in all_results if r["innings"] == inn]
        if not subset:
            continue
        pr = np.array([r["pred_raw"] for r in subset])
        pc = np.array([r["pred_cal"] for r in subset])
        a = np.array([r["actual"] for r in subset])
        print(f"  Innings {inn}: Brier {_brier(pr,a):.4f} -> {_brier(pc,a):.4f} ({_brier(pc,a)-_brier(pr,a):+.4f}) | "
              f"ECE {_ece(pr,a):.4f} -> {_ece(pc,a):.4f} ({_ece(pc,a)-_ece(pr,a):+.4f})")
    print()

    # Verdict
    if overall_ec < overall_er:
        print(f"  Calibrator IMPROVES overall ECE by {overall_er - overall_ec:.4f}")
    else:
        print(f"  Calibrator WORSENS overall ECE by {overall_ec - overall_er:.4f}")

    if overall_bc < overall_br:
        print(f"  Calibrator IMPROVES overall Brier by {overall_br - overall_bc:.4f}")
    else:
        print(f"  Calibrator WORSENS overall Brier by {overall_bc - overall_br:.4f}")

    # Root cause analysis
    inn1_sub = [r for r in all_results if r["innings"] == 1]
    inn2_sub = [r for r in all_results if r["innings"] == 2]
    if inn1_sub:
        pr1 = np.array([r["pred_raw"] for r in inn1_sub])
        pc1 = np.array([r["pred_cal"] for r in inn1_sub])
        a1 = np.array([r["actual"] for r in inn1_sub])
        bias_raw = pr1.mean() - a1.mean()
        bias_cal = pc1.mean() - a1.mean()
        print(f"\n  INNINGS 1 BIAS: Raw {bias_raw:+.4f} -> Calibrated {bias_cal:+.4f}")
        if abs(bias_cal) > abs(bias_raw):
            print(f"  ⚠ Calibrator makes innings 1 bias WORSE")
            print(f"  ROOT CAUSE: mc_trainer.py only trains on innings 2 data.")
            print(f"  FIX: Train innings-specific calibrators (separate for inn1 & inn2)")

    if inn2_sub:
        pr2 = np.array([r["pred_raw"] for r in inn2_sub])
        pc2 = np.array([r["pred_cal"] for r in inn2_sub])
        a2 = np.array([r["actual"] for r in inn2_sub])
        bias_raw = pr2.mean() - a2.mean()
        bias_cal = pc2.mean() - a2.mean()
        print(f"  INNINGS 2 BIAS: Raw {bias_raw:+.4f} -> Calibrated {bias_cal:+.4f}")

    print()

    # Trust ranking
    segments = []
    for inn in [1, 2]:
        for phase in ["powerplay", "middle", "death"]:
            subset = [r for r in all_results if r["innings"] == inn and r["phase"] == phase]
            if len(subset) < 10:
                continue
            pc = np.array([r["pred_cal"] for r in subset])
            a = np.array([r["actual"] for r in subset])
            segments.append((f"Inn{inn}_{phase}", _brier(pc, a), _ece(pc, a), len(subset)))

    segments.sort(key=lambda x: x[1])
    print(f"  TRUST RANKING (calibrated, best -> worst by Brier):")
    for rank, (label, brier, ece, n) in enumerate(segments, 1):
        trust = "***" if brier < 0.15 else "**" if brier < 0.20 else "*"
        print(f"    {rank}. {label:<20} Brier={brier:.4f}  ECE={ece:.4f}  N={n:<5} {trust}")
    print()
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
