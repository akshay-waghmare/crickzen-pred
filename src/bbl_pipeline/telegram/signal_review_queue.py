"""
Simple review queue for Telegram public signal drafts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid


class SignalQueueError(Exception):
    """Raised when the review queue cannot be read or written."""


@dataclass
class QueuedSignalDraft:
    """One queued signal awaiting human review."""

    queue_id: str
    created_at_utc: str
    status: str
    phase: str
    match_id: str
    match: str
    source_json: str
    signal_snapshot: dict[str, Any]
    draft_message: str
    tracker_action: str
    source_checks: list[dict[str, Any]]
    trigger_reason: str
    approved_at_utc: str | None = None
    rejected_at_utc: str | None = None
    approval_note: str | None = None
    telegram_message_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SignalReviewQueue:
    """Atomic JSON-file-backed queue for pending signal drafts."""

    def __init__(self, queue_path: str | Path):
        self.queue_path = Path(queue_path)
        self._ensure_exists()

    def _ensure_exists(self) -> None:
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.queue_path.exists():
            self._write_all([])

    def list_items(self, *, status: str | None = None) -> list[dict[str, Any]]:
        items = self._read_all()
        if status is None:
            return items
        return [item for item in items if item.get("status") == status]

    def get_item(self, queue_id: str) -> dict[str, Any] | None:
        for item in self._read_all():
            if item.get("queue_id") == queue_id:
                return item
        return None

    def enqueue(
        self,
        *,
        phase: str,
        match_id: str,
        match: str,
        source_json: str,
        signal_snapshot: dict[str, Any],
        draft_message: str,
        tracker_action: str,
        source_checks: list[dict[str, Any]],
        trigger_reason: str,
    ) -> dict[str, Any]:
        items = self._read_all()
        entry = QueuedSignalDraft(
            queue_id=str(uuid.uuid4()),
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            status="pending",
            phase=phase,
            match_id=match_id,
            match=match,
            source_json=source_json,
            signal_snapshot=signal_snapshot,
            draft_message=draft_message,
            tracker_action=tracker_action,
            source_checks=source_checks,
            trigger_reason=trigger_reason,
        ).to_dict()
        items.append(entry)
        self._write_all(items)
        return entry

    def update_status(
        self,
        queue_id: str,
        *,
        status: str,
        approval_note: str | None = None,
        telegram_message_id: int | None = None,
    ) -> dict[str, Any]:
        items = self._read_all()
        for item in items:
            if item.get("queue_id") != queue_id:
                continue
            item["status"] = status
            item["approval_note"] = approval_note
            item["telegram_message_id"] = telegram_message_id
            now_iso = datetime.now(timezone.utc).isoformat()
            if status == "approved":
                item["approved_at_utc"] = now_iso
            if status == "rejected":
                item["rejected_at_utc"] = now_iso
            self._write_all(items)
            return item
        raise SignalQueueError(f"Queue item not found: {queue_id}")

    def pending_for_match_phase(self, match_id: str, phase: str) -> dict[str, Any] | None:
        for item in reversed(self.list_items(status="pending")):
            if item.get("match_id") == match_id and item.get("phase") == phase:
                return item
        return None

    def _read_all(self) -> list[dict[str, Any]]:
        try:
            with open(self.queue_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except json.JSONDecodeError as e:
            raise SignalQueueError(f"Invalid queue JSON: {e}")
        except IOError as e:
            raise SignalQueueError(f"Failed reading queue: {e}")
        if not isinstance(payload, list):
            raise SignalQueueError("Signal queue must be a JSON array")
        return payload

    def _write_all(self, items: list[dict[str, Any]]) -> None:
        temp_path = self.queue_path.with_suffix(f"{self.queue_path.suffix}.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)
            temp_path.replace(self.queue_path)
        except IOError as e:
            raise SignalQueueError(f"Failed writing queue: {e}")
