"""Tests for live prediction endpoints."""

from __future__ import annotations


class TestLeagues:
    def test_list_leagues(self, client, user_token):
        resp = client.get("/api/matches/leagues")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        keys = [l["key"] for l in data]
        assert "IPL" in keys
        assert "BBL" in keys


class TestDetectLeague:
    def test_detect_ipl(self, client):
        resp = client.get("/api/matches/detect-league", params={
            "url": "https://crex.live/scoreboard/indian-premier-league/some-match",
        })
        assert resp.status_code == 200
        assert resp.json()["league"] == "IPL"

    def test_detect_unknown(self, client):
        resp = client.get("/api/matches/detect-league", params={
            "url": "https://example.com/unknown-league",
        })
        assert resp.status_code == 200
        assert resp.json()["league"] is None


class TestMatchList:
    def test_list_empty(self, client, user_token):
        resp = client.get("/api/matches", headers={
            "Authorization": f"Bearer {user_token}",
        })
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_requires_auth(self, client):
        resp = client.get("/api/matches")
        assert resp.status_code == 401


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
