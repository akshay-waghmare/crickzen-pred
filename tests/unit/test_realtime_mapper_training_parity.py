import math
import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from bbl_pipeline.features.format_config import FormatConfig
from bbl_pipeline.features.store import InMemoryFeatureStore
from bbl_pipeline.inference.realtime_mapper import RealTimeFeatureMapper


class DummyFeatureStore:
    def get_player_stats(self, _name):
        return {}

    def get_venue_stats(self, _venue):
        return {
            "venue_avg_score": 176.0,
            "venue_avg_wickets": 11.7777777778,
            "venue_bat_first_win_rate": 0.48,
        }

    def get_team_stats(self, team):
        stats = {
            "Sunrisers Hyderabad": {
                "win_rate": 0.457565,
                "bat_first_wr": 0.446667,
                "bowl_first_wr": 0.471074,
            },
            "Mumbai Indians": {
                "win_rate": 0.546763,
                "bat_first_wr": 0.531469,
                "bowl_first_wr": 0.562963,
            },
        }
        return stats.get(team, {})


def make_mapper():
    return RealTimeFeatureMapper(
        DummyFeatureStore(),
        global_stats={},
        format_config=FormatConfig.t20(),
    )


def test_ipl_v6_innings2_features_match_training_formulas():
    mapper = make_mapper()

    features = mapper.create_feature_dataframe(
        {
            "innings_num": 2,
            "over_number": 2,
            "ball_number": 1,
            "total_score": 31,
            "total_wickets": 0,
            "current_batsman": "Abhishek Sharma",
            "non_striker": "Travis Head",
            "current_bowler": "T Boult",
            "batting_team": "Sunrisers Hyderabad",
            "bowling_team": "Mumbai Indians",
            "venue": "Wankhede Stadium, Mumbai",
            "target_score": 244,
            "runs_needed": 213,
            "first_innings_score": 243,
            "inn1_wickets_lost": 5,
            "inn1_pp_runs": 78,
            "inn1_death_rr": 12.4,
        }
    ).iloc[0]

    balls_remaining = 120 - (2 * 6 + 1)
    resources_remaining = (balls_remaining / 120) * 1.0
    resources_used = 1.0 - resources_remaining

    assert features["projected_score"] == 0.0
    assert features["projected_vs_venue_avg"] == 0.0
    assert math.isclose(features["resources_remaining"], resources_remaining)
    assert math.isclose(features["score_vs_par"], 31 - (243 * resources_used))
    assert math.isclose(
        features["chase_difficulty"],
        213 / (resources_remaining * 243 + 1),
    )
    assert math.isclose(features["crr_times_res"], features["current_run_rate"] * resources_remaining)
    assert math.isclose(features["team_strength_diff"], 0.457565 - 0.546763)
    assert math.isclose(features["batting_team_situation_wr"], 0.471074)
    assert math.isclose(features["bowling_team_situation_wr"], 0.531469)


def test_boundary_pct_last_18_uses_training_formula():
    mapper = make_mapper()
    mapper.ball_history = [
        {
            "innings_num": 2,
            "over_number": idx // 6,
            "ball_number": idx % 6,
            "runs_scored": runs,
            "is_boundary": int(runs in (4, 6)),
            "is_wicket": 0,
        }
        for idx, runs in enumerate([1, 2, 0, 4, 1, 0, 6, 1, 1, 4, 0, 2, 1, 1, 4, 0, 1, 2])
    ]

    stats = mapper._calculate_rolling_stats(current_innings=2, total_balls_in_match=18)
    runs = [1, 2, 0, 4, 1, 0, 6, 1, 1, 4, 0, 2, 1, 1, 4, 0, 1, 2]
    boundaries_last_18 = sum(1 for run in runs if run in (4, 6))

    assert math.isclose(stats["boundary_pct_last_18"], boundaries_last_18 / len(runs))


def test_set_batter_exposure_infers_missing_partner_from_partnership_counter():
    mapper = make_mapper()
    mapper._current_innings = 2
    mapper._balls_since_wicket = 30

    features = mapper.create_feature_dataframe(
        {
            "innings_num": 2,
            "over_number": 12,
            "ball_number": 0,
            "total_score": 120,
            "total_wickets": 2,
            "batting_team": "Sunrisers Hyderabad",
            "bowling_team": "Mumbai Indians",
            "venue": "Wankhede Stadium, Mumbai",
            "target_score": 181,
            "runs_needed": 61,
            "batsman1_balls": 0,
            "batsman2_balls": 4,
        }
    ).iloc[0]

    assert features["set_batter_exposure"] == 27.0


def test_season_overrides_disabled_for_training_parity():
    assert InMemoryFeatureStore.USE_SEASON_OVERRIDES is False


def test_venue_situation_overrides_disabled_for_training_parity():
    assert InMemoryFeatureStore.USE_VENUE_SITUATION_OVERRIDES is False
