"""SQLite database engine, session management, and startup helpers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import Settings, get_settings
from app.models import RefreshToken, User

logger = logging.getLogger(__name__)

_engine = None


def init_engine(settings: Settings | None = None):
    global _engine
    s = settings or get_settings()
    connect_args = {"check_same_thread": False}
    _engine = create_engine(s.DATABASE_URL, connect_args=connect_args)

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return _engine


def get_engine():
    global _engine
    if _engine is None:
        init_engine()
    return _engine


def get_session() -> Generator[Session, None, None]:
    engine = get_engine()
    with Session(engine) as session:
        yield session


def create_db_and_tables(engine=None):
    e = engine or get_engine()
    SQLModel.metadata.create_all(e)
    logger.info("Database tables created/verified")


def seed_admin_user(session: Session, settings: Settings | None = None):
    s = settings or get_settings()
    if not s.ADMIN_EMAIL or not s.ADMIN_PASSWORD:
        logger.warning("ADMIN_EMAIL or ADMIN_PASSWORD not set, skipping seed")
        return
    existing = session.exec(select(User).where(User.email == s.ADMIN_EMAIL)).first()
    if existing:
        logger.info("Admin user already exists: %s", s.ADMIN_EMAIL)
        return
    from app.auth import hash_password

    admin = User(
        email=s.ADMIN_EMAIL,
        hashed_password=hash_password(s.ADMIN_PASSWORD),
        is_active=True,
        plan="admin",
    )
    session.add(admin)
    session.commit()
    logger.info("Admin user seeded: %s", s.ADMIN_EMAIL)


def purge_expired_tokens(session: Session):
    now = datetime.now(timezone.utc)
    expired = session.exec(select(RefreshToken).where(RefreshToken.expires_at < now)).all()
    count = len(expired)
    for token in expired:
        session.delete(token)
    if count > 0:
        session.commit()
        logger.info("Purged %d expired refresh tokens", count)


async def periodic_token_purge(interval_hours: int = 1):
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            engine = get_engine()
            with Session(engine) as session:
                purge_expired_tokens(session)
        except Exception:
            logger.exception("Error during periodic token purge")
