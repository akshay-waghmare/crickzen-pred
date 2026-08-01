"""Public acquisition payloads for CrickenZen.

This module is the safety boundary between internal live prediction state and
unauthenticated public pages/APIs. Public serializers are whitelist-only: they
construct a new payload and never pass through raw predictor state.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from app.config import get_project_root, get_settings
from app.opening_predictions import OpeningArtifactStore, OpeningDecision
from app.prediction_manager import PredictionManager, _state_has_result
from app.routers.live import _enrich_detail_state


PUBLIC_FORBIDDEN_KEYS = {
    "monte_carlo",
    "odm",
    "blend",
    "features",
    "pred_state",
    "scraped_data",
    "history",
    "chart_history",
    "commentary",
    "ball_history",
    "balls_data",
    "ml_prob",
    "mc_prob",
    "ml_weight",
    "mc_weight",
}


@dataclass
class PublicSwingPoint:
    over: str
    score: str
    win_probability_pct: int | None
    label: str


@dataclass
class PublicPredictionPoint:
    over: str
    score: str
    win_probability_pct: int | None
    expected_final_score: int | None
    projected_score: int | None
    innings: int | None


@dataclass
class PublicMatchSummary:
    slug: str
    title: str
    league: str
    status: str
    score: str | None = None
    overs: str | None = None
    batting_team: str | None = None
    bowling_team: str | None = None
    win_probability_pct: int | None = None
    probability_team: str | None = None
    projection_label: str | None = None
    insight: str = "Model probability will appear once live ball data is available."
    updated_at: str | None = None
    detail_url: str | None = None
    # Stable source identity for public consumers. Team labels in a live state
    # may be abbreviated, while the CREX route remains the canonical match key.
    match_url: str | None = None
    format_label: str | None = None
    model_mode: str | None = None
    model_source: str | None = None
    model_label: str | None = None
    expected_final_score: int | None = None
    projected_score: int | None = None
    innings: int | None = None
    current_run_rate: float | None = None
    required_run_rate: float | None = None
    venue_average_score: float | None = None
    resource_pct: float | None = None
    resource_win_probability_pct: int | None = None
    score_vs_par: float | None = None
    pressure_index: float | None = None
    last_swings: list[PublicSwingPoint] = field(default_factory=list)
    prediction_history: list[PublicPredictionPoint] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    explanation_pack: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublicMatchDetail(PublicMatchSummary):
    venue: str | None = None
    target: int | None = None
    dashboard_url: str = "/dashboard"


def model_source_label(state: dict[str, Any] | None) -> str | None:
    model_dir = str((state or {}).get("model_dir") or "").replace("\\", "/")
    if "hundred_all_v1" in model_dir:
        return "hundred_specific"
    if "t20_all_v2" in model_dir:
        return "combined_gender_aware_fallback"
    if "odi_all_v3_feature_pruned_candidate" in model_dir or "odi_all_v2" in model_dir:
        return "combined_gender_aware_fallback"
    if model_dir:
        return "league_specific"
    return None


def model_label(state: dict[str, Any] | None) -> str | None:
    model_dir = str((state or {}).get("model_dir") or "").replace("\\", "/")
    if "hundred_all_v1" in model_dir:
        return "The Hundred all-gender v1"
    if "t20_all_v2" in model_dir:
        return "T20 all-gender v2"
    if "odi_all_v3_feature_pruned_candidate" in model_dir:
        return "ODI all-gender v3 feature-pruned"
    if "odi_all_v2" in model_dir:
        return "ODI all-gender v2"
    return model_dir.rsplit("/", 1)[-1] if model_dir else None


def model_mode_label(state: dict[str, Any] | None) -> str:
    model_dir = str((state or {}).get("model_dir") or "").replace("\\", "/")
    if "hundred_all_v1" in model_dir:
        return "ML"
    if "t20_all_v2" in model_dir or "odi_all_v2" in model_dir or "odi_all_v3_feature_pruned_candidate" in model_dir:
        return "ML + calibrated"
    return "MC-only" if (state or {}).get("mc_only") else "ML + calibrated"


def state_feature(state: dict[str, Any] | None, key: str) -> float | None:
    state = state or {}
    features = state.get("features") or {}
    return as_float(features.get(key) if features.get(key) is not None else state.get(key))


def metric_float(state: dict[str, Any] | None, key: str, digits: int = 2) -> float | None:
    value = state_feature(state, key)
    return round(value, digits) if value is not None else None


def public_reasons(state: dict[str, Any] | None) -> list[str]:
    """Return short, number-backed reasons without exposing raw features."""
    expected = expected_final_score(state)
    venue = metric_float(state, "venue_avg_score", 1)
    score_vs_par = metric_float(state, "score_vs_par", 1)
    required = metric_float(state, "required_run_rate", 1)
    current = metric_float(state, "current_run_rate", 1)
    pressure = metric_float(state, "pressure_index", 1)
    reasons: list[str] = []
    if expected is not None and venue is not None:
        delta = round(expected - venue, 1)
        direction = "above" if delta >= 0 else "below"
        reasons.append(f"Expected final {expected:g}, {abs(delta):g} {direction} the venue average.")
    if score_vs_par is not None:
        direction = "above" if score_vs_par >= 0 else "below"
        reasons.append(f"Current score is {abs(score_vs_par):g} runs {direction} resource-adjusted par.")
    if required is not None and required > 0:
        reasons.append(f"Chase pressure is {required:g} required runs per over from here.")
    elif current is not None:
        reasons.append(f"Current scoring rate is {current:g} runs per over.")
    if pressure is not None and pressure > 0:
        reasons.append(f"Pressure index is {pressure:g} on the public model scale.")
    return reasons[:3]


def public_explanation_pack(state: dict[str, Any] | None, swings: list[PublicSwingPoint]) -> dict[str, Any]:
    """Expose the video-studio explanation shape without private player/model data."""
    expected = expected_final_score(state)
    venue = metric_float(state, "venue_avg_score", 1)
    pack: dict[str, Any] = {
        "venue_behaviour": None,
        "toss_impact": "Toss impact will appear when toss context is available.",
        "expected_score": expected,
        "expected_wickets": metric_float(state, "expected_wickets", 1),
        "turning_point": None,
        "probability_swing": None,
    }
    if expected is not None and venue is not None:
        pack["venue_behaviour"] = "Tracking above the venue baseline." if expected >= venue else "Tracking below the venue baseline."
    if swings:
        largest = max(swings, key=lambda point: abs(point.win_probability_pct or 0))
        pack["turning_point"] = {"over": largest.over, "score": largest.score, "label": largest.label}
        if len(swings) >= 2:
            before = swings[-2].win_probability_pct
            after = swings[-1].win_probability_pct
            pack["probability_swing"] = {"before": before, "after": after, "delta": (after - before) if before is not None and after is not None else None}
    return pack


def public_payload(obj: PublicMatchSummary | PublicMatchDetail) -> dict[str, Any]:
    """Convert a public dataclass payload into JSON-safe dictionaries."""
    return asdict(obj)


def slugify(value: str) -> str:
    """Return a stable lowercase ASCII-ish slug."""
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "cricket-match"


def normalize_match_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", "")).lower()


def title_from_url(url: str) -> str:
    match = re.search(r"/cricket-live-score/([^/]+?)-match-updates", url or "", flags=re.I)
    if not match:
        match = re.search(r"/scoreboard/([^/?#]+)", url or "", flags=re.I)
    if not match:
        return "Cricket match"
    bits = match.group(1).split("-")
    if "vs" in bits:
        idx = bits.index("vs")
        if idx > 0 and idx + 1 < len(bits):
            return f"{bits[idx - 1].upper()} vs {bits[idx + 1].upper()}"
    return " ".join(bits[:6]).title()


def match_title(state: dict[str, Any] | None, match_url: str = "", label: str = "") -> str:
    state = state or {}
    batting = state.get("batting_team")
    bowling = state.get("bowling_team")
    if batting or bowling:
        return f"{batting or '?'} vs {bowling or '?'}"
    if label:
        parsed = title_from_label(label)
        if parsed:
            return parsed
    return title_from_url(match_url)


def title_from_label(label: str) -> str | None:
    """Derive a clean 'TEAM1 vs TEAM2' title from a CREX label.

    Handles the common CREX label format:
      'MI vs CSK on Jun 07, 2026 at 14:30 PM T20'
    where the trailing word after the date/time is the format (T20, ODI, etc.),
    not a second team.
    """
    clean = re.sub(r"\s+", " ", label or "").strip()
    if not clean:
        return None
    fixture = re.match(
        r"^(.+?)\s+on\s+[A-Za-z]{3}\s+\d{1,2},\s+\d{4}\s+at\s+[0-9:]+\s+[AP]M\s+([A-Za-z0-9]+)$",
        clean,
    )
    if fixture:
        team_part = fixture.group(1)
        format_part = fixture.group(2).upper()
        if " vs " in team_part.lower():
            return team_part
        if format_part in ("T20", "ODI", "TEST", "T10", "T20I"):
            return _clean_team_label(team_part)
        return f"{_clean_team_label(team_part)} vs {format_part}"
    fixture_no_fmt = re.match(
        r"^(.+?)\s+on\s+[A-Za-z]{3}\s+\d{1,2},\s+\d{4}\s+at\s+[0-9:]+\s+[AP]M$",
        clean,
    )
    if fixture_no_fmt:
        return _clean_team_label(fixture_no_fmt.group(1))
    live = re.match(r"^([A-Z][A-Z-]*)\s+[0-9]+[/-][0-9]+.*?\b([A-Z][A-Z-]*)\b", clean)
    if live:
        return f"{live.group(1)} vs {live.group(2)}"
    return clean[:72]


def _clean_team_label(value: str) -> str:
    clean = re.sub(r"\s+", " ", value or "").strip()
    clean = re.sub(
        r"\s+\d+(st|nd|rd|th)\s+(t20|odi|test|match)\b.*$",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    return clean.strip() or value.strip()


def slug_for_match(title: str, league: str = "", match_url: str = "") -> str:
    if title and title != "Cricket match":
        base = title
    else:
        base = title_from_url(match_url)
    suffix = f"{league} win probability" if league else "win probability"
    return slugify(f"{base} {suffix}")


def as_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def public_innings(state: dict[str, Any] | None) -> int | None:
    """Return the live innings number without requiring a legacy numeric field."""
    state = state or {}
    innings = as_int(
        state.get("innings")
        or state.get("current_innings")
        or state.get("innings_number")
        or (state.get("projection") or {}).get("innings")
    )
    if innings in (1, 2):
        return innings
    if state.get("is_second_innings"):
        return 2
    return 1 if state else None


def public_probability_pct(state: dict[str, Any] | None) -> int | None:
    state = state or {}
    candidates = [
        ((state.get("blend") or {}).get("blended_prob")),
        state.get("league_calibrated_prob"),
        state.get("bat_win_prob"),
    ]
    for raw in candidates:
        prob = as_float(raw)
        if prob is None:
            continue
        if 0.0 <= prob <= 1.0:
            return int(round(prob * 100))
    return None


def score_line(state: dict[str, Any] | None) -> str | None:
    state = state or {}
    score = state.get("score")
    wickets = state.get("wickets")
    if score in (None, "") or wickets in (None, ""):
        return None
    return f"{as_int(score, 0)}/{as_int(wickets, 0)}"


def overs_label(state: dict[str, Any] | None) -> str | None:
    state = state or {}
    overs = state.get("overs")
    if overs in (None, ""):
        overs = state.get("over")
    if overs in (None, ""):
        return None
    return str(overs)


def projection_label(state: dict[str, Any] | None) -> str | None:
    state = state or {}
    projection = state.get("projection") or {}
    target = as_int(projection.get("target") or state.get("target"))
    runs_required = as_int(projection.get("runs_required"))
    rrr = as_float(projection.get("required_run_rate"))
    if target and runs_required is not None:
        if rrr is not None:
            return f"{runs_required} needed, RRR {rrr:.2f}"
        return f"{runs_required} needed"
    projected = as_float(projection.get("projected_score") or projection.get("expected_final_score"))
    if projected is not None:
        return f"Projected {projected:.0f}"
    return None


def expected_final_score(state: dict[str, Any] | None) -> int | None:
    features = (state or {}).get("features") or {}
    value = as_float(features.get("expected_final_score") or (state or {}).get("expected_final_score"))
    return int(round(value)) if value is not None else None


def projected_score(state: dict[str, Any] | None) -> int | None:
    features = (state or {}).get("features") or {}
    value = as_float(features.get("projected_score") or (state or {}).get("projected_score"))
    return int(round(value)) if value is not None else None


def _history_probability_pct(point: dict[str, Any]) -> int | None:
    for key in ("bat_prob", "bat_win_prob", "league_calibrated_prob"):
        prob = as_float(point.get(key))
        if prob is not None and 0.0 <= prob <= 1.0:
            return int(round(prob * 100))
    return None


def public_swings(state: dict[str, Any] | None, *, limit: int = 5) -> list[PublicSwingPoint]:
    state = state or {}
    history = state.get("chart_history") or state.get("history") or []
    if not isinstance(history, list):
        return []

    points: list[PublicSwingPoint] = []
    previous_pct: int | None = None
    for point in history:
        if not isinstance(point, dict):
            continue
        pct = _history_probability_pct(point)
        if pct is None:
            continue
        score = point.get("score")
        wickets = point.get("wickets")
        score_text = f"{as_int(score, 0)}/{as_int(wickets, 0)}" if score not in (None, "") else ""
        delta = pct - previous_pct if previous_pct is not None else 0
        label = f"{delta:+d}%" if previous_pct is not None else "start"
        points.append(
            PublicSwingPoint(
                over=str(point.get("overs") or point.get("over") or ""),
                score=score_text,
                win_probability_pct=pct,
                label=label,
            )
        )
        previous_pct = pct
    return points[-limit:]


def public_prediction_history(state: dict[str, Any] | None, *, limit: int = 24) -> list[PublicPredictionPoint]:
    """Expose a capped chart derivative, never the raw predictor history."""
    state = state or {}
    history = state.get("chart_history") or state.get("history") or []
    if not isinstance(history, list):
        return []

    points: list[PublicPredictionPoint] = []
    for point in history:
        if not isinstance(point, dict):
            continue
        expected = as_float(point.get("expected_final_score") or point.get("expected_score"))
        projected = as_float(point.get("projected_score"))
        probability_pct = _history_probability_pct(point)
        if probability_pct is None and expected is None and projected is None:
            continue
        score = point.get("score")
        wickets = point.get("wickets")
        score_text = f"{as_int(score, 0)}/{as_int(wickets, 0)}" if score not in (None, "") else ""
        points.append(PublicPredictionPoint(
            over=str(point.get("overs") or point.get("over") or ""),
            score=score_text,
            win_probability_pct=probability_pct,
            expected_final_score=int(round(expected)) if expected is not None else None,
            projected_score=int(round(projected)) if projected is not None else None,
            innings=as_int(
                point.get("innings")
                or point.get("current_innings")
                or point.get("innings_number")
                or (2 if point.get("is_second_innings") else None)
            ),
        ))
    return points[-limit:]


def build_public_insight(state: dict[str, Any] | None, swings: list[PublicSwingPoint]) -> str:
    state = state or {}
    title = match_title(state)
    batting_team = state.get("batting_team") or "Batting side"
    bowling_team = state.get("bowling_team") or "Bowling side"

    if len(swings) >= 2:
        current = swings[-1].win_probability_pct
        previous = swings[0].win_probability_pct
        if current is not None and previous is not None:
            delta = current - previous
            if abs(delta) >= 5:
                gaining = batting_team if delta > 0 else bowling_team
                return f"{gaining} win probability {'up' if delta > 0 else 'down'} {abs(delta)}% across the recent overs."

    projection = state.get("projection") or {}
    target = as_int(projection.get("target") or state.get("target"))
    rrr = as_float(projection.get("required_run_rate") or state.get("required_run_rate"))
    crr = as_float(projection.get("current_run_rate") or state.get("current_run_rate"))
    if target and rrr is not None:
        if crr is not None and rrr > crr + 1:
            return "Chasing side under pressure: required rate is above current scoring pace."
        if rrr >= 10:
            return "Chase pressure is high with the required rate in double digits."
        return "Chasing side is still within the model's scoring range."

    score_vs_par = as_float(projection.get("score_vs_par"))
    if score_vs_par is not None and abs(score_vs_par) >= 3:
        direction = "above" if score_vs_par > 0 else "below"
        return f"{batting_team} are tracking {abs(score_vs_par):.0f} runs {direction} par."

    projected = as_float(projection.get("projected_score"))
    venue_avg = as_float(projection.get("venue_avg_score"))
    if projected is not None and venue_avg is not None and abs(projected - venue_avg) >= 5:
        direction = "above" if projected > venue_avg else "below"
        return f"{batting_team} projection is {abs(projected - venue_avg):.0f} runs {direction} the venue average."

    pct = public_probability_pct(state)
    if pct is not None:
        favoured = batting_team if pct >= 50 else bowling_team
        edge = "narrow edge" if 45 <= pct <= 55 else "clear edge"
        return f"Model currently gives {favoured} a {edge} in {title}."

    return "Model probability will appear once live ball data is available."


def is_ipl_candidate(candidate: dict[str, Any]) -> bool:
    league = str(candidate.get("league") or candidate.get("league_key") or "").upper()
    url = str(candidate.get("url") or "").lower()
    source = str(candidate.get("source") or "").lower()
    label = str(candidate.get("label") or "").lower()
    if league != "IPL":
        return False
    text = f"{url} {source} {label}"
    return "indian-premier-league" in text or "ipl" in text


def _candidate_summary(candidate: dict[str, Any]) -> PublicMatchSummary:
    league = str(candidate.get("league") or candidate.get("league_key") or "Cricket")
    url = str(candidate.get("url") or "")
    label = str(candidate.get("label") or "")
    title = match_title(None, url, label)
    slug = slug_for_match(title, league, url)
    status = "live" if candidate.get("is_live") else "upcoming"
    summary = PublicMatchSummary(
        slug=slug,
        title=title,
        league=league,
        status=status,
        score=None,
        overs=None,
        win_probability_pct=None,
        projection_label="Fixture" if status == "upcoming" else "Awaiting model",
        insight="Model probability will appear once live ball data is available.",
        updated_at=None,
        detail_url=f"/match/{slug}",
        match_url=url or None,
    )
    return summary


def _opening_candidate_summary(candidate: dict[str, Any], decision: OpeningDecision) -> PublicMatchSummary:
    """Serialize a ready opening decision without imitating a live state."""
    first_display = str(candidate.get("team1_name") or candidate.get("team1Name") or decision.first_team or "Team 1")
    second_display = str(candidate.get("team2_name") or candidate.get("team2Name") or decision.second_team or "Team 2")
    title = f"{first_display} vs {second_display}"
    url = str(candidate.get("url") or "")
    league = str(candidate.get("match_format") or candidate.get("matchFormat") or "T20")
    probability = decision.first_team_probability_pct
    return PublicMatchSummary(
        slug=slug_for_match(title, league, url),
        title=title,
        league=league,
        status="upcoming",
        win_probability_pct=probability,
        probability_team=first_display,
        projection_label="Opening model",
        insight=(
            f"Pre-match opening model gives {first_display} a {probability}% win probability "
            f"from pre-start team-strength history."
        ),
        updated_at=decision.generated_at,
        detail_url=f"/match/{slug_for_match(title, league, url)}",
        match_url=url or None,
        format_label="T20",
        model_mode="Pre-match calibrated Elo",
        model_source="opening_team_strength",
        model_label=decision.model_label,
        reasons=[
            f"{decision.first_team} has {decision.first_team_prior_matches} prior T20 fixtures in the model history.",
            f"{decision.second_team} has {decision.second_team_prior_matches} prior T20 fixtures in the model history.",
        ],
    )


def serialize_prediction(
    *,
    prediction_id: str,
    match_url: str,
    league: str,
    status: str,
    state: dict[str, Any] | None,
    detail: bool = False,
) -> PublicMatchSummary | PublicMatchDetail:
    title = match_title(state, match_url)
    slug = slug_for_match(title, league, match_url)
    swings = public_swings(state)
    # Keep list responses compact, but let the selected-match detail endpoint
    # expose the persisted full-match derivative used by the dashboard chart.
    # Two complete innings are at most 600 legal-ball states in ODI cricket.
    # Keep list payloads small, but do not silently remove the first innings
    # from a selected match's history replay.
    prediction_history = public_prediction_history(state, limit=600 if detail else 24)
    summary_kwargs = {
        "slug": slug,
        "title": title,
        "league": league,
        "status": status,
        "score": score_line(state),
        "overs": overs_label(state),
        "batting_team": (state or {}).get("batting_team"),
        "bowling_team": (state or {}).get("bowling_team"),
        "win_probability_pct": public_probability_pct(state),
        "projection_label": projection_label(state),
        "insight": build_public_insight(state, swings),
        "updated_at": (state or {}).get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "detail_url": f"/match/{slug}",
        "match_url": match_url or None,
        "format_label": (state or {}).get("format"),
        "model_mode": model_mode_label(state),
        "model_source": model_source_label(state),
        "model_label": model_label(state),
        "expected_final_score": expected_final_score(state),
        "projected_score": projected_score(state),
        "innings": public_innings(state),
        "current_run_rate": metric_float(state, "current_run_rate"),
        "required_run_rate": metric_float(state, "required_run_rate"),
        "venue_average_score": metric_float(state, "venue_avg_score"),
        "resource_pct": metric_float(state, "resource_pct"),
        "resource_win_probability_pct": (int(round(state_feature(state, "resource_win_prob") * 100))
                                          if state_feature(state, "resource_win_prob") is not None else None),
        "score_vs_par": metric_float(state, "score_vs_par"),
        "pressure_index": metric_float(state, "pressure_index"),
        "last_swings": swings,
        "prediction_history": prediction_history,
        "reasons": public_reasons(state),
        "explanation_pack": public_explanation_pack(state, swings),
    }
    if not detail:
        return PublicMatchSummary(**summary_kwargs)
    projection = (state or {}).get("projection") or {}
    return PublicMatchDetail(
        **summary_kwargs,
        venue=(state or {}).get("venue"),
        target=as_int(projection.get("target") or (state or {}).get("target")),
        dashboard_url="/dashboard",
    )


class PublicMatchService:
    """Read-only service for public match summaries/details."""

    def __init__(
        self,
        manager: PredictionManager | None = None,
        scheduler: Any = None,
        opening_store: OpeningArtifactStore | None = None,
    ):
        self.manager = manager or PredictionManager.get_instance()
        self.scheduler = scheduler
        settings = get_settings()
        artifact_path = Path(get_project_root()) / getattr(
            settings,
            "OPENING_MODEL_ARTIFACT_PATH",
            "artifacts/opening-baseline/t20_all_elo64_runtime_v1.json",
        )
        self.opening_store = opening_store or OpeningArtifactStore(
            artifact_path,
            ttl_seconds=getattr(settings, "OPENING_MODEL_ARTIFACT_TTL_SECONDS", 86_400),
            max_as_of_age_days=getattr(settings, "OPENING_MODEL_MAX_AS_OF_AGE_DAYS", 14),
        )

    def list_matches(self) -> list[PublicMatchSummary]:
        rows: list[PublicMatchSummary] = []
        seen_urls: set[str] = set()
        for pred in self.manager.list_predictions():
            if pred.get("status") != "running":
                continue
            match_url = pred.get("match_url", "")
            seen_urls.add(normalize_match_url(match_url))
            prediction = self.manager.get_prediction(pred["id"])
            raw_state = prediction.read_state() if prediction else None
            state = _enrich_detail_state(raw_state, prediction.output_json_path) if prediction else None
            if not state:
                # Startup processes may be alive while CREX is still loading.
                # A no-state process is not actionable Match Intelligence and
                # must not become a blank public card.
                seen_urls.discard(normalize_match_url(match_url))
                continue
            if prediction and _is_publicly_stale_prediction(prediction, state):
                seen_urls.discard(normalize_match_url(match_url))
                continue
            rows.append(
                serialize_prediction(
                    prediction_id=pred["id"],
                    match_url=match_url,
                    league=pred.get("league") or pred.get("league_code") or "Cricket",
                    status=pred.get("status") or "running",
                    state=state,
                )
            )

        for candidate in self._scheduler_candidates():
            # A live candidate without a running predictor has no probability
            # yet.  Do not expose it as a blank Match Intelligence card; it is
            # either being started by the scheduler or is not model-supported.
            if candidate.get("is_live"):
                continue
            url = str(candidate.get("url") or "")
            if normalize_match_url(url) in seen_urls:
                continue
            rows.append(_candidate_summary(candidate))
            seen_urls.add(normalize_match_url(url))
        rows.extend(self._opening_rows(seen_urls))
        return _sort_public_rows(rows)

    def list_ipl_today(self) -> list[PublicMatchSummary]:
        rows: list[PublicMatchSummary] = []
        seen_urls: set[str] = set()
        for pred in self.manager.list_predictions():
            if str(pred.get("league") or "").upper() != "IPL":
                continue
            if pred.get("status") != "running":
                continue
            match_url = pred.get("match_url", "")
            seen_urls.add(normalize_match_url(match_url))
            prediction = self.manager.get_prediction(pred["id"])
            raw_state = prediction.read_state() if prediction else None
            state = _enrich_detail_state(raw_state, prediction.output_json_path) if prediction else None
            if not state:
                seen_urls.discard(normalize_match_url(match_url))
                continue
            if prediction and _is_publicly_stale_prediction(prediction, state):
                seen_urls.discard(normalize_match_url(match_url))
                continue
            rows.append(
                serialize_prediction(
                    prediction_id=pred["id"],
                    match_url=match_url,
                    league=pred.get("league") or "IPL",
                    status=pred.get("status") or "running",
                    state=state,
                )
            )

        for candidate in self._scheduler_candidates():
            if not is_ipl_candidate(candidate):
                continue
            if candidate.get("is_live"):
                continue
            url = str(candidate.get("url") or "")
            if normalize_match_url(url) in seen_urls:
                continue
            rows.append(_candidate_summary(candidate))
            seen_urls.add(normalize_match_url(url))
        rows.extend(
            row for row in self._opening_rows(seen_urls)
            if str(row.league).upper() == "IPL"
        )
        return _sort_public_rows(rows)

    def get_match(self, slug: str) -> PublicMatchDetail | None:
        target = slugify(slug)
        for pred in self.manager.list_predictions():
            prediction = self.manager.get_prediction(pred["id"])
            raw_state = prediction.read_state() if prediction else None
            state = _enrich_detail_state(raw_state, prediction.output_json_path) if prediction else None
            if prediction and _is_publicly_stale_prediction(prediction, state):
                continue
            detail = serialize_prediction(
                prediction_id=pred["id"],
                match_url=pred.get("match_url", ""),
                league=pred.get("league") or pred.get("league_code") or "Cricket",
                status=pred.get("status") or "running",
                state=state,
                detail=True,
            )
            if detail.slug == target:
                return detail

        # Finished predictors leave the in-memory manager by design, but their
        # public-safe state and full history sidecars remain on disk. Direct
        # Match Intelligence routes must keep resolving those completed match
        # replays without adding them back into the live match list.
        for detail in self._completed_archive_details():
            if detail.slug == target:
                return detail

        for candidate in self._scheduler_candidates():
            summary = _candidate_summary(candidate)
            if summary.slug == target:
                return PublicMatchDetail(
                    **asdict(summary),
                    venue=None,
                    target=None,
                    last_swings=[],
                    dashboard_url="/dashboard",
                )
        for summary in self._opening_rows(set()):
            if summary.slug == target:
                return PublicMatchDetail(
                    **asdict(summary),
                    venue=None,
                    target=None,
                    dashboard_url="/dashboard",
                )
        return None

    def get_match_by_source_url(self, match_url: str) -> PublicMatchDetail | None:
        target = normalize_match_url(match_url)
        if not target:
            return None
        for pred in self.manager.list_predictions():
            if normalize_match_url(pred.get("match_url", "")) != target:
                continue
            prediction = self.manager.get_prediction(pred["id"])
            state = _enrich_detail_state(prediction.read_state(), prediction.output_json_path) if prediction else None
            if state:
                return serialize_prediction(prediction_id=pred["id"], match_url=pred.get("match_url", ""), league=pred.get("league") or pred.get("league_code") or "Cricket", status=pred.get("status") or "running", state=state, detail=True)
        for summary in self._opening_rows(set()):
            if normalize_match_url(summary.match_url or "") == target:
                return PublicMatchDetail(
                    **asdict(summary),
                    venue=None,
                    target=None,
                    dashboard_url="/dashboard",
                )
        return self._completed_archive_detail_by_source_url(target)

    def _completed_archive_detail_by_source_url(self, target: str) -> PublicMatchDetail | None:
        """Resolve one retained completed match without hydrating the full archive."""
        state_dir = Path(get_project_root()) / get_settings().STATE_DIR
        if not state_dir.exists():
            return None
        for live_path in sorted(state_dir.glob("*_livematch.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:240]:
            raw_state = self._read_completed_archive_state(live_path)
            if raw_state is None:
                continue
            source_url = str(raw_state.get("match_url") or (raw_state.get("state") or {}).get("match_url") or "")
            if normalize_match_url(source_url) != target:
                continue
            return self._serialize_completed_archive_state(live_path, raw_state)
        return None

    def _completed_archive_details(self) -> list[PublicMatchDetail]:
        state_dir = Path(get_project_root()) / get_settings().STATE_DIR
        if not state_dir.exists():
            return []
        details: list[PublicMatchDetail] = []
        for live_path in sorted(state_dir.glob("*_livematch.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:240]:
            raw_state = self._read_completed_archive_state(live_path)
            if raw_state is None:
                continue
            detail = self._serialize_completed_archive_state(live_path, raw_state)
            if detail is not None:
                details.append(detail)
        return details

    @staticmethod
    def _read_completed_archive_state(live_path: Path) -> dict[str, Any] | None:
        try:
            raw_state = json.loads(live_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return raw_state if isinstance(raw_state, dict) else None

    @staticmethod
    def _serialize_completed_archive_state(live_path: Path, raw_state: dict[str, Any]) -> PublicMatchDetail | None:
        prediction_id = live_path.name.replace("_livematch.json", "")
        output_path = str(live_path.parent / (prediction_id + ".json"))
        # Predictor sidecars retain the terminal match snapshot under a nested
        # ``state`` key. Rehydrate that wrapper before checking completion.
        state = _enrich_detail_state(dict(raw_state), output_path)
        if not state or not _state_has_result(state):
            return None
        match_url = str(state.get("match_url") or "")
        if not match_url:
            return None
        return serialize_prediction(
            prediction_id=prediction_id,
            match_url=match_url,
            league=str(state.get("league") or state.get("format") or "Cricket"),
            status="completed",
            state=state,
            detail=True,
        )

    def _scheduler_candidates(self) -> list[dict[str, Any]]:
        if self.scheduler is None:
            return []
        try:
            status = self.scheduler.status()
        except Exception:
            return []
        candidates = status.get("last_candidates") or []
        return [c for c in candidates if isinstance(c, dict)]

    def _opening_rows(self, seen_urls: set[str]) -> list[PublicMatchSummary]:
        rows: list[PublicMatchSummary] = []
        for candidate in self._scheduler_prematch_candidates():
            url = str(candidate.get("url") or "")
            normalized_url = normalize_match_url(url)
            if not normalized_url or normalized_url in seen_urls:
                continue
            decision = self.opening_store.evaluate(candidate)
            if decision.status != "ready":
                continue
            rows.append(_opening_candidate_summary(candidate, decision))
            seen_urls.add(normalized_url)
        return rows

    def _scheduler_prematch_candidates(self) -> list[dict[str, Any]]:
        if self.scheduler is None:
            return []
        try:
            status = self.scheduler.status()
        except Exception:
            return []
        candidates = status.get("last_prematch_candidates") or []
        return [candidate for candidate in candidates if isinstance(candidate, dict)]


def service_from_request(request: Any) -> PublicMatchService:
    return PublicMatchService(scheduler=getattr(request.app.state, "auto_scheduler", None))


def _sort_public_rows(rows: list[PublicMatchSummary]) -> list[PublicMatchSummary]:
    """Prefer live rows first, then the most recently updated payloads."""
    def sort_key(row: PublicMatchSummary) -> tuple[int, str]:
        is_live = 1 if row.status == "running" else 0
        updated_at = row.updated_at or ""
        return (is_live, updated_at)

    return sorted(rows, key=sort_key, reverse=True)


def _is_publicly_stale_prediction(prediction: Any, state: dict[str, Any] | None) -> bool:
    latest_activity = None
    if prediction is not None and hasattr(prediction, "latest_state_at"):
        latest_activity = prediction.latest_state_at()
    if latest_activity is None and state:
        latest_activity = _parse_timestamp(state.get("timestamp"))
    if latest_activity is None:
        return False
    age_seconds = (datetime.now(timezone.utc) - latest_activity).total_seconds()
    return age_seconds > max(30, get_settings().PUBLIC_MATCH_STALE_SECONDS)


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
