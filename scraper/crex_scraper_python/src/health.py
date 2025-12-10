"""
Health Grader and Monitoring for Scraper.
Manages health state, stall detection, and resource monitoring.
"""

import logging
import time
import psutil
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Deque, Dict, Optional
from collections import deque

from .config import get_settings

logger = logging.getLogger(__name__)

class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    RECOVERING = "recovering"

@dataclass
class AuditEntry:
    timestamp: float
    event: str
    details: Dict
    level: str = "INFO"

@dataclass
class HealthSummary:
    state: HealthState
    score: int
    uptime_seconds: float
    pids_count: int
    memory_usage_mb: float
    last_scrape_timestamp: float
    active_matches: int
    details: Dict = field(default_factory=dict)

class HealthGrader:
    """
    Monitors scraper health, detects stalls, and manages audit logs.
    """

    def __init__(self):
        self.settings = get_settings()
        self._state = HealthState.HEALTHY
        self._start_time = time.time()
        self._last_successful_scrape = time.time()
        self._audit_log: Deque[AuditEntry] = deque(maxlen=self.settings.audit_max_entries)
        self._freshness_window: Deque[float] = deque(maxlen=1000) # Keep last 1000 samples
        self._consecutive_failures = 0
        self._process = psutil.Process()
        self._last_recovery_attempt = 0.0
        self._reconciliation_warnings: Deque[str] = deque(maxlen=50)

    @property
    def state(self) -> HealthState:
        return self._state

    def record_reconciliation_warning(self, message: str):
        """Record a reconciliation warning."""
        self._reconciliation_warnings.append(f"{time.time()}: {message}")

    def should_trigger_recovery(self) -> bool:
        """
        Check if automated recovery should be triggered.
        Returns True if in FAILING state and outside cooldown.
        """
        if self._state == HealthState.FAILING:
            if not self.is_in_cooldown():
                return True
        return False

    def is_in_cooldown(self) -> bool:
        """Check if we are in a recovery cooldown period."""
        return (time.time() - self._last_recovery_attempt) < self.settings.pause_cooldown

    def record_recovery_attempt(self):
        """Record that a recovery attempt is starting."""
        self._last_recovery_attempt = time.time()
        self.transition_to(HealthState.RECOVERING, "Automated recovery triggered")

    def record_freshness(self, age_seconds: float):
        """Record data freshness age."""
        self._freshness_window.append(age_seconds)

    def get_freshness_stats(self) -> Dict[str, float]:
        """Calculate freshness percentiles (p50, p90, p99)."""
        if not self._freshness_window:
            return {"p50": 0.0, "p90": 0.0, "p99": 0.0}
        
        data = sorted(list(self._freshness_window))
        n = len(data)
        
        def get_percentile(p: float) -> float:
            k = (n - 1) * p
            f = int(k)
            c = int(k) + 1
            if c >= n:
                return data[n-1]
            d = k - f
            return data[f] * (1 - d) + data[c] * d

        return {
            "p50": get_percentile(0.50),
            "p90": get_percentile(0.90),
            "p99": get_percentile(0.99)
        }

    def record_success(self):
        """Record a successful scrape operation."""
        self._last_successful_scrape = time.time()
        self._consecutive_failures = 0
        if self._state != HealthState.HEALTHY and self._state != HealthState.RECOVERING:
            self.transition_to(HealthState.RECOVERING, "Successful scrape recorded")

    def record_failure(self, error: str):
        """Record a scrape failure."""
        self._consecutive_failures += 1
        self.add_audit_log("scrape_failure", {"error": str(error)}, level="WARNING")
        self._evaluate_state()

    def add_audit_log(self, event: str, details: Dict, level: str = "INFO"):
        """Add an entry to the audit ring buffer."""
        entry = AuditEntry(
            timestamp=time.time(),
            event=event,
            details=details,
            level=level
        )
        self._audit_log.append(entry)
        if level in ("WARNING", "ERROR"):
            logger.warning(f"Audit: {event} - {details}")

    def get_audit_log(self) -> List[AuditEntry]:
        """Get recent audit entries."""
        return list(self._audit_log)

    def check_stall(self) -> bool:
        """
        Check if the scraper has stalled (no success for threshold).
        Returns True if stalled.
        """
        time_since_last = time.time() - self._last_successful_scrape
        is_stalled = time_since_last > self.settings.staleness_threshold_seconds
        
        if is_stalled and self._state != HealthState.FAILING:
            self.transition_to(
                HealthState.FAILING, 
                f"Stall detected: No success for {time_since_last:.1f}s"
            )
        
        return is_stalled

    def get_pids_count(self) -> int:
        """Get current number of PIDs (threads/processes) for this container."""
        try:
            # In Docker, we might want to count all processes in the cgroup or just children
            # For now, counting children of the current process
            return len(self._process.children(recursive=True)) + 1
        except Exception:
            return 0

    def get_memory_usage(self) -> float:
        """Get memory usage in MB."""
        try:
            return self._process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0

    def _evaluate_state(self):
        """Determine current health state based on failures and metrics."""
        # Check failures
        if self._consecutive_failures >= self.settings.failing_error_threshold:
            self.transition_to(HealthState.FAILING, "Too many consecutive failures")
            return
        elif self._consecutive_failures >= self.settings.degraded_error_threshold:
            self.transition_to(HealthState.DEGRADED, "Consecutive failures detected")
            return

        # Check freshness
        stats = self.get_freshness_stats()
        if stats["p90"] > self.settings.degraded_freshness_threshold:
            self.transition_to(HealthState.DEGRADED, f"Freshness lag: p90={stats['p90']:.1f}s")
            return

        # If we are in a bad state but metrics look good, we might want to recover
        # This logic is typically handled in record_success or a separate recovery check
        if self._state == HealthState.RECOVERING and self._consecutive_failures == 0:
             # Simple recovery: if we just had a success and metrics are okay, go to HEALTHY
             # In a real system we might want N successes.
             self.transition_to(HealthState.HEALTHY, "Recovered")

    def transition_to(self, new_state: HealthState, reason: str):
        """Transition to a new health state."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            self.add_audit_log(
                "state_transition", 
                {"from": old_state, "to": new_state, "reason": reason},
                level="WARNING" if new_state in (HealthState.DEGRADED, HealthState.FAILING) else "INFO"
            )
            logger.info(f"Health transition: {old_state} -> {new_state} ({reason})")

    def get_summary(self) -> HealthSummary:
        """Generate a health summary report."""
        score = 100
        if self._state == HealthState.DEGRADED:
            score = 70
        elif self._state == HealthState.FAILING:
            score = 30
        elif self._state == HealthState.RECOVERING:
            score = 50

        return HealthSummary(
            state=self._state,
            score=score,
            uptime_seconds=time.time() - self._start_time,
            pids_count=self.get_pids_count(),
            memory_usage_mb=self.get_memory_usage(),
            last_scrape_timestamp=self._last_successful_scrape,
            active_matches=0, # To be filled by caller
            details={
                "consecutive_failures": self._consecutive_failures,
                "audit_log_count": len(self._audit_log),
                "freshness": self.get_freshness_stats(),
                "reconciliation_warnings": list(self._reconciliation_warnings)
            }
        )
