"""
Unit tests for Monte Carlo simulation engine.

Tests cover:
- MatchState validation and operations
- NextBallSampler distributions
- SimulationResult statistics
- Temperature calibration
- Betting decision logic
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from bbl_pipeline.simulation import (
    MatchState,
    SimulationResult,
    NextBallSampler,
    simulate,
    simulate_single_ball,
    simulate_one_over,
    evaluate_bet,
    BettingThresholds,
    BetDecision,
    apply_temperature,
    apply_temperature_vectorized,
    get_phase,
    calculate_kelly_stake,
    odds_to_implied_prob,
    RUN_DIST,
    WICKET_PROB,
)


class TestMatchState:
    """Tests for MatchState dataclass."""
    
    def test_valid_state_creation(self):
        """Test valid state creation."""
        state = MatchState(
            innings=1,
            score=50,
            wickets_lost=2,
            balls_remaining=60,
            batting_team="Melbourne Stars",
            bowling_team="Sydney Sixers",
            league="bbl",
        )
        assert state.innings == 1
        assert state.score == 50
        assert state.wickets_lost == 2
        assert state.balls_remaining == 60
        assert state.league == "bbl"
    
    def test_innings_2_with_target(self):
        """Test innings 2 requires target."""
        state = MatchState(
            innings=2,
            score=100,
            wickets_lost=3,
            balls_remaining=48,
            target_runs=170,
            batting_team="Melbourne Stars",
            bowling_team="Sydney Sixers",
            league="bbl",
        )
        assert state.target_runs == 170
    
    def test_invalid_innings(self):
        """Test invalid innings raises error."""
        with pytest.raises(ValueError, match="innings must be 1 or 2"):
            MatchState(
                innings=3,
                score=50,
                wickets_lost=2,
                balls_remaining=60,
                batting_team="A",
                bowling_team="B",
                league="bbl",
            )
    
    def test_negative_score(self):
        """Test negative score raises error."""
        with pytest.raises(ValueError, match="score must be >= 0"):
            MatchState(
                innings=1,
                score=-10,
                wickets_lost=0,
                balls_remaining=120,
                batting_team="A",
                bowling_team="B",
                league="bbl",
            )
    
    def test_wickets_exceeds_10(self):
        """Test wickets > 10 raises error."""
        with pytest.raises(ValueError, match="wickets_lost must be 0-10"):
            MatchState(
                innings=1,
                score=100,
                wickets_lost=11,
                balls_remaining=0,
                batting_team="A",
                bowling_team="B",
                league="bbl",
            )
    
    def test_is_over_all_out(self):
        """Test is_over when all out."""
        state = MatchState(
            innings=1,
            score=100,
            wickets_lost=10,
            balls_remaining=30,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        assert state.is_over
    
    def test_is_over_overs_complete(self):
        """Test is_over when overs complete."""
        state = MatchState(
            innings=1,
            score=180,
            wickets_lost=4,
            balls_remaining=0,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        assert state.is_over
    
    def test_is_over_target_chased(self):
        """Test is_over when target chased."""
        state = MatchState(
            innings=2,
            score=170,
            wickets_lost=5,
            balls_remaining=12,
            target_runs=170,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        assert state.is_over
    
    def test_not_over(self):
        """Test is_over is False during game."""
        state = MatchState(
            innings=1,
            score=100,
            wickets_lost=4,
            balls_remaining=30,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        assert not state.is_over
    
    def test_apply_outcome_runs(self):
        """Test applying runs outcome."""
        state = MatchState(
            innings=1,
            score=100,
            wickets_lost=2,
            balls_remaining=60,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        new_state = state.apply_outcome(runs=4, is_wicket=False)
        
        assert new_state.score == 104
        assert new_state.wickets_lost == 2
        assert new_state.balls_remaining == 59
    
    def test_apply_outcome_wicket(self):
        """Test applying wicket outcome."""
        state = MatchState(
            innings=1,
            score=100,
            wickets_lost=2,
            balls_remaining=60,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        new_state = state.apply_outcome(runs=0, is_wicket=True)
        
        assert new_state.score == 100
        assert new_state.wickets_lost == 3
        assert new_state.balls_remaining == 59
    
    def test_copy(self):
        """Test state copy."""
        state = MatchState(
            innings=1,
            score=100,
            wickets_lost=2,
            balls_remaining=60,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        copy = state.copy()
        
        assert copy == state
        assert copy is not state


class TestNextBallSampler:
    """Tests for NextBallSampler."""
    
    def test_sample_returns_tuple(self):
        """Test sample returns (runs, wicket) tuple."""
        sampler = NextBallSampler()
        state = MatchState(
            innings=1,
            score=50,
            wickets_lost=2,
            balls_remaining=60,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        runs, is_wicket = sampler.sample(state)
        
        assert isinstance(runs, (int, np.integer))
        assert isinstance(is_wicket, (bool, np.bool_))
        assert 0 <= runs <= 6
    
    def test_sample_batch_shape(self):
        """Test sample_batch returns correct shape."""
        sampler = NextBallSampler()
        state = MatchState(
            innings=1,
            score=50,
            wickets_lost=2,
            balls_remaining=60,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        runs, is_wicket = sampler.sample_batch(state, n_sims=100)
        
        assert runs.shape == (100,)
        assert is_wicket.shape == (100,)
    
    def test_sample_vectorized_shape(self):
        """Test sample_vectorized returns correct shape."""
        sampler = NextBallSampler()
        phases = np.array(['powerplay', 'middle', 'death', 'death', 'middle'])
        wickets = np.array([0, 2, 4, 6, 8])
        runs, is_wicket = sampler.sample_vectorized(phases, wickets, n=5)
        
        assert runs.shape == (5,)
        assert is_wicket.shape == (5,)
    
    def test_run_distribution_mean(self):
        """Test run distribution has expected mean."""
        sampler = NextBallSampler()
        state = MatchState(
            innings=1,
            score=50,
            wickets_lost=2,
            balls_remaining=100,  # Powerplay
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        runs, _ = sampler.sample_batch(state, n_sims=10000)
        
        # Expected mean from powerplay distribution
        expected_mean = sum(r * p for r, p in RUN_DIST['powerplay'].items())
        actual_mean = runs.mean()
        
        # Should be within 0.15 of expected
        assert abs(actual_mean - expected_mean) < 0.15
    
    def test_wicket_rate_by_phase(self):
        """Test wicket rates differ by phase."""
        sampler = NextBallSampler()
        n = 50000
        
        # Powerplay state (balls_remaining=100 → powerplay)
        pp_state = MatchState(
            innings=1, score=20, wickets_lost=0, balls_remaining=100,
            batting_team="A", bowling_team="B", league="bbl",
        )
        _, wickets_pp = sampler.sample_batch(pp_state, n_sims=n)
        rate_pp = wickets_pp.mean()
        
        # Death state (balls_remaining=10)
        death_state = MatchState(
            innings=1, score=150, wickets_lost=0, balls_remaining=10,
            batting_team="A", bowling_team="B", league="bbl",
        )
        _, wickets_death = sampler.sample_batch(death_state, n_sims=n)
        rate_death = wickets_death.mean()
        
        # Death should have higher wicket rate
        assert rate_death > rate_pp
        
        # Rates should be close to expected (with multiplier for 0 wickets = 1.0)
        assert abs(rate_pp - WICKET_PROB['powerplay']) < 0.01
        assert abs(rate_death - WICKET_PROB['death']) < 0.015


class TestSimulationResult:
    """Tests for SimulationResult."""
    
    def test_from_probs(self):
        """Test from_probs factory method."""
        probs = np.array([0.4, 0.5, 0.6, 0.7, 0.8])
        result = SimulationResult.from_probs(
            probs=probs,
            horizon_balls=1,
            time_taken_ms=10.0,
            league="bbl",
        )
        
        assert result.mean_prob == pytest.approx(0.6, abs=0.01)
        assert result.p5 == pytest.approx(0.4, abs=0.05)
        assert result.p95 == pytest.approx(0.8, abs=0.05)
    
    def test_from_probs_ci(self):
        """Test confidence interval calculation."""
        np.random.seed(42)
        probs = np.random.beta(5, 5, size=1000)
        result = SimulationResult.from_probs(
            probs=probs,
            horizon_balls=6,
            time_taken_ms=50.0,
            league="bbl",
        )
        
        # CI bounds should be reasonable
        assert result.p5 <= result.mean_prob <= result.p95
        
        # CI width should be reasonable
        ci_width = result.p95 - result.p5
        assert ci_width < 0.5


class TestTemperatureCalibration:
    """Tests for temperature calibration."""
    
    def test_apply_temperature_identity(self):
        """Test temperature=1.0 gives identity."""
        prob = 0.6
        result = apply_temperature(prob, 1.0)
        assert result == pytest.approx(prob, abs=1e-6)
    
    def test_apply_temperature_sharpen(self):
        """Test temperature<1.0 sharpens predictions."""
        prob = 0.6
        result = apply_temperature(prob, 0.8)
        
        # Probability > 0.5 should increase with T < 1
        assert result > prob
        # Verify the specific value from spec
        assert result == pytest.approx(0.624, abs=0.001)
    
    def test_apply_temperature_soften(self):
        """Test temperature>1.0 softens predictions."""
        prob = 0.7
        result = apply_temperature(prob, 1.2)
        
        # Probability > 0.5 should decrease toward 0.5 with T > 1
        assert prob > result > 0.5
    
    def test_apply_temperature_symmetric(self):
        """Test temperature is symmetric around 0.5."""
        prob_high = 0.7
        prob_low = 0.3
        
        result_high = apply_temperature(prob_high, 0.8)
        result_low = apply_temperature(prob_low, 0.8)
        
        # Results should be symmetric around 0.5
        assert result_high == pytest.approx(1 - result_low, abs=0.001)
    
    def test_apply_temperature_vectorized(self):
        """Test vectorized temperature application."""
        probs = np.array([0.3, 0.5, 0.7])
        results = apply_temperature_vectorized(probs, 0.8)
        
        # Check individual values match scalar version
        for i, p in enumerate(probs):
            expected = apply_temperature(p, 0.8)
            assert results[i] == pytest.approx(expected, abs=1e-6)


class TestBetting:
    """Tests for betting decision support."""
    
    def test_odds_to_implied_prob(self):
        """Test odds conversion."""
        assert odds_to_implied_prob(2.0) == pytest.approx(0.5)
        assert odds_to_implied_prob(1.5) == pytest.approx(0.6667, abs=0.001)
        assert odds_to_implied_prob(3.0) == pytest.approx(0.3333, abs=0.001)
    
    def test_odds_to_implied_prob_invalid(self):
        """Test invalid odds raises error."""
        with pytest.raises(ValueError):
            odds_to_implied_prob(1.0)
        with pytest.raises(ValueError):
            odds_to_implied_prob(0.5)
    
    def test_kelly_stake_positive_edge(self):
        """Test Kelly stake with positive edge."""
        stake = calculate_kelly_stake(
            model_prob=0.6,
            odds=2.0,  # Implied 50%
            fraction=0.25,
        )
        
        # Kelly = (1 * 0.6 - 0.4) / 1 = 0.2
        # Quarter Kelly = 0.05
        assert stake == pytest.approx(0.05, abs=0.01)
    
    def test_kelly_stake_no_edge(self):
        """Test Kelly stake with no edge."""
        stake = calculate_kelly_stake(
            model_prob=0.5,
            odds=2.0,  # Implied 50%
            fraction=0.25,
        )
        
        assert stake == pytest.approx(0.0, abs=0.01)
    
    def test_kelly_stake_negative_edge(self):
        """Test Kelly stake with negative edge."""
        stake = calculate_kelly_stake(
            model_prob=0.4,
            odds=2.0,  # Implied 50%
            fraction=0.25,
        )
        
        assert stake == 0.0
    
    def test_evaluate_bet_bet(self):
        """Test evaluate_bet returns BET for large edge."""
        result = SimulationResult(
            mean_prob=0.65,
            std_prob=0.03,
            p5=0.60,
            p95=0.70,
            n_sims=1000,
            horizon_balls=1,
            time_taken_ms=50.0,
            league="bbl",
        )
        
        # Market implies 55%, model says 65% = 10% edge
        decision = evaluate_bet(
            simulation_result=result,
            market_odds=1.82,  # ~55% implied
            balls_remaining=60,  # Middle overs
        )
        
        assert decision.decision == BetDecision.BET
        assert decision.edge > 0.05
    
    def test_evaluate_bet_no_bet(self):
        """Test evaluate_bet returns NO_BET for small edge."""
        result = SimulationResult(
            mean_prob=0.52,
            std_prob=0.03,
            p5=0.47,
            p95=0.57,
            n_sims=1000,
            horizon_balls=1,
            time_taken_ms=50.0,
            league="bbl",
        )
        
        # Market implies 50%, model says 52% = 2% edge (below threshold)
        decision = evaluate_bet(
            simulation_result=result,
            market_odds=2.0,
            balls_remaining=60,
        )
        
        assert decision.decision == BetDecision.NO_BET
    
    def test_evaluate_bet_skip(self):
        """Test evaluate_bet returns SKIP for high uncertainty."""
        result = SimulationResult(
            mean_prob=0.65,
            std_prob=0.15,  # High uncertainty
            p5=0.40,
            p95=0.90,
            n_sims=1000,
            horizon_balls=1,
            time_taken_ms=50.0,
            league="bbl",
        )
        
        decision = evaluate_bet(
            simulation_result=result,
            market_odds=1.82,
            balls_remaining=60,
        )
        
        assert decision.decision == BetDecision.SKIP
    
    def test_phase_aware_thresholds(self):
        """Test phase-aware betting thresholds."""
        thresholds = BettingThresholds()
        
        # Death overs require higher edge
        assert thresholds.get_edge_min('death') > thresholds.get_edge_min('middle')
        
        # Death overs allow higher uncertainty
        assert thresholds.get_sigma_max('death') > thresholds.get_sigma_max('middle')

    def test_evaluate_bet_with_model_prob_override(self):
        """Test evaluate_bet uses explicit model_prob for edge calculation instead of simulation mean.
        
        This is the recommended approach for betting: use league-calibrated model probability
        from predictor.predict() for edge calculation, while using Monte Carlo simulation
        only for uncertainty estimation (σ).
        """
        # Simulation result with mean_prob = 0.50 (resource_win_prob heuristic)
        result = SimulationResult(
            mean_prob=0.50,  # This is the Monte Carlo mean (less accurate)
            std_prob=0.03,
            p5=0.45,
            p95=0.55,
            n_sims=2000,
            horizon_balls=6,
            time_taken_ms=50.0,
            league="bbl",
        )
        
        # Market implies 55% (odds 1.82)
        market_odds = 1.82
        
        # Without model_prob override: edge = 0.50 - 0.549 = -0.049 (NO_BET)
        decision_without = evaluate_bet(
            simulation_result=result,
            market_odds=market_odds,
            balls_remaining=60,  # Middle overs
        )
        assert decision_without.decision == BetDecision.NO_BET
        assert decision_without.model_prob == 0.50  # Uses simulation mean
        assert decision_without.edge < 0  # Negative edge
        
        # With model_prob override = 0.65 (league-calibrated ML model)
        # Edge = 0.65 - 0.549 = 0.10 (BET!)
        decision_with = evaluate_bet(
            simulation_result=result,
            market_odds=market_odds,
            balls_remaining=60,
            model_prob=0.65,  # League-calibrated probability
        )
        assert decision_with.decision == BetDecision.BET
        assert decision_with.model_prob == 0.65  # Uses provided model_prob
        assert decision_with.edge > 0.05  # Positive edge
        
        # Verify σ still comes from simulation (uncertainty quantification)
        assert decision_with.sigma == 0.03  # From simulation result, not model_prob

    def test_evaluate_bet_model_prob_used_for_kelly_stake(self):
        """Test that Kelly stake uses the model_prob (not simulation mean) when provided."""
        result = SimulationResult(
            mean_prob=0.50,
            std_prob=0.02,
            p5=0.47,
            p95=0.53,
            n_sims=2000,
            horizon_balls=6,
            time_taken_ms=50.0,
            league="bbl",
        )
        
        # With model_prob = 0.70, odds = 2.0
        # Kelly = (b * p - q) / b where b = 1.0, p = 0.70, q = 0.30
        # = (1.0 * 0.70 - 0.30) / 1.0 = 0.40 * fraction
        decision = evaluate_bet(
            simulation_result=result,
            market_odds=2.0,
            balls_remaining=60,
            model_prob=0.70,
        )
        
        assert decision.kelly_stake > 0  # Should recommend stake
        # Kelly stake uses prob_for_edge (0.70), not simulation mean (0.50)


class TestGetPhase:
    """Tests for phase detection."""
    
    def test_powerplay(self):
        """Test powerplay detection."""
        # Balls 1-36 = overs 1-6 = powerplay
        assert get_phase(120) == 'powerplay'  # Ball 1
        assert get_phase(96) == 'powerplay'   # Over 4
        assert get_phase(85) == 'powerplay'   # Over 6
    
    def test_middle(self):
        """Test middle overs detection."""
        # Overs 7-15 = middle
        assert get_phase(84) == 'middle'  # Over 7
        assert get_phase(60) == 'middle'  # Over 10
        assert get_phase(31) == 'middle'  # Over 15
    
    def test_death(self):
        """Test death overs detection."""
        # Overs 16-20 = death
        assert get_phase(30) == 'death'  # Over 16
        assert get_phase(18) == 'death'  # Over 17
        assert get_phase(6) == 'death'   # Over 20
        assert get_phase(1) == 'death'   # Last ball


class TestSimulateIntegration:
    """Integration tests for simulate function."""
    
    @patch('bbl_pipeline.simulation.engine.TerminalStateEvaluator')
    def test_simulate_returns_result(self, mock_evaluator):
        """Test simulate returns SimulationResult."""
        # Mock the evaluator to return fixed probability
        mock_instance = MagicMock()
        mock_instance.evaluate.return_value = 0.6
        mock_evaluator.return_value = mock_instance
        
        state = MatchState(
            innings=1,
            score=50,
            wickets_lost=2,
            balls_remaining=60,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        
        result = simulate(state, horizon=1, n_simulations=100)
        
        assert isinstance(result, SimulationResult)
        assert result.n_sims == 100
        assert result.horizon_balls == 1
    
    @patch('bbl_pipeline.simulation.engine.TerminalStateEvaluator')
    def test_simulate_single_ball(self, mock_evaluator):
        """Test single ball simulation."""
        mock_instance = MagicMock()
        mock_instance.evaluate.return_value = 0.5
        mock_evaluator.return_value = mock_instance
        
        state = MatchState(
            innings=1,
            score=50,
            wickets_lost=2,
            balls_remaining=60,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        
        result = simulate_single_ball(state, n_simulations=500)
        
        assert result.horizon_balls == 1
        assert result.n_sims == 500
    
    @patch('bbl_pipeline.simulation.engine.TerminalStateEvaluator')
    def test_simulate_one_over(self, mock_evaluator):
        """Test one over simulation."""
        mock_instance = MagicMock()
        mock_instance.evaluate.return_value = 0.5
        mock_evaluator.return_value = mock_instance
        
        state = MatchState(
            innings=1,
            score=50,
            wickets_lost=2,
            balls_remaining=60,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        
        result = simulate_one_over(state, n_simulations=1000)
        
        assert result.horizon_balls == 6
        assert result.n_sims == 1000


class TestMLModelBatchEvaluation:
    """Tests for ML model-based batch evaluation in simulation."""
    
    def test_simulate_with_mock_predictor(self):
        """Test simulate() accepts predictor parameter and uses it for evaluation."""
        from bbl_pipeline.simulation.engine import simulate_vectorized
        
        # Create mock predictor
        mock_predictor = MagicMock()
        # predict_batch returns array of probabilities
        mock_predictor.predict_batch.return_value = np.full(1000, 0.65)
        
        state = MatchState(
            innings=2,
            score=80,
            wickets_lost=3,
            balls_remaining=48,
            target_runs=160,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        
        result = simulate_vectorized(state, horizon=6, n_simulations=1000, predictor=mock_predictor)
        
        # Verify predictor was used
        assert mock_predictor.predict_batch.called
        assert result.mean_prob == pytest.approx(0.65, abs=0.05)  # Should be close to 0.65
    
    def test_simulate_without_predictor_uses_resource_prob(self):
        """Test simulate() without predictor falls back to resource_win_prob."""
        from bbl_pipeline.simulation.engine import simulate_vectorized
        
        state = MatchState(
            innings=1,
            score=50,
            wickets_lost=2,
            balls_remaining=60,
            batting_team="A",
            bowling_team="B",
            league="bbl",
        )
        
        # Without predictor, should use resource_win_prob evaluator
        result = simulate_vectorized(state, horizon=1, n_simulations=500)
        
        # Result should be valid
        assert 0 <= result.mean_prob <= 1
        assert result.n_sims == 500
    
    def test_terminal_state_evaluator_with_predictor(self):
        """Test TerminalStateEvaluator uses predictor for batch evaluation."""
        from bbl_pipeline.simulation.evaluator import TerminalStateEvaluator
        
        mock_predictor = MagicMock()
        mock_predictor.predict_batch.return_value = np.array([0.7, 0.8, 0.9])
        
        evaluator = TerminalStateEvaluator(predictor=mock_predictor)
        
        states = [
            MatchState(innings=1, score=50, wickets_lost=2, balls_remaining=60,
                      batting_team="A", bowling_team="B", league="bbl"),
            MatchState(innings=1, score=70, wickets_lost=3, balls_remaining=48,
                      batting_team="A", bowling_team="B", league="bbl"),
            MatchState(innings=1, score=90, wickets_lost=4, balls_remaining=36,
                      batting_team="A", bowling_team="B", league="bbl"),
        ]
        
        probs = evaluator.evaluate_batch_with_model(states)
        
        assert mock_predictor.predict_batch.called
        assert len(probs) == 3
        np.testing.assert_array_almost_equal(probs, [0.7, 0.8, 0.9])
    
    def test_terminal_state_evaluator_without_predictor_fallback(self):
        """Test TerminalStateEvaluator falls back to resource_win_prob without predictor."""
        from bbl_pipeline.simulation.evaluator import TerminalStateEvaluator
        
        evaluator = TerminalStateEvaluator()  # No predictor
        
        states = [
            MatchState(innings=1, score=50, wickets_lost=2, balls_remaining=60,
                      batting_team="A", bowling_team="B", league="bbl"),
            MatchState(innings=1, score=70, wickets_lost=3, balls_remaining=48,
                      batting_team="A", bowling_team="B", league="bbl"),
        ]
        
        probs = evaluator.evaluate_batch_with_model(states)
        
        # Should still return valid probabilities
        assert len(probs) == 2
        assert all(0 <= p <= 1 for p in probs)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
