"""Retry helpers with exponential backoff and optional jitter."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Tuple, Type, TypeVar

from ..config import get_settings

T = TypeVar("T")


class RetryError(RuntimeError):
    """Raised when an operation exhausts its retry budget."""


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 5
    base_delay: float = 1.0
    max_delay: float = 16.0
    jitter: float = 0.25
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    logger: Optional[Callable[[dict[str, Any]], None]] = None

    @classmethod
    def from_settings(cls, *, overrides: Optional[dict[str, Any]] = None) -> "RetryConfig":
        settings = get_settings()
        data = {
            "max_attempts": settings.retry_max_attempts,
            "base_delay": settings.retry_base_delay_seconds,
            "max_delay": settings.retry_max_delay_seconds,
            "jitter": settings.retry_jitter_seconds,
        }
        if overrides:
            data.update(overrides)
        return cls(**data)  # type: ignore[arg-type]


def _compute_delay(attempt: int, config: RetryConfig) -> float:
    exponential = config.base_delay * (2 ** (attempt - 1))
    return min(exponential, config.max_delay)


def retryable(
    *,
    config: Optional[RetryConfig] = None,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that retries sync function calls with exponential backoff."""

    retry_config = config or RetryConfig.from_settings()

    if retry_config.max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapped(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            last_exception: Optional[Exception] = None

            while attempt < retry_config.max_attempts:
                try:
                    return func(*args, **kwargs)
                except retry_config.retry_exceptions as exc:  # type: ignore[misc]
                    attempt += 1
                    last_exception = exc
                    if attempt >= retry_config.max_attempts:
                        break

                    delay = _compute_delay(attempt, retry_config)
                    jitter = retry_config.jitter * rng()
                    total_delay = delay + jitter

                    if retry_config.logger:
                        retry_config.logger(
                            {
                                "event": "retry",
                                "function": getattr(func, "__name__", "<callable>"),
                                "attempt": attempt,
                                "max_attempts": retry_config.max_attempts,
                                "delay": total_delay,
                                "base_delay": delay,
                                "jitter": jitter,
                                "error_type": exc.__class__.__name__,
                                "error": str(exc),
                            }
                        )

                    if on_retry:
                        on_retry(attempt, exc, total_delay)

                    sleep(total_delay)
                except Exception:
                    raise

            raise RetryError(
                f"Operation {getattr(func, '__name__', '<callable>')} failed after {retry_config.max_attempts} attempts"
            ) from last_exception

        return wrapped

    return decorator


__all__ = ["RetryConfig", "RetryError", "retryable"]
