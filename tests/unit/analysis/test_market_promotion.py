import json
from datetime import datetime, timezone

import pandas as pd

from bbl_pipeline.analysis.market_promotion import (
    build_promotion_review,
    expected_calibration_error,
)


def _seven_match_rows(candidate=True, market=True):
    rows = []
    for match_number in range(7):
        for ball in range(30):
            actual = float((match_number + ball) % 2 == 0)
            rows.append({
                "match_id": f"m{match_number}",
                "timestamp": datetime(2026, 9, 1, tzinfo=timezone.utc),
                "innings": 2,
                "over_number": ball // 6 + 1,
                "ball_in_over": ball % 6 + 1,
                "match_phase": "middle",
                "batting_team_tier": "mid",
                "batting_team": "Dublin Guardians",
                "bowling_team": "Belfast Wolves",
                "winner": "Dublin Guardians" if actual else "Belfast Wolves",
                "features_json": '{"required_run_rate": 8.2}',
                "market_batting_team_prob": 0.7 if market else None,
                "model_final_prob": 0.5,
                "candidate_batting_team_prob": (1.0 if actual else 0.0) if candidate else None,
            })
    return pd.DataFrame(rows)


def test_ece_is_zero_for_reliably_binned_predictions():
    assert expected_calibration_error(
        [0, 0, 0, 0, 0, 0, 0, 0, 1, 1] + [1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
        [0.2] * 10 + [0.8] * 10,
    ) == 0.0


def test_candidate_must_beat_market_on_all_three_metrics():
    report = build_promotion_review(
        _seven_match_rows(),
        candidate_id="candidate-v1",
        window_start="2026-09-01T00:00:00Z",
        window_end="2026-09-08T00:00:00Z",
        generated_at="2026-09-08T00:01:00Z",
        candidate_manifest={
            "candidate_id": "candidate-v1",
            "model_artifact": {"sha256": "artifact"},
            "feature_order": ["required_run_rate"],
            "feature_order_sha256": "features",
            "source_revision": "test",
        },
    )

    assert report["decision"] == "promote_candidate"
    assert report["counts"]["completed_matches"] == 7
    assert report["counts"]["eligible_rows_candidate_market"] == 210
    assert all(value < 0 for value in report["metrics"]["candidate_minus_market_match_equal"].values())
    assert all(gate["passed"] for gate in report["gates"].values())


def test_missing_market_is_insufficient_evidence():
    report = build_promotion_review(
        _seven_match_rows(market=False),
        candidate_id="candidate-v1",
        window_start="2026-09-01T00:00:00Z",
        window_end="2026-09-08T00:00:00Z",
        generated_at="2026-09-08T00:01:00Z",
        candidate_manifest={
            "candidate_id": "candidate-v1",
            "model_artifact": {"sha256": "artifact"},
            "feature_order": ["required_run_rate"],
            "feature_order_sha256": "features",
            "source_revision": "test",
        },
    )

    assert report["decision"] == "insufficient_evidence"
    assert not report["gates"]["market_coverage"]["passed"]


def test_candidate_that_does_not_clear_market_margin_is_not_promoted():
    rows = _seven_match_rows()
    rows["candidate_batting_team_prob"] = 0.70
    report = build_promotion_review(
        rows,
        candidate_id="candidate-v1",
        window_start="2026-09-01T00:00:00Z",
        window_end="2026-09-08T00:00:00Z",
        generated_at="2026-09-08T00:01:00Z",
        candidate_manifest={
            "candidate_id": "candidate-v1",
            "model_artifact": {"sha256": "artifact"},
            "feature_order": ["required_run_rate"],
            "feature_order_sha256": "features",
            "source_revision": "test",
        },
    )

    assert report["decision"] == "retain_incumbent"
    assert not report["gates"]["candidate_beats_market"]["passed"]


def test_review_artifacts_are_repeatable_and_manifest_is_idempotent(tmp_path):
    manifest = {
        "candidate_id": "candidate-v1",
        "model_artifact": {"sha256": "artifact"},
        "feature_order": ["required_run_rate"],
        "feature_order_sha256": "features",
        "source_revision": "test",
    }
    report = build_promotion_review(
        _seven_match_rows(),
        candidate_id="candidate-v1",
        window_start="2026-09-01T00:00:00Z",
        window_end="2026-09-08T00:00:00Z",
        generated_at="2026-09-08T00:01:00Z",
        candidate_manifest=manifest,
    )
    from bbl_pipeline.analysis.market_promotion import write_promotion_review

    paths = write_promotion_review(report, tmp_path)
    write_promotion_review(report, tmp_path)

    first = json.loads(open(paths["json"], encoding="utf-8").read())
    manifest_lines = open(paths["manifest"], encoding="utf-8").read().splitlines()
    assert first["input_digest_sha256"] == report["input_digest_sha256"]
    assert len(manifest_lines) == 1
