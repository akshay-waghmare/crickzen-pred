#!/usr/bin/env python3
"""
Train innings-based MC Platt-scaling calibrators for ODI directly from Cricsheet JSONs.

Extracts ball states from completed ODI matches, runs MC simulations at sampled
points, then fits Platt calibrators per innings (and optionally per innings×phase).

Produces a comprehensive RAW vs CALIBRATED comparison report.

Usage:
    python scripts/train_odi_mc_calibrator_from_json.py \
        --input-dir odis_json \
        --output-dir models/odi_mc_v1 \
        --gender male --min-year 2018 \
        --n-matches 200 --n-samples-per-match 6 \
        --n-sims 500
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bbl_pipeline.calibration.mc_calibrator import (
    MCCalibrator,
    InningsMCCalibrators,
    InningsPhaseCalibrators,
    over_to_phase,
    PHASE_PP,
    PHASE_MID,
    PHASE_SETUP,
    PHASE_DEATH,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

_TOTAL_OVERS = 50
_TOTAL_BALLS = 300
_ODI_PHASES = [PHASE_PP, PHASE_MID, PHASE_SETUP, PHASE_DEATH]


def _compute_ece(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error."""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (probs >= lo) & (probs < hi)
        if mask.sum() == 0:
            continue
        ece += abs(probs[mask].mean() - outcomes[mask].mean()) * mask.sum() / len(probs)
    return ece


def extract_ball_states_from_json(json_path: str, gender_filter: str = None, min_year: int = None):
    """Extract ball-by-ball states from a Cricsheet ODI JSON file.
    
    Returns list of dicts with: innings, over, ball, score, wickets, target, batting_team_won
    """
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

    info = data.get("info", {})
    
    # Filter
    match_type = info.get("match_type", "")
    if match_type not in ("ODI", "ODM"):
        return []
    if gender_filter and info.get("gender", "") != gender_filter:
        return []
    dates = info.get("dates", [])
    if min_year and dates:
        try:
            year = int(str(dates[0])[:4])
            if year < min_year:
                return []
        except (ValueError, IndexError):
            pass
    
    # Need a winner
    outcome = info.get("outcome", {})
    winner = outcome.get("winner")
    if not winner:
        return []
    
    # Get teams
    teams = info.get("teams", [])
    if len(teams) != 2:
        return []
    
    # Parse innings
    innings_data = data.get("innings", [])
    if len(innings_data) < 2:
        return []  # Need both innings complete
    
    # Build ball-by-ball state for each innings
    states = []
    innings_scores = {}  # Track final scores
    
    for inn_idx, inn in enumerate(innings_data[:2], 1):
        team_name = inn.get("team", "")
        batting_team_won = (team_name == winner)
        
        score = 0
        wickets = 0
        target = None
        
        if inn_idx == 2:
            # Target = first innings score + 1
            first_inn_score = innings_scores.get(1, 250)
            target = first_inn_score + 1
        
        overs_list = inn.get("overs", [])
        for over_data in overs_list:
            over_num = over_data.get("over", 0)  # 0-indexed
            deliveries = over_data.get("deliveries", [])
            
            ball_in_over = 0
            for delivery in deliveries:
                runs = delivery.get("runs", {})
                total_runs = runs.get("total", 0)
                is_wicket = len(delivery.get("wickets", [])) > 0
                
                # Check for extras that don't count as a ball
                extras = delivery.get("extras", {})
                is_wide = "wides" in extras
                is_noball = "noballs" in extras
                
                if not is_wide:
                    ball_in_over += 1
                
                # Record state BEFORE this delivery
                balls_bowled = over_num * 6 + ball_in_over
                balls_remaining = _TOTAL_BALLS - balls_bowled + 1
                
                if balls_remaining > 0 and balls_remaining <= _TOTAL_BALLS:
                    states.append({
                        "innings": inn_idx,
                        "over": over_num,  # 0-indexed
                        "ball": ball_in_over,
                        "score": score,
                        "wickets": wickets,
                        "balls_remaining": balls_remaining,
                        "target": target,
                        "batting_team_won": int(batting_team_won),
                        "phase": over_to_phase(over_num, _TOTAL_OVERS),
                    })
                
                # Update state after delivery
                score += total_runs
                if is_wicket:
                    wickets += 1
        
        innings_scores[inn_idx] = score
    
    return states


