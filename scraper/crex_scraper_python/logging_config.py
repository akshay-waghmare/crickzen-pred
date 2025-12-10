"""Application-wide logging configuration helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from structlog.contextvars import bind_contextvars, unbind_contextvars

from src.logging.adapters import configure_logging as _configure_structlog

from src.config import ScraperSettings, get_settings

try:  # pragma: no cover - typing only
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:  # pragma: no cover - import hints only
        from src.core.scraper_context import ScraperContext
except ImportError:  # pragma: no cover - safety when TYPE_CHECKING unavailable
    TYPE_CHECKING = False  # type: ignore


def setup_logging(
    settings: Optional[ScraperSettings] = None,
    *,
    stream=None,
) -> ScraperSettings:
    """Configure structured logging based on scraper settings."""

    cfg = settings or get_settings()
    fmt = (cfg.log_format or "json").lower()
    indent = 2 if fmt in {"json-pretty", "pretty"} else None

    _configure_structlog(level=cfg.log_level, json_indent=indent, stream=stream)
    bind_contextvars(scraper_id=cfg.scraper_id)
    return cfg


@contextmanager
def scraper_logging_context(
    context: "ScraperContext" | None = None,
    *,
    match_id: Optional[str] = None,
) -> Iterator[None]:
    """Bind match-specific logging context for the duration of the block."""

    resolved_match_id = match_id or (context.match_id if context else None)
    keys_to_unbind: list[str] = []

    if resolved_match_id:
        bind_contextvars(match_id=resolved_match_id)
        keys_to_unbind.append("match_id")

    try:
        yield
    finally:
        if keys_to_unbind:
            unbind_contextvars(*keys_to_unbind)


__all__ = ["setup_logging", "scraper_logging_context"]
