"""
Terminal State Evaluator for Monte Carlo Simulation Engine.

Wraps ResourceFeatureCalculator to evaluate win probability at terminal states.
Includes temperature calibration for league-specific adjustments.
Supports optional ML model (Predictor) for more accurate evaluation.
"""

import numpy as np
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from pathlib import Path
import joblib
import structlog

from ..features.calculator import ResourceFeatureCalculator
from ..features.format_config import FormatConfig
from .state import MatchState

# Avoid circular import - only import Predictor and FeatureContext for type hints
if TYPE_CHECKING:
    from ..inference.predictor import Predictor
    from .feature_context import FeatureContext

logger = structlog.get_logger()

# Cache for loaded temperature calibrators
_TEMPERATURE_CACHE: Dict[str, Dict[str, float]] = {}


def apply_temperature(prob: float, temperature: float) -> float:
    """
    Apply temperature scaling to probability.
    
    Temperature < 1.0 = sharper predictions (toward 0/1)
    Temperature > 1.0 = softer predictions (toward 0.5)
    
    Formula: sigmoid(logit(prob) / temperature)
    
    Args:
        prob: Uncalibrated probability (0-1)
        temperature: Temperature parameter
        
    Returns:
        Calibrated probability
        
    Example:
        >>> apply_temperature(0.60, 0.8)
        0.6241...  # logit(0.60)/0.8 = 0.506, sigmoid(0.506) = 0.624
    """
    # Clip to avoid log(0) or log(inf)
    prob = np.clip(prob, 1e-7, 1 - 1e-7)
    
    # Convert to logit
    logit = np.log(prob / (1 - prob))
    
    # Scale by temperature
    scaled_logit = logit / temperature
    
    # Convert back to probability
    calibrated = 1 / (1 + np.exp(-scaled_logit))
    
    return float(calibrated)


def apply_temperature_vectorized(probs: np.ndarray, temperature: float) -> np.ndarray:
    """
    Apply temperature scaling to array of probabilities.
    
    Args:
        probs: Array of probabilities
        temperature: Temperature parameter
        
    Returns:
        Array of calibrated probabilities
    """
    probs = np.clip(probs, 1e-7, 1 - 1e-7)
    logits = np.log(probs / (1 - probs))
    scaled_logits = logits / temperature
    return 1 / (1 + np.exp(-scaled_logits))


def load_league_temperature(
    league: str,
    innings: int,
    model_dir: str = "models/t20_male_v2",
) -> Optional[float]:
    """
    Load temperature for a specific league and innings.
    
    Args:
        league: League code (e.g., 'bbl', 'sa20')
        innings: Innings number (1 or 2)
        model_dir: Path to model directory
        
    Returns:
        Temperature value or None if not found
    """
    cache_key = f"{model_dir}/{league}"
    
    # Check cache first
    if cache_key in _TEMPERATURE_CACHE:
        cached = _TEMPERATURE_CACHE[cache_key]
        return cached.get(f"T{innings}")
    
    # Try to load from calibrator file
    calibrator_path = Path(model_dir) / "league_calibrators" / league / "league_calibrator.pkl"
    
    if not calibrator_path.exists():
        logger.debug("No league calibrator found", league=league, path=str(calibrator_path))
        return None
    
    try:
        calibrator = joblib.load(calibrator_path)
        
        # Extract temperature values
        temps = {}
        for innings_key in (1, 2):
            if hasattr(calibrator, 'calibrators') and innings_key in calibrator.calibrators:
                cal = calibrator.calibrators[innings_key]
                if hasattr(cal, 'temperature'):
                    temps[f"T{innings_key}"] = cal.temperature
        
        _TEMPERATURE_CACHE[cache_key] = temps
        logger.debug("Loaded league temperatures", league=league, temps=temps)
        
        return temps.get(f"T{innings}")
    
    except Exception as e:
        logger.warning("Failed to load league calibrator", league=league, error=str(e))
        return None


