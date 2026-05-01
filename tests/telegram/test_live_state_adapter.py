"""Tests for loading Telegram signal snapshots from live predictor JSON."""

import json
from pathlib import Path

import pytest

from bbl_pipeline.telegram.live_state_adapter import (
    LiveStateError,
    build_signal_snapshot_from_json,
    load_live_signal_state,
)
from bbl_pipeline.telegram.signals import (
    PHASE_CHASE_MIDPOINT,
    PHASE_FINAL_REVIEW,
    PHASE_POWERPLAY,
    PHASE_PRE_MATCH,
    PHASE_TOSS,
)


def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_live_signal_state_uses_full_history_and_sidecar(tmp_path):
    main_path = tmp_path / "ipl_live_ml.json"
    history_path = tmp_path / "ipl_live_ml_history.json"
    sidecar_path = tmp_path / "ipl_live_ml_livematch.json"

    _write_json(
        main_path,
        {
            "timestamp": "2026-05-01T19:45:00+05:30",
            "batting_team": "RR",
            "bowling_team": "DC",
            "bat_win_prob": 0.57,
            "history": [{"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.54}],
        },
    )
    _write_json(
        history_path,
        {
            "history": [
                {"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.54},
                {"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.57},
            ]
        },
    )
    _write_json(sidecar_path, {"state": {"toss_winner": "DC", "toss_decision": "bowl"}})

    state = load_live_signal_state(main_path)

    assert len(state.main_state["history"]) == 2
    assert state.sidecar_state["state"]["toss_winner"] == "DC"


def test_build_prematch_snapshot_from_live_json(tmp_path):
    main_path = tmp_path / "ipl_live_ml.json"
    _write_json(
        main_path,
        {
            "timestamp": "2026-05-01T19:45:00+05:30",
            "batting_team": "RR",
            "bowling_team": "DC",
            "score": 0,
            "wickets": 0,
            "overs": 0.0,
            "is_second_innings": False,
            "bat_win_prob": 0.57,
            "bowl_win_prob": 0.43,
            "history": [{"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.57}],
        },
    )

    snapshot = build_signal_snapshot_from_json(
        main_path,
        PHASE_PRE_MATCH,
        dashboard_url="https://app.crickzen.com/dashboard",
    )

    assert snapshot.match == "RR vs DC"
    assert snapshot.model_favorite == "RR"
    assert snapshot.win_probability_pct == 57
    assert snapshot.dashboard_url == "https://app.crickzen.com/dashboard"


def test_build_toss_snapshot_prefills_toss_fields(tmp_path):
    main_path = tmp_path / "ipl_live_ml.json"
    sidecar_path = tmp_path / "ipl_live_ml_livematch.json"
    _write_json(
        main_path,
        {
            "timestamp": "2026-05-01T19:55:00+05:30",
            "batting_team": "RR",
            "bowling_team": "DC",
            "score": 0,
            "wickets": 0,
            "overs": 0.0,
            "is_second_innings": False,
            "bat_win_prob": 0.52,
            "bowl_win_prob": 0.48,
            "history": [{"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.52}],
        },
    )
    _write_json(sidecar_path, {"state": {"toss_winner": "DC", "toss_decision": "bowl"}})

    snapshot = build_signal_snapshot_from_json(main_path, PHASE_TOSS)

    assert snapshot.toss_winner == "DC"
    assert snapshot.toss_decision == "bowl"
    assert snapshot.pre_match_favorite == "RR"


def test_build_powerplay_snapshot_calculates_delta_and_score(tmp_path):
    main_path = tmp_path / "ipl_live_ml.json"
    _write_json(
        main_path,
        {
            "timestamp": "2026-05-01T20:30:00+05:30",
            "batting_team": "RR",
            "bowling_team": "DC",
            "score": 42,
            "wickets": 2,
            "overs": 6.0,
            "is_second_innings": False,
            "bat_win_prob": 0.63,
            "bowl_win_prob": 0.37,
            "history": [
                {"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.54},
                {"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.63},
            ],
        },
    )

    snapshot = build_signal_snapshot_from_json(main_path, PHASE_POWERPLAY)

    assert snapshot.score == "42/2"
    assert snapshot.overs == "6.0"
    assert snapshot.probability_delta_pct == 9


def test_build_chase_snapshot_calculates_pressure_fields(tmp_path):
    main_path = tmp_path / "ipl_live_ml.json"
    _write_json(
        main_path,
        {
            "timestamp": "2026-05-01T22:05:00+05:30",
            "batting_team": "DC",
            "bowling_team": "RR",
            "score": 109,
            "wickets": 4,
            "overs": 13.0,
            "target": 176,
            "total_overs": 20,
            "is_second_innings": True,
            "bat_win_prob": 0.58,
            "bowl_win_prob": 0.42,
            "history": [
                {"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.53},
                {"innings": 2, "batting_team": "DC", "bowling_team": "RR", "win_probability": 0.58},
            ],
        },
    )

    snapshot = build_signal_snapshot_from_json(main_path, PHASE_CHASE_MIDPOINT)

    assert snapshot.match == "RR vs DC"
    assert snapshot.runs_needed == 67
    assert snapshot.balls_remaining == 42
    assert snapshot.wickets_in_hand == 6


def test_build_final_review_snapshot_detects_winner(tmp_path):
    main_path = tmp_path / "ipl_live_ml.json"
    _write_json(
        main_path,
        {
            "timestamp": "2026-05-01T22:50:00+05:30",
            "batting_team": "DC",
            "bowling_team": "RR",
            "score": 176,
            "wickets": 6,
            "overs": 19.2,
            "target": 176,
            "total_overs": 20,
            "is_second_innings": True,
            "bat_win_prob": 0.99,
            "bowl_win_prob": 0.01,
            "history": [
                {"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.57},
                {"innings": 2, "batting_team": "DC", "bowling_team": "RR", "win_probability": 0.99},
            ],
        },
    )

    snapshot = build_signal_snapshot_from_json(main_path, PHASE_FINAL_REVIEW)

    assert snapshot.winner == "DC"
    assert snapshot.review is not None


def test_missing_live_json_raises(tmp_path):
    with pytest.raises(LiveStateError, match="not found"):
        load_live_signal_state(tmp_path / "missing.json")
