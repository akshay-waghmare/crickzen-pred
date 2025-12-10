"""Circuit breaker implementation for scraper resilience."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, TypeVar

from ..config import ScraperSettings, get_settings

T = TypeVar("T")


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a call is attempted while the breaker is open."""


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int
    timeout_seconds: float
    success_threshold: int
    settings: ScraperSettings = field(default_factory=get_settings)

    def __post_init__(self) -> None:
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._lock = threading.RLock()
        self._last_state_change = time.monotonic()
        self._opened_at: Optional[float] = None
        self.total_calls = 0
        self.total_successes = 0
        self.total_failures = 0
        self.total_rejections = 0

    # ------------------------------------------------------------------

    @classmethod
    def from_settings(
        cls,
        name: str,
        settings: Optional[ScraperSettings] = None,
        *,
        overrides: Optional[dict[str, float]] = None,
    ) -> "CircuitBreaker":
        cfg = settings or get_settings()
        data = {
            "failure_threshold": cfg.circuit_breaker_threshold,
            "timeout_seconds": cfg.circuit_breaker_timeout_seconds,
            "success_threshold": cfg.circuit_breaker_success_threshold,
            "settings": cfg,
        }
        if overrides:
            data.update(overrides)
        return cls(name=name, **data)  # type: ignore[arg-type]

    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitBreakerState:
        with self._lock:
            if self._state is CircuitBreakerState.OPEN and self._opened_at is not None:
                if time.monotonic() - self._opened_at >= self.timeout_seconds:
                    self._transition_to(CircuitBreakerState.HALF_OPEN)
            return self._state

    # ------------------------------------------------------------------

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        with self._lock:
            current_state = self.state
            if current_state is CircuitBreakerState.OPEN:
                self.total_rejections += 1
                raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is open")
            self.total_calls += 1

        try:
            result = func(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        else:
            self.record_success()
            return result

    # ------------------------------------------------------------------

    def record_success(self) -> None:
        with self._lock:
            if self._state is CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._transition_to(CircuitBreakerState.CLOSED)
            else:
                self._failure_count = 0
            self.total_successes += 1

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self.total_failures += 1
            if self._state is CircuitBreakerState.HALF_OPEN:
                self._transition_to(CircuitBreakerState.OPEN)
            elif self._failure_count >= self.failure_threshold:
                self._transition_to(CircuitBreakerState.OPEN)

    # ------------------------------------------------------------------

    def _transition_to(self, state: CircuitBreakerState) -> None:
        self._state = state
        self._last_state_change = time.monotonic()
        if state is CircuitBreakerState.OPEN:
            self._opened_at = self._last_state_change
            self._failure_count = 0
            self._success_count = 0
        elif state is CircuitBreakerState.CLOSED:
            self._opened_at = None
            self._failure_count = 0
            self._success_count = 0
        elif state is CircuitBreakerState.HALF_OPEN:
            self._opened_at = None
            self._failure_count = 0
            self._success_count = 0

    # ------------------------------------------------------------------

    def reset(self) -> None:
        with self._lock:
            self._transition_to(CircuitBreakerState.CLOSED)
            self.total_calls = 0
            self.total_successes = 0
            self.total_failures = 0
            self.total_rejections = 0


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitBreakerState",
]
