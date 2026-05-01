"""
Dry-run drafting for CrickZen Telegram public signals.

This module turns verified match state into Telegram-ready drafts with
publish guardrails. It does not post to Telegram directly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Iterable


READY_TO_PUBLISH = "READY TO PUBLISH"
NOT_READY_TO_PUBLISH = "NOT READY TO PUBLISH"

PHASE_PRE_MATCH = "pre_match"
PHASE_TOSS = "toss"
PHASE_POWERPLAY = "powerplay"
PHASE_MID_INNINGS = "mid_innings"
PHASE_INNINGS_BREAK = "innings_break"
PHASE_CHASE_MIDPOINT = "chase_midpoint"
PHASE_FINAL_REVIEW = "final_review"

DEFAULT_FRESHNESS_MINUTES = 20


@dataclass(frozen=True)
class SourceCheck:
    """One source-of-truth check for a public signal draft."""

    name: str
    passed: bool
    detail: str


@dataclass
class SignalSnapshot:
    """Minimal match state needed to draft a public signal."""

    match_id: str | None = None
    match: str | None = None
    team_a: str | None = None
    team_b: str | None = None
    model_favorite: str | None = None
    win_probability_pct: int | None = None
    source_timestamp: str | None = None
    score: str | None = None
    overs: str | None = None
    toss_winner: str | None = None
    toss_decision: str | None = None
    probability_delta_pct: int | None = None
    reason: str | None = None
    caveat: str | None = None
    target: int | None = None
    runs_needed: int | None = None
    balls_remaining: int | None = None
    wickets_in_hand: int | None = None
    pre_match_favorite: str | None = None
    winner: str | None = None
    what_changed: str | None = None
    review: str | None = None
    dashboard_url: str | None = None

    def resolved_match(self) -> str:
        """Return the best available human-readable match title."""
        if self.match:
            return self.match.strip()
        if self.team_a and self.team_b:
            return f"{self.team_a.strip()} vs {self.team_b.strip()}"
        return "Unknown match"

    def current_favorite(self) -> str | None:
        """Return the active favorite for the current snapshot."""
        return self.model_favorite or self.pre_match_favorite


@dataclass
class SignalPostDraft:
    """Telegram-ready draft plus publish gating state."""

    status: str
    phase: str
    source_checks: list[SourceCheck]
    message: str
    tracker_action: str

    @property
    def publish_ready(self) -> bool:
        """Whether the draft is ready for a human to publish."""
        return self.status == READY_TO_PUBLISH


@dataclass
class AccuracyTrackerRow:
    """Simple public-facing result tracker row."""

    date: str
    match: str
    pre_match_favorite: str
    final_result: str
    confidence: str
    what_changed: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-safe tracker row."""
        return asdict(self)


def confidence_label(win_probability_pct: int | None) -> str:
    """Map a rounded win probability to a public confidence band."""
    if win_probability_pct is None:
        return "Unknown"
    edge = abs(win_probability_pct - 50)
    if edge < 5:
        return "Low"
    if edge < 15:
        return "Medium"
    return "High"


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO-ish timestamp into an aware UTC datetime."""
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_fresh(
    source_timestamp: str | None,
    *,
    now: datetime | None = None,
    max_age_minutes: int = DEFAULT_FRESHNESS_MINUTES,
) -> bool:
    """Return whether the model snapshot is recent enough to publish."""
    parsed = parse_timestamp(source_timestamp)
    if parsed is None:
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    return current - parsed <= timedelta(minutes=max_age_minutes)


def normalize_match_text(value: str) -> str:
    """Normalize match text for loose equality checks."""
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def verify_expected_match(snapshot: SignalSnapshot, expected_match: str | None) -> bool:
    """Check whether the snapshot matches the operator's expected fixture."""
    if not expected_match:
        return snapshot.resolved_match() != "Unknown match"
    expected = normalize_match_text(expected_match)
    candidates = {
        normalize_match_text(snapshot.resolved_match()),
        normalize_match_text(f"{snapshot.team_a or ''} vs {snapshot.team_b or ''}"),
        normalize_match_text(f"{snapshot.team_b or ''} vs {snapshot.team_a or ''}"),
    }
    return expected in candidates


