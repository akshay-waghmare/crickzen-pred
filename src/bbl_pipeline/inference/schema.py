from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class MatchState:
    """
    Represents the state of a match at a specific point in time for inference.
    Enhanced to support resource-based feature calculation.
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
    
    # Optional enhanced state info
    first_innings_score: Optional[int] = None  # Score of first innings (for 2nd innings context)
    
    def get_overs_bowled(self) -> float:
        """Return overs bowled as a float (e.g., 5.3 = 5 overs 3 balls)."""
        return self.over + (self.ball / 6.0)
    
    def get_balls_bowled(self) -> int:
        """Return total balls bowled."""
        return self.over * 6 + self.ball
    
    def get_overs_remaining(self, total_overs: int = 20) -> float:
        """Return overs remaining in the innings."""
        return total_overs - self.get_overs_bowled()
    
    def get_balls_remaining(self, total_overs: int = 20) -> int:
        """Return balls remaining in the innings."""
        return (total_overs * 6) - self.get_balls_bowled()
    
    def get_wickets_remaining(self) -> int:
        """Return wickets in hand."""
        return 10 - self.wickets_lost
    
    def get_runs_required(self) -> Optional[int]:
        """Return runs required to win (only valid for 2nd innings)."""
        if self.target_runs is None:
            return None
        return max(0, self.target_runs - self.current_score)
    
    def get_required_run_rate(self) -> Optional[float]:
        """Return required run rate (only valid for 2nd innings)."""
        runs_required = self.get_runs_required()
        overs_remaining = self.get_overs_remaining()
        
        if runs_required is None or overs_remaining <= 0:
            return None
        
        return runs_required / overs_remaining
    
    def get_current_run_rate(self) -> float:
        """Return current run rate."""
        overs_bowled = self.get_overs_bowled()
        if overs_bowled <= 0:
            return 0.0
        return self.current_score / overs_bowled
    
    def is_powerplay(self) -> bool:
        """Check if current over is in powerplay (overs 1-6)."""
        return self.over < 6
    
    def is_death_overs(self) -> bool:
        """Check if current over is in death overs (overs 16-20)."""
        return self.over >= 15
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for feature extraction."""
        return {
            'match_id': self.match_id,
            'venue': self.venue,
            'batting_team': self.batting_team,
            'bowling_team': self.bowling_team,
            'innings': self.innings,
            'over': self.over,
            'ball': self.ball,
            'current_score': self.current_score,
            'wickets_lost': self.wickets_lost,
            'batsman_1': self.batsman_1,
            'batsman_2': self.batsman_2,
            'bowler': self.bowler,
            'target_runs': self.target_runs,
            'first_innings_score': self.first_innings_score,
        }

