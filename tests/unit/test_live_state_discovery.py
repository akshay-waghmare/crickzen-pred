from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bbl_pipeline.app.live_state_discovery import (
    AUTO_CURRENT_SOURCE_VALUE,
    discover_current_state_json,
    resolve_live_state_path,
)


def _write_state(base_path: Path, payload: dict, sidecar_last_ball: str = "0.0") -> None:
    base_path.write_text(json.dumps(payload), encoding="utf-8")
    sidecar_path = base_path.with_name(f"{base_path.stem}_livematch.json")
    sidecar_path.write_text(json.dumps({"state": {"last_ball_number": sidecar_last_ball}}), encoding="utf-8")


def test_discover_current_state_json_prefers_active_match(tmp_path: Path) -> None:
    now = datetime(2026, 5, 6, 14, 0, tzinfo=timezone.utc)
    completed_payload = {
        "timestamp": (now - timedelta(seconds=30)).isoformat(),
        "batting_team": "Delhi Capitals",
        "bowling_team": "Mumbai Indians",
        "score": 175,
        "wickets": 7,
        "overs": 20.0,
        "target": 171,
        "is_second_innings": True,
        "total_overs": 20,
    }
    active_payload = {
        "timestamp": (now - timedelta(seconds=20)).isoformat(),
        "batting_team": "Sunrisers Hyderabad",
        "bowling_team": "Punjab Kings",
        "score": 32,
        "wickets": 0,
        "overs": 2.2,
        "target": None,
        "is_second_innings": False,
        "total_overs": 20,
    }

    completed_path = tmp_path / "ipl_old.json"
    active_path = tmp_path / "ipl_live.json"
    _write_state(completed_path, completed_payload, sidecar_last_ball="20.0")
    _write_state(active_path, active_payload, sidecar_last_ball="2.2")

    active_stat = active_path.stat()
    os.utime(completed_path, (active_stat.st_atime + 5, active_stat.st_mtime + 5))

    selected = discover_current_state_json(tmp_path, now=now)

    assert selected == active_path


def test_resolve_live_state_path_returns_auto_selected_file(tmp_path: Path) -> None:
    now = datetime(2026, 5, 6, 14, 0, tzinfo=timezone.utc)
    payload = {
        "timestamp": (now - timedelta(seconds=10)).isoformat(),
        "batting_team": "Sunrisers Hyderabad",
        "bowling_team": "Punjab Kings",
        "score": 32,
        "wickets": 0,
        "overs": 2.2,
        "target": None,
        "is_second_innings": False,
        "total_overs": 20,
    }
    state_path = tmp_path / "pbks_srh.json"
    _write_state(state_path, payload, sidecar_last_ball="2.2")

    resolved, note = resolve_live_state_path(AUTO_CURRENT_SOURCE_VALUE, source_dir=tmp_path, now=now)

    assert resolved == str(state_path)
    assert note == "Auto-selected current feed: pbks_srh.json"


def test_resolve_live_state_path_reports_missing_auto_source(tmp_path: Path) -> None:
    resolved, note = resolve_live_state_path(AUTO_CURRENT_SOURCE_VALUE, source_dir=tmp_path)

    assert resolved is None
    assert note == f"No active dashboard state found in {tmp_path}"
