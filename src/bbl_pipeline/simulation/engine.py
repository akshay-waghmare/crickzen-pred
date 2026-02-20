"""
Monte Carlo Simulation Engine for T20 Win Probability.

Provides single-ball and multi-ball simulation with uncertainty quantification.
Supports optional ML model (Predictor) for accurate terminal state evaluation.
"""

import numpy as np
from typing import Optional, Tuple, List, TYPE_CHECKING
import structlog
import time

from .config import get_phase, EDGE_MIN_BY_PHASE, SIGMA_MAX_BY_PHASE
from .state import MatchState, SimulationResult
from .sampler import NextBallSampler
from .evaluator import TerminalStateEvaluator, apply_temperature, load_league_temperature
from .feature_context import FeatureContext

# Avoid circular import
if TYPE_CHECKING:
    from ..inference.predictor import Predictor

logger = structlog.get_logger()


def simulate(
    state: MatchState,
    horizon: int = 1,
    n_simulations: int = 1000,
    apply_temp: bool = True,
    model_dir: str = "models/t20_male_v2",
    predictor: "Predictor" = None,
) -> SimulationResult:
    """
    Run Monte Carlo simulation from current state.
    
    Args:
        state: Current match state
        horizon: Number of balls to simulate (1, 6, 12, etc.)
        n_simulations: Number of Monte Carlo paths
        apply_temp: Whether to apply league temperature calibration
        model_dir: Path to model directory
        predictor: Optional Predictor instance for ML-based evaluation.
                  If provided, uses batch ML prediction for terminal states
                  (more accurate, ~400-800ms for 2000 sims).
        
    Returns:
        SimulationResult with mean, std, percentiles, confidence interval
        
    Examples:
        >>> # 1-ball simulation (fast, resource_win_prob)
        >>> result = simulate(state, horizon=1, n_simulations=1000)
        >>> print(f"Win prob: {result.mean:.1%} ± {result.std:.1%}")
        
        >>> # 1-over (6 balls) simulation with ML model
        >>> from bbl_pipeline.inference.predictor import Predictor
        >>> predictor = Predictor.load("models/t20_male_v2", league="bbl")
        >>> result = simulate(state, horizon=6, n_simulations=5000, predictor=predictor)
        >>> print(f"90% CI: [{result.ci_low:.1%}, {result.ci_high:.1%}]")
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if n_simulations < 100:
        raise ValueError("n_simulations must be >= 100 for reliable estimates")
    
    start_time = time.time()
    
    # Pass league to sampler for league-specific distributions
    league = state.league if hasattr(state, 'league') else None
    sampler = NextBallSampler(league=league, model_dir=model_dir)
    evaluator = TerminalStateEvaluator(model_dir=model_dir, predictor=predictor)
    
    # If using ML model, don't apply temperature separately (predictor handles calibration)
    use_ml_model = predictor is not None
    
    # Log which model is being used for simulation
    if use_ml_model:
        predictor_source = getattr(predictor, 'model_dir', 'unknown')
        logger.debug(
            "Using ML model for Monte Carlo evaluation",
            predictor_model_dir=predictor_source,
            fallback_model_dir=model_dir,
        )
    
    # Get league temperature once for efficiency (only needed if not using ML model)
    temperature = None
    if apply_temp and not use_ml_model:
        temperature = load_league_temperature(
            league=state.league,
            innings=state.innings,
            model_dir=model_dir,
        )
    
    # Storage for terminal states and probabilities
    terminal_states = []
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
        
        if use_ml_model:
            # Collect states for batch evaluation
            terminal_states.append(sim_state)
        else:
            # Evaluate terminal state immediately
            prob = evaluator.evaluate(sim_state, apply_temp=False)
            
            # Apply temperature if provided
            if temperature is not None and temperature != 1.0:
                prob = apply_temperature(prob, temperature)
            
            terminal_probs[i] = prob
    
    # Batch evaluation for ML model
    if use_ml_model and terminal_states:
        # Build FeatureContext once for all terminal states (amortizes feature store lookups)
        feature_context = None
        try:
            feature_context = predictor.build_feature_context(
                batting_team=state.batting_team,
                bowling_team=state.bowling_team,
                venue=state.venue,
                league=state.league,
                innings=state.innings
            )
            logger.debug(
                "Built FeatureContext for MC terminal evaluation",
                feature_mode="full",
                venue_avg_score=feature_context.venue_avg_score,
                team_a_wr=feature_context.team_a_wr,
            )
        except (KeyError, AttributeError) as e:
            logger.warning(
                "FeatureContext build failed, using simplified features",
                error=str(e),
                venue=state.venue,
                batting_team=state.batting_team,
                bowling_team=state.bowling_team,
                feature_mode="simplified",
            )
            feature_context = None
        
        terminal_probs = evaluator.evaluate_batch_with_model(
            terminal_states, 
            feature_context=feature_context,
            apply_temp=False
        )
        # Track feature mode for result
        _feature_mode = "full" if feature_context else "simplified"
    
    elapsed = time.time() - start_time
    
    # Determine feature mode for result
    if use_ml_model:
        sim_feature_mode = _feature_mode
    else:
        sim_feature_mode = None  # Not applicable for resource_win_prob
    
    result = SimulationResult.from_probs(
        probs=terminal_probs,
        horizon_balls=horizon,
        time_taken_ms=elapsed * 1000,
        league=state.league,
        temperature=temperature if not use_ml_model else None,
        feature_mode=sim_feature_mode,
    )
    
    # Get model source info for logging
    predictor_model_dir = None
    if use_ml_model and predictor is not None:
        # Try to get model_dir from predictor if available
        predictor_model_dir = getattr(predictor, 'model_dir', None)
    
    logger.debug(
        "Simulation complete",
        horizon=horizon,
        n_simulations=n_simulations,
        mean=f"{result.mean_prob:.4f}",
        std=f"{result.std_prob:.4f}",
        elapsed_ms=f"{elapsed * 1000:.1f}",
        use_ml_model=use_ml_model,
        ml_model_source=predictor_model_dir if use_ml_model else None,
    )
    
    return result


def simulate_vectorized(
    state: MatchState,
    horizon: int = 1,
    n_simulations: int = 1000,
    apply_temp: bool = True,
    model_dir: str = "models/t20_male_v2",
    predictor: "Predictor" = None,
) -> SimulationResult:
    """
    Run Monte Carlo simulation with vectorized sampling.
    
    More efficient for larger simulation counts by batch-sampling outcomes.
    
    When a predictor is provided, uses ML model for terminal state evaluation
    (more accurate, ~400-800ms). Otherwise falls back to resource_win_prob 
    heuristic (faster, ~60ms).
    
    Args:
        state: Current match state
        horizon: Number of balls to simulate (1, 6, 12, etc.)
        n_simulations: Number of Monte Carlo paths
        apply_temp: Whether to apply league temperature calibration
        model_dir: Path to model directory
        predictor: Optional Predictor instance for ML-based evaluation.
                  If provided, uses batch ML prediction for terminal states.
        
    Returns:
        SimulationResult with statistics
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if n_simulations < 100:
        raise ValueError("n_simulations must be >= 100 for reliable estimates")
    
    start_time = time.time()
    
    # Pass league to sampler for league-specific distributions
    league = state.league if hasattr(state, 'league') else None
    sampler = NextBallSampler(league=league, model_dir=model_dir)
    evaluator = TerminalStateEvaluator(model_dir=model_dir, predictor=predictor)
    
    # If using ML model, don't apply temperature separately (predictor handles calibration)
    use_ml_model = predictor is not None
    
    # Get league temperature once (only needed if not using ML model)
    temperature = None
    if apply_temp and not use_ml_model:
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
    
    if use_ml_model:
        # Use batch ML model evaluation for all terminal states
        terminal_states = []
        for i in range(n_simulations):
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
            terminal_states.append(eval_state)
        
        # Build FeatureContext once for all terminal states (amortizes feature store lookups)
        feature_context = None
        try:
            feature_context = predictor.build_feature_context(
                batting_team=state.batting_team,
                bowling_team=state.bowling_team,
                venue=state.venue,
                league=state.league,
                innings=state.innings
            )
            logger.debug(
                "Built FeatureContext for MC vectorized evaluation",
                feature_mode="full",
                venue_avg_score=feature_context.venue_avg_score,
                team_a_wr=feature_context.team_a_wr,
            )
        except (KeyError, AttributeError) as e:
            logger.warning(
                "FeatureContext build failed, using simplified features",
                error=str(e),
                venue=state.venue,
                batting_team=state.batting_team,
                bowling_team=state.bowling_team,
                feature_mode="simplified",
            )
            feature_context = None
        
        # Batch prediction (ML model with calibration + FeatureContext)
        terminal_probs = evaluator.evaluate_batch_with_model(
            terminal_states, 
            feature_context=feature_context,
            apply_temp=False
        )
        # Track feature mode for result
        vec_feature_mode = "full" if feature_context else "simplified"
    else:
        # Use resource_win_prob heuristic (faster)
        vec_feature_mode = None  # Not applicable for resource_win_prob
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
    
    # Apply temperature calibration (only if not using ML model)
    if not use_ml_model and temperature is not None and temperature != 1.0:
        from .evaluator import apply_temperature_vectorized
        terminal_probs = apply_temperature_vectorized(terminal_probs, temperature)
    
    elapsed = time.time() - start_time
    
    result = SimulationResult.from_probs(
        probs=terminal_probs,
        horizon_balls=horizon,
        time_taken_ms=elapsed * 1000,
        league=state.league,
        temperature=temperature if not use_ml_model else None,
        feature_mode=vec_feature_mode,
    )
    
    # Get model source info for logging
    predictor_model_dir = None
    if use_ml_model and predictor is not None:
        predictor_model_dir = getattr(predictor, 'model_dir', None)
    
    logger.debug(
        "Vectorized simulation complete",
        horizon=horizon,
        n_simulations=n_simulations,
        mean=f"{result.mean_prob:.4f}",
        std=f"{result.std_prob:.4f}",
        elapsed_ms=f"{elapsed * 1000:.1f}",
        use_ml_model=use_ml_model,
        ml_model_source=predictor_model_dir if use_ml_model else None,
    )
    
    return result


