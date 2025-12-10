import pytest
import time
from unittest.mock import MagicMock
from crex_scraper_python.src.health import HealthGrader, HealthState

def test_stall_detection_triggers_recovery():
    grader = HealthGrader()
    # Override settings for test (bypass frozen dataclass)
    object.__setattr__(grader.settings, 'staleness_threshold_seconds', 0.1)
    object.__setattr__(grader.settings, 'pause_cooldown', 1.0)
    
    # Initially healthy
    assert grader.state == HealthState.HEALTHY
    
    # Simulate stall
    time.sleep(0.2)
    assert grader.check_stall() is True
    assert grader.state == HealthState.FAILING
    
    # Should trigger recovery
    assert grader.should_trigger_recovery() is True
    
    # Record recovery
    grader.record_recovery_attempt()
    assert grader.state == HealthState.RECOVERING
    assert grader.is_in_cooldown() is True
    
    # Should not trigger recovery again immediately (in cooldown)
    # Even if we are still failing (state might be RECOVERING, but if we force it back to FAILING)
    grader.transition_to(HealthState.FAILING, "Still failing")
    assert grader.should_trigger_recovery() is False
    
    # Wait for cooldown
    time.sleep(1.1)
    assert grader.is_in_cooldown() is False
    assert grader.should_trigger_recovery() is True
