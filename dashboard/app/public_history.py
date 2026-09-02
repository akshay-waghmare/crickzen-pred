"""Immutable public prediction history and match-level proof metrics.

The live public feed is intentionally short-lived.  This module creates the
separate durable record needed after a match finishes:

* one immutable JSON record per canonical match URL;
* the first usable public forecast observed for that match;
* a winner recovered from the terminal score state; and
* Brier, log-loss, accuracy, and ten-bin calibration metrics over completed
  records only.

The record is deliberately match-level.  Repeated ball states from one match
must not be presented as hundreds of independent matches when we explain
trustworthiness to the public.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

from app.config import get_project_root, get_settings


HISTORY_SCHEMA_VERSION = 1
HISTORY_FILE_PREFIX = "history-"
CALIBRATION_BIN_COUNT = 10
MIN_READY_SAMPLE_COUNT = 30


HISTORY_DEFINITIONS = {
    "scope": (
        "Completed matches only. One row per match, using the first usable "
        "public forecast observed for that match."
    ),
    "brier": "Average squared probability error. 0 is perfect; lower is better.",
    "ece": (
        "Expected Calibration Error: the weighted gap between forecast confidence "
        "and observed win rate in ten probability buckets. Lower is better."
    ),
    "log_loss": "Supporting metric that penalises confident wrong forecasts. Lower is better.",
    "accuracy": "The share of first public calls whose selected team won. Higher is better.",
    "small_sample": (
        f"Results remain marked collecting until at least {MIN_READY_SAMPLE_COUNT} "
        "eligible completed matches are available."
    ),
}


def _history_directory() -> Path:
    settings = get_settings()
    configured = getattr(settings, "PUBLIC_HISTORY_DIR", "data/public_history")
    return Path(get_project_root()) / str(configured)


def normalize_source_url(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", "")).lower()


def archive_id_for_source_url(match_url: str, prediction_id: str = "") -> str:
    """Return a stable ID, independent of a temporary predictor process ID."""
    source = normalize_source_url(match_url)
    if not source:
        source = str(prediction_id or "unknown").strip().lower()
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]
    return f"{HISTORY_FILE_PREFIX}{digest}"


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _probability(value: Any) -> float | None:
    number = _as_float(value)
    if number is None:
        return None
    if 1.0 < number <= 100.0:
        number /= 100.0
    return number if 0.0 <= number <= 1.0 else None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return int(number) if number is not None else None


def _state_view(raw_state: dict[str, Any]) -> dict[str, Any]:
    """Flatten the sidecar wrapper without losing its top-level identity."""
    nested = raw_state.get("state")
    if isinstance(nested, dict):
        merged = dict(raw_state)
        merged.update(nested)
        return merged
    return dict(raw_state)


def _candidate_values(raw_state: dict[str, Any], key: str) -> Iterable[Any]:
    state = raw_state.get("state") if isinstance(raw_state.get("state"), dict) else {}
    for container in (raw_state, state, raw_state.get("pred_state") or {}):
        if isinstance(container, dict) and key in container:
            yield container.get(key)


def _first_nonempty(raw_state: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        for value in _candidate_values(raw_state, key):
            text = str(value or "").strip()
            if text:
                return text
    return None


def _history_points(raw_state: dict[str, Any]) -> list[dict[str, Any]]:
    points = raw_state.get("history")
    if isinstance(points, list):
        return [point for point in points if isinstance(point, dict)]
    nested = raw_state.get("state")
    if isinstance(nested, dict) and isinstance(nested.get("history"), list):
        return [point for point in nested["history"] if isinstance(point, dict)]
    return []


def _point_probability(point: dict[str, Any]) -> float | None:
    for key in ("bat_prob", "bat_win_prob", "league_calibrated_prob", "win_probability"):
        probability = _probability(point.get(key))
        if probability is not None:
            return probability
    return None


def _point_timestamp(point: dict[str, Any], fallback: str) -> str:
    value = point.get("timestamp") or point.get("updated_at") or fallback
    return str(value or "")


def _is_terminal_point(point: dict[str, Any], terminal_state: dict[str, Any]) -> bool:
    """Reject a probability emitted after the result was already knowable."""
    clamp = point.get("terminal_clamp")
    if isinstance(clamp, dict) and clamp.get("applied"):
        return True
    target = _as_int(point.get("target") or point.get("target_runs") or terminal_state.get("target"))
    score = _as_int(point.get("score") or point.get("current_score"))
    wickets = _as_int(point.get("wickets") or point.get("wickets_lost"))
    overs = _as_float(point.get("overs") or point.get("over"))
    total_overs = _as_float(point.get("total_overs") or terminal_state.get("total_overs"))
    if target is not None and score is not None and score >= target:
        return True
    if wickets is not None and wickets >= 10:
        return True
    if total_overs is not None and overs is not None and overs >= total_overs:
        return True
    return False


def _match_label(raw_state: dict[str, Any]) -> str:
    state = _state_view(raw_state)
    batting = str(state.get("batting_team") or "").strip()
    bowling = str(state.get("bowling_team") or "").strip()
    if batting and bowling:
        return f"{batting} vs {bowling}"
    return "Cricket match"


def _winner_from_terminal_state(raw_state: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (winner, evidence) without guessing ties or abandoned games."""
    explicit_keys = (
        "winner",
        "final_winner",
        "match_winner",
        "winner_team",
    )
    for key in explicit_keys:
        value = _first_nonempty(raw_state, (key,))
        if value:
            return value, "provider_winner_field"

    state = _state_view(raw_state)
    batting = str(state.get("batting_team") or "").strip()
    bowling = str(state.get("bowling_team") or "").strip()
    target = _as_int(state.get("target") or state.get("target_runs"))
    score = _as_int(state.get("score") or state.get("current_score"))
    wickets = _as_int(state.get("wickets") or state.get("wickets_lost"))
    overs = _as_float(state.get("overs") or state.get("over"))
    total_overs = _as_float(state.get("total_overs"))
    is_second_innings = bool(state.get("is_second_innings") or state.get("innings") == 2)

    if not batting or not bowling or not is_second_innings or target is None or score is None:
        return None, None
    if score >= target:
        return batting, "terminal_score_reached_target"
    if wickets is not None and wickets >= 10:
        return bowling, "terminal_all_out"
    if total_overs is not None and overs is not None and overs >= total_overs:
        return bowling, "terminal_overs_exhausted"
    return None, None


