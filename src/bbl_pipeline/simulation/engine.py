"""
Monte Carlo Simulation Engine for T20 Win Probability.

Provides single-ball and multi-ball simulation with uncertainty quantification.
"""

import numpy as np
from typing import Optional, Tuple, List
import structlog
import time

from .config import get_phase, EDGE_MIN_BY_PHASE, SIGMA_MAX_BY_PHASE
from .state import MatchState, SimulationResult
from .sampler import NextBallSampler
from .evaluator import TerminalStateEvaluator, apply_temperature, load_league_temperature

logger = structlog.get_logger()


def simulate(
    state: MatchState,
    horizon: int = 1,
    n_simulations: int = 1000,
    apply_temp: bool = True,
    model_dir: str = "models/t20_male_v1",
) -> SimulationResult:
    """
    Run Monte Carlo simulation from current state.
    
    Args:
        state: Current match state
        horizon: Number of balls to simulate (1, 6, 12, etc.)
        n_simulations: Number of Monte Carlo paths
        apply_temp: Whether to apply league temperature calibration
        model_dir: Path to model directory
        
    Returns:
        SimulationResult with mean, std, percentiles, confidence interval
        
    Examples:
        >>> # 1-ball simulation
        >>> result = simulate(state, horizon=1, n_simulations=1000)
        >>> print(f"Win prob: {result.mean:.1%} ± {result.std:.1%}")
        
        >>> # 1-over (6 balls) simulation
        >>> result = simulate(state, horizon=6, n_simulations=5000)
        >>> print(f"90% CI: [{result.ci_low:.1%}, {result.ci_high:.1%}]")
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if n_simulations < 100:
        raise ValueError("n_simulations must be >= 100 for reliable estimates")
    
    start_time = time.time()
    
    sampler = NextBallSampler()
    evaluator = TerminalStateEvaluator(model_dir=model_dir)
    
    # Get league temperature once for efficiency
    temperature = None
    if apply_temp:
        temperature = load_league_temperature(
            league=state.league,
            innings=state.innings,
            model_dir=model_dir,
        )
    
    # Storage for terminal probabilities
    terminal_probs = np.zeros(n_simulations)
    
    # Run simulations
    for i in range(n_simulations):
        # Copy state for this simulation path
        sim_state = state.copy()
        
        # Simulate horizon balls
        for _ in range(horizon):
            if sim_state.is_over:
                break
            
            # Sample next ball outcome
            runs, is_wicket = sampler.sample(sim_state)
            
            # Apply outcome to state
            sim_state = sim_state.apply_outcome(runs=runs, is_wicket=is_wicket)
        
        # Evaluate terminal state
        prob = evaluator.evaluate(sim_state, apply_temp=False)
        
        # Apply temperature if provided
        if temperature is not None and temperature != 1.0:
            prob = apply_temperature(prob, temperature)
        
        terminal_probs[i] = prob
    
    elapsed = time.time() - start_time
    
    result = SimulationResult.from_probs(
        probs=terminal_probs,
        horizon_balls=horizon,
        time_taken_ms=elapsed * 1000,
        league=state.league,
        temperature=temperature,
    )
    
    logger.debug(
        "Simulation complete",
        horizon=horizon,
        n_simulations=n_simulations,
        mean=f"{result.mean_prob:.4f}",
        std=f"{result.std_prob:.4f}",
        elapsed_ms=f"{elapsed * 1000:.1f}",
    )
    
    return result


def simulate_vectorized(
    state: MatchState,
    horizon: int = 1,
    n_simulations: int = 1000,
    apply_temp: bool = True,
    model_dir: str = "models/t20_male_v1",
) -> SimulationResult:
    """
    Run Monte Carlo simulation with vectorized sampling.
    
    More efficient for larger simulation counts by batch-sampling outcomes.
    Falls back to sequential evaluation for terminal states.
    
    Args:
        state: Current match state
        horizon: Number of balls to simulate (1, 6, 12, etc.)
        n_simulations: Number of Monte Carlo paths
        apply_temp: Whether to apply league temperature calibration
        model_dir: Path to model directory
        
    Returns:
        SimulationResult with statistics
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if n_simulations < 100:
        raise ValueError("n_simulations must be >= 100 for reliable estimates")
    
    start_time = time.time()
    
    sampler = NextBallSampler()
    evaluator = TerminalStateEvaluator(model_dir=model_dir)
    
    # Get league temperature once
    temperature = None
    if apply_temp:
        temperature = load_league_temperature(
            league=state.league,
            innings=state.innings,
            model_dir=model_dir,
        )
    
    # Initialize state arrays
    scores = np.full(n_simulations, state.score, dtype=np.int32)
    wickets = np.full(n_simulations, state.wickets_lost, dtype=np.int32)
    balls_remaining = np.full(n_simulations, state.balls_remaining, dtype=np.int32)
    is_over = np.zeros(n_simulations, dtype=bool)
    
    # Simulate horizon balls
    for ball in range(horizon):
        # Find active (non-terminal) simulations
        active_mask = ~is_over & (balls_remaining > 0) & (wickets < 10)
        
        if state.innings == 2 and state.target_runs:
            # Check for chased target
            chased = scores >= state.target_runs
            is_over |= chased
            active_mask &= ~chased
        
        n_active = active_mask.sum()
        if n_active == 0:
            break
        
        # Get phases for active simulations
        phases = np.array([get_phase(br) for br in balls_remaining[active_mask]])
        active_wickets = wickets[active_mask]
        
        # Sample outcomes for all active simulations
        runs_arr, wicket_arr = sampler.sample_vectorized(
            phases=phases,
            wickets=active_wickets,
            n=n_active,
        )
        
        # Apply outcomes
        scores[active_mask] += runs_arr
        balls_remaining[active_mask] -= 1
        wickets[active_mask] += wicket_arr.astype(np.int32)
        
        # Update terminal conditions
        is_over |= (wickets >= 10) | (balls_remaining <= 0)
        
        if state.innings == 2 and state.target_runs:
            is_over |= scores >= state.target_runs
    
    # Evaluate terminal states
    terminal_probs = np.zeros(n_simulations)
    
    for i in range(n_simulations):
        # Create state for evaluation
        eval_state = MatchState(
            innings=state.innings,
            score=int(scores[i]),
            wickets_lost=int(wickets[i]),
            balls_remaining=int(balls_remaining[i]),
            target_runs=state.target_runs,
            batting_team=state.batting_team,
            bowling_team=state.bowling_team,
            venue=state.venue,
            league=state.league,
        )
        
        terminal_probs[i] = evaluator.evaluate(eval_state, apply_temp=False)
    
    # Apply temperature calibration
    if temperature is not None and temperature != 1.0:
        from .evaluator import apply_temperature_vectorized
        terminal_probs = apply_temperature_vectorized(terminal_probs, temperature)
    
    elapsed = time.time() - start_time
    
    result = SimulationResult.from_probs(
        probs=terminal_probs,
        horizon_balls=horizon,
        time_taken_ms=elapsed * 1000,
        league=state.league,
        temperature=temperature,
    )
    
    logger.debug(
        "Vectorized simulation complete",
        horizon=horizon,
        n_simulations=n_simulations,
        mean=f"{result.mean_prob:.4f}",
        std=f"{result.std_prob:.4f}",
        elapsed_ms=f"{elapsed * 1000:.1f}",
    )
    
    return result


