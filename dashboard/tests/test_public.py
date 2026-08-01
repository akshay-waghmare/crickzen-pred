"""Tests for public acquisition pages and API."""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.prediction_manager import Prediction, PredictionManager
from app.opening_predictions import OpeningArtifactStore
from app.public import PublicMatchService, is_ipl_candidate, public_payload


class FakeScheduler:
    def __init__(self, candidates, prematch_candidates=None):
        self.candidates = candidates
        self.prematch_candidates = prematch_candidates or []

    def status(self):
        return {
            "enabled": True,
            "running": True,
            "last_candidates": self.candidates,
            "last_prematch_candidates": self.prematch_candidates,
        }


def _opening_artifact(path: Path):
    path.write_text(json.dumps({
        "schema_version": 1,
        "estimator": "elo",
        "format": "T20",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": datetime.now(timezone.utc).date().isoformat(),
        "minimum_prior_matches": 5,
        "rating_scale": 400.0,
        "calibrator": {"intercept": 0.0, "slope": 1.0},
        "teams": {
            "Argentina": {"rating": 1515.8, "matches": 44, "wins": 19},
            "Canada": {"rating": 1602.5, "matches": 94, "wins": 50},
        },
    }), encoding="utf-8")


def test_public_api_matches_no_auth(client):
    resp = client.get("/api/public/matches")

    assert resp.status_code == 200
    assert "matches" in resp.json()


def test_public_api_ipl_today_no_auth(client):
    resp = client.get("/api/public/ipl-today")

    assert resp.status_code == 200
    assert "matches" in resp.json()


def test_public_api_unknown_slug_404(client):
    resp = client.get("/api/public/matches/not-a-real-match")

    assert resp.status_code == 404
    assert resp.json()["detail"]["suggested_url"] == "/ipl-prediction-today"


def test_public_pages_no_auth(client):
    for path in ["/", "/ipl-prediction-today", "/match/not-a-real-match"]:
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code in (200, 404)
        assert resp.headers["content-type"].startswith("text/html")


def test_public_home_is_not_dashboard_redirect(client):
    resp = client.get("/", follow_redirects=False)

    assert resp.status_code == 200
    assert "location" not in resp.headers


def test_ipl_candidate_filter_excludes_mixed_crex_feed():
    assert is_ipl_candidate({
        "url": "https://crex.com/cricket-live-score/dc-vs-rcb-39th-match-indian-premier-league-2026-match-updates-118K",
        "league": "IPL",
        "source": "https://crex.com/series/indian-premier-league-2026-1PW",
        "label": "DC 39th T20 on Apr 27, 2:00 PM RCB",
    })
    assert not is_ipl_candidate({
        "url": "https://crex.com/cricket-live-score/ban-vs-nz-1st-t20-new-zealand-tour-of-bangladesh-2026-match-updates-10Z3",
        "league": "IPL",
        "source": "https://crex.com/cricket-live-score",
        "label": "BAN vs NZ live",
    })


def test_public_service_ipl_today_filters_candidates():
    service = PublicMatchService(
        scheduler=FakeScheduler([
            {
                "url": "https://crex.com/cricket-live-score/dc-vs-rcb-39th-match-indian-premier-league-2026-match-updates-118K",
                "league": "IPL",
                "source": "https://crex.com/series/indian-premier-league-2026-1PW",
                "label": "DC 39th T20 on Apr 27, 2:00 PM RCB",
                "is_live": False,
            },
            {
                "url": "https://crex.com/cricket-live-score/ban-vs-nz-1st-t20-new-zealand-tour-of-bangladesh-2026-match-updates-10Z3",
                "league": "IPL",
                "source": "https://crex.com/cricket-live-score",
                "label": "BAN vs NZ live",
                "is_live": True,
            },
        ])
    )

    matches = [public_payload(match) for match in service.list_ipl_today()]

    assert len(matches) == 1
    assert "dc" in matches[0]["slug"]


