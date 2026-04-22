"""Test fixtures for CrickenZen Dashboard."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def settings():
    return Settings(
        JWT_SECRET="test-secret-key-for-testing-only",
        DOMAIN="localhost",
        ADMIN_EMAIL="admin@test.com",
        ADMIN_PASSWORD="testpassword123",
        DATABASE_URL="sqlite://",
        SESSION_CAP=50,
        MAX_USER_MATCHES=2,
        MAX_TOTAL_MATCHES=6,
        AUTO_PREDICTIONS_ENABLED=False,
        REGISTRATION_OPEN=True,
    )


@pytest.fixture()
def engine(settings):
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture()
def app(settings, engine):
    return create_app(settings_override=settings, engine_override=engine)


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_token(client):
    """Login as admin and return access token."""
    resp = client.post("/auth/login", json={
        "email": "admin@test.com",
        "password": "testpassword123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture()
def user_token(client):
    """Register a regular user and return access token."""
    resp = client.post("/auth/register", json={
        "email": "user@test.com",
        "password": "userpassword123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]