def draft_signal(
    phase: str,
    snapshot: SignalSnapshot,
    *,
    expected_match: str | None = None,
    now: datetime | None = None,
    max_age_minutes: int = DEFAULT_FRESHNESS_MINUTES,
) -> SignalPostDraft:
    """Build a Telegram draft with source checks and publish gating."""
    checks = _source_checks(
        phase,
        snapshot,
        expected_match=expected_match,
        now=now,
        max_age_minutes=max_age_minutes,
    )
    ready = all(check.passed for check in checks if check.name != "dashboard_cta")
    if ready:
        message = _format_phase_message(phase, snapshot)
        tracker_action = _tracker_action(phase)
        status = READY_TO_PUBLISH
    else:
        failures = [check.detail for check in checks if not check.passed and check.name != "dashboard_cta"]
        message = _format_internal_note(phase, snapshot, failures)
        tracker_action = "no action"
        status = NOT_READY_TO_PUBLISH
    return SignalPostDraft(
        status=status,
        phase=phase,
        source_checks=checks,
        message=message,
        tracker_action=tracker_action,
    )


def build_accuracy_tracker_row(
    pre_match_snapshot: SignalSnapshot,
    final_snapshot: SignalSnapshot,
    *,
    now: datetime | None = None,
) -> AccuracyTrackerRow:
    """Build the public accuracy tracker row after a final review."""
    pre_match_favorite = pre_match_snapshot.current_favorite()
    if not pre_match_favorite:
        raise ValueError("pre_match_snapshot is missing a favorite")
    if not final_snapshot.winner:
        raise ValueError("final_snapshot is missing winner")

    date_source = parse_timestamp(pre_match_snapshot.source_timestamp)
    if date_source is None:
        date_source = now or datetime.now(timezone.utc)
    confidence = confidence_label(pre_match_snapshot.win_probability_pct)
    if pre_match_snapshot.win_probability_pct is not None:
        confidence = f"{confidence} ({pre_match_snapshot.win_probability_pct}%)"

    what_changed = (
        final_snapshot.what_changed
        or final_snapshot.reason
        or final_snapshot.review
        or "No post-match note recorded."
    )
    return AccuracyTrackerRow(
        date=date_source.date().isoformat(),
        match=pre_match_snapshot.resolved_match(),
        pre_match_favorite=pre_match_favorite,
        final_result=final_snapshot.winner,
        confidence=confidence,
        what_changed=what_changed,
    )


def _source_checks(
    phase: str,
    snapshot: SignalSnapshot,
    *,
    expected_match: str | None,
    now: datetime | None,
    max_age_minutes: int,
) -> list[SourceCheck]:
    fixture_ok = verify_expected_match(snapshot, expected_match)
    freshness_ok = is_fresh(snapshot.source_timestamp, now=now, max_age_minutes=max_age_minutes)
    return [
        SourceCheck(
            name="fixture",
            passed=fixture_ok,
            detail="Fixture verified." if fixture_ok else "Fixture does not match the requested teams/date.",
        ),
        SourceCheck(
            name="freshness",
            passed=freshness_ok,
            detail="Model state is fresh." if freshness_ok else "Model state is stale or missing a timestamp.",
        ),
        _phase_data_check(phase, snapshot),
        SourceCheck(
            name="dashboard_cta",
            passed=bool(snapshot.dashboard_url),
            detail="Dashboard CTA ready." if snapshot.dashboard_url else "Dashboard CTA omitted.",
        ),
    ]


