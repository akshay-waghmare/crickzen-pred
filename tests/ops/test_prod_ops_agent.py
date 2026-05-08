from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

from bbl_pipeline.ops.prod_ops_agent import audit_state_directory


def _write_state(base_path: Path, payload: dict, sidecar: dict | None = None) -> None:
    base_path.write_text(json.dumps(payload), encoding="utf-8")
    if sidecar is not None:
        sidecar_path = base_path.with_name(f"{base_path.stem}_livematch.json")
        sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")


def test_audit_flags_stale_completed_current_and_recommends_active(tmp_path: Path) -> None:
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)

    completed_payload = {
        "timestamp": (now - timedelta(minutes=4)).isoformat(),
        "batting_team": "Delhi Capitals",
        "bowling_team": "Mumbai Indians",
        "score": 170,
        "wickets": 7,
        "overs": 20.0,
        "target": 171,
        "is_second_innings": True,
        "total_overs": 20,
    }
    active_payload = {
        "timestamp": (now - timedelta(seconds=20)).isoformat(),
        "batting_team": "Chennai Super Kings",
        "bowling_team": "Punjab Kings",
        "score": 84,
        "wickets": 2,
        "overs": 9.4,
        "target": None,
        "is_second_innings": False,
        "total_overs": 20,
    }

    stale_match = tmp_path / "ipl_old.json"
    active_match = tmp_path / "ipl_live.json"
    _write_state(
        stale_match,
        completed_payload,
        sidecar={"state": {"last_ball_number": "20.0"}},
    )
    _write_state(
        active_match,
        active_payload,
        sidecar={"state": {"last_ball_number": "9.4"}},
    )

    # Force the completed file to look newer on disk than the active file.
    active_stat = active_match.stat()
    os.utime(stale_match, (active_stat.st_atime + 5, active_stat.st_mtime + 5))

    report = audit_state_directory(
        tmp_path,
        stale_after_seconds=120,
        completed_grace_seconds=180,
        now=now,
    )

    assert report.current_candidate is not None
    assert report.current_candidate.match_id == "ipl_old"
    assert report.recommended_candidate is not None
    assert report.recommended_candidate.match_id == "ipl_live"
    assert report.needs_attention is True
    assert any("completed match" in reason for reason in report.reasons)
    assert any("Recommended active match" in reason for reason in report.reasons)


def test_audit_returns_no_attention_for_single_fresh_active_match(tmp_path: Path) -> None:
    now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    payload = {
        "timestamp": (now - timedelta(seconds=30)).isoformat(),
        "batting_team": "RCB",
        "bowling_team": "GT",
        "score": 45,
        "wickets": 1,
        "overs": 5.2,
        "target": None,
        "is_second_innings": False,
        "total_overs": 20,
    }
    _write_state(
        tmp_path / "ipl_live.json",
        payload,
        sidecar={"state": {"last_ball_number": "5.2"}},
    )

    report = audit_state_directory(tmp_path, stale_after_seconds=120, now=now)

    assert report.current_candidate is not None
    assert report.recommended_candidate is not None
    assert report.current_candidate.match_id == "ipl_live"
    assert report.recommended_candidate.match_id == "ipl_live"
    assert report.needs_attention is False
