"""
Publishing workflow for CrickZen Telegram public signals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Optional

from bbl_pipeline.telegram.bot_client import PostResult, TelegramBotClient
from bbl_pipeline.telegram.signals import (
    PHASE_FINAL_REVIEW,
    PHASE_PRE_MATCH,
    NOT_READY_TO_PUBLISH,
    READY_TO_PUBLISH,
    AccuracyTrackerRow,
    SignalPostDraft,
    SignalSnapshot,
    SourceCheck,
    _tracker_action,
    build_accuracy_tracker_row,
    confidence_label,
    draft_signal,
    parse_timestamp,
)
from bbl_pipeline.telegram.storage import PredictionStorage


@dataclass
class SignalPublishResult:
    """Result of attempting to publish a public signal."""

    draft: SignalPostDraft
    post_result: Optional[PostResult]
    tracker_row: Optional[AccuracyTrackerRow]

    @property
    def success(self) -> bool:
        """Whether the signal was actually posted to Telegram."""
        return bool(self.post_result and self.post_result.success)


class PublicSignalPublisher:
    """Draft, validate, post, and persist public Telegram signals."""

    def __init__(
        self,
        client: TelegramBotClient,
        storage: PredictionStorage,
        *,
        dashboard_base_url: str | None = None,
    ) -> None:
        self.client = client
        self.storage = storage
        self.dashboard_base_url = dashboard_base_url

    def draft(
        self,
        phase: str,
        snapshot: SignalSnapshot,
        *,
        expected_match: str | None = None,
        now: datetime | None = None,
    ) -> SignalPostDraft:
        """Create a validated draft for operator preview."""
        prepared = self._prepare_snapshot(snapshot)
        return draft_signal(
            phase,
            prepared,
            expected_match=expected_match or prepared.resolved_match(),
            now=now,
        )

    def publish(
        self,
        phase: str,
        snapshot: SignalSnapshot,
        *,
        expected_match: str | None = None,
        now: datetime | None = None,
    ) -> SignalPublishResult:
        """Post a public signal and persist the post record and tracker row."""
        prepared = self._prepare_snapshot(snapshot)
        draft = self.draft(
            phase,
            prepared,
            expected_match=expected_match or prepared.resolved_match(),
            now=now,
        )
        if not draft.publish_ready:
            return SignalPublishResult(draft=draft, post_result=None, tracker_row=None)

        post_result = self.client.send_message(draft.message)
        tracker_row = None
        if post_result.success:
            self.storage.append_record(
                {
                    "match_id": prepared.match_id or prepared.resolved_match(),
                    "match": prepared.resolved_match(),
                    "phase": phase,
                    "post_type": "public_signal",
                    "status": draft.status,
                    "tracker_action": draft.tracker_action,
                    "message": draft.message,
                    "source_checks": [asdict(check) for check in draft.source_checks],
                    "snapshot": asdict(prepared),
                    "telegram_message_id": post_result.message_id,
                    "telegram_timestamp": post_result.timestamp.isoformat() if post_result.timestamp else None,
                }
            )
            tracker_row = self._apply_tracker_update(phase, prepared, now=now)

        return SignalPublishResult(
            draft=draft,
            post_result=post_result,
            tracker_row=tracker_row,
        )

    def publish_approved(
        self,
        phase: str,
        snapshot: SignalSnapshot,
        approved_message: str,
        *,
        source_checks: list | None = None,
        now: datetime | None = None,
    ) -> SignalPublishResult:
        """Post a human-approved draft message verbatim (bypasses freshness re-check).

        Use this when the operator has already reviewed the queued draft.  The
        ``approved_message`` is the exact text that was shown to the operator and
        is posted as-is so that what-you-see == what-gets-sent.
        """
        prepared = self._prepare_snapshot(snapshot)
        post_result = self.client.send_message(approved_message)
        tracker_row = None
        if post_result.success:
            self.storage.append_record(
                {
                    "match_id": prepared.match_id or prepared.resolved_match(),
                    "match": prepared.resolved_match(),
                    "phase": phase,
                    "post_type": "public_signal",
                    "status": READY_TO_PUBLISH,
                    "tracker_action": _tracker_action(phase),
                    "message": approved_message,
                    "source_checks": source_checks or [],
                    "snapshot": asdict(prepared),
                    "telegram_message_id": post_result.message_id,
                    "telegram_timestamp": post_result.timestamp.isoformat() if post_result.timestamp else None,
                    "approved_by": "operator",
                }
            )
            tracker_row = self._apply_tracker_update(phase, prepared, now=now)

        dummy_draft = SignalPostDraft(
            status=READY_TO_PUBLISH if post_result.success else NOT_READY_TO_PUBLISH,
            phase=phase,
            source_checks=[SourceCheck(**c) if isinstance(c, dict) else c for c in (source_checks or [])],
            message=approved_message,
            tracker_action=_tracker_action(phase),
        )
        return SignalPublishResult(draft=dummy_draft, post_result=post_result, tracker_row=tracker_row)

    def _prepare_snapshot(self, snapshot: SignalSnapshot) -> SignalSnapshot:
        """Fill optional defaults before drafting or posting."""
        if snapshot.dashboard_url or not self.dashboard_base_url:
            return snapshot
        return replace(snapshot, dashboard_url=self.dashboard_base_url)

    def _apply_tracker_update(
        self,
        phase: str,
        snapshot: SignalSnapshot,
        *,
        now: datetime | None = None,
    ) -> AccuracyTrackerRow | None:
        if phase == PHASE_PRE_MATCH:
            row = self._build_open_tracker_row(snapshot, now=now)
            self.storage.upsert_tracker_row(row.to_dict())
            return row
        if phase == PHASE_FINAL_REVIEW:
            row = self._build_final_tracker_row(snapshot, now=now)
            self.storage.upsert_tracker_row(row.to_dict())
            return row
        return None

    def _build_open_tracker_row(
        self,
        snapshot: SignalSnapshot,
        *,
        now: datetime | None = None,
    ) -> AccuracyTrackerRow:
        timestamp = parse_timestamp(snapshot.source_timestamp) or now or datetime.now(timezone.utc)
        confidence = confidence_label(snapshot.win_probability_pct)
        if snapshot.win_probability_pct is not None:
            confidence = f"{confidence} ({snapshot.win_probability_pct}%)"
        return AccuracyTrackerRow(
            date=timestamp.date().isoformat(),
            match=snapshot.resolved_match(),
            pre_match_favorite=snapshot.current_favorite() or "Unknown",
            final_result="",
            confidence=confidence,
            what_changed="",
        )

    def _build_final_tracker_row(
        self,
        snapshot: SignalSnapshot,
        *,
        now: datetime | None = None,
    ) -> AccuracyTrackerRow:
        existing = self.storage.find_tracker_row(snapshot.resolved_match())
        if existing:
            pre_match_snapshot = SignalSnapshot(
                match=existing.get("match"),
                model_favorite=existing.get("pre_match_favorite") or None,
                pre_match_favorite=existing.get("pre_match_favorite") or None,
                win_probability_pct=_confidence_pct(existing.get("confidence", "")),
                source_timestamp=_date_to_timestamp(existing.get("date")),
            )
        else:
            pre_match_snapshot = SignalSnapshot(
                match=snapshot.resolved_match(),
                model_favorite=snapshot.pre_match_favorite or snapshot.current_favorite(),
                pre_match_favorite=snapshot.pre_match_favorite or snapshot.current_favorite(),
                source_timestamp=snapshot.source_timestamp,
            )
        return build_accuracy_tracker_row(pre_match_snapshot, snapshot, now=now)


def _confidence_pct(confidence_text: str) -> int | None:
    """Extract the original percentage from 'Medium (57%)' style text."""
    if "(" not in confidence_text or "%" not in confidence_text:
        return None
    try:
        return int(confidence_text.split("(", 1)[1].split("%", 1)[0].strip())
    except ValueError:
        return None


def _date_to_timestamp(date_text: str | None) -> str | None:
    """Convert YYYY-MM-DD into a UTC ISO timestamp string."""
    if not date_text:
        return None
    try:
        return datetime.fromisoformat(date_text).replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None
