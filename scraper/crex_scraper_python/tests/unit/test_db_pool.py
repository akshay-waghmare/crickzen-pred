import threading
import time
from pathlib import Path

import pytest

from src.persistence.db_pool import ConnectionPool, ConnectionPoolError


def test_pool_reuses_connections(tmp_path: Path):
    db_path = tmp_path / "pool.sqlite"
    pool = ConnectionPool(database_path=str(db_path), min_size=1, max_size=2, acquire_timeout=1)

    connection_ids = set()
    for _ in range(5):
        with pool.get_connection() as conn:
            connection_ids.add(id(conn))
            conn.execute("CREATE TABLE IF NOT EXISTS items (value INTEGER)")
            conn.execute("INSERT INTO items (value) VALUES (1)")
    assert len(connection_ids) <= 2

    with pool.get_connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    assert result == 5

    pool.close()


def test_pool_rolls_back_on_error(tmp_path: Path):
    db_path = tmp_path / "pool.sqlite"
    pool = ConnectionPool(database_path=str(db_path), min_size=0, max_size=1, acquire_timeout=1)

    with pool.get_connection() as conn:
        conn.execute("CREATE TABLE events (value INTEGER)")

    with pytest.raises(RuntimeError):
        with pool.get_connection() as conn:
            conn.execute("INSERT INTO events (value) VALUES (1)")
            raise RuntimeError("boom")

    with pool.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert count == 0

    pool.close()


def test_pool_respects_timeout(tmp_path: Path):
    db_path = tmp_path / "pool.sqlite"
    pool = ConnectionPool(database_path=str(db_path), min_size=0, max_size=1, acquire_timeout=0.2)

    gate = threading.Event()

    def hold_connection():
        with pool.get_connection():
            gate.wait()

    thread = threading.Thread(target=hold_connection)
    thread.start()

    time.sleep(0.05)  # ensure thread acquired connection
    with pytest.raises(ConnectionPoolError):
        with pool.get_connection():
            pass

    gate.set()
    thread.join()
    pool.close()


def test_pool_close_releases_resources(tmp_path: Path):
    db_path = tmp_path / "pool.sqlite"
    pool = ConnectionPool(database_path=str(db_path), min_size=1, max_size=2, acquire_timeout=1)

    stats_before = pool.stats()
    assert stats_before["available"] == 1

    with pool.get_connection():
        stats_mid = pool.stats()
        assert stats_mid["in_use"] == 1

    pool.close()
    stats_after = pool.stats()
    assert stats_after["open_connections"] <= stats_after["in_use"]


def test_unhealthy_connection_replaced(tmp_path: Path):
    db_path = tmp_path / "pool.sqlite"
    pool = ConnectionPool(database_path=str(db_path), min_size=1, max_size=2, acquire_timeout=1)

    with pool.get_connection() as conn:
        conn.close()  # Simulate external close

    with pool.get_connection() as conn:
        conn.execute("SELECT 1")

    stats = pool.stats()
    assert stats["open_connections"] >= stats["min_size"]
    pool.close()
