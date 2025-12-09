from dataclasses import dataclass
from typing import Optional

@dataclass
class MatchState:
    """
    Represents the state of a match at a specific point in time for inference.
    """
    match_id: str
    venue: str
    batting_team: str
    bowling_team: str
    innings: int
    over: int
    ball: int
    current_score: int
    wickets_lost: int
    batsman_1: str  # Striker
    batsman_2: str  # Non-striker
    bowler: str
    target_runs: Optional[int] = None  # None for 1st innings
