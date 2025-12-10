"""Prometheus metrics helpers for the scraper service."""

from __future__ import annotations

import threading
from typing import Optional

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    start_http_server,
)

from ..config import ScraperSettings, get_settings

try:  # pragma: no cover - typing-only import
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from ..core.scraper_context import ScraperContext
except ImportError:  # pragma: no cover - mypy safety on partial installs
    TYPE_CHECKING = False  # type: ignore

DEFAULT_LATENCY_BUCKETS: tuple[float, ...] = (
    0.1,
    0.25,
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    30.0,
    60.0,
)

_METRIC_LOCK = threading.Lock()
_METRIC_SERVER_STARTED = False

METRIC_REGISTRY: CollectorRegistry = CollectorRegistry()


def _initialize_metrics(registry: CollectorRegistry) -> dict[str, object]:
    errors = Counter(
        "scraper_errors_total",
        "Total number of scraper errors encountered.",
        ("match_id", "error_type"),
        registry=registry,
    )
    retries = Counter(
        "scraper_retry_attempts_total",
        "Total number of retry attempts performed by operation.",
        ("operation",),
        registry=registry,
    )
    updates = Counter(
        "scraper_updates_total",
        "Total number of successful scraper updates.",
        ("match_id",),
        registry=registry,
    )
    latency = Histogram(
        "scraper_update_latency_seconds",
        "Latency of scraper update cycles in seconds.",
        ("match_id",),
        buckets=DEFAULT_LATENCY_BUCKETS,
        registry=registry,
    )
    memory = Gauge(
        "scraper_memory_bytes",
        "Observed memory usage for a scraper worker in bytes.",
        ("match_id",),
        registry=registry,
    )
    pids = Gauge(
        "scraper_pids_total",
        "Observed process count associated with the scraper worker.",
        ("match_id",),
        registry=registry,
    )
    active = Gauge(
        "active_scrapers_count",
        "Number of active scraper workers registered.",
        registry=registry,
    )
    staleness = Gauge(
        "data_staleness_seconds",
        "Seconds since the scraper last produced fresh data.",
        ("match_id",),
        registry=registry,
    )
    return {
        "errors": errors,
        "retries": retries,
        "updates": updates,
        "latency": latency,
        "memory": memory,
        "pids": pids,
        "active": active,
        "staleness": staleness,
    }


_metrics = _initialize_metrics(METRIC_REGISTRY)
SCRAPER_ERRORS_TOTAL: Counter = _metrics["errors"]  # type: ignore[assignment]
SCRAPER_RETRY_ATTEMPTS_TOTAL: Counter = _metrics["retries"]  # type: ignore[assignment]
SCRAPER_UPDATES_TOTAL: Counter = _metrics["updates"]  # type: ignore[assignment]
SCRAPER_UPDATE_LATENCY_SECONDS: Histogram = _metrics["latency"]  # type: ignore[assignment]
SCRAPER_MEMORY_BYTES: Gauge = _metrics["memory"]  # type: ignore[assignment]
SCRAPER_PIDS_TOTAL: Gauge = _metrics["pids"]  # type: ignore[assignment]
ACTIVE_SCRAPERS_COUNT: Gauge = _metrics["active"]  # type: ignore[assignment]
DATA_STALENESS_SECONDS: Gauge = _metrics["staleness"]  # type: ignore[assignment]


def ensure_metrics_server(settings: Optional[ScraperSettings] = None) -> bool:
    """Start the Prometheus metrics HTTP server if enabled."""

    cfg = settings or get_settings()
    if not cfg.enable_prometheus_metrics:
        return False

    global _METRIC_SERVER_STARTED
    with _METRIC_LOCK:
        if _METRIC_SERVER_STARTED:
            return False
        start_http_server(
            cfg.prometheus_port,
            addr=cfg.prometheus_host,
            registry=METRIC_REGISTRY,
        )
        _METRIC_SERVER_STARTED = True
        return True


def record_scraper_error(match_id: str, error_type: str) -> None:
    SCRAPER_ERRORS_TOTAL.labels(match_id=match_id, error_type=error_type).inc()


