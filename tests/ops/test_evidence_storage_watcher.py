from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from bbl_pipeline.ops.evidence_storage_watcher import (
    WatcherConfig,
    audit_evidence_storage,
    classify_match_format,
    match_slug_from_url,
)


MATCH_URL = "https://crex.com/cricket-live-score/dg-vs-rd-ntb-t20-blast-2026-match-updates-13F3"


def _write_dashboard(dashboard_dir: Path, now: datetime, *, prediction_id: str = "prediction-1") -> None:
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": (now - timedelta(seconds=20)).isoformat(),
        "match_url": MATCH_URL,
        "league": "ntb",
        "state": {
            "batting_team": "Dublin Guardians",
            "bowling_team": "Rotterdam Dockers",
            "score": 42,
            "wickets": 1,
            "overs": 5.2,
            "is_second_innings": False,
            "total_overs": 20,
        },
    }
    base_path = dashboard_dir / f"{prediction_id}.json"
    sidecar_path = dashboard_dir / f"{prediction_id}_livematch.json"
    base_path.write_text(json.dumps(payload), encoding="utf-8")
    sidecar_path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(base_path, (now.timestamp(), now.timestamp()))
    os.utime(sidecar_path, (now.timestamp(), now.timestamp()))


def _write_evidence(states_dir: Path, now: datetime, *, duplicate: bool = False) -> Path:
    path = states_dir / "ntb" / f"{match_slug_from_url(MATCH_URL)}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "match_id": [match_slug_from_url(MATCH_URL)],
        "league": ["ntb"],
        "timestamp": [now - timedelta(seconds=10)],
        "innings": [1],
        "over_number": [1],
        "ball_in_over": [1],
        "match_url": [MATCH_URL],
        "state_key": ["inn1:over1:ball1:runs1:wickets0"],
        "batting_team": ["Dublin Guardians"],
        "bowling_team": ["Rotterdam Dockers"],
        "striker_name": ["A Batter"],
        "non_striker_name": ["B Batter"],
        "bowler_name": ["C Bowler"],
        "bowler_overs": [0.1],
        "bowler_runs": [1],
        "bowler_wickets": [0],
        "features_json": ['{"resource_pct": 0.9}'],
        "inference_context_json": ['{"model": "incumbent"}'],
        "features_complete": [True],
        "team_identity_complete": [True],
        "model_probability_valid": [True],
        "market_probability_valid": [False],
        "model_final_prob": [0.62],
        "market_status": ["unavailable"],
        "market_unavailable_reason": ["provider_no_market"],
    }
    if duplicate:
        row = {key: values * 2 for key, values in row.items()}
    pq.write_table(pa.table(row), path)
    return path


def _config(tmp_path: Path) -> WatcherConfig:
    return WatcherConfig(
        dashboard_dir=tmp_path / "dashboard_states",
        match_states_dir=tmp_path / "match_states",
        report_path=tmp_path / "model_reviews" / "evidence_watcher.json",
        events_path=tmp_path / "model_reviews" / "evidence_watcher_events.jsonl",
        dashboard_active_seconds=600,
        evidence_grace_seconds=180,
        evidence_stale_seconds=300,
    )


def test_match_slug_handles_trailing_slash_and_query() -> None:
    assert match_slug_from_url(MATCH_URL) == "dg-vs-rd-ntb-t20-blast-2026-match-updates-13F3"
    assert match_slug_from_url(f"{MATCH_URL}/?tab=scorecard") == "dg-vs-rd-ntb-t20-blast-2026-match-updates-13F3"


def test_classify_match_format_only_allows_t20_and_odi() -> None:
    assert classify_match_format(MATCH_URL, {"state": {"total_overs": 20}}) == "t20"
    assert classify_match_format("https://crex.com/cricket-live-score/a-vs-b-odi-match-test", {"state": {"total_overs": 50}}) == "test"
    assert classify_match_format("https://crex.com/cricket-live-score/a-vs-b-3rd-odi", {"state": {"total_overs": 50}}) == "odi"


def test_audit_ignores_test_match_dashboard_state(tmp_path: Path) -> None:
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    config = _config(tmp_path)
    _write_dashboard(config.dashboard_dir, now)
    for path in (config.dashboard_dir / "prediction-1.json", config.dashboard_dir / "prediction-1_livematch.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["match_url"] = "https://crex.com/cricket-live-score/a-vs-b-test-match-2026"
        payload["state"]["total_overs"] = 90
        path.write_text(json.dumps(payload), encoding="utf-8")
        os.utime(path, (now.timestamp(), now.timestamp()))

    report = audit_evidence_storage(config, now=now)

    assert report["status"] == "healthy"
    assert report["active_prediction_count"] == 0


def test_audit_is_healthy_and_event_is_transition_only(tmp_path: Path) -> None:
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    config = _config(tmp_path)
    _write_dashboard(config.dashboard_dir, now)
    _write_evidence(config.match_states_dir, now)

    first = audit_evidence_storage(config, now=now)
    second = audit_evidence_storage(config, now=now)

    assert first["status"] == "healthy"
    assert first["active_prediction_count"] == 1
    assert first["matches"][0]["row_count"] == 1
    assert second["status"] == "healthy"
    assert len(config.events_path.read_text(encoding="utf-8").splitlines()) == 1


def test_audit_raises_critical_when_active_evidence_is_missing(tmp_path: Path) -> None:
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    config = _config(tmp_path)
    _write_dashboard(config.dashboard_dir, now)
    # Make the active state older than the flush grace window.
    payload_path = config.dashboard_dir / "prediction-1.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["timestamp"] = (now - timedelta(seconds=240)).isoformat()
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    sidecar_path = config.dashboard_dir / "prediction-1_livematch.json"
    sidecar_path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(payload_path, (now.timestamp(), now.timestamp()))
    os.utime(sidecar_path, (now.timestamp(), now.timestamp()))

    report = audit_evidence_storage(config, now=now)

    assert report["status"] == "critical"
    assert any(issue["code"] == "evidence_missing" for issue in report["issues"])


def test_audit_catches_duplicate_ball_keys(tmp_path: Path) -> None:
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    config = _config(tmp_path)
    _write_dashboard(config.dashboard_dir, now)
    _write_evidence(config.match_states_dir, now, duplicate=True)

    report = audit_evidence_storage(config, now=now)

    assert report["status"] == "critical"
    assert any(issue["code"] == "duplicate_state_keys" for issue in report["issues"])


def test_audit_does_not_flag_pre_match_prediction_before_first_ball(tmp_path: Path) -> None:
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    config = _config(tmp_path)
    _write_dashboard(config.dashboard_dir, now)
    for path in (config.dashboard_dir / "prediction-1.json", config.dashboard_dir / "prediction-1_livematch.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["timestamp"] = (now - timedelta(seconds=240)).isoformat()
        payload["state"].update({"score": 0, "overs": 0.0})
        payload.pop("ball_history", None)
        path.write_text(json.dumps(payload), encoding="utf-8")
        os.utime(path, (now.timestamp(), now.timestamp()))

    report = audit_evidence_storage(config, now=now)

    assert report["status"] == "healthy"
    assert report["matches"][0]["phase"] == "pre_match"