def _first_forecast(raw_state: dict[str, Any]) -> dict[str, Any] | None:
    fallback_timestamp = str(raw_state.get("timestamp") or "")
    state = _state_view(raw_state)
    fallback_batting = str(state.get("batting_team") or "").strip()
    fallback_bowling = str(state.get("bowling_team") or "").strip()

    candidates = _history_points(raw_state) + [state]
    for point in candidates:
        if _is_terminal_point(point, state):
            continue
        probability = _point_probability(point)
        batting = str(point.get("batting_team") or fallback_batting).strip()
        bowling = str(point.get("bowling_team") or fallback_bowling).strip()
        if probability is None or not batting or not bowling:
            continue
        predicted_side = batting if probability >= 0.5 else bowling
        confidence = probability if predicted_side == batting else 1.0 - probability
        return {
            "timestamp": _point_timestamp(point, fallback_timestamp),
            "batting_team": batting,
            "bowling_team": bowling,
            "batting_probability": round(probability, 6),
            "predicted_side": predicted_side,
            "predicted_probability": round(confidence, 6),
            "predicted_probability_pct": round(confidence * 100.0, 2),
            "observation": "first_usable_public_forecast",
            "model_label": str(raw_state.get("model_label") or "").strip() or None,
        }
    return None


def _public_slug_aliases(match_url: str, match_label: str, league: str) -> list[str]:
    """Create stable lookup aliases for older creator-card links."""
    def slugify(value: str) -> str:
        text = re.sub(r"[^a-z0-9]+", "-", value.lower())
        return re.sub(r"-+", "-", text).strip("-")

    aliases = [slugify(f"{match_label} {league} win probability")]
    path_match = re.search(r"/(?:cricket-live-score|cric-live)/([^/?#]+)", match_url or "", re.I)
    if path_match:
        fixture = path_match.group(1).split("-match-updates", 1)[0]
        parts = fixture.split("-vs-", 1)
        if len(parts) == 2:
            left = parts[0].split("-")[0]
            right = parts[1].split("-")[0]
            for first, second in ((left, right), (right, left)):
                aliases.append(slugify(f"{first}-vs-{second}-t20-win-probability"))
    return list(dict.fromkeys(alias for alias in aliases if alias))


