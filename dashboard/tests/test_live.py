"""Tests for live prediction endpoints."""

from __future__ import annotations

import json
import os
import signal
import subprocess
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.prediction_manager import Prediction, PredictionManager
from app.public import PublicMatchService
from app.routers.live import _build_projection, _derive_commentary_from_history, _enrich_detail_state


class FakeProc:
    def __init__(self, returncode=None):
        self.returncode = returncode
        self.killed = False
        self.pid = 12345

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def send_signal(self, signal):
        self.returncode = -2

    def kill(self):
        self.killed = True
        self.returncode = -9


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

    def test_cleanup_removes_expired_finished_predictions(self, tmp_path):
        manager = PredictionManager()
        proc = FakeProc(returncode=0)
        pred = Prediction(
            prediction_id="finished-old",
            user_id="user-1",
            match_url="https://crex.com/scoreboard/example/live",
            league_key="IPL",
            league_code="ipl",
            output_json_path=str(tmp_path / "finished-old.json"),
            proc=proc,
        )
        manager._predictions[pred.id] = pred

        pred.refresh_status()
        pred.status_updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)

        removed = manager.cleanup_expired(Settings(FINISHED_MATCH_RETENTION_MINUTES=1))

        assert removed == 1
        assert manager.list_predictions() == []

    def test_cleanup_kills_stale_running_predictions(self, tmp_path):
        manager = PredictionManager()
        state_path = tmp_path / "stale-running.json"
        state_path.write_text("{}", encoding="utf-8")
        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp()
        os.utime(state_path, (old_ts, old_ts))

        proc = FakeProc(returncode=None)
        pred = Prediction(
            prediction_id="stale-running",
            user_id="user-1",
            match_url="https://crex.com/scoreboard/example/live",
            league_key="IPL",
            league_code="ipl",
            output_json_path=str(state_path),
            proc=proc,
        )
        manager._predictions[pred.id] = pred

        removed = manager.cleanup_expired(Settings(STALE_RUNNING_MATCH_MINUTES=1))

        assert removed == 1
        assert proc.killed is True
        assert manager.list_predictions() == []

    def test_stop_escalates_to_group_sigkill_when_predictor_ignores_sigterm(self, tmp_path, monkeypatch):
        class StubbornProc(FakeProc):
            def wait(self, timeout=None):
                raise subprocess.TimeoutExpired("predictor", timeout)

        proc = StubbornProc(returncode=None)
        pred = Prediction(
            prediction_id="stubborn-predictor",
            user_id="user-1",
            match_url="https://crex.com/scoreboard/example/live",
            league_key="IPL",
            league_code="ipl",
            output_json_path=str(tmp_path / "stubborn-predictor.json"),
            proc=proc,
        )
        signals = []
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setattr(signal, "SIGKILL", 9, raising=False)
        monkeypatch.setattr(os, "getpgid", lambda _: 4321, raising=False)
        monkeypatch.setattr(
            os,
            "killpg",
            lambda pgid, signum: signals.append((pgid, signum)),
            raising=False,
        )

        pred.stop()

        assert signals == [(4321, signal.SIGTERM), (4321, signal.SIGKILL)]
        assert proc.killed is True
        assert pred.status == "stopped"

    def test_find_active_by_url_ignores_stale_running_prediction(self, tmp_path):
        manager = PredictionManager()
        state_path = tmp_path / "stale-find.json"
        state_path.write_text("{}", encoding="utf-8")
        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=40)).timestamp()
        os.utime(state_path, (old_ts, old_ts))

        proc = FakeProc(returncode=None)
        pred = Prediction(
            prediction_id="stale-find",
            user_id="user-1",
            match_url="https://crex.com/scoreboard/example/live",
            league_key="IPL",
            league_code="ipl",
            output_json_path=str(state_path),
            proc=proc,
        )
        manager._predictions[pred.id] = pred

        found = manager.find_active_by_url("https://crex.com/scoreboard/example/live", "IPL")

        assert found is None
        assert pred.status == "stopped"
        assert proc.killed is True

    def test_cleanup_marks_completed_running_prediction_finished(self, tmp_path):
        manager = PredictionManager()
        state_path = tmp_path / "completed-running.json"
        state_path.write_text(json.dumps({
            "is_second_innings": True,
            "score": 181,
            "wickets": 4,
            "overs": 18.2,
            "target": 180,
            "total_overs": 20,
        }), encoding="utf-8")

        proc = FakeProc(returncode=None)
        pred = Prediction(
            prediction_id="completed-running",
            user_id="user-1",
            match_url="https://crex.com/scoreboard/example/live",
            league_key="IPL",
            league_code="ipl",
            output_json_path=str(state_path),
            proc=proc,
        )
        manager._predictions[pred.id] = pred

        removed = manager.cleanup_expired(Settings(FINISHED_MATCH_RETENTION_MINUTES=60))

        assert removed == 0
        assert pred.status == "finished"
        assert proc.killed is True


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


