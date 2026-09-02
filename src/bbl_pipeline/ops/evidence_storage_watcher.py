"""Watch live prediction evidence for missing, stale, or malformed storage.

The predictor writes two different kinds of state:

* ``dashboard_states`` is a rolling, frequently updated live state.
* ``match_states/<league>/<match-slug>.parquet`` is the durable per-ball
  evidence used by the market comparison and promotion reports.

This watcher joins those surfaces by the provider URL and checks them during a
match.  It deliberately reports data-quality failures rather than restarting
predictors or changing public probabilities.  The report is atomic and the
event log only records transitions, so a long-running watcher remains cheap
and useful to an operator.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any
from urllib.parse import urlparse

import pyarrow.parquet as pq


DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_DASHBOARD_ACTIVE_SECONDS = 120
DEFAULT_EVIDENCE_GRACE_SECONDS = 180
DEFAULT_EVIDENCE_STALE_SECONDS = 300
DEFAULT_MIN_FEATURE_COMPLETENESS = 0.95
DEFAULT_MAX_DASHBOARD_FILES = 500
DEFAULT_MAX_EVIDENCE_FILES = 500

_VALID_MARKET_STATUSES = {"available", "unavailable"}
_REQUIRED_COLUMNS = (
    "match_id",
    "league",
    "timestamp",
    "innings",
    "over_number",
    "ball_in_over",
    "match_url",
    "state_key",
    "batting_team",
    "bowling_team",
    "striker_name",
    "non_striker_name",
    "bowler_name",
    "bowler_overs",
    "bowler_runs",
    "bowler_wickets",
    "features_json",
    "inference_context_json",
    "features_complete",
    "team_identity_complete",
    "model_probability_valid",
    "market_probability_valid",
    "model_final_prob",
    "market_status",
    "market_unavailable_reason",
)
_QUALITY_COLUMNS = (
    "timestamp",
    "match_id",
    "match_url",
    "state_key",
    "batting_team",
    "bowling_team",
    "striker_name",
    "non_striker_name",
    "bowler_name",
    "features_complete",
    "team_identity_complete",
    "model_probability_valid",
    "market_probability_valid",
    "model_final_prob",
    "market_status",
    "market_unavailable_reason",
)


@dataclass(frozen=True)
class WatcherConfig:
    """Filesystem and timing contract for one watcher run."""

    dashboard_dir: Path
    match_states_dir: Path
    report_path: Path
    events_path: Path
    dashboard_active_seconds: int = DEFAULT_DASHBOARD_ACTIVE_SECONDS
    evidence_grace_seconds: int = DEFAULT_EVIDENCE_GRACE_SECONDS
    evidence_stale_seconds: int = DEFAULT_EVIDENCE_STALE_SECONDS
    min_feature_completeness: float = DEFAULT_MIN_FEATURE_COMPLETENESS
    max_dashboard_files: int = DEFAULT_MAX_DASHBOARD_FILES
    max_evidence_files: int = DEFAULT_MAX_EVIDENCE_FILES


@dataclass(frozen=True)
class DashboardMatch:
    """A live prediction assembled from the base JSON and its sidecar."""

    prediction_id: str
    dashboard_path: str
    sidecar_path: str | None
    match_url: str
    league: str
    match_format: str
    payload_timestamp: str | None
    activity_at: datetime
    payload: dict[str, Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            seconds = float(value)
            if seconds > 100_000_000_000:
                seconds /= 1000.0
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _payload_timestamp(payload: dict[str, Any]) -> datetime | None:
    for key in ("timestamp", "updated_at", "updatedAt", "last_updated", "lastUpdated"):
        parsed = _parse_timestamp(payload.get(key))
        if parsed is not None:
            return parsed
    state = payload.get("state")
    if isinstance(state, dict):
        for key in ("timestamp", "updated_at", "updatedAt", "last_updated", "lastUpdated"):
            parsed = _parse_timestamp(state.get(key))
            if parsed is not None:
                return parsed
    return None


def _state_payload(payload: dict[str, Any]) -> dict[str, Any]:
    state = payload.get("state")
    return state if isinstance(state, dict) else payload


def _is_terminal(payload: dict[str, Any]) -> bool:
    state = _state_payload(payload)
    if payload.get("winner") or state.get("winner"):
        return True
    result = str(payload.get("result_type") or state.get("result_type") or "").lower()
    if result in {"completed", "no_result", "abandoned"}:
        return True
    if not state.get("is_second_innings"):
        return False
    try:
        score = float(state.get("score"))
        target = state.get("target")
        if target is not None and score >= float(target):
            return True
    except (TypeError, ValueError):
        pass
    try:
        if float(state.get("wickets")) >= 10:
            return True
    except (TypeError, ValueError):
        pass
    try:
        total_overs = float(state.get("total_overs") or 20)
        if float(state.get("overs")) >= total_overs:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _has_observed_ball(payload: dict[str, Any]) -> bool:
    """Return whether the live state has progressed past the pre-match snapshot."""
    state = _state_payload(payload)
    try:
        if float(state.get("overs") or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    try:
        if float(state.get("ball") or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    history = payload.get("ball_history") or payload.get("history")
    return isinstance(history, list) and len(history) > 0


def classify_match_format(match_url: str, payload: dict[str, Any]) -> str:
    """Classify the formats supported by the prediction service.

    The prediction scope is deliberately limited to T20 and one-day/ODI
    matches. Test/first-class fixtures and unknown formats are out of scope and
    must not create missing-evidence alerts.
    """
    text = f"{match_url} {payload.get('league', '')}".lower()
    if re.search(r"test[- ]?(match|series|cricket)?|first[- ]class|four[- ]day", text):
        return "test"
    state = _state_payload(payload)
    try:
        total_overs = float(state.get("total_overs"))
        if total_overs > 20:
            return "odi"
        if total_overs > 0:
            return "t20" if total_overs <= 20 else "unknown"
    except (TypeError, ValueError):
        pass
    if re.search(r"(^|[^a-z])t20([^a-z]|$)|twenty20|t20i", text):
        return "t20"
    if re.search(r"(^|[^a-z])odi([^a-z]|$)|one[- ]day|50[- ]over", text):
        return "odi"
    return "unknown"


def _normalise_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}".lower()


def match_slug_from_url(url: str) -> str:
    """Return the provider match slug used as the durable evidence filename."""
    parsed = urlparse((url or "").strip())
    segments = [segment for segment in parsed.path.split("/") if segment]
    for segment in reversed(segments):
        if "-vs-" in segment.lower():
            return re.sub(r"[^A-Za-z0-9._-]+", "-", segment).strip("-")
    return re.sub(r"[^A-Za-z0-9._-]+", "-", segments[-1] if segments else "unknown-match").strip("-")


def _json_read(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _file_activity(path: Path, payload: dict[str, Any]) -> datetime:
    payload_at = _payload_timestamp(payload)
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        mtime = _utc_now()
    # The older boundary is intentional.  A predictor that keeps touching a
    # file with a frozen embedded timestamp is not fresh live data.
    return min(payload_at, mtime) if payload_at is not None else mtime


def _prediction_id(path: Path) -> str:
    for suffix in ("_livematch", "_history"):
        if path.stem.endswith(suffix):
            return path.stem[: -len(suffix)]
    return path.stem


def discover_dashboard_matches(
    dashboard_dir: Path,
    *,
    now: datetime,
    active_seconds: int,
    max_files: int = DEFAULT_MAX_DASHBOARD_FILES,
) -> tuple[list[DashboardMatch], list[str]]:
    """Discover recently active predictions without requiring the dashboard DB."""
    errors: list[str] = []
    if not dashboard_dir.exists():
        return [], [f"dashboard state directory is missing: {dashboard_dir}"]

    base_paths = sorted(
        (path for path in dashboard_dir.glob("*.json") if not path.name.endswith(("_history.json", "_livematch.json"))),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )[: max(1, max_files)]
    matches: list[DashboardMatch] = []
    for base_path in base_paths:
        try:
            base_mtime = datetime.fromtimestamp(base_path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if max(0.0, (now - base_mtime).total_seconds()) > max(1, active_seconds):
            continue
        base_payload = _json_read(base_path)
        if base_payload is None:
            errors.append(f"invalid dashboard JSON: {base_path.name}")
            continue
        prediction_id = _prediction_id(base_path)
        sidecar_path = dashboard_dir / f"{prediction_id}_livematch.json"
        sidecar_payload = _json_read(sidecar_path) if sidecar_path.exists() else None
        payload = sidecar_payload or base_payload
        activity_at = min(
            _file_activity(base_path, base_payload),
            _file_activity(sidecar_path, sidecar_payload) if sidecar_payload is not None else _file_activity(base_path, base_payload),
        )
        age = max(0.0, (now - activity_at).total_seconds())
        if age > max(1, active_seconds):
            continue
        match_url = str(payload.get("match_url") or base_payload.get("match_url") or "").strip()
        state = _state_payload(payload)
        league = str(payload.get("league") or payload.get("league_code") or base_payload.get("league") or "").strip()
        if not match_url:
            errors.append(f"active dashboard state has no match_url: {base_path.name}")
            continue
        match_format = classify_match_format(match_url, payload)
        if match_format not in {"t20", "odi"}:
            continue
        if _is_terminal(payload):
            continue
        matches.append(
            DashboardMatch(
                prediction_id=prediction_id,
                dashboard_path=str(base_path),
                sidecar_path=str(sidecar_path) if sidecar_path.exists() else None,
                match_url=match_url,
                league=league,
                match_format=match_format,
                payload_timestamp=(
                    _iso(_payload_timestamp(payload)) if _payload_timestamp(payload) is not None else None
                ),
                activity_at=activity_at,
                payload=payload,
            )
        )
    return matches, errors


def _evidence_paths(root: Path, max_files: int) -> list[Path]:
    if not root.exists():
        return []
    excluded = {"match_metadata.parquet", "all_matches.parquet", "signal_events.parquet", "volatility_profiles.parquet"}
    paths = [path for path in root.rglob("*.parquet") if path.name not in excluded]
    return sorted(paths, key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)[: max(1, max_files)]


def _expected_evidence_path(root: Path, match: DashboardMatch) -> Path:
    league = match.league or "unknown"
    return root / league / f"{match_slug_from_url(match.match_url)}.parquet"


def _as_bool(value: Any) -> bool:
    return value is True or value == 1 or str(value).strip().lower() in {"true", "1", "yes"}


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _evidence_audit(path: Path, match: DashboardMatch, *, now: datetime, config: WatcherConfig) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    expected_path = _expected_evidence_path(config.match_states_dir, match)
    if not _has_observed_ball(match.payload):
        return {
            "prediction_id": match.prediction_id,
            "match_url": match.match_url,
            "league": match.league,
            "format": match.match_format,
            "dashboard_age_seconds": round(max(0.0, (now - match.activity_at).total_seconds()), 1),
            "evidence_path": str(expected_path),
            "evidence_exists": path.exists(),
            "row_count": 0,
            "phase": "pre_match",
            "issues": issues,
            "status": "healthy",
        }
    if not path.exists():
        age = max(0.0, (now - match.activity_at).total_seconds())
        severity = "critical" if age >= config.evidence_grace_seconds else "warning"
        issues.append({
            "severity": severity,
            "code": "evidence_missing",
            "message": f"expected per-ball evidence file is missing: {expected_path}",
        })
        return {
            "prediction_id": match.prediction_id,
            "match_url": match.match_url,
            "league": match.league,
            "format": match.match_format,
            "dashboard_age_seconds": round(max(0.0, (now - match.activity_at).total_seconds()), 1),
            "evidence_path": str(expected_path),
            "evidence_exists": False,
            "row_count": 0,
            "issues": issues,
        }

    try:
        schema = pq.read_schema(path)
        metadata = pq.read_metadata(path)
    except Exception as exc:  # pyarrow raises several file-format exceptions
        issues.append({"severity": "critical", "code": "evidence_unreadable", "message": f"cannot read {path}: {exc}"})
        return {
            "prediction_id": match.prediction_id,
            "match_url": match.match_url,
            "league": match.league,
            "dashboard_age_seconds": round(max(0.0, (now - match.activity_at).total_seconds()), 1),
            "evidence_path": str(path),
            "evidence_exists": True,
            "row_count": 0,
            "issues": issues,
        }

    names = set(schema.names)
    missing_columns = sorted(set(_REQUIRED_COLUMNS) - names)
    if missing_columns:
        issues.append({
            "severity": "critical",
            "code": "schema_incomplete",
            "message": f"missing required evidence columns: {', '.join(missing_columns)}",
        })

    row_count = int(metadata.num_rows)
    if row_count <= 0:
        issues.append({"severity": "critical", "code": "evidence_empty", "message": "evidence file has zero rows"})

    available_quality_columns = [column for column in _QUALITY_COLUMNS if column in names]
    columns: dict[str, list[Any]] = {}
    try:
        table = pq.read_table(path, columns=available_quality_columns)
        columns = {name: table[name].to_pylist() for name in available_quality_columns}
    except Exception as exc:
        issues.append({"severity": "critical", "code": "evidence_rows_unreadable", "message": f"cannot read evidence rows: {exc}"})

    def values(name: str) -> list[Any]:
        return columns.get(name, [])

    timestamps = [_parse_timestamp(value) for value in values("timestamp")]
    valid_timestamps = [value for value in timestamps if value is not None]
    latest_timestamp = max(valid_timestamps) if valid_timestamps else None
    evidence_age = None if latest_timestamp is None else max(0.0, (now - latest_timestamp).total_seconds())
    try:
        file_mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        file_mtime = now
    file_age = max(0.0, (now - file_mtime).total_seconds())

    if not valid_timestamps and row_count:
        issues.append({"severity": "critical", "code": "timestamp_invalid", "message": "no parseable per-ball timestamps"})
    elif evidence_age is not None and evidence_age >= config.evidence_stale_seconds:
        issues.append({"severity": "critical", "code": "evidence_stale", "message": f"latest persisted ball is {evidence_age:.1f}s old"})
    elif evidence_age is not None and evidence_age >= config.evidence_grace_seconds:
        issues.append({"severity": "warning", "code": "evidence_lagging", "message": f"latest persisted ball is {evidence_age:.1f}s old"})

    dashboard_timestamp = _parse_timestamp(match.payload_timestamp)
    if dashboard_timestamp is not None and latest_timestamp is not None:
        lag = max(0.0, (dashboard_timestamp - latest_timestamp).total_seconds())
        if lag >= config.evidence_stale_seconds:
            issues.append({"severity": "critical", "code": "evidence_behind_dashboard", "message": f"evidence trails dashboard state by {lag:.1f}s"})
        elif lag >= config.evidence_grace_seconds:
            issues.append({"severity": "warning", "code": "evidence_behind_dashboard", "message": f"evidence trails dashboard state by {lag:.1f}s"})

    if row_count and "state_key" in columns:
        state_keys = [str(value) for value in values("state_key") if _nonempty(value)]
        duplicate_count = len(state_keys) - len(set(state_keys))
        if duplicate_count:
            issues.append({"severity": "critical", "code": "duplicate_state_keys", "message": f"{duplicate_count} duplicate state_key rows"})

    if row_count and "match_id" in columns:
        match_ids = {str(value).strip() for value in values("match_id") if _nonempty(value)}
        if len(match_ids) > 1:
            issues.append({"severity": "critical", "code": "mixed_match_ids", "message": f"file contains {len(match_ids)} match IDs"})

    expected_url = _normalise_url(match.match_url)
    if row_count and "match_url" in columns:
        urls = {_normalise_url(str(value)) for value in values("match_url") if _nonempty(value)}
        if not urls:
            issues.append({"severity": "critical", "code": "source_url_missing", "message": "evidence rows contain no source URL"})
        elif expected_url not in urls:
            issues.append({"severity": "critical", "code": "source_url_mismatch", "message": "evidence source URL does not match dashboard match URL"})
        elif len(urls) > 1:
            issues.append({"severity": "critical", "code": "mixed_source_urls", "message": f"file contains {len(urls)} source URLs"})

    def ratio(name: str, predicate) -> float | None:
        vals = values(name)
        if not vals:
            return None
        return sum(1 for value in vals if predicate(value)) / len(vals)

    feature_ratio = ratio("features_complete", _as_bool)
    identity_ratio = ratio("team_identity_complete", _as_bool)
    probability_ratio = ratio("model_probability_valid", _as_bool)
    market_status_values = values("market_status")
    market_status_ratio = (
        sum(1 for value in market_status_values if str(value or "").strip().lower() in _VALID_MARKET_STATUSES) / len(market_status_values)
        if market_status_values else None
    )
    if feature_ratio is not None and feature_ratio < config.min_feature_completeness:
        issues.append({"severity": "warning", "code": "feature_completeness_low", "message": f"feature completeness is {feature_ratio:.1%}"})
    if identity_ratio is not None and identity_ratio < 1.0:
        issues.append({"severity": "critical", "code": "team_identity_incomplete", "message": f"team identity is complete for only {identity_ratio:.1%} of rows"})
    if probability_ratio is not None and probability_ratio < config.min_feature_completeness:
        issues.append({"severity": "warning", "code": "model_probability_invalid", "message": f"model probability valid for only {probability_ratio:.1%} of rows"})
    if market_status_ratio is not None and market_status_ratio < 1.0:
        issues.append({"severity": "critical", "code": "market_status_implicit", "message": "market availability is not explicit on every row"})
    if market_status_values:
        for status, reason in zip(market_status_values, values("market_unavailable_reason")):
            if str(status or "").strip().lower() == "unavailable" and not _nonempty(reason):
                issues.append({"severity": "critical", "code": "market_missing_reason", "message": "an unavailable market row has no reason"})
                break

    role_completeness = {
        name: ratio(name, _nonempty)
        for name in ("striker_name", "non_striker_name", "bowler_name")
    }
    if any(value is not None and value < config.min_feature_completeness for value in role_completeness.values()):
        issues.append({"severity": "warning", "code": "role_completeness_low", "message": "striker, non-striker, or bowler is missing on too many rows"})

    status = "healthy"
    if any(issue["severity"] == "critical" for issue in issues):
        status = "critical"
    elif issues:
        status = "warning"
    return {
        "prediction_id": match.prediction_id,
        "match_url": match.match_url,
        "league": match.league,
        "format": match.match_format,
        "dashboard_age_seconds": round(max(0.0, (now - match.activity_at).total_seconds()), 1),
        "evidence_path": str(path),
        "evidence_exists": True,
        "file_age_seconds": round(file_age, 1),
        "evidence_age_seconds": None if evidence_age is None else round(evidence_age, 1),
        "latest_timestamp": _iso(latest_timestamp) if latest_timestamp is not None else None,
        "latest_state_key": (values("state_key")[-1] if values("state_key") else None),
        "row_count": row_count,
        "quality": {
            "feature_completeness": feature_ratio,
            "team_identity_completeness": identity_ratio,
            "model_probability_validity": probability_ratio,
            "market_status_explicitness": market_status_ratio,
            "role_completeness": role_completeness,
        },
        "issues": issues,
        "status": status,
    }


def _severity(status: str) -> int:
    return {"healthy": 0, "warning": 1, "critical": 2}.get(status, 2)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _fingerprint(report: dict[str, Any]) -> str:
    relevant = {
        "status": report.get("status"),
        "issues": report.get("issues", []),
        "matches": [
            {
                "prediction_id": match.get("prediction_id"),
                "status": match.get("status"),
                "row_count": match.get("row_count"),
                "latest_state_key": match.get("latest_state_key"),
            }
            for match in report.get("matches", [])
        ],
    }
    return json.dumps(relevant, sort_keys=True, separators=(",", ":"))


def _append_transition_event(path: Path, report: dict[str, Any], previous: dict[str, Any] | None) -> None:
    if previous is not None and _fingerprint(previous) == _fingerprint(report):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_at": report["checked_at"],
        "status": report["status"],
        "previous_status": previous.get("status") if previous else None,
        "active_prediction_count": report["active_prediction_count"],
        "issues": report["issues"],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, ensure_ascii=True) + "\n")


def audit_evidence_storage(config: WatcherConfig, *, now: datetime | None = None) -> dict[str, Any]:
    """Run one bounded storage audit and persist its machine-readable report."""
    now = now or _utc_now()
    matches, discovery_errors = discover_dashboard_matches(
        config.dashboard_dir,
        now=now,
        active_seconds=config.dashboard_active_seconds,
        max_files=config.max_dashboard_files,
    )
    evidence_paths = _evidence_paths(config.match_states_dir, config.max_evidence_files)
    exact_paths = {path.resolve(): path for path in evidence_paths}
    audits: list[dict[str, Any]] = []
    for match in matches:
        expected = _expected_evidence_path(config.match_states_dir, match)
        path = exact_paths.get(expected.resolve(), expected)
        audit = _evidence_audit(path, match, now=now, config=config)
        audits.append(audit)

    issues: list[dict[str, str]] = [
        {"severity": "critical", "code": "dashboard_discovery", "message": message}
        for message in discovery_errors
    ]
    for audit in audits:
        for issue in audit.get("issues", []):
            issues.append({
                "severity": issue["severity"],
                "code": issue["code"],
                "prediction_id": audit["prediction_id"],
                "message": issue["message"],
            })
    status = "healthy"
    if any(issue["severity"] == "critical" for issue in issues):
        status = "critical"
    elif issues:
        status = "warning"
    report: dict[str, Any] = {
        "schema_version": 1,
        "checked_at": _iso(now),
        "status": status,
        "exit_code": _severity(status),
        "active_prediction_count": len(matches),
        "dashboard_files_seen": min(config.max_dashboard_files, len(list(config.dashboard_dir.glob("*.json"))) if config.dashboard_dir.exists() else 0),
        "evidence_files_seen": len(evidence_paths),
        "config": {
            "dashboard_dir": str(config.dashboard_dir),
            "match_states_dir": str(config.match_states_dir),
            "dashboard_active_seconds": config.dashboard_active_seconds,
            "evidence_grace_seconds": config.evidence_grace_seconds,
            "evidence_stale_seconds": config.evidence_stale_seconds,
            "min_feature_completeness": config.min_feature_completeness,
        },
        "issues": issues,
        "matches": audits,
    }
    previous: dict[str, Any] | None = None
    try:
        if config.report_path.exists():
            raw_previous = json.loads(config.report_path.read_text(encoding="utf-8"))
            previous = raw_previous if isinstance(raw_previous, dict) else None
        _append_transition_event(config.events_path, report, previous)
        _atomic_write_json(config.report_path, report)
    except Exception as exc:
        report["status"] = "critical"
        report["exit_code"] = 2
        report["issues"].append({"severity": "critical", "code": "watcher_storage", "message": f"watcher could not persist its own report: {exc}"})
        # Best effort stdout visibility; do not hide a persistence failure.
        print(json.dumps(report, sort_keys=True), flush=True)
    return report


def _config_from_args(args: argparse.Namespace) -> WatcherConfig:
    return WatcherConfig(
        dashboard_dir=Path(args.dashboard_dir),
        match_states_dir=Path(args.match_states_dir),
        report_path=Path(args.report_path),
        events_path=Path(args.events_path),
        dashboard_active_seconds=max(1, args.dashboard_active_seconds),
        evidence_grace_seconds=max(1, args.evidence_grace_seconds),
        evidence_stale_seconds=max(1, args.evidence_stale_seconds),
        min_feature_completeness=min(1.0, max(0.0, args.min_feature_completeness)),
        max_dashboard_files=max(1, args.max_dashboard_files),
        max_evidence_files=max(1, args.max_evidence_files),
    )


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dashboard-dir", default="data/dashboard_states")
    parser.add_argument("--match-states-dir", default="data/match_states")
    parser.add_argument("--report-path", default="data/model_reviews/evidence_watcher.json")
    parser.add_argument("--events-path", default="data/model_reviews/evidence_watcher_events.jsonl")
    parser.add_argument("--dashboard-active-seconds", type=int, default=DEFAULT_DASHBOARD_ACTIVE_SECONDS)
    parser.add_argument("--evidence-grace-seconds", type=int, default=DEFAULT_EVIDENCE_GRACE_SECONDS)
    parser.add_argument("--evidence-stale-seconds", type=int, default=DEFAULT_EVIDENCE_STALE_SECONDS)
    parser.add_argument("--min-feature-completeness", type=float, default=DEFAULT_MIN_FEATURE_COMPLETENESS)
    parser.add_argument("--max-dashboard-files", type=int, default=DEFAULT_MAX_DASHBOARD_FILES)
    parser.add_argument("--max-evidence-files", type=int, default=DEFAULT_MAX_EVIDENCE_FILES)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Watch live prediction evidence storage.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser("audit", help="Run one bounded evidence audit.")
    _add_common_args(audit_parser)
    audit_parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    watch_parser = subparsers.add_parser("watch", help="Run the evidence audit continuously.")
    _add_common_args(watch_parser)
    watch_parser.add_argument("--interval-seconds", type=float, default=DEFAULT_INTERVAL_SECONDS)
    watch_parser.add_argument("--once", action="store_true", help="Run one iteration and exit.")

    args = parser.parse_args(argv)
    config = _config_from_args(args)
    if args.command == "audit":
        report = audit_evidence_storage(config)
        print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"[evidence-watcher] status={report['status']} active={report['active_prediction_count']} issues={len(report['issues'])}")
        return int(report["exit_code"])

    try:
        while True:
            report = audit_evidence_storage(config)
            print(
                f"[evidence-watcher] checked={report['checked_at']} status={report['status']} "
                f"active={report['active_prediction_count']} issues={len(report['issues'])}",
                flush=True,
            )
            if args.once:
                return int(report["exit_code"])
            time.sleep(max(1.0, args.interval_seconds))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
