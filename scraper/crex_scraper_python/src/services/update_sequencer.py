"""
UpdateSequencer Service - Ensure ordered update delivery with deduplication.

Feature: 007-fast-updates
"""

import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..models import ScoreSnapshot, BallEvent

logger = logging.getLogger(__name__)


class UpdateSequencer:
    """
    Ensures ordered update delivery with latest-state-wins deduplication.
    
    Features:
    - Orders updates by sequence number
    - Implements latest-state-wins for backpressure handling
    - Provides update queue with size limits
    - Supports async delivery with callbacks
    """

    def __init__(
        self,
        max_queue_size: int = 100,
        on_update: Optional[Callable[[str, Any], None]] = None,
    ):
        """
        Initialize the update sequencer.
        
        Args:
            max_queue_size: Maximum updates to queue per match
            on_update: Callback when update is ready to deliver
        """
        self.max_queue_size = max_queue_size
        self.on_update = on_update
        
        # Per-match update queues
        self._queues: Dict[str, deque] = {}
        # Latest state per match (for latest-wins deduplication)
        self._latest_scores: Dict[str, ScoreSnapshot] = {}
        self._latest_balls: Dict[str, BallEvent] = {}
        # Sequence tracking
        self._last_delivered_seq: Dict[str, int] = {}
        # Statistics
        self._stats = {
            "total_received": 0,
            "total_delivered": 0,
            "total_dropped": 0,
            "total_deduplicated": 0,
        }

    def enqueue_score(self, score: ScoreSnapshot) -> bool:
        """
        Enqueue a score update with latest-state-wins handling.
        
        Args:
            score: Score snapshot to enqueue
            
        Returns:
            True if enqueued, False if dropped or deduplicated
        """
        match_id = score.match_id
        self._stats["total_received"] += 1
        
        # Check if this is newer than current latest
        current_latest = self._latest_scores.get(match_id)
        if current_latest and score.sequence_number <= current_latest.sequence_number:
            self._stats["total_deduplicated"] += 1
            logger.debug(f"[{match_id}] Dropping older score seq {score.sequence_number}")
            return False

        # Latest-state-wins: Replace pending score with newer one
        self._latest_scores[match_id] = score
        
        # Ensure queue exists
        if match_id not in self._queues:
            self._queues[match_id] = deque(maxlen=self.max_queue_size)

        # Add to queue (or replace if already has a score pending)
        queue = self._queues[match_id]
        
        # Find and replace existing score in queue, or add new
        replaced = False
        for i, (update_type, update) in enumerate(queue):
            if update_type == "score":
                # Replace with newer score
                queue[i] = ("score", score)
                replaced = True
                self._stats["total_deduplicated"] += 1
                break
        
        if not replaced:
            if len(queue) >= self.max_queue_size:
                self._stats["total_dropped"] += 1
                logger.warning(f"[{match_id}] Queue full, dropping oldest update")
            queue.append(("score", score))

        logger.debug(f"[{match_id}] Enqueued score seq {score.sequence_number}")
        return True

    def enqueue_ball(self, ball: BallEvent) -> bool:
        """
        Enqueue a ball event. Ball events are NOT deduplicated (each ball matters).
        
        Args:
            ball: Ball event to enqueue
            
        Returns:
            True if enqueued, False if dropped
        """
        match_id = ball.match_id
        self._stats["total_received"] += 1
        
        # Check if this is a duplicate
        current_latest = self._latest_balls.get(match_id)
        if current_latest and ball.sequence_number <= current_latest.sequence_number:
            self._stats["total_deduplicated"] += 1
            logger.debug(f"[{match_id}] Dropping duplicate ball seq {ball.sequence_number}")
            return False

        self._latest_balls[match_id] = ball
        
        # Ensure queue exists
        if match_id not in self._queues:
            self._queues[match_id] = deque(maxlen=self.max_queue_size)

        queue = self._queues[match_id]
        
        if len(queue) >= self.max_queue_size:
            self._stats["total_dropped"] += 1
            logger.warning(f"[{match_id}] Queue full, dropping oldest update")
        
        queue.append(("ball", ball))
        logger.debug(f"[{match_id}] Enqueued ball {ball.ball_number} seq {ball.sequence_number}")
        return True

    async def deliver_pending(self, match_id: str) -> int:
        """
        Deliver all pending updates for a match.
        
        Args:
            match_id: Match to deliver updates for
            
        Returns:
            Number of updates delivered
        """
        queue = self._queues.get(match_id)
        if not queue:
            return 0

        delivered = 0
        while queue:
            update_type, update = queue.popleft()
            
            # Deliver via callback
            if self.on_update:
                try:
                    self.on_update(update_type, update)
                    self._stats["total_delivered"] += 1
                    delivered += 1
                    
                    # Track last delivered sequence
                    seq = update.sequence_number
                    if seq > self._last_delivered_seq.get(match_id, 0):
                        self._last_delivered_seq[match_id] = seq
                        
                except Exception as e:
                    logger.error(f"Error delivering update: {e}")
                    # Re-queue on failure
                    queue.appendleft((update_type, update))
                    break

        return delivered

    def get_pending_count(self, match_id: str) -> int:
        """Get number of pending updates for a match."""
        queue = self._queues.get(match_id)
        return len(queue) if queue else 0

    def get_latest_score(self, match_id: str) -> Optional[ScoreSnapshot]:
        """Get latest score for a match (for latest-state-wins)."""
        return self._latest_scores.get(match_id)

    def get_latest_ball(self, match_id: str) -> Optional[BallEvent]:
        """Get latest ball for a match."""
        return self._latest_balls.get(match_id)

    def get_stats(self) -> Dict:
        """Get overall sequencer statistics."""
        return {
            **self._stats,
            "matches_tracked": len(self._queues),
            "total_pending": sum(len(q) for q in self._queues.values()),
        }

    def get_match_stats(self, match_id: str) -> Dict:
        """Get statistics for a specific match."""
        return {
            "match_id": match_id,
            "pending_count": self.get_pending_count(match_id),
            "last_delivered_seq": self._last_delivered_seq.get(match_id, 0),
            "latest_score_seq": (
                self._latest_scores[match_id].sequence_number
                if match_id in self._latest_scores else 0
            ),
            "latest_ball_seq": (
                self._latest_balls[match_id].sequence_number
                if match_id in self._latest_balls else 0
            ),
        }

    def clear_match(self, match_id: str):
        """Clear all tracking for a match."""
        if match_id in self._queues:
            del self._queues[match_id]
        if match_id in self._latest_scores:
            del self._latest_scores[match_id]
        if match_id in self._latest_balls:
            del self._latest_balls[match_id]
        if match_id in self._last_delivered_seq:
            del self._last_delivered_seq[match_id]
        logger.debug(f"[{match_id}] Sequencer state cleared")

    def clear_all(self):
        """Clear all tracking state."""
        self._queues.clear()
        self._latest_scores.clear()
        self._latest_balls.clear()
        self._last_delivered_seq.clear()
        logger.info("All sequencer state cleared")
