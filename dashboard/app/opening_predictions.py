"""Strict loader and scorer for pre-match opening artifacts.

This module is intentionally independent of the live predictor. A missing,
stale, ambiguous, or low-coverage artifact yields ``not_ready``; it never
falls back to a live model or a generic 50% number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class OpeningDecision:
    status: str
    reason: str | None = None
    first_team: str | None = None
    second_team: str | None = None
    first_team_probability_pct: int | None = None
    first_team_prior_matches: int | None = None
    second_team_prior_matches: int | None = None
    generated_at: str | None = None
    model_label: str | None = None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _scheduled_date(value: Any) -> date | None:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if timestamp >= 100_000_000_000:
        timestamp /= 1000
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
    except (OSError, OverflowError, ValueError):
        return None


def _team_key(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip()).casefold()
    # CREX's full women's labels map to Cricsheet's canonical country names.
    # Do not remove arbitrary tokens: unresolved labels must stay not-ready.
    text = re.sub(r"(?:\s+women|\s+woman)$", "", text).strip()
    return text


def _candidate_teams(candidate: dict[str, Any]) -> tuple[str, str] | None:
    first = str(candidate.get("team1_name") or candidate.get("team1Name") or "").strip()
    second = str(candidate.get("team2_name") or candidate.get("team2Name") or "").strip()
    if first and second:
        return first, second
    label = str(candidate.get("label") or "")
    match = re.match(r"^\s*(.+?)\s+vs\s+(.+?)(?:,|\s+\d+(?:st|nd|rd|th)\s+t20|$)", label, flags=re.I)
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip()


class OpeningArtifactStore:
    """Read a generated opening artifact and reject unsafe candidate inputs."""

    def __init__(
        self,
        artifact_path: str | Path,
        *,
        ttl_seconds: int = 86_400,
        max_as_of_age_days: int = 14,
    ):
        self.artifact_path = Path(artifact_path)
        self.ttl_seconds = ttl_seconds
        self.max_as_of_age_days = max_as_of_age_days
        self._cached_mtime_ns: int | None = None
        self._cached_artifact: dict[str, Any] | None = None

    def evaluate(self, candidate: dict[str, Any], *, now: datetime | None = None) -> OpeningDecision:
        if not isinstance(candidate, dict) or bool(candidate.get("is_live")):
            return OpeningDecision("not_ready", "candidate_is_not_upcoming")
        match_url = str(candidate.get("url") or candidate.get("match_url") or "").strip()
        if not match_url:
            return OpeningDecision("not_ready", "missing_exact_match_url")
        match_format = str(candidate.get("match_format") or candidate.get("matchFormat") or "").casefold()
        if "t20" not in match_format or "t10" in match_format:
            return OpeningDecision("not_ready", "unsupported_format")
        fixture_date = _scheduled_date(candidate.get("scheduled_start_time") or candidate.get("scheduledStartTime"))
        if fixture_date is None:
            return OpeningDecision("not_ready", "missing_scheduled_start")
        teams = _candidate_teams(candidate)
        if teams is None:
            return OpeningDecision("not_ready", "missing_exact_teams")
        artifact = self._load()
        if artifact is None:
            return OpeningDecision("not_ready", "opening_artifact_unavailable")
        if artifact.get("schema_version") != 1 or artifact.get("estimator") != "elo" or artifact.get("format") != "T20":
            return OpeningDecision("not_ready", "opening_artifact_contract_invalid")
        generated_at = _parse_datetime(artifact.get("generated_at"))
        reference = now or datetime.now(timezone.utc)
        if generated_at is None or (reference - generated_at).total_seconds() > self.ttl_seconds:
            return OpeningDecision("not_ready", "opening_artifact_stale")
        try:
            as_of_date = date.fromisoformat(str(artifact.get("as_of_date") or ""))
        except ValueError:
            return OpeningDecision("not_ready", "opening_artifact_as_of_invalid")
        if fixture_date <= as_of_date:
            return OpeningDecision("not_ready", "fixture_not_after_artifact_as_of")
        if (fixture_date - as_of_date).days > self.max_as_of_age_days:
            return OpeningDecision("not_ready", "opening_history_too_old_for_fixture")

        teams_by_key = {
            _team_key(name): (name, values)
            for name, values in (artifact.get("teams") or {}).items()
            if _team_key(name) and isinstance(values, dict)
        }
        first_key, second_key = _team_key(teams[0]), _team_key(teams[1])
        if not first_key or not second_key or first_key == second_key:
            return OpeningDecision("not_ready", "teams_not_distinct")
        first_entry = teams_by_key.get(first_key)
        second_entry = teams_by_key.get(second_key)
        if first_entry is None or second_entry is None:
            return OpeningDecision("not_ready", "team_not_covered_by_artifact")
        first_name, first_stats = first_entry
        second_name, second_stats = second_entry
        try:
            first_rating = float(first_stats["rating"])
            second_rating = float(second_stats["rating"])
            first_matches = int(first_stats["matches"])
            second_matches = int(second_stats["matches"])
            rating_scale = float(artifact["rating_scale"])
            minimum_matches = int(artifact["minimum_prior_matches"])
        except (KeyError, TypeError, ValueError):
            return OpeningDecision("not_ready", "opening_artifact_team_state_invalid")
        if first_matches < minimum_matches or second_matches < minimum_matches:
            return OpeningDecision("not_ready", "team_history_below_minimum")
        probability = 1.0 / (1.0 + 10.0 ** ((second_rating - first_rating) / rating_scale))
        calibrator = artifact.get("calibrator") or {}
        try:
            intercept = float(calibrator["intercept"])
            slope = float(calibrator["slope"])
            probability = 1.0 / (1.0 + math.exp(-(intercept + slope * math.log(probability / (1.0 - probability)))))
        except (KeyError, TypeError, ValueError, OverflowError):
            return OpeningDecision("not_ready", "opening_artifact_calibration_invalid")
        return OpeningDecision(
            "ready",
            first_team=first_name,
            second_team=second_name,
            first_team_probability_pct=int(round(probability * 100)),
            first_team_prior_matches=first_matches,
            second_team_prior_matches=second_matches,
            generated_at=generated_at.isoformat(),
            model_label="T20 opening Elo v1",
        )

    def _load(self) -> dict[str, Any] | None:
        try:
            stat = self.artifact_path.stat()
        except OSError:
            return None
        if self._cached_mtime_ns == stat.st_mtime_ns and self._cached_artifact is not None:
            return self._cached_artifact
        try:
            loaded = json.loads(self.artifact_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(loaded, dict):
            return None
        self._cached_mtime_ns = stat.st_mtime_ns
        self._cached_artifact = loaded
        return loaded
