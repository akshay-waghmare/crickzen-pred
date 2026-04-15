"""Tests for admin endpoints."""

from __future__ import annotations


class TestSubscriberCRUD:
    def test_list_subscribers_as_admin(self, client, admin_token):
        resp = client.get("/admin/subscribers", headers={
            "Authorization": f"Bearer {admin_token}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Admin user should be in the list
        assert any(u["email"] == "admin@test.com" for u in data)

    def test_list_subscribers_as_non_admin(self, client, user_token):
        resp = client.get("/admin/subscribers", headers={
            "Authorization": f"Bearer {user_token}",
        })
        assert resp.status_code == 403

    def test_create_subscriber(self, client, admin_token):
        resp = client.post("/admin/subscribers", json={
            "email": "subscriber@test.com",
            "password": "subpassword123",
            "plan": "monthly",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "subscriber@test.com"
        assert data["plan"] == "monthly"
        assert data["is_active"] is True

    def test_create_duplicate_subscriber(self, client, admin_token):
        client.post("/admin/subscribers", json={
            "email": "dup-sub@test.com",
            "password": "password123",
            "plan": "free",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.post("/admin/subscribers", json={
            "email": "dup-sub@test.com",
            "password": "password123",
            "plan": "free",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 409

    def test_suspend_and_reactivate(self, client, admin_token):
        # Create subscriber
        create = client.post("/admin/subscribers", json={
            "email": "toggle@test.com",
            "password": "password123",
            "plan": "monthly",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        user_id = create.json()["id"]

        # Suspend
        resp = client.patch(f"/admin/subscribers/{user_id}/suspend",
                            headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200

        # Verify suspended
        subs = client.get("/admin/subscribers",
                          headers={"Authorization": f"Bearer {admin_token}"}).json()
        user = next(u for u in subs if u["id"] == user_id)
        assert user["is_active"] is False

        # Reactivate
        resp = client.patch(f"/admin/subscribers/{user_id}/reactivate",
                            headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200

        # Verify active
        subs = client.get("/admin/subscribers",
                          headers={"Authorization": f"Bearer {admin_token}"}).json()
        user = next(u for u in subs if u["id"] == user_id)
        assert user["is_active"] is True