class TestPublicMatchService:
    def test_list_ipl_today_skips_finished_predictions(self, tmp_path):
        manager = PredictionManager()

        live_path = tmp_path / "live.json"
        live_path.write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "batting_team": "CSK",
            "bowling_team": "PBKS",
            "score": 52,
            "wickets": 1,
            "overs": 6.2,
            "bat_win_prob": 0.61,
        }), encoding="utf-8")

        finished_path = tmp_path / "finished.json"
        finished_path.write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "batting_team": "MI",
            "bowling_team": "DC",
            "score": 171,
            "wickets": 4,
            "overs": 19.3,
            "target": 170,
            "is_second_innings": True,
            "bat_win_prob": 0.99,
        }), encoding="utf-8")

        live_pred = Prediction(
            prediction_id="live-1",
            user_id="system:auto-scheduler",
            match_url="https://crex.com/cricket-live-score/csk-vs-pbks-match-updates-abc",
            league_key="IPL",
            league_code="ipl",
            output_json_path=str(live_path),
            proc=FakeProc(returncode=None),
        )
        finished_pred = Prediction(
            prediction_id="finished-1",
            user_id="system:auto-scheduler",
            match_url="https://crex.com/cricket-live-score/mi-vs-dc-match-updates-def",
            league_key="IPL",
            league_code="ipl",
            output_json_path=str(finished_path),
            proc=FakeProc(returncode=0),
        )
        finished_pred.set_status("finished")

        manager._predictions[live_pred.id] = live_pred
        manager._predictions[finished_pred.id] = finished_pred

        rows = PublicMatchService(manager=manager).list_ipl_today()

        assert len(rows) == 1
        assert rows[0].title == "CSK vs PBKS"


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

    def test_projection_falls_back_to_run_rate_when_features_missing(self):
        projection = _build_projection({
            "score": 106,
            "wickets": 3,
            "overs": 10.2,
            "current_run_rate": 10.26,
            "features": {},
        })

        assert projection["balls_remaining"] == 58
        assert round(projection["projected_score"], 1) == 205.2
        assert round(projection["expected_final_score"], 1) == 205.2

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

    def test_enrich_detail_state_exposes_recent_balls_from_ball_data(self):
        state = _enrich_detail_state({
            "score": 28,
            "wickets": 1,
            "overs": 4.1,
            "bat_win_prob": 0.54,
            "balls_data": [
                {"ball_number": 3.1, "runs": 0},
                {"ball_number": 3.2, "runs": 1},
                {"ball_number": 3.3, "runs": 4},
                {"ball_number": 3.4, "runs": 2},
                {"ball_number": 3.5, "runs": 6},
                {"ball_number": 4.0, "runs": 0, "is_wicket": True, "commentary": "Wicket"},
                {"ball_number": 4.1, "runs": 1},
            ],
        })

        assert [ball["label"] for ball in state["recent_balls"]] == ["1", "4", "2", "6", "W", "1"]
        assert state["recent_balls"][2]["is_boundary"] is False
        assert state["recent_balls"][3]["is_boundary"] is True
        assert state["recent_balls"][4]["is_wicket"] is True

    def test_enrich_detail_state_derives_recent_balls_from_history(self):
        state = _enrich_detail_state({
            "score": 57,
            "wickets": 1,
            "overs": 10.4,
            "bat_win_prob": 0.54,
            "history": [
                {"innings": 1, "overs": 10.0, "score": 50, "wickets": 0, "bat_prob": 0.51, "batting_team": "Team A"},
                {"innings": 1, "overs": 10.1, "score": 51, "wickets": 0, "bat_prob": 0.52, "batting_team": "Team A"},
                {"innings": 1, "overs": 10.2, "score": 55, "wickets": 0, "bat_prob": 0.56, "batting_team": "Team A"},
                {"innings": 1, "overs": 10.3, "score": 55, "wickets": 1, "bat_prob": 0.48, "batting_team": "Team A"},
                {"innings": 1, "overs": 10.4, "score": 57, "wickets": 1, "bat_prob": 0.50, "batting_team": "Team A"},
            ],
        })

        assert [ball["label"] for ball in state["recent_balls"]] == ["1", "4", "W", "2"]
        assert state["recent_balls"][1]["is_boundary"] is True
        assert state["recent_balls"][2]["text"] == "55/1"

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
