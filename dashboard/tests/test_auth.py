"""Tests for auth endpoints."""

from __future__ import annotations

from sqlmodel import Session, select

from app.auth import verify_password
from app.config import Settings
from app.database import seed_admin_user
from app.models import User


class TestLogin:
    def test_login_success(self, client):
        resp = client.post("/auth/login", json={
            "email": "admin@test.com",
            "password": "testpassword123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        resp = client.post("/auth/login", json={
            "email": "admin@test.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_unknown_email(self, client):
        resp = client.post("/auth/login", json={
            "email": "nobody@test.com",
            "password": "whatever",
        })
        assert resp.status_code == 401


class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={
            "email": "newuser@test.com",
            "password": "newpassword123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    def test_register_duplicate_email(self, client):
        client.post("/auth/register", json={
            "email": "dup@test.com",
            "password": "password123",
        })
        resp = client.post("/auth/register", json={
            "email": "dup@test.com",
            "password": "password123",
        })
        assert resp.status_code == 409

    def test_register_short_password(self, client):
        resp = client.post("/auth/register", json={
            "email": "short@test.com",
            "password": "abc",
        })
        assert resp.status_code == 422


class TestRefresh:
    def test_refresh_success(self, client):
        login = client.post("/auth/login", json={
            "email": "admin@test.com",
            "password": "testpassword123",
        })
        refresh_token = login.json()["refresh_token"]
        resp = client.post("/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_refresh_invalid_token(self, client):
        resp = client.post("/auth/refresh", json={
            "refresh_token": "bogus-token",
        })
        assert resp.status_code == 401


class TestMe:
    def test_me_authenticated(self, client, admin_token):
        resp = client.get("/auth/me", headers={
            "Authorization": f"Bearer {admin_token}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@test.com"

    def test_me_no_token(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401


class TestLogout:
    def test_logout(self, client):
        login = client.post("/auth/login", json={
            "email": "admin@test.com",
            "password": "testpassword123",
        })
        data = login.json()
        resp = client.post("/auth/logout", json={
            "refresh_token": data["refresh_token"],
        })
        assert resp.status_code == 200


class TestAdminBootstrap:
    def test_existing_admin_password_not_changed_without_force_sync(self, engine):
        initial = Settings(
            JWT_SECRET="test-secret-key-for-testing-only",
            DOMAIN="localhost",
            ADMIN_EMAIL="admin@test.com",
            ADMIN_PASSWORD="original-password-123",
            DATABASE_URL="sqlite://",
            ADMIN_FORCE_SYNC=False,
        )
        updated = Settings(
            JWT_SECRET="test-secret-key-for-testing-only",
            DOMAIN="localhost",
            ADMIN_EMAIL="admin@test.com",
            ADMIN_PASSWORD="new-password-123",
            DATABASE_URL="sqlite://",
            ADMIN_FORCE_SYNC=False,
        )

        with Session(engine) as session:
            seed_admin_user(session, initial)
        with Session(engine) as session:
            seed_admin_user(session, updated)
        with Session(engine) as session:
            admin = session.exec(select(User).where(User.email == "admin@test.com")).first()

        assert admin is not None
        assert verify_password("original-password-123", admin.hashed_password)
        assert not verify_password("new-password-123", admin.hashed_password)

    def test_existing_admin_password_is_reset_with_force_sync(self, engine):
        initial = Settings(
            JWT_SECRET="test-secret-key-for-testing-only",
            DOMAIN="localhost",
            ADMIN_EMAIL="admin@test.com",
            ADMIN_PASSWORD="original-password-123",
            DATABASE_URL="sqlite://",
            ADMIN_FORCE_SYNC=False,
        )
        updated = Settings(
            JWT_SECRET="test-secret-key-for-testing-only",
            DOMAIN="localhost",
            ADMIN_EMAIL="admin@test.com",
            ADMIN_PASSWORD="new-password-123",
            DATABASE_URL="sqlite://",
            ADMIN_FORCE_SYNC=True,
        )

        with Session(engine) as session:
            seed_admin_user(session, initial)
        with Session(engine) as session:
            seed_admin_user(session, updated)
        with Session(engine) as session:
            admin = session.exec(select(User).where(User.email == "admin@test.com")).first()

        assert admin is not None
        assert verify_password("new-password-123", admin.hashed_password)
        assert admin.is_admin is True
        assert admin.is_active is True
        assert admin.plan == "admin"