def record_scraper_retry(operation: str) -> None:
    SCRAPER_RETRY_ATTEMPTS_TOTAL.labels(operation=operation).inc()


def record_scraper_update(match_id: str, *, latency_seconds: Optional[float] = None) -> None:
    SCRAPER_UPDATES_TOTAL.labels(match_id=match_id).inc()
    if latency_seconds is not None:
        SCRAPER_UPDATE_LATENCY_SECONDS.labels(match_id=match_id).observe(
            max(latency_seconds, 0.0)
        )
    set_data_staleness(match_id, 0.0)


def set_scraper_memory(match_id: str, memory_bytes: float) -> None:
    SCRAPER_MEMORY_BYTES.labels(match_id=match_id).set(max(memory_bytes, 0.0))


def set_data_staleness(match_id: str, staleness_seconds: float) -> None:
    DATA_STALENESS_SECONDS.labels(match_id=match_id).set(max(staleness_seconds, 0.0))


def set_active_scrapers(count: int) -> None:
    ACTIVE_SCRAPERS_COUNT.set(max(count, 0))


def clear_scraper_gauges(match_id: str) -> None:
    for gauge in (SCRAPER_MEMORY_BYTES, DATA_STALENESS_SECONDS):
        try:
            gauge.remove(match_id)
        except KeyError:
            continue


def update_context_metrics(context: "ScraperContext") -> None:
    set_scraper_memory(context.match_id, float(context.memory_bytes))
    set_data_staleness(context.match_id, float(context.staleness_seconds))
    try:
        SCRAPER_PIDS_TOTAL.labels(match_id=context.match_id).set(max(int(getattr(context, "total_pids", 0)), 0))
    except Exception:
        pass


def reset_metrics_for_tests() -> None:
    global METRIC_REGISTRY
    global SCRAPER_ERRORS_TOTAL
    global SCRAPER_RETRY_ATTEMPTS_TOTAL
    global SCRAPER_UPDATES_TOTAL
    global SCRAPER_UPDATE_LATENCY_SECONDS
    global SCRAPER_MEMORY_BYTES
    global ACTIVE_SCRAPERS_COUNT
    global DATA_STALENESS_SECONDS
    global _METRIC_SERVER_STARTED

    with _METRIC_LOCK:
        METRIC_REGISTRY = CollectorRegistry()
        metrics = _initialize_metrics(METRIC_REGISTRY)
        SCRAPER_ERRORS_TOTAL = metrics["errors"]  # type: ignore[assignment]
        SCRAPER_RETRY_ATTEMPTS_TOTAL = metrics["retries"]  # type: ignore[assignment]
        SCRAPER_UPDATES_TOTAL = metrics["updates"]  # type: ignore[assignment]
        SCRAPER_UPDATE_LATENCY_SECONDS = metrics["latency"]  # type: ignore[assignment]
        SCRAPER_MEMORY_BYTES = metrics["memory"]  # type: ignore[assignment]
        ACTIVE_SCRAPERS_COUNT = metrics["active"]  # type: ignore[assignment]
        DATA_STALENESS_SECONDS = metrics["staleness"]  # type: ignore[assignment]
        _METRIC_SERVER_STARTED = False


__all__ = [
    "ensure_metrics_server",
    "record_scraper_error",
    "record_scraper_retry",
    "record_scraper_update",
    "set_scraper_memory",
    "set_data_staleness",
    "set_active_scrapers",
    "clear_scraper_gauges",
    "update_context_metrics",
    "reset_metrics_for_tests",
    "SCRAPER_RETRY_ATTEMPTS_TOTAL",
    "METRIC_REGISTRY",
    "SCRAPER_ERRORS_TOTAL",
    "SCRAPER_UPDATES_TOTAL",
    "SCRAPER_UPDATE_LATENCY_SECONDS",
    "SCRAPER_MEMORY_BYTES",
    "SCRAPER_PIDS_TOTAL",
    "ACTIVE_SCRAPERS_COUNT",
    "DATA_STALENESS_SECONDS",
]
