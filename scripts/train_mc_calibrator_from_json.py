#!/usr/bin/env python3
"""
Train MCCalibrator (Platt scaling) from BBL match JSONs.

Runs MC predictions at each over-end checkpoint across all matches,
collects (raw_MC_prob, actual_outcome) pairs, and fits a Platt calibrator.

Usage:
    python scripts/train_mc_calibrator_from_json.py \
        --json-dir bbl_male_json \
        --model-dir models/t20_male_v2 \
        --max-matches 100 \
        --n-sims 200
"""

import argparse
import glob
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bbl_pipeline.simulation import MatchState, simulate
from bbl_pipeline.calibration.mc_calibrator import MCCalibrator


def count_legal(delivery: dict) -> int:
    extras = delivery.get("extras", {})
    if "wides" in extras or "noballs" in extras:
        return 0
    return 1


def collect_from_match(filepath: str, n_sims: int = 200) -> list:
    """Run MC predictions at each over-end and return (pred, outcome) pairs."""
    with open(filepath) as f:
        data = json.load(f)

    info = data["info"]
    outcome = info.get("outcome", {})
    innings_data = data.get("innings", [])
    if len(innings_data) < 2:
        return []

    winner = outcome.get("winner")
    teams = info["teams"]
    if not winner or winner not in teams:
        return []

    target_info = innings_data[1].get("target", {})
    target_overs = target_info.get("overs", 20)
    target_runs = target_info.get("runs")
    if target_runs is None:
        return []

    # Determine total overs
    inn2_total_overs = target_overs
    total_balls = inn2_total_overs * 6
    if total_balls < 6 or total_balls > 120 or total_balls % 6 != 0:
        return []

    batting_team = innings_data[1]["team"]
    bowling_team = [t for t in teams if t != batting_team][0]
    batting_won = 1 if winner == batting_team else 0

    results = []
    score = 0
    wickets = 0
    legal_balls = 0

    for ov in innings_data[1]["overs"]:
        for d in ov["deliveries"]:
            runs = d["runs"]["total"]
            is_wkt = bool(d.get("wickets"))
            legal_balls += count_legal(d)
            score += runs
            if is_wkt:
                wickets += 1

            balls_remaining = max(0, total_balls - legal_balls)

            # Checkpoint at end of each over
            if legal_balls % 6 == 0 and balls_remaining > 0 and score < target_runs:
                try:
                    state = MatchState(
                        innings=2,
                        score=score,
                        wickets_lost=min(wickets, 9),
                        balls_remaining=balls_remaining,
                        target_runs=target_runs,
                        batting_team=batting_team,
                        bowling_team=bowling_team,
                        league="bbl",
                        total_balls=total_balls,
                    )
                    result = simulate(state, horizon=6, n_simulations=n_sims)
                    results.append({
                        "pred": result.mean_prob,
                        "actual": batting_won,
                        "total_overs": inn2_total_overs,
                    })
                except Exception:
                    pass

    return results


def compute_ece(probs, outcomes, n_bins=10):
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (probs >= lo) & (probs < hi)
        if mask.sum() == 0:
            continue
        ece += abs(probs[mask].mean() - outcomes[mask].mean()) * mask.sum() / len(probs)
    return ece


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-dir", default="bbl_male_json")
    parser.add_argument("--model-dir", default="models/t20_male_v2")
    parser.add_argument("--max-matches", type=int, default=100)
    parser.add_argument("--n-sims", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    np.random.seed(args.seed)

    # Find all completed matches (both DLS and standard)
    all_json = sorted(glob.glob(f"{args.json_dir}/*.json"))
    valid = []
    for f in all_json:
        with open(f) as fh:
            d = json.load(fh)
        if d.get("info", {}).get("outcome", {}).get("winner") and len(d.get("innings", [])) >= 2:
            valid.append(f)

    selected = valid[:args.max_matches]
    print(f"Training on {len(selected)} matches ({len(valid)} available)")

    all_results = []
    t0 = time.time()
    for i, fp in enumerate(selected):
        results = collect_from_match(fp, n_sims=args.n_sims)
        all_results.extend(results)
        if (i + 1) % 10 == 0:
            elapsed = time.time() - t0
            print(f"  {i+1}/{len(selected)} matches, {len(all_results)} predictions ({elapsed:.0f}s)")

    elapsed = time.time() - t0
    print(f"\nCollected {len(all_results)} predictions from {len(selected)} matches in {elapsed:.0f}s")

    if len(all_results) < 50:
        print("Too few samples to train calibrator!")
        return 1

    preds = np.array([r["pred"] for r in all_results])
    actuals = np.array([r["actual"] for r in all_results])

    # Train/val split (80/20)
    n = len(preds)
    perm = np.random.permutation(n)
    split = int(n * 0.8)
    train_idx, val_idx = perm[:split], perm[split:]

    # Fit calibrator on training set
    calibrator = MCCalibrator()
    calibrator.fit(preds[train_idx], actuals[train_idx])
    print(f"\nFitted: {calibrator.summary()}")

    # Validate
    val_preds = preds[val_idx]
    val_acts = actuals[val_idx]
    val_cal = calibrator.calibrate_batch(val_preds)

    raw_brier = np.mean((val_preds - val_acts) ** 2)
    cal_brier = np.mean((val_cal - val_acts) ** 2)
    raw_ece = compute_ece(val_preds, val_acts)
    cal_ece = compute_ece(val_cal, val_acts)

    print(f"\n{'='*50}")
    print(f"VALIDATION ({len(val_preds)} samples)")
    print(f"{'='*50}")
    print(f"{'Metric':<12} {'Raw':>10} {'Calibrated':>10} {'Delta':>10}")
    print(f"{'-'*42}")
    print(f"{'Brier':<12} {raw_brier:>10.4f} {cal_brier:>10.4f} {cal_brier - raw_brier:>+10.4f}")
    print(f"{'ECE':<12} {raw_ece:>10.4f} {cal_ece:>10.4f} {cal_ece - raw_ece:>+10.4f}")

    # Reliability
    print(f"\nReliability (validation):")
    bin_edges = np.linspace(0, 1, 11)
    for i in range(10):
        mask = (val_cal >= bin_edges[i]) & (val_cal < bin_edges[i+1])
        if mask.sum() < 3:
            continue
        label = f"{bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}"
        mp = val_cal[mask].mean()
        aw = val_acts[mask].mean()
        print(f"  {label}: pred={mp:.3f}, actual={aw:.3f}, gap={aw-mp:+.3f}, n={mask.sum()}")

    # Save
    out_path = Path(args.model_dir) / "mc_calibrator.pkl"
    calibrator.save(str(out_path))
    print(f"\nCalibrator saved to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
