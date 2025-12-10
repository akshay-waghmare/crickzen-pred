"""
BallTracker Service - Track ball-by-ball updates with gap detection.

Feature: 007-fast-updates
"""

import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from ..models import BallEvent, UpdateSequence

logger = logging.getLogger(__name__)


class BallTracker:
    """
    Tracks ball-by-ball updates and detects gaps.
    
    Features:
    - Maintains sequence tracking per match
    - Detects skipped balls (e.g., 9.3 → 9.6)
    - Alerts on gaps for investigation
    - Supports gap recovery notification
    """

    def __init__(
        self,
        on_gap_detected: Optional[Callable[[str, str], None]] = None,
        on_gap_recovered: Optional[Callable[[str], None]] = None,
        max_gap_before_alert: int = 2,
    ):
        """
        Initialize the ball tracker.
        
        Args:
            on_gap_detected: Callback when gap detected (match_id, details)
            on_gap_recovered: Callback when gap recovered (match_id)
            max_gap_before_alert: Number of balls that can be skipped before alerting
        """
        self.on_gap_detected = on_gap_detected
        self.on_gap_recovered = on_gap_recovered
        self.max_gap_before_alert = max_gap_before_alert
        
        # Per-match tracking state
        self._sequences: Dict[str, UpdateSequence] = {}
        self._last_balls: Dict[str, BallEvent] = {}
        self._gap_counts: Dict[str, int] = {}

    def track_ball(self, ball: BallEvent) -> Tuple[bool, Optional[str]]:
        """
        Track a new ball event and check for gaps.
        
        Args:
            ball: The new ball event
            
        Returns:
            Tuple of (is_valid, gap_details) - gap_details is None if no gap
        """
        match_id = ball.match_id
        
        # Get or create sequence tracker
        sequence = self._sequences.get(match_id)
        if sequence is None:
            sequence = UpdateSequence.initial(match_id)
            self._sequences[match_id] = sequence
            self._gap_counts[match_id] = 0

        # Check for gaps
        last_ball = self._last_balls.get(match_id)
        gap_detected = False
        gap_details = None

        if last_ball is not None:
            gap_size = ball.gap_from(last_ball)
            if gap_size > 0:
                gap_detected = True
                gap_details = (
                    f"Gap detected: {last_ball.ball_number} → {ball.ball_number} "
                    f"(skipped {gap_size} balls, seq {last_ball.sequence_number} → {ball.sequence_number})"
                )
                logger.warning(f"[{match_id}] {gap_details}")
                
                # Track consecutive gaps
                self._gap_counts[match_id] = self._gap_counts.get(match_id, 0) + 1
                
                # Alert if too many gaps
                if gap_size >= self.max_gap_before_alert:
                    self._handle_gap_alert(match_id, gap_details, gap_size)
            else:
                # Successful update - reset gap counter
                if self._gap_counts.get(match_id, 0) > 0:
                    self._handle_gap_recovered(match_id)
                self._gap_counts[match_id] = 0

        # Update sequence
        new_sequence = sequence.process_update(
            ball.sequence_number,
            ball.ball_number,
        )
        self._sequences[match_id] = new_sequence
        self._last_balls[match_id] = ball

        return not gap_detected, gap_details

    def _handle_gap_alert(self, match_id: str, details: str, gap_size: int):
        """Handle gap detection alert."""
        logger.error(
            f"[{match_id}] BALL GAP ALERT: {details} "
            f"(consecutive gaps: {self._gap_counts.get(match_id, 0)})"
        )
        
        if self.on_gap_detected:
            try:
                self.on_gap_detected(match_id, details)
            except Exception as e:
                logger.error(f"Error in gap_detected callback: {e}")

    def _handle_gap_recovered(self, match_id: str):
        """Handle gap recovery."""
        gap_count = self._gap_counts.get(match_id, 0)
        logger.info(f"[{match_id}] Gap recovered after {gap_count} consecutive gaps")
        
        if self.on_gap_recovered:
            try:
                self.on_gap_recovered(match_id)
            except Exception as e:
                logger.error(f"Error in gap_recovered callback: {e}")

    def get_sequence(self, match_id: str) -> Optional[UpdateSequence]:
        """Get current sequence tracking for a match."""
        return self._sequences.get(match_id)

    def get_last_ball(self, match_id: str) -> Optional[BallEvent]:
        """Get the last ball tracked for a match."""
        return self._last_balls.get(match_id)

    def get_gap_count(self, match_id: str) -> int:
        """Get consecutive gap count for a match."""
        return self._gap_counts.get(match_id, 0)

    def reset_match(self, match_id: str):
        """Reset tracking for a match (e.g., new innings)."""
        if match_id in self._sequences:
            del self._sequences[match_id]
        if match_id in self._last_balls:
            del self._last_balls[match_id]
        if match_id in self._gap_counts:
            del self._gap_counts[match_id]
        logger.debug(f"[{match_id}] Ball tracking reset")

    def get_stats(self) -> Dict:
        """Get overall tracking statistics."""
        return {
            "matches_tracked": len(self._sequences),
            "total_gap_count": sum(self._gap_counts.values()),
            "matches_with_gaps": sum(1 for c in self._gap_counts.values() if c > 0),
        }

    def get_match_stats(self, match_id: str) -> Dict:
        """Get tracking statistics for a specific match."""
        sequence = self._sequences.get(match_id)
        last_ball = self._last_balls.get(match_id)
        
        return {
            "match_id": match_id,
            "last_sequence": sequence.last_sequence if sequence else 0,
            "last_ball_number": sequence.last_ball_number if sequence else 0,
            "gap_detected": sequence.gap_detected if sequence else False,
            "consecutive_gaps": self._gap_counts.get(match_id, 0),
            "last_ball": last_ball.to_dict() if last_ball else None,
        }

    def validate_ball_continuity(
        self,
        match_id: str,
        expected_ball: float,
        actual_ball: float,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that a ball is continuous from expected.
        
        Args:
            match_id: Match identifier
            expected_ball: Expected ball number
            actual_ball: Actual ball number received
            
        Returns:
            Tuple of (is_continuous, gap_description)
        """
        if abs(expected_ball - actual_ball) < 0.01:
            return True, None
            
        # Check if it's the next ball
        expected_next = self._calculate_next_ball(expected_ball)
        if abs(expected_next - actual_ball) < 0.01:
            return True, None
            
        # Gap detected
        gap_size = self._calculate_ball_gap(expected_ball, actual_ball)
        return False, f"Expected ball {expected_ball} or {expected_next}, got {actual_ball} (gap: {gap_size})"

    def _calculate_next_ball(self, current: float) -> float:
        """Calculate the next expected ball number."""
        over = int(current)
        ball = int((current % 1) * 10 + 0.5)
        
        if ball >= 6:
            # New over
            return float(over + 1) + 0.1
        else:
            # Next ball in same over
            return current + 0.1

    def _calculate_ball_gap(self, old: float, new: float) -> int:
        """Calculate the number of balls between two ball numbers."""
        old_over = int(old)
        old_ball = int((old % 1) * 10 + 0.5)
        new_over = int(new)
        new_ball = int((new % 1) * 10 + 0.5)
        
        old_total = old_over * 6 + old_ball
        new_total = new_over * 6 + new_ball
        
        return max(0, new_total - old_total - 1)
