"""Run the offline, time-safe opening baseline against raw fixture data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pyarrow.dataset as ds

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.bbl_pipeline.prematch.opening_baseline import (
    REQUIRED_RAW_COLUMNS,
    assess_promotion_gate,
    apply_calibration,
    build_fixture_outcomes,
    evaluate_by_segment,
    evaluate_predictions,
    fit_platt_calibrator,
    generate_elo_opening_predictions,
    generate_opening_predictions,
    load_competition_by_match_id,
    split_predictions_chronologically,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--minimum-prior-matches", type=int, default=5)
    parser.add_argument(
        "--estimator",
        choices=("smoothed_win_rate", "elo"),
        default="smoothed_win_rate",
        help="Time-safe opening candidate to evaluate; neither option serves public rows.",
    )
    parser.add_argument("--elo-k-factor", type=float, default=64.0)
    parser.add_argument("--holdout-fraction", type=float, default=0.2)
    parser.add_argument(
        "--cricsheet-json-dir",
        type=Path,
        help="Optional exact-ID Cricsheet archive used to recover info.event.name competition metadata",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    columns = sorted(REQUIRED_RAW_COLUMNS | {"league", "gender", "venue_id"})
    table = ds.dataset(args.raw_dir, format="parquet", partitioning="hive").to_table(columns=columns)
    raw_frame = table.to_pandas()
    competition_by_match_id = {}
    if args.cricsheet_json_dir:
        competition_by_match_id = load_competition_by_match_id(
            args.cricsheet_json_dir,
            raw_frame["match_id"].astype(str).unique(),
        )
    fixtures = build_fixture_outcomes(
        raw_frame,
        competition_by_match_id=competition_by_match_id,
    )
    if args.estimator == "elo":
        predictions = generate_elo_opening_predictions(
            fixtures,
            k_factor=args.elo_k_factor,
            minimum_prior_matches=args.minimum_prior_matches,
        )
    else:
        predictions = generate_opening_predictions(
            fixtures,
            minimum_prior_matches=args.minimum_prior_matches,
        )
    eligible = evaluate_predictions(predictions)
    all_rows = evaluate_predictions(predictions, require_coverage_ready=False)
    split = split_predictions_chronologically(
        predictions,
        holdout_fraction=args.holdout_fraction,
    )
    calibrator = fit_platt_calibrator(split.calibration)
    holdout_raw = evaluate_predictions(split.holdout)
    calibrated_holdout = apply_calibration(split.holdout, calibrator)
    holdout_calibrated = evaluate_predictions(calibrated_holdout)
    holdout_segments = {
        "raw": {
            attribute: {
                key: metrics.__dict__
                for key, metrics in evaluate_by_segment(
                    split.holdout,
                    attribute=attribute,
                    minimum_samples=20 if attribute == "league" else 50,
                ).items()
            }
            for attribute in ("gender", "league")
        },
        "platt_calibrated": {
            attribute: {
                key: metrics.__dict__
                for key, metrics in evaluate_by_segment(
                    calibrated_holdout,
                    attribute=attribute,
                    minimum_samples=20 if attribute == "league" else 50,
                ).items()
            }
            for attribute in ("gender", "league")
        },
    }
    promotion = assess_promotion_gate(
        holdout_calibrated,
        {
            key: metrics
            for key, metrics in evaluate_by_segment(calibrated_holdout, attribute="gender").items()
        },
        {
            key: metrics
            for key, metrics in evaluate_by_segment(
                calibrated_holdout,
                attribute="league",
                minimum_samples=20,
            ).items()
        },
    )
    report = {
        "fixture_count": len(fixtures),
        "estimator": args.estimator,
        "elo_k_factor": args.elo_k_factor if args.estimator == "elo" else None,
        "prediction_count": len(predictions),
        "minimum_prior_matches": args.minimum_prior_matches,
        "holdout_fraction": args.holdout_fraction,
        "competition_metadata": {
            "source": str(args.cricsheet_json_dir) if args.cricsheet_json_dir else None,
            "requested_match_id_count": len({str(value) for value in raw_frame["match_id"]}),
            "named_competition_count": len(competition_by_match_id),
            "not_named_competition_count": len({str(value) for value in raw_frame["match_id"]}) - len(competition_by_match_id),
        },
        "eligible": eligible.__dict__,
        "all_rows": all_rows.__dict__,
        "segments": {
            "gender": {
                key: metrics.__dict__
                for key, metrics in evaluate_by_segment(predictions, attribute="gender").items()
            },
            "league": {
                key: metrics.__dict__
                for key, metrics in evaluate_by_segment(
                    predictions,
                    attribute="league",
                    minimum_samples=20,
                ).items()
            },
        },
        "final_temporal_holdout": {
            "start_date": split.holdout_start.isoformat(),
            "calibration_sample_count": len(split.calibration),
            "holdout_sample_count": len(split.holdout),
            "raw": holdout_raw.__dict__,
            "platt_calibrated": holdout_calibrated.__dict__,
            "platt_parameters": calibrator.__dict__,
            "segments": holdout_segments,
        },
        "promotion_decision": promotion.decision,
        "promotion_reasons": list(promotion.reasons),
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
