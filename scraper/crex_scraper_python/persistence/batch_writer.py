"""Utilities for batching persistence operations."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Deque, List, Optional, Sequence, TypeVar

from ..config import ScraperSettings, get_settings
from ..db_pool import ConnectionPool

T = TypeVar("T")
MetricEmitter = Optional[Callable[[str, dict], None]]


class BatchWriterError(RuntimeError):
    """Raised when a batch flush fails permanently."""


class BatchWriter:
    """Batched write helper with time/size based flush policies."""

    def __init__(
        self,
        pool: ConnectionPool,
        persist_fn: Callable[[object, Sequence[T]], None],
        *,
        settings: Optional[ScraperSettings] = None,
        batch_size: Optional[int] = None,
        flush_interval: Optional[float] = None,
        metric_emitter: MetricEmitter = None,
    ) -> None:
        self._pool = pool
        self._persist_fn = persist_fn
        self._settings = settings or get_settings()
        self._batch_size = batch_size or self._settings.batch_size
        self._flush_interval = flush_interval or self._settings.batch_flush_interval_seconds
        if self._batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if self._flush_interval <= 0:
            raise ValueError("flush_interval must be positive")

        self._metric_emitter = metric_emitter

        self._queue: Deque[T] = deque()
        self._lock = threading.RLock()
        self._flush_trigger = threading.Event()
        self._stop_event = threading.Event()
        self._stats = {
            "queued": 0,
            "flushed": 0,
            "critical": 0,
            "last_flush_duration_ms": 0.0,
            "flush_failures": 0,
        }
        self._last_error: Optional[Exception] = None

        self._worker = threading.Thread(target=self._run, name="BatchWriter", daemon=True)
        self._worker.start()

    # ------------------------------------------------------------------

    def add(self, update: T, *, critical: bool = False) -> None:
        if critical:
            self._persist_immediately(update)
            return

        with self._lock:
            self._queue.append(update)
            self._stats["queued"] += 1
            should_flush_now = len(self._queue) >= self._batch_size

        if should_flush_now:
            self.flush()
        else:
            self._flush_trigger.set()

    # ------------------------------------------------------------------

    def flush(self, *, raise_exceptions: bool = True) -> int:
        batch: List[T]
        with self._lock:
            if not self._queue:
                return 0
            batch = list(self._queue)
            self._queue.clear()

        start = time.perf_counter()
        try:
            self._persist_batch(batch)
        except Exception as exc:
            with self._lock:
                for item in reversed(batch):
                    self._queue.appendleft(item)
                self._stats["flush_failures"] += 1
                self._last_error = exc
            if raise_exceptions:
                raise
            return 0

        duration_ms = (time.perf_counter() - start) * 1000.0
        with self._lock:
            self._stats["flushed"] += len(batch)
            self._stats["last_flush_duration_ms"] = duration_ms
            self._last_error = None

        self._emit_metric(
            "batch_writer.flush",
            {
                "count": len(batch),
                "duration_ms": duration_ms,
            },
        )
        return len(batch)

    # ------------------------------------------------------------------

    def shutdown(self, *, wait: bool = True) -> None:
        self._stop_event.set()
        self._flush_trigger.set()
        if wait and self._worker.is_alive():
            self._worker.join(timeout=self._flush_interval * 2)
        self.flush(raise_exceptions=False)

    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        with self._lock:
            return {
                **self._stats,
                "queued_pending": len(self._queue),
                "last_error": repr(self._last_error) if self._last_error else None,
            }

    # ------------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._flush_trigger.wait(timeout=self._flush_interval)
            self._flush_trigger.clear()
            if self._stop_event.is_set():
                break
            self.flush(raise_exceptions=False)
        # Final flush attempt on shutdown
        self.flush(raise_exceptions=False)

    def _persist_batch(self, batch: Sequence[T]) -> None:
        if not batch:
            return
        with self._pool.get_connection() as connection:
            self._persist_fn(connection, batch)

    def _persist_immediately(self, update: T) -> None:
        with self._pool.get_connection() as connection:
            self._persist_fn(connection, [update])
        with self._lock:
            self._stats["critical"] += 1
        self._emit_metric("batch_writer.critical", {"count": 1})

    def _emit_metric(self, name: str, payload: dict) -> None:
        if self._metric_emitter is not None:
            try:
                self._metric_emitter(name, payload)
            except Exception:
                # Metrics should never break core logic
                pass


__all__ = ["BatchWriter", "BatchWriterError"]
