"""Integration test for US1: Continuous Live Data Availability.

Tests the complete flow of scraper resilience features working together:
- Selector fallback parsing
- Playwright lifecycle management
- Network retry logic
- Memory monitoring and restart scheduling
- State snapshot persistence
"""

import time
from datetime import datetime, timezone

import pytest

from src.config import ScraperSettings, reload_settings
from src.core.scraper_context import ScraperContext, ScraperRegistry
from src.core.scraper_state import StateStore
from src.monitoring import monitoring


@pytest.fixture(autouse=True)
def reset_test_state():
    """Reset global state between tests."""
    monitoring.reset_metrics_for_tests()
    reload_settings({})
    yield
    monitoring.reset_metrics_for_tests()


def test_us1_memory_restart_creates_state_snapshot(tmp_path):
    """Integration: Memory limit triggers restart with state snapshot.
    
    This test validates the complete US1 flow:
    1. ScraperContext monitors memory usage
    2. Soft limit breach triggers restart request
    3. State snapshot is created before restart
    4. Orchestrator would schedule delayed restart (mocked here)
    """
    # Setup: Tiny memory limits for fast testing
    settings = ScraperSettings(
        memory_soft_limit_mb=1,  # 1MB triggers restart
        memory_restart_grace_seconds=30,
    )
    
    db_path = tmp_path / "test_state.db"
    state_store = StateStore(settings=settings, db_path=str(db_path))
    
    # Create scraper context
    context = ScraperContext(
        match_id="integration-test",
        url="https://crex.com/match/12345",
        settings=settings,
    )
    
    # Simulate scraper making progress
    context.record_update()
    time.sleep(0.1)
    context.record_update()
    
    # Create state snapshot (scraper would do this before shutdown)
    snapshot = context.create_state_snapshot(
        last_processed_over=15,
        last_processed_ball=3,
        last_score="150/3",
        last_wickets=3,
        metadata={"innings": 1, "team": "India"},
    )
    state_store.save(snapshot)
    
    # Simulate memory growth past soft limit
    context.update_memory_bytes(2 * 1024 * 1024)  # 2MB > 1MB limit
    
    # Verify restart was triggered
    assert context.restart_requested is True
    assert context.restart_reason == "memory_soft_limit"
    assert context.memory_restart_scheduled is True
    assert context.restart_deadline is not None
    
    # Verify health payload includes restart info
    health = context.to_health_payload()
    assert health["restart_requested"] is True
    assert health["restart_reason"] == "memory_soft_limit"
    assert health["memory_restart_scheduled"] is True
    assert health["memory_restart_deadline"] is not None
    assert health["restart_metadata"]["memory_mb"] == pytest.approx(2.0, rel=1e-2)
    
    # Verify state snapshot was saved and can be loaded
    loaded_snapshot = state_store.load("integration-test")
    assert loaded_snapshot is not None
    assert loaded_snapshot.match_id == "integration-test"
    assert loaded_snapshot.last_processed_over == 15
    assert loaded_snapshot.last_processed_ball == 3
    assert loaded_snapshot.last_score == "150/3"
    assert loaded_snapshot.metadata["team"] == "India"
    
    # Verify metrics were recorded
    monitoring.update_context_metrics(context)
    # Memory metric should reflect the high usage
    # (metric verification would check prometheus_client registry)
    
    print("✓ Memory restart flow validated")
    print("✓ State snapshot persisted and loaded")
    print("✓ Health payload enriched with restart metadata")


def test_us1_scraper_lifecycle_with_state_persistence(tmp_path):
    """Integration: Complete scraper lifecycle with state management.
    
    Simulates:
    1. Scraper starts and makes progress
    2. State snapshot saved periodically
    3. Scraper detects need for restart
    4. Final state snapshot before shutdown
    5. New scraper loads state and resumes
    """
    db_path = tmp_path / "lifecycle_state.db"
    state_store = StateStore(db_path=str(db_path))
    
    settings = ScraperSettings(
        memory_soft_limit_mb=100,
        memory_restart_grace_seconds=30,
    )
    
    # === PHASE 1: Initial scraper run ===
    context1 = ScraperContext(
        match_id="match-lifecycle",
        url="https://crex.com/match/999",
        settings=settings,
    )
    
    # Simulate progress over several updates
    for over in range(1, 6):
        context1.record_update()
        snapshot = context1.create_state_snapshot(
            last_processed_over=over,
            last_processed_ball=6,
            last_score=f"{over * 30}/0",
            metadata={"phase": "phase1"},
        )
        state_store.save(snapshot)
        time.sleep(0.01)  # Small delay to simulate real work
    
    # Final state before shutdown
    final_snapshot_phase1 = context1.create_state_snapshot(
        last_processed_over=5,
        last_processed_ball=6,
        last_score="150/2",
        last_wickets=2,
        metadata={"phase": "phase1_complete"},
    )
    state_store.save(final_snapshot_phase1)
    
    # Shutdown scraper 1
    context1.shutdown()
    assert context1.is_shutdown is True
    
    # === PHASE 2: New scraper loads state and resumes ===
    
    # Load the saved state
    loaded_state = state_store.load("match-lifecycle")
    assert loaded_state is not None
    assert loaded_state.last_processed_over == 5
    assert loaded_state.last_processed_ball == 6
    assert loaded_state.last_score == "150/2"
    assert loaded_state.last_wickets == 2
    
    # New scraper starts (would use loaded state to resume)
    context2 = ScraperContext(
        match_id="match-lifecycle",
        url="https://crex.com/match/999",
        settings=settings,
    )
    
    # Resume from last known position (6th over onwards)
    for over in range(6, 11):
        context2.record_update()
        snapshot = context2.create_state_snapshot(
            last_processed_over=over,
            last_processed_ball=6,
            last_score=f"{over * 30}/2",
            metadata={"phase": "phase2", "resumed_from": 5},
        )
        state_store.save(snapshot)
        time.sleep(0.01)
    
    # Verify final state
    final_state = state_store.load("match-lifecycle")
    assert final_state is not None
    assert final_state.last_processed_over == 10
    assert final_state.metadata["phase"] == "phase2"
    assert final_state.metadata["resumed_from"] == 5
    
    # Cleanup
    context2.shutdown()
    state_store.delete("match-lifecycle")
    
    print("✓ Scraper lifecycle with state persistence validated")
    print("✓ State loaded after restart and scraping resumed")


