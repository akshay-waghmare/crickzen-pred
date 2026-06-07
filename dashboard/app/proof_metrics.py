"""
Dashboard-side loader for proof-metrics snapshot artifacts.

Reads the latest snapshot JSON files from data/dashboard_metrics/
and returns typed summary, segment, and ledger payloads for the proof API.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional

from datetime import datetime, timezone

STALENESS_THRESHOLD_HOURS = 24
DEFAULT_SNAPSHOT_DIR = Path("data/dashboard_metrics")


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, float) and math.isinf(value):
        return None
    return float(value)


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)


def _is_stale(data: dict[str, Any]) -> bool:
    freshness = data.get("freshness", {})
    built_at = freshness.get("built_at")
    if not built_at:
        return True
    try:
        built_dt = datetime.fromisoformat(built_at)
        age = datetime.now(timezone.utc) - built_dt
        return age.total_seconds() > STALENESS_THRESHOLD_HOURS * 3600
    except (ValueError, TypeError):
        return True


def load_latest_summary(
    league: str,
    snapshot_dir: Optional[Path] = None,
) -> dict[str, Any]:
    base = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    summary_path = base / "latest" / f"{league.lower()}_summary.json"
    data = _read_json(summary_path)
    if data is None:
        return {
            "league": league,
            "window": None,
            "status": "not_ready",
            "probability_metrics": None,
            "accuracy_metrics": None,
            "freshness": None,
            "definitions": {},
        }
    if _is_stale(data):
        data["freshness"] = data.get("freshness", {})
        data["freshness"]["stale"] = True
    return data


def load_latest_segments(
    league: str,
    snapshot_dir: Optional[Path] = None,
) -> list[dict[str, Any]]:
    base = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    segments_path = base / "latest" / f"{league.lower()}_segments.json"
    data = _read_json(segments_path)
    if data is None:
        return []
    return data


def load_latest_ledger(
    league: str,
    snapshot_dir: Optional[Path] = None,
) -> list[dict[str, Any]]:
    base = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    ledger_path = base / "latest" / f"{league.lower()}_ledger.json"
    data = _read_json(ledger_path)
    if data is None:
        return []
    return data


def load_latest_manifest(
    league: str,
    snapshot_dir: Optional[Path] = None,
) -> dict[str, Any]:
    base = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    manifest_path = base / "latest" / f"{league.lower()}_manifest.json"
    data = _read_json(manifest_path)
    if data is None:
        return {"status": "not_ready", "league": league}
    return data


def load_accuracy_summary(
    league: str,
    snapshot_dir: Optional[Path] = None,
) -> dict[str, Any]:
    base = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    acc_path = base / "latest" / f"{league.lower()}_accuracy.json"
    data = _read_json(acc_path)
    if data is None:
        return {
            "league": league,
            "window": None,
            "status": "not_ready",
            "accuracy_metrics": None,
            "freshness": None,
            "definitions": {},
        }
    if _is_stale(data):
        data["freshness"] = data.get("freshness", {})
        data["freshness"]["stale"] = True
    return data
