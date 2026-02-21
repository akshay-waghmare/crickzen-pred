"""
State classes for Monte Carlo Simulation Engine.

Contains MatchState and SimulationResult dataclasses per data-model.md.
"""

from dataclasses import dataclass, field
from typing import Optional, List
import numpy as np

from .config import get_phase


@dataclass
class MatchState:
    """
    Current match situation for simulation.
    
    Attributes:
        innings: 1 (batting first) or 2 (chasing)
        score: Current runs scored (0+)
        wickets_lost: Wickets lost (0-10)
        balls_remaining: Balls remaining in innings (0-total_balls)
        total_balls: Total balls in innings (6-120, default 120 for T20)
        target_runs: Target to chase (required if innings=2)
        league: League code for temperature calibration
        batting_team: Canonical batting team name
        bowling_team: Canonical bowling team name
        venue: Venue name (optional)
        batting_team_win_rate: Win rate of batting team (0-1, default 0.5)
        bowling_team_win_rate: Win rate of bowling team (0-1, default 0.5)
        batting_team_situation_wr: Situational win rate for batting team
        bowling_team_situation_wr: Situational win rate for bowling team
    """
    innings: int
    score: int
    wickets_lost: int
    balls_remaining: int
    league: str
    batting_team: str
    bowling_team: str
    total_balls: int = 120
    target_runs: Optional[int] = None
    venue: Optional[str] = None
    batting_team_win_rate: float = 0.5
    bowling_team_win_rate: float = 0.5
    batting_team_situation_wr: float = 0.5
    bowling_team_situation_wr: float = 0.5
    
    def __post_init__(self) -> None:
        """Validate state after initialization."""
        if self.innings not in (1, 2):
            raise ValueError(f"innings must be 1 or 2, got {self.innings}")
        if self.score < 0:
            raise ValueError(f"score must be >= 0, got {self.score}")
        if not 0 <= self.wickets_lost <= 10:
            raise ValueError(f"wickets_lost must be 0-10, got {self.wickets_lost}")
        if not (6 <= self.total_balls <= 120 and self.total_balls % 6 == 0):
            raise ValueError(f"total_balls must be 6-120 and divisible by 6, got {self.total_balls}")
        if not 0 <= self.balls_remaining <= self.total_balls:
            raise ValueError(f"balls_remaining must be 0-{self.total_balls}, got {self.balls_remaining}")
        if self.innings == 2 and self.target_runs is None:
            raise ValueError("target_runs required for innings 2")
    
    @property
    def overs_completed(self) -> float:
        """Overs completed in current innings."""
        return (self.total_balls - self.balls_remaining) / 6
    
    @property
    def phase(self) -> str:
        """Current game phase: powerplay, middle, or death."""
        return get_phase(self.balls_remaining, total_balls=self.total_balls)
    
    @property
    def is_over(self) -> bool:
        """Check if innings is over."""
        if self.wickets_lost >= 10:
            return True
        if self.balls_remaining <= 0:
            return True
        if self.innings == 2 and self.target_runs and self.score >= self.target_runs:
            return True
        return False
    
    @property
    def runs_required(self) -> Optional[int]:
        """Runs required to win (innings 2 only)."""
        if self.innings == 2 and self.target_runs:
            return max(0, self.target_runs - self.score)
        return None
    
    @property
    def required_run_rate(self) -> Optional[float]:
        """Required run rate to win (innings 2 only)."""
        if self.innings == 2 and self.target_runs and self.balls_remaining > 0:
            runs_needed = self.target_runs - self.score
            overs_remaining = self.balls_remaining / 6
            return runs_needed / overs_remaining if overs_remaining > 0 else float('inf')
        return None
    
    def copy(self) -> "MatchState":
        """Create a copy of this state."""
        return MatchState(
            innings=self.innings,
            score=self.score,
            wickets_lost=self.wickets_lost,
            balls_remaining=self.balls_remaining,
            league=self.league,
            batting_team=self.batting_team,
            bowling_team=self.bowling_team,
            total_balls=self.total_balls,
            target_runs=self.target_runs,
            venue=self.venue,
        )
    
    def apply_outcome(self, runs: int, is_wicket: bool) -> "MatchState":
        """
        Apply ball outcome and return new state.
        
        Args:
            runs: Runs scored (0-6)
            is_wicket: Whether a wicket fell
            
        Returns:
            New MatchState with updated values
        """
        return MatchState(
            innings=self.innings,
            score=self.score + runs,
            wickets_lost=self.wickets_lost + (1 if is_wicket else 0),
            balls_remaining=self.balls_remaining - 1,
            league=self.league,
            batting_team=self.batting_team,
            bowling_team=self.bowling_team,
            total_balls=self.total_balls,
            target_runs=self.target_runs,
            venue=self.venue,
        )


