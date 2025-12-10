"""State snapshot persistence for seamless scraper restarts.

This module provides lightweight checkpoint functionality to enable scrapers to
resume from their last known good state after restart, preventing data duplication
and ensuring continuity during memory-triggered or scheduled restarts.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ..loggers.adapters import get_logger

from ..config import ScraperSettings, get_settings

logger = get_logger(component="scraper_state")


def _utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(tz=timezone.utc)


@dataclass
class ScraperStateSnapshot:
    """Lightweight state checkpoint for scraper resume."""

    match_id: str
    url: str
    last_processed_over: Optional[int] = None
    last_processed_ball: Optional[int] = None
    last_score: Optional[str] = None
    last_wickets: Optional[int] = None
    last_update_timestamp: Optional[str] = None
    snapshot_timestamp: str = field(default_factory=lambda: _utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScraperStateSnapshot":
        """Deserialize from dictionary."""
        # Extract known fields
        known_fields = {
            "match_id",
            "url",
            "last_processed_over",
            "last_processed_ball",
            "last_score",
            "last_wickets",
            "last_update_timestamp",
            "snapshot_timestamp",
            "metadata",
        }
        kwargs = {k: v for k, v in data.items() if k in known_fields}
        return cls(**kwargs)


class StateStore:
    """Persistent storage for scraper state snapshots using SQLite."""

    def __init__(
        self,
        *,
        settings: Optional[ScraperSettings] = None,
        db_path: Optional[str] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._db_path = db_path or str(
            Path(self._settings.sqlite_db_path).parent / "scraper_state.db"
        )
        self._lock = threading.RLock()
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create state snapshot table if it doesn't exist."""
        with self._lock:
            with sqlite3.connect(self._db_path, timeout=10.0) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS state_snapshots (
                        match_id TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        snapshot_data TEXT NOT NULL,
                        snapshot_timestamp TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.commit()

    def save(self, snapshot: ScraperStateSnapshot) -> None:
        """Persist a state snapshot."""
        with self._lock:
            snapshot_json = json.dumps(snapshot.to_dict())
            with sqlite3.connect(self._db_path, timeout=10.0) as conn:
                conn.execute(
                    """
                    INSERT INTO state_snapshots 
                        (match_id, url, snapshot_data, snapshot_timestamp, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(match_id) DO UPDATE SET
                        snapshot_data = excluded.snapshot_data,
                        snapshot_timestamp = excluded.snapshot_timestamp,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        snapshot.match_id,
                        snapshot.url,
                        snapshot_json,
                        snapshot.snapshot_timestamp,
                    ),
                )
                conn.commit()

        logger.info(
            "state.snapshot.saved",
            metadata={
                "match_id": snapshot.match_id,
                "url": snapshot.url,
                "timestamp": snapshot.snapshot_timestamp,
            },
        )

    def load(self, match_id: str) -> Optional[ScraperStateSnapshot]:
        """Load the most recent state snapshot for a match."""
        with self._lock:
            with sqlite3.connect(self._db_path, timeout=10.0) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT snapshot_data, snapshot_timestamp
                    FROM state_snapshots
                    WHERE match_id = ?
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (match_id,),
                )
                row = cursor.fetchone()

        if not row:
            logger.debug(
                "state.snapshot.not_found",
                metadata={"match_id": match_id},
            )
            return None

        try:
            data = json.loads(row["snapshot_data"])
            snapshot = ScraperStateSnapshot.from_dict(data)
            logger.info(
                "state.snapshot.loaded",
                metadata={
                    "match_id": match_id,
                    "timestamp": snapshot.snapshot_timestamp,
                },
            )
            return snapshot
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            logger.error(
                "state.snapshot.corrupt",
                metadata={
                    "match_id": match_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            return None

    def delete(self, match_id: str) -> bool:
        """Delete a state snapshot (e.g., when match completes)."""
        with self._lock:
            with sqlite3.connect(self._db_path, timeout=10.0) as conn:
                cursor = conn.execute(
                    "DELETE FROM state_snapshots WHERE match_id = ?",
                    (match_id,),
                )
                conn.commit()
                deleted = cursor.rowcount > 0

        if deleted:
            logger.info(
                "state.snapshot.deleted",
                metadata={"match_id": match_id},
            )
        else:
            logger.debug(
                "state.snapshot.delete_noop",
                metadata={"match_id": match_id, "reason": "not_found"},
            )

        return deleted

    def list_all(self) -> list[ScraperStateSnapshot]:
        """List all stored state snapshots."""
        with self._lock:
            with sqlite3.connect(self._db_path, timeout=10.0) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT snapshot_data
                    FROM state_snapshots
                    ORDER BY updated_at DESC
                    """
                )
                rows = cursor.fetchall()

        snapshots = []
        for row in rows:
            try:
                data = json.loads(row["snapshot_data"])
                snapshots.append(ScraperStateSnapshot.from_dict(data))
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                logger.warning(
                    "state.snapshot.corrupt_skip",
                    metadata={"error": str(exc)},
                )
                continue

        return snapshots

    def clear_all(self) -> int:
        """Clear all state snapshots. Returns count deleted."""
        with self._lock:
            with sqlite3.connect(self._db_path, timeout=10.0) as conn:
                cursor = conn.execute("DELETE FROM state_snapshots")
                conn.commit()
                count = cursor.rowcount

        logger.info("state.snapshots.cleared", metadata={"count": count})
        return count


__all__ = [
    "ScraperStateSnapshot",
    "StateStore",
]
