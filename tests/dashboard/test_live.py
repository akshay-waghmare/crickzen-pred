"""Tests for GET /api/live-state endpoint."""

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path


class TestLiveState:
    """GET /api/live-state tests."""

    def _write_state(self, client, data: dict | None = None):
        """Helper: write a live_state.json file to the tmp dir used by tests."""
        # Get the STATE_FILE path from the app settings
        from app.config import get_settings

        settings = get_settings()
        state_path = Path(settings.STATE_FILE)

        if data is None:
            data = {
                "batting_team": "SYS",
                "bowling_team": "BRH",
                "score": 142,
                "wickets": 4,
                "overs": 14.3,
                "target": None,
                "bat_win_prob": 0.63,
                "bowl_win_prob": 0.37,
                "current_run_rate": 9.73,
                "required_run_rate": None,
                "is_second_innings": False,
                "phase": "middle",
                "league": "bbl",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "history": [],
            }

        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(data), encoding="utf-8")
        return state_path

    def test_401_without_token(self, client):
        """Unauthenticated request returns 401."""
        self._write_state(client)
        resp = client.get("/api/live-state")
        assert resp.status_code == 401

    def test_200_with_valid_token(self, client, auth_headers):
        """Authenticated request returns match state."""
        self._write_state(client)
        resp = client.get("/api/live-state", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["batting_team"] == "SYS"
        assert data["score"] == 142
        assert data["bat_win_prob"] == 0.63
        assert "poll_interval_ms" in data

    def test_poll_interval_in_response(self, client, auth_headers):
        """Response includes poll_interval_ms from server config."""
        self._write_state(client)
        resp = client.get("/api/live-state", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["poll_interval_ms"] == 3000

    def test_stale_detection(self, client, auth_headers):
        """State older than 60s is marked as stale."""
        old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        self._write_state(
            client,
            {
                "batting_team": "SYS",
                "bowling_team": "BRH",
                "score": 100,
                "wickets": 3,
                "overs": 10.0,
                "bat_win_prob": 0.5,
                "bowl_win_prob": 0.5,
                "timestamp": old_time.isoformat(),
                "history": [],
            },
        )
        resp = client.get("/api/live-state", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["stale"] is True

    def test_304_on_etag_match(self, client, auth_headers):
        """Matching ETag returns 304 Not Modified."""
        self._write_state(client)

        # First request — get the ETag
        resp1 = client.get("/api/live-state", headers=auth_headers)
        assert resp1.status_code == 200
        etag = resp1.headers.get("etag")
        assert etag is not None

        # Second request with If-None-Match
        resp2 = client.get(
            "/api/live-state",
            headers={**auth_headers, "If-None-Match": etag},
        )
        assert resp2.status_code == 304

    def test_404_when_file_absent(self, client, auth_headers):
        """Missing state file returns 404."""
        # Don't write any file
        resp = client.get("/api/live-state", headers=auth_headers)
        assert resp.status_code == 404
        assert "No live match state" in resp.json()["detail"]

    def test_fresh_data_not_stale(self, client, auth_headers):
        """Recently-written state is NOT marked stale."""
        self._write_state(client)
        resp = client.get("/api/live-state", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json().get("stale") is not True