def build_archive_record(
    *,
    raw_state: dict[str, Any],
    match_url: str,
    league: str,
    prediction_id: str = "",
    archived_at: str | None = None,
) -> dict[str, Any] | None:
    """Build a completed record, or None when the outcome is not provable."""
    if not isinstance(raw_state, dict):
        return None
    source_url = normalize_source_url(match_url or str(raw_state.get("match_url") or ""))
    winner, evidence = _winner_from_terminal_state(raw_state)
    forecast = _first_forecast(raw_state)
    if not source_url or not winner or not forecast:
        return None

    match_label = _match_label(raw_state)
    record = {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "archive_id": archive_id_for_source_url(source_url, prediction_id),
        "status": "completed",
        "archived_at": archived_at or datetime.now(timezone.utc).isoformat(),
        "league": str(league or "Cricket"),
        "match_label": match_label,
        "match_url": source_url,
        "public_slug_aliases": _public_slug_aliases(source_url, match_label, str(league or "Cricket")),
        "prediction": forecast,
        "outcome": {
            "winner": winner,
            "evidence": evidence,
            "verified_at": str(raw_state.get("timestamp") or archived_at or ""),
        },
        "integrity": {
            "source": "terminal_prediction_state",
            "source_sha256": hashlib.sha256(
                json.dumps(raw_state, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest(),
        },
    }
    return record


def write_completed_prediction_archive(
    *,
    raw_state: dict[str, Any],
    match_url: str,
    league: str,
    prediction_id: str = "",
) -> dict[str, Any] | None:
    """Write once. Existing records are never replaced by a later run."""
    record = build_archive_record(
        raw_state=raw_state,
        match_url=match_url,
        league=league,
        prediction_id=prediction_id,
    )
    if record is None:
        return None

    directory = _history_directory()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record['archive_id']}.json"
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        return read_history_record(record["archive_id"])
    return record


def _read_record(path: Path) -> dict[str, Any] | None:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict) or record.get("schema_version") != HISTORY_SCHEMA_VERSION:
        return None
    if record.get("status") != "completed":
        return None
    return record


def read_history_records(league: str | None = None) -> list[dict[str, Any]]:
    directory = _history_directory()
    if not directory.exists():
        return []
    wanted = str(league or "").lower()
    records: list[dict[str, Any]] = []
    for path in directory.glob(f"{HISTORY_FILE_PREFIX}*.json"):
        record = _read_record(path)
        if record is None:
            continue
        if wanted and str(record.get("league") or "").lower() != wanted:
            continue
        records.append(record)
    return sorted(records, key=lambda item: str(item.get("archived_at") or ""), reverse=True)


def read_history_record(archive_id: str) -> dict[str, Any] | None:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", str(archive_id or ""))
    if not clean:
        return None
    return _read_record(_history_directory() / f"{clean}.json")


def find_history_record_by_slug(slug: str, league: str | None = None) -> dict[str, Any] | None:
    target = str(slug or "").strip().lower()
    if not target:
        return None
    for record in read_history_records(league):
        aliases = record.get("public_slug_aliases") or []
        if target in {str(alias).lower() for alias in aliases}:
            return record
    return None


def find_history_record_by_source_url(match_url: str, league: str | None = None) -> dict[str, Any] | None:
    target = normalize_source_url(match_url)
    if not target:
        return None
    for record in read_history_records(league):
        if normalize_source_url(str(record.get("match_url") or "")) == target:
            return record
    return None


