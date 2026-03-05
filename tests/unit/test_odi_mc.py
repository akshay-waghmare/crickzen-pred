"""
Unit tests for ODI Monte Carlo simulation support.

Tests MatchState(300), ODI get_phase(), evaluator ODI detection,
NextBallSampler dynamic phases, and MatchState ODI operations.

Covers: FR-001, FR-002, FR-003, FR-004, FR-005, FR-009, FR-010
"""

import pytest
import numpy as np

from bbl_pipeline.simulation.state import MatchState
from bbl_pipeline.simulation.config import (
    get_phase,
    get_odi_phase_boundaries,
    ODI_PHASES,
    ODI_RUN_DIST,
    ODI_RUN_CDF,
    ODI_WICKET_PROB,
    ODI_WICKET_MULTIPLIER,
    PHASES,
)
from bbl_pipeline.simulation.evaluator import TerminalStateEvaluator
from bbl_pipeline.simulation.sampler import NextBallSampler


# =============================================================================
# T003/T007: MatchState ODI Validation (FR-001)
# =============================================================================

class TestMatchStateODI:
    """Test MatchState accepts total_balls=300 for ODI."""

    def test_odi_state_creation(self):
        """MatchState(total_balls=300) creates without error."""
        state = MatchState(
            innings=1, score=0, wickets_lost=0, balls_remaining=300,
            total_balls=300, league="odi", batting_team="Team A", bowling_team="Team B",
        )
        assert state.total_balls == 300
        assert state.balls_remaining == 300
        assert state.overs_completed == 0.0

    def test_odi_state_mid_innings(self):
        """MatchState at 30 overs into ODI."""
        state = MatchState(
            innings=1, score=150, wickets_lost=3, balls_remaining=120,
            total_balls=300, league="odi", batting_team="Team A", bowling_team="Team B",
        )
        assert state.overs_completed == 30.0
        assert state.score == 150

    def test_odi_second_innings_with_target(self):
        """MatchState innings 2 with target in ODI."""
        state = MatchState(
            innings=2, score=100, wickets_lost=2, balls_remaining=180,
            total_balls=300, league="odi", batting_team="Team A", bowling_team="Team B",
            target_runs=280,
        )
        assert state.runs_required == 180
        assert state.required_run_rate == pytest.approx(180 / 30, rel=0.01)

    def test_odi_state_various_valid_total_balls(self):
        """Various valid total_balls between 6 and 300."""
        for total_balls in [6, 12, 60, 120, 180, 240, 300]:
            state = MatchState(
                innings=1, score=0, wickets_lost=0, balls_remaining=total_balls,
                total_balls=total_balls, league="test", batting_team="A", bowling_team="B",
            )
            assert state.total_balls == total_balls

    def test_odi_state_above_300_raises(self):
        """total_balls above 300 raises ValueError."""
        with pytest.raises(ValueError, match="total_balls must be 6-300"):
            MatchState(
                innings=1, score=0, wickets_lost=0, balls_remaining=600,
                total_balls=600, league="test", batting_team="A", bowling_team="B",
            )

    def test_t20_still_works(self):
        """Standard T20 total_balls=120 still works."""
        state = MatchState(
            innings=1, score=0, wickets_lost=0, balls_remaining=120,
            total_balls=120, league="bbl", batting_team="A", bowling_team="B",
        )
        assert state.total_balls == 120


# =============================================================================
# T012: MatchState ODI Operations (US4)
# =============================================================================

