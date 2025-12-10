"""Unit tests for scraper state snapshot persistence."""

from pathlib import Path

import pytest

from src.core.scraper_state import ScraperStateSnapshot, StateStore


def test_snapshot_serialization():
    """Snapshot can be serialized to and from dict."""
    snapshot = ScraperStateSnapshot(
        match_id="test-123",
        url="https://example.com/match/123",
        last_processed_over=15,
        last_processed_ball=3,
        last_score="150/3",
        last_wickets=3,
        metadata={"team": "India", "venue": "Mumbai"},
    )

    data = snapshot.to_dict()
    assert data["match_id"] == "test-123"
    assert data["last_processed_over"] == 15
    assert data["metadata"]["team"] == "India"

    restored = ScraperStateSnapshot.from_dict(data)
    assert restored.match_id == "test-123"
    assert restored.last_processed_over == 15
    assert restored.metadata["team"] == "India"


def test_state_store_save_and_load(tmp_path: Path):
    """State store persists and retrieves snapshots."""
    db_path = tmp_path / "test_state.db"
    store = StateStore(db_path=str(db_path))

    snapshot = ScraperStateSnapshot(
        match_id="match-456",
        url="https://example.com/match/456",
        last_processed_over=20,
        last_score="200/5",
    )

    store.save(snapshot)

    loaded = store.load("match-456")
    assert loaded is not None
    assert loaded.match_id == "match-456"
    assert loaded.last_processed_over == 20
    assert loaded.last_score == "200/5"


def test_state_store_load_nonexistent(tmp_path: Path):
    """Loading nonexistent snapshot returns None."""
    db_path = tmp_path / "test_state.db"
    store = StateStore(db_path=str(db_path))

    loaded = store.load("nonexistent-match")
    assert loaded is None


def test_state_store_update_existing(tmp_path: Path):
    """Saving snapshot with same match_id updates the existing record."""
    db_path = tmp_path / "test_state.db"
    store = StateStore(db_path=str(db_path))

    # Save initial snapshot
    snapshot1 = ScraperStateSnapshot(
        match_id="match-789",
        url="https://example.com/match/789",
        last_processed_over=10,
    )
    store.save(snapshot1)

    # Update with new data
    snapshot2 = ScraperStateSnapshot(
        match_id="match-789",
        url="https://example.com/match/789",
        last_processed_over=15,
        last_score="120/2",
    )
    store.save(snapshot2)

    # Load should return updated snapshot
    loaded = store.load("match-789")
    assert loaded is not None
    assert loaded.last_processed_over == 15
    assert loaded.last_score == "120/2"


def test_state_store_delete(tmp_path: Path):
    """State store can delete snapshots."""
    db_path = tmp_path / "test_state.db"
    store = StateStore(db_path=str(db_path))

    snapshot = ScraperStateSnapshot(
        match_id="match-delete",
        url="https://example.com/match/delete",
    )
    store.save(snapshot)

    assert store.load("match-delete") is not None

    deleted = store.delete("match-delete")
    assert deleted is True

    assert store.load("match-delete") is None

    # Deleting again returns False
    deleted_again = store.delete("match-delete")
    assert deleted_again is False


def test_state_store_list_all(tmp_path: Path):
    """State store can list all snapshots."""
    db_path = tmp_path / "test_state.db"
    store = StateStore(db_path=str(db_path))

    snapshots = [
        ScraperStateSnapshot(
            match_id=f"match-{i}",
            url=f"https://example.com/match/{i}",
            last_processed_over=i * 10,
        )
        for i in range(1, 4)
    ]

    for snapshot in snapshots:
        store.save(snapshot)

    all_snapshots = store.list_all()
    assert len(all_snapshots) == 3

    match_ids = {s.match_id for s in all_snapshots}
    assert match_ids == {"match-1", "match-2", "match-3"}


def test_state_store_clear_all(tmp_path: Path):
    """State store can clear all snapshots."""
    db_path = tmp_path / "test_state.db"
    store = StateStore(db_path=str(db_path))

    for i in range(5):
        snapshot = ScraperStateSnapshot(
            match_id=f"match-{i}",
            url=f"https://example.com/match/{i}",
        )
        store.save(snapshot)

    assert len(store.list_all()) == 5

    count = store.clear_all()
    assert count == 5

    assert len(store.list_all()) == 0


def test_snapshot_with_metadata(tmp_path: Path):
    """Snapshot preserves custom metadata."""
    db_path = tmp_path / "test_state.db"
    store = StateStore(db_path=str(db_path))

    snapshot = ScraperStateSnapshot(
        match_id="match-meta",
        url="https://example.com/match/meta",
        metadata={
            "innings": 1,
            "batting_team": "Australia",
            "bowling_team": "England",
            "venue": "Lord's",
            "custom_field": {"nested": "data"},
        },
    )

    store.save(snapshot)
    loaded = store.load("match-meta")

    assert loaded is not None
    assert loaded.metadata["innings"] == 1
    assert loaded.metadata["batting_team"] == "Australia"
    assert loaded.metadata["custom_field"]["nested"] == "data"


def test_snapshot_handles_none_values(tmp_path: Path):
    """Snapshot correctly handles None for optional fields."""
    db_path = tmp_path / "test_state.db"
    store = StateStore(db_path=str(db_path))

    snapshot = ScraperStateSnapshot(
        match_id="match-none",
        url="https://example.com/match/none",
        last_processed_over=None,
        last_processed_ball=None,
        last_score=None,
    )

    store.save(snapshot)
    loaded = store.load("match-none")

    assert loaded is not None
    assert loaded.last_processed_over is None
    assert loaded.last_processed_ball is None
    assert loaded.last_score is None
