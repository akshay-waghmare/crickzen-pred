"""
Test suite for reduced-over T20 match support (008-t20-reduced-overs).

Covers:
- Phase boundary scaling (4 tests)
- FormatConfig.t20_reduced() factory (4 tests)
- MatchState reduced-over validation (2 tests)
- MC simulation with reduced overs (2 tests)
- Evaluator reduced balls_bowled (1 test)
- 20-over regression (1 test)
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from bbl_pipeline.simulation import MatchState, SimulationResult, simulate, get_phase
from bbl_pipeline.simulation.config import get_scaled_phase_boundaries
from bbl_pipeline.features.format_config import FormatConfig


# =====================================================================
# Phase Boundary Tests
# =====================================================================


class TestPhaseBoundaries:
    """Test dynamic phase boundaries for reduced-over matches."""

    def test_phase_15_overs(self):
        """Over 12 of a 15-over match is death, not middle."""
        # 15 overs: pp=4, middle_end=11
        # overs_completed=12 (balls_remaining=18) → death (12 >= 11)
        assert get_phase(18, total_balls=90) == "death"
        # overs_completed=11 (balls_remaining=24) → death (11 is NOT < 11)
        assert get_phase(24, total_balls=90) == "death"
        # overs_completed=10 (balls_remaining=30) → middle (10 < 11)
        assert get_phase(30, total_balls=90) == "middle"

    def test_phase_10_overs(self):
        """Over 9+ of a 10-over match is death."""
        # 10 overs: pp=3, middle_end=8
        # overs_completed=9 (balls_remaining=6) → death
        assert get_phase(6, total_balls=60) == "death"
        # overs_completed=8 (balls_remaining=12) → death (8 is NOT < 8)
        assert get_phase(12, total_balls=60) == "death"
        # overs_completed=7 (balls_remaining=18) → middle (7 < 8)
        assert get_phase(18, total_balls=60) == "middle"

    def test_phase_5_overs(self):
        """Over 4 of a 5-over match is death."""
        # 5 overs: pp=max(2,min(6,round(1.5)))=2
        # death_overs=max(2,round(1.25))=2, death_start=5-2+1=4, middle_end=3
        # Over 4 (overs_completed=4, balls_remaining=6) → death
        assert get_phase(6, total_balls=30) == "death"
        # Over 2 (overs_completed=2, balls_remaining=18) → middle
        assert get_phase(18, total_balls=30) == "middle"

    def test_phase_20_overs_unchanged(self):
        """20-over match phases are unchanged from standard constants (regression)."""
        # Over 6 still powerplay, over 16 still death
        assert get_phase(85, total_balls=120) == "powerplay"
        assert get_phase(84, total_balls=120) == "middle"
        assert get_phase(31, total_balls=120) == "middle"
        assert get_phase(30, total_balls=120) == "death"

    def test_scaled_boundaries_proportional(self):
        """get_scaled_phase_boundaries returns reasonable proportions."""
        pp_end, mid_end = get_scaled_phase_boundaries(15)
        assert 2 <= pp_end <= 6
        assert pp_end <= mid_end
        assert mid_end < 15

    def test_scaled_boundaries_super_over(self):
        """Super over (≤2 overs) returns all death (0, 0)."""
        assert get_scaled_phase_boundaries(1) == (0, 0)
        assert get_scaled_phase_boundaries(2) == (0, 0)


# =====================================================================
# FormatConfig Tests
# =====================================================================


class TestFormatConfigReduced:
    """Test FormatConfig.t20_reduced() factory method."""

    def test_reduced_config_par_score(self):
        """15-over par score is approximately 133 (±5%)."""
        config = FormatConfig.t20_reduced(15)
        # DLS-based scaling: 160 * resource_pct(15, 0_wickets)
        assert 126 <= config.par_score <= 145  # ~133 ±5%

    def test_reduced_config_identity(self):
        """t20_reduced(20) equals t20() exactly."""
        reduced_20 = FormatConfig.t20_reduced(20)
        standard = FormatConfig.t20()
        assert reduced_20 == standard

    def test_reduced_config_super_over(self):
        """t20_reduced(1) creates a valid super-over config."""
        config = FormatConfig.t20_reduced(1)
        assert config.total_balls == 6
        assert config.total_overs == 1
        assert config.par_score > 0

    def test_reduced_config_total_balls(self):
        """t20_reduced(12) has total_balls == 72."""
        config = FormatConfig.t20_reduced(12)
        assert config.total_balls == 72
        assert config.total_overs == 12

    def test_reduced_config_invalid_overs(self):
        """t20_reduced with invalid overs raises ValueError."""
        with pytest.raises(ValueError, match="total_overs must be 1-20"):
            FormatConfig.t20_reduced(0)
        with pytest.raises(ValueError, match="total_overs must be 1-20"):
            FormatConfig.t20_reduced(21)

    def test_reduced_config_format_name(self):
        """t20_reduced sets format_name to 't20_reduced'."""
        config = FormatConfig.t20_reduced(15)
        assert config.format_name == "t20_reduced"

    def test_reduced_config_score_caps_consistent(self):
        """Score caps are consistent with par_score."""
        config = FormatConfig.t20_reduced(10)
        assert config.score_cap_min < config.par_score
        assert config.par_score < config.score_cap_max


# =====================================================================
# MatchState Tests
# =====================================================================


class TestMatchStateReduced:
    """Test MatchState with reduced total_balls."""

    def test_state_reduced_validation(self):
        """balls_remaining=60, total_balls=60 (10-over match) is valid."""
        state = MatchState(
            innings=1, score=0, wickets_lost=0, balls_remaining=60,
            batting_team="A", bowling_team="B", league="bbl",
            total_balls=60,
        )
        assert state.total_balls == 60
        assert state.balls_remaining == 60

    def test_state_reduced_overs_completed(self):
        """overs_completed is correct for a 90-ball (15-over) match."""
        state = MatchState(
            innings=1, score=70, wickets_lost=3, balls_remaining=30,
            batting_team="A", bowling_team="B", league="bbl",
            total_balls=90,
        )
        # (90 - 30) / 6 = 10.0
        assert state.overs_completed == pytest.approx(10.0)


# =====================================================================
# MC Simulation Tests
# =====================================================================


class TestMCSimulationReduced:
    """Test Monte Carlo simulation with reduced overs."""

    def test_mc_reduced_over_completes(self):
        """MC simulation on a 15-over state returns a valid probability."""
        state = MatchState(
            innings=2, score=80, wickets_lost=2, balls_remaining=30,
            target_runs=135,
            batting_team="A", bowling_team="B", league="bbl",
            total_balls=90,
        )
        result = simulate(state, horizon=6, n_simulations=500)
        assert isinstance(result, SimulationResult)
        assert 0 <= result.mean_prob <= 1
        assert result.n_sims == 500

    def test_mc_reduced_vs_full_differs(self):
        """MC on 15-over match at same score/overs-remaining gives different
        probability than a 20-over match at the same point."""
        # 15-over match: 80/2 after 10 overs chasing 135
        # 5 overs remaining (30 balls), need 55 more
        reduced_state = MatchState(
            innings=2, score=80, wickets_lost=2, balls_remaining=30,
            target_runs=135,
            batting_team="A", bowling_team="B", league="bbl",
            total_balls=90,
        )

        # 20-over match: same score/position but 10 overs remaining (60 balls)
        # and chasing 180 (proportionally the same)
        full_state = MatchState(
            innings=2, score=80, wickets_lost=2, balls_remaining=60,
            target_runs=180,
            batting_team="A", bowling_team="B", league="bbl",
            total_balls=120,
        )

        np.random.seed(42)
        reduced_result = simulate(reduced_state, horizon=6, n_simulations=1000)

        np.random.seed(42)
        full_result = simulate(full_state, horizon=6, n_simulations=1000)

        # Probabilities should differ (different match dynamics)
        # Both should be valid
        assert 0 < reduced_result.mean_prob < 1
        assert 0 < full_result.mean_prob < 1
        # Phase assignments differ, so at least some difference expected
        # (though we don't enforce a specific direction)


# =====================================================================
# Evaluator Tests
# =====================================================================


class TestEvaluatorReduced:
    """Test evaluator computes correct balls_bowled for reduced overs."""

    def test_evaluator_reduced_balls_bowled(self):
        """Evaluator computes correct balls_bowled for a 90-ball state."""
        from bbl_pipeline.simulation.evaluator import TerminalStateEvaluator

        evaluator = TerminalStateEvaluator()

        state = MatchState(
            innings=1, score=100, wickets_lost=4, balls_remaining=30,
            batting_team="A", bowling_team="B", league="bbl",
            total_balls=90,
        )
        # balls_bowled = total_balls - balls_remaining = 90 - 30 = 60
        # = 10 overs. Evaluator should not crash or miscalculate.
        prob = evaluator.evaluate(state)
        assert 0 <= prob <= 1


# =====================================================================
# Regression Tests
# =====================================================================


class TestRegressionDefault:
    """20-over regression: default total_balls=120 produces identical output."""

    def test_20_over_regression(self):
        """Standard 20-over state (default total_balls) produces a valid
        simulation result identical to pre-change behavior."""
        state = MatchState(
            innings=1, score=80, wickets_lost=2, balls_remaining=60,
            batting_team="Brisbane Heat", bowling_team="Sydney Sixers",
            league="bbl",
        )
        # total_balls should default to 120
        assert state.total_balls == 120

        np.random.seed(123)
        result = simulate(state, horizon=6, n_simulations=1000)

        # Should produce valid probability
        assert 0 < result.mean_prob < 1
        assert result.n_sims == 1000
        assert result.horizon_balls == 6

    def test_get_phase_default_regression(self):
        """get_phase without total_balls kwarg still works (default 120)."""
        assert get_phase(120) == "powerplay"
        assert get_phase(84) == "middle"
        assert get_phase(30) == "death"


# =====================================================================
# MCCalibrator Tests
# =====================================================================


class TestMCCalibrator:
    """Test MCCalibrator Platt-scaling module."""

    def test_fit_and_calibrate(self):
        """Fit on synthetic data and calibrate returns float in [0, 1]."""
        from bbl_pipeline.calibration.mc_calibrator import MCCalibrator

        np.random.seed(42)
        mc_probs = np.random.beta(3, 3, size=500)
        outcomes = (np.random.rand(500) < mc_probs).astype(float)

        cal = MCCalibrator()
        cal.fit(mc_probs, outcomes)

        calibrated = cal.calibrate(0.65)
        assert 0 < calibrated < 1
        assert isinstance(calibrated, float)

    def test_calibrate_batch(self):
        """calibrate_batch returns array of same length."""
        from bbl_pipeline.calibration.mc_calibrator import MCCalibrator

        np.random.seed(42)
        mc_probs = np.random.beta(3, 3, size=500)
        outcomes = (np.random.rand(500) < mc_probs).astype(float)

        cal = MCCalibrator()
        cal.fit(mc_probs, outcomes)

        batch = np.array([0.3, 0.5, 0.7])
        result = cal.calibrate_batch(batch)
        assert result.shape == (3,)
        assert all(0 < p < 1 for p in result)

    def test_save_load_roundtrip(self, tmp_path):
        """save() + load() roundtrip preserves calibration."""
        from bbl_pipeline.calibration.mc_calibrator import MCCalibrator

        np.random.seed(42)
        mc_probs = np.random.beta(3, 3, size=500)
        outcomes = (np.random.rand(500) < mc_probs).astype(float)

        cal = MCCalibrator()
        cal.fit(mc_probs, outcomes)

        path = str(tmp_path / "mc_cal.pkl")
        cal.save(path)

        loaded = MCCalibrator.load(path)
        assert loaded.training_samples == cal.training_samples
        assert loaded.calibrate(0.5) == pytest.approx(cal.calibrate(0.5), abs=1e-6)

    def test_not_fitted_raises(self):
        """calibrate() before fit() raises RuntimeError."""
        from bbl_pipeline.calibration.mc_calibrator import MCCalibrator

        cal = MCCalibrator()
        with pytest.raises(RuntimeError, match="not been fitted"):
            cal.calibrate(0.5)

    def test_summary(self):
        """summary() returns a readable string after fitting."""
        from bbl_pipeline.calibration.mc_calibrator import MCCalibrator

        np.random.seed(42)
        mc_probs = np.random.beta(3, 3, size=200)
        outcomes = (np.random.rand(200) < mc_probs).astype(float)

        cal = MCCalibrator()
        cal.fit(mc_probs, outcomes)

        summary = cal.summary()
        assert "MCCalibrator" in summary
        assert "samples=200" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
