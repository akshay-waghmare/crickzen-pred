"""
ScoreSnapshot Model - Current match state at a point in time.

Feature: 007-fast-updates
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ScoreSnapshot:
    """
    Current match state at a point in time.
    
    Identity: match_id (singleton per match, always latest state)
    """
    match_id: str
    innings: int  # Current innings (1 or 2)
    batting_team: str
    runs: int  # Total runs scored
    wickets: int  # Wickets fallen (0-10)
    overs: float  # Overs completed (e.g., 15.4)
    run_rate: float  # Current run rate
    timestamp: datetime
    sequence_number: int  # For ordering updates
    required_rate: Optional[float] = None  # Required run rate (2nd innings only)
    target: Optional[int] = None  # Target score (2nd innings only)

    # Match format limits
    MAX_WICKETS = 10
    T20_MAX_OVERS = 20.0
    ODI_MAX_OVERS = 50.0
    TEST_MAX_OVERS = 450.0  # Rough upper bound

    def __post_init__(self):
        """Validate the ScoreSnapshot after initialization."""
        self._validate()

    def _validate(self):
        """Validate all fields according to cricket rules."""
        # Validate match_id
        if not self.match_id or not isinstance(self.match_id, str):
            raise ValueError("match_id must be a non-empty string")

        # Validate innings
        if self.innings not in (1, 2):
            raise ValueError(f"innings must be 1 or 2, got {self.innings}")

        # Validate wickets
        if not 0 <= self.wickets <= self.MAX_WICKETS:
            raise ValueError(f"wickets must be 0-{self.MAX_WICKETS}, got {self.wickets}")

        # Validate runs
        if self.runs < 0:
            raise ValueError(f"runs cannot be negative, got {self.runs}")

        # Validate overs
        if self.overs < 0:
            raise ValueError(f"overs cannot be negative, got {self.overs}")

        # Validate ball within over
        ball_in_over = int((self.overs % 1) * 10 + 0.5)
        if ball_in_over > 6:
            raise ValueError(f"Invalid overs {self.overs}: ball within over must be 0-6")

        # Validate run_rate
        if self.run_rate < 0:
            raise ValueError(f"run_rate cannot be negative, got {self.run_rate}")

        # Validate required_rate (only for 2nd innings)
        if self.required_rate is not None:
            if self.innings != 2:
                raise ValueError("required_rate only valid for 2nd innings")
            if self.required_rate < 0:
                raise ValueError(f"required_rate cannot be negative, got {self.required_rate}")

        # Validate target (only for 2nd innings)
        if self.target is not None:
            if self.innings != 2:
                raise ValueError("target only valid for 2nd innings")
            if self.target < 0:
                raise ValueError(f"target cannot be negative, got {self.target}")

        # Validate sequence_number
        if self.sequence_number < 0:
            raise ValueError(f"sequence_number must be >= 0, got {self.sequence_number}")

    @property
    def balls_faced(self) -> int:
        """Total legal deliveries faced in this innings."""
        completed_overs = int(self.overs)
        balls_in_current_over = int((self.overs % 1) * 10 + 0.5)
        return completed_overs * 6 + balls_in_current_over

    @property
    def runs_needed(self) -> Optional[int]:
        """Runs needed to win (2nd innings only)."""
        if self.target is None:
            return None
        return max(0, self.target - self.runs)

    @property
    def balls_remaining(self, max_overs: float = 20.0) -> int:
        """Balls remaining in the innings (assuming T20 by default)."""
        total_balls = int(max_overs) * 6
        return max(0, total_balls - self.balls_faced)

    @property
    def is_all_out(self) -> bool:
        """Whether the batting team is all out."""
        return self.wickets >= self.MAX_WICKETS

    @property
    def score_string(self) -> str:
        """Standard cricket score format: 'runs/wickets (overs)'."""
        return f"{self.runs}/{self.wickets} ({self.overs:.1f})"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "match_id": self.match_id,
            "innings": self.innings,
            "batting_team": self.batting_team,
            "runs": self.runs,
            "wickets": self.wickets,
            "overs": self.overs,
            "run_rate": self.run_rate,
            "timestamp": self.timestamp.isoformat(),
            "sequence_number": self.sequence_number,
        }
        if self.required_rate is not None:
            result["required_rate"] = self.required_rate
        if self.target is not None:
            result["target"] = self.target
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ScoreSnapshot":
        """Create ScoreSnapshot from dictionary."""
        timestamp = data["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        return cls(
            match_id=data["match_id"],
            innings=int(data["innings"]),
            batting_team=data["batting_team"],
            runs=int(data["runs"]),
            wickets=int(data["wickets"]),
            overs=float(data["overs"]),
            run_rate=float(data["run_rate"]),
            timestamp=timestamp,
            sequence_number=int(data["sequence_number"]),
            required_rate=data.get("required_rate"),
            target=data.get("target"),
        )

    def is_newer_than(self, other: "ScoreSnapshot") -> bool:
        """Check if this snapshot is newer than another (by sequence)."""
        if other.match_id != self.match_id:
            raise ValueError("Cannot compare snapshots from different matches")
        return self.sequence_number > other.sequence_number

    def __str__(self) -> str:
        """Human-readable string representation."""
        result = f"{self.batting_team}: {self.score_string}"
        if self.innings == 2 and self.target:
            result += f" (Target: {self.target}, RRR: {self.required_rate:.2f})"
        else:
            result += f" (RR: {self.run_rate:.2f})"
        return result
