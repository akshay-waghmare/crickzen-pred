import pytest
from collections import deque
from crex_scraper_python.src.health import HealthGrader

def test_audit_ring_buffer_trim():
    grader = HealthGrader()
    # Override settings
    object.__setattr__(grader.settings, 'audit_max_entries', 5)
    # Re-initialize deque to pick up new maxlen
    grader._audit_log = deque(maxlen=5)
    
    # Add more entries than capacity
    for i in range(10):
        grader.add_audit_log("test_event", {"index": i})
        
    log = grader.get_audit_log()
    
    # Verify size cap
    assert len(log) == 5
    
    # Verify FIFO behavior (oldest dropped)
    assert log[0].details["index"] == 5
    assert log[-1].details["index"] == 9
