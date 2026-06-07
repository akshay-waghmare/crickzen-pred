"""Public acquisition payloads for CrickenZen.

This module is the safety boundary between internal live prediction state and
unauthenticated public pages/APIs. Public serializers are whitelist-only: they
construct a new payload and never pass through raw predictor state.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse, urlunparse

from app.config import get_settings
from app.prediction_manager import PredictionManager
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
    projection_label: str | None = None
    insight: str = "Model probability will appear once live ball data is available."
    updated_at: str | None = None
    detail_url: str | None = None


@dataclass
class PublicMatchDetail(PublicMatchSummary):
    venue: str | None = None
    target: int | None = None
    last_swings: list[PublicSwingPoint] = field(default_factory=list)
    dashboard_url: str = "/dashboard"


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
    )
    return summary


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
    }
    if not detail:
        return PublicMatchSummary(**summary_kwargs)
    projection = (state or {}).get("projection") or {}
    return PublicMatchDetail(
        **summary_kwargs,
        venue=(state or {}).get("venue"),
        target=as_int(projection.get("target") or (state or {}).get("target")),
        last_swings=swings,
        dashboard_url="/dashboard",
    )


class PublicMatchService:
    """Read-only service for public match summaries/details."""

    def __init__(self, manager: PredictionManager | None = None, scheduler: Any = None):
        self.manager = manager or PredictionManager.get_instance()
        self.scheduler = scheduler

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
            url = str(candidate.get("url") or "")
            if normalize_match_url(url) in seen_urls:
                continue
            rows.append(_candidate_summary(candidate))
            seen_urls.add(normalize_match_url(url))
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
            url = str(candidate.get("url") or "")
            if normalize_match_url(url) in seen_urls:
                continue
            rows.append(_candidate_summary(candidate))
            seen_urls.add(normalize_match_url(url))
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
        return None

    def _scheduler_candidates(self) -> list[dict[str, Any]]:
        if self.scheduler is None:
            return []
        try:
            status = self.scheduler.status()
        except Exception:
            return []
        candidates = status.get("last_candidates") or []
        return [c for c in candidates if isinstance(c, dict)]


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
