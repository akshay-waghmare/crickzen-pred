import sqlite3
import time

import pytest

from src.persistence.db_pool import ConnectionPool
from src.persistence.batch_writer import BatchWriter


def _create_pool(tmp_path):
    db_path = tmp_path / "batch_writer.sqlite"
    return ConnectionPool(database_path=str(db_path), min_size=0, max_size=1, acquire_timeout=1.0)


def _ensure_table(pool):
    with pool.get_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS events (value INTEGER)")
        conn.commit()


def _count_rows(pool) -> int:
    with pool.get_connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    return int(result)


def test_flush_on_batch_size(tmp_path):
    pool = _create_pool(tmp_path)
    _ensure_table(pool)

    persisted = []

    def persist(conn: sqlite3.Connection, batch):
        persisted.append(list(batch))
        conn.executemany("INSERT INTO events (value) VALUES (?)", [(item,) for item in batch])
        conn.commit()

    writer = BatchWriter(pool, persist, batch_size=3, flush_interval=2.0)

    try:
        writer.add(1)
        writer.add(2)
        writer.add(3)
        assert _count_rows(pool) == 3
        assert sum(len(b) for b in persisted) == 3
    finally:
        writer.shutdown()
        pool.close()


def test_flush_by_interval(tmp_path):
    pool = _create_pool(tmp_path)
    _ensure_table(pool)

    def persist(conn: sqlite3.Connection, batch):
        conn.executemany("INSERT INTO events (value) VALUES (?)", [(item,) for item in batch])
        conn.commit()

    writer = BatchWriter(pool, persist, batch_size=10, flush_interval=0.1)

    try:
        writer.add(5)
        time.sleep(0.3)
        assert _count_rows(pool) == 1
    finally:
        writer.shutdown()
        pool.close()


def test_critical_event_bypasses_batch(tmp_path):
    pool = _create_pool(tmp_path)
    _ensure_table(pool)

    def persist(conn: sqlite3.Connection, batch):
        conn.executemany("INSERT INTO events (value) VALUES (?)", [(item,) for item in batch])
        conn.commit()

    writer = BatchWriter(pool, persist, batch_size=10, flush_interval=5.0)

    try:
        writer.add(9, critical=True)
        assert _count_rows(pool) == 1
        stats = writer.get_stats()
        assert stats["critical"] == 1
    finally:
        writer.shutdown()
        pool.close()


def test_flush_failure_requeues_items(tmp_path):
    pool = _create_pool(tmp_path)
    _ensure_table(pool)

    calls = {"fail": True}

    def persist(conn: sqlite3.Connection, batch):
        if calls["fail"]:
            calls["fail"] = False
            raise RuntimeError("boom")
        conn.executemany("INSERT INTO events (value) VALUES (?)", [(item,) for item in batch])
        conn.commit()

    writer = BatchWriter(pool, persist, batch_size=2, flush_interval=5.0)

    try:
        writer.add(1)
        with pytest.raises(RuntimeError):
            writer.add(2)  # Trigger flush that fails

        stats = writer.get_stats()
        assert stats["queued_pending"] == 2
        assert stats["flush_failures"] == 1

        writer.flush()
        assert _count_rows(pool) == 2
    finally:
        writer.shutdown()
        pool.close()
