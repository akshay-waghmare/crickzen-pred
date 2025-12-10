"""
UpdateSequence Model - Ordering mechanism for reliable update delivery.

Feature: 007-fast-updates
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class UpdateSequence:
    """
    Tracks update ordering and gap detection for a match.
    
    State Transitions:
      Initial → Processing → Updated → (Gap Detected → Alerting → Updated)
    """
    match_id: str
    last_sequence: int  # Last processed sequence number
    last_ball_number: float  # Last processed ball number
    gap_detected: bool = False  # Whether a gap was detected
    gap_details: Optional[str] = None  # Description of gap if detected
    updated_at: datetime = None
    consecutive_gaps: int = 0  # Track repeated gaps for escalation

    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.updated_at is None:
            self.updated_at = datetime.now()
        self._validate()

    def _validate(self):
        """Validate the UpdateSequence."""
        if not self.match_id or not isinstance(self.match_id, str):
            raise ValueError("match_id must be a non-empty string")

        if self.last_sequence < 0:
            raise ValueError(f"last_sequence must be >= 0, got {self.last_sequence}")

    def process_update(
        self,
        new_sequence: int,
        new_ball_number: float,
    ) -> "UpdateSequence":
        """
        Process a new update and detect gaps.
        Returns a new UpdateSequence with updated state.
        """
        gap_detected = False
        gap_details = None
        consecutive_gaps = 0

        # Check for sequence gap
        expected_sequence = self.last_sequence + 1
        if new_sequence > expected_sequence:
            gap_detected = True
            missed_count = new_sequence - expected_sequence
            gap_details = (
                f"Missed {missed_count} updates: seq {expected_sequence} to {new_sequence - 1}, "
                f"ball {self.last_ball_number} to {new_ball_number}"
            )
            consecutive_gaps = self.consecutive_gaps + 1

        # Check for ball number gap (within same over or across overs)
        if not gap_detected:
            ball_gap = self._calculate_ball_gap(self.last_ball_number, new_ball_number)
            if ball_gap > 1:
                gap_detected = True
                gap_details = f"Ball gap detected: {self.last_ball_number} → {new_ball_number} (skipped {ball_gap - 1})"
                consecutive_gaps = self.consecutive_gaps + 1

        return UpdateSequence(
            match_id=self.match_id,
            last_sequence=new_sequence,
            last_ball_number=new_ball_number,
            gap_detected=gap_detected,
            gap_details=gap_details,
            updated_at=datetime.now(),
            consecutive_gaps=consecutive_gaps if gap_detected else 0,
        )

    def _calculate_ball_gap(self, old_ball: float, new_ball: float) -> int:
        """
        Calculate the number of balls between two ball numbers.
        Returns 1 for consecutive balls.
        """
        old_over = int(old_ball)
        old_ball_in_over = int((old_ball % 1) * 10 + 0.5)
        new_over = int(new_ball)
        new_ball_in_over = int((new_ball % 1) * 10 + 0.5)

        # Handle invalid cases
        if new_over < old_over:
            return 0  # Can't go backwards
        if new_over == old_over and new_ball_in_over <= old_ball_in_over:
            return 0  # Same or earlier ball in same over

        # Calculate total balls
        old_total = old_over * 6 + old_ball_in_over
        new_total = new_over * 6 + new_ball_in_over

        return new_total - old_total

    def clear_gap(self) -> "UpdateSequence":
        """Clear gap detection state after recovery."""
        return UpdateSequence(
            match_id=self.match_id,
            last_sequence=self.last_sequence,
            last_ball_number=self.last_ball_number,
            gap_detected=False,
            gap_details=None,
            updated_at=datetime.now(),
            consecutive_gaps=0,
        )

    @property
    def needs_escalation(self) -> bool:
        """Whether gap detection should be escalated (3+ consecutive gaps)."""
        return self.consecutive_gaps >= 3

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "match_id": self.match_id,
            "last_sequence": self.last_sequence,
            "last_ball_number": self.last_ball_number,
            "gap_detected": self.gap_detected,
            "gap_details": self.gap_details,
            "updated_at": self.updated_at.isoformat(),
            "consecutive_gaps": self.consecutive_gaps,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateSequence":
        """Create UpdateSequence from dictionary."""
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        return cls(
            match_id=data["match_id"],
            last_sequence=int(data["last_sequence"]),
            last_ball_number=float(data["last_ball_number"]),
            gap_detected=data.get("gap_detected", False),
            gap_details=data.get("gap_details"),
            updated_at=updated_at,
            consecutive_gaps=int(data.get("consecutive_gaps", 0)),
        )

    @classmethod
    def initial(cls, match_id: str) -> "UpdateSequence":
        """Create initial state for a new match."""
        return cls(
            match_id=match_id,
            last_sequence=0,
            last_ball_number=0.0,
            gap_detected=False,
            gap_details=None,
            consecutive_gaps=0,
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        status = "GAP DETECTED" if self.gap_detected else "OK"
        return f"UpdateSequence {self.match_id}: seq={self.last_sequence}, ball={self.last_ball_number} [{status}]"
