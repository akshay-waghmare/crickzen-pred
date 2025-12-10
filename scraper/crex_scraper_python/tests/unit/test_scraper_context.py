import time
from datetime import datetime, timedelta, timezone

import pytest

import src.core.scraper_context as scraper_context_module

from src.config import ScraperSettings
from src.core.scraper_context import ScraperContext, ScraperRegistry, derive_match_id


def build_settings(**overrides):
    data = ScraperSettings().to_dict()
    data.update(overrides)
    return ScraperSettings(**data)


def test_should_restart_triggers_on_age():
    settings = build_settings(max_lifetime_hours=0.001)  # ~3.6 seconds
    context = ScraperContext(match_id="match-1", url="https://example.com", settings=settings)
    context.start_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    assert context.should_restart()


def test_should_restart_triggers_on_staleness():
    settings = build_settings(staleness_threshold_seconds=60)
    context = ScraperContext(match_id="match-2", url="https://example.com", settings=settings)
    past = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
    context.last_update_time = past
    assert context.should_restart(now=datetime.now(tz=timezone.utc))


def test_should_restart_triggers_on_error_threshold():
    settings = build_settings(max_consecutive_errors=3)
    context = ScraperContext(match_id="match-3", url="https://example.com", settings=settings)
    context.error_count = 3
    assert context.should_restart()


def test_health_status_transitions():
    settings = build_settings(
        staleness_threshold_seconds=300,
        degraded_staleness_seconds=120,
        degraded_error_threshold=2,
        failing_error_threshold=4,
    )
    context = ScraperContext(match_id="match-4", url="https://example.com", settings=settings)

    # Healthy state
    assert context.health_status == "healthy"

    # Degraded via errors
    context.error_count = 2
    assert context.health_status == "degraded"

    # Failing via errors
    context.error_count = 5
    assert context.health_status == "failing"

    # Reset errors and make staleness degrade/fail
    context.error_count = 0
    context.last_update_time = datetime.now(tz=timezone.utc) - timedelta(seconds=200)
    assert context.health_status == "degraded"
    context.last_update_time = datetime.now(tz=timezone.utc) - timedelta(seconds=500)
    assert context.health_status == "failing"


def test_record_update_resets_error_count():
    context = ScraperContext(match_id="match-5", url="https://example.com")
    context.error_count = 5
    context.record_update()
    assert context.error_count == 0
    assert context.total_updates == 1


def test_run_cleanup_executes_callbacks():
    context = ScraperContext(match_id="match-6", url="https://example.com")
    executed = []

    def cb(instance):
        executed.append(instance.match_id)

    context.register_cleanup(cb)
    context.run_cleanup()
    context.run_cleanup()
    assert executed == ["match-6"]


def test_mark_shutdown_freezes_uptime():
    context = ScraperContext(match_id="match-7", url="https://example.com")
    context.mark_shutdown()
    before = context.uptime_seconds
    time.sleep(0.01)
    # Uptime should not drift after shutdown marker
    assert context.uptime_seconds == pytest.approx(before, abs=0.01)


def test_request_shutdown_disables_restart_logic():
    context = ScraperContext(match_id="match-shutdown", url="https://example.com")
    context.request_shutdown()
    assert context.shutdown_requested is True
    assert context.should_restart(now=datetime.now(tz=timezone.utc)) is False
    assert context.health_status == "stopping"


def test_shutdown_sets_event_and_runs_cleanup_once():
    context = ScraperContext(match_id="match-clean", url="https://example.com")
    executed = []

    def cb(instance):
        executed.append(instance.match_id)

    context.register_cleanup(cb)
    context.shutdown()
    assert context.is_shutdown is True
    assert context.wait_for_shutdown(timeout=0.01) is True
    assert executed == ["match-clean"]
    # Subsequent shutdowns should be no-ops
    context.shutdown()
    assert executed == ["match-clean"]


