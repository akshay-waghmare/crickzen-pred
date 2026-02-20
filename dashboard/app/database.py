"""SQLite database engine, session management, and startup helpers."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import Settings, get_settings
from app.models import RefreshToken, User

logger = logging.getLogger(__name__)

# Module-level engine — set by init_engine() or overridden in tests
_engine = None


def init_engine(settings: Settings | None = None):
    """Create the SQLAlchemy engine with WAL mode for SQLite."""
    global _engine
    s = settings or get_settings()
    connect_args = {"check_same_thread": False}
    _engine = create_engine(s.DATABASE_URL, connect_args=connect_args)

    # Enable WAL mode for SQLite
    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return _engine


def get_engine():
    """Return the current engine, initialising if needed."""
    global _engine
    if _engine is None:
        init_engine()
    return _engine


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    engine = get_engine()
    with Session(engine) as session:
        yield session


def create_db_and_tables(engine=None):
    """Create all tables if they don't exist."""
    e = engine or get_engine()
    SQLModel.metadata.create_all(e)
    logger.info("Database tables created/verified")


def seed_admin_user(session: Session, settings: Settings | None = None):
    """Create the admin user from env vars if not already present."""
    s = settings or get_settings()
    if not s.ADMIN_EMAIL or not s.ADMIN_PASSWORD:
        logger.warning("ADMIN_EMAIL or ADMIN_PASSWORD not set, skipping seed")
        return

    existing = session.exec(
        select(User).where(User.email == s.ADMIN_EMAIL)
    ).first()
    if existing:
        logger.info("Admin user already exists: %s", s.ADMIN_EMAIL)
        return

    # Import here to avoid circular dependency
    from app.auth import hash_password

    admin = User(
        email=s.ADMIN_EMAIL,
        hashed_password=hash_password(s.ADMIN_PASSWORD),
        is_active=True,
    )
    session.add(admin)
    session.commit()
    logger.info("Admin user seeded: %s", s.ADMIN_EMAIL)


def purge_expired_tokens(session: Session):
    """Delete refresh tokens that have passed their expiry date."""
    now = datetime.now(timezone.utc)
    expired = session.exec(
        select(RefreshToken).where(RefreshToken.expires_at < now)
    ).all()
    count = len(expired)
    for token in expired:
        session.delete(token)
    if count > 0:
        session.commit()
        logger.info("Purged %d expired refresh tokens", count)


async def periodic_token_purge(interval_hours: int = 1):
    """Background task that periodically purges expired tokens."""
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            engine = get_engine()
            with Session(engine) as session:
                purge_expired_tokens(session)
        except Exception:
            logger.exception("Error during periodic token purge")
