"""Build the versioned, as-of-date artifact used by the opening serializer.

The artifact is generated from resolved historical fixtures only. It must be
rebuilt as new results arrive; the dashboard rejects it when it is too old or
when an upcoming fixture is not strictly after its recorded as-of date.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

import pyarrow.dataset as ds

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.bbl_pipeline.prematch.opening_baseline import (
    REQUIRED_RAW_COLUMNS,
    build_elo_runtime_state,
    build_fixture_outcomes,
    fit_platt_calibrator,
    generate_elo_opening_predictions,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--as-of-date", type=_parse_date)
    parser.add_argument("--minimum-prior-matches", type=int, default=5)
    parser.add_argument("--elo-k-factor", type=float, default=64.0)
    parser.add_argument("--rating-scale", type=float, default=400.0)
    parser.add_argument("--initial-rating", type=float, default=1500.0)
    args = parser.parse_args()

    if args.minimum_prior_matches < 0:
        raise ValueError("minimum-prior-matches must be non-negative")
    columns = sorted(REQUIRED_RAW_COLUMNS | {"league", "gender", "venue_id"})
    table = ds.dataset(args.raw_dir, format="parquet", partitioning="hive").to_table(columns=columns)
    fixtures = build_fixture_outcomes(table.to_pandas())
    if not fixtures:
        raise ValueError("No resolved fixtures were available for the opening artifact")
    as_of_date = args.as_of_date or fixtures[-1].match_date
    predictions = generate_elo_opening_predictions(
        (fixture for fixture in fixtures if fixture.match_date <= as_of_date),
        k_factor=args.elo_k_factor,
        rating_scale=args.rating_scale,
        initial_rating=args.initial_rating,
        minimum_prior_matches=args.minimum_prior_matches,
    )
    calibrator = fit_platt_calibrator(predictions)
    state = build_elo_runtime_state(
        fixtures,
        as_of_date=as_of_date,
        k_factor=args.elo_k_factor,
        rating_scale=args.rating_scale,
        initial_rating=args.initial_rating,
    )
    teams = {
        name: {
            "rating": state.ratings[name],
            "matches": state.matches.get(name, 0),
            "wins": state.wins.get(name, 0),
        }
        for name in sorted(state.ratings, key=str.casefold)
    }
    artifact = {
        "schema_version": 1,
        "estimator": "elo",
        "format": "T20",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": state.as_of_date.isoformat(),
        "minimum_prior_matches": args.minimum_prior_matches,
        "k_factor": state.k_factor,
        "rating_scale": state.rating_scale,
        "initial_rating": state.initial_rating,
        "calibrator": {
            "intercept": calibrator.intercept,
            "slope": calibrator.slope,
            "training_sample_count": calibrator.training_sample_count,
        },
        "teams": teams,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "as_of_date": artifact["as_of_date"],
        "team_count": len(teams),
        "calibration_rows": calibrator.training_sample_count,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
