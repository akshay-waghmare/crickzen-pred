"""Core resilience modules for the scraper system."""

from .circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from .retry_utils import RetryConfig, RetryError, retryable
from .scraper_context import ScraperContext, ScraperRegistry
from .scraper_state import ScraperStateSnapshot, StateStore
from .cleanup_orphans import (
    find_orphaned_chromium_processes,
    terminate_processes,
    cleanup_orphans_once,
    start_cleanup_thread,
    stop_cleanup_thread,
)
from .fast_update_manager import FastUpdateManager, MatchState

__all__ = [
    # Circuit breaker
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    # Retry utilities
    "RetryConfig",
    "RetryError",
    "retryable",
    # Scraper context
    "ScraperContext",
    "ScraperRegistry",
    # State management
    "ScraperStateSnapshot",
    "StateStore",
    # Cleanup
    "find_orphaned_chromium_processes",
    "terminate_processes",
    "cleanup_orphans_once",
    "start_cleanup_thread",
    "stop_cleanup_thread",
    # Fast updates
    "FastUpdateManager",
    "MatchState",
]
