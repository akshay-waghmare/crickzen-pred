import pytest
from crex_scraper_python.src.metrics import MetricsCollector

def test_recovery_metrics_increment():
    metrics = MetricsCollector()
    
    # Initial value
    initial = metrics.browser_restarts.labels(reason="stall_recovery")._value.get()
    assert initial == 0
    
    # Increment
    metrics.browser_restarts.labels(reason="stall_recovery").inc()
    
    # Verify
    current = metrics.browser_restarts.labels(reason="stall_recovery")._value.get()
    assert current == 1
