from datetime import datetime, timezone
import json

from app.opening_predictions import OpeningArtifactStore


NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def _artifact(generated_at: str | None = None):
    return {
        "schema_version": 1,
        "estimator": "elo",
        "format": "T20",
        "generated_at": generated_at or NOW.isoformat(),
        "as_of_date": "2026-08-01",
        "minimum_prior_matches": 5,
        "rating_scale": 400.0,
        "calibrator": {"intercept": 0.0, "slope": 1.0},
        "teams": {
            "Argentina": {"rating": 1515.8, "matches": 44, "wins": 19},
            "Canada": {"rating": 1602.5, "matches": 94, "wins": 50},
        },
    }


def _candidate(**overrides):
    candidate = {
        "url": "https://crex.com/cricket-live-score/arg-w-vs-can-w-4th-t20-match-updates-12YR",
        "is_live": False,
        "match_format": "T20",
        "scheduled_start_time": int(datetime(2026, 8, 2, 12, tzinfo=timezone.utc).timestamp() * 1000),
        "team1_name": "Argentina Women",
        "team2_name": "Canada Women",
    }
    candidate.update(overrides)
    return candidate


def test_opening_store_scores_exact_upcoming_candidate_with_canonical_team_resolution(tmp_path):
    path = tmp_path / "opening.json"
    path.write_text(json.dumps(_artifact()), encoding="utf-8")

    decision = OpeningArtifactStore(path).evaluate(_candidate(), now=NOW)

    assert decision.status == "ready"
    assert decision.first_team == "Argentina"
    assert decision.second_team == "Canada"
    assert decision.first_team_probability_pct is not None
    assert decision.first_team_probability_pct < 50


def test_opening_store_refuses_live_stale_or_ambiguous_candidates(tmp_path):
    path = tmp_path / "opening.json"
    path.write_text(json.dumps(_artifact("2026-07-30T00:00:00+00:00")), encoding="utf-8")
    store = OpeningArtifactStore(path, ttl_seconds=3600)

    assert store.evaluate(_candidate(is_live=True), now=NOW).reason == "candidate_is_not_upcoming"
    assert store.evaluate(_candidate(), now=NOW).reason == "opening_artifact_stale"

    path.write_text(json.dumps(_artifact()), encoding="utf-8")
    store = OpeningArtifactStore(path)
    assert store.evaluate(_candidate(team1_name="Unknown Women"), now=NOW).reason == "team_not_covered_by_artifact"
    assert store.evaluate(_candidate(scheduled_start_time=int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp() * 1000)), now=NOW).reason == "fixture_not_after_artifact_as_of"
    assert store.evaluate(_candidate(scheduled_start_time=int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)), now=NOW).reason == "opening_history_too_old_for_fixture"