@dataclass
class SimulationResult:
    """
    Aggregated output from N Monte Carlo simulations.
    
    Attributes:
        mean_prob: Mean win probability across simulations
        std_prob: Standard deviation of win probabilities
        p5: 5th percentile win probability
        p95: 95th percentile win probability
        n_sims: Number of simulations run
        horizon_balls: Number of balls simulated forward
        time_taken_ms: Execution time in milliseconds
        league: League used for temperature calibration
        temperature: Temperature applied (if any)
        feature_mode: "full" (FeatureContext) or "simplified" (defaults)
        all_probs: Raw probability array (optional, for debugging)
    """
    mean_prob: float
    std_prob: float
    p5: float
    p95: float
    n_sims: int
    horizon_balls: int
    time_taken_ms: float
    league: str
    temperature: Optional[float] = None
    feature_mode: Optional[str] = None  # "full" or "simplified"
    all_probs: Optional[np.ndarray] = field(default=None, repr=False)
    
    def __post_init__(self) -> None:
        """Validate result after initialization."""
        if not 0.0 <= self.mean_prob <= 1.0:
            raise ValueError(f"mean_prob must be 0-1, got {self.mean_prob}")
        if self.std_prob < 0:
            raise ValueError(f"std_prob must be >= 0, got {self.std_prob}")
        if self.n_sims <= 0:
            raise ValueError(f"n_sims must be > 0, got {self.n_sims}")
    
    @classmethod
    def from_probs(
        cls,
        probs: np.ndarray,
        horizon_balls: int,
        time_taken_ms: float,
        league: str,
        temperature: Optional[float] = None,
        feature_mode: Optional[str] = None,
    ) -> "SimulationResult":
        """
        Create SimulationResult from array of probabilities.
        
        Args:
            probs: Array of win probabilities from N simulations
            horizon_balls: Number of balls simulated forward
            time_taken_ms: Execution time in milliseconds
            league: League code
            temperature: Temperature applied (if any)
            feature_mode: "full" (FeatureContext used) or "simplified" (defaults)
            
        Returns:
            SimulationResult with computed statistics
        """
        return cls(
            mean_prob=float(np.mean(probs)),
            std_prob=float(np.std(probs)),
            p5=float(np.percentile(probs, 5)),
            p95=float(np.percentile(probs, 95)),
            n_sims=len(probs),
            horizon_balls=horizon_balls,
            time_taken_ms=time_taken_ms,
            league=league,
            temperature=temperature,
            feature_mode=feature_mode,
            all_probs=probs,
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary (excludes all_probs)."""
        return {
            "mean_prob": self.mean_prob,
            "std_prob": self.std_prob,
            "p5": self.p5,
            "p95": self.p95,
            "n_sims": self.n_sims,
            "horizon_balls": self.horizon_balls,
            "time_taken_ms": self.time_taken_ms,
            "league": self.league,
            "temperature": self.temperature,
            "feature_mode": self.feature_mode,
        }
