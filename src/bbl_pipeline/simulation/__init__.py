"""
Monte Carlo Simulation Engine for T20 Win Probability.

This module provides forward-looking win probability distributions by simulating
ball-by-ball outcomes. It complements the ML-based win probability model by
providing uncertainty quantification and multi-ball lookahead capabilities.

Key Components:
- MatchState: Current match situation for simulation
- NextBallSampler: Phase-based outcome sampling
- simulate(): Main simulation API
- evaluate_bet(): Betting decision support

Example:
    from bbl_pipeline.simulation import MatchState, simulate, evaluate_bet
    
    state = MatchState(
        innings=2, score=110, wickets_lost=4, balls_remaining=48,
        target_runs=170, league="bbl",
        batting_team="Melbourne Stars", bowling_team="Sydney Sixers"
    )
    
    result = simulate(state, horizon_balls=6, n_sims=2000, league="bbl")
    print(f"Win probability: {result.mean_prob:.3f} ± {result.std_prob:.3f}")
"""

from .state import MatchState, SimulationResult
from .config import (
    RUN_DIST,
    WICKET_PROB,
    WICKET_MULTIPLIER,
    EDGE_MIN_BY_PHASE,
    SIGMA_MAX_BY_PHASE,
    get_phase,
    PHASES,
)
from .sampler import NextBallSampler
from .evaluator import (
    TerminalStateEvaluator,
    evaluate_terminal_state,
    apply_temperature,
    apply_temperature_vectorized,
    load_league_temperature,
)
from .engine import (
    simulate,
    simulate_vectorized,
    simulate_single_ball,
    simulate_one_over,
    get_required_simulations,
)
from .betting import (
    BetDecision,
    BettingThresholds,
    BettingDecision,
    evaluate_bet,
    calculate_kelly_stake,
    calculate_edge,
    odds_to_implied_prob,
    implied_prob_to_odds,
)

__all__ = [
    # Core entities
    "MatchState",
    "SimulationResult",
    # Configuration
    "RUN_DIST",
    "WICKET_PROB",
    "WICKET_MULTIPLIER",
    "EDGE_MIN_BY_PHASE",
    "SIGMA_MAX_BY_PHASE",
    "PHASES",
    "get_phase",
    # Sampler
    "NextBallSampler",
    # Evaluator
    "TerminalStateEvaluator",
    "evaluate_terminal_state",
    "apply_temperature",
    "apply_temperature_vectorized",
    "load_league_temperature",
    # Engine
    "simulate",
    "simulate_vectorized",
    "simulate_single_ball",
    "simulate_one_over",
    "get_required_simulations",
    # Betting
    "BetDecision",
    "BettingThresholds",
    "BettingDecision",
    "evaluate_bet",
    "calculate_kelly_stake",
    "calculate_edge",
    "odds_to_implied_prob",
    "implied_prob_to_odds",
]
