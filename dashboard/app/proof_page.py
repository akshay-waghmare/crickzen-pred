"""
Proof page context builder for the CrickenZen dashboard.

Centralizes proof-page display shaping. Loads snapshot artifacts through the
existing proof-metrics loaders, derives page status, groups segments, formats
ledger rows, and exposes methodology copy so the template stays thin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.proof_metrics import (
    load_accuracy_summary,
    load_latest_ledger,
    load_latest_manifest,
    load_latest_segments,
    load_latest_summary,
)

DEFAULT_LEAGUE = "ipl"
MAX_LEDGER_ROWS = 20

METHODOLOGY_COPY = {
    "brier": "Brier score measures the average squared error between predicted probabilities and actual outcomes. "
             "A score of 0 means perfect predictions; 1 is the worst. Lower is better.",
    "ece": "Expected Calibration Error (ECE) compares predicted confidence against actual accuracy. "
           "If the model says 60% and it wins 60% of the time, calibration is perfect (ECE = 0). "
           "Lower is better.",
    "accuracy": "Accuracy tracks discrete pre-match prediction calls. It counts how often the model-favored team "
                "actually won. This is not the same as probability calibration — a model can have good accuracy "
                "on clear favourites but poor calibration on close matches.",
    "calibration_vs_accuracy": "Brier and ECE measure probability quality (calibration). "
                               "Accuracy measures discrete call hit rate. They are different metrics and should not "
                               "be added together or averaged into a single trust score.",
    "scope": "All metrics are computed from completed matches only. Live ball-state data is excluded. "
             "Proof ledger rows are derived from the model's first-ball probability compared against the actual "
             "winner. Sample sizes and dates are shown so you can judge how current this evidence is.",
    "stale_warning": "This proof snapshot is stale. The data may not reflect the most recent matches. "
                     "Run the snapshot builder to refresh.",
    "partial_warning": "Some proof sections are unavailable. Probability metrics may be ready while "
                       "accuracy or ledger data is still accumulating.",
    "not_ready": "Proof data is not available yet. This can happen when no completed match data exists for "
                 "this league, or the snapshot has not been generated. Run the snapshot build script to create it.",
}

METRIC_LABELS = {
    "brier": "Brier Score",
    "ece": "ECE",
    "accuracy_pct": "Accuracy",
    "wins": "Wins",
    "losses": "Losses",
    "sample_count": "Sample Size",
}


@dataclass
class SummaryCard:
    label: str
    value: Optional[str] = None
    definition: str = ""
    subtext: str = ""
    not_ready: bool = False


@dataclass
class SegmentDisplayGroup:
    segment_type: str
    label: str
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LedgerDisplayRow:
    match: str
    predicted_side: str
    probability: str
    winner: str
    result: str
    result_badge: str
    timestamp: str = ""


@dataclass
class ProofPageContext:
    league: str = DEFAULT_LEAGUE
    status: str = "not_ready"
    freshness_label: str = ""
    evaluation_window: str = ""
    last_updated: str = ""
    stale: bool = False
    summary_cards: list[SummaryCard] = field(default_factory=list)
    methodology: dict[str, str] = field(default_factory=dict)
    segments: list[SegmentDisplayGroup] = field(default_factory=list)
    ledger_rows: list[LedgerDisplayRow] = field(default_factory=list)
    status_banner: str = ""
    status_banner_class: str = ""


def _fmt_metric(value: Any, decimals: int = 4, suffix: str = "") -> Optional[str]:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if decimals == 0:
        return f"{int(round(v))}{suffix}"
    return f"{v:.{decimals}f}{suffix}"


def _derive_page_status(
    prob_ready: bool,
    acc_ready: bool,
    ledger_count: int,
    stale: bool,
) -> str:
    if not prob_ready and not acc_ready and ledger_count == 0:
        return "not_ready"
    if stale:
        return "stale"
    if not prob_ready or not acc_ready:
        return "partial"
    return "ready"


def build_proof_page_context(league: str = DEFAULT_LEAGUE) -> ProofPageContext:
    summary = load_latest_summary(league=league)
    segments_data = load_latest_segments(league=league)
    ledger_data = load_latest_ledger(league=league)
    manifest = load_latest_manifest(league=league)

    prob = summary.get("probability_metrics") or {}
    acc = summary.get("accuracy_metrics") or {}
    freshness = summary.get("freshness") or {}

    prob_ready = prob.get("sample_count", 0) > 0
    acc_ready = acc.get("sample_count", 0) > 0 if acc else False
    ledger_count = len(ledger_data) if ledger_data else 0
    stale = freshness.get("stale", False) if freshness else False

    page_status = _derive_page_status(prob_ready, acc_ready, ledger_count, stale)

    status_banner = ""
    status_banner_class = ""
    if page_status == "not_ready":
        status_banner = METHODOLOGY_COPY["not_ready"]
        status_banner_class = "border-slate-700 bg-slate-900/80 text-slate-300"
    elif page_status == "stale":
        status_banner = METHODOLOGY_COPY["stale_warning"]
        status_banner_class = "border-amber-700 bg-amber-900/30 text-amber-200"
    elif page_status == "partial":
        status_banner = METHODOLOGY_COPY["partial_warning"]
        status_banner_class = "border-slate-700 bg-slate-900/80 text-slate-400"

    freshness_label = "Fresh" if not stale else "Stale"
    evaluation_window = summary.get("window", "all_available")
    last_updated = freshness.get("built_at", "")

    cards = _build_summary_cards(summary, prob, acc, prob_ready, acc_ready)

    seg_groups = _build_segment_groups(segments_data)

    ledger_rows = _build_ledger_display(ledger_data)

    methodology = {
        "brier": METHODOLOGY_COPY["brier"],
        "ece": METHODOLOGY_COPY["ece"],
        "accuracy": METHODOLOGY_COPY["accuracy"],
        "calibration_vs_accuracy": METHODOLOGY_COPY["calibration_vs_accuracy"],
        "scope": METHODOLOGY_COPY["scope"],
    }

    return ProofPageContext(
        league=league,
        status=page_status,
        freshness_label=freshness_label,
        evaluation_window=evaluation_window,
        last_updated=last_updated,
        stale=stale,
        summary_cards=cards,
        methodology=methodology,
        segments=seg_groups,
        ledger_rows=ledger_rows,
        status_banner=status_banner,
        status_banner_class=status_banner_class,
    )


def _build_summary_cards(
    summary: dict[str, Any],
    prob: dict[str, Any],
    acc: dict[str, Any],
    prob_ready: bool,
    acc_ready: bool,
) -> list[SummaryCard]:
    cards: list[SummaryCard] = []

    brier = _fmt_metric(prob.get("brier"))
    ece = _fmt_metric(prob.get("ece"))
    log_loss = _fmt_metric(prob.get("log_loss"))
    sample_count = prob.get("sample_count", 0)
    excluded = prob.get("excluded_rows", 0)
    acc_pct = _fmt_metric(acc.get("accuracy_pct"), decimals=1, suffix="%")
    wins = acc.get("wins", 0)
    losses = acc.get("losses", 0)

    cards.append(
        SummaryCard(
            label="Brier Score",
            value=brier if prob_ready else None,
            definition="Probability error. Lower is better.",
            subtext=f"Excludes {excluded:,} rows with missing data" if prob_ready and excluded > 0 else "",
            not_ready=not prob_ready,
        )
    )

    cards.append(
        SummaryCard(
            label="ECE",
            value=ece if prob_ready else None,
            definition="Calibration gap. Lower is better.",
            subtext=f"Based on {sample_count:,} ball states" if prob_ready else "",
            not_ready=not prob_ready,
        )
    )

    cards.append(
        SummaryCard(
            label="Accuracy",
            value=acc_pct if acc_ready else None,
            definition="Pre-match call hit rate.",
            subtext=f"{wins} wins / {losses} losses / {acc.get('excluded_rows', 0)} excluded" if acc_ready else "",
            not_ready=not acc_ready,
        )
    )

    cards.append(
        SummaryCard(
            label="Sample Size",
            value=_fmt_metric(sample_count, decimals=0) if prob_ready else None,
            definition="Evaluated ball states from completed matches.",
            subtext=f"Window: {summary.get('window', 'all_available')}",
            not_ready=not prob_ready,
        )
    )

    if prob_ready and log_loss is not None:
        cards.append(
            SummaryCard(
                label="Log Loss (supporting)",
                value=log_loss,
                definition="Penalises confident wrong predictions.",
                subtext="Supporting context only. Brier and ECE are primary.",
                not_ready=False,
            )
        )

    return cards


def _build_segment_groups(segments_data: Optional[list[dict[str, Any]]]) -> list[SegmentDisplayGroup]:
    groups: list[SegmentDisplayGroup] = []
    by_type: dict[str, list[dict[str, Any]]] = {}
    for seg in (segments_data or []) if isinstance(segments_data, list) else []:
        stype = seg.get("segment_type", "other")
        by_type.setdefault(stype, []).append(seg)

    group_order = [
        ("innings", "By Innings"),
        ("phase", "By Match Phase"),
        ("team_tier", "By Team Tier"),
    ]

    for stype, label in group_order:
        rows = by_type.pop(stype, [])
        if rows:
            groups.append(SegmentDisplayGroup(segment_type=stype, label=label, rows=rows))

    for stype, rows in sorted(by_type.items()):
        groups.append(SegmentDisplayGroup(segment_type=stype, label=stype.replace("_", " ").title(), rows=rows))

    return groups


def _build_ledger_display(ledger_data: Optional[list[dict[str, Any]]]) -> list[LedgerDisplayRow]:
    rows: list[LedgerDisplayRow] = []
    if not isinstance(ledger_data, list):
        return rows
    for row in ledger_data[:MAX_LEDGER_ROWS]:
        predicted_side = row.get("predicted_side", "-")
        prob_pct = row.get("predicted_probability_pct")
        probability = f"{prob_pct:.0f}%" if prob_pct is not None else "-"
        winner = row.get("final_winner", "-")
        result_status = row.get("result_status", "")
        result_badge = "correct" if result_status == "correct" else "incorrect"
        result_label = "Correct" if result_status == "correct" else "Wrong"
        timestamp = row.get("timestamp", "")

        rows.append(
            LedgerDisplayRow(
                match=row.get("match_label", "-"),
                predicted_side=predicted_side,
                probability=probability,
                winner=winner,
                result=result_label,
                result_badge=result_badge,
                timestamp=timestamp[:10] if timestamp else "",
            )
        )
    return rows
