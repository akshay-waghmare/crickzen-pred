"""Structured logging utilities for the cricket scraper.

This package centralises observability helpers so application modules can
initialise JSON logging, bind correlation identifiers, and capture diagnostic
artifacts in a consistent way.
"""

from .adapters import (
    bind_correlation_id,
    clear_correlation_id,
    configure_logging,
    get_logger,
)
from .diagnostics import (
    capture_html_snapshot,
    capture_screenshot,
    capture_state_dump,
    get_artifact_directory,
    prune_expired_artifacts,
)

__all__ = [
    "bind_correlation_id",
    "clear_correlation_id",
    "configure_logging",
    "get_logger",
    "capture_html_snapshot",
    "capture_screenshot",
    "capture_state_dump",
    "get_artifact_directory",
    "prune_expired_artifacts",
]
