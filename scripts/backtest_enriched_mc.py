#!/usr/bin/env python3
"""
Backtest enriched MC vs base MC on completed ODI matches.

Measures Brier score improvement (or regression) from MC enrichments
(partnership momentum, new batsman factor, pitch deterioration).

Usage:
    python scripts/backtest_enriched_mc.py \
        --input-dir odis_json \
        --n-matches 100 \
        --n-simulations 500 \
        --min-year 2015

Output:
    Prints a summary table comparing base vs enriched MC Brier scores.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import brier_score_loss

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bbl_pipeline.simulation.state import MatchState
from bbl_pipeline.simulation.sampler import NextBallSampler
from bbl_pipeline.simulation.evaluator import TerminalStateEvaluator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _extract_ball_states(match_json: dict) -> list[dict]:
    """Extract ball-by-ball states from a completed ODI match JSON.
    
    Returns list of dicts with:
        innings, over, ball, score, wickets, target, batting_team, bowling_team,
        winner (the actual match winner)
    """
    info = match_json.get("info", {})
    outcome = info.get("outcome", {})
    
    # Skip no-result matches
    if "winner" not in outcome:
        return []
    
    winner = outcome["winner"]
    teams = info.get("players", {})
    team_names = list(teams.keys())
    if len(team_names) < 2:
        return []
    
    innings_data = match_json.get("innings", [])
    if len(innings_data) < 2:
        return []
    
    # Determine total overs from match type
    overs_per_innings = info.get("overs", 50)
    total_balls = overs_per_innings * 6
    
    states = []
    first_innings_total = None
    
    for inn_idx, inn in enumerate(innings_data[:2]):
        innings_num = inn_idx + 1
        batting_team = inn.get("team", team_names[inn_idx])
        bowling_team = [t for t in team_names if t != batting_team]
        bowling_team = bowling_team[0] if bowling_team else team_names[1 - inn_idx]
        
        score = 0
        wickets = 0
        
        for over_data in inn.get("overs", []):
            over_num = over_data.get("over", 0)
            for ball_idx, delivery in enumerate(over_data.get("deliveries", [])):
                runs = delivery.get("runs", {}).get("total", 0)
                is_wicket = len(delivery.get("wickets", [])) > 0
                
                # Record state BEFORE this delivery
                balls_bowled = over_num * 6 + ball_idx
                # Skip if beyond total (shouldn't happen but safety)
                if balls_bowled >= total_balls:
                    break
                
                balls_remaining = total_balls - balls_bowled
                target = (first_innings_total + 1) if innings_num == 2 and first_innings_total else None
                
                # Determine if batting team won
                batting_team_won = 1 if batting_team == winner else 0
                
                # Sample every 6th ball to reduce data size
                if balls_bowled % 6 == 0 and balls_remaining > 0:
                    states.append({
                        "innings": innings_num,
                        "over": over_num,
                        "score": score,
                        "wickets": wickets,
                        "balls_remaining": balls_remaining,
                        "total_balls": total_balls,
                        "target": target,
                        "batting_team": batting_team,
                        "bowling_team": bowling_team,
                        "batting_team_won": batting_team_won,
                    })
                
                # Apply delivery
                score += runs
                if is_wicket:
                    wickets += 1
        
        if innings_num == 1:
            first_innings_total = score
    
    return states


def _simulate_prob(state_dict: dict, enrichments: bool, n_sims: int, seed: int) -> float:
    """Run MC simulation for a single ball state."""
    sampler = NextBallSampler(seed=seed, league="odi", enrichments=enrichments)
    evaluator = TerminalStateEvaluator(model_dir="models/nonexistent")
    
    state = MatchState(
        innings=state_dict["innings"],
        score=state_dict["score"],
        wickets_lost=state_dict["wickets"],
        balls_remaining=state_dict["balls_remaining"],
        total_balls=state_dict["total_balls"],
        target_runs=state_dict.get("target"),
        league="odi",
        batting_team=state_dict["batting_team"],
        bowling_team=state_dict["bowling_team"],
    )
    
    probs = np.zeros(n_sims)
    for i in range(n_sims):
        sim_state = state.copy()
        s = NextBallSampler(seed=seed + i, league="odi", enrichments=enrichments)
        while not sim_state.is_over:
            runs, is_wicket = s.sample(sim_state)
            sim_state = sim_state.apply_outcome(runs=int(runs), is_wicket=is_wicket)
        probs[i] = evaluator.evaluate(sim_state, apply_temp=False)
    
    return float(np.mean(probs))


def main():
    parser = argparse.ArgumentParser(
        description="Backtest enriched vs base MC on completed ODI matches",
    )
    parser.add_argument("--input-dir", required=True, help="Directory with ODI JSON files")
    parser.add_argument("--n-matches", type=int, default=100, help="Max matches to process")
    parser.add_argument("--n-simulations", type=int, default=200, help="MC sims per state")
    parser.add_argument("--min-year", type=int, default=2015, help="Min match year")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    
    rng = np.random.RandomState(args.seed)
    
    # Load matches
    json_files = sorted(Path(args.input_dir).glob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files in {args.input_dir}")
    
    all_states = []
    matches_used = 0
    
    for jf in json_files:
        if matches_used >= args.n_matches:
            break
        try:
            with open(jf) as f:
                match = json.load(f)
            # Year filter
            dates = match.get("info", {}).get("dates", [])
            if dates and int(str(dates[0])[:4]) < args.min_year:
                continue
            # Overs filter (50-over only)
            overs = match.get("info", {}).get("overs", 50)
            if overs != 50:
                continue
            
            states = _extract_ball_states(match)
            if states:
                all_states.extend(states)
                matches_used += 1
        except Exception:
            continue
    
    logger.info(f"Extracted {len(all_states)} ball states from {matches_used} matches")
    
    if not all_states:
        logger.error("No valid states found")
        return 1
    
    # Sample states for efficiency
    max_states = min(2000, len(all_states))
    indices = rng.choice(len(all_states), size=max_states, replace=False)
    sampled = [all_states[i] for i in indices]
    logger.info(f"Sampled {len(sampled)} states for evaluation")
    
    # Run MC simulations
    base_probs = np.zeros(len(sampled))
    enriched_probs = np.zeros(len(sampled))
    actuals = np.array([s["batting_team_won"] for s in sampled], dtype=float)
    
    t0 = time.time()
    for i, state in enumerate(sampled):
        base_probs[i] = _simulate_prob(state, enrichments=False, n_sims=args.n_simulations, seed=args.seed + i)
        enriched_probs[i] = _simulate_prob(state, enrichments=True, n_sims=args.n_simulations, seed=args.seed + i)
        
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(sampled) - i - 1) / rate
            logger.info(f"  [{i+1}/{len(sampled)}] {rate:.1f} states/s, ETA {eta:.0f}s")
    
    elapsed = time.time() - t0
    logger.info(f"Evaluation complete in {elapsed:.1f}s")
    
    # Compute metrics
    base_brier = brier_score_loss(actuals, base_probs)
    enriched_brier = brier_score_loss(actuals, enriched_probs)
    improvement = (base_brier - enriched_brier) / base_brier * 100
    
    print(f"\n{'='*60}")
    print("BACKTEST: ENRICHED MC vs BASE MC  (ODI)")
    print(f"{'='*60}")
    print(f"Matches: {matches_used}")
    print(f"Ball states evaluated: {len(sampled)}")
    print(f"MC simulations per state: {args.n_simulations}")
    print(f"{'─'*60}")
    print(f"{'Method':<20} | {'Brier':>10} | {'Improvement':>12}")
    print(f"{'─'*60}")
    print(f"{'Base MC':<20} | {base_brier:>10.4f} | {'—':>12}")
    print(f"{'Enriched MC':<20} | {enriched_brier:>10.4f} | {improvement:>+11.2f}%")
    print(f"{'='*60}")
    
    if improvement > 0:
        print(f"\n✓ Enrichments improved Brier by {improvement:.2f}%")
    else:
        print(f"\n✗ Enrichments worsened Brier by {abs(improvement):.2f}%")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