def public_history_record(record: dict[str, Any]) -> dict[str, Any]:
    """Whitelist the durable record before returning it from the public API."""
    return {
        "archive_id": record.get("archive_id"),
        "status": record.get("status"),
        "archived_at": record.get("archived_at"),
        "league": record.get("league"),
        "match_label": record.get("match_label"),
        "match_url": record.get("match_url"),
        "public_slug_aliases": record.get("public_slug_aliases") or [],
        "prediction": record.get("prediction") or {},
        "outcome": record.get("outcome") or {},
        "integrity": {
            "source": (record.get("integrity") or {}).get("source"),
            "source_sha256": (record.get("integrity") or {}).get("source_sha256"),
        },
    }


def _calibration_buckets(probabilities: list[float], outcomes: list[int]) -> tuple[float, list[dict[str, Any]]]:
    buckets: list[dict[str, Any]] = []
    ece = 0.0
    total = len(probabilities)
    for index in range(CALIBRATION_BIN_COUNT):
        lower = index / CALIBRATION_BIN_COUNT
        upper = (index + 1) / CALIBRATION_BIN_COUNT
        selected = [i for i, probability in enumerate(probabilities)
                    if (probability >= lower and probability < upper) or
                    (index == CALIBRATION_BIN_COUNT - 1 and probability == 1.0)]
        count = len(selected)
        bucket = {
            "lower": round(lower, 2),
            "upper": round(upper, 2),
            "forecast_mean": None,
            "observed_rate": None,
            "count": count,
        }
        if count:
            forecast_mean = sum(probabilities[i] for i in selected) / count
            observed_rate = sum(outcomes[i] for i in selected) / count
            bucket["forecast_mean"] = round(forecast_mean, 6)
            bucket["observed_rate"] = round(observed_rate, 6)
            ece += (count / total) * abs(forecast_mean - observed_rate)
        buckets.append(bucket)
    return round(ece, 6), buckets


def history_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    probabilities: list[float] = []
    outcomes: list[int] = []
    wins = 0
    losses = 0
    excluded = 0
    for record in records:
        prediction = record.get("prediction") or {}
        outcome = record.get("outcome") or {}
        probability = _probability(prediction.get("predicted_probability"))
        predicted_side = str(prediction.get("predicted_side") or "").strip()
        winner = str(outcome.get("winner") or "").strip()
        if probability is None or not predicted_side or not winner:
            excluded += 1
            continue
        actual = 1 if predicted_side.casefold() == winner.casefold() else 0
        probabilities.append(probability)
        outcomes.append(actual)
        wins += actual
        losses += 1 - actual

    sample_count = len(probabilities)
    ece, calibration = _calibration_buckets(probabilities, outcomes) if sample_count else (None, [])
    brier = (
        sum((probability - actual) ** 2 for probability, actual in zip(probabilities, outcomes)) / sample_count
        if sample_count else None
    )
    log_loss = (
        -sum(
            actual * math.log(max(min(probability, 1.0 - 1e-15), 1e-15))
            + (1 - actual) * math.log(max(min(1.0 - probability, 1.0 - 1e-15), 1e-15))
            for probability, actual in zip(probabilities, outcomes)
        ) / sample_count
        if sample_count else None
    )
    status = "not_ready" if sample_count == 0 else ("ready" if sample_count >= MIN_READY_SAMPLE_COUNT else "collecting")
    return {
        "status": status,
        "eligible_match_count": sample_count,
        "excluded_record_count": excluded,
        "accuracy_pct": round((wins / sample_count) * 100.0, 2) if sample_count else None,
        "wins": wins,
        "losses": losses,
        "brier": round(brier, 6) if brier is not None else None,
        "ece": ece,
        "log_loss": round(log_loss, 6) if log_loss is not None else None,
        "calibration": calibration,
        "definitions": HISTORY_DEFINITIONS,
    }


def history_summary(league: str | None = None) -> dict[str, Any]:
    records = read_history_records(league)
    metrics = history_metrics(records)
    return {
        "status": metrics["status"],
        "league": league or "all",
        "record_count": len(records),
        "eligible_match_count": metrics["eligible_match_count"],
        "metrics": {
            key: metrics[key]
            for key in ("accuracy_pct", "wins", "losses", "brier", "ece", "log_loss")
        },
        "calibration": metrics["calibration"],
        "excluded_record_count": metrics["excluded_record_count"],
        "definitions": metrics["definitions"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