def run_mc_for_state(state_dict: dict, n_sims: int = 500, horizon: int = 6) -> float:
    """Run MC simulation for a single ball state."""
    from bbl_pipeline.simulation.state import MatchState as SimMatchState
    from bbl_pipeline.simulation.engine import simulate_vectorized
    
    innings = state_dict["innings"]
    score = state_dict["score"]
    wickets = min(9, state_dict["wickets"])
    balls_remaining = max(1, min(_TOTAL_BALLS, state_dict["balls_remaining"]))
    target = state_dict.get("target")
    
    sim_state = SimMatchState(
        innings=innings,
        score=score,
        wickets_lost=wickets,
        balls_remaining=balls_remaining,
        total_balls=_TOTAL_BALLS,
        target_runs=target,
        league="odi",
        batting_team="TeamA",
        bowling_team="TeamB",
    )
    
    result = simulate_vectorized(
        state=sim_state,
        horizon=min(horizon, balls_remaining),
        n_simulations=n_sims,
        apply_temp=False,
    )
    return float(result.mean_prob)


def print_comparison_table(title: str, sections: list):
    """Print a formatted comparison table."""
    print(f"\n{'='*90}")
    print(f"  {title}")
    print(f"{'='*90}")
    print(
        f"  {'Segment':<22} | {'N':>6} | "
        f"{'Raw Brier':>10} | {'Cal Brier':>10} | {'Δ Brier':>8} | "
        f"{'Raw ECE':>8} | {'Cal ECE':>8} | {'Δ ECE':>8}"
    )
    print(f"  {'-'*86}")
    for row in sections:
        delta_b = row["cal_brier"] - row["raw_brier"]
        delta_e = row["cal_ece"] - row["raw_ece"]
        sign_b = "+" if delta_b >= 0 else ""
        sign_e = "+" if delta_e >= 0 else ""
        print(
            f"  {row['name']:<22} | {row['n']:>6} | "
            f"{row['raw_brier']:>10.4f} | {row['cal_brier']:>10.4f} | {sign_b}{delta_b:>7.4f} | "
            f"{row['raw_ece']:>8.4f} | {row['cal_ece']:>8.4f} | {sign_e}{delta_e:>7.4f}"
        )
    print(f"  {'-'*86}")