def test_public_service_emits_only_a_ready_upcoming_opening_row(tmp_path):
    artifact_path = tmp_path / "opening.json"
    _opening_artifact(artifact_path)
    candidate = {
        "url": "https://crex.com/cricket-live-score/arg-w-vs-can-w-4th-t20-match-updates-12YR",
        "is_live": False,
        "match_format": "T20",
        "scheduled_start_time": int((datetime.now(timezone.utc) + timedelta(days=2)).timestamp() * 1000),
        "team1_name": "Argentina Women",
        "team2_name": "Canada Women",
        "label": "Argentina Women vs Canada Women, 4th T20",
    }
    service = PublicMatchService(
        manager=PredictionManager(),
        scheduler=FakeScheduler([], [candidate]),
        opening_store=OpeningArtifactStore(artifact_path),
    )

    matches = [public_payload(match) for match in service.list_matches()]

    assert len(matches) == 1
    assert matches[0]["status"] == "upcoming"
    assert matches[0]["match_url"] == candidate["url"]
    assert matches[0]["probability_team"] == "Argentina Women"
    assert matches[0]["model_label"] == "T20 opening Elo v1"
    assert matches[0]["win_probability_pct"] is not None


def test_public_response_does_not_leak_premium_keys(client):
    resp = client.get("/api/public/matches")
    text = resp.text

    for key in [
        "monte_carlo",
        "odm",
        "blend",
        "features",
        "pred_state",
        "history",
        "chart_history",
        "commentary",
        "ml_prob",
        "mc_prob",
        "ml_weight",
        "mc_weight",
    ]:
        assert f'"{key}"' not in text


def test_public_page_sets_tracking_cookie(client):
    resp = client.get("/?utm_source=instagram&utm_medium=reel&utm_campaign=may-launch")

    cookie_header = resp.headers.get("set-cookie", "")
    assert resp.status_code == 200
    assert "cz_vid=" in cookie_header
    assert "cz_landing_path=" in cookie_header
    assert "cz_utm_source=instagram" in cookie_header


class _FakeProc:
    def __init__(self, returncode=None):
        self.returncode = returncode
        self.pid = 12345

    def poll(self):
        return self.returncode

    def wait(self):
        return self.returncode

    def send_signal(self, signal):
        self.returncode = -2

    def kill(self):
        self.returncode = -9


def test_public_service_skips_stale_running_prediction(tmp_path):
    manager = PredictionManager()
    output = tmp_path / "stale-public.json"
    output.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "batting_team": "MI",
        "bowling_team": "PBKS",
        "score": 81,
        "wickets": 2,
        "overs": 8.5,
        "bat_win_prob": 0.49,
    }), encoding="utf-8")
    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=8)).timestamp()
    os.utime(output, (old_ts, old_ts))

    pred = Prediction(
        prediction_id="stale-public",
        user_id="system:auto-scheduler",
        match_url="https://crex.com/cricket-live-score/mi-vs-pbks-match-updates-xyz",
        league_key="IPL",
        league_code="ipl",
        output_json_path=str(output),
        proc=_FakeProc(returncode=None),
    )
    manager._predictions[pred.id] = pred

    rows = PublicMatchService(manager=manager).list_matches()

    assert rows == []


def test_completed_archive_rehydrates_nested_livematch_state(monkeypatch, tmp_path):
    state_dir = tmp_path / "dashboard_states"
    state_dir.mkdir()
    prediction_id = "completed-archive"
    match_url = "https://crex.com/cricket-live-score/msg-vs-tr-match-updates-ZKN"
    (state_dir / f"{prediction_id}_livematch.json").write_text(json.dumps({
        "match_url": match_url,
        "model_dir": "models/t20_all_v2",
        "bat_win_prob": 1.0,
        "history": [{
            "overs": 17.2,
            "score": 140,
            "wickets": 4,
            "innings": 2,
            "bat_prob": 1.0,
            "batting_team": "MSG",
            "bowling_team": "TR",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
        "state": {
            "is_second_innings": True,
            "score": 140,
            "wickets": 4,
            "overs": 17.2,
            "total_overs": 20,
            "target": 140,
            "batting_team": "MSG",
            "bowling_team": "TR",
        },
    }), encoding="utf-8")
    monkeypatch.setattr("app.public.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("app.public.get_settings", lambda: SimpleNamespace(STATE_DIR="dashboard_states"))

    detail = PublicMatchService(manager=PredictionManager()).get_match_by_source_url(match_url)

    assert detail is not None
    assert detail.status == "completed"
    assert detail.match_url == match_url
    assert detail.win_probability_pct == 100
    assert detail.prediction_history
