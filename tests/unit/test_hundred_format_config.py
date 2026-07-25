"""Contract tests for the five-ball Hundred format configuration."""

from bbl_pipeline.features.format_config import FormatConfig
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState


def test_hundred_structural_contract() -> None:
    config = FormatConfig.hundred()

    assert config.format_name == "hundred"
    assert config.total_balls == 100
    assert config.total_legal_balls == 100
    assert config.balls_per_over == 5
    assert config.scoring_set_size == 5
    assert config.end_change_interval == 10
    assert config.powerplay_balls == 25
    assert config.max_balls_per_bowler == 20
    assert config.phase_thresholds == {
        "powerplay": 5,
        "middle": 12,
        "death": 17,
        "final": 20,
    }


def test_hundred_league_resolution_does_not_change_t20() -> None:
    hundred = FormatConfig.from_league("hundred_all")
    t20 = FormatConfig.from_league("t20_all")

    assert hundred.format_name == "hundred"
    assert hundred.total_balls == 100
    assert t20.format_name == "t20"
    assert t20.total_balls == 120
    assert t20.balls_per_over == 6


def test_hundred_gender_default_is_overridable() -> None:
    assert FormatConfig.hundred("male").gender == "male"
    assert FormatConfig.hundred("female").gender == "female"
    assert FormatConfig.from_league("hundred_female").gender == "female"


def test_hundred_match_state_and_terminal_clamp_use_five_ball_sets() -> None:
    state = MatchState(
        match_id="hundred-clock",
        venue="Test",
        batting_team="A",
        bowling_team="B",
        innings=2,
        over=19,
        ball=5,
        current_score=139,
        wickets_lost=3,
        batsman_1="A Batter",
        batsman_2="B Batter",
        bowler="C Bowler",
        target_runs=140,
        total_overs=20,
        balls_per_over=5,
    )

    assert state.get_balls_bowled() == 100
    assert state.get_balls_remaining() == 0
    assert state.get_overs_bowled() == 20.0
    assert not state.is_powerplay()
    assert state.is_death_overs()

    predictor = object.__new__(Predictor)
    predictor.format_config = FormatConfig.hundred()
    clamp = predictor._second_innings_terminal_clamp(state)

    assert clamp is not None
    assert clamp["reason"] == "no_balls_remaining"
    assert clamp["balls_remaining"] == 0
