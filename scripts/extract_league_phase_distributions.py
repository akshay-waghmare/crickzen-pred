"""
Extract Phase Distributions for Any T20 League
===============================================

Generates phase_distributions_{league}.json for MC simulation engine.
Required format: PP (overs 1-6), MID (7-15), DEATH (16-20).

Usage:
    python scripts/extract_league_phase_distributions.py --league ntb
    python scripts/extract_league_phase_distributions.py --league ipl
"""
import argparse
import json
import pandas as pd
from pathlib import Path


def get_phase(over: int) -> str:
    if over <= 5:
        return "powerplay"
    elif over <= 14:
        return "middle"
    else:
        return "death"


def main():
    parser = argparse.ArgumentParser(description="Extract phase distributions for any T20 league")
    parser.add_argument("--league", required=True, help="League slug (e.g., ntb, ipl, psl)")
    parser.add_argument("--raw-dir", default=None,
                        help="Raw parquet directory (default: data/<league>_raw/matches)")
    parser.add_argument("--output", default=None,
                        help="Output JSON path (default: data/phase_distributions_<league>.json)")
    args = parser.parse_args()

    league = args.league
    raw_dir = args.raw_dir or f"data/{league}_raw/matches"
    output = args.output or f"data/phase_distributions_{league}.json"

    raw_path = Path(raw_dir)
    if not raw_path.exists():
        print(f"ERROR: Raw data not found at {raw_dir}")
        return

    df = pd.read_parquet(raw_path)
    df = df[df["is_super_over"] == False].copy()
    df["is_wicket"] = df["wicket_type"].notna() & (df["wicket_type"] != "")
    df["phase"] = df["over"].apply(get_phase)

    run_dist = {}
    wicket_prob = {}
    boundary_pct = {}

    for phase in ["powerplay", "middle", "death"]:
        pdf = df[df["phase"] == phase]
        runs = pdf["runs_total"].value_counts(normalize=True).sort_index()
        dist = {str(r): float(runs.get(r, 0.0)) for r in range(8)}
        run_dist[phase] = dist
        wicket_prob[phase] = float(pdf["is_wicket"].mean())
        boundary_pct[phase] = float(pdf["runs_total"].isin([4, 6]).mean())

    result = {
        "total_balls": int(len(df)),
        "run_dist": run_dist,
        "wicket_prob": wicket_prob,
        "boundary_pct": boundary_pct,
        "wicket_multiplier": {"powerplay": 1.0, "middle": 1.0, "death": 1.0},
    }

    with open(output, "w") as f:
        json.dump(result, f, indent=2)

    pp_count = len(df[df["phase"] == "powerplay"])
    mid_count = len(df[df["phase"] == "middle"])
    death_count = len(df[df["phase"] == "death"])
    print(f"Extracted distributions from {len(df):,} {league.upper()} balls")
    print(f"Phases: PP={pp_count:,}, MID={mid_count:,}, DEATH={death_count:,}")
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
