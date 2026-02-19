"""Tests for auth endpoints: login, refresh, logout, user management."""

import time

import jwt
import pytest


class TestLogin:
    """POST /auth/login tests."""

    def test_login_success(self, client):
        """Successful login returns access token and sets refresh cookie."""
        resp = client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "testpassword123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        # Refresh token should be set as HttpOnly cookie
        assert "refresh_token" in resp.cookies

    def test_login_wrong_password(self, client):
        """Invalid password returns 401."""
        resp = client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["detail"]

    def test_login_nonexistent_user(self, client):
        """Non-existent email returns 401."""
        resp = client.post(
            "/auth/login",
            json={"email": "nobody@test.com", "password": "whatever"},
        )
        assert resp.status_code == 401

    def test_login_inactive_user(self, client, admin_token):
        """Inactive user returns 403."""
        # Create a subscriber
        client.post(
            "/auth/users",
            json={"email": "inactive@test.com", "password": "password123"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Deactivate them via direct DB manipulation
        from sqlmodel import Session, select

        from app.database import get_engine
        from app.models import User

        engine = get_engine()
        with Session(engine) as session:
            user = session.exec(
                select(User).where(User.email == "inactive@test.com")
            ).first()
            assert user is not None
            user.is_active = False
            session.add(user)
            session.commit()

        # Try to login
        resp = client.post(
            "/auth/login",
            json={"email": "inactive@test.com", "password": "password123"},
        )
        assert resp.status_code == 403
        assert "deactivated" in resp.json()["detail"]


class TestRefresh:
    """POST /auth/refresh tests."""

    def test_refresh_rotation(self, client):
        """Refresh issues new access token and rotates refresh cookie."""
        # Login first
        login_resp = client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "testpassword123"},
        )
        assert login_resp.status_code == 200
        old_refresh = login_resp.cookies.get("refresh_token")
        assert old_refresh is not None

        # Refresh
        refresh_resp = client.post(
            "/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert refresh_resp.status_code == 200
        data = refresh_resp.json()
        assert "access_token" in data
        # New refresh cookie should be set
        new_refresh = refresh_resp.cookies.get("refresh_token")
        assert new_refresh is not None
        assert new_refresh != old_refresh

    def test_refresh_no_cookie(self, client):
        """Missing refresh cookie returns 401."""
        resp = client.post("/auth/refresh")
        assert resp.status_code == 401

    def test_refresh_replay_attack(self, client):
        """Using a consumed refresh token revokes all user tokens."""
        # Login
        login_resp = client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "testpassword123"},
        )
        old_refresh = login_resp.cookies.get("refresh_token")

        # First refresh — consumes the token
        refresh1 = client.post(
            "/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert refresh1.status_code == 200

        # Replay the old token — should trigger revoke-all
        replay_resp = client.post(
            "/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert replay_resp.status_code == 401
        assert "replay" in replay_resp.json()["detail"].lower() or "revoked" in replay_resp.json()["detail"].lower()


class TestLogout:
    """POST /auth/logout tests."""

    def test_logout_clears_cookie(self, client):
        """Logout revokes refresh token and clears cookie."""
        # Login
        login_resp = client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "testpassword123"},
        )
        refresh_token = login_resp.cookies.get("refresh_token")
        access_token = login_resp.json()["access_token"]

        # Logout
        logout_resp = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            cookies={"refresh_token": refresh_token},
        )
        assert logout_resp.status_code == 204

        # Try to refresh with the revoked token
        refresh_resp = client.post(
            "/auth/refresh",
            cookies={"refresh_token": refresh_token},
        )
        # Should be rejected (revoked)
        assert refresh_resp.status_code == 401