def main():
    parser = argparse.ArgumentParser(
        description="Train ODI MC calibrators from Cricsheet JSONs with raw vs calibrated comparison"
    )
    parser.add_argument("--input-dir", required=True, help="Directory with ODI Cricsheet JSON files")
    parser.add_argument("--output-dir", default="models/odi_mc_v1", help="Output directory for calibrators")
    parser.add_argument("--gender", default="male", help="Gender filter (male/female)")
    parser.add_argument("--min-year", type=int, default=2018, help="Minimum year filter")
    parser.add_argument("--n-matches", type=int, default=200, help="Max matches to process")
    parser.add_argument("--n-samples-per-match", type=int, default=8, help="Ball states to sample per match")
    parser.add_argument("--n-sims", type=int, default=500, help="MC simulations per sample")
    parser.add_argument("--horizon", type=int, default=6, help="MC horizon (balls)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.RandomState(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    # ─── Step 1: Extract ball states from JSONs ───────────────────────
    logger.info(f"Scanning {args.input_dir} for ODI JSONs (gender={args.gender}, min_year={args.min_year})...")
    
    json_files = sorted(Path(args.input_dir).glob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files")
    
    all_states = []
    matches_used = 0
    
    # Shuffle for random sampling
    file_indices = rng.permutation(len(json_files))
    
    for idx in file_indices:
        if matches_used >= args.n_matches:
            break
        
        fp = json_files[idx]
        states = extract_ball_states_from_json(str(fp), args.gender, args.min_year)
        
        if not states:
            continue
        
        # Sample N states per match (spread across innings/phases)
        if len(states) > args.n_samples_per_match:
            sample_idx = rng.choice(len(states), size=args.n_samples_per_match, replace=False)
            states = [states[i] for i in sample_idx]
        
        all_states.extend(states)
        matches_used += 1
        
        if matches_used % 50 == 0:
            logger.info(f"  Processed {matches_used} matches, {len(all_states)} ball states")
    
    logger.info(f"Extracted {len(all_states)} ball states from {matches_used} matches")
    
    if len(all_states) < 100:
        logger.error("Too few states extracted. Check input directory and filters.")
        return 1
    
    # Print distribution by innings/phase
    for inn in [1, 2]:
        for phase in _ODI_PHASES:
            count = sum(1 for s in all_states if s["innings"] == inn and s["phase"] == phase)
            logger.info(f"  inn{inn}_{phase}: {count} samples")
    
    # ─── Step 2: Run MC simulations ───────────────────────────────────
    logger.info(f"Running {len(all_states)} × {args.n_sims} MC simulations (horizon={args.horizon}, workers={args.workers})...")
    t0 = time.time()
    
    mc_probs = np.zeros(len(all_states), dtype=float)
    
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_mc_for_state, s, args.n_sims, args.horizon): i
            for i, s in enumerate(all_states)
        }
        done = 0
        for future in as_completed(futures):
            i = futures[future]
            try:
                mc_probs[i] = future.result()
            except Exception as e:
                logger.debug(f"  Sample {i} failed: {e}, using 0.5")
                mc_probs[i] = 0.5
            done += 1
            if done % 100 == 0:
                elapsed = time.time() - t0
                rate = done / max(elapsed, 1e-9)
                eta = (len(all_states) - done) / max(rate, 1e-9)
                logger.info(f"  [{done}/{len(all_states)}] {rate:.1f} states/s, ETA {eta:.0f}s")
    
    sim_time = time.time() - t0
    logger.info(f"MC simulation complete in {sim_time:.1f}s ({len(all_states)/max(sim_time,1):.1f} states/s)")
    
    # Prepare arrays
    actuals = np.array([s["batting_team_won"] for s in all_states], dtype=float)
    innings_arr = np.array([s["innings"] for s in all_states])
    phases_arr = np.array([s["phase"] for s in all_states])
    
    # ─── Step 3: Train calibrators ────────────────────────────────────
    # Split: 70% train, 30% test (stratified by innings)
    perm = rng.permutation(len(all_states))
    split = int(len(all_states) * 0.7)
    train_idx, test_idx = perm[:split], perm[split:]
    
    logger.info(f"Train: {len(train_idx)}, Test: {len(test_idx)}")
    
    # ─── 3a: Overall calibrator (single) ──────────────────────────────
    cal_overall = MCCalibrator()
    cal_overall.fit(mc_probs[train_idx], actuals[train_idx])
    
    # ─── 3b: Innings calibrators (2) ─────────────────────────────────
    innings_cals = InningsMCCalibrators()
    for inn in [1, 2]:
        mask_train = innings_arr[train_idx] == inn
        if mask_train.sum() < 30:
            logger.warning(f"Too few inn{inn} training samples ({mask_train.sum()})")
            continue
        cal = MCCalibrator()
        cal.fit(mc_probs[train_idx[mask_train]], actuals[train_idx[mask_train]])
        if inn == 1:
            innings_cals.innings_1 = cal
        else:
            innings_cals.innings_2 = cal
    
    # ─── 3c: Innings × Phase calibrators (8) ─────────────────────────
    phase_cals = InningsPhaseCalibrators(total_overs=_TOTAL_OVERS)
    for inn in [1, 2]:
        for phase in _ODI_PHASES:
            mask_train = (innings_arr[train_idx] == inn) & (phases_arr[train_idx] == phase)
            if mask_train.sum() < 20:
                logger.warning(f"inn{inn}_{phase}: only {mask_train.sum()} training samples, skipping")
                continue
            cal = MCCalibrator()
            cal.fit(mc_probs[train_idx[mask_train]], actuals[train_idx[mask_train]])
            phase_cals.set(inn, phase, cal)
    
    # ─── Step 4: Evaluate ALL methods on TEST set ─────────────────────
    print("\n" + "=" * 90)
    print("  ODI MC CALIBRATION: RAW vs CALIBRATED COMPARISON")
    print("  " + "-" * 86)
    print(f"  Matches: {matches_used} | Samples: {len(all_states)} | Train: {len(train_idx)} | Test: {len(test_idx)}")
    print(f"  MC sims: {args.n_sims} | Horizon: {args.horizon} balls | Gender: {args.gender}")
    print("=" * 90)
    
    test_probs = mc_probs[test_idx]
    test_actuals = actuals[test_idx]
    test_innings = innings_arr[test_idx]
    test_phases = phases_arr[test_idx]
    
    # Calibrate test set with each method
    cal_overall_probs = cal_overall.calibrate_batch(test_probs)
    
    cal_innings_probs = np.zeros_like(test_probs)
    for i, (p, inn) in enumerate(zip(test_probs, test_innings)):
        cal_obj = innings_cals.innings_1 if inn == 1 else innings_cals.innings_2
        cal_innings_probs[i] = cal_obj.calibrate(p) if cal_obj else p
    
    cal_phase_probs = np.zeros_like(test_probs)
    for i, (p, inn, ph) in enumerate(zip(test_probs, test_innings, test_phases)):
        cal_obj = phase_cals.get(int(inn), ph)
        cal_phase_probs[i] = cal_obj.calibrate(p) if cal_obj else p
    
    # ─── Overall comparison ──────────────────────────────────────────
    methods = [
        ("Raw (uncalibrated)", test_probs),
        ("Overall (1 cal)", cal_overall_probs),
        ("Innings (2 cals)", cal_innings_probs),
        ("Inn×Phase (8 cals)", cal_phase_probs),
    ]
    
    print(f"\n  {'Method':<25} | {'Brier':>8} | {'ECE':>8} | {'LogLoss':>8} | {'Δ Brier':>8}")
    print(f"  {'-'*70}")
    
    raw_brier = brier_score_loss(test_actuals, test_probs)
    for name, preds in methods:
        brier = brier_score_loss(test_actuals, preds)
        ece = _compute_ece(preds, test_actuals)
        try:
            ll = log_loss(test_actuals, np.clip(preds, 0.001, 0.999))
        except Exception:
            ll = float("nan")
        delta = brier - raw_brier
        sign = "+" if delta >= 0 else ""
        print(f"  {name:<25} | {brier:>8.4f} | {ece:>8.4f} | {ll:>8.4f} | {sign}{delta:>7.4f}")
    
    # ─── By innings ──────────────────────────────────────────────────
    print(f"\n  {'--- BY INNINGS ---':<25}")
    print(f"  {'Segment':<25} | {'N':>5} | {'Raw Brier':>10} | {'Inn Cal':>10} | {'Phase Cal':>10} | {'Δ(Inn)':>8} | {'Δ(Phase)':>8}")
    print(f"  {'-'*85}")
    
    for inn in [1, 2]:
        mask = test_innings == inn
        if mask.sum() == 0:
            continue
        raw_b = brier_score_loss(test_actuals[mask], test_probs[mask])
        inn_b = brier_score_loss(test_actuals[mask], cal_innings_probs[mask])
        pha_b = brier_score_loss(test_actuals[mask], cal_phase_probs[mask])
        d_inn = inn_b - raw_b
        d_pha = pha_b - raw_b
        print(
            f"  {'Innings ' + str(inn):<25} | {mask.sum():>5} | {raw_b:>10.4f} | {inn_b:>10.4f} | "
            f"{pha_b:>10.4f} | {'+' if d_inn >= 0 else ''}{d_inn:>7.4f} | {'+' if d_pha >= 0 else ''}{d_pha:>7.4f}"
        )
    
    # ─── By phase ────────────────────────────────────────────────────
    print(f"\n  {'--- BY PHASE ---':<25}")
    print(f"  {'Segment':<25} | {'N':>5} | {'Raw Brier':>10} | {'Inn Cal':>10} | {'Phase Cal':>10} | {'Δ(Inn)':>8} | {'Δ(Phase)':>8}")
    print(f"  {'-'*85}")
    
    for phase in _ODI_PHASES:
        mask = test_phases == phase
        if mask.sum() == 0:
            continue
        raw_b = brier_score_loss(test_actuals[mask], test_probs[mask])
        inn_b = brier_score_loss(test_actuals[mask], cal_innings_probs[mask])
        pha_b = brier_score_loss(test_actuals[mask], cal_phase_probs[mask])
        d_inn = inn_b - raw_b
        d_pha = pha_b - raw_b
        print(
            f"  {phase:<25} | {mask.sum():>5} | {raw_b:>10.4f} | {inn_b:>10.4f} | "
            f"{pha_b:>10.4f} | {'+' if d_inn >= 0 else ''}{d_inn:>7.4f} | {'+' if d_pha >= 0 else ''}{d_pha:>7.4f}"
        )
    
    # ─── By innings × phase ─────────────────────────────────────────
    print(f"\n  {'--- BY INNINGS × PHASE ---':<25}")
    print(f"  {'Segment':<25} | {'N':>5} | {'Raw Brier':>10} | {'Raw ECE':>8} | {'Phase Brier':>11} | {'Phase ECE':>9}")
    print(f"  {'-'*85}")
    
    for inn in [1, 2]:
        for phase in _ODI_PHASES:
            mask = (test_innings == inn) & (test_phases == phase)
            if mask.sum() < 5:
                continue
            raw_b = brier_score_loss(test_actuals[mask], test_probs[mask])
            raw_e = _compute_ece(test_probs[mask], test_actuals[mask])
            pha_b = brier_score_loss(test_actuals[mask], cal_phase_probs[mask])
            pha_e = _compute_ece(cal_phase_probs[mask], test_actuals[mask])
            print(
                f"  inn{inn}_{phase:<18} | {mask.sum():>5} | {raw_b:>10.4f} | {raw_e:>8.4f} | "
                f"{pha_b:>11.4f} | {pha_e:>9.4f}"
            )
    
    # ─── Probability bins analysis ───────────────────────────────────
    print(f"\n  {'--- PROBABILITY BINS (RAW) ---':<25}")
    print(f"  {'Bin':<15} | {'N':>5} | {'Mean Pred':>9} | {'Mean Actual':>11} | {'Gap':>8}")
    print(f"  {'-'*60}")
    
    bin_edges = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (test_probs >= lo) & (test_probs < hi)
        if mask.sum() == 0:
            continue
        mean_p = test_probs[mask].mean()
        mean_a = test_actuals[mask].mean()
        gap = abs(mean_p - mean_a)
        print(f"  [{lo:.1f}, {hi:.1f}){'':>5} | {mask.sum():>5} | {mean_p:>9.4f} | {mean_a:>11.4f} | {gap:>8.4f}")
    
    # ─── Save calibrators ────────────────────────────────────────────
    # Save innings-specific (2 calibrators)
    innings_path = os.path.join(args.output_dir, "mc_calibrators_innings.pkl")
    innings_cals.save(innings_path)
    logger.info(f"Saved innings calibrators (2) → {innings_path}")
    
    # Save innings × phase (8 calibrators)
    phase_path = os.path.join(args.output_dir, "mc_calibrators_innings_phase.pkl")
    phase_cals.save(phase_path)
    logger.info(f"Saved innings×phase calibrators (8) → {phase_path}")
    
    # Save overall (legacy)
    overall_path = os.path.join(args.output_dir, "mc_calibrator.pkl")
    cal_overall.save(overall_path)
    logger.info(f"Saved overall calibrator (1) → {overall_path}")
    
    print(f"\n{'='*90}")
    print(f"  CALIBRATORS SAVED TO: {args.output_dir}/")
    print(f"    mc_calibrator.pkl                (1 overall)")
    print(f"    mc_calibrators_innings.pkl        (2 innings-specific)")
    print(f"    mc_calibrators_innings_phase.pkl  (8 innings×phase)")
    print(f"{'='*90}")
    
    total_time = time.time() - t0
    logger.info(f"Total elapsed: {total_time:.1f}s")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
