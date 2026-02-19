"""SQLModel database models for auth."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """Registered subscriber who can access the dashboard."""

    __tablename__ = "users"  # type: ignore[assignment]

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36,
    )
    email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RefreshToken(SQLModel, table=True):
    """Tracks long-lived refresh tokens for session continuity."""

    __tablename__ = "refresh_tokens"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True, max_length=64)
    user_id: str = Field(foreign_key="users.id", max_length=36)
    expires_at: datetime
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    revoked: bool = Field(default=False)