class TestCreateUser:
    """POST /auth/users tests."""

    def test_admin_creates_subscriber(self, client, admin_token):
        """Admin can create a new subscriber."""
        resp = client.post(
            "/auth/users",
            json={"email": "subscriber@test.com", "password": "subpass123"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "subscriber@test.com"
        assert data["is_active"] is True

    def test_non_admin_cannot_create_user(self, client, admin_token):
        """Non-admin user gets 403 when creating users."""
        # Create a subscriber first
        client.post(
            "/auth/users",
            json={"email": "sub2@test.com", "password": "subpass123"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Login as subscriber
        sub_login = client.post(
            "/auth/login",
            json={"email": "sub2@test.com", "password": "subpass123"},
        )
        sub_token = sub_login.json()["access_token"]

        # Try to create another user
        resp = client.post(
            "/auth/users",
            json={"email": "sub3@test.com", "password": "pass123"},
            headers={"Authorization": f"Bearer {sub_token}"},
        )
        assert resp.status_code == 403

    def test_duplicate_email_rejected(self, client, admin_token):
        """Creating a user with existing email returns 409."""
        client.post(
            "/auth/users",
            json={"email": "dup@test.com", "password": "pass123"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = client.post(
            "/auth/users",
            json={"email": "dup@test.com", "password": "pass456"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 409

    def test_unauthenticated_cannot_create_user(self, client):
        """No token → 401."""
        resp = client.post(
            "/auth/users",
            json={"email": "anon@test.com", "password": "pass123"},
        )
        assert resp.status_code == 401


class TestHealth:
    """GET /health tests."""

    def test_health_ok(self, client):
        """Health endpoint returns ok without auth."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestSecurityHardening:
    """FR-014–FR-018: Security-specific test cases."""

    def test_password_uses_argon2id(self, client):
        """FR-014: Passwords are hashed with Argon2id."""
        from sqlmodel import Session, select
        from app.database import get_engine
        from app.models import User

        engine = get_engine()
        with Session(engine) as session:
            user = session.exec(
                select(User).where(User.email == "admin@test.com")
            ).first()
            assert user is not None
            # Argon2id hashes start with $argon2id$
            assert user.hashed_password.startswith("$argon2id$")

    def test_bad_jwt_signature_returns_401(self, client):
        """FR-015: Forged JWT with wrong secret is rejected."""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        forged_token = pyjwt.encode(
            {
                "sub": "fake-user-id",
                "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            "wrong-secret-key",
            algorithm="HS256",
        )
        resp = client.get(
            "/api/live-state",
            headers={"Authorization": f"Bearer {forged_token}"},
        )
        assert resp.status_code == 401

    def test_expired_jwt_returns_401(self, client):
        """FR-015: Expired JWT is rejected."""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        expired_token = pyjwt.encode(
            {
                "sub": "fake-user-id",
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            "test-secret-key-for-testing-only",
            algorithm="HS256",
        )
        resp = client.get(
            "/api/live-state",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    def test_refresh_replay_revokes_all_sessions(self, client):
        """FR-016: Consumed refresh token replay revokes all user tokens."""
        # Login and get a refresh token
        login_resp = client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "testpassword123"},
        )
        old_refresh = login_resp.cookies.get("refresh_token")

        # Login again to create a second session
        login2_resp = client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "testpassword123"},
        )
        second_refresh = login2_resp.cookies.get("refresh_token")

        # Consume the first token
        refresh1 = client.post(
            "/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert refresh1.status_code == 200

        # Replay old token → should revoke ALL
        replay_resp = client.post(
            "/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert replay_resp.status_code == 401

        # Second session should also be revoked
        second_refresh_resp = client.post(
            "/auth/refresh",
            cookies={"refresh_token": second_refresh},
        )
        assert second_refresh_resp.status_code == 401

    def test_non_admin_cannot_create_users(self, client, admin_token):
        """FR-016: Only admin can create users, non-admin gets 403."""
        # Create a subscriber
        client.post(
            "/auth/users",
            json={"email": "sectest@test.com", "password": "password123"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Login as subscriber
        sub_resp = client.post(
            "/auth/login",
            json={"email": "sectest@test.com", "password": "password123"},
        )
        sub_token = sub_resp.json()["access_token"]

        resp = client.post(
            "/auth/users",
            json={"email": "another@test.com", "password": "pass123"},
            headers={"Authorization": f"Bearer {sub_token}"},
        )
        assert resp.status_code == 403

