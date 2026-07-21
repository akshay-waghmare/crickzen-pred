"""Inference-clock and feature-contract tests for Hundred v1."""

from pathlib import Path

import pandas as pd

from bbl_pipeline.features.format_config import FormatConfig
from bbl_pipeline.features.store import InMemoryFeatureStore
from bbl_pipeline.inference.realtime_mapper import RealTimeFeatureMapper


def _mapper() -> RealTimeFeatureMapper:
    store = InMemoryFeatureStore(
        Path("C:/tmp/hundred-missing-player.parquet"),
        Path("C:/tmp/hundred-missing-venue.parquet"),
    )
    return RealTimeFeatureMapper(
        feature_store=store,
        global_stats={},
        format_config=FormatConfig.hundred(),
    )


def _state(**overrides: object) -> dict:
    state = {
        "match_id": "hundred-test",
        "innings_num": 2,
        "over_number": 4,
        "ball_number": 5,
        "legal_balls_bowled": 25,
        "total_score": 35,
        "total_wickets": 1,
        "target_score": 140,
        "venue": "Test Venue",
        "batting_team": "Team A",
        "bowling_team": "Team B",
    }
    state.update(overrides)
    return state


def test_hundred_mapper_uses_legal_clock_and_five_ball_phase() -> None:
    mapper = _mapper()
    features = mapper.create_feature_dataframe(
        _state(over_number=5, ball_number=1, legal_balls_bowled=26)
    )
    row = features.iloc[0]

    assert row["balls_remaining"] == 74
    assert row["overs_remaining"] == 14.8
    assert row["is_powerplay"] == 0
    assert row["is_middle_overs"] == 1
    assert row["is_death_overs"] == 0

    match_state = mapper.map_scraped_to_match_state(
        _state(over_number=0, ball_number=6, legal_balls_bowled=26)
    )
    assert match_state.over == 5
    assert match_state.ball == 1


def test_hundred_mapper_prefers_normalized_clock_over_raw_coordinates() -> None:
    mapper = _mapper()
    features = mapper.create_feature_dataframe(
        _state(over_number=0, ball_number=6, legal_balls_bowled=25)
    )
    row = features.iloc[0]

    assert row["balls_remaining"] == 75
    assert row["overs_remaining"] == 15.0


def test_feature_validation_preserves_model_order_and_missing_defaults() -> None:
    mapper = _mapper()
    validated = mapper.validate_features(
        pd.DataFrame({"second": [2.0], "first": [1.0]}),
        ["first", "missing_probability", "second"],
    )

    assert list(validated.columns) == ["first", "missing_probability", "second"]
    assert validated.loc[0, "missing_probability"] == 0.5
