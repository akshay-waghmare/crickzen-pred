"""
Fast Update Manager - Coordinates fast ball-by-ball and scorecard updates.

Feature: 007-fast-updates

This service manages:
- Immediate push on sV3 intercept
- Dedicated scorecard polling loop (10s interval)
- Adaptive backoff with jitter
- Match priority-based scheduling
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from ..config import get_settings
from ..models import (
    BallEvent,
    ScoreSnapshot,
    ScorecardState,
    UpdateSequence,
    MatchPriority,
    MatchPhase,
    MatchImportance,
)
from ..services import BallTracker, ScoreParser, UpdateSequencer, ScorecardDiffer
from ..metrics import MetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class MatchState:
    """Tracks state for a single live match."""
    match_id: str
    url: str
    priority: MatchPriority
    last_sv3_time: float = 0.0
    last_sc4_time: float = 0.0
    last_ball_number: float = 0.0
    consecutive_errors: int = 0
    current_backoff: float = 1.0
    scorecard_poll_task: Optional[asyncio.Task] = None
    is_active: bool = True


class FastUpdateManager:
    """
    Manages fast updates for live cricket matches.
    
    Responsibilities:
    - Track active matches and their priorities
    - Handle immediate sV3 pushes
    - Run dedicated scorecard polling loops
    - Apply adaptive backoff on errors
    - Emit metrics for monitoring
    """

    def __init__(
        self,
        metrics: Optional[MetricsCollector] = None,
        on_score_push: Optional[Callable[[str, Dict], bool]] = None,
        on_scorecard_push: Optional[Callable[[str, Dict], bool]] = None,
    ):
        """
        Initialize the FastUpdateManager.
        
        Args:
            metrics: Metrics collector for observability
            on_score_push: Callback to push score data to backend
            on_scorecard_push: Callback to push scorecard data to backend
        """
        self.settings = get_settings()
        self.metrics = metrics or MetricsCollector()
        self.on_score_push = on_score_push
        self.on_scorecard_push = on_scorecard_push
        
        # Per-match state
        self._matches: Dict[str, MatchState] = {}
        self._lock = asyncio.Lock()
        
        # Services
        self._ball_tracker = BallTracker(
            on_gap_detected=self._handle_gap_detected,
            max_gap_before_alert=self.settings.max_ball_gap_before_alert,
        )
        self._sequencer = UpdateSequencer(
            max_queue_size=100,
            on_update=self._deliver_update,
        )
        self._scorecard_differ = ScorecardDiffer(
            staleness_threshold_seconds=self.settings.scorecard_polling_interval_seconds * 3,
        )
        
        # Score parsers per match
        self._parsers: Dict[str, ScoreParser] = {}
        
        # Manager state
        self._running = False
        self._priority_update_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the fast update manager."""
        if not self.settings.enable_fast_updates:
            logger.info("Fast updates disabled, skipping FastUpdateManager start")
            return
            
        logger.info("Starting FastUpdateManager...")
        self._running = True
        
        # Start priority update loop
        self._priority_update_task = asyncio.create_task(self._priority_update_loop())
        
        logger.info("FastUpdateManager started")

    async def stop(self):
        """Stop the fast update manager."""
        logger.info("Stopping FastUpdateManager...")
        self._running = False
        
        # Cancel priority update task
        if self._priority_update_task:
            self._priority_update_task.cancel()
            try:
                await self._priority_update_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all scorecard poll tasks
        async with self._lock:
            for match_id, state in self._matches.items():
                if state.scorecard_poll_task:
                    state.scorecard_poll_task.cancel()
            self._matches.clear()
        
        logger.info("FastUpdateManager stopped")

    async def register_match(self, match_id: str, url: str, match_type: str = "franchise"):
        """
        Register a match for fast updates.
        
        Args:
            match_id: Unique match identifier
            url: Match URL for scorecard polling
            match_type: Type of match (international, franchise, domestic, club)
        """
        if not self.settings.enable_fast_updates:
            return
            
        async with self._lock:
            if match_id in self._matches:
                return  # Already registered
            
            # Create initial priority
            priority = MatchPriority(
                match_id=match_id,
                viewer_count=100,  # Default, will be updated
                match_phase=MatchPhase.START,
                match_importance=MatchImportance(match_type.lower()),
            )
            
            state = MatchState(
                match_id=match_id,
                url=url,
                priority=priority,
            )
            
            self._matches[match_id] = state
            self._parsers[match_id] = ScoreParser(match_id)
            
            # Start scorecard polling for this match
            state.scorecard_poll_task = asyncio.create_task(
                self._scorecard_poll_loop(match_id)
            )
            
            logger.info(f"[{match_id}] Registered for fast updates")

    async def unregister_match(self, match_id: str):
        """Unregister a match from fast updates."""
        async with self._lock:
            state = self._matches.pop(match_id, None)
            if state:
                state.is_active = False
                if state.scorecard_poll_task:
                    state.scorecard_poll_task.cancel()
            
            self._parsers.pop(match_id, None)
            self._ball_tracker.reset_match(match_id)
            self._sequencer.clear_match(match_id)
            self._scorecard_differ.clear_match(match_id)
            
            logger.info(f"[{match_id}] Unregistered from fast updates")

    def handle_sv3_update(self, match_id: str, data: Dict[str, Any]):
        """
        Handle immediate sV3 update from CrexAdapter callback.
        
        This is called synchronously from the adapter's response handler.
        """
        if not self.settings.enable_fast_updates:
            return
            
        start_time = time.time()
        
        try:
            # Parse sV3 data
            parser = self._parsers.get(match_id)
            if not parser:
                logger.warning(f"[{match_id}] No parser registered, ignoring sV3 update")
                return
            
            score_snapshot, ball_event = parser.parse_sv3_response(data)
            
            # Update match state
            state = self._matches.get(match_id)
            if state:
                state.last_sv3_time = time.time()
                state.consecutive_errors = 0
                state.current_backoff = self.settings.adaptive_polling_min_seconds
            
            # Track ball if present
            if ball_event:
                is_valid, gap_details = self._ball_tracker.track_ball(ball_event)
                if is_valid:
                    self.metrics.record_ball_update(match_id, "success")
                else:
                    self.metrics.record_ball_update(match_id, "gap_detected")
                
                # Enqueue for delivery
                self._sequencer.enqueue_ball(ball_event)
            
            # Enqueue score snapshot
            if score_snapshot:
                self._sequencer.enqueue_score(score_snapshot)
            
            # Record latency
            latency = time.time() - start_time
            self.metrics.record_update_latency(match_id, latency)
            self.metrics.record_immediate_push(match_id, "sv3", "success")
            
            # Deliver immediately if fast updates enabled
            if self.settings.enable_immediate_push and self.on_score_push:
                asyncio.create_task(self._deliver_score_immediate(match_id, data))
                
        except Exception as e:
            logger.error(f"[{match_id}] Error handling sV3 update: {e}")
            self.metrics.record_immediate_push(match_id, "sv3", "failure")

    def handle_sc4_update(self, match_id: str, data: Dict[str, Any]):
        """
        Handle sC4 scorecard update from CrexAdapter callback.
        """
        if not self.settings.enable_fast_updates:
            return
            
        try:
            # Update staleness
            state = self._matches.get(match_id)
            if state:
                state.last_sc4_time = time.time()
            
            staleness = self._scorecard_differ.get_staleness_seconds(match_id, 1)
            self.metrics.update_scorecard_staleness(match_id, staleness)
            self.metrics.record_immediate_push(match_id, "sc4", "success")
            
        except Exception as e:
            logger.error(f"[{match_id}] Error handling sC4 update: {e}")
            self.metrics.record_immediate_push(match_id, "sc4", "failure")

    async def _scorecard_poll_loop(self, match_id: str):
        """
        Dedicated scorecard polling loop for a match.
        
        Runs at scorecard_polling_interval_seconds (default 10s).
        """
        logger.info(f"[{match_id}] Starting scorecard poll loop")
        
        state = self._matches.get(match_id)
        if not state:
            return
            
        while self._running and state.is_active:
            try:
                # Calculate adaptive interval based on errors
                interval = self._calculate_adaptive_interval(state)
                self.metrics.update_adaptive_polling(match_id, interval)
                
                await asyncio.sleep(interval)
                
                # Check staleness
                staleness = time.time() - state.last_sc4_time
                self.metrics.update_scorecard_staleness(match_id, staleness)
                
                # If scorecard is stale, log warning
                if staleness > self.settings.scorecard_polling_interval_seconds * 2:
                    logger.warning(f"[{match_id}] Scorecard stale: {staleness:.1f}s")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{match_id}] Scorecard poll error: {e}")
                state.consecutive_errors += 1
                
                # Apply backoff
                state.current_backoff = min(
                    state.current_backoff * 2,
                    self.settings.adaptive_polling_max_seconds,
                )
                
                await asyncio.sleep(state.current_backoff)
        
        logger.info(f"[{match_id}] Scorecard poll loop stopped")

    async def _priority_update_loop(self):
        """
        Periodically update match priorities.
        """
        while self._running:
            try:
                await asyncio.sleep(30)  # Update priorities every 30s
                
                async with self._lock:
                    for match_id, state in self._matches.items():
                        # Update priority score
                        self.metrics.update_match_priority(
                            match_id,
                            state.priority.priority_score,
                        )
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Priority update loop error: {e}")
                await asyncio.sleep(5)

    def _calculate_adaptive_interval(self, state: MatchState) -> float:
        """
        Calculate adaptive polling interval with jitter.
        
        Uses exponential backoff on errors, with random jitter to prevent thundering herd.
        """
        # Base interval from priority
        base_interval = state.priority.polling_interval_seconds
        
        # Apply backoff if there are errors
        if state.consecutive_errors > 0:
            backoff = min(
                state.current_backoff * (2 ** state.consecutive_errors),
                self.settings.adaptive_polling_max_seconds,
            )
            base_interval = max(base_interval, backoff)
        
        # Add jitter (±20%)
        jitter = random.uniform(-0.2, 0.2) * base_interval
        interval = base_interval + jitter
        
        # Clamp to configured bounds
        return max(
            self.settings.adaptive_polling_min_seconds,
            min(interval, self.settings.adaptive_polling_max_seconds),
        )

    async def _deliver_score_immediate(self, match_id: str, data: Dict):
        """Deliver score update immediately to backend."""
        if self.on_score_push:
            try:
                success = await asyncio.to_thread(self.on_score_push, match_id, data)
                if success:
                    self.metrics.record_score_update(match_id, "immediate")
                else:
                    logger.warning(f"[{match_id}] Immediate score push failed")
            except Exception as e:
                logger.error(f"[{match_id}] Error in immediate score push: {e}")

    def _deliver_update(self, update_type: str, update: Any):
        """Callback from UpdateSequencer when update is ready."""
        match_id = update.match_id if hasattr(update, 'match_id') else "unknown"
        logger.debug(f"[{match_id}] Delivering {update_type} update")
        self.metrics.record_score_update(match_id, "sequenced")

    def _handle_gap_detected(self, match_id: str, details: str):
        """Callback when ball gap is detected."""
        logger.warning(f"[{match_id}] Gap detected: {details}")
        self.metrics.record_ball_update(match_id, "gap_detected")

    def get_match_states(self) -> Dict[str, Dict]:
        """Get current state of all tracked matches."""
        return {
            match_id: {
                "priority_score": state.priority.priority_score,
                "last_sv3_time": state.last_sv3_time,
                "last_sc4_time": state.last_sc4_time,
                "consecutive_errors": state.consecutive_errors,
                "current_backoff": state.current_backoff,
                "is_active": state.is_active,
            }
            for match_id, state in self._matches.items()
        }

    def get_stats(self) -> Dict:
        """Get overall manager statistics."""
        return {
            "enabled": self.settings.enable_fast_updates,
            "active_matches": len(self._matches),
            "ball_tracker": self._ball_tracker.get_stats(),
            "sequencer": self._sequencer.get_stats(),
            "scorecard_differ": self._scorecard_differ.get_stats(),
        }

    # Public callback methods for adapter integration
    def on_sv3_update(self, match_id: str, data: Dict[str, Any]) -> None:
        """
        Public callback for sV3 updates from CrexAdapter.
        
        This matches the signature expected by CrexAdapter.__init__().
        Feature: 007-fast-updates
        """
        self.handle_sv3_update(match_id, data)

    def on_sc4_update(self, match_id: str, data: Dict[str, Any]) -> None:
        """
        Public callback for sC4 updates from CrexAdapter.
        
        This matches the signature expected by CrexAdapter.__init__().
        Feature: 007-fast-updates
        """
        self.handle_sc4_update(match_id, data)
