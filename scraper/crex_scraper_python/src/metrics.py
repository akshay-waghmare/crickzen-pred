"""
Prometheus Metrics Collector for Scraper.
"""

import logging
from typing import Dict
from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry

logger = logging.getLogger(__name__)

class MetricsCollector:
    """
    Centralized metrics collection for the scraper service.
    """

    def __init__(self, registry: CollectorRegistry = None):
        self.registry = registry or CollectorRegistry(auto_describe=True)
        
        # Freshness
        self.freshness = Gauge(
            'scraper_freshness_seconds',
            'Time since last successful scrape per match',
            ['match_id', 'domain'],
            registry=self.registry
        )

        # Queue & Concurrency
        self.queue_depth = Gauge(
            'scraper_queue_depth',
            'Number of tasks waiting in the scheduler queue',
            registry=self.registry
        )
        self.active_tasks = Gauge(
            'scraper_active_tasks',
            'Number of tasks currently being processed',
            registry=self.registry
        )

        # Counters
        self.scrapes_total = Counter(
            'scraper_scrapes_total',
            'Total number of scrape attempts',
            ['domain', 'status'], # status: success, failure, timeout
            registry=self.registry
        )
        self.domain_failures = Counter(
            'scraper_domain_failures_total',
            'Total number of domain-specific failures',
            ['domain', 'error_type'],
            registry=self.registry
        )

        # Latency
        self.scrape_duration = Histogram(
            'scraper_scrape_duration_seconds',
            'Time taken to complete a scrape task',
            ['domain'],
            buckets=(1, 2.5, 5, 7.5, 10, 15, 20, 30, 60),
            registry=self.registry
        )
        
        # Health
        self.health_score = Gauge(
            'scraper_health_score',
            'Current health score of the scraper (0-100)',
            registry=self.registry
        )
        
        # Resources
        self.browser_restarts = Counter(
            'scraper_browser_restarts_total',
            'Total number of browser/context restarts',
            ['reason'],
            registry=self.registry
        )

        # Fast Updates Metrics (Feature 007)
        self.ball_updates_total = Counter(
            'scraper_ball_updates_total',
            'Total number of ball updates processed',
            ['match_id', 'status'],  # status: success, gap_detected, dropped
            registry=self.registry
        )
        self.ball_gaps_total = Counter(
            'scraper_ball_gaps_total',
            'Total number of ball gaps detected',
            ['match_id'],
            registry=self.registry
        )
        self.score_updates_total = Counter(
            'scraper_score_updates_total',
            'Total number of score updates pushed',
            ['match_id', 'update_type'],  # update_type: immediate, polled
            registry=self.registry
        )
        self.update_latency = Histogram(
            'scraper_update_latency_seconds',
            'Time from sV3 intercept to backend push',
            ['match_id'],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
            registry=self.registry
        )
        self.scorecard_staleness = Gauge(
            'scraper_scorecard_staleness_seconds',
            'Time since last scorecard update per match',
            ['match_id'],
            registry=self.registry
        )
        self.immediate_push_total = Counter(
            'scraper_immediate_push_total',
            'Total number of immediate push operations',
            ['match_id', 'type', 'status'],  # type: sv3, sc4; status: success, failure
            registry=self.registry
        )
        self.match_priority_score = Gauge(
            'scraper_match_priority_score',
            'Current priority score per match',
            ['match_id'],
            registry=self.registry
        )
        self.adaptive_polling_interval = Gauge(
            'scraper_adaptive_polling_interval_seconds',
            'Current adaptive polling interval per match',
            ['match_id'],
            registry=self.registry
        )

        # Persistent Page Pool Metrics (Feature 007 - Phase 2)
        self.persistent_pool_size = Gauge(
            'scraper_persistent_pool_size',
            'Number of persistent pages in the pool',
            registry=self.registry
        )
        self.persistent_page_age = Gauge(
            'scraper_persistent_page_age_seconds',
            'Age of persistent page per match',
            ['match_id'],
            registry=self.registry
        )
        self.fast_poll_latency = Histogram(
            'scraper_fast_poll_latency_ms',
            'Latency of fast poll operations',
            ['source'],  # source: api, page, localStorage
            buckets=(10, 50, 100, 250, 500, 1000, 2500, 5000),
            registry=self.registry
        )
        self.fast_poll_total = Counter(
            'scraper_fast_poll_total',
            'Total number of fast poll operations',
            ['match_id', 'status'],  # status: success, failure, unchanged
            registry=self.registry
        )
        self.persistent_page_errors = Counter(
            'scraper_persistent_page_errors_total',
            'Total number of persistent page errors',
            ['match_id', 'error_type'],
            registry=self.registry
        )

    def record_scrape_result(self, domain: str, status: str, duration: float):
        """Record the outcome of a scrape attempt."""
        self.scrapes_total.labels(domain=domain, status=status).inc()
        self.scrape_duration.labels(domain=domain).observe(duration)

    def update_freshness(self, match_id: str, domain: str, age_seconds: float):
        """Update freshness gauge for a match."""
        self.freshness.labels(match_id=match_id, domain=domain).set(age_seconds)

    def set_queue_metrics(self, depth: int, active: int):
        """Update queue depth and active task counts."""
        self.queue_depth.set(depth)
        self.active_tasks.set(active)

    # Fast Updates Metrics Methods (Feature 007)
    
    def record_ball_update(self, match_id: str, status: str):
        """Record a ball update event."""
        self.ball_updates_total.labels(match_id=match_id, status=status).inc()
        if status == "gap_detected":
            self.ball_gaps_total.labels(match_id=match_id).inc()

    def record_score_update(self, match_id: str, update_type: str):
        """Record a score update push."""
        self.score_updates_total.labels(match_id=match_id, update_type=update_type).inc()

    def record_update_latency(self, match_id: str, latency_seconds: float):
        """Record the latency from intercept to push."""
        self.update_latency.labels(match_id=match_id).observe(latency_seconds)

    def update_scorecard_staleness(self, match_id: str, staleness_seconds: float):
        """Update the scorecard staleness gauge."""
        self.scorecard_staleness.labels(match_id=match_id).set(staleness_seconds)

    def record_immediate_push(self, match_id: str, push_type: str, status: str):
        """Record an immediate push operation."""
        self.immediate_push_total.labels(
            match_id=match_id,
            type=push_type,
            status=status
        ).inc()

    def update_match_priority(self, match_id: str, priority_score: float):
        """Update the priority score for a match."""
        self.match_priority_score.labels(match_id=match_id).set(priority_score)

    def update_adaptive_polling(self, match_id: str, interval_seconds: float):
        """Update the adaptive polling interval for a match."""
        self.adaptive_polling_interval.labels(match_id=match_id).set(interval_seconds)

    # Persistent Page Pool Metrics Methods (Feature 007 - Phase 2)

    def update_pool_size(self, size: int):
        """Update the persistent page pool size."""
        self.persistent_pool_size.set(size)

    def update_page_age(self, match_id: str, age_seconds: float):
        """Update the age of a persistent page."""
        self.persistent_page_age.labels(match_id=match_id).set(age_seconds)

    def record_fast_poll(self, match_id: str, status: str, latency_ms: float, source: str = "api"):
        """Record a fast poll operation."""
        self.fast_poll_total.labels(match_id=match_id, status=status).inc()
        self.fast_poll_latency.labels(source=source).observe(latency_ms)

    def record_persistent_page_error(self, match_id: str, error_type: str):
        """Record a persistent page error."""
        self.persistent_page_errors.labels(match_id=match_id, error_type=error_type).inc()