class TerminalStateEvaluator:
    """
    Evaluates win probability at terminal simulation states.
    
    Uses ResourceFeatureCalculator for core evaluation (fast, heuristic-based).
    Optionally uses ML Predictor for more accurate evaluation (slower but better).
    Applies league-specific temperature calibration.
    
    Automatically creates FormatConfig-aware calculators for reduced-over matches
    so that par scores, phase thresholds, and RRR calculations are properly scaled.
    """
    
    def __init__(self, model_dir: str = "models/t20_male_v2", predictor: Optional["Predictor"] = None):
        """
        Initialize evaluator.
        
        Args:
            model_dir: Path to model directory for temperature loading
            predictor: Optional Predictor instance for ML-based evaluation.
                      If provided, evaluate_batch_with_model() uses the ML model
                      instead of resource_win_prob heuristic.
        """
        # Default calculator for standard 20-over T20
        self.calculator = ResourceFeatureCalculator()
        # Cache of calculators keyed by total_balls for reduced-over matches
        self._calculator_cache: Dict[int, ResourceFeatureCalculator] = {120: self.calculator}
        self.model_dir = model_dir
        self.predictor = predictor
    
    def _get_calculator(self, total_balls: int) -> ResourceFeatureCalculator:
        """Get or create a FormatConfig-aware calculator for the given total_balls."""
        if total_balls not in self._calculator_cache:
            total_overs = total_balls // 6
            config = FormatConfig.t20_reduced(total_overs)
            self._calculator_cache[total_balls] = ResourceFeatureCalculator(config=config)
        return self._calculator_cache[total_balls]
    
    def evaluate(
        self,
        state: MatchState,
        apply_temp: bool = True,
    ) -> float:
        """
        Evaluate win probability for a single state.
        
        Args:
            state: Match state to evaluate
            apply_temp: Whether to apply temperature calibration
            
        Returns:
            Win probability (0-1)
        """
        # Handle terminal conditions
        if state.innings == 2 and state.target_runs:
            if state.score >= state.target_runs:
                return 1.0  # Target chased
            if state.wickets_lost >= 10 or state.balls_remaining <= 0:
                return 0.0  # All out or overs complete without chasing
        
        if state.innings == 1:
            if state.wickets_lost >= 10 or state.balls_remaining <= 0:
                # First innings complete - probability depends on score
                # Use existing calculator logic
                pass
        
        # Convert balls_remaining to over/ball format
        balls_bowled = state.total_balls - state.balls_remaining
        over = balls_bowled // 6  # 0-indexed over
        ball = balls_bowled % 6  # 0-5, need to convert to 1-6
        if ball == 0 and over > 0:
            # At the start of a new over
            ball = 6
            over -= 1
        elif ball == 0:
            ball = 1  # Very start of match
        
        # Use format-aware calculator (handles reduced-over matches correctly)
        calculator = self._get_calculator(state.total_balls)
        features = calculator.calculate_all_features(
            innings=state.innings,
            over=over,
            ball=ball,
            current_score=state.score,
            wickets_lost=state.wickets_lost,
            target_runs=state.target_runs,
        )
        
        raw_prob = features['resource_win_prob']
        
        # Apply temperature calibration if requested
        if apply_temp:
            temperature = load_league_temperature(
                league=state.league,
                innings=state.innings,
                model_dir=self.model_dir,
            )
            if temperature is not None and temperature != 1.0:
                return apply_temperature(raw_prob, temperature)
        
        return raw_prob
    
    def evaluate_batch(
        self,
        states_data: Dict[str, np.ndarray],
        league: str,
        innings: int,
        apply_temp: bool = True,
    ) -> np.ndarray:
        """
        Evaluate win probability for multiple states (vectorized).
        
        Args:
            states_data: Dictionary with arrays for each state field:
                - scores: (n,) array of scores
                - wickets: (n,) array of wickets lost
                - balls_remaining: (n,) array of balls remaining
                - target_runs: (n,) array of targets (innings 2) or None
            league: League code
            innings: Innings number
            apply_temp: Whether to apply temperature
            
        Returns:
            Array of win probabilities (n,)
        """
        n = len(states_data['scores'])
        probs = np.zeros(n)
        
        scores = states_data['scores']
        wickets = states_data['wickets']
        balls_remaining = states_data['balls_remaining']
        target_runs = states_data.get('target_runs')
        batting_team = states_data.get('batting_team', 'Team A')
        bowling_team = states_data.get('bowling_team', 'Team B')
        venue = states_data.get('venue', '')
        
        # Handle terminal conditions first
        if innings == 2 and target_runs is not None:
            # Target chased
            chased_mask = scores >= target_runs
            probs[chased_mask] = 1.0
            
            # All out or overs complete without chasing
            failed_mask = ((wickets >= 10) | (balls_remaining <= 0)) & ~chased_mask
            probs[failed_mask] = 0.0
            
            # Need to evaluate remaining states
            eval_mask = ~chased_mask & ~failed_mask
        else:
            eval_mask = np.ones(n, dtype=bool)
        
        # Evaluate non-terminal states
        eval_indices = np.where(eval_mask)[0]
        total_balls_val = states_data.get('total_balls', 120)
        
        # Use format-aware calculator for reduced-over matches
        calculator = self._get_calculator(total_balls_val)
        
        for i in eval_indices:
            # Convert balls_remaining to over/ball format
            br = int(balls_remaining[i])
            balls_bowled = total_balls_val - br
            over = balls_bowled // 6
            ball = balls_bowled % 6
            if ball == 0 and over > 0:
                ball = 6
                over -= 1
            elif ball == 0:
                ball = 1
            
            features = calculator.calculate_all_features(
                innings=innings,
                over=over,
                ball=ball,
                current_score=int(scores[i]),
                wickets_lost=int(wickets[i]),
                target_runs=int(target_runs[i]) if target_runs is not None else None,
            )
            probs[i] = features['resource_win_prob']
        
        # Apply temperature calibration
        if apply_temp:
            temperature = load_league_temperature(
                league=league,
                innings=innings,
                model_dir=self.model_dir,
            )
            if temperature is not None and temperature != 1.0:
                # Only apply to evaluated states
                probs[eval_mask] = apply_temperature_vectorized(probs[eval_mask], temperature)
        
        return probs

    def evaluate_batch_with_model(
        self,
        states: List[MatchState],
        feature_context: Optional["FeatureContext"] = None,
        apply_temp: bool = False,
    ) -> np.ndarray:
        """
        Evaluate win probability for multiple states using ML model (batch).
        
        This method uses the Predictor's batch prediction capability for
        accurate ML model-based evaluation. Falls back to resource_win_prob
        if no predictor is available.
        
        Args:
            states: List of MatchState objects to evaluate
            feature_context: Optional FeatureContext with cached venue/team stats.
                If provided, uses real feature store values for terminal state
                evaluation (full mode). If None, falls back to simplified defaults.
            apply_temp: Whether to apply temperature (usually False since
                       predictor handles its own calibration)
            
        Returns:
            Array of win probabilities (n,)
            
        Performance:
            ~100-170ms for 2000 states with ML model + FeatureContext (full)
            ~50-100ms for 2000 states with ML model + defaults (simplified)
            ~60ms for 2000 states with resource_win_prob fallback
        """
        if not states:
            return np.array([])
        
        # Use predictor if available
        if self.predictor is not None:
            # Use the batch prediction method
            predictor_model = getattr(self.predictor, 'model_dir', 'unknown')
            
            # Determine calibration type being used
            calibration_type = "raw"
            if hasattr(self.predictor, 'per_over_calibrators') and self.predictor.per_over_calibrators:
                calibration_type = f"per_over_brier_optimized ({len(self.predictor.per_over_calibrators)} calibrators)"
            elif hasattr(self.predictor, 'phase_calibrators') and self.predictor.phase_calibrators:
                calibration_type = f"phase_isotonic ({len(self.predictor.phase_calibrators)} calibrators)"
            elif hasattr(self.predictor, 'calibrator_inn1') and self.predictor.calibrator_inn1:
                calibration_type = "innings_specific (2 calibrators)"
            elif hasattr(self.predictor, 'calibrator') and self.predictor.calibrator:
                calibration_type = "combined (1 calibrator)"
            
            has_league = hasattr(self.predictor, 'league_calibrator') and self.predictor.league_calibrator
            feature_mode = "full" if feature_context else "simplified"
            
            league = states[0].league if states and hasattr(states[0], 'league') else None
            logger.debug(
                "MC terminal eval using ML predictor",
                predictor_model_dir=predictor_model,
                n_states=len(states),
                calibration=calibration_type,
                league_calibration=has_league,
                feature_mode=feature_mode,
                league_param=league,
            )
            return self.predictor.predict_batch(states, feature_context=feature_context, league=league)
        
        # Fallback to resource_win_prob evaluation (loop)
        logger.warning(
            "MC terminal eval using RESOURCE FALLBACK (no predictor)",
            n_states=len(states),
            method="resource_win_prob",
        )
        n = len(states)
        probs = np.zeros(n)
        
        for i, state in enumerate(states):
            probs[i] = self.evaluate(state, apply_temp=apply_temp)
        
        return probs


# Convenience function
def evaluate_terminal_state(
    state: MatchState,
    apply_temp: bool = True,
    model_dir: str = "models/t20_male_v2",
) -> float:
    """
    Evaluate win probability for a terminal simulation state.
    
    Args:
        state: Match state to evaluate
        apply_temp: Whether to apply temperature calibration
        model_dir: Path to model directory
        
    Returns:
        Win probability (0-1)
    """
    evaluator = TerminalStateEvaluator(model_dir=model_dir)
    return evaluator.evaluate(state, apply_temp=apply_temp)
