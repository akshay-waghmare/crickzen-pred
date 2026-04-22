"""Tests for live prediction endpoints."""

from __future__ import annotations

import json

from app.routers.live import _build_projection, _derive_commentary_from_history, _enrich_detail_state


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


class TestAutoScheduler:
    def test_auto_status_disabled(self, client, user_token):
        resp = client.get("/api/matches/auto/status", headers={
            "Authorization": f"Bearer {user_token}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["running"] is False


class TestDetailState:
    def test_projection_uses_feature_fields(self):
        projection = _build_projection({
            "score": 120,
            "wickets": 3,
            "overs": 12.4,
            "target": 181,
            "current_run_rate": 9.47,
            "features": {
                "projected_score": 188.4,
                "expected_final_score": 189.1,
                "venue_avg_score": 172.0,
                "score_vs_par": 8.0,
                "projected_vs_venue_avg": 16.4,
                "resource_win_prob": 0.63,
                "required_run_rate": 8.32,
            },
        })

        assert projection["projected_score"] == 188.4
        assert projection["runs_required"] == 61
        assert projection["balls_remaining"] == 44
        assert projection["resource_win_prob"] == 0.63

    def test_synthesises_commentary_from_distinct_history(self):
        commentary = _derive_commentary_from_history([
            {"innings": 1, "overs": 4.1, "score": 37, "wickets": 1, "bat_prob": 0.52, "batting_team": "Team A"},
            {"innings": 1, "overs": 4.1, "score": 37, "wickets": 1, "bat_prob": 0.52, "batting_team": "Team A"},
            {"innings": 1, "overs": 4.2, "score": 41, "wickets": 1, "bat_prob": 0.55, "batting_team": "Team A"},
            {"innings": 1, "overs": 4.3, "score": 41, "wickets": 2, "bat_prob": 0.47, "batting_team": "Team A"},
        ])

        assert len(commentary) == 3
        assert commentary[0]["event"] == "Wicket"
        assert commentary[1]["event"] == "Boundary"
        assert commentary[2]["event"] == "Update"

    def test_enrich_detail_state_loads_sidecars(self, tmp_path):
        output = tmp_path / "abc123.json"
        output.write_text("{}", encoding="utf-8")
        (tmp_path / "abc123_history.json").write_text(json.dumps({
            "history": [
                {"innings": 1, "overs": 1.0, "score": 8, "wickets": 0, "bat_prob": 0.51, "batting_team": "Team A"},
                {"innings": 1, "overs": 1.1, "score": 12, "wickets": 0, "bat_prob": 0.54, "batting_team": "Team A"},
            ]
        }), encoding="utf-8")
        (tmp_path / "abc123_livematch.json").write_text(json.dumps({
            "state": {"bowler1_name": "Bowler B", "toss_decision": "bat"},
            "features": {"projected_score": 176.0, "resource_win_prob": 0.58},
        }), encoding="utf-8")

        state = _enrich_detail_state({
            "score": 12,
            "wickets": 0,
            "overs": 1.1,
            "bat_win_prob": 0.54,
            "features": {},
        }, str(output))

        assert state["bowler1_name"] == "Bowler B"
        assert state["projection"]["projected_score"] == 176.0
        assert len(state["chart_history"]) == 2
        assert len(state["commentary"]) == 2
