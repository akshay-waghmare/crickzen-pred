#!/usr/bin/env python3
"""Derive empirical final-over win probability lookup from IPL Cricsheet JSON files.

Parses IPL match data to build a (runs_needed × wickets_in_hand) lookup table
for chasing team win probability at the start of the final over (over 20).

Usage:
    python scripts/derive_final_over_lookup.py
"""

import json
import glob
import os
import sys
from collections import defaultdict
from pathlib import Path

INPUT_DIR = "ipl_male_json"
OUTPUT_PATH = "data/ipl_final_over_lookup.json"

MAX_RUNS = 25
MAX_WICKETS = 10


def parse_match(filepath: str) -> dict | None:
    """Parse a single Cricsheet JSON and extract final-over state.

    Returns dict with runs_needed, wickets_in_hand, chasing_won
    or None if the match doesn't have a valid 2nd innings final over.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    info = data.get("info", {})
    innings = data.get("innings", [])

    # Need at least 2 innings
    if len(innings) < 2:
        return None

    outcome = info.get("outcome", {})
    winner = outcome.get("winner")
    # Skip no-result / tied matches without a winner
    if not winner:
        return None

    # --- 1st innings: compute target ---
    inn1 = innings[0]
    inn1_team = inn1.get("team", "")
    inn1_total = 0
    for over_obj in inn1.get("overs", []):
        for delivery in over_obj.get("deliveries", []):
            inn1_total += delivery.get("runs", {}).get("total", 0)
    target = inn1_total + 1

    # --- 2nd innings: find state at start of over 19 (0-indexed) ---
    inn2 = innings[1]
    inn2_team = inn2.get("team", "")
    overs = inn2.get("overs", [])

    # Check that over 19 exists
    final_over = None
    for over_obj in overs:
        if over_obj.get("over") == 19:
            final_over = over_obj
            break

    if final_over is None:
        return None

    # Compute score and wickets at START of over 19 (sum overs 0-18)
    current_score = 0
    wickets_lost = 0
    for over_obj in overs:
        if over_obj.get("over") >= 19:
            break
        for delivery in over_obj.get("deliveries", []):
            current_score += delivery.get("runs", {}).get("total", 0)
            if delivery.get("wickets"):
                wickets_lost += len(delivery["wickets"])

    runs_needed = target - current_score
    wickets_in_hand = 10 - wickets_lost
    chasing_won = winner == inn2_team

    return {
        "runs_needed": runs_needed,
        "wickets_in_hand": wickets_in_hand,
        "chasing_won": chasing_won,
        "match_file": os.path.basename(filepath),
        "inn2_team": inn2_team,
        "target": target,
        "score_at_19": current_score,
    }


def build_empirical_table(records: list[dict]) -> dict:
    """Group records by (runs_needed, wickets_in_hand), compute win rate."""
    groups = defaultdict(lambda: {"wins": 0, "total": 0})
    for rec in records:
        key = (rec["runs_needed"], rec["wickets_in_hand"])
        groups[key]["total"] += 1
        if rec["chasing_won"]:
            groups[key]["wins"] += 1

    empirical = {}
    for (rn, wih), stats in groups.items():
        empirical[(rn, wih)] = stats["wins"] / stats["total"]
    return empirical


def interpolate_and_fill(empirical: dict) -> list[list[float]]:
    """Build full lookup table with monotonic interpolation and boundary conditions.

    Returns table[runs_needed][wickets_in_hand] for runs 0..MAX_RUNS, wickets 0..MAX_WICKETS.
    """
    table = [[None for _ in range(MAX_WICKETS + 1)] for _ in range(MAX_RUNS + 1)]

    # Seed with empirical values
    for (rn, wih), prob in empirical.items():
        if 0 <= rn <= MAX_RUNS and 0 <= wih <= MAX_WICKETS:
            table[rn][wih] = prob

    # --- Enforce boundary conditions ---
    # runs_needed <= 0 → 1.0 (already won/tied in chaser's favor)
    for wih in range(MAX_WICKETS + 1):
        table[0][wih] = 1.0

    # wickets_in_hand = 0 → 0.0 (all out)
    for rn in range(MAX_RUNS + 1):
        table[rn][0] = 0.0

    # Build a base curve for interpolation using a simple logistic-like model
    # Anchored to empirical data where available, then fill gaps
    _fill_base_estimates(table)

    # Enforce monotonicity
    _enforce_monotonicity(table)

    # Final boundary overrides (after monotonicity)
    for rn in range(MAX_RUNS + 1):
        table[rn][0] = 0.0
    for wih in range(MAX_WICKETS + 1):
        table[0][wih] = 1.0

    # runs > 20 with wickets <= 2 → 0.0
    for rn in range(21, MAX_RUNS + 1):
        for wih in range(0, 3):
            table[rn][wih] = 0.0

    # runs > 25 → 0.01
    # (already handled since MAX_RUNS=25, but set row 25 conservatively for high runs)

    # Round to 4 decimal places
    for rn in range(MAX_RUNS + 1):
        for wih in range(MAX_WICKETS + 1):
            table[rn][wih] = round(table[rn][wih], 4)

    return table


def _fill_base_estimates(table: list[list[float | None]]) -> None:
    """Fill None cells with reasonable estimates based on a simple model.

    Uses the idea that ~7 runs/over is typical (par), with wickets
    providing insurance. Logistic curve centered around par.
    """
    import math

    for rn in range(MAX_RUNS + 1):
        for wih in range(MAX_WICKETS + 1):
            if table[rn][wih] is not None:
                continue

            if rn == 0:
                table[rn][wih] = 1.0
                continue
            if wih == 0:
                table[rn][wih] = 0.0
                continue

            # Typical final over: ~8 runs is par for a full-strength team
            # Wickets in hand affect both ability and risk
            par_runs = 6.0 + 0.4 * wih  # More wickets → slightly higher par
            # Steepness of the curve
            k = 0.35 + 0.02 * wih

            # Logistic: P(win) = 1 / (1 + exp(k * (runs_needed - par)))
            z = k * (rn - par_runs)
            prob = 1.0 / (1.0 + math.exp(z))

            # Scale down for very low wickets
            if wih <= 2:
                prob *= (wih / 3.0)

            # Clamp to reasonable range
            prob = max(0.0, min(1.0, prob))
            table[rn][wih] = prob


def _enforce_monotonicity(table: list[list[float | None]]) -> None:
    """Enforce monotonic constraints:
    - P decreases as runs_needed increases (fixed wickets)
    - P increases as wickets_in_hand increases (fixed runs)
    """
    # Pass 1: For each wickets column, ensure P decreases with runs_needed
    for wih in range(MAX_WICKETS + 1):
        for rn in range(1, MAX_RUNS + 1):
            if table[rn][wih] is not None and table[rn - 1][wih] is not None:
                if table[rn][wih] > table[rn - 1][wih]:
                    table[rn][wih] = table[rn - 1][wih]

    # Pass 2: For each runs row, ensure P increases with wickets_in_hand
    for rn in range(MAX_RUNS + 1):
        for wih in range(1, MAX_WICKETS + 1):
            if table[rn][wih] is not None and table[rn][wih - 1] is not None:
                if table[rn][wih] < table[rn][wih - 1]:
                    table[rn][wih] = table[rn][wih - 1]

    # Pass 3: Repeat decreasing-with-runs after wicket adjustment
    for wih in range(MAX_WICKETS + 1):
        for rn in range(1, MAX_RUNS + 1):
            if table[rn][wih] is not None and table[rn - 1][wih] is not None:
                if table[rn][wih] > table[rn - 1][wih]:
                    table[rn][wih] = table[rn - 1][wih]


def format_summary(records: list[dict], table: list[list[float]], n_files: int, n_errors: int) -> str:
    """Format summary statistics."""
    lines = [
        "=" * 60,
        "IPL Final Over Win Probability Lookup",
        "=" * 60,
        f"Files processed:      {n_files}",
        f"Parse errors:         {n_errors}",
        f"Final overs found:    {len(records)}",
        f"Table dimensions:     {MAX_RUNS + 1} runs × {MAX_WICKETS + 1} wickets",
        "",
        "--- Empirical Data Points ---",
    ]

    for rec in records:
        won_str = "WON" if rec["chasing_won"] else "LOST"
        lines.append(
            f"  {rec['match_file']}: {rec['inn2_team']} needed {rec['runs_needed']} "
            f"with {rec['wickets_in_hand']} wkts → {won_str}"
        )

    # Table coverage stats
    non_boundary = 0
    filled = 0
    for rn in range(1, MAX_RUNS + 1):
        for wih in range(1, MAX_WICKETS + 1):
            non_boundary += 1
            if table[rn][wih] is not None and table[rn][wih] > 0:
                filled += 1
    lines.append(f"\nTable coverage (non-boundary): {filled}/{non_boundary} cells filled")

    # Sample of the table
    lines.append("\n--- Lookup Table Sample (runs_needed × wickets_in_hand) ---")
    header = "runs\\wkts " + " ".join(f"{w:>5}" for w in range(MAX_WICKETS + 1))
    lines.append(header)
    for rn in [0, 1, 2, 4, 6, 8, 10, 12, 15, 18, 20, 25]:
        if rn <= MAX_RUNS:
            row = f"  {rn:>4}    " + " ".join(f"{table[rn][w]:>5.2f}" for w in range(MAX_WICKETS + 1))
            lines.append(row)

    return "\n".join(lines)


def main():
    project_root = Path(__file__).resolve().parent.parent
    input_dir = project_root / INPUT_DIR
    output_path = project_root / OUTPUT_PATH

    if not input_dir.exists():
        print(f"ERROR: Input directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    json_files = sorted(glob.glob(str(input_dir / "*.json")))
    if not json_files:
        print(f"ERROR: No JSON files found in {input_dir}", file=sys.stderr)
        sys.exit(1)

    records = []
    n_errors = 0
    for filepath in json_files:
        try:
            result = parse_match(filepath)
            if result is not None:
                records.append(result)
        except Exception as e:
            n_errors += 1
            print(f"WARNING: Error parsing {os.path.basename(filepath)}: {e}", file=sys.stderr)

    print(f"Parsed {len(json_files)} files, found {len(records)} final-over records, {n_errors} errors")

    # Build empirical and interpolated table
    empirical = build_empirical_table(records)
    if empirical:
        print(f"Empirical data points: {len(empirical)}")
        for (rn, wih), prob in sorted(empirical.items()):
            print(f"  runs={rn}, wickets={wih} → {prob:.3f}")

    table = interpolate_and_fill(empirical)

    # Print summary
    print(format_summary(records, table, len(json_files), n_errors))

    # Build output structure
    output = {
        "description": "IPL final over (over 20) win probability lookup for chasing team",
        "dimensions": {
            "rows": "runs_needed (0-25)",
            "cols": "wickets_in_hand (0-10)",
        },
        "source": f"{len(json_files)} IPL Cricsheet JSON files",
        "empirical_records": len(records),
        "table": table,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nOutput written to: {output_path}")
    print(f"File size: {output_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