def simulate_single_ball(
    state: MatchState,
    n_simulations: int = 1000,
    apply_temp: bool = True,
    model_dir: str = "models/t20_male_v2",
    predictor: "Predictor" = None,
) -> SimulationResult:
    """
    Convenience function for 1-ball simulation.
    
    Optimized for single-ball case with lower default simulation count.
    
    Args:
        state: Current match state
        n_simulations: Number of simulations
        apply_temp: Whether to apply temperature
        model_dir: Path to model directory
        predictor: Optional Predictor instance for ML-based evaluation.
                  If provided, uses batch ML prediction for terminal states.
        
    Returns:
        SimulationResult
    """
    return simulate(
        state=state,
        horizon=1,
        n_simulations=n_simulations,
        apply_temp=apply_temp,
        model_dir=model_dir,
        predictor=predictor,
    )


def simulate_one_over(
    state: MatchState,
    n_simulations: int = 5000,
    apply_temp: bool = True,
    model_dir: str = "models/t20_male_v2",
    predictor: "Predictor" = None,
) -> SimulationResult:
    """
    Convenience function for 6-ball (one over) simulation.
    
    Uses higher default simulation count for more stable estimates.
    
    Args:
        state: Current match state
        n_simulations: Number of simulations
        apply_temp: Whether to apply temperature
        model_dir: Path to model directory
        predictor: Optional Predictor instance for ML-based evaluation.
                  If provided, uses batch ML prediction for terminal states.
        
    Returns:
        SimulationResult
    """
    return simulate_vectorized(
        state=state,
        horizon=6,
        n_simulations=n_simulations,
        apply_temp=apply_temp,
        model_dir=model_dir,
        predictor=predictor,
    )