def simulate_single_ball(
    state: MatchState,
    n_simulations: int = 1000,
    apply_temp: bool = True,
    model_dir: str = "models/t20_male_v1",
) -> SimulationResult:
    """
    Convenience function for 1-ball simulation.
    
    Optimized for single-ball case with lower default simulation count.
    
    Args:
        state: Current match state
        n_simulations: Number of simulations
        apply_temp: Whether to apply temperature
        model_dir: Path to model directory
        
    Returns:
        SimulationResult
    """
    return simulate(
        state=state,
        horizon=1,
        n_simulations=n_simulations,
        apply_temp=apply_temp,
        model_dir=model_dir,
    )


def simulate_one_over(
    state: MatchState,
    n_simulations: int = 5000,
    apply_temp: bool = True,
    model_dir: str = "models/t20_male_v1",
) -> SimulationResult:
    """
    Convenience function for 6-ball (one over) simulation.
    
    Uses higher default simulation count for more stable estimates.
    
    Args:
        state: Current match state
        n_simulations: Number of simulations
        apply_temp: Whether to apply temperature
        model_dir: Path to model directory
        
    Returns:
        SimulationResult
    """
    return simulate_vectorized(
        state=state,
        horizon=6,
        n_simulations=n_simulations,
        apply_temp=apply_temp,
        model_dir=model_dir,
    )


def calculate_simulation_uncertainty(
    result: SimulationResult,
    phase: str,
) -> Tuple[bool, str]:
    """
    Assess whether simulation uncertainty is within acceptable bounds.
    
    Args:
        result: SimulationResult from simulation
        phase: Current game phase ('powerplay', 'middle', 'death')
        
    Returns:
        Tuple of (is_acceptable, message)
    """
    sigma_max = SIGMA_MAX_BY_PHASE.get(phase, 0.08)
    
    if result.std <= sigma_max:
        return True, f"Uncertainty σ={result.std:.4f} within bounds (max {sigma_max:.2f})"
    else:
        return False, f"Uncertainty σ={result.std:.4f} exceeds max {sigma_max:.2f}"


def get_required_simulations(horizon: int, precision: float = 0.01) -> int:
    """
    Calculate required number of simulations for desired precision.
    
    Uses standard error formula: SE = σ / √n
    
    Args:
        horizon: Simulation horizon in balls
        precision: Desired precision (default 1% = 0.01)
        
    Returns:
        Recommended number of simulations
    """
    # Estimate expected standard deviation based on horizon
    # Longer horizons have higher variance
    if horizon <= 1:
        expected_std = 0.05
    elif horizon <= 6:
        expected_std = 0.10
    elif horizon <= 12:
        expected_std = 0.15
    else:
        expected_std = 0.20
    
    # Required n for SE <= precision: n >= (σ/precision)²
    required_n = int((expected_std / precision) ** 2)
    
    # Apply reasonable bounds
    return max(500, min(required_n, 50000))
