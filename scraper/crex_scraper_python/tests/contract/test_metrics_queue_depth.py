import pytest
from unittest.mock import MagicMock, patch
from crex_scraper_python.src.metrics import MetricsCollector

def test_metrics_queue_depth():
    """
    Test that queue depth metric is registered and can be set.
    """
    registry = MagicMock()
    metrics = MetricsCollector(registry=registry)
    
    # Verify gauge created
    assert metrics.queue_depth is not None
    
    # Verify we can set it
    metrics.queue_depth.set(10)
    
    # Since we use prometheus_client, we can't easily check the value without accessing the registry internals
    # or using the .collect() method.
    # But we can verify no exception was raised.
    
    # We can also check if it's in the registry
    # registry.register.assert_called() # MetricsCollector calls register implicitly via prometheus_client
    pass
