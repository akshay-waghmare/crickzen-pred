"""
Async Scheduler for managing scrape tasks with priority.
Handles task queuing, prioritization, and distribution.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Dict, Set

from .config import get_settings
from .adapters.rate_limit import TokenBucket

logger = logging.getLogger(__name__)

class TaskPriority(IntEnum):
    LIVE = 1
    IMMINENT = 2
    COMPLETED = 3
    BACKGROUND = 4

@dataclass(order=True)
class ScrapeTask:
    priority: int
    match_id: str = field(compare=False)
    url: str = field(compare=False)
    task_type: str = field(compare=False)  # LIVE, IMMINENT, COMPLETED
    timestamp: float = field(compare=False, default_factory=time.time)
    retry_count: int = field(compare=False, default=0)

class AsyncScheduler:
    """
    Priority-based scheduler for scrape tasks.
    """

    def __init__(self):
        self.settings = get_settings()
        self._queue: Optional[asyncio.PriorityQueue] = None
        self._active_tasks: Set[str] = set()  # Track active match_ids to prevent duplicates
        self._lock: Optional[asyncio.Lock] = None
        self._shutting_down = False
        self.rate_limiter = TokenBucket(
            capacity=self.settings.rate_limit_burst,
            refill_rate=self.settings.rate_limit_tokens_per_sec
        )

    async def setup(self):
        """Initialize asyncio primitives."""
        if self._queue is None:
            self._queue = asyncio.PriorityQueue(maxsize=self.settings.max_queue_size)
        if self._lock is None:
            self._lock = asyncio.Lock()

    async def enqueue(self, match_id: str, url: str, task_type: str) -> bool:
        """
        Enqueue a scrape task.
        Returns True if enqueued, False if queue full or duplicate.
        """
        if self._shutting_down:
            return False

        # Determine priority
        priority = TaskPriority.BACKGROUND
        if task_type.upper() == "LIVE":
            priority = TaskPriority.LIVE
        elif task_type.upper() == "IMMINENT":
            priority = TaskPriority.IMMINENT
        elif task_type.upper() == "COMPLETED":
            priority = TaskPriority.COMPLETED

        # Rate limit check (Token Bucket)
        if not self.rate_limiter.consume():
            logger.warning(f"Rate limit exceeded, dropping task {match_id}")
            return False

        async with self._lock:
            if match_id in self._active_tasks:
                # Task already active or queued, skip to prevent pile-up
                # For LIVE matches, we might want to update priority if it was lower, 
                # but for now simple dedup is sufficient.
                return False
            
            if self._queue.full():
                logger.warning(f"Scheduler queue full ({self._queue.qsize()}), dropping task {match_id}")
                return False

            task = ScrapeTask(
                priority=int(priority),
                match_id=match_id,
                url=url,
                task_type=task_type
            )
            
            try:
                self._queue.put_nowait(task)
                self._active_tasks.add(match_id)
                logger.debug(f"Enqueued task: {match_id} ({task_type}) priority={priority}")
                return True
            except asyncio.QueueFull:
                return False

    async def next_task(self) -> ScrapeTask:
        """
        Get the next highest priority task.
        Blocks until a task is available.
        """
        return await self._queue.get()

    async def task_done(self, task: ScrapeTask):
        """
        Mark a task as completed.
        """
        async with self._lock:
            if task.match_id in self._active_tasks:
                self._active_tasks.remove(task.match_id)

    @property
    def qsize(self) -> int:
        """Return current queue size."""
        return self._queue.qsize()

        
        self._queue.task_done()

    async def shutdown(self):
        """Shutdown the scheduler."""
        self._shutting_down = True
        # We don't explicitly clear the queue here as consumers should handle shutdown signal
        logger.info("AsyncScheduler shutdown initiated.")
