"""
Pre-match serializer and service boundary for CrickenZen.

Provides a safe pre-match data contract separate from live public payloads.
Includes fixture discovery, venue-prior lookup, toss-sensitivity heuristics,
pressure-zone generation, conditions-status framework, and deterministic
reason-block generation for the before-the-toss product surface.

V1 focuses on IPL with venue priors from src/bbl_pipeline/features/store.py.
All factors carry honest ready/partial/not-ready status; nothing is invented.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

DEFAULT_LEAGUE = "ipl"
REASON_COUNT_MIN = 3
REASON_COUNT_MAX = 5

# Venue priors from src/bbl_pipeline/features/store.py (IPL subset)
# Keys: canonical venue name -> {venue_avg_score, venue_avg_wickets, venue_bat_first_win_rate}
IPL_VENUE_PRIORS: dict[str, dict[str, float]] = {
    "Eden Gardens, Kolkata": {"venue_avg_score": 175.0, "venue_avg_wickets": 6.0, "venue_bat_first_win_rate": 0.52},
    "Wankhede Stadium, Mumbai": {"venue_avg_score": 178.0, "venue_avg_wickets": 6.0, "venue_bat_first_win_rate": 0.47},
    "MA Chidambaram Stadium, Chepauk, Chennai": {"venue_avg_score": 156.0, "venue_avg_wickets": 6.5, "venue_bat_first_win_rate": 0.57},
    "M Chinnaswamy Stadium, Bengaluru": {"venue_avg_score": 184.0, "venue_avg_wickets": 5.5, "venue_bat_first_win_rate": 0.44},
    "Arun Jaitley Stadium, Delhi": {"venue_avg_score": 166.0, "venue_avg_wickets": 6.2, "venue_bat_first_win_rate": 0.52},
    "Rajiv Gandhi International Stadium, Uppal, Hyderabad": {"venue_avg_score": 172.0, "venue_avg_wickets": 6.1, "venue_bat_first_win_rate": 0.54},
    "Narendra Modi Stadium, Ahmedabad": {"venue_avg_score": 175.0, "venue_avg_wickets": 6.0, "venue_bat_first_win_rate": 0.50},
    "Sawai Mansingh Stadium, Jaipur": {"venue_avg_score": 172.0, "venue_avg_wickets": 6.2, "venue_bat_first_win_rate": 0.52},
    "Punjab Cricket Association IS Bindra Stadium, Mohali": {"venue_avg_score": 168.0, "venue_avg_wickets": 6.3, "venue_bat_first_win_rate": 0.51},
    "Himachal Pradesh Cricket Association Stadium, Dharamsala": {"venue_avg_score": 168.0, "venue_avg_wickets": 6.0, "venue_bat_first_win_rate": 0.50},
    "Maharashtra Cricket Association Stadium, Pune": {"venue_avg_score": 176.0, "venue_avg_wickets": 6.1, "venue_bat_first_win_rate": 0.52},
    "Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow": {"venue_avg_score": 172.0, "venue_avg_wickets": 6.2, "venue_bat_first_win_rate": 0.53},
    "Dr DY Patil Sports Academy, Mumbai": {"venue_avg_score": 175.0, "venue_avg_wickets": 6.0, "venue_bat_first_win_rate": 0.50},
    "Brabourne Stadium, Mumbai": {"venue_avg_score": 172.0, "venue_avg_wickets": 6.1, "venue_bat_first_win_rate": 0.50},
    "Holkar Cricket Stadium, Indore": {"venue_avg_score": 180.0, "venue_avg_wickets": 5.8, "venue_bat_first_win_rate": 0.48},
    "Vidarbha Cricket Association Stadium, Jamtha, Nagpur": {"venue_avg_score": 162.0, "venue_avg_wickets": 6.4, "venue_bat_first_win_rate": 0.53},
    "Saurashtra Cricket Association Stadium, Rajkot": {"venue_avg_score": 175.0, "venue_avg_wickets": 6.0, "venue_bat_first_win_rate": 0.52},
}

# Generic cricket terms that should NOT match as venue aliases
_VENUE_GENERIC_WORDS: set[str] = {
    "cricket", "stadium", "stadiums", "sports", "academy", "ground",
    "association", "international", "national", "park", "arena", "oval",
    "field", "club", "college", "university", "school", "complex",
    "indoor", "outdoor", "centre", "center", "premier", "royal",
    "live", "score", "match", "series", "league",
}

# Short-name aliases for matching against CREX labels/URLs
_VENUE_ALIAS_MAP: dict[str, str] = {}
for _venue_name in IPL_VENUE_PRIORS:
    _VENUE_ALIAS_MAP[_venue_name.lower()] = _venue_name
    for _part in _venue_name.lower().replace(",", "").split():
        if len(_part) > 3 and _part not in _VENUE_GENERIC_WORDS:
            _VENUE_ALIAS_MAP.setdefault(_part, _venue_name)
# Common short forms
_VENUE_ALIAS_MAP["wankhede"] = "Wankhede Stadium, Mumbai"
_VENUE_ALIAS_MAP["chepauk"] = "MA Chidambaram Stadium, Chepauk, Chennai"
_VENUE_ALIAS_MAP["chinnaswamy"] = "M Chinnaswamy Stadium, Bengaluru"
_VENUE_ALIAS_MAP["chidambaram"] = "MA Chidambaram Stadium, Chepauk, Chennai"
_VENUE_ALIAS_MAP["uppal"] = "Rajiv Gandhi International Stadium, Uppal, Hyderabad"
_VENUE_ALIAS_MAP["motera"] = "Narendra Modi Stadium, Ahmedabad"
_VENUE_ALIAS_MAP["ekana"] = "Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow"
_VENUE_ALIAS_MAP["bindra"] = "Punjab Cricket Association IS Bindra Stadium, Mohali"
_VENUE_ALIAS_MAP["sawai"] = "Sawai Mansingh Stadium, Jaipur"

DEFAULT_VENUE_PRIOR = {"venue_avg_score": 160.0, "venue_avg_wickets": 6.0, "venue_bat_first_win_rate": 0.50}


def _slugify(value: str) -> str:
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "cricket-match"


def _title_from_url(url: str) -> str:
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


def _match_title(url: str = "", label: str = "") -> str:
    """Derive a clean 'TEAM1 vs TEAM2' title from a CREX candidate label or URL.

    Handles the common CREX label format:
      'MI vs CSK on Jun 07, 2026 at 14:30 PM T20'
    where the trailing word after the date/time is the format (T20, ODI, etc.),
    not a second team.
    """
    if label:
        clean = re.sub(r"\s+", " ", label or "").strip()
        if clean:
            # "TEAM1 vs TEAM2 on Mon DD, YYYY at HH:MM AM/PM FORMAT"
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

            # Fallback: "TEAM1 vs TEAM2 on Mon DD, YYYY at HH:MM AM/PM" (no trailing format)
            fixture_no_fmt = re.match(
                r"^(.+?)\s+on\s+[A-Za-z]{3}\s+\d{1,2},\s+\d{4}\s+at\s+[0-9:]+\s+[AP]M$",
                clean,
            )
            if fixture_no_fmt:
                return _clean_team_label(fixture_no_fmt.group(1))

            # Live score line: "CSK 180/3 (18.2) RR" or similar
            live = re.match(
                r"^([A-Z][A-Z-]*)\s+[0-9]+[/-][0-9]+.*?\b([A-Z][A-Z-]*)\b",
                clean,
            )
            if live:
                return f"{live.group(1)} vs {live.group(2)}"

            return clean[:72]
    return _title_from_url(url)


def _clean_team_label(value: str) -> str:
    clean = re.sub(r"\s+", " ", value or "").strip()
    clean = re.sub(r"\s+\d+(st|nd|rd|th)\s+(t20|odi|test|match)\b.*$", "", clean, flags=re.IGNORECASE)
    return clean.strip() or value.strip()


@dataclass
class ConditionsStatus:
    label: str
    status: str  # ready, partial, not_ready
    detail: str


@dataclass
class PressureZoneBand:
    label: str
    description: str
    range_text: str


@dataclass
class PrematchReason:
    title: str
    body: str


@dataclass
class PrematchBriefSummary:
    slug: str
    title: str
    league: str
    status: str
    start_time: str | None = None
    venue: str | None = None
    win_probability_pct: int | None = None
    projected_first_innings: str | None = None
    toss_sensitivity_label: str | None = None
    insight: str = "Pre-match model insight will appear once fixture details are available."
    detail_url: str | None = None


@dataclass
class PrematchBriefDetail(PrematchBriefSummary):
    venue_avg_score: int | None = None
    venue_bat_first_win_rate: float | None = None
    venue_label: str | None = None
    conditions: list[ConditionsStatus] = field(default_factory=list)
    pressure_zones: list[PressureZoneBand] = field(default_factory=list)
    reasons: list[PrematchReason] = field(default_factory=list)
    source_status: str = "partial"
    live_match_slug: str | None = None


def pre_match_slug(title: str, league: str = "", start_time: str = "") -> str:
    suffix = f"{league} pre match brief" if league else "pre match brief"
    if start_time:
        try:
            dt = pd.Timestamp(start_time)
            date_part = dt.strftime("%Y%m%d")
            suffix = f"{league} {date_part} pre match brief"
        except (ValueError, TypeError):
            pass
    return _slugify(f"{title} {suffix}")


def _lookup_venue_prior(venue_name: str | None) -> dict[str, float] | None:
    if not venue_name:
        return None
    if venue_name in IPL_VENUE_PRIORS:
        return IPL_VENUE_PRIORS[venue_name]
    clean = venue_name.strip().lower()
    for key, value in IPL_VENUE_PRIORS.items():
        if key.lower() == clean or clean.startswith(key.lower().split(",")[0]):
            return value
    return None


def _venue_bias_label(bat_first_wr: float | None) -> str:
    if bat_first_wr is None:
        return "Unknown venue bias"
    if bat_first_wr >= 0.55:
        return "Batting-first friendly"
    if bat_first_wr <= 0.45:
        return "Chase-friendly"
    return "Balanced venue"


def _toss_sensitivity_label(
    bat_first_wr: float | None,
    pre_match_edge_magnitude: int = 0,
) -> tuple[str, str]:
    if bat_first_wr is None:
        return ("Unknown", "Venue toss data is not available.")

    deviation = abs(bat_first_wr - 0.50)
    if deviation >= 0.07 or pre_match_edge_magnitude <= 5:
        label = "High leverage"
        reason = "Toss could significantly shift the match edge at this venue."
    elif deviation >= 0.04 or pre_match_edge_magnitude <= 10:
        label = "Medium leverage"
        reason = "Toss has a moderate effect on the expected match balance."
    else:
        label = "Low leverage"
        reason = "Toss is unlikely to meaningfully change the pre-match edge."

    return (label, reason)


def _generate_pressure_zones(venue_avg: float | None) -> list[PressureZoneBand]:
    if venue_avg is None:
        return []
    par = round(venue_avg)
    return [
        PressureZoneBand(
            label="Above par",
            description="Bowling side under pressure. The batting team is well placed.",
            range_text=f"{par + 5}+",
        ),
        PressureZoneBand(
            label="Par band",
            description="Around the expected first-innings range at this venue.",
            range_text=f"{par - 5} to {par + 4}",
        ),
        PressureZoneBand(
            label="Below par",
            description="Batting side at a disadvantage. Chase-favourable position.",
            range_text=f"below {par - 5}",
        ),
    ]


def _build_conditions() -> list[ConditionsStatus]:
    return [
        ConditionsStatus(
            label="Dew risk",
            status="not_ready",
            detail="Live dew-risk data is not yet available. This section will update when conditions feeds are integrated.",
        ),
        ConditionsStatus(
            label="Rain risk",
            status="not_ready",
            detail="Live rain-risk data is not yet available. This section will update when conditions feeds are integrated.",
        ),
    ]


def _generate_reasons(
    *,
    win_probability_pct: int | None = None,
    venue_label: str | None = None,
    venue_avg_score: int | None = None,
    toss_label: str | None = None,
    bat_first_wr: float | None = None,
) -> list[PrematchReason]:
    reasons: list[PrematchReason] = []

    if win_probability_pct is not None:
        if win_probability_pct >= 65:
            reasons.append(
                PrematchReason(
                    title="Clear model edge",
                    body=f"The pre-match model favours one side at approximately {win_probability_pct}% win probability, "
                         f"suggesting a meaningful gap in expected strength before toss.",
                )
            )
        elif win_probability_pct >= 55:
            reasons.append(
                PrematchReason(
                    title="Moderate model lean",
                    body=f"The pre-match view leans one way at about {win_probability_pct}%, "
                         f"but this is close enough that toss and early conditions could shift the balance.",
                )
            )
        else:
            reasons.append(
                PrematchReason(
                    title="Balanced match-up",
                    body=f"The model sees this as a close contest at approximately {win_probability_pct}% either way. "
                         f"Toss, conditions, and early-game execution are likely to decide the outcome.",
                )
            )

    if venue_label and venue_avg_score:
        reasons.append(
            PrematchReason(
                title=f"{venue_label} venue profile",
                body=f"The expected first-innings par at this venue is approximately {venue_avg_score} runs. "
                     f"Teams batting first will aim to reach or exceed that benchmark.",
            )
        )

    if toss_label and toss_label != "Unknown":
        reasons.append(
            PrematchReason(
                title=f"Toss: {toss_label.lower()} leverage",
                body=f"At this venue, the toss carries {toss_label.lower()} leverage. "
                     f"The decision to bat or chase first depends on the specific scoring profile here.",
            )
        )

    if bat_first_wr is not None:
        if bat_first_wr >= 0.55:
            reasons.append(
                PrematchReason(
                    title="Bat-first advantage",
                    body=f"Historically, teams batting first have won approximately {int(bat_first_wr * 100)}% of "
                         f"completed matches at this venue, suggesting a structural advantage.",
                )
            )
        elif bat_first_wr <= 0.45:
            reasons.append(
                PrematchReason(
                    title="Chase advantage",
                    body=f"Historically, teams chasing have performed well here with only {int(bat_first_wr * 100)}% "
                         f"bat-first win rate, making the toss decision more impactful.",
                )
            )

    # Ensure 3-5 reasons; trim to max or pad with context
    if len(reasons) < REASON_COUNT_MIN:
        fillers = [
            PrematchReason(
                title="Toss context",
                body="The toss decision will depend on venue conditions, team composition, and whether batting or chasing first is advantageous here.",
            ),
            PrematchReason(
                title="Scoring conditions",
                body="The expected par score and pitch behaviour shape how teams approach the first innings and set targets.",
            ),
            PrematchReason(
                title="Pre-match context",
                body="Conditions, dew, and rain data are not yet integrated. The model view is based on team strength, venue history, and projected scoring context.",
            ),
        ]
        needed = REASON_COUNT_MIN - len(reasons)
        reasons.extend(fillers[:needed])

    return reasons[:REASON_COUNT_MAX]


def build_prematch_summary(
    candidate: dict[str, Any],
    league: str = DEFAULT_LEAGUE,
) -> PrematchBriefSummary:
    url = str(candidate.get("url") or "")
    label = str(candidate.get("label") or "")
    title = _match_title(url=url, label=label)
    slug = pre_match_slug(title, league, candidate.get("label"))
    status = "upcoming"
    start_time = candidate.get("label") or None

    return PrematchBriefSummary(
        slug=slug,
        title=title,
        league=league.upper(),
        status=status,
        start_time=start_time,
        venue=None,
        win_probability_pct=None,
        projected_first_innings=None,
        toss_sensitivity_label=None,
        insight="Pre-match model insight will appear once fixture details are available.",
        detail_url=f"/pre-match/{slug}",
    )


def _pre_match_live_slug(title: str, league: str) -> str:
    return _slugify(f"{title} {league.lower()} win probability")


def build_prematch_detail(
    summary: PrematchBriefSummary,
    venue_name: str | None = None,
    win_probability_pct: int | None = None,
) -> PrematchBriefDetail:
    venue_prior = _lookup_venue_prior(venue_name)
    venue_avg = venue_prior.get("venue_avg_score") if venue_prior else None
    venue_bat_first = venue_prior.get("venue_bat_first_win_rate") if venue_prior else None
    venue_label = _venue_bias_label(venue_bat_first)

    projected_first_innings = None
    if venue_avg is not None:
        projected_first_innings = f"~{int(venue_avg)} par"

    toss_label, toss_reason = _toss_sensitivity_label(
        venue_bat_first,
        abs(55 - (win_probability_pct or 50)),
    )

    conditions = _build_conditions()
    pressure_zones = _generate_pressure_zones(venue_avg)

    reasons = _generate_reasons(
        win_probability_pct=win_probability_pct,
        venue_label=venue_label,
        venue_avg_score=int(venue_avg) if venue_avg is not None else None,
        toss_label=toss_label,
        bat_first_wr=venue_bat_first,
    )

    source_status = "ready" if (venue_prior and win_probability_pct is not None) else "partial"
    live_match_slug = _pre_match_live_slug(summary.title, summary.league)

    return PrematchBriefDetail(
        slug=summary.slug,
        title=summary.title,
        league=summary.league,
        status=summary.status,
        start_time=summary.start_time,
        venue=venue_name,
        win_probability_pct=win_probability_pct,
        projected_first_innings=projected_first_innings,
        toss_sensitivity_label=toss_label,
        insight=f"Pre-match brief: {venue_label}. Toss: {toss_label.lower()} leverage." if venue_label else summary.insight,
        detail_url=summary.detail_url,
        venue_avg_score=int(venue_avg) if venue_avg is not None else None,
        venue_bat_first_win_rate=venue_bat_first,
        venue_label=venue_label,
        conditions=conditions,
        pressure_zones=pressure_zones,
        reasons=reasons,
        source_status=source_status,
        live_match_slug=live_match_slug,
    )


class PrematchService:
    """Read-only service for pre-match brief summaries and details."""

    def __init__(self, scheduler: Any = None, prediction_manager: Any = None):
        self.scheduler = scheduler
        self.prediction_manager = prediction_manager
        self._candidates_by_slug: dict[str, dict[str, Any]] = {}

    def _scheduler_candidates(self) -> list[dict[str, Any]]:
        if self.scheduler is None:
            return []
        try:
            status = self.scheduler.status()
        except Exception:
            return []
        candidates = status.get("last_candidates") or []
        return [c for c in candidates if isinstance(c, dict)]

    def _lookup_prediction_probability(self, candidate_url: str) -> int | None:
        """Try to find pre-match probability from any running prediction on the same URL."""
        if self.prediction_manager is None:
            return None
        try:
            from app.public import public_probability_pct
            from app.routers.live import _enrich_detail_state

            for pred in self.prediction_manager.list_predictions():
                pred_url = str(pred.get("match_url") or "").strip().lower()
                if not pred_url or pred_url != candidate_url.strip().lower():
                    continue
                prediction = self.prediction_manager.get_prediction(pred["id"])
                if prediction is None:
                    continue
                raw_state = prediction.read_state() or {}
                state = _enrich_detail_state(raw_state, prediction.output_json_path)
                pct = public_probability_pct(state)
                if pct is not None:
                    return pct
        except Exception:
            pass
        return None

    def list_upcoming(self, league: str = DEFAULT_LEAGUE) -> list[PrematchBriefSummary]:
        candidates = self._scheduler_candidates()
        if not candidates:
            return []

        league_upper = league.upper()
        live_urls: set[str] = set()
        if self.prediction_manager:
            try:
                for pred in self.prediction_manager.list_predictions():
                    if pred.get("status") == "running":
                        url = str(pred.get("match_url") or "")
                        if url:
                            live_urls.add(url.strip().lower())
            except Exception:
                pass

        self._candidates_by_slug.clear()
        summaries: list[PrematchBriefSummary] = []
        for candidate in candidates:
            cand_league = str(candidate.get("league") or "").upper()
            if cand_league != league_upper:
                continue
            url = str(candidate.get("url") or "").strip().lower()
            if url in live_urls:
                continue
            summary = build_prematch_summary(candidate, league=league)
            self._candidates_by_slug[summary.slug] = candidate
            summaries.append(summary)
        return summaries

    def get_detail(self, slug: str, league: str = DEFAULT_LEAGUE) -> PrematchBriefDetail | None:
        summaries = self.list_upcoming(league=league)
        for summary in summaries:
            if summary.slug == slug or _slugify(slug) == _slugify(summary.slug):
                candidate = self._candidates_by_slug.get(summary.slug, {})
                venue_name = _resolve_venue_from_candidate(candidate)
                candidate_url = str(candidate.get("url") or "")
                win_prob = self._lookup_prediction_probability(candidate_url) if candidate_url else None
                return build_prematch_detail(
                    summary,
                    venue_name=venue_name,
                    win_probability_pct=win_prob,
                )
        return None


def _resolve_venue_from_candidate(candidate: dict[str, Any]) -> str | None:
    """Scan candidate label/url for known IPL venue names.

    Uses the short-name alias map derived from IPL_VENUE_PRIORS keys to match
    abbreviated venue names (e.g. 'wankhede', 'chepauk') that appear in CREX
    match labels and URLs, even when venue is not a separate field.
    """
    searchable_texts: list[str] = []
    label = str(candidate.get("label") or "")
    url = str(candidate.get("url") or "")
    if label:
        searchable_texts.append(label.lower())
    if url:
        searchable_texts.append(url.lower())
    searchable = " ".join(searchable_texts)
    for alias, canonical in _VENUE_ALIAS_MAP.items():
        if alias in searchable:
            return canonical
    return None


def prematch_service_from_request(request: Any) -> PrematchService:
    from app.prediction_manager import PredictionManager
    return PrematchService(
        scheduler=getattr(request.app.state, "auto_scheduler", None),
        prediction_manager=PredictionManager.get_instance() if hasattr(request.app.state, "auto_scheduler") and request.app.state.auto_scheduler is not None else None,
    )