def _phase_data_check(phase: str, snapshot: SignalSnapshot) -> SourceCheck:
    favorite = snapshot.current_favorite()
    probability_ready = snapshot.win_probability_pct is not None
    if phase == PHASE_FINAL_REVIEW:
        passed = bool(snapshot.pre_match_favorite or favorite) and bool(snapshot.winner)
        detail = "Final review fields present." if passed else "Final review is missing pre-match favorite or winner."
        return SourceCheck(name="phase_data", passed=passed, detail=detail)

    if phase == PHASE_TOSS:
        passed = bool(snapshot.toss_winner and snapshot.toss_decision and favorite and probability_ready)
        detail = "Toss context is complete." if passed else "Toss update is missing toss context, favorite, or probability."
        return SourceCheck(name="phase_data", passed=passed, detail=detail)

    if phase == PHASE_CHASE_MIDPOINT:
        passed = bool(
            favorite
            and probability_ready
            and snapshot.runs_needed is not None
            and snapshot.balls_remaining is not None
            and snapshot.wickets_in_hand is not None
        )
        detail = "Chase midpoint fields present." if passed else "Chase midpoint is missing chase pressure fields or probability."
        return SourceCheck(name="phase_data", passed=passed, detail=detail)

    passed = bool(favorite and probability_ready)
    detail = "Probability and favorite present." if passed else "Favorite or win probability is missing."
    return SourceCheck(name="phase_data", passed=passed, detail=detail)


def _tracker_action(phase: str) -> str:
    if phase == PHASE_PRE_MATCH:
        return "open tracker row"
    if phase == PHASE_FINAL_REVIEW:
        return "update tracker row"
    return "no action"


def _format_internal_note(phase: str, snapshot: SignalSnapshot, failures: Iterable[str]) -> str:
    issues = "; ".join(failures) if failures else "Publish checks failed."
    return "\n".join(
        [
            "Internal note only.",
            f"Phase: {phase}",
            f"Match: {snapshot.resolved_match()}",
            f"Issue: {issues}",
        ]
    )


def _format_phase_message(phase: str, snapshot: SignalSnapshot) -> str:
    if phase == PHASE_PRE_MATCH:
        return _format_pre_match(snapshot)
    if phase == PHASE_TOSS:
        return _format_toss(snapshot)
    if phase == PHASE_POWERPLAY:
        return _format_powerplay(snapshot)
    if phase == PHASE_MID_INNINGS:
        return _format_mid_innings(snapshot)
    if phase == PHASE_INNINGS_BREAK:
        return _format_innings_break(snapshot)
    if phase == PHASE_CHASE_MIDPOINT:
        return _format_chase_midpoint(snapshot)
    if phase == PHASE_FINAL_REVIEW:
        return _format_final_review(snapshot)
    raise ValueError(f"Unsupported phase: {phase}")


def _format_pre_match(snapshot: SignalSnapshot) -> str:
    caveat = snapshot.caveat or "Toss and confirmed XI can move this."
    lines = [
        "IPL Pre-match Signal",
        f"Match: {snapshot.resolved_match()}",
        "Phase: Before toss",
        f"Model favorite: {snapshot.current_favorite()}",
        f"Confidence: {confidence_label(snapshot.win_probability_pct)} ({snapshot.win_probability_pct}%)",
        f"Why: {snapshot.reason or 'Model edge favours the current side.'}",
        f"Caveat: {caveat}",
    ]
    if snapshot.dashboard_url:
        lines.extend(["", f"Full dashboard: {snapshot.dashboard_url}"])
    return "\n".join(lines)


def _format_toss(snapshot: SignalSnapshot) -> str:
    pre_match_favorite = snapshot.pre_match_favorite or snapshot.current_favorite()
    change = _probability_delta(snapshot.probability_delta_pct)
    lines = [
        "Toss Update",
        f"Match: {snapshot.resolved_match()}",
        f"Toss: {snapshot.toss_winner} chose {snapshot.toss_decision}",
        f"Pre-match favorite: {pre_match_favorite}",
        f"Current favorite: {snapshot.current_favorite()} ({snapshot.win_probability_pct}%)",
        f"Change: {change}",
        f"Read: {snapshot.reason or 'Toss context does not materially change the model view.'}",
    ]
    if snapshot.dashboard_url:
        lines.extend(["", f"Track live probability: {snapshot.dashboard_url}"])
    return "\n".join(lines)


