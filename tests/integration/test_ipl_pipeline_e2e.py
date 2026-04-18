"""
End-to-end integration tests for the IPL prediction pipeline.

Exercises FormatConfig, penalty tables, final-over lookup, team ratings,
league calibration, market blending, edge cases, and resource feature
calculation — all without requiring the actual trained model.

Run with:
    pytest tests/integration/test_ipl_pipeline_e2e.py -v
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bbl_pipeline.features.format_config import FormatConfig
from bbl_pipeline.features.calculator import ResourceFeatureCalculator
from bbl_pipeline.features.win_prob_lookup_tables import (
    get_final_over_win_prob,
    FINAL_OVER_WIN_PROB,
)
from bbl_pipeline.training.league_calibrator import LeagueCalibrator
from bbl_pipeline.inference.crex_live_predictor import blend_predictions

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
IPL_FEATURE_STORE = PROJECT_ROOT / "data" / "ipl_feature_store_v2"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def ipl_config():
    """Return an IPL FormatConfig."""
    return FormatConfig.ipl()


@pytest.fixture
def t20_config():
    """Return the default T20 FormatConfig for comparison."""
    return FormatConfig.t20()


@pytest.fixture
def ipl_calculator(ipl_config):
    """ResourceFeatureCalculator wired to IPL constants."""
    return ResourceFeatureCalculator(config=ipl_config)


@pytest.fixture
def synthetic_league_data():
    """Synthetic DataFrame + labels for LeagueCalibrator tests.

    Creates 6000 rows (1000 per innings × phase combination) so every
    phase-specific calibrator has enough samples (min_samples=500).
    """
    rng = np.random.RandomState(42)
    rows = []
    for innings in [1, 2]:
        for phase in ["powerplay", "middle", "death"]:
            n = 1000
            rows.append(
                pd.DataFrame(
                    {
                        "innings": innings,
                        "phase": phase,
                        "date": pd.Timestamp("2025-01-01"),
                    },
                    index=range(n),
                )
            )
    df = pd.concat(rows, ignore_index=True)
    raw_probs = rng.uniform(0.1, 0.9, size=len(df)).astype(np.float64)
    y_true = (raw_probs + rng.normal(0, 0.15, size=len(df)) > 0.5).astype(int)
    return df, raw_probs, y_true


# ======================================================================
# 1. FormatConfig.ipl() loads correctly
# ======================================================================
class TestFormatConfigIPL:
    """Verify IPL-specific overrides are present and sensible."""

    def test_par_score(self, ipl_config):
        assert ipl_config.par_score == pytest.approx(173.45)

    def test_league_avg_score(self, ipl_config):
        assert ipl_config.league_avg_score == pytest.approx(167.28)

    def test_bat_first_win_rate(self, ipl_config):
        assert ipl_config.bat_first_win_rate == pytest.approx(0.4581)

    def test_expected_run_rates_keys(self, ipl_config):
        expected_keys = {"powerplay", "middle", "death", "final"}
        assert set(ipl_config.expected_run_rates.keys()) == expected_keys

    def test_expected_run_rates_values(self, ipl_config):
        rr = ipl_config.expected_run_rates
        assert rr["powerplay"] == pytest.approx(7.53)
        assert rr["middle"] == pytest.approx(7.51)
        assert rr["death"] == pytest.approx(9.02)
        assert rr["final"] == pytest.approx(10.68)

    def test_first_innings_midpoint(self, ipl_config):
        assert ipl_config.first_innings_score_midpoint == pytest.approx(173.0)

    def test_final_over_lookup_present(self, ipl_config):
        assert ipl_config.final_over_lookup is not None
        assert len(ipl_config.final_over_lookup) >= 20

    def test_total_overs_unchanged(self, ipl_config):
        assert ipl_config.total_overs == 20

    def test_total_wickets_unchanged(self, ipl_config):
        assert ipl_config.total_wickets == 10


# ======================================================================
# 2. IPL penalty tables differ from T20 base
# ======================================================================
class TestIPLPenaltiesDifferFromBase:
    """IPL penalties must be league-specific, not identical to generic T20."""

    def test_chase_wicket_penalty_2d_differs(self, ipl_config, t20_config):
        ipl_2d = ipl_config.chase_wicket_penalty_2d
        t20_2d = t20_config.chase_wicket_penalty_2d
        assert ipl_2d is not None
        assert t20_2d is not None
        assert ipl_2d != t20_2d, "IPL chase penalties should differ from T20 base"

    def test_first_innings_wicket_penalty_3d_differs(self, ipl_config, t20_config):
        ipl_3d = ipl_config.first_innings_wicket_penalty_3d
        t20_3d = t20_config.first_innings_wicket_penalty_3d
        assert ipl_3d is not None
        assert t20_3d is not None
        assert ipl_3d != t20_3d, "IPL 3D penalties should differ from T20 base"

    def test_3d_penalty_has_all_phases(self, ipl_config):
        phases = {"powerplay", "middle", "death", "final"}
        assert set(ipl_config.first_innings_wicket_penalty_3d.keys()) == phases

    def test_3d_penalty_has_all_ease_levels(self, ipl_config):
        expected_ease = {"well_ahead", "ahead", "par", "behind", "well_behind"}
        for phase, ease_dict in ipl_config.first_innings_wicket_penalty_3d.items():
            assert set(ease_dict.keys()) == expected_ease, f"Missing ease levels in {phase}"

    def test_2d_penalty_has_all_difficulty_levels(self, ipl_config):
        expected_diff = {"very_easy", "easy", "comfortable", "tough", "desperate"}
        assert set(ipl_config.chase_wicket_penalty_2d.keys()) == expected_diff

    def test_penalty_values_in_range(self, ipl_config):
        for diff, wkt_map in ipl_config.chase_wicket_penalty_2d.items():
            for w, val in wkt_map.items():
                assert 0.0 <= val <= 1.0, f"Out of range: {diff}[{w}]={val}"

    def test_ten_wickets_always_zero(self, ipl_config):
        for diff, wkt_map in ipl_config.chase_wicket_penalty_2d.items():
            assert wkt_map[10] == 0.0, f"{diff} should be 0 at 10 wickets"


# ======================================================================
# 3. Final-over lookup works
# ======================================================================
class TestFinalOverLookup:
    """Verify the module-level FINAL_OVER_WIN_PROB table and helper."""

    def test_zero_runs_needed_always_wins(self):
        assert get_final_over_win_prob(0, 5) == 1.0

    def test_no_wickets_in_hand_loses(self):
        assert get_final_over_win_prob(10, 0) == 0.0

    def test_negative_runs_needed_wins(self):
        assert get_final_over_win_prob(-3, 7) == 1.0

    def test_exact_lookup(self):
        val = get_final_over_win_prob(5, 5)
        assert 0.0 <= val <= 1.0
        expected = FINAL_OVER_WIN_PROB[5][5]
        assert val == pytest.approx(expected)

    def test_high_runs_near_impossible(self):
        val = get_final_over_win_prob(100, 10)
        assert val <= 0.02

    @pytest.mark.parametrize(
        "runs,wickets",
        [(1, 1), (6, 5), (10, 8), (15, 3), (20, 10), (25, 10)],
    )
    def test_variety_of_scenarios(self, runs, wickets):
        prob = get_final_over_win_prob(runs, wickets)
        assert 0.0 <= prob <= 1.0

    def test_more_wickets_better_probability(self):
        p_low = get_final_over_win_prob(8, 2)
        p_high = get_final_over_win_prob(8, 8)
        assert p_high >= p_low, "More wickets should give >= win prob"

    def test_fewer_runs_better_probability(self):
        p_easy = get_final_over_win_prob(2, 5)
        p_hard = get_final_over_win_prob(15, 5)
        assert p_easy >= p_hard, "Fewer runs needed should give >= win prob"

    def test_ipl_config_lookup_present(self, ipl_config):
        lookup = ipl_config.final_over_lookup
        assert lookup is not None
        # 0 runs needed → 100% for everyone
        assert lookup[0][5] == 1.0
        # Sanity: high runs needed → low probability
        assert lookup[20][1] < 0.05


# ======================================================================
# 4. Team ratings are loaded (feature store parquet)
# ======================================================================
class TestTeamRatings:
    """Validate the IPL feature store team_ratings.parquet."""

    @pytest.fixture(autouse=True)
    def _skip_if_missing(self):
        path = IPL_FEATURE_STORE / "team_ratings.parquet"
        if not path.exists():
            pytest.skip(f"IPL feature store not found at {path}")

    def test_team_ratings_loads(self):
        df = pd.read_parquet(IPL_FEATURE_STORE / "team_ratings.parquet")
        assert len(df) > 0

    def test_team_count(self):
        df = pd.read_parquet(IPL_FEATURE_STORE / "team_ratings.parquet")
        assert len(df) == 15, f"Expected 15 IPL teams, got {len(df)}"

    def test_no_duplicate_teams(self):
        df = pd.read_parquet(IPL_FEATURE_STORE / "team_ratings.parquet")
        assert df["team"].is_unique, "Duplicate team names found"

    def test_required_columns(self):
        df = pd.read_parquet(IPL_FEATURE_STORE / "team_ratings.parquet")
        required = {"team", "win_rate", "matches", "bat_first_wr", "bowl_first_wr"}
        assert required.issubset(set(df.columns))

    def test_win_rates_in_range(self):
        df = pd.read_parquet(IPL_FEATURE_STORE / "team_ratings.parquet")
        assert (df["win_rate"] >= 0.0).all() and (df["win_rate"] <= 1.0).all()


# ======================================================================
# 5. Phase-wise calibration is configured
# ======================================================================
class TestLeagueCalibrator:
    """LeagueCalibrator with phase_specific=True fits 6 phase + 2 innings calibrators."""

    def test_fit_creates_phase_calibrators(self, synthetic_league_data):
        df, raw_probs, y_true = synthetic_league_data
        cal = LeagueCalibrator(
            method="temperature", innings_specific=True, phase_specific=True
        )
        cal.fit(df, raw_probs, y_true, league="ipl", min_samples=500)
        assert cal.fitted

        # 2 innings-level + 6 phase-level = 8 calibrators
        assert len(cal.calibrators) >= 8, (
            f"Expected ≥8 calibrators, got {len(cal.calibrators)}: "
            f"{sorted(cal.calibrators.keys())}"
        )

    def test_phase_calibrator_keys(self, synthetic_league_data):
        df, raw_probs, y_true = synthetic_league_data
        cal = LeagueCalibrator(
            method="temperature", innings_specific=True, phase_specific=True
        )
        cal.fit(df, raw_probs, y_true, league="ipl", min_samples=500)

        expected_phase_keys = {
            "inn1_powerplay", "inn1_middle", "inn1_death",
            "inn2_powerplay", "inn2_middle", "inn2_death",
        }
        expected_innings_keys = {"innings_1", "innings_2"}
        actual_keys = set(cal.calibrators.keys())
        assert expected_phase_keys.issubset(actual_keys)
        assert expected_innings_keys.issubset(actual_keys)

    def test_predict_returns_valid_probs(self, synthetic_league_data):
        df, raw_probs, y_true = synthetic_league_data
        cal = LeagueCalibrator(
            method="temperature", innings_specific=True, phase_specific=True
        )
        cal.fit(df, raw_probs, y_true, league="ipl", min_samples=500)

        calibrated = cal.predict(df, raw_probs)
        assert len(calibrated) == len(raw_probs)
        assert np.all((calibrated >= 0.0) & (calibrated <= 1.0))

    def test_platt_method_also_works(self, synthetic_league_data):
        df, raw_probs, y_true = synthetic_league_data
        cal = LeagueCalibrator(
            method="platt", innings_specific=True, phase_specific=True
        )
        cal.fit(df, raw_probs, y_true, league="ipl", min_samples=500)
        assert cal.fitted
        calibrated = cal.predict(df, raw_probs)
        assert np.all(np.isfinite(calibrated))


# ======================================================================
# 6. Market ensemble blending
# ======================================================================
class TestBlendPredictions:
    """blend_predictions returns correct results for ensemble and fallback."""

    def test_ensemble_mode(self):
        prob, src = blend_predictions(
            model_prob=0.70, market_prob=0.60, market_age_seconds=10.0, alpha=0.6
        )
        assert src == "ensemble"
        expected = 0.6 * 0.70 + 0.4 * 0.60  # 0.66
        assert prob == pytest.approx(expected, abs=1e-3)

    def test_pure_model_alpha_one(self):
        prob, src = blend_predictions(
            model_prob=0.80, market_prob=0.50, market_age_seconds=5.0, alpha=1.0
        )
        assert src == "ensemble"
        assert prob == pytest.approx(0.80, abs=1e-3)

    def test_pure_market_alpha_zero(self):
        prob, src = blend_predictions(
            model_prob=0.80, market_prob=0.50, market_age_seconds=5.0, alpha=0.0
        )
        assert src == "ensemble"
        assert prob == pytest.approx(0.50, abs=1e-3)

    def test_fallback_when_market_none(self):
        prob, src = blend_predictions(
            model_prob=0.65, market_prob=None, market_age_seconds=None, alpha=0.7
        )
        assert src == "model_only"
        assert prob == pytest.approx(0.65, abs=1e-3)

    def test_fallback_when_market_stale(self):
        prob, src = blend_predictions(
            model_prob=0.65, market_prob=0.60, market_age_seconds=120.0, alpha=0.7
        )
        assert src == "model_only"

    def test_fallback_when_market_nan(self):
        prob, src = blend_predictions(
            model_prob=0.65, market_prob=float("nan"), market_age_seconds=5.0, alpha=0.7
        )
        assert src == "model_only"

    def test_fallback_when_model_nan(self):
        prob, src = blend_predictions(
            model_prob=float("nan"), market_prob=0.6, market_age_seconds=5.0, alpha=0.7
        )
        assert src == "model_only"
        assert prob == pytest.approx(0.5, abs=1e-3)

    def test_result_clamped(self):
        prob, _ = blend_predictions(
            model_prob=0.001, market_prob=0.001, market_age_seconds=1.0, alpha=0.5
        )
        assert prob >= 0.001
        assert prob <= 0.999


# ======================================================================
# 7. Edge cases don't crash
# ======================================================================
class TestEdgeCases:
    """Unusual but valid inputs must not raise exceptions."""

    def test_ten_wickets_lost_first_innings(self, ipl_calculator):
        prob = ipl_calculator.calculate_resource_win_probability(
            innings=1,
            expected_final_score=80.0,
            target_runs=0,
            resource_pct=0.0,
            current_run_rate=4.0,
            required_run_rate=0.0,
            current_score=80,
            balls_remaining=0,
            wickets_lost=10,
        )
        assert 0.0 <= prob <= 1.0

    def test_ten_wickets_lost_second_innings(self, ipl_calculator):
        prob = ipl_calculator.calculate_resource_win_probability(
            innings=2,
            expected_final_score=120.0,
            target_runs=180,
            resource_pct=0.0,
            current_run_rate=6.0,
            required_run_rate=36.0,
            current_score=120,
            balls_remaining=0,
            wickets_lost=10,
        )
        assert 0.0 <= prob <= 1.0

    def test_unknown_venue_avg(self, ipl_calculator):
        """venue_avg_score=None should not crash."""
        prob = ipl_calculator.calculate_resource_win_probability(
            innings=1,
            expected_final_score=170.0,
            target_runs=0,
            resource_pct=50.0,
            current_run_rate=8.5,
            required_run_rate=0.0,
            current_score=85,
            balls_remaining=60,
            wickets_lost=2,
            venue_avg_score=None,
        )
        assert 0.0 <= prob <= 1.0

    def test_zero_balls_remaining(self, ipl_calculator):
        prob = ipl_calculator.calculate_resource_win_probability(
            innings=2,
            expected_final_score=165.0,
            target_runs=170,
            resource_pct=0.0,
            current_run_rate=8.25,
            required_run_rate=99.0,
            current_score=165,
            balls_remaining=0,
            wickets_lost=5,
        )
        assert 0.0 <= prob <= 1.0

    def test_missing_market_data_blend(self):
        prob, src = blend_predictions(
            model_prob=0.55, market_prob=None, market_age_seconds=None, alpha=0.7
        )
        assert src == "model_only"
        assert 0.0 <= prob <= 1.0

    def test_blend_none_model_prob(self):
        prob, src = blend_predictions(
            model_prob=None, market_prob=0.6, market_age_seconds=5.0, alpha=0.7
        )
        assert src == "model_only"
        assert 0.0 <= prob <= 1.0

    def test_final_over_negative_runs(self):
        assert get_final_over_win_prob(-5, 8) == 1.0

    def test_final_over_zero_wickets(self):
        assert get_final_over_win_prob(10, 0) == 0.0

    def test_dynamic_penalty_zero_rrr(self, ipl_calculator):
        penalty = ipl_calculator.get_dynamic_wicket_penalty(
            wickets_lost=3, current_run_rate=8.0, required_run_rate=0.0
        )
        assert 0.0 <= penalty <= 1.0

    def test_dynamic_penalty_zero_crr(self, ipl_calculator):
        penalty = ipl_calculator.get_dynamic_wicket_penalty(
            wickets_lost=5, current_run_rate=0.0, required_run_rate=9.0
        )
        assert 0.0 <= penalty <= 1.0


# ======================================================================
# 8. ResourceFeatureCalculator with IPL config
# ======================================================================
class TestResourceCalculatorIPL:
    """Calculator should use IPL-specific constants when configured."""

    def test_par_score_is_ipl(self, ipl_calculator):
        assert ipl_calculator.PAR_SCORE_T20 == pytest.approx(173.45)

    def test_league_avg_is_ipl(self, ipl_calculator):
        assert ipl_calculator.LEAGUE_AVG_SCORE == pytest.approx(167.28)

    def test_bat_first_win_rate_is_ipl(self, ipl_calculator):
        assert ipl_calculator.HISTORICAL_BAT_FIRST_WIN_RATE == pytest.approx(0.4581)

    def test_first_innings_midpoint_is_ipl(self, ipl_calculator):
        assert ipl_calculator.FIRST_INNINGS_SCORE_MIDPOINT == pytest.approx(173.0)

    def test_3d_penalties_populated(self, ipl_calculator):
        assert len(ipl_calculator.FIRST_INNINGS_WICKET_PENALTY_3D) == 4

    def test_resource_win_prob_first_innings_good(self, ipl_calculator):
        """Strong first-innings position → high win prob.

        IPL bat-first win rate is only 0.4581, so we need a clearly
        dominant projected score (well above the 173 midpoint) to
        cross 50%.
        """
        prob = ipl_calculator.calculate_resource_win_probability(
            innings=1,
            expected_final_score=210.0,
            target_runs=0,
            resource_pct=35.0,
            current_run_rate=10.5,
            required_run_rate=0.0,
            current_score=145,
            balls_remaining=30,
            wickets_lost=1,
        )
        assert prob > 0.5, f"Strong first-innings position should have >50% win prob, got {prob}"

    def test_resource_win_prob_chase_easy(self, ipl_calculator):
        """Comfortable chase → high win prob for batting team."""
        prob = ipl_calculator.calculate_resource_win_probability(
            innings=2,
            expected_final_score=175.0,
            target_runs=160,
            resource_pct=40.0,
            current_run_rate=9.0,
            required_run_rate=6.0,
            current_score=100,
            balls_remaining=60,
            wickets_lost=2,
        )
        assert prob > 0.5, f"Easy chase should have >50% win prob, got {prob}"

    def test_resource_win_prob_chase_desperate(self, ipl_calculator):
        """Hopeless chase → low win prob for batting team."""
        prob = ipl_calculator.calculate_resource_win_probability(
            innings=2,
            expected_final_score=130.0,
            target_runs=200,
            resource_pct=10.0,
            current_run_rate=5.0,
            required_run_rate=20.0,
            current_score=100,
            balls_remaining=18,
            wickets_lost=7,
        )
        assert prob < 0.3, f"Desperate chase should have <30% win prob, got {prob}"

    def test_dynamic_penalty_easy_chase(self, ipl_calculator):
        """In an easy chase, wickets barely matter."""
        penalty = ipl_calculator.get_dynamic_wicket_penalty(
            wickets_lost=3, current_run_rate=12.0, required_run_rate=6.0
        )
        assert penalty >= 0.85, f"Easy chase with 3 wkts should have high penalty, got {penalty}"

    def test_dynamic_penalty_desperate_chase(self, ipl_calculator):
        """In a desperate chase, wickets hurt badly."""
        penalty = ipl_calculator.get_dynamic_wicket_penalty(
            wickets_lost=7, current_run_rate=4.0, required_run_rate=14.0
        )
        assert penalty < 0.3, f"Desperate chase with 7 wkts should have low penalty, got {penalty}"
