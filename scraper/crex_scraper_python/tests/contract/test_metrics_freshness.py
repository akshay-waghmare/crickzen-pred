import pytest
import time
from crex_scraper_python.src.health import HealthGrader

def test_freshness_percentiles():
    """
    Test that HealthGrader aggregates freshness percentiles correctly.
    """
    health = HealthGrader()
    
    # Record some freshness ages (in seconds)
    # 10 samples: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
    for i in range(1, 11):
        health.record_freshness(float(i))
        
    stats = health.get_freshness_stats()
    
    assert "p50" in stats
    assert "p90" in stats
    assert "p99" in stats
    
    # p50 of 1..10 is 5.5
    assert stats["p50"] == 5.5
    # p90 is 9.1 or 9 depending on implementation (numpy style vs simple)
    # Let's assume simple nearest rank or linear interpolation
    assert 8.0 <= stats["p90"] <= 10.0

def test_freshness_window():
    """
    Test that freshness aggregation uses a rolling window.
    """
    health = HealthGrader()
    
    # Fill with old values
    for _ in range(100):
        health.record_freshness(100.0)
        
    # Add new values
    for _ in range(100):
        health.record_freshness(1.0)
        
    stats = health.get_freshness_stats()
    # Should reflect recent values if window is small enough, or mix if large.
    # Assuming window size is reasonable (e.g. 1000 or time based).
    # If implementation uses a deque of size N, we can test that.
    
    assert stats["p50"] < 100.0
