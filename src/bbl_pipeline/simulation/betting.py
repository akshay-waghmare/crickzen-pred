"""
Betting Decision Support for Monte Carlo Simulation Engine.

Provides phase-aware bet evaluation with Kelly criterion and edge thresholds.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
import numpy as np

from .config import get_phase, EDGE_MIN_BY_PHASE, SIGMA_MAX_BY_PHASE
from .state import SimulationResult


class BetDecision(Enum):
    """Betting decision outcomes."""
    BET = "BET"
    NO_BET = "NO_BET"
    SKIP = "SKIP"  # Uncertainty too high


@dataclass
class BettingThresholds:
    """
    Phase-aware betting thresholds.
    
    Different phases have different edge requirements due to
    varying prediction confidence:
    - Death overs: Higher edge required (8.60% wicket rate, more volatile)
    - Powerplay: Medium edge (4.40% wicket rate)
    - Middle overs: Lower edge acceptable (most stable)
    """
    edge_min_powerplay: float = 0.04  # 4%
    edge_min_middle: float = 0.03  # 3%
    edge_min_death: float = 0.06  # 6%
    sigma_max_powerplay: float = 0.06
    sigma_max_middle: float = 0.05
    sigma_max_death: float = 0.08
    kelly_fraction: float = 0.25  # Quarter Kelly for safety
    
    def get_edge_min(self, phase: str) -> float:
        """Get minimum edge for phase."""
        return {
            'powerplay': self.edge_min_powerplay,
            'middle': self.edge_min_middle,
            'death': self.edge_min_death,
        }.get(phase, self.edge_min_middle)
    
    def get_sigma_max(self, phase: str) -> float:
        """Get maximum sigma for phase."""
        return {
            'powerplay': self.sigma_max_powerplay,
            'middle': self.sigma_max_middle,
            'death': self.sigma_max_death,
        }.get(phase, self.sigma_max_middle)


@dataclass
class BettingDecision:
    """
    Complete betting decision with rationale.
    
    Attributes:
        decision: BET, NO_BET, or SKIP
        edge: Calculated edge (model_prob - implied_prob)
        kelly_stake: Recommended stake as fraction of bankroll
        confidence: Confidence in the decision (1 - σ/σ_max)
        phase: Current game phase
        rationale: Human-readable explanation
    """
    decision: BetDecision
    edge: float
    kelly_stake: float
    confidence: float
    phase: str
    rationale: str
    
    # Metadata
    model_prob: float = 0.0
    market_odds: float = 0.0
    implied_prob: float = 0.0
    sigma: float = 0.0
    
    @property
    def is_bet(self) -> bool:
        return self.decision == BetDecision.BET
    
    def to_dict(self) -> dict:
        return {
            'decision': self.decision.value,
            'edge': self.edge,
            'kelly_stake': self.kelly_stake,
            'confidence': self.confidence,
            'phase': self.phase,
            'rationale': self.rationale,
            'model_prob': self.model_prob,
            'market_odds': self.market_odds,
            'implied_prob': self.implied_prob,
            'sigma': self.sigma,
        }


def odds_to_implied_prob(odds: float) -> float:
    """
    Convert decimal odds to implied probability.
    
    Args:
        odds: Decimal odds (e.g., 2.0 for even money)
        
    Returns:
        Implied probability (0-1)
        
    Examples:
        >>> odds_to_implied_prob(2.0)  # Even money
        0.5
        >>> odds_to_implied_prob(1.5)  # Short odds
        0.6666...
        >>> odds_to_implied_prob(3.0)  # Longer odds
        0.3333...
    """
    if odds <= 1.0:
        raise ValueError(f"Decimal odds must be > 1.0, got {odds}")
    return 1.0 / odds


def implied_prob_to_odds(prob: float) -> float:
    """
    Convert implied probability to decimal odds.
    
    Args:
        prob: Probability (0-1)
        
    Returns:
        Decimal odds
    """
    if prob <= 0 or prob >= 1:
        raise ValueError(f"Probability must be in (0, 1), got {prob}")
    return 1.0 / prob


def calculate_edge(model_prob: float, implied_prob: float) -> float:
    """
    Calculate betting edge.
    
    Args:
        model_prob: Model's probability estimate
        implied_prob: Market implied probability
        
    Returns:
        Edge (positive = value bet)
    """
    return model_prob - implied_prob


def calculate_kelly_stake(
    model_prob: float,
    odds: float,
    fraction: float = 0.25,
) -> float:
    """
    Calculate Kelly criterion stake.
    
    Formula: f* = (bp - q) / b
    Where:
        b = odds - 1 (net payout per unit staked)
        p = model probability of winning
        q = 1 - p (probability of losing)
    
    Args:
        model_prob: Model's probability of winning
        odds: Decimal odds offered
        fraction: Kelly fraction (0.25 = quarter Kelly)
        
    Returns:
        Recommended stake as fraction of bankroll (0 to 1)
    """
    if odds <= 1.0:
        return 0.0
    
    b = odds - 1  # Net payout per unit
    p = model_prob
    q = 1 - p
    
    # Kelly formula
    kelly = (b * p - q) / b
    
    # Apply fractional Kelly for safety
    kelly *= fraction
    
    # Clamp to reasonable bounds
    return max(0.0, min(kelly, 0.10))  # Max 10% stake


def evaluate_bet(
    simulation_result: SimulationResult,
    market_odds: float,
    balls_remaining: int,
    thresholds: Optional[BettingThresholds] = None,
    model_prob: Optional[float] = None,
) -> BettingDecision:
    """
    Evaluate whether to bet based on simulation result and market odds.
    
    Args:
        simulation_result: Result from Monte Carlo simulation (provides uncertainty σ)
        market_odds: Decimal odds offered by market
        balls_remaining: Balls remaining in match (for phase detection)
        thresholds: Betting thresholds (uses defaults if None)
        model_prob: If provided, use this league-calibrated model probability for
                   edge calculation instead of simulation_result.mean_prob.
                   This is RECOMMENDED for betting decisions as it uses the 
                   trained ML model with league-specific calibration.
                   Monte Carlo mean_prob uses resource_win_prob heuristic.
        
    Returns:
        BettingDecision with full rationale
        
    Note:
        For betting, you should pass the league-calibrated model probability:
        
        >>> model_prob = predictor.predict(match_state)  # League-calibrated
        >>> sim_result = simulate(state, horizon=6)  # For uncertainty (σ)
        >>> decision = evaluate_bet(sim_result, odds, balls, model_prob=model_prob)
    """
    if thresholds is None:
        thresholds = BettingThresholds()
    
    # Determine phase
    phase = get_phase(balls_remaining)
    
    # Get phase-specific thresholds
    edge_min = thresholds.get_edge_min(phase)
    sigma_max = thresholds.get_sigma_max(phase)
    
    # Extract values
    # Use provided model_prob (league-calibrated) if given, otherwise fall back to simulation mean
    # For betting, model_prob should be the league-calibrated ML model output
    # simulation_result.mean_prob uses resource_win_prob heuristic which is less accurate
    prob_for_edge = model_prob if model_prob is not None else simulation_result.mean_prob
    sigma = simulation_result.std_prob  # Always use Monte Carlo for uncertainty estimation
    
    # Calculate market implied probability
    implied_prob = odds_to_implied_prob(market_odds)
    
    # Calculate edge using league-calibrated probability
    edge = calculate_edge(prob_for_edge, implied_prob)
    
    # Calculate confidence
    confidence = max(0.0, 1.0 - sigma / sigma_max)
    
    # Decision logic
    if sigma > sigma_max:
        decision = BetDecision.SKIP
        kelly_stake = 0.0
        rationale = (
            f"Uncertainty too high: σ={sigma:.4f} > max {sigma_max:.2f} for {phase}. "
            "Wait for more stable conditions."
        )
    elif edge < edge_min:
        decision = BetDecision.NO_BET
        kelly_stake = 0.0
        if edge > 0:
            rationale = (
                f"Positive edge {edge:.2%} below {phase} threshold {edge_min:.0%}. "
                "Insufficient value."
            )
        else:
            rationale = (
                f"Negative edge {edge:.2%}. Market odds imply higher probability than model."
            )
    else:
        decision = BetDecision.BET
        kelly_stake = calculate_kelly_stake(
            model_prob=prob_for_edge,
            odds=market_odds,
            fraction=thresholds.kelly_fraction,
        )
        rationale = (
            f"Value bet found: edge {edge:.2%} >= {edge_min:.0%} ({phase}). "
            f"Model: {prob_for_edge:.1%}, Market: {implied_prob:.1%}. "
            f"Kelly stake: {kelly_stake:.2%}"
        )
    
    return BettingDecision(
        decision=decision,
        edge=edge,
        kelly_stake=kelly_stake,
        confidence=confidence,
        phase=phase,
        rationale=rationale,
        model_prob=prob_for_edge,
        market_odds=market_odds,
        implied_prob=implied_prob,
        sigma=sigma,
    )


def evaluate_over_under(
    current_score: int,
    balls_remaining: int,
    line: float,
    over_odds: float,
    under_odds: float,
    simulated_scores: np.ndarray,
    thresholds: Optional[BettingThresholds] = None,
) -> Tuple[Optional[BettingDecision], Optional[BettingDecision]]:
    """
    Evaluate over/under total bet.
    
    Args:
        current_score: Current team score
        balls_remaining: Balls remaining
        line: Over/under line (e.g., 165.5)
        over_odds: Decimal odds for over
        under_odds: Decimal odds for under
        simulated_scores: Array of simulated final scores
        thresholds: Betting thresholds
        
    Returns:
        Tuple of (over_decision, under_decision)
    """
    if thresholds is None:
        thresholds = BettingThresholds()
    
    # Calculate probabilities
    over_prob = (simulated_scores > line).mean()
    under_prob = (simulated_scores <= line).mean()
    
    # Calculate std dev as uncertainty proxy
    score_std = simulated_scores.std()
    # Convert to probability uncertainty (rough approximation)
    prob_std = score_std / (simulated_scores.max() - simulated_scores.min() + 1)
    
    phase = get_phase(balls_remaining)
    edge_min = thresholds.get_edge_min(phase)
    sigma_max = thresholds.get_sigma_max(phase)
    
    # Create mock simulation results
    over_result = SimulationResult(
        mean=over_prob,
        std=prob_std,
        p5=np.percentile([over_prob], 5),
        p50=over_prob,
        p95=np.percentile([over_prob], 95),
        ci_low=max(0, over_prob - 1.96 * prob_std),
        ci_high=min(1, over_prob + 1.96 * prob_std),
        n_simulations=len(simulated_scores),
        horizon=balls_remaining,
        elapsed_ms=0,
    )
    
    under_result = SimulationResult(
        mean=under_prob,
        std=prob_std,
        p5=np.percentile([under_prob], 5),
        p50=under_prob,
        p95=np.percentile([under_prob], 95),
        ci_low=max(0, under_prob - 1.96 * prob_std),
        ci_high=min(1, under_prob + 1.96 * prob_std),
        n_simulations=len(simulated_scores),
        horizon=balls_remaining,
        elapsed_ms=0,
    )
    
    over_decision = evaluate_bet(over_result, over_odds, balls_remaining, thresholds)
    under_decision = evaluate_bet(under_result, under_odds, balls_remaining, thresholds)
    
    return over_decision, under_decision
