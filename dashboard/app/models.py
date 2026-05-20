"""SQLModel ORM models for CrickenZen Dashboard."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """Registered subscriber or admin."""

    __tablename__ = "users"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    plan: str = Field(default="free")  # free | monthly | yearly
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RefreshToken(SQLModel, table=True):
    """Opaque refresh token (only the SHA-256 hash is stored)."""

    __tablename__ = "refresh_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    token_hash: str = Field(index=True, unique=True)
    user_id: str = Field(index=True)
    expires_at: datetime
    revoked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MatchPrediction(SQLModel, table=True):
    """Tracks an active (or recently finished) live prediction subprocess."""

    __tablename__ = "match_predictions"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], primary_key=True)
    user_id: str = Field(index=True)
    match_url: str
    league: str
    status: str = Field(default="running")  # running | stopped | finished | error
    output_json_path: str = Field(default="")
    pid: Optional[int] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stopped_at: Optional[datetime] = Field(default=None)


class VisitorEvent(SQLModel, table=True):
    """First-party marketing and conversion tracking for dashboard traffic."""

    __tablename__ = "visitor_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    visitor_id: str = Field(index=True)
    event_name: str = Field(index=True)  # page_view | register_success
    path: str = Field(index=True)
    landing_path: Optional[str] = Field(default=None)
    user_id: Optional[str] = Field(default=None, index=True)
    utm_source: Optional[str] = Field(default=None, index=True)
    utm_medium: Optional[str] = Field(default=None)
    utm_campaign: Optional[str] = Field(default=None, index=True)
    utm_content: Optional[str] = Field(default=None)
    utm_term: Optional[str] = Field(default=None)
    referrer_url: Optional[str] = Field(default=None)
    referrer_host: Optional[str] = Field(default=None, index=True)
    user_agent: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
