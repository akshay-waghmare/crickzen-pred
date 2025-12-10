"""Lifecycle and health tracking for scraper instances."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import urlparse

try:  # Optional dependency for type checking
    import psutil  # type: ignore
except Exception:  # pragma: no cover - psutil is optional during static analysis
    psutil = None  # type: ignore

from ..loggers.adapters import get_logger

from ..config import ScraperSettings, get_settings

try:  # Avoid circular import during type checking
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from .scraper_state import ScraperStateSnapshot
except ImportError:
    TYPE_CHECKING = False  # type: ignore

CleanupCallback = Callable[["ScraperContext"], None]


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


logger = get_logger(component="scraper_context")


@dataclass
class ScraperContext:
    """Tracks runtime state for a single scraper worker."""

    match_id: str
    url: str
    scraper_id: str = field(default_factory=lambda: get_settings().scraper_id)
    settings: ScraperSettings = field(default_factory=get_settings)
    start_time: datetime = field(default_factory=utcnow)
    last_update_time: datetime = field(default_factory=utcnow)
    error_count: int = 0
    total_errors: int = 0
    total_updates: int = 0
    memory_bytes: int = 0
    cpu_percent: float = 0.0
    browser_pid: Optional[int] = None
    total_pids: int = 0  # Count of chromium/playwright related processes observed
    polling_interval: float = field(default_factory=lambda: get_settings().polling_interval_seconds)

    def __post_init__(self) -> None:
        self._lock = threading.RLock()
        self._cleanup_callbacks: List[CleanupCallback] = []
        self._shutdown_time: Optional[datetime] = None
        self._shutdown_event = threading.Event()
        self._shutdown_requested = False
        self._cleanup_ran = False
        self._restart_requested = False
        self._restart_reason: Optional[str] = None
        self._restart_requested_at: Optional[datetime] = None
        self._restart_deadline: Optional[datetime] = None
        self._restart_metadata: Dict[str, object] = {}

    # --- Derived properties -------------------------------------------------

    @property
    def uptime_seconds(self) -> float:
        with self._lock:
            reference = self._shutdown_time or utcnow()
            return (reference - self.start_time).total_seconds()

    @property
    def staleness_seconds(self) -> float:
        with self._lock:
            reference = self._shutdown_time or utcnow()
            return (reference - self.last_update_time).total_seconds()

    @property
    def health_status(self) -> str:
        staleness = self.staleness_seconds
        if self.shutdown_requested:
            return "stopping"
        if self.memory_bytes >= self.settings.memory_hard_limit_mb * 1024 * 1024:
            return "failing"
        if self.error_count >= self.settings.failing_error_threshold:
            return "failing"
        if staleness >= self.settings.staleness_threshold_seconds:
            return "failing"
        if self.error_count >= self.settings.degraded_error_threshold:
            return "degraded"
        if staleness >= self.settings.degraded_staleness_seconds:
            return "degraded"
        return "healthy"

    @property
    def shutdown_requested(self) -> bool:
        with self._lock:
            return self._shutdown_requested

    @property
    def is_shutdown(self) -> bool:
        with self._lock:
            return self._shutdown_time is not None

    @property
    def shutdown_event(self) -> threading.Event:
        return self._shutdown_event

    @property
    def restart_requested(self) -> bool:
        with self._lock:
            return self._restart_requested

    @property
    def restart_reason(self) -> Optional[str]:
        with self._lock:
            return self._restart_reason

    @property
    def restart_requested_at(self) -> Optional[datetime]:
        with self._lock:
            return self._restart_requested_at

    @property
    def restart_deadline(self) -> Optional[datetime]:
        with self._lock:
            return self._restart_deadline

    @property
    def restart_metadata(self) -> Dict[str, object]:
        with self._lock:
            return dict(self._restart_metadata)

    @property
    def memory_restart_scheduled(self) -> bool:
        with self._lock:
            return self._restart_requested and self._restart_reason == "memory_soft_limit"

    @property
    def memory_restart_deadline(self) -> Optional[datetime]:
        with self._lock:
            if self._restart_requested and self._restart_reason == "memory_soft_limit":
                return self._restart_deadline
            return None

    # --- State mutation -----------------------------------------------------

    def record_update(self, *, timestamp: Optional[datetime] = None) -> None:
        ts = timestamp or utcnow()
        with self._lock:
            self.last_update_time = ts
            self.error_count = 0
            self.total_updates += 1

    def record_error(self) -> None:
        with self._lock:
            self.error_count += 1
            self.total_errors += 1

    def update_resource_usage(self, process_pid: Optional[int] = None) -> None:
        if psutil is None:
            self._maybe_schedule_memory_restart()
            return
        pid = process_pid or self.browser_pid
        rss = None
        cpu = None
        if pid is not None:
            try:
                process = psutil.Process(pid)
                rss = process.memory_info().rss
                cpu = process.cpu_percent(interval=0.0)
            except psutil.Error:
                with self._lock:
                    self.browser_pid = None
        # Independent PID scan to catch leaks even if browser_pid missing
        try:
            chrome_like = 0
            for proc in psutil.process_iter(['name', 'cmdline']):
                name = (proc.info.get('name') or '').lower()
                cmd = ' '.join(proc.info.get('cmdline') or []).lower()
                if 'chrome' in name or 'chromium' in name or 'playwright' in cmd:
                    chrome_like += 1
            with self._lock:
                self.total_pids = chrome_like
                if rss is not None:
                    self.memory_bytes = rss
                if cpu is not None:
                    self.cpu_percent = cpu if cpu is not None else self.cpu_percent
        except Exception:
            pass
        self._maybe_schedule_memory_restart(current_memory_bytes=self.memory_bytes, now=utcnow())
        # Per-context PID restart removed - using periodic container restart instead

    def update_memory_bytes(self, memory_bytes: int) -> None:
        with self._lock:
            self.memory_bytes = memory_bytes
        self._maybe_schedule_memory_restart(current_memory_bytes=memory_bytes, now=utcnow())

    def set_browser_pid(self, pid: int) -> None:
        with self._lock:
            self.browser_pid = pid

    def set_polling_interval(self, interval_seconds: float) -> None:
        with self._lock:
            self.polling_interval = interval_seconds

    def request_restart(
        self,
        reason: str,
        *,
        grace_seconds: Optional[int] = None,
        now: Optional[datetime] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> bool:
        """Request a graceful restart for the scraper."""

        now = now or utcnow()
        grace = grace_seconds if grace_seconds is not None else self.settings.memory_restart_grace_seconds
        deadline = now + timedelta(seconds=grace)
        extra = dict(metadata or {})

        with self._lock:
            if self._restart_requested or self._shutdown_requested:
                return False
            self._restart_requested = True
            self._restart_reason = reason
            self._restart_requested_at = now
            self._restart_deadline = deadline
            self._restart_metadata = extra

        logger.warning(
            "scraper.restart.requested",
            metadata={
                "match_id": self.match_id,
                "reason": reason,
                "deadline": deadline.isoformat(),
                "grace_seconds": grace,
                **extra,
            },
        )

        self.request_shutdown()
        return True

    def _maybe_schedule_memory_restart(
        self,
        *,
        current_memory_bytes: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> bool:
        threshold_bytes = self.settings.memory_soft_limit_mb * 1024 * 1024
        memory = current_memory_bytes if current_memory_bytes is not None else self.memory_bytes
        if memory < threshold_bytes:
            return False

        metadata = {
            "memory_bytes": int(memory),
            "memory_mb": round(memory / 1024 / 1024, 2),
            "soft_limit_mb": self.settings.memory_soft_limit_mb,
            "soft_limit_bytes": threshold_bytes,
        }

        return self.request_restart(
            "memory_soft_limit",
            grace_seconds=self.settings.memory_restart_grace_seconds,
            now=now,
            metadata=metadata,
        )

    def _maybe_schedule_pid_restart(
        self,
        *,
        now: Optional[datetime] = None,
    ) -> bool:
        threshold = self.settings.pid_restart_threshold
        with self._lock:
            current = self.total_pids
        
        logger.debug(
            f"[PID_RESTART_CHECK] match_id={self.match_id} current_pids={current} "
            f"threshold={threshold} restart_requested={self._restart_requested}"
        )
        
        if current < threshold:
            logger.debug(f"[PID_RESTART_CHECK] Below threshold, not restarting (current={current} < threshold={threshold})")
            return False
        
        # PID threshold exceeded - trigger graceful container restart
        logger.critical(
            f"[PID_THRESHOLD_EXCEEDED] match_id={self.match_id} current_pids={current} exceeds threshold={threshold}. "
            "Triggering graceful container restart."
        )
        metadata = {"pids": current, "threshold": threshold, "action": "graceful_container_restart"}
        
        # Log structured event
        logger.error("pid_threshold_exceeded", metadata=metadata)
        
        # Trigger graceful container restart (handled by main module)
        self._trigger_container_restart(metadata)
        return True
    
    def _trigger_container_restart(self, metadata: dict) -> None:
        """Signal that container should gracefully restart due to PID threshold."""
        import threading
        import time
        import os
        
        def graceful_exit():
            # Mark container as unhealthy immediately (503 responses)
            try:
                from ..crex_main_url import CONTAINER_UNHEALTHY
                CONTAINER_UNHEALTHY.set()
                logger.warning("container_marked_unhealthy", metadata=metadata)
            except Exception:
                pass  # Module may not be imported yet
            
            # Wait briefly for health checks to propagate and clients to detect unhealthy state
            logger.info("waiting_for_health_check_propagation", metadata={"wait_seconds": 10})
            time.sleep(10)
            
            # Now exit - Docker will restart container (use os._exit to exit entire process, not just thread)
            logger.critical("exiting_container_for_restart", metadata=metadata)
            os._exit(1)
        
        # Run in background thread so we can return immediately
        threading.Thread(target=graceful_exit, daemon=False).start()

    # --- Lifecycle ----------------------------------------------------------

    def should_restart(self, *, now: Optional[datetime] = None) -> bool:
        reference = now or utcnow()
        with self._lock:
            if self._shutdown_requested:
                return False
            age = (reference - self.start_time).total_seconds()
            staleness = (reference - self.last_update_time).total_seconds()
            if age >= self.settings.max_lifetime_seconds:
                return True
            if staleness >= self.settings.staleness_threshold_seconds:
                return True
            if self.error_count >= self.settings.max_consecutive_errors:
                return True
            if self.memory_bytes >= self.settings.memory_soft_limit_mb * 1024 * 1024:
                return True
            return False

    def mark_shutdown(self) -> None:
        with self._lock:
            if self._shutdown_time is None:
                self._shutdown_time = utcnow()

    def register_cleanup(self, callback: CleanupCallback) -> None:
        with self._lock:
            self._cleanup_callbacks.append(callback)

    def run_cleanup(self) -> None:
        callbacks: Iterable[CleanupCallback]
        with self._lock:
            if self._cleanup_ran:
                return
            callbacks = list(self._cleanup_callbacks)
            self._cleanup_ran = True
        for callback in callbacks:
            try:
                callback(self)
            except Exception:
                # Cleanup should never raise; swallow to ensure others run
                continue

    def request_shutdown(self) -> None:
        with self._lock:
            self._shutdown_requested = True

    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        return self._shutdown_event.wait(timeout)

    def shutdown(self) -> None:
        with self._lock:
            if not self._shutdown_requested:
                self._shutdown_requested = True
        self.mark_shutdown()
        self.run_cleanup()
        self._shutdown_event.set()

    # --- Serialization ------------------------------------------------------

    def to_health_payload(self) -> dict[str, object]:
        with self._lock:
            restart_requested = self._restart_requested
            restart_reason = self._restart_reason
            restart_requested_at_dt = self._restart_requested_at
            restart_deadline_dt = self._restart_deadline
            restart_metadata = dict(self._restart_metadata)
            memory_restart_scheduled = restart_requested and restart_reason == "memory_soft_limit"
            return {
                "scraper_id": self.scraper_id,
                "match_id": self.match_id,
                "url": self.url,
                "start_time": self.start_time.isoformat(),
                "last_update": self.last_update_time.isoformat(),
                "uptime_seconds": round(self.uptime_seconds, 2),
                "staleness_seconds": round(self.staleness_seconds, 2),
                "error_count": self.error_count,
                "total_errors": self.total_errors,
                "total_updates": self.total_updates,
                "status": self.health_status,
                "memory_mb": round(self.memory_bytes / 1024 / 1024, 2),
                "cpu_percent": round(self.cpu_percent, 2),
                "total_pids": self.total_pids,
                "polling_interval": self.polling_interval,
                "shutdown_requested": self._shutdown_requested,
                "is_shutdown": self._shutdown_time is not None,
                "memory_soft_limit_mb": self.settings.memory_soft_limit_mb,
                "memory_restart_grace_seconds": self.settings.memory_restart_grace_seconds,
                "restart_requested": restart_requested,
                "restart_reason": restart_reason,
                "restart_requested_at": restart_requested_at_dt.isoformat()
                if restart_requested_at_dt
                else None,
                "restart_deadline": restart_deadline_dt.isoformat()
                if restart_deadline_dt
                else None,
                "restart_metadata": restart_metadata,
                "memory_restart_scheduled": memory_restart_scheduled,
                "memory_restart_deadline": restart_deadline_dt.isoformat()
                if memory_restart_scheduled and restart_deadline_dt
                else None,
            }

    def create_state_snapshot(
        self,
        *,
        last_processed_over: Optional[int] = None,
        last_processed_ball: Optional[int] = None,
        last_score: Optional[str] = None,
        last_wickets: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ScraperStateSnapshot":
        """Create a state snapshot for persistence.
        
        This allows scrapers to save their progress before restart and resume
        from the last known good state, preventing data duplication.
        """
        from .scraper_state import ScraperStateSnapshot

        return ScraperStateSnapshot(
            match_id=self.match_id,
            url=self.url,
            last_processed_over=last_processed_over,
            last_processed_ball=last_processed_ball,
            last_score=last_score,
            last_wickets=last_wickets,
            last_update_timestamp=self.last_update_time.isoformat(),
            metadata=metadata or {},
        )


class ScraperRegistry:
    """Thread-safe registry for scraper contexts."""

    def __init__(self) -> None:
        self._by_match: dict[str, ScraperContext] = {}
        self._by_url: dict[str, ScraperContext] = {}
        self._lock = threading.RLock()

    def register(self, context: ScraperContext) -> ScraperContext:
        with self._lock:
            self._by_match[context.match_id] = context
            self._by_url[context.url] = context
        return context

    def get(self, match_id: str) -> Optional[ScraperContext]:
        with self._lock:
            return self._by_match.get(match_id)

    def get_by_url(self, url: str) -> Optional[ScraperContext]:
        with self._lock:
            return self._by_url.get(url)

    def remove(self, match_id: str) -> Optional[ScraperContext]:
        with self._lock:
            context = self._by_match.pop(match_id, None)
            if context:
                self._by_url.pop(context.url, None)
            return context

    def remove_by_url(self, url: str) -> Optional[ScraperContext]:
        with self._lock:
            context = self._by_url.pop(url, None)
            if context:
                self._by_match.pop(context.match_id, None)
            return context

    def all_contexts(self) -> List[ScraperContext]:
        with self._lock:
            return list(self._by_match.values())

    def clear(self) -> None:
        with self._lock:
            self._by_match.clear()
            self._by_url.clear()

    def __len__(self) -> int:  # pragma: no cover - convenience
        with self._lock:
            return len(self._by_match)


def derive_match_id(url: str) -> str:
    parsed = urlparse(url)
    path = (parsed.path or "").rstrip("/")
    if path:
        candidate = path.split("/")[-1]
        if candidate:
            return candidate
    netloc = parsed.netloc or "scraper"
    sanitized = netloc.replace(":", "-")
    return f"match-{sanitized}"


__all__ = ["ScraperContext", "ScraperRegistry", "derive_match_id", "utcnow"]
