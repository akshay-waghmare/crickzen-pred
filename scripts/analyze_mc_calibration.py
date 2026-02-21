"""
Calibration analysis of the reduced-over MC engine.

Runs MC predictions at multiple checkpoints across all DLS matches in the
BBL dataset and computes calibration metrics (Brier, ECE, reliability).
"""

import json
import glob
import numpy as np
from collections import defaultdict

from bbl_pipeline.simulation import MatchState, simulate, get_phase
from bbl_pipeline.features.format_config import FormatConfig


def count_legal(delivery: dict) -> int:
    extras = delivery.get("extras", {})
    if "wides" in extras or "noballs" in extras:
        return 0
    return 1


def analyze_match(filepath: str) -> list:
    """Run MC predictions at end of each over and return (pred, outcome) pairs."""
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

    # Determine actual overs per innings from target metadata
    target = innings_data[1].get("target", {})
    target_overs = target.get("overs", 20)
    target_runs = target.get("runs")
    if target_runs is None:
        return []

    # Use the target overs as total overs for both innings
    # (DLS matches: inn1 may be full 20, inn2 reduced, or both reduced)
    inn1_total_overs = 20  # Inn1 is typically full, or we use 20 as reference
    inn2_total_overs = target_overs

    # For inn1, check actual balls bowled
    inn1_legal = 0
    for ov in innings_data[0]["overs"]:
        for d in ov["deliveries"]:
            inn1_legal += count_legal(d)
    inn1_actual_overs = inn1_legal // 6
    if inn1_actual_overs < 20:
        inn1_total_overs = inn1_actual_overs

    results = []

    # ----- INNINGS 2 ONLY (where we have a target) -----
    batting_team = innings_data[1]["team"]
    bowling_team = [t for t in teams if t != batting_team][0]
    batting_won = 1 if winner == batting_team else 0

    total_balls = inn2_total_overs * 6
    if total_balls < 6 or total_balls > 120 or total_balls % 6 != 0:
        return []

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

            # Record at end of each over
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
                    np.random.seed(42)
                    result = simulate(state, horizon=6, n_simulations=500)
                    phase = get_phase(balls_remaining, total_balls=total_balls)
                    overs_completed = legal_balls / 6
                    pct_complete = overs_completed / inn2_total_overs

                    results.append({
                        "pred": result.mean_prob,
                        "actual": batting_won,
                        "phase": phase,
                        "overs_completed": overs_completed,
                        "total_overs": inn2_total_overs,
                        "pct_complete": pct_complete,
                        "score": score,
                        "wickets": wickets,
                        "target": target_runs,
                        "rrr": (target_runs - score) / (balls_remaining / 6),
                    })
                except Exception:
                    pass

    return results


