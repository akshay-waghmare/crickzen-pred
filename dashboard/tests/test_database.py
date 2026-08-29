from __future__ import annotations

from sqlalchemy.pool import NullPool

import app.database as database
from app.config import Settings


def test_sqlite_engine_avoids_exhaustible_queue_pool(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "_engine", None)
    engine = database.init_engine(
        Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'dashboard.db'}")
    )

    assert isinstance(engine.pool, NullPool)

    monkeypatch.setattr(database, "_engine", None)