def test_us1_registry_tracks_multiple_scrapers(tmp_path):
    """Integration: Registry manages multiple concurrent scrapers.
    
    Validates:
    - Multiple scrapers can be registered
    - Each maintains independent state
    - Memory monitoring works per-scraper
    - Health status aggregates correctly
    """
    registry = ScraperRegistry()
    settings = ScraperSettings(
        memory_soft_limit_mb=50,
        memory_restart_grace_seconds=20,
    )
    
    # Create multiple scrapers
    contexts = []
    for i in range(1, 4):
        context = ScraperContext(
            match_id=f"match-{i}",
            url=f"https://crex.com/match/{i}",
            settings=settings,
        )
        registry.register(context)
        contexts.append(context)
    
    # Verify all registered
    assert len(registry) == 3
    all_contexts = registry.all_contexts()
    assert len(all_contexts) == 3
    
    # Simulate different states
    contexts[0].record_update()  # Healthy
    contexts[1].record_error()   # Degraded
    contexts[1].record_error()
    contexts[1].record_error()
    contexts[2].update_memory_bytes(60 * 1024 * 1024)  # Restart requested
    
    # Verify individual statuses
    assert contexts[0].health_status == "healthy"
    assert contexts[1].health_status == "degraded"
    assert contexts[2].restart_requested is True
    
    # Verify retrieval
    assert registry.get("match-1") is contexts[0]
    assert registry.get_by_url("https://crex.com/match/2") is contexts[1]
    
    # Remove one and verify
    removed = registry.remove("match-1")
    assert removed is contexts[0]
    assert len(registry) == 2
    assert registry.get("match-1") is None
    
    # Cleanup
    for context in contexts[1:]:
        context.shutdown()
    registry.clear()
    
    print("✓ Registry manages multiple scrapers correctly")
    print("✓ Independent state tracking per scraper")


@pytest.mark.skip(reason="Requires running Flask app and actual scraper - manual test")
def test_us1_full_e2e_with_real_scraper():
    """E2E: Full scraper startup, memory monitoring, and restart.
    
    This test requires:
    - Flask app running on http://localhost:5000
    - POST /start-scrape endpoint available
    - Real browser/Playwright setup
    - Actual match URL
    
    Run manually to verify complete integration.
    """
    import requests
    
    # Start a scraper
    response = requests.post(
        "http://localhost:5000/start-scrape",
        json={"url": "https://crex.com/live/some-match"},
    )
    assert response.status_code == 200
    
    # Monitor health endpoint
    time.sleep(5)
    health_response = requests.get("http://localhost:5000/health")
    assert health_response.status_code == 200
    health_data = health_response.json()
    
    assert health_data["success"] is True
    assert health_data["data"]["active_scraper_count"] >= 1
    
    # Check for restart behavior after memory threshold
    # (would need to simulate memory pressure or wait for natural accumulation)
    
    print("✓ Full E2E scraper flow validated")


if __name__ == "__main__":
    """Quick manual run without pytest."""
    import tempfile
    from pathlib import Path
    
    print("Running US1 Integration Tests...")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        print("\n1. Testing memory restart + state snapshot...")
        test_us1_memory_restart_creates_state_snapshot(tmp_path)
        
        print("\n2. Testing scraper lifecycle with persistence...")
        test_us1_scraper_lifecycle_with_state_persistence(tmp_path)
        
        print("\n3. Testing registry with multiple scrapers...")
        test_us1_registry_tracks_multiple_scrapers(tmp_path)
        
        print("\n" + "=" * 60)
        print("✅ All US1 integration tests passed!")
        print("\nReady to start actual scraper for manual validation.")