def compute_ece(predictions, actuals, n_bins=10):
    """Compute Expected Calibration Error."""
    predictions = np.array(predictions)
    actuals = np.array(actuals)
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (predictions >= bin_edges[i]) & (predictions < bin_edges[i + 1])
        if mask.sum() == 0:
            continue
        bin_pred = predictions[mask].mean()
        bin_actual = actuals[mask].mean()
        ece += mask.sum() / len(predictions) * abs(bin_pred - bin_actual)
    return ece


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["dls", "standard", "both"], default="dls",
                        help="Which matches: dls (DLS only), standard (20-over), both")
    parser.add_argument("--max-matches", type=int, default=0)
    args = parser.parse_args()

    matches = glob.glob("bbl_male_json/*.json")
    dls_files = []
    standard_files = []
    for f in matches:
        with open(f) as fh:
            data = json.load(fh)
        info = data.get("info", {})
        outcome = info.get("outcome", {})
        if "method" in outcome:
            dls_files.append(f)
        elif outcome.get("winner") and len(data.get("innings", [])) >= 2:
            standard_files.append(f)

    if args.mode == "dls":
        selected = dls_files
        print(f"Found {len(dls_files)} DLS matches")
    elif args.mode == "standard":
        selected = standard_files
        print(f"Found {len(standard_files)} standard 20-over matches")
    else:
        selected = dls_files + standard_files
        print(f"Found {len(dls_files)} DLS + {len(standard_files)} standard = {len(selected)} total")

    if args.max_matches > 0:
        selected = sorted(selected)[:args.max_matches]

    print()

    all_results = []
    match_count = 0
    for filepath in sorted(selected):
        results = analyze_match(filepath)
        if results:
            match_count += 1
            all_results.extend(results)

    print(f"Analyzed {match_count} matches, {len(all_results)} prediction points")
    print()

    if not all_results:
        print("No predictions to analyze!")
        return

    predictions = np.array([r["pred"] for r in all_results])
    actuals = np.array([r["actual"] for r in all_results])

    # Overall metrics
    brier = np.mean((predictions - actuals) ** 2)
    ece = compute_ece(predictions, actuals)
    log_loss_val = -np.mean(
        actuals * np.log(np.clip(predictions, 1e-7, 1))
        + (1 - actuals) * np.log(np.clip(1 - predictions, 1e-7, 1))
    )

    print("=" * 60)
    print("OVERALL CALIBRATION METRICS (Innings 2 only)")
    print("=" * 60)
    print(f"  Brier Score:  {brier:.4f}")
    print(f"  ECE (10-bin): {ece:.4f}")
    print(f"  Log Loss:     {log_loss_val:.4f}")
    print(f"  Mean Pred:    {predictions.mean():.4f}")
    print(f"  Actual Win%:  {actuals.mean():.4f}")
    print()

    # Reliability diagram (text)
    print("=" * 60)
    print("RELIABILITY DIAGRAM (Predicted vs Actual Win Rate)")
    print("=" * 60)
    print(f"{'Bin':>12} | {'Count':>6} | {'Mean Pred':>10} | {'Actual Win%':>12} | {'Gap':>8}")
    print("-" * 60)

    bin_edges = np.linspace(0, 1, 11)
    for i in range(10):
        mask = (predictions >= bin_edges[i]) & (predictions < bin_edges[i + 1])
        count = mask.sum()
        if count == 0:
            continue
        mean_pred = predictions[mask].mean()
        actual_wr = actuals[mask].mean()
        gap = actual_wr - mean_pred
        label = f"{bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}"
        print(f"{label:>12} | {count:>6} | {mean_pred:>9.3f} | {actual_wr:>11.3f} | {gap:>+7.3f}")

    print()

    # By match completion percentage
    print("=" * 60)
    print("CALIBRATION BY MATCH STAGE")
    print("=" * 60)
    print(f"{'Stage':>20} | {'Count':>6} | {'Brier':>8} | {'Mean Pred':>10} | {'Actual':>8}")
    print("-" * 60)

    stages = [
        ("Early (0-33%)", lambda r: r["pct_complete"] <= 0.33),
        ("Middle (33-66%)", lambda r: 0.33 < r["pct_complete"] <= 0.66),
        ("Late (66-100%)", lambda r: r["pct_complete"] > 0.66),
    ]

    for name, cond in stages:
        filtered = [r for r in all_results if cond(r)]
        if not filtered:
            continue
        preds = np.array([r["pred"] for r in filtered])
        acts = np.array([r["actual"] for r in filtered])
        b = np.mean((preds - acts) ** 2)
        print(f"{name:>20} | {len(filtered):>6} | {b:>7.4f} | {preds.mean():>9.3f} | {acts.mean():>7.3f}")

    print()

    # By reduced vs full overs
    print("=" * 60)
    print("REDUCED vs FULL OVERS")
    print("=" * 60)
    reduced = [r for r in all_results if r["total_overs"] < 20]
    full = [r for r in all_results if r["total_overs"] >= 20]

    for label, subset in [("Reduced (<20 ov)", reduced), ("Full (20 ov)", full)]:
        if not subset:
            continue
        preds = np.array([r["pred"] for r in subset])
        acts = np.array([r["actual"] for r in subset])
        b = np.mean((preds - acts) ** 2)
        e = compute_ece(preds, acts)
        print(f"  {label}: n={len(subset)}, Brier={b:.4f}, ECE={e:.4f}, "
              f"mean_pred={preds.mean():.3f}, actual={acts.mean():.3f}")

    print()

    # Distribution of predictions
    print("=" * 60)
    print("PREDICTION DISTRIBUTION")
    print("=" * 60)
    for thresh in [0.5, 0.7, 0.8, 0.9, 0.95, 0.99]:
        pct = (predictions >= thresh).mean() * 100
        print(f"  Predictions >= {thresh:.2f}: {pct:.1f}%")

    pct_extreme = ((predictions >= 0.95) | (predictions <= 0.05)).mean() * 100
    print(f"  Extreme (>=0.95 or <=0.05): {pct_extreme:.1f}%")


if __name__ == "__main__":
    main()
