"""
MatchPriority Model - Priority scoring for resource allocation.

Feature: 007-fast-updates
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class MatchPhase(Enum):
    """Phase of the cricket match affecting priority."""
    TOSS = "toss"
    START = "start"
    POWERPLAY = "powerplay"  # First 6 overs in limited-overs
    MIDDLE = "middle"  # Middle overs
    DEATH = "death"  # Final overs (16-20 in T20, 40-50 in ODI)
    FINAL_OVER = "final_over"  # Last over
    SUPER_OVER = "super_over"  # Tie-breaker

    @property
    def weight(self) -> float:
        """Phase weight for priority calculation."""
        weights = {
            MatchPhase.TOSS: 0.5,
            MatchPhase.START: 1.0,
            MatchPhase.POWERPLAY: 2.0,
            MatchPhase.MIDDLE: 2.0,
            MatchPhase.DEATH: 2.5,
            MatchPhase.FINAL_OVER: 3.0,
            MatchPhase.SUPER_OVER: 4.0,
        }
        return weights[self]


class MatchImportance(Enum):
    """Importance level of the match."""
    CLUB = "club"  # Local club match
    DOMESTIC = "domestic"  # Domestic league/tournament
    FRANCHISE = "franchise"  # IPL, BBL, etc.
    INTERNATIONAL = "international"  # ODI, T20I, Test

    @property
    def weight(self) -> float:
        """Importance weight for priority calculation."""
        weights = {
            MatchImportance.CLUB: 1.0,
            MatchImportance.DOMESTIC: 2.0,
            MatchImportance.FRANCHISE: 2.5,
            MatchImportance.INTERNATIONAL: 3.0,
        }
        return weights[self]


@dataclass
class MatchPriority:
    """
    Priority scoring for resource allocation.
    
    Used by the scheduler to determine which matches get more frequent updates.
    """
    match_id: str
    viewer_count: int  # Current active viewers
    match_phase: MatchPhase
    match_importance: MatchImportance
    calculated_at: datetime = None
    # Optional overrides
    manual_boost: float = 1.0  # Manual priority multiplier (e.g., for featured matches)
    is_close_finish: bool = False  # Extra priority for tight matches

    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.calculated_at is None:
            self.calculated_at = datetime.now()
        self._validate()

    def _validate(self):
        """Validate the MatchPriority."""
        if not self.match_id or not isinstance(self.match_id, str):
            raise ValueError("match_id must be a non-empty string")

        if self.viewer_count < 0:
            raise ValueError(f"viewer_count cannot be negative, got {self.viewer_count}")

        if self.manual_boost <= 0:
            raise ValueError(f"manual_boost must be positive, got {self.manual_boost}")

    @property
    def priority_score(self) -> float:
        """
        Calculate the composite priority score.
        
        Formula: viewer_count × phase_weight × importance_weight × manual_boost × close_finish_bonus
        """
        base_score = (
            self.viewer_count
            * self.match_phase.weight
            * self.match_importance.weight
            * self.manual_boost
        )

        # Add 50% bonus for close finishes
        if self.is_close_finish:
            base_score *= 1.5

        return base_score

    @property
    def polling_interval_seconds(self) -> float:
        """
        Suggested polling interval based on priority.
        Higher priority = shorter interval.
        """
        score = self.priority_score

        if score >= 10000:  # Very high priority
            return 0.5
        elif score >= 5000:  # High priority
            return 1.0
        elif score >= 1000:  # Medium priority
            return 2.0
        elif score >= 100:  # Low priority
            return 3.0
        else:  # Very low priority
            return 5.0

    @classmethod
    def from_match_state(
        cls,
        match_id: str,
        viewer_count: int,
        overs: float,
        max_overs: float,
        runs_needed: Optional[int],
        wickets: int,
        match_type: str,
    ) -> "MatchPriority":
        """
        Create MatchPriority from current match state.
        
        Args:
            match_id: Unique match identifier
            viewer_count: Current active viewers
            overs: Current overs completed
            max_overs: Maximum overs in format (20 for T20, 50 for ODI)
            runs_needed: Runs needed to win (2nd innings only)
            wickets: Wickets fallen
            match_type: "international", "franchise", "domestic", "club"
        """
        # Determine match phase
        if overs == 0:
            phase = MatchPhase.TOSS
        elif overs < 6:
            phase = MatchPhase.POWERPLAY
        elif overs >= max_overs - 1:
            phase = MatchPhase.FINAL_OVER
        elif overs >= max_overs - 4:
            phase = MatchPhase.DEATH
        else:
            phase = MatchPhase.MIDDLE

        # Determine importance
        importance_map = {
            "international": MatchImportance.INTERNATIONAL,
            "franchise": MatchImportance.FRANCHISE,
            "domestic": MatchImportance.DOMESTIC,
            "club": MatchImportance.CLUB,
        }
        importance = importance_map.get(match_type.lower(), MatchImportance.DOMESTIC)

        # Determine if close finish
        is_close = False
        if runs_needed is not None:
            balls_remaining = (max_overs - overs) * 6
            if balls_remaining > 0:
                required_rate = runs_needed / (balls_remaining / 6)
                # Close if RRR > 8 but still achievable, or very few runs needed
                is_close = (8 <= required_rate <= 15) or (runs_needed <= 20 and overs >= max_overs - 3)

        return cls(
            match_id=match_id,
            viewer_count=viewer_count,
            match_phase=phase,
            match_importance=importance,
            is_close_finish=is_close,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "match_id": self.match_id,
            "viewer_count": self.viewer_count,
            "match_phase": self.match_phase.value,
            "match_importance": self.match_importance.value,
            "priority_score": self.priority_score,
            "polling_interval_seconds": self.polling_interval_seconds,
            "calculated_at": self.calculated_at.isoformat(),
            "manual_boost": self.manual_boost,
            "is_close_finish": self.is_close_finish,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MatchPriority":
        """Create MatchPriority from dictionary."""
        calculated_at = data.get("calculated_at")
        if isinstance(calculated_at, str):
            calculated_at = datetime.fromisoformat(calculated_at.replace("Z", "+00:00"))

        return cls(
            match_id=data["match_id"],
            viewer_count=int(data["viewer_count"]),
            match_phase=MatchPhase(data["match_phase"]),
            match_importance=MatchImportance(data["match_importance"]),
            calculated_at=calculated_at,
            manual_boost=float(data.get("manual_boost", 1.0)),
            is_close_finish=data.get("is_close_finish", False),
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"MatchPriority {self.match_id}: "
            f"score={self.priority_score:.0f}, "
            f"phase={self.match_phase.value}, "
            f"interval={self.polling_interval_seconds}s"
        )

    def __lt__(self, other: "MatchPriority") -> bool:
        """For priority queue ordering (higher score = higher priority)."""
        return self.priority_score > other.priority_score

    def __eq__(self, other: object) -> bool:
        """Equality check."""
        if not isinstance(other, MatchPriority):
            return False
        return self.match_id == other.match_id and self.priority_score == other.priority_score
