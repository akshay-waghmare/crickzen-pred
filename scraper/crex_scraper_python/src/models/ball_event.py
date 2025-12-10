"""
BallEvent Model - Represents a single delivery in a cricket match.

Feature: 007-fast-updates
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import re


@dataclass(frozen=True)
class Extras:
    """Extra runs for a delivery."""
    wides: int = 0
    no_balls: int = 0
    byes: int = 0
    leg_byes: int = 0

    @property
    def total(self) -> int:
        """Total extra runs."""
        return self.wides + self.no_balls + self.byes + self.leg_byes

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "wides": self.wides,
            "no_balls": self.no_balls,
            "byes": self.byes,
            "leg_byes": self.leg_byes,
            "total": self.total,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Extras":
        """Create Extras from dictionary."""
        return cls(
            wides=data.get("wides", 0),
            no_balls=data.get("no_balls", 0),
            byes=data.get("byes", 0),
            leg_byes=data.get("leg_byes", 0),
        )


@dataclass(frozen=True)
class Wicket:
    """Wicket details for a delivery."""
    type: str  # bowled, caught, lbw, stumped, run_out, hit_wicket
    batsman: str
    fielder: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "type": self.type,
            "batsman": self.batsman,
        }
        if self.fielder:
            result["fielder"] = self.fielder
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Wicket":
        """Create Wicket from dictionary."""
        return cls(
            type=data["type"],
            batsman=data["batsman"],
            fielder=data.get("fielder"),
        )


@dataclass
class BallEvent:
    """
    Represents a single delivery in a cricket match.
    
    Identity: Composite key (match_id, ball_number, sequence_number)
    """
    match_id: str
    ball_number: float  # Over.ball format (e.g., 9.4 = 9th over, 4th ball)
    runs: int  # Runs scored off bat (0-6, 7 for boundary overthrow)
    timestamp: datetime
    sequence_number: int  # Monotonically increasing per match
    extras: Optional[Extras] = None
    wicket: Optional[Wicket] = None

    # Validation patterns
    _BALL_NUMBER_PATTERN = re.compile(r"^\d+\.[1-6]$")

    def __post_init__(self):
        """Validate the BallEvent after initialization."""
        self._validate()

    def _validate(self):
        """Validate all fields according to cricket rules."""
        # Validate match_id
        if not self.match_id or not isinstance(self.match_id, str):
            raise ValueError("match_id must be a non-empty string")

        # Validate ball_number format
        ball_str = f"{self.ball_number:.1f}"
        # Extract the ball within the over (decimal part)
        ball_in_over = int((self.ball_number % 1) * 10 + 0.5)  # Handle float precision
        if ball_in_over < 1 or ball_in_over > 6:
            raise ValueError(
                f"Invalid ball_number {self.ball_number}: ball within over must be 1-6"
            )

        # Validate runs (0-7, allowing for boundary overthrow)
        if not 0 <= self.runs <= 7:
            raise ValueError(f"runs must be between 0 and 7, got {self.runs}")

        # Validate sequence_number
        if self.sequence_number < 0:
            raise ValueError(f"sequence_number must be >= 0, got {self.sequence_number}")

    @property
    def over(self) -> int:
        """Get the over number (0-indexed)."""
        return int(self.ball_number)

    @property
    def ball_in_over(self) -> int:
        """Get the ball number within the over (1-6)."""
        return int((self.ball_number % 1) * 10 + 0.5)

    @property
    def total_runs(self) -> int:
        """Total runs including extras."""
        extra_runs = self.extras.total if self.extras else 0
        return self.runs + extra_runs

    @property
    def is_wicket(self) -> bool:
        """Whether this delivery resulted in a wicket."""
        return self.wicket is not None

    @property
    def is_legal_delivery(self) -> bool:
        """Whether this was a legal delivery (counts towards over)."""
        if self.extras:
            return self.extras.wides == 0 and self.extras.no_balls == 0
        return True

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "match_id": self.match_id,
            "ball_number": self.ball_number,
            "runs": self.runs,
            "timestamp": self.timestamp.isoformat(),
            "sequence_number": self.sequence_number,
        }
        if self.extras:
            result["extras"] = self.extras.to_dict()
        if self.wicket:
            result["wicket"] = self.wicket.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BallEvent":
        """Create BallEvent from dictionary."""
        extras = None
        if "extras" in data and data["extras"]:
            extras = Extras.from_dict(data["extras"])

        wicket = None
        if "wicket" in data and data["wicket"]:
            wicket = Wicket.from_dict(data["wicket"])

        timestamp = data["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        return cls(
            match_id=data["match_id"],
            ball_number=float(data["ball_number"]),
            runs=int(data["runs"]),
            timestamp=timestamp,
            sequence_number=int(data["sequence_number"]),
            extras=extras,
            wicket=wicket,
        )

    def follows(self, previous: "BallEvent") -> bool:
        """
        Check if this ball follows the previous ball in sequence.
        Returns True if there's no gap.
        """
        if previous.match_id != self.match_id:
            raise ValueError("Cannot compare balls from different matches")

        # Check sequence continuity
        if self.sequence_number != previous.sequence_number + 1:
            return False

        # Check ball number continuity
        expected_ball = self._next_ball_number(previous.ball_number, previous.is_legal_delivery)
        return abs(self.ball_number - expected_ball) < 0.01  # Float tolerance

    def _next_ball_number(self, current: float, was_legal: bool) -> float:
        """Calculate the expected next ball number."""
        if not was_legal:
            # Illegal delivery - same ball number expected
            return current

        ball_in_over = int((current % 1) * 10 + 0.5)
        if ball_in_over >= 6:
            # End of over - next over starts
            return float(int(current) + 1) + 0.1
        else:
            # Next ball in same over
            return current + 0.1

    def gap_from(self, previous: "BallEvent") -> int:
        """
        Calculate the number of balls missed between previous and this ball.
        Returns 0 if no gap.
        """
        if previous.match_id != self.match_id:
            raise ValueError("Cannot compare balls from different matches")

        sequence_gap = self.sequence_number - previous.sequence_number - 1
        return max(0, sequence_gap)

    def __str__(self) -> str:
        """Human-readable string representation."""
        result = f"Ball {self.ball_number}: {self.runs} run(s)"
        if self.extras and self.extras.total > 0:
            result += f" + {self.extras.total} extras"
        if self.is_wicket:
            result += f" WICKET ({self.wicket.type})"
        return result
