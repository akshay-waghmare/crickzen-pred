"""
Integration tests for ODI MC-only predictor.

Tests the full MC simulation pipeline for ODI matches without requiring
a trained ML model or feature store. Validates that simulate() and
simulate_vectorized() work end-to-end with 300-ball ODI states.

Covers: T029, SC-001, SC-005
"""

import pytest
import numpy as np

from bbl_pipeline.simulation.state import MatchState
from bbl_pipeline.simulation.engine import simulate, simulate_vectorized, simulate_one_over
from bbl_pipeline.simulation.sampler import NextBallSampler
from bbl_pipeline.simulation.evaluator import TerminalStateEvaluator
from bbl_pipeline.features.format_config import FormatConfig


class TestODIMCSimulationEndToEnd:
    """End-to-end ODI MC simulation through the engine module."""

    def test_simulate_odi_first_innings(self):
        """simulate() produces valid result for ODI first innings."""
        state = MatchState(
            innings=1, score=150, wickets_lost=3, balls_remaining=120,
            total_balls=300, league="odi", batting_team="Australia", bowling_team="India",
        )
        result = simulate(state, horizon=1, n_simulations=500)
        assert result is not None
        assert hasattr(result, 'mean_prob')
        assert 0.0 <= result.mean_prob <= 1.0
        assert result.n_sims == 500

    def test_simulate_odi_second_innings_chase(self):
        """simulate() produces valid result for ODI chase scenario."""
        state = MatchState(
            innings=2, score=100, wickets_lost=2, balls_remaining=180,
            total_balls=300, league="odi", batting_team="England", bowling_team="New Zealand",
            target_runs=280,
        )
        result = simulate(state, horizon=1, n_simulations=500)
        assert result is not None
        assert 0.0 <= result.mean_prob <= 1.0

    def test_simulate_vectorized_odi(self):
        """simulate_vectorized() works with ODI state."""
        state = MatchState(
            innings=1, score=200, wickets_lost=5, balls_remaining=60,
            total_balls=300, league="odi", batting_team="Team A", bowling_team="Team B",
        )
        result = simulate_vectorized(state, horizon=6, n_simulations=1000)
        assert result is not None
        assert hasattr(result, 'mean_prob')
        assert 0.0 <= result.mean_prob <= 1.0

    def test_simulate_one_over_odi(self):
        """simulate_one_over() works with ODI state."""
        state = MatchState(
            innings=1, score=100, wickets_lost=2, balls_remaining=180,
            total_balls=300, league="odi", batting_team="Team A", bowling_team="Team B",
        )
        result = simulate_one_over(state, n_simulations=500)
        assert result is not None
        assert 0.0 <= result.mean_prob <= 1.0


class TestODIFormatConfigIntegration:
    """Test that FormatConfig.odi() integrates correctly with MC pipeline."""

    def test_format_config_odi_matches_simulation(self):
        """FormatConfig.odi() total_balls matches what simulation expects."""
        config = FormatConfig.odi()
        assert config.total_balls == 300
        assert config.total_overs == 50
        assert config.par_score == 257.7
        assert len(config.phase_names) == 4

    def test_format_config_from_league_odi(self):
        """FormatConfig.from_league('odi') returns ODI config."""
        config = FormatConfig.from_league("odi")
        assert config.total_balls == 300
        assert config.format_name == "odi"

    def test_evaluator_uses_odi_config_for_300_balls(self):
        """TerminalStateEvaluator correctly uses FormatConfig.odi() for 300-ball innings."""
        evaluator = TerminalStateEvaluator(model_dir="models/nonexistent")
        state = MatchState(
            innings=1, score=260, wickets_lost=7, balls_remaining=0,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        prob = evaluator.evaluate(state, apply_temp=False)
        # 260/7 is slightly above par (257.7) — should be moderate
        assert 0.3 < prob < 0.7


class TestODIMCProbabilityRealism:
    """Test that MC probabilities are realistic for known ODI scenarios."""

    def test_first_innings_above_par_favorable(self):
        """Score above par at end of innings gives probability > 0.5."""
        state = MatchState(
            innings=1, score=300, wickets_lost=8, balls_remaining=0,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        result = simulate(state, horizon=1, n_simulations=500)
        # 300 is above par (257.7) — should be favorable for batting team
        assert result.mean_prob > 0.5

    def test_second_innings_easy_chase(self):
        """Easy chase (need 50 from 120 balls, 8 wickets left) → high probability."""
        state = MatchState(
            innings=2, score=200, wickets_lost=2, balls_remaining=120,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
            target_runs=250,
        )
        result = simulate(state, horizon=1, n_simulations=1000)
        # Need 50 from 120 balls with 8 wickets — very easy
        assert result.mean_prob > 0.7

    def test_second_innings_impossible_chase(self):
        """Impossible chase (need 200 from 12 balls) → very low probability."""
        state = MatchState(
            innings=2, score=100, wickets_lost=5, balls_remaining=12,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
            target_runs=300,
        )
        result = simulate(state, horizon=1, n_simulations=1000)
        # Need 200 from 12 balls — impossible
        assert result.mean_prob < 0.05

    def test_second_innings_target_already_chased(self):
        """Target already chased → probability = 1.0."""
        state = MatchState(
            innings=2, score=280, wickets_lost=4, balls_remaining=30,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
            target_runs=275,
        )
        result = simulate(state, horizon=1, n_simulations=100)
        # raw_mean=1.0 but legacy calibrator may shift slightly
        assert result.mean_prob > 0.99

    def test_second_innings_all_out(self):
        """All out without reaching target → probability = 0.0."""
        state = MatchState(
            innings=2, score=200, wickets_lost=10, balls_remaining=60,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
            target_runs=280,
        )
        result = simulate(state, horizon=1, n_simulations=100)
        # raw_mean=0.0 but legacy calibrator may shift slightly
        assert result.mean_prob < 0.01


class TestODISamplerLeagueDetection:
    """Test that league-based sampler detection works for ODI."""

    def test_sampler_with_odi_league(self):
        """NextBallSampler loads ODI distributions when league='odi'."""
        sampler = NextBallSampler(seed=42, league="odi")
        assert "setup" in sampler._run_values
        assert len(sampler._run_values) == 4

    def test_sampler_with_odis_league(self):
        """NextBallSampler loads ODI distributions when league='odis'."""
        sampler = NextBallSampler(seed=42, league="odis")
        assert "setup" in sampler._run_values

    def test_sampler_no_league_uses_t20(self):
        """NextBallSampler without league uses T20 (3 phases)."""
        sampler = NextBallSampler(seed=42)
        assert "setup" not in sampler._run_values
        assert len(sampler._run_values) == 3

    def test_sampler_bbl_league_uses_t20(self):
        """NextBallSampler with T20 league has 3 phases."""
        sampler = NextBallSampler(seed=42, league="bbl")
        assert len(sampler._run_values) == 3
