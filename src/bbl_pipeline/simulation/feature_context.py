"""
FeatureContext: Cached venue/team features for MC terminal state evaluation.

Built once per Monte Carlo call to amortize feature store lookup cost
across 2000+ terminal states (~10ms total vs 10,000ms for per-state lookups).

See specs/005-mc-full-features/contracts/FeatureContext.md for API contract.
"""

from dataclasses import dataclass


@dataclass
class FeatureContext:
    """
    Cached venue/team features for MC terminal state evaluation.
    
    Built once per MC call to amortize feature store lookup cost
    across 2000 terminal state evaluations (~10ms total vs 10,000ms per-state).
    
    Attributes:
        venue_avg_score: Average first innings score at this venue (100-250 range)
        venue_bat_first_wr: Batting first win rate at this venue (0-1)
        team_a_wr: Overall win rate of team A (batting team in MC context) (0-1)
        team_b_wr: Overall win rate of team B (bowling team in MC context) (0-1)
        batting_situation_wr: Situation-specific win rate for batting team (0-1)
            - Innings 1: batting team's bat_first_wr
            - Innings 2: batting team's bowl_first_wr (chasing)
        bowling_situation_wr: Situation-specific win rate for bowling team (0-1)
            - Innings 1: bowling team's bowl_first_wr
            - Innings 2: bowling team's bat_first_wr (defending)
        league: League code for temperature/platt calibration (e.g., 'bbl', 'sa20')
    
    Example:
        >>> context = FeatureContext(
        ...     venue_avg_score=150.0,
        ...     venue_bat_first_wr=0.48,
        ...     team_a_wr=0.62,
        ...     team_b_wr=0.38,
        ...     batting_situation_wr=0.65,
        ...     bowling_situation_wr=0.42,
        ...     league="bbl"
        ... )
    """
    venue_avg_score: float
    venue_bat_first_wr: float
    team_a_wr: float
    team_b_wr: float
    batting_situation_wr: float
    bowling_situation_wr: float
    league: str
    
    def __post_init__(self) -> None:
        """Validate feature values are in expected ranges."""
        if not 100 <= self.venue_avg_score <= 250:
            raise ValueError(
                f"venue_avg_score {self.venue_avg_score} out of range [100, 250]"
            )
        if not 0 <= self.venue_bat_first_wr <= 1:
            raise ValueError(
                f"venue_bat_first_wr {self.venue_bat_first_wr} not in [0, 1]"
            )
        if not 0 <= self.team_a_wr <= 1:
            raise ValueError(f"team_a_wr {self.team_a_wr} not in [0, 1]")
        if not 0 <= self.team_b_wr <= 1:
            raise ValueError(f"team_b_wr {self.team_b_wr} not in [0, 1]")
        if not 0 <= self.batting_situation_wr <= 1:
            raise ValueError(
                f"batting_situation_wr {self.batting_situation_wr} not in [0, 1]"
            )
        if not 0 <= self.bowling_situation_wr <= 1:
            raise ValueError(
                f"bowling_situation_wr {self.bowling_situation_wr} not in [0, 1]"
            )
        if not self.league:
            raise ValueError("league must be non-empty string")