def _format_powerplay(snapshot: SignalSnapshot) -> str:
    lines = [
        "Powerplay Update",
        f"Match: {snapshot.resolved_match()}",
        f"Score: {snapshot.score or 'N/A'} after {snapshot.overs or '6'} overs",
        f"Current favorite: {snapshot.current_favorite()} ({snapshot.win_probability_pct}%)",
        f"Move since pre-match: {_probability_delta(snapshot.probability_delta_pct)}",
        f"What changed: {snapshot.what_changed or snapshot.reason or 'Early overs shifted the model balance.'}",
    ]
    if snapshot.dashboard_url:
        lines.extend(["", f"Track live probability: {snapshot.dashboard_url}"])
    return "\n".join(lines)


def _format_mid_innings(snapshot: SignalSnapshot) -> str:
    lines = [
        "Mid-innings Update",
        f"Match: {snapshot.resolved_match()}",
        f"Score: {snapshot.score or 'N/A'} after {snapshot.overs or '10'} overs",
        f"Model read: {snapshot.reason or 'Current scoring pace is shaping the model view.'}",
        f"Current favorite: {snapshot.current_favorite()} ({snapshot.win_probability_pct}%)",
        f"What changed: {snapshot.what_changed or snapshot.reason or 'Mid-innings context is moving the edge.'}",
    ]
    if snapshot.dashboard_url:
        lines.extend(["", f"Track live probability: {snapshot.dashboard_url}"])
    return "\n".join(lines)


def _format_innings_break(snapshot: SignalSnapshot) -> str:
    lines = [
        "Innings Break",
        f"Match: {snapshot.resolved_match()}",
        f"Target: {snapshot.target}",
        f"Chase favorite: {snapshot.current_favorite()} ({snapshot.win_probability_pct}%)",
        f"Confidence: {confidence_label(snapshot.win_probability_pct)}",
        f"Read: {snapshot.reason or 'The chase setup now defines the model edge.'}",
    ]
    if snapshot.dashboard_url:
        lines.extend(["", f"Track live probability: {snapshot.dashboard_url}"])
    return "\n".join(lines)


def _format_chase_midpoint(snapshot: SignalSnapshot) -> str:
    lines = [
        "Chase Midpoint",
        f"Match: {snapshot.resolved_match()}",
        f"Chase state: {snapshot.runs_needed} from {snapshot.balls_remaining}, {snapshot.wickets_in_hand} wickets left",
        f"Current favorite: {snapshot.current_favorite()} ({snapshot.win_probability_pct}%)",
        f"Pressure read: {snapshot.reason or 'The chase is still within the model range.'}",
    ]
    if snapshot.dashboard_url:
        lines.extend(["", f"Track live probability: {snapshot.dashboard_url}"])
    return "\n".join(lines)


def _format_final_review(snapshot: SignalSnapshot) -> str:
    pre_match_favorite = snapshot.pre_match_favorite or snapshot.current_favorite()
    call_right = "Right" if snapshot.winner == pre_match_favorite else "Wrong"
    lines = [
        "Final Review",
        f"Match: {snapshot.resolved_match()}",
        f"Pre-match favorite: {pre_match_favorite}",
        f"Winner: {snapshot.winner}",
        f"Model call: {call_right}",
        f"What changed: {snapshot.what_changed or snapshot.reason or 'Final review pending detail.'}",
        f"Review: {snapshot.review or 'Review the probability swings against the match finish before the next signal.'}",
        "",
        "Tracker updated.",
    ]
    if snapshot.dashboard_url:
        lines.insert(-2, f"See full probability timeline: {snapshot.dashboard_url}")
    return "\n".join(lines)


def _probability_delta(delta: int | None) -> str:
    if delta is None or delta == 0:
        return "No major change"
    return f"{delta:+d} pts"
