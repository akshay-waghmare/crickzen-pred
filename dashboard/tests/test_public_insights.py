"""Tests for public insight and serializer helpers."""

from __future__ import annotations

import json

from app.public import (
    PUBLIC_FORBIDDEN_KEYS,
    build_public_insight,
    public_payload,
    public_probability_pct,
    public_swings,
    serialize_prediction,
    slugify,
)


def test_slugify_stable_ascii_slug():
    assert slugify("DC vs RCB - IPL 2026 Win Probability!") == "dc-vs-rcb-ipl-2026-win-probability"


def test_probability_rounds_to_whole_percent():
    assert public_probability_pct({"blend": {"blended_prob": 0.574}}) == 57
    assert public_probability_pct({"league_calibrated_prob": 0.576}) == 58
    assert public_probability_pct({}) is None


def test_insight_probability_swing():
    state = {"batting_team": "RCB", "bowling_team": "DC"}
    swings = public_swings({
        "chart_history": [
            {"overs": 10.0, "score": 90, "wickets": 2, "bat_prob": 0.48},
            {"overs": 12.0, "score": 112, "wickets": 2, "bat_prob": 0.58},
        ]
    })

    assert build_public_insight(state, swings) == "RCB win probability up 10% across the recent overs."


def test_insight_chase_pressure():
    insight = build_public_insight({
        "target": 181,
        "projection": {
            "target": 181,
            "required_run_rate": 12.2,
            "current_run_rate": 8.7,
        },
    }, [])

    assert "under pressure" in insight


def test_insight_first_innings_par():
    insight = build_public_insight({
        "batting_team": "DC",
        "projection": {"score_vs_par": 11.8},
    }, [])

    assert insight == "DC are tracking 12 runs above par."


def test_insight_missing_state_fallback():
    assert build_public_insight(None, []) == "Model probability will appear once live ball data is available."


def test_public_serializer_redacts_premium_keys():
    payload = public_payload(serialize_prediction(
        prediction_id="abc123",
        match_url="https://crex.com/cricket-live-score/dc-vs-rcb-39th-match-indian-premier-league-2026-match-updates-118K",
        league="IPL",
        status="running",
        state={
            "score": 100,
            "wickets": 2,
            "overs": 11.4,
            "batting_team": "DC",
            "bowling_team": "RCB",
            "blend": {"blended_prob": 0.612, "ml_prob": 0.59, "mc_prob": 0.63},
            "monte_carlo": {"available": True},
            "odm": {"status": "ready"},
            "features": {"projected_score": 184},
            "history": [{"overs": 11.4, "score": 100, "wickets": 2, "bat_prob": 0.61}],
            "commentary": [{"text": "premium"}],
        },
        detail=True,
    ))
    text = json.dumps(payload)

    for key in PUBLIC_FORBIDDEN_KEYS:
        assert f'"{key}"' not in text
    assert payload["win_probability_pct"] == 61


def test_public_history_preserves_innings_and_summary_derives_a_chase():
    payload = public_payload(serialize_prediction(
        prediction_id="tan-ugn",
        match_url="https://crex.com/cricket-live-score/tan-w-vs-ugn-w-match-updates-131D",
        league="T20",
        status="running",
        state={
            "is_second_innings": True,
            "history": [
                {"innings": 1, "overs": 20.0, "score": 132, "wickets": 6, "bat_prob": 0.54, "expected_score": 132},
                {"innings": 2, "overs": 1.2, "score": 8, "wickets": 0, "bat_prob": 0.78, "expected_score": 160},
            ],
        },
    ))

    assert payload["innings"] == 2
    assert [point["innings"] for point in payload["prediction_history"]] == [1, 2]