def simulate_two_overs(
    state: MatchState,
    n_simulations: int = 5000,
    apply_temp: bool = True,
    model_dir: str = "models/t20_male_v2",
    predictor: "Predictor" = None,
) -> SimulationResult:
    """
    Convenience function for 12-ball (two over) simulation.
    
    Uses higher default simulation count for more stable estimates.
    
    Args:
        state: Current match state
        n_simulations: Number of simulations
        apply_temp: Whether to apply temperature
        model_dir: Path to model directory
        predictor: Optional Predictor instance for ML-based evaluation.
                  If provided, uses batch ML prediction for terminal states.
        
    Returns:
        SimulationResult
    """
    return simulate_vectorized(
        state=state,
        horizon=12,
        n_simulations=n_simulations,
        apply_temp=apply_temp,
        model_dir=model_dir,
        predictor=predictor,
    )


def simulate_five_overs(
    state: MatchState,
    n_simulations: int = 5000,
    apply_temp: bool = True,
    model_dir: str = "models/t20_male_v2",
    predictor: "Predictor" = None,
) -> SimulationResult:
    """
    Convenience function for 30-ball (five over) simulation.
    
    Useful for first innings uncertainty quantification where predictions
    are less stable. Uses higher default simulation count for more stable estimates.
    
    Args:
        state: Current match state
        n_simulations: Number of simulations
        apply_temp: Whether to apply temperature
        model_dir: Path to model directory
        predictor: Optional Predictor instance for ML-based evaluation.
                  If provided, uses batch ML prediction for terminal states.
        
    Returns:
        SimulationResult
    """
    return simulate_vectorized(
        state=state,
        horizon=30,
        n_simulations=n_simulations,
        apply_temp=apply_temp,
        model_dir=model_dir,
        predictor=predictor,
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
