#!/usr/bin/env python
"""
Extract ODI phase-specific run distributions and wicket rates from Cricsheet JSON files.

Parses ball-by-ball data from 3,000+ ODI matches and computes:
  - Per-phase run probability vectors (0/1/2/3/4/5/6) for 4 ODI phases
  - Per-phase wicket probability
  - Per-wickets-down wicket multiplier table

Usage:
    python scripts/extract_odi_phase_distributions.py \
        --input-dir odis_json \
        --output data/phase_distributions_odi.json \
        --gender male \
        --min-year 2010 \
        --verbose

Output: phase_distributions_{league}.json matching data-model.md schema.
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np


# ===========================================================================
# ODI Phase Boundaries (50-over format)
# ===========================================================================
# Powerplay: overs 1-10 (over_num 0-9)
# Middle:    overs 11-34 (over_num 10-33)
# Setup:     overs 35-40 (over_num 34-39)
# Death:     overs 41-50 (over_num 40-49)

PP_END = 10       # First over of middle phase (0-indexed)
MID_END = 34      # First over of setup phase
SETUP_END = 40    # First over of death phase


def get_phase(over_num: int) -> str:
    """Map 0-indexed over number to ODI phase."""
    if over_num < PP_END:
        return "powerplay"
    elif over_num < MID_END:
        return "middle"
    elif over_num < SETUP_END:
        return "setup"
    else:
        return "death"


def parse_match(filepath: Path, gender_filter: str | None = None, min_year: int | None = None) -> dict | None:
    """
    Parse a single Cricsheet ODI JSON file.

    Returns dict with ball-level data grouped by phase, or None if filtered out.
    """
    with open(filepath) as f:
        data = json.load(f)

    info = data.get("info", {})

    # Filter by match type
    match_type = info.get("match_type", "")
    if match_type not in ("ODI", "ODM"):
        return None

    # Filter by gender
    if gender_filter:
        match_gender = info.get("gender", "")
        if match_gender != gender_filter:
            return None

    # Filter by year
    dates = info.get("dates", [])
    if min_year and dates:
        try:
            year = int(str(dates[0])[:4])
            if year < min_year:
                return None
        except (ValueError, IndexError):
            pass

    # Must have outcome (complete match)
    outcome = info.get("outcome", {})
    if not outcome:
        return None

    # Parse innings
    result = {
        "match_id": filepath.stem,
        "gender": info.get("gender", "unknown"),
        "dates": dates,
        "teams": info.get("teams", []),
        "balls": [],  # List of (phase, total_runs, is_wicket, wickets_before)
    }

    innings_list = data.get("innings", [])
    for inn_idx, innings in enumerate(innings_list[:2]):  # First two innings only
        wickets_lost = 0
        for over_data in innings.get("overs", []):
            over_num = over_data.get("over", 0)
            phase = get_phase(over_num)

            for delivery in over_data.get("deliveries", []):
                runs = delivery.get("runs", {})
                total_runs = runs.get("total", 0)
                is_wicket = bool(delivery.get("wickets"))

                # Cap runs at 6 for distribution (7+ = 6 + extras, rare)
                run_bucket = min(total_runs, 6)

                result["balls"].append({
                    "phase": phase,
                    "runs": run_bucket,
                    "is_wicket": is_wicket,
                    "wickets_before": wickets_lost,
                    "innings": inn_idx + 1,
                })

                if is_wicket:
                    # Count each wicket in the delivery
                    wickets_lost += len(delivery.get("wickets", []))

    return result


def extract_distributions(
    input_dir: str,
    gender_filter: str | None = None,
    min_year: int | None = None,
    verbose: bool = False,
) -> dict:
    """
    Extract phase distributions from all ODI JSON files in directory.

    Returns dict matching phase_distributions schema from data-model.md.
    """
    input_path = Path(input_dir)
    json_files = sorted(input_path.glob("*.json"))

    if not json_files:
        print(f"ERROR: No JSON files found in {input_path}", file=sys.stderr)
        sys.exit(1)

    # Counters
    phase_run_counts = defaultdict(lambda: defaultdict(int))  # phase -> run -> count
    phase_ball_counts = defaultdict(int)                       # phase -> total balls
    phase_wicket_counts = defaultdict(int)                     # phase -> total wickets
    wickets_down_balls = defaultdict(int)    # wickets_before -> total balls
    wickets_down_wickets = defaultdict(int)  # wickets_before -> total wickets

    total_matches = 0
    total_balls = 0
    skipped = 0

    for i, filepath in enumerate(json_files):
        if verbose and (i + 1) % 500 == 0:
            print(f"  Processing {i + 1}/{len(json_files)}...")

        try:
            match_data = parse_match(filepath, gender_filter, min_year)
        except Exception as e:
            if verbose:
                print(f"  WARNING: Failed to parse {filepath.name}: {e}")
            skipped += 1
            continue

        if match_data is None:
            skipped += 1
            continue

        total_matches += 1

        for ball in match_data["balls"]:
            phase = ball["phase"]
            runs = ball["runs"]
            is_wicket = ball["is_wicket"]
            wickets_before = ball["wickets_before"]

            phase_run_counts[phase][runs] += 1
            phase_ball_counts[phase] += 1
            total_balls += 1

            if is_wicket:
                phase_wicket_counts[phase] += 1
                wickets_down_wickets[wickets_before] += 1

            wickets_down_balls[wickets_before] += 1

    if total_matches == 0:
        print("ERROR: No matches processed", file=sys.stderr)
        sys.exit(1)

    # Build run distributions (normalized to sum to 1.0)
    run_dist = {}
    for phase in ["powerplay", "middle", "setup", "death"]:
        total = phase_ball_counts[phase]
        if total == 0:
            continue
        dist = {}
        for r in range(7):
            dist[str(r)] = round(phase_run_counts[phase][r] / total, 4)
        # Normalize to exactly 1.0
        s = sum(dist.values())
        if abs(s - 1.0) > 0.0001:
            for k in dist:
                dist[k] = round(dist[k] / s, 4)
        run_dist[phase] = dist

    # Build wicket probabilities
    wicket_prob = {}
    for phase in ["powerplay", "middle", "setup", "death"]:
        total = phase_ball_counts[phase]
        if total == 0:
            continue
        wicket_prob[phase] = round(phase_wicket_counts[phase] / total, 4)

    # Build wicket multiplier table
    # First compute base wicket rate (all balls)
    total_wickets = sum(phase_wicket_counts.values())
    base_rate = total_wickets / total_balls if total_balls > 0 else 0.05

    wicket_multiplier = {}
    for w in range(10):
        balls_at_w = wickets_down_balls.get(w, 0)
        wkts_at_w = wickets_down_wickets.get(w, 0)
        if balls_at_w > 100:  # Need sufficient data
            rate_at_w = wkts_at_w / balls_at_w
            multiplier = rate_at_w / base_rate if base_rate > 0 else 1.0
            wicket_multiplier[str(w)] = round(multiplier, 2)
        else:
            # Insufficient data — use 1.0 (no adjustment)
            wicket_multiplier[str(w)] = 1.0

    # Compute expected run rates per phase
    run_rates = {}
    for phase in ["powerplay", "middle", "setup", "death"]:
        total = phase_ball_counts[phase]
        if total == 0:
            continue
        total_runs_phase = sum(r * c for r, c in phase_run_counts[phase].items())
        run_rates[phase] = round(total_runs_phase / total * 6, 2)  # RPO

    result = {
        "format": "odi",
        "gender": gender_filter or "all",
        "total_matches": total_matches,
        "total_balls": total_balls,
        "extraction_date": datetime.now().strftime("%Y-%m-%d"),
        "source": str(input_path),
        "filters": {
            "gender": gender_filter,
            "min_year": min_year,
        },
        "run_dist": run_dist,
        "wicket_prob": wicket_prob,
        "wicket_multiplier": wicket_multiplier,
        "expected_run_rates": run_rates,
        "phase_ball_counts": dict(phase_ball_counts),
        "total_wickets": total_wickets,
        "skipped_files": skipped,
    }

    return result


def print_summary(result: dict) -> None:
    """Print a human-readable summary of extraction results."""
    print(f"\n{'='*60}")
    print(f"ODI Phase Distribution Extraction Summary")
    print(f"{'='*60}")
    print(f"Format:        {result['format']}")
    print(f"Gender:        {result['gender']}")
    print(f"Matches:       {result['total_matches']:,}")
    print(f"Total balls:   {result['total_balls']:,}")
    print(f"Total wickets: {result['total_wickets']:,}")
    print(f"Skipped files: {result['skipped_files']:,}")
    print()

    print("Phase Ball Counts:")
    for phase in ["powerplay", "middle", "setup", "death"]:
        count = result["phase_ball_counts"].get(phase, 0)
        pct = count / result["total_balls"] * 100 if result["total_balls"] > 0 else 0
        print(f"  {phase:12s}: {count:>8,} balls ({pct:.1f}%)")

    print(f"\nExpected Run Rates (RPO):")
    for phase, rpo in result.get("expected_run_rates", {}).items():
        print(f"  {phase:12s}: {rpo:.2f}")

    print(f"\nWicket Probabilities:")
    for phase, prob in result.get("wicket_prob", {}).items():
        print(f"  {phase:12s}: {prob:.4f} ({prob*100:.2f}%)")

    print(f"\nWicket Multiplier (by wickets down):")
    for w in range(10):
        mult = result["wicket_multiplier"].get(str(w), 1.0)
        print(f"  {w} wickets: {mult:.2f}")

    print(f"\nRun Distributions:")
    for phase in ["powerplay", "middle", "setup", "death"]:
        dist = result["run_dist"].get(phase, {})
        dist_str = " ".join(f"{int(k)}:{float(v):.3f}" for k, v in sorted(dist.items(), key=lambda x: int(x[0])))
        total = sum(float(v) for v in dist.values())
        print(f"  {phase:12s}: {dist_str} (sum={total:.4f})")

    # Compute average innings total from distributions
    total_runs_per_ball = 0
    total_wickets_per_ball = 0
    for phase in ["powerplay", "middle", "setup", "death"]:
        dist = result["run_dist"].get(phase, {})
        balls = result["phase_ball_counts"].get(phase, 0)
        if result["total_balls"] > 0:
            phase_weight = balls / result["total_balls"]
            avg_runs = sum(int(k) * float(v) for k, v in dist.items())
            total_runs_per_ball += avg_runs * phase_weight

    # Estimate average innings total (300 balls, assuming all are batted without all-outs)
    wicket_rate = result['total_wickets'] / result['total_balls'] if result['total_balls'] > 0 else 0.04
    expected_total = total_runs_per_ball * 300
    print(f"\nEstimated average ODI total (300 balls, no all-outs): {expected_total:.1f}")
    print(f"Overall wicket rate: {wicket_rate:.4f} ({wicket_rate*100:.2f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Extract ODI phase distributions from Cricsheet JSON files"
    )
    parser.add_argument(
        "--input-dir", required=True,
        help="Directory containing Cricsheet ODI JSON files"
    )
    parser.add_argument(
        "--output", required=True,
        help="Output JSON file path (e.g. data/phase_distributions_odi.json)"
    )
    parser.add_argument(
        "--gender", choices=["male", "female"],
        help="Filter by gender (omit for all)"
    )
    parser.add_argument(
        "--min-year", type=int,
        help="Minimum match year to include"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print progress during extraction"
    )

    args = parser.parse_args()

    print(f"Extracting ODI phase distributions from {args.input_dir}...")
    if args.gender:
        print(f"  Gender filter: {args.gender}")
    if args.min_year:
        print(f"  Min year: {args.min_year}")

    result = extract_distributions(
        input_dir=args.input_dir,
        gender_filter=args.gender,
        min_year=args.min_year,
        verbose=args.verbose,
    )

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved to {output_path}")
    print_summary(result)


if __name__ == "__main__":
    main()