def test_to_health_payload_matches_schema():
    context = ScraperContext(match_id="match-8", url="https://example.com/match/123")
    payload = context.to_health_payload()
    assert payload["match_id"] == "match-8"
    assert "status" in payload
    assert "memory_mb" in payload
    assert "uptime_seconds" in payload
    assert payload["shutdown_requested"] is False
    assert payload["is_shutdown"] is False
    assert payload["restart_requested"] is False
    assert payload["memory_restart_scheduled"] is False
    assert payload["restart_metadata"] == {}
    assert payload["memory_restart_deadline"] is None


def test_memory_soft_limit_triggers_restart(monkeypatch):
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(scraper_context_module, "utcnow", lambda: base_time)
    settings = build_settings(memory_soft_limit_mb=1, memory_restart_grace_seconds=30)
    context = ScraperContext(match_id="match-memory", url="https://example.com/memory", settings=settings)

    context.update_memory_bytes(2 * 1024 * 1024)

    assert context.restart_requested is True
    assert context.restart_reason == "memory_soft_limit"
    assert context.memory_restart_scheduled is True
    expected_deadline = base_time + timedelta(seconds=30)
    assert context.memory_restart_deadline == expected_deadline

    payload = context.to_health_payload()
    assert payload["restart_requested"] is True
    assert payload["restart_reason"] == "memory_soft_limit"
    assert payload["memory_restart_scheduled"] is True
    assert payload["memory_restart_deadline"] == expected_deadline.isoformat()
    assert payload["restart_metadata"]["memory_mb"] == pytest.approx(2.0, rel=1e-3)
    assert payload["restart_metadata"]["soft_limit_mb"] == 1


def test_memory_restart_not_rescheduled_if_already_requested(monkeypatch):
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(scraper_context_module, "utcnow", lambda: base_time)
    settings = build_settings(memory_soft_limit_mb=1, memory_restart_grace_seconds=40)
    context = ScraperContext(match_id="match-memory-2", url="https://example.com/memory/2", settings=settings)

    context.update_memory_bytes(2 * 1024 * 1024)
    first_deadline = context.memory_restart_deadline

    later_time = base_time + timedelta(seconds=10)
    monkeypatch.setattr(scraper_context_module, "utcnow", lambda: later_time)
    context.update_memory_bytes(3 * 1024 * 1024)

    assert context.memory_restart_deadline == first_deadline
    assert context.restart_requested is True
    assert context.restart_metadata["memory_mb"] == pytest.approx(2.0, rel=1e-3)


def test_scraper_registry_register_and_remove():
    registry = ScraperRegistry()
    context = ScraperContext(match_id="match-9", url="https://example.com/match/9")
    registry.register(context)
    assert registry.get("match-9") is context
    assert registry.get_by_url("https://example.com/match/9") is context
    all_contexts = registry.all_contexts()
    assert len(all_contexts) == 1
    registry.remove("match-9")
    assert registry.get("match-9") is None
    assert registry.get_by_url("https://example.com/match/9") is None


def test_derive_match_id_returns_last_segment():
    assert derive_match_id("https://example.com/a/b/c") == "c"
    assert derive_match_id("https://example.com/").startswith("match-")


def test_create_state_snapshot():
    """ScraperContext can create state snapshots for persistence."""
    context = ScraperContext(match_id="match-snap", url="https://example.com/snap")
    context.record_update()

    snapshot = context.create_state_snapshot(
        last_processed_over=25,
        last_processed_ball=4,
        last_score="250/4",
        last_wickets=4,
        metadata={"innings": 1, "team": "Pakistan"},
    )

    assert snapshot.match_id == "match-snap"
    assert snapshot.url == "https://example.com/snap"
    assert snapshot.last_processed_over == 25
    assert snapshot.last_processed_ball == 4
    assert snapshot.last_score == "250/4"
    assert snapshot.last_wickets == 4
    assert snapshot.metadata["innings"] == 1
    assert snapshot.metadata["team"] == "Pakistan"
    assert snapshot.last_update_timestamp is not None