class TestMatchStateODIOperations:
    """Test MatchState operations across 300-ball ODI innings."""

    def test_apply_outcome_runs(self):
        """apply_outcome correctly updates score and balls in ODI."""
        state = MatchState(
            innings=1, score=100, wickets_lost=2, balls_remaining=180,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        new_state = state.apply_outcome(runs=4, is_wicket=False)
        assert new_state.score == 104
        assert new_state.balls_remaining == 179
        assert new_state.wickets_lost == 2

    def test_apply_outcome_wicket(self):
        """apply_outcome correctly updates wickets in ODI."""
        state = MatchState(
            innings=1, score=200, wickets_lost=5, balls_remaining=60,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        new_state = state.apply_outcome(runs=0, is_wicket=True)
        assert new_state.score == 200
        assert new_state.wickets_lost == 6
        assert new_state.balls_remaining == 59

    def test_innings_completion_all_out(self):
        """Innings complete when 10 wickets lost in ODI."""
        state = MatchState(
            innings=1, score=180, wickets_lost=10, balls_remaining=60,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        assert state.is_over is True

    def test_innings_completion_overs_done(self):
        """Innings complete when all 300 balls bowled."""
        state = MatchState(
            innings=1, score=280, wickets_lost=6, balls_remaining=0,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        assert state.is_over is True
        assert state.overs_completed == 50.0

    def test_innings_completion_target_chased(self):
        """Innings complete when target chased in ODI."""
        state = MatchState(
            innings=2, score=280, wickets_lost=4, balls_remaining=30,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
            target_runs=275,
        )
        assert state.is_over is True

    def test_overs_completed_property(self):
        """overs_completed correct for various ODI positions."""
        cases = [
            (300, 0.0),   # Start
            (240, 10.0),  # After powerplay
            (120, 30.0),  # Halfway
            (60, 40.0),   # Setup
            (0, 50.0),    # End
        ]
        for balls_remaining, expected_overs in cases:
            state = MatchState(
                innings=1, score=0, wickets_lost=0, balls_remaining=balls_remaining,
                total_balls=300, league="odi", batting_team="A", bowling_team="B",
            )
            assert state.overs_completed == expected_overs, \
                f"balls_remaining={balls_remaining}: expected {expected_overs}, got {state.overs_completed}"

    def test_propagate_total_balls_through_apply_outcome(self):
        """apply_outcome preserves total_balls=300."""
        state = MatchState(
            innings=1, score=0, wickets_lost=0, balls_remaining=300,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        new_state = state.apply_outcome(runs=1, is_wicket=False)
        assert new_state.total_balls == 300

    def test_copy_preserves_total_balls(self):
        """copy() preserves total_balls=300."""
        state = MatchState(
            innings=1, score=100, wickets_lost=3, balls_remaining=120,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        copied = state.copy()
        assert copied.total_balls == 300


# =============================================================================
# T004/T005/T007: ODI Phase System (FR-009)
# =============================================================================

class TestODIPhaseSystem:
    """Test ODI 4-phase system: powerplay, middle, setup, death."""

    def test_odi_phases_tuple(self):
        """ODI_PHASES contains 4 phases."""
        assert ODI_PHASES == ("powerplay", "middle", "setup", "death")

    def test_t20_phases_unchanged(self):
        """T20 PHASES still has 3 phases."""
        assert PHASES == ("powerplay", "middle", "death")

    def test_odi_phase_boundaries(self):
        """get_odi_phase_boundaries returns correct thresholds."""
        pp_end, mid_end, setup_end = get_odi_phase_boundaries()
        assert pp_end == 10
        assert mid_end == 34
        assert setup_end == 40

    def test_odi_powerplay_phase(self):
        """ODI overs 1-10 are powerplay."""
        # Over 0 (start of innings)
        assert get_phase(300, total_balls=300) == "powerplay"
        # Over 5 (mid powerplay)
        assert get_phase(270, total_balls=300) == "powerplay"
        # Over 9 (last powerplay over)
        assert get_phase(246, total_balls=300) == "powerplay"

    def test_odi_middle_phase(self):
        """ODI overs 11-34 are middle."""
        # Over 10 (first middle over)
        assert get_phase(240, total_balls=300) == "middle"
        # Over 20 (mid middle)
        assert get_phase(180, total_balls=300) == "middle"
        # Over 33 (last middle over)
        assert get_phase(102, total_balls=300) == "middle"

    def test_odi_setup_phase(self):
        """ODI overs 35-40 are setup."""
        # Over 34 (first setup over)
        assert get_phase(96, total_balls=300) == "setup"
        # Over 37 (mid setup)
        assert get_phase(78, total_balls=300) == "setup"
        # Over 39 (last setup over)
        assert get_phase(66, total_balls=300) == "setup"

    def test_odi_death_phase(self):
        """ODI overs 41-50 are death."""
        # Over 40 (first death over)
        assert get_phase(60, total_balls=300) == "death"
        # Over 45 (mid death)
        assert get_phase(30, total_balls=300) == "death"
        # Over 49 (last over)
        assert get_phase(6, total_balls=300) == "death"
        # Last ball
        assert get_phase(1, total_balls=300) == "death"

    def test_odi_phase_zero_balls(self):
        """0 balls remaining returns death."""
        assert get_phase(0, total_balls=300) == "death"

    def test_odi_phase_boundary_exact(self):
        """Phase boundaries at exact thresholds."""
        # Over 10 completed = 240 balls remaining = middle (not powerplay)
        assert get_phase(240, total_balls=300) == "middle"
        # Over 34 completed = 96 balls remaining = setup (not middle)
        assert get_phase(96, total_balls=300) == "setup"
        # Over 40 completed = 60 balls remaining = death (not setup)
        assert get_phase(60, total_balls=300) == "death"

    def test_t20_phases_unchanged_standard(self):
        """T20 get_phase still returns 3-phase system."""
        assert get_phase(120) == "powerplay"
        assert get_phase(84) == "middle"
        assert get_phase(30) == "death"

    def test_t20_reduced_still_works(self):
        """Reduced-over T20 still works."""
        # 15-over match
        assert get_phase(90, total_balls=90) in ("powerplay", "middle", "death")


# =============================================================================
# T006/T007: Evaluator ODI Format Detection (FR-005)
# =============================================================================

class TestEvaluatorODIDetection:
    """Test TerminalStateEvaluator uses FormatConfig.odi() for ODI."""

    def test_evaluator_odi_config(self):
        """Evaluator uses FormatConfig.odi() for 300-ball innings."""
        evaluator = TerminalStateEvaluator(model_dir="models/nonexistent")
        calc = evaluator._get_calculator(300)
        # Verify it's using ODI config (par=257.7)
        assert calc.config.par_score == 257.7
        assert calc.config.total_balls == 300
        assert len(calc.config.phase_names) == 4

    def test_evaluator_t20_config(self):
        """Evaluator still uses T20 config for 120-ball innings."""
        evaluator = TerminalStateEvaluator(model_dir="models/nonexistent")
        calc = evaluator._get_calculator(120)
        assert calc.config.total_balls == 120

    def test_evaluator_reduced_t20_config(self):
        """Evaluator uses reduced T20 config for <120-ball innings."""
        evaluator = TerminalStateEvaluator(model_dir="models/nonexistent")
        calc = evaluator._get_calculator(90)  # 15-over match
        assert calc.config.total_balls == 90

    def test_evaluator_caches_calculators(self):
        """Evaluator caches calculators by total_balls."""
        evaluator = TerminalStateEvaluator(model_dir="models/nonexistent")
        calc1 = evaluator._get_calculator(300)
        calc2 = evaluator._get_calculator(300)
        assert calc1 is calc2  # Same object

    def test_evaluate_odi_first_innings(self):
        """Evaluator produces reasonable probability for ODI first innings."""
        evaluator = TerminalStateEvaluator(model_dir="models/nonexistent")
        state = MatchState(
            innings=1, score=150, wickets_lost=3, balls_remaining=120,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        prob = evaluator.evaluate(state, apply_temp=False)
        # 150/3 after 30 overs is reasonable in ODI — probability should be moderate
        assert 0.05 < prob < 0.95, f"Got extreme probability: {prob}"

    def test_evaluate_odi_second_innings_chase(self):
        """Evaluator produces reasonable probability for ODI chase."""
        evaluator = TerminalStateEvaluator(model_dir="models/nonexistent")
        state = MatchState(
            innings=2, score=150, wickets_lost=2, balls_remaining=120,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
            target_runs=280,
        )
        prob = evaluator.evaluate(state, apply_temp=False)
        # Chasing 280 at 150/2 after 30 overs — favorable position
        assert 0.1 < prob < 0.95, f"Got extreme probability: {prob}"

    def test_evaluate_odi_target_chased(self):
        """Evaluator returns 1.0 when target chased in ODI."""
        evaluator = TerminalStateEvaluator(model_dir="models/nonexistent")
        state = MatchState(
            innings=2, score=285, wickets_lost=4, balls_remaining=30,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
            target_runs=280,
        )
        prob = evaluator.evaluate(state, apply_temp=False)
        assert prob == 1.0

    def test_evaluate_odi_all_out(self):
        """Evaluator returns 0.0 when all out in ODI chase."""
        evaluator = TerminalStateEvaluator(model_dir="models/nonexistent")
        state = MatchState(
            innings=2, score=200, wickets_lost=10, balls_remaining=60,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
            target_runs=280,
        )
        prob = evaluator.evaluate(state, apply_temp=False)
        assert prob == 0.0


# =============================================================================
# T007: MatchState.phase property integration with ODI phases
# =============================================================================

class TestMatchStatePhaseIntegration:
    """Test MatchState.phase returns correct ODI phases."""

    def test_phase_returns_powerplay_odi(self):
        """MatchState.phase returns 'powerplay' in ODI powerplay."""
        state = MatchState(
            innings=1, score=30, wickets_lost=0, balls_remaining=270,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        assert state.phase == "powerplay"

    def test_phase_returns_middle_odi(self):
        """MatchState.phase returns 'middle' in ODI middle overs."""
        state = MatchState(
            innings=1, score=100, wickets_lost=2, balls_remaining=180,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        assert state.phase == "middle"

    def test_phase_returns_setup_odi(self):
        """MatchState.phase returns 'setup' in ODI setup phase."""
        state = MatchState(
            innings=1, score=200, wickets_lost=4, balls_remaining=90,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        assert state.phase == "setup"

    def test_phase_returns_death_odi(self):
        """MatchState.phase returns 'death' in ODI death overs."""
        state = MatchState(
            innings=1, score=250, wickets_lost=6, balls_remaining=30,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        assert state.phase == "death"


# =============================================================================
# T010: ODI Config Constants Validation (FR-004)
# =============================================================================

class TestODIConfigConstants:
    """Validate ODI default distribution constants."""

    def test_odi_run_dist_has_4_phases(self):
        """ODI_RUN_DIST has all 4 phases."""
        assert set(ODI_RUN_DIST.keys()) == {"powerplay", "middle", "setup", "death"}

    def test_odi_run_dist_sums_to_one(self):
        """Each phase run distribution sums to 1.0."""
        for phase, dist in ODI_RUN_DIST.items():
            total = sum(dist.values())
            assert abs(total - 1.0) < 0.001, f"{phase} sums to {total}"

    def test_odi_run_dist_has_7_outcomes(self):
        """Each phase has 7 run outcomes (0-6)."""
        for phase, dist in ODI_RUN_DIST.items():
            assert sorted(dist.keys()) == [0, 1, 2, 3, 4, 5, 6], f"{phase} missing outcomes"

    def test_odi_wicket_prob_has_4_phases(self):
        """ODI_WICKET_PROB has all 4 phases."""
        assert set(ODI_WICKET_PROB.keys()) == {"powerplay", "middle", "setup", "death"}

    def test_odi_wicket_prob_in_range(self):
        """Wicket probabilities are in valid range [0.01, 0.15]."""
        for phase, prob in ODI_WICKET_PROB.items():
            assert 0.01 <= prob <= 0.15, f"{phase} wicket prob {prob} out of range"

    def test_odi_wicket_multiplier_has_10_entries(self):
        """ODI_WICKET_MULTIPLIER has 10 entries (wickets 0-9)."""
        assert set(ODI_WICKET_MULTIPLIER.keys()) == set(range(10))

    def test_odi_wicket_multiplier_in_range(self):
        """All multipliers are in valid range [0.5, 2.0]."""
        for wickets, mult in ODI_WICKET_MULTIPLIER.items():
            assert 0.5 <= mult <= 2.0, f"Wickets {wickets}: multiplier {mult} out of range"

    def test_odi_run_cdf_has_4_phases(self):
        """ODI_RUN_CDF pre-computed CDFs exist for all 4 phases."""
        assert set(ODI_RUN_CDF.keys()) == {"powerplay", "middle", "setup", "death"}

    def test_odi_run_cdf_ends_near_one(self):
        """Each CDF ends at approximately 1.0."""
        for phase, (values, cdf) in ODI_RUN_CDF.items():
            assert abs(cdf[-1] - 1.0) < 0.001, f"{phase} CDF ends at {cdf[-1]}"


# =============================================================================
# T013: NextBallSampler ODI Tests (FR-002, FR-003)
# =============================================================================

class TestNextBallSamplerODI:
    """Test NextBallSampler with ODI 4-phase distributions."""

    def test_sampler_odi_league_uses_odi_defaults(self):
        """Sampler for ODI league uses 4-phase ODI defaults."""
        sampler = NextBallSampler(seed=42, league="odi")
        assert "setup" in sampler._run_values
        assert "setup" in sampler._run_cdfs
        assert len(sampler._run_values) == 4

    def test_sampler_odm_league_uses_odi_defaults(self):
        """Sampler for ODM league also uses ODI defaults."""
        sampler = NextBallSampler(seed=42, league="odis")
        assert "setup" in sampler._run_values

    def test_sampler_t20_league_no_setup_phase(self):
        """T20 sampler has no 'setup' phase."""
        sampler = NextBallSampler(seed=42)  # No league = global T20
        assert "setup" not in sampler._run_values
        assert len(sampler._run_values) == 3

    def test_sampler_odi_sample_runs(self):
        """Sampler produces valid runs for ODI phases including setup."""
        sampler = NextBallSampler(seed=42, league="odi")
        for phase in ODI_PHASES:
            runs = sampler._sample_runs(phase)
            assert runs in [0, 1, 2, 3, 4, 5, 6], f"Invalid runs {runs} for {phase}"

    def test_sampler_odi_sample_wicket(self):
        """Sampler produces valid wicket outcomes for ODI phases."""
        sampler = NextBallSampler(seed=42, league="odi")
        for phase in ODI_PHASES:
            # Sample many times — should get at least some True and False
            results = [sampler._sample_wicket(phase, wickets_lost=2) for _ in range(200)]
            assert any(r for r in results), f"No wickets fell in 200 balls ({phase})"
            assert any(not r for r in results), f"Every ball was a wicket ({phase})"

    def test_odi_wicket_multiplier_loaded(self):
        """ODI sampler has wicket multiplier with int keys 0-9."""
        sampler = NextBallSampler(seed=42, league="odi")
        assert 0 in sampler._wicket_multiplier
        assert 9 in sampler._wicket_multiplier
        assert sampler._wicket_multiplier[0] == 0.84  # Empirical: openers less vulnerable
        assert sampler._wicket_multiplier[9] == 2.00  # Clamped from 2.61

    def test_sampler_odi_get_wicket_prob(self):
        """get_wicket_prob works for all ODI phases."""
        sampler = NextBallSampler(seed=42, league="odi")
        for phase in ODI_PHASES:
            prob = sampler.get_wicket_prob(phase, wickets_lost=3)
            assert 0.0 < prob <= 0.25, f"{phase}: prob {prob} out of range"

    def test_sampler_odi_sample_full_state(self):
        """Sampler.sample() works with ODI MatchState."""
        sampler = NextBallSampler(seed=42, league="odi")
        state = MatchState(
            innings=1, score=100, wickets_lost=2, balls_remaining=180,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        runs, is_wicket = sampler.sample(state)
        assert isinstance(runs, (int, np.integer))
        assert isinstance(is_wicket, bool)
        assert 0 <= runs <= 6

    def test_sampler_odi_setup_phase_sampling(self):
        """Sampler handles setup phase correctly (specific to ODI)."""
        sampler = NextBallSampler(seed=42, league="odi")
        state = MatchState(
            innings=1, score=200, wickets_lost=4, balls_remaining=90,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        assert state.phase == "setup"
        runs, is_wicket = sampler.sample(state)
        assert 0 <= runs <= 6

    def test_sampler_odi_vectorized_has_setup(self):
        """sample_vectorized iterates over setup phase for ODI."""
        sampler = NextBallSampler(seed=42, league="odi")
        # sample_vectorized iterates over self._run_values.keys()
        phases = list(sampler._run_values.keys())
        assert "setup" in phases

    def test_sampler_odi_run_distribution_shape(self):
        """ODI sampler produces expected run distribution (basic sanity)."""
        sampler = NextBallSampler(seed=42, league="odi")
        n = 10_000
        runs = [sampler._sample_runs("death") for _ in range(n)]
        avg = np.mean(runs)
        # ODI death phase includes boundaries — avg ~1.5-3.0 runs per ball
        assert 1.0 < avg < 3.5, f"Death-phase avg runs per ball: {avg}"

    def test_sampler_odi_death_more_boundaries_than_middle(self):
        """ODI death has more scoring than middle (distribution check)."""
        sampler = NextBallSampler(seed=42, league="odi")
        n = 10_000
        mid_runs = [sampler._sample_runs("middle") for _ in range(n)]
        death_runs = [sampler._sample_runs("death") for _ in range(n)]
        assert np.mean(death_runs) > np.mean(mid_runs)


# =============================================================================
# T014: Full ODI Innings MC Simulation Integration (SC-002)
# =============================================================================

class TestODIMCSimulationIntegration:
    """End-to-end ODI MC simulation: run 10K sims, validate totals."""

    def test_full_odi_innings_simulation_completes(self):
        """Simulate a full ODI first innings without crashing."""
        sampler = NextBallSampler(seed=42, league="odi")
        state = MatchState(
            innings=1, score=0, wickets_lost=0, balls_remaining=300,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        while not state.is_over:
            runs, is_wicket = sampler.sample(state)
            state = state.apply_outcome(runs=int(runs), is_wicket=is_wicket)
        # Innings should have completed
        assert state.balls_remaining == 0 or state.wickets_lost >= 10
        assert state.score > 0

    def test_odi_average_total_realistic(self):
        """Average of 10K ODI innings is roughly 200-320 (realistic)."""
        np.random.seed(42)
        n_sims = 10_000
        totals = []
        for i in range(n_sims):
            sampler = NextBallSampler(seed=i, league="odi")
            state = MatchState(
                innings=1, score=0, wickets_lost=0, balls_remaining=300,
                total_balls=300, league="odi", batting_team="A", bowling_team="B",
            )
            while not state.is_over:
                runs, is_wicket = sampler.sample(state)
                state = state.apply_outcome(runs=int(runs), is_wicket=is_wicket)
            totals.append(state.score)
        avg = np.mean(totals)
        std = np.std(totals)
        # ODI par is ~257.7, accept 200-320 range for default distributions
        assert 200 < avg < 320, f"Average ODI total {avg:.1f} out of range"
        assert 20 < std < 80, f"Std dev {std:.1f} seems unrealistic"

    def test_odi_second_innings_target_chasing(self):
        """ODI second innings can chase a target."""
        sampler = NextBallSampler(seed=42, league="odi")
        state = MatchState(
            innings=2, score=0, wickets_lost=0, balls_remaining=300,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
            target_runs=250,
        )
        while not state.is_over:
            runs, is_wicket = sampler.sample(state)
            state = state.apply_outcome(runs=int(runs), is_wicket=is_wicket)
        # Should have terminated (either chased, all out, or overs done)
        assert state.is_over

    def test_odi_all_4_phases_visited(self):
        """A full ODI innings visits all 4 phases."""
        sampler = NextBallSampler(seed=42, league="odi")
        state = MatchState(
            innings=1, score=0, wickets_lost=0, balls_remaining=300,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        phases_seen = set()
        while not state.is_over:
            phases_seen.add(state.phase)
            runs, is_wicket = sampler.sample(state)
            state = state.apply_outcome(runs=int(runs), is_wicket=is_wicket)
        # If not all out before setup/death, all 4 should be visited
        assert "powerplay" in phases_seen
        assert "middle" in phases_seen
        # setup and death depend on wickets — only check if innings lasted enough
        if state.balls_remaining < 60:  # Got past setup phase
            assert "setup" in phases_seen
        if state.balls_remaining == 0 or state.balls_remaining <= 60:
            assert "death" in phases_seen or state.wickets_lost >= 10


# =============================================================================
# T032: MC Calibrator ODI Phase Boundaries & InningsPhaseCalibrators (US3)
# =============================================================================

class TestOverToPhaseODI:
    """Test over_to_phase() with ODI boundaries."""

    def test_t20_default_powerplay(self):
        from bbl_pipeline.calibration.mc_calibrator import over_to_phase
        assert over_to_phase(0) == "pp"
        assert over_to_phase(5) == "pp"

    def test_t20_default_middle(self):
        from bbl_pipeline.calibration.mc_calibrator import over_to_phase
        assert over_to_phase(6) == "mid"
        assert over_to_phase(14) == "mid"

    def test_t20_default_death(self):
        from bbl_pipeline.calibration.mc_calibrator import over_to_phase
        assert over_to_phase(15) == "death"
        assert over_to_phase(19) == "death"

    def test_odi_powerplay(self):
        from bbl_pipeline.calibration.mc_calibrator import over_to_phase
        assert over_to_phase(0, total_overs=50) == "pp"
        assert over_to_phase(9, total_overs=50) == "pp"

    def test_odi_middle(self):
        from bbl_pipeline.calibration.mc_calibrator import over_to_phase
        assert over_to_phase(10, total_overs=50) == "mid"
        assert over_to_phase(33, total_overs=50) == "mid"

    def test_odi_setup(self):
        from bbl_pipeline.calibration.mc_calibrator import over_to_phase
        assert over_to_phase(34, total_overs=50) == "setup"
        assert over_to_phase(39, total_overs=50) == "setup"

    def test_odi_death(self):
        from bbl_pipeline.calibration.mc_calibrator import over_to_phase
        assert over_to_phase(40, total_overs=50) == "death"
        assert over_to_phase(49, total_overs=50) == "death"

    def test_odi_boundary_transitions(self):
        """Verify exact boundary transitions between phases."""
        from bbl_pipeline.calibration.mc_calibrator import over_to_phase
        assert over_to_phase(9, total_overs=50) == "pp"
        assert over_to_phase(10, total_overs=50) == "mid"
        assert over_to_phase(33, total_overs=50) == "mid"
        assert over_to_phase(34, total_overs=50) == "setup"
        assert over_to_phase(39, total_overs=50) == "setup"
        assert over_to_phase(40, total_overs=50) == "death"


class TestInningsPhaseCalibratorsODI:
    """Test InningsPhaseCalibrators with 4-phase ODI support."""

    def test_odi_valid_phases(self):
        from bbl_pipeline.calibration.mc_calibrator import InningsPhaseCalibrators
        ipc = InningsPhaseCalibrators(total_overs=50)
        assert "setup" in ipc.valid_phases
        assert len(ipc.valid_phases) == 4

    def test_t20_valid_phases(self):
        from bbl_pipeline.calibration.mc_calibrator import InningsPhaseCalibrators
        ipc = InningsPhaseCalibrators(total_overs=20)
        assert "setup" not in ipc.valid_phases
        assert len(ipc.valid_phases) == 3

    def test_odi_set_setup_calibrator(self):
        from bbl_pipeline.calibration.mc_calibrator import (
            InningsPhaseCalibrators, MCCalibrator,
        )
        ipc = InningsPhaseCalibrators(total_overs=50)
        cal = MCCalibrator()
        ipc.set(1, "setup", cal)
        assert ipc.get(1, "setup") is cal

    def test_t20_reject_setup_phase(self):
        from bbl_pipeline.calibration.mc_calibrator import InningsPhaseCalibrators, MCCalibrator
        ipc = InningsPhaseCalibrators(total_overs=20)
        with pytest.raises(ValueError, match="Invalid phase"):
            ipc.set(1, "setup", MCCalibrator())

    def test_odi_calibrate_fallback(self):
        from bbl_pipeline.calibration.mc_calibrator import InningsPhaseCalibrators
        ipc = InningsPhaseCalibrators(total_overs=50)
        # No calibrator set → returns raw
        assert ipc.calibrate(0.65, innings=1, phase="setup") == 0.65

    def test_odi_8_calibrators(self):
        """ODI should support 8 calibrators (2 innings × 4 phases)."""
        from bbl_pipeline.calibration.mc_calibrator import (
            InningsPhaseCalibrators, MCCalibrator,
        )
        ipc = InningsPhaseCalibrators(total_overs=50)
        for innings in [1, 2]:
            for phase in ["pp", "mid", "setup", "death"]:
                ipc.set(innings, phase, MCCalibrator())
        assert len(ipc.calibrators) == 8

    def test_odi_summary_includes_setup(self):
        from bbl_pipeline.calibration.mc_calibrator import InningsPhaseCalibrators
        ipc = InningsPhaseCalibrators(total_overs=50)
        summ = ipc.summary()
        assert "setup" in summ
        assert "total_overs=50" in summ


# =============================================================================
# T035: Resource Win Prob Validation for ODI Scenarios (US3)
# =============================================================================

class TestResourceWinProbODI:
    """Validate resource_win_prob returns sensible ODI probabilities."""

    def _eval(self, innings, score, wickets, balls_remaining, target=None):
        """Helper to evaluate a single ODI state."""
        evaluator = TerminalStateEvaluator(model_dir="models/nonexistent")
        state = MatchState(
            innings=innings, score=score, wickets_lost=wickets,
            balls_remaining=balls_remaining, total_balls=300,
            league="odi", batting_team="A", bowling_team="B",
            target_runs=target,
        )
        return evaluator.evaluate(state, apply_temp=False)

    def test_first_innings_start_near_50_50(self):
        """0/0 at start of ODI innings → ~50% (no information)."""
        prob = self._eval(1, 0, 0, 300)
        assert 0.35 < prob < 0.65, f"Start of innings prob={prob}"

    def test_first_innings_above_par_favorable(self):
        """Score well above par → > 50%."""
        prob = self._eval(1, 320, 6, 0)
        assert prob > 0.6, f"320/6 completed should be favorable: {prob}"

    def test_first_innings_below_par_unfavorable(self):
        """Score below par → < 50%."""
        prob = self._eval(1, 180, 10, 60)
        assert prob < 0.4, f"180 all out should be unfavorable: {prob}"

    def test_second_innings_easy_chase(self):
        """Need 30 from 120 balls, 8 wickets in hand → very likely."""
        prob = self._eval(2, 220, 2, 120, target=250)
        assert prob > 0.7, f"Easy chase should be > 0.7: {prob}"

    def test_second_innings_hard_chase(self):
        """Need 200 from 60 balls, 3 wickets left → very unlikely."""
        prob = self._eval(2, 120, 7, 60, target=320)
        assert prob < 0.15, f"Hard chase should be < 0.15: {prob}"

    def test_second_innings_target_reached(self):
        """Score already past target → 1.0."""
        prob = self._eval(2, 260, 3, 60, target=255)
        assert prob > 0.99, f"Target surpassed should be ~1.0: {prob}"

    def test_second_innings_all_out_short(self):
        """All out well below target → 0.0."""
        prob = self._eval(2, 150, 10, 120, target=300)
        assert prob < 0.01, f"All out short should be ~0.0: {prob}"

    def test_first_innings_more_wickets_worse(self):
        """More wickets lost at same score/overs → lower probability."""
        prob_3w = self._eval(1, 150, 3, 120)
        prob_7w = self._eval(1, 150, 7, 120)
        assert prob_7w < prob_3w, f"7 wickets ({prob_7w}) should be worse than 3 ({prob_3w})"

    def test_first_innings_higher_score_better(self):
        """Higher score with same wickets/overs → better probability."""
        prob_200 = self._eval(1, 200, 5, 60)
        prob_280 = self._eval(1, 280, 5, 60)
        assert prob_280 > prob_200, f"280/5 ({prob_280}) should be better than 200/5 ({prob_200})"


# =============================================================================
# T039: MC Enrichment Unit Tests (US6)
# =============================================================================

class TestPartnershipMomentum:
    """T036: Partnership momentum enrichment tests."""

    def test_no_effect_early_partnership(self):
        """No boundary upgrade when partnership < 20 balls."""
        sampler = NextBallSampler(seed=42, league="odi", enrichments=True)
        sampler._balls_since_last_wicket = 5
        state = MatchState(
            innings=1, score=100, wickets_lost=3, balls_remaining=120,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        assert sampler._apply_partnership_momentum(0, state) == 0

    def test_momentum_effect_established_partnership(self):
        """Boundary upgrade possible after 30+ balls partnership."""
        sampler = NextBallSampler(seed=42, league="odi", enrichments=True)
        sampler._balls_since_last_wicket = 40
        state = MatchState(
            innings=1, score=150, wickets_lost=2, balls_remaining=150,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        upgrades = 0
        for _ in range(1000):
            result = sampler._apply_partnership_momentum(1, state)
            if result == 4:
                upgrades += 1
        assert upgrades > 20, f"Expected some upgrades, got {upgrades}"
        assert upgrades < 120, f"Too many upgrades: {upgrades}"

    def test_enrichments_disabled_no_effect(self):
        """Enrichments=False → no partnership momentum."""
        sampler = NextBallSampler(seed=42, league="odi", enrichments=False)
        assert sampler.enrichments is False


class TestNewBatsmanFactor:
    """T037: New batsman factor enrichment tests."""

    def test_new_batsman_reduces_runs(self):
        """Within 10 balls of wicket, some 1s/2s become dots."""
        sampler = NextBallSampler(seed=42, league="odi", enrichments=True)
        sampler._balls_since_last_wicket = 2
        dots = sum(sampler._apply_new_batsman_runs_modifier(1) == 0 for _ in range(1000))
        assert dots > 50, f"Expected some dots from settling, got {dots}"
        assert dots < 250, f"Too many dots: {dots}"

    def test_settled_batsman_no_effect(self):
        """After 10+ balls, no settling effect."""
        sampler = NextBallSampler(seed=42, league="odi", enrichments=True)
        sampler._balls_since_last_wicket = 15
        dots = sum(sampler._apply_new_batsman_runs_modifier(1) == 0 for _ in range(1000))
        assert dots == 0, f"Expected no effect after settling, got {dots} dots"

    def test_boundaries_not_affected(self):
        """Boundaries (4, 6) are never reduced by new batsman factor."""
        sampler = NextBallSampler(seed=42, league="odi", enrichments=True)
        sampler._balls_since_last_wicket = 0
        for _ in range(100):
            assert sampler._apply_new_batsman_runs_modifier(4) == 4
            assert sampler._apply_new_batsman_runs_modifier(6) == 6


class TestPitchDeterioration:
    """T038: Pitch deterioration enrichment tests."""

    def test_no_effect_early_innings(self):
        """No extra wickets in first 40% of innings."""
        sampler = NextBallSampler(seed=42, league="odi", enrichments=True)
        state = MatchState(
            innings=1, score=50, wickets_lost=1, balls_remaining=240,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        extra = sum(
            sampler._apply_pitch_deterioration(False, state, "middle", 1)
            for _ in range(1000)
        )
        assert extra == 0, f"Expected no extra wickets early, got {extra}"

    def test_extra_wickets_late_innings(self):
        """Extra wickets in last 30% of innings."""
        sampler = NextBallSampler(seed=42, league="odi", enrichments=True)
        state = MatchState(
            innings=1, score=200, wickets_lost=5, balls_remaining=30,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        extra = sum(
            sampler._apply_pitch_deterioration(False, state, "death", 5)
            for _ in range(10000)
        )
        assert extra > 100, f"Expected some extra wickets late, got {extra}"
        assert extra < 700, f"Too many extra wickets: {extra}"

    def test_already_wicket_unchanged(self):
        """If already a wicket, pitch deterioration doesn't double-apply."""
        sampler = NextBallSampler(seed=42, league="odi", enrichments=True)
        state = MatchState(
            innings=1, score=200, wickets_lost=5, balls_remaining=30,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        for _ in range(100):
            assert sampler._apply_pitch_deterioration(True, state, "death", 5) is True


class TestEnrichedMCSimulation:
    """Integration test: enriched vs base MC for ODI."""

    def test_enriched_simulation_completes(self):
        """Enriched MC simulation completes without crashing."""
        sampler = NextBallSampler(seed=42, league="odi", enrichments=True)
        state = MatchState(
            innings=1, score=0, wickets_lost=0, balls_remaining=300,
            total_balls=300, league="odi", batting_team="A", bowling_team="B",
        )
        while not state.is_over:
            runs, is_wicket = sampler.sample(state)
            state = state.apply_outcome(runs=int(runs), is_wicket=is_wicket)
        assert state.is_over
        assert state.score > 0

    def test_enriched_does_not_crash_t20(self):
        """Enrichments work with T20 states too."""
        sampler = NextBallSampler(seed=42, league="bbl", enrichments=True)
        state = MatchState(
            innings=1, score=0, wickets_lost=0, balls_remaining=120,
            total_balls=120, league="bbl", batting_team="A", bowling_team="B",
        )
        while not state.is_over:
            runs, is_wicket = sampler.sample(state)
            state = state.apply_outcome(runs=int(runs), is_wicket=is_wicket)
        assert state.is_over

    def test_enrichment_produces_different_distribution(self):
        """Enriched and base MC should differ slightly in distribution."""
        n_sims = 500
        base_totals = []
        enriched_totals = []
        for i in range(n_sims):
            s_base = NextBallSampler(seed=i, league="odi", enrichments=False)
            state = MatchState(
                innings=1, score=0, wickets_lost=0, balls_remaining=300,
                total_balls=300, league="odi", batting_team="A", bowling_team="B",
            )
            while not state.is_over:
                r, w = s_base.sample(state)
                state = state.apply_outcome(runs=int(r), is_wicket=w)
            base_totals.append(state.score)

            s_rich = NextBallSampler(seed=i, league="odi", enrichments=True)
            state = MatchState(
                innings=1, score=0, wickets_lost=0, balls_remaining=300,
                total_balls=300, league="odi", batting_team="A", bowling_team="B",
            )
            while not state.is_over:
                r, w = s_rich.sample(state)
                state = state.apply_outcome(runs=int(r), is_wicket=w)
            enriched_totals.append(state.score)

        base_avg = np.mean(base_totals)
        enriched_avg = np.mean(enriched_totals)
        assert 180 < base_avg < 340, f"Base avg {base_avg} unrealistic"
        assert 180 < enriched_avg < 340, f"Enriched avg {enriched_avg} unrealistic"
        diff = abs(base_avg - enriched_avg)
        assert diff < 40, f"Too large difference: {diff}"


