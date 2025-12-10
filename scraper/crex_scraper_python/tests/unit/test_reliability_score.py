import pytest
from crex_scraper_python.src.adapters.reliability import ReliabilityTracker

def test_reliability_score_calculation():
    """
    Test reliability score calculation.
    """
    tracker = ReliabilityTracker(window_size=10)
    
    # Initial score 100
    assert tracker.get_score() == 100
    
    # 5 successes, 5 failures
    for _ in range(5):
        tracker.record_success()
    for _ in range(5):
        tracker.record_failure()
        
    assert tracker.get_score() == 50
    
    # Add 5 more successes (should push out first 5 successes if window is 10? No, FIFO)
    # History: S S S S S F F F F F
    # Add S: S S S S F F F F F S (window size 10)
    tracker.record_success()
    # History: S S S S F F F F F S -> 5 successes, 5 failures -> 50%
    
    # Let's fill with failures
    for _ in range(10):
        tracker.record_failure()
        
    assert tracker.get_score() == 0
