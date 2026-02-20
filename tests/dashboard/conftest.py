"""Shared test fixtures for dashboard tests."""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Ensure dashboard package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "dashboard"))


@pytest.fixture(name="engine")
def engine_fixture():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine):
    """Create a new database session for each test."""
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(engine, tmp_path):
    """Create a FastAPI TestClient with test database and temp state file."""
    from app.main import create_app, limiter
    from app.config import Settings
    from app.database import get_session

    # Create a sample live_state.json for tests
    state_file = tmp_path / "live_state.json"

    settings = Settings(
        JWT_SECRET="test-secret-key-for-testing-only",
        DOMAIN="localhost",
        ADMIN_EMAIL="admin@test.com",
        ADMIN_PASSWORD="testpassword123",
        DATABASE_URL="sqlite://",
        STATE_FILE=str(state_file),
        POLL_INTERVAL_MS=3000,
        ACCESS_TOKEN_EXPIRE_MINUTES=55,
        REFRESH_TOKEN_EXPIRE_DAYS=30,
        SESSION_CAP=50,
    )

    app = create_app(settings_override=settings, engine_override=engine)

    # Reset the rate limiter storage before each test
    limiter.reset()

    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override

    with TestClient(app) as client:
        yield client


@pytest.fixture(name="admin_token")
def admin_token_fixture(client):
    """Login as admin and return the access token."""
    response = client.post(
        "/auth/login",
        json={"email": "admin@test.com", "password": "testpassword123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(admin_token):
    """Return authorization headers with admin token."""
    return {"Authorization": f"Bearer {admin_token}"}
