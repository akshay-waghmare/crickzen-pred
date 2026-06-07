"""
Pre-match page context builder for CrickenZen.

Normalizes pre-match detail data into a template-safe context with
ready/partial/not-ready sections, factor cards, and framing copy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.prematch import (
    PrematchBriefDetail,
    PrematchBriefSummary,
    ConditionsStatus,
    PressureZoneBand,
    PrematchReason,
    PrematchService,
    prematch_service_from_request,
)

DEFAULT_LEAGUE = "ipl"


@dataclass
class FactorCard:
    label: str
    value: str | None = None
    subtext: str = ""
    not_ready: bool = False


@dataclass
class ConditionCard:
    label: str
    status: str
    detail: str
    badge_class: str


@dataclass
class PrematchPageContext:
    league: str = DEFAULT_LEAGUE
    status: str = "not_ready"
    title: str = ""
    venue: str | None = None
    start_time: str | None = None
    detail: PrematchBriefDetail | None = None
    summary_cards: list[FactorCard] = field(default_factory=list)
    condition_cards: list[ConditionCard] = field(default_factory=list)
    pressure_zones: list[PressureZoneBand] = field(default_factory=list)
    reasons: list[PrematchReason] = field(default_factory=list)
    briefs: list[PrematchBriefSummary] = field(default_factory=list)
    methodology: str = ""
    detail_url: str | None = None


METHODOLOGY_COPY = (
    "This pre-match brief is based on venue history, team-strength priors, and projected scoring context. "
    "It represents the before-the-toss model view and is separate from live ball-by-ball prediction. "
    "Sections marked 'not ready' indicate that the supporting data for that factor is not yet available "
    "or integrated. The brief does not use fabricated values or hidden model magic."
)


def build_prematch_list_context(request: Any, league: str = DEFAULT_LEAGUE) -> PrematchPageContext:
    service = prematch_service_from_request(request)
    briefs = service.list_upcoming(league=league)
    status = "ready" if briefs else "not_ready"
    return PrematchPageContext(
        league=league,
        status=status,
        briefs=briefs,
        methodology=METHODOLOGY_COPY,
    )


def build_prematch_detail_context(
    request: Any,
    slug: str,
    league: str = DEFAULT_LEAGUE,
) -> PrematchPageContext:
    service = prematch_service_from_request(request)
    detail = service.get_detail(slug, league=league)

    if detail is None:
        return PrematchPageContext(
            league=league,
            status="not_ready",
            methodology=METHODOLOGY_COPY,
        )

    cards = _build_factor_cards(detail)
    cond_cards = _build_condition_cards(detail.conditions or [])
    return PrematchPageContext(
        league=league,
        status=detail.source_status,
        title=detail.title,
        venue=detail.venue,
        start_time=detail.start_time,
        detail=detail,
        summary_cards=cards,
        condition_cards=cond_cards,
        pressure_zones=detail.pressure_zones or [],
        reasons=detail.reasons or [],
        methodology=METHODOLOGY_COPY,
        detail_url=detail.detail_url or f"/pre-match/{slug}",
    )


def _build_factor_cards(detail: PrematchBriefDetail) -> list[FactorCard]:
    cards: list[FactorCard] = []

    # Win probability
    prob_ready = detail.win_probability_pct is not None
    cards.append(
        FactorCard(
            label="Win probability",
            value=f"{detail.win_probability_pct}%" if prob_ready else None,
            subtext="Pre-match model lean before toss",
            not_ready=not prob_ready,
        )
    )

    # Projected first innings
    proj_ready = detail.projected_first_innings is not None
    cards.append(
        FactorCard(
            label="Projected first innings",
            value=detail.projected_first_innings if proj_ready else None,
            subtext=f"Venue par: {detail.venue_avg_score}" if detail.venue_avg_score else "Based on venue priors",
            not_ready=not proj_ready,
        )
    )

    # Toss sensitivity
    toss_ready = detail.toss_sensitivity_label is not None and detail.toss_sensitivity_label != "Unknown"
    cards.append(
        FactorCard(
            label="Toss sensitivity",
            value=detail.toss_sensitivity_label if toss_ready else None,
            subtext="How much the match edge shifts with toss outcome",
            not_ready=not toss_ready,
        )
    )

    # Venue profile
    venue_ready = detail.venue_label is not None and detail.venue_label != "Unknown venue bias"
    cards.append(
        FactorCard(
            label="Venue profile",
            value=detail.venue_label if venue_ready else None,
            subtext=f"Avg first-innings: {detail.venue_avg_score}" if detail.venue_avg_score else "Venue data pending",
            not_ready=not venue_ready,
        )
    )

    return cards


def _build_condition_cards(conditions: list[ConditionsStatus]) -> list[ConditionCard]:
    cards: list[ConditionCard] = []
    for cond in conditions:
        if cond.status == "ready":
            badge = "bg-emerald-400 text-slate-950"
        elif cond.status == "partial":
            badge = "bg-amber-500 text-slate-950"
        else:
            badge = "bg-slate-700 text-slate-300"
        cards.append(
            ConditionCard(
                label=cond.label,
                status=cond.status,
                detail=cond.detail,
                badge_class=badge,
            )
        )
    return cards
