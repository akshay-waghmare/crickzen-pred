"""
Watch live predictor output, queue signal drafts, and require explicit approval.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

from bbl_pipeline.telegram.bot_client import TelegramBotClient
from bbl_pipeline.telegram.config import load_config
from bbl_pipeline.telegram.live_state_adapter import LiveStateError, build_signal_snapshot_from_json, load_live_signal_state
from bbl_pipeline.telegram.signal_publisher import PublicSignalPublisher
from bbl_pipeline.telegram.signal_review_queue import SignalReviewQueue
from bbl_pipeline.telegram.signals import (
    PHASE_CHASE_MIDPOINT,
    PHASE_FINAL_REVIEW,
    PHASE_INNINGS_BREAK,
    PHASE_MID_INNINGS,
    PHASE_POWERPLAY,
    PHASE_PRE_MATCH,
    PHASE_TOSS,
    SignalSnapshot,
)
from bbl_pipeline.telegram.storage import PredictionStorage


RUNNER_STATE_DEFAULT = "data/telegram_signal_runner_state.json"


def detect_current_phase(main_state: dict[str, Any], sidecar_state: dict[str, Any] | None = None) -> tuple[str | None, str]:
    """Return the single current lifecycle phase that should be queued next."""
    sidecar = sidecar_state or {}
    live_state = sidecar.get("state", {})
    toss_winner = live_state.get("toss_winner")
    toss_decision = live_state.get("toss_decision")
    overs = _safe_float(main_state.get("overs"), 0.0) or 0.0
    score = _safe_int(main_state.get("score"), 0) or 0
    target = _safe_int(main_state.get("target"))
    is_second_innings = bool(main_state.get("is_second_innings"))
    total_overs = _safe_float(main_state.get("total_overs"), 20.0) or 20.0
    wickets = _safe_int(main_state.get("wickets"), 0) or 0
    balls_remaining = _balls_remaining(overs, total_overs) if is_second_innings else None

    if _determine_winner(main_state) is not None:
        return PHASE_FINAL_REVIEW, "match complete"

    if is_second_innings:
        if balls_remaining is not None and balls_remaining <= 60:
            return PHASE_CHASE_MIDPOINT, "chase entered midpoint or later"
        return PHASE_INNINGS_BREAK, "second innings started"

    if overs >= 10.0:
        return PHASE_MID_INNINGS, "first innings reached 10 overs"
    if overs >= 6.0:
        return PHASE_POWERPLAY, "first innings reached powerplay checkpoint"
    if toss_winner and toss_decision:
        return PHASE_TOSS, "toss context available"
    if score == 0 and overs == 0:
        return PHASE_PRE_MATCH, "pre-match state"

    return None, "no phase threshold reached"


class SignalAutomationRunner:
    """Queue signal drafts from live predictor state and approve them explicitly."""

    def __init__(
        self,
        *,
        source_json: str,
        queue_path: str,
        storage: PredictionStorage,
        publisher: PublicSignalPublisher | None = None,
        dashboard_url: str | None = None,
    ) -> None:
        self.source_json = source_json
        self.queue = SignalReviewQueue(queue_path)
        self.storage = storage
        self.publisher = publisher
        self.dashboard_url = dashboard_url

    def scan_once(self) -> dict[str, Any] | None:
        """Load live state and enqueue the current missing phase if needed."""
        live_state = load_live_signal_state(self.source_json)
        phase, trigger_reason = detect_current_phase(live_state.main_state, live_state.sidecar_state)
        if not phase:
            return None

        snapshot = build_signal_snapshot_from_json(
            self.source_json,
            phase,
            dashboard_url=self.dashboard_url,
        )
        match_id = snapshot.match_id or snapshot.resolved_match()
        if self._already_queued_or_posted(match_id, phase):
            return None

        if phase in {PHASE_TOSS, PHASE_FINAL_REVIEW}:
            tracker_row = self.storage.find_tracker_row(snapshot.resolved_match())
            if tracker_row and tracker_row.get("pre_match_favorite"):
                snapshot.pre_match_favorite = tracker_row["pre_match_favorite"]

        if self.publisher is None:
            raise RuntimeError("Publisher is required for queue drafting")

        draft = self.publisher.draft(
            phase,
            snapshot,
            expected_match=snapshot.resolved_match(),
        )
        if not draft.publish_ready:
            return None

        return self.queue.enqueue(
            phase=phase,
            match_id=match_id,
            match=snapshot.resolved_match(),
            source_json=self.source_json,
            signal_snapshot=asdict(snapshot),
            draft_message=draft.message,
            tracker_action=draft.tracker_action,
            source_checks=[asdict(check) for check in draft.source_checks],
            trigger_reason=trigger_reason,
        )

    def approve(self, queue_id: str, *, approval_note: str | None = None) -> dict[str, Any]:
        """Publish a queued draft after human approval.

        Posts the stored draft message verbatim — source checks (including
        freshness) are NOT re-run, since the operator already reviewed them.
        """
        if self.publisher is None:
            raise RuntimeError("Publisher is required for approval")
        item = self.queue.get_item(queue_id)
        if item is None:
            raise RuntimeError(f"Queue item not found: {queue_id}")
        if item.get("status") != "pending":
            raise RuntimeError(f"Queue item is not pending: {queue_id}")

        snapshot = SignalSnapshot(**item["signal_snapshot"])
        approved_message = item.get("draft_message", "")
        if not approved_message:
            raise RuntimeError("Queue item has no draft_message to post")

        result = self.publisher.publish_approved(
            item["phase"],
            snapshot,
            approved_message,
            source_checks=item.get("source_checks"),
        )
        if not result.success:
            error = result.post_result.error_message if result.post_result else "Telegram post failed"
            raise RuntimeError(error)

        return self.queue.update_status(
            queue_id,
            status="approved",
            approval_note=approval_note,
            telegram_message_id=result.post_result.message_id if result.post_result else None,
        )

    def reject(self, queue_id: str, *, note: str | None = None) -> dict[str, Any]:
        """Reject a queued draft without posting."""
        return self.queue.update_status(queue_id, status="rejected", approval_note=note)

    def _already_queued_or_posted(self, match_id: str, phase: str) -> bool:
        if self.queue.pending_for_match_phase(match_id, phase) is not None:
            return True
        for record in self.storage.read_all_records():
            if (
                record.get("post_type") == "public_signal"
                and record.get("match_id") == match_id
                and record.get("phase") == phase
            ):
                return True
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Queue and approve Telegram public signal drafts from live predictor JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    watch_parser = subparsers.add_parser("watch", help="Watch the live JSON and queue pending drafts.")
    watch_parser.add_argument("--source-json", default=None, help="Live predictor JSON path.")
    watch_parser.add_argument("--source-dir", default=None, help="Directory to auto-discover latest live predictor JSON (e.g. data/dashboard_states).")
    watch_parser.add_argument("--queue-path", default=None, help="Review queue JSON path.")
    watch_parser.add_argument("--interval-seconds", type=float, default=15.0, help="Polling interval.")
    watch_parser.add_argument("--once", action="store_true", help="Scan once and exit.")
    watch_parser.add_argument("--auto-approve", action="store_true", help="Post drafts automatically without human approval.")

    list_parser = subparsers.add_parser("list", help="List queued drafts.")
    list_parser.add_argument("--queue-path", default=None, help="Review queue JSON path.")
    list_parser.add_argument("--status", default=None, help="Optional status filter.")

    approve_parser = subparsers.add_parser("approve", help="Approve and post a queued draft.")
    approve_parser.add_argument("queue_id", help="Queue id to approve.")
    approve_parser.add_argument("--queue-path", default=None, help="Review queue JSON path.")
    approve_parser.add_argument("--note", default=None, help="Optional approval note.")

    reject_parser = subparsers.add_parser("reject", help="Reject a queued draft without posting.")
    reject_parser.add_argument("queue_id", help="Queue id to reject.")
    reject_parser.add_argument("--queue-path", default=None, help="Review queue JSON path.")
    reject_parser.add_argument("--note", default=None, help="Optional rejection note.")

    args = parser.parse_args(argv)
    cfg = load_config()
    queue_path = args.queue_path or cfg.signal_queue_path
    source_json = getattr(args, "source_json", None) or cfg.signal_source_json
    source_dir = getattr(args, "source_dir", None)
    storage = PredictionStorage(cfg.storage_path, tracker_path=cfg.signal_tracker_path)
    publisher = PublicSignalPublisher(
        TelegramBotClient(cfg),
        storage,
        dashboard_base_url=cfg.public_dashboard_base_url,
    )
    runner = SignalAutomationRunner(
        source_json=source_json,
        queue_path=queue_path,
        storage=storage,
        publisher=publisher,
        dashboard_url=cfg.public_dashboard_base_url,
    )

    if args.command == "watch":
        logging.basicConfig(
            stream=sys.stdout,
            level=logging.INFO,
            format="%(asctime)s [runner] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        log = logging.getLogger(__name__)
        auto = getattr(args, "auto_approve", False)
        log.info("Watcher started — interval=%ss source_dir=%s auto_approve=%s", args.interval_seconds, source_dir or source_json, auto)
        while True:
            try:
                if source_dir:
                    latest = _find_latest_state_json(Path(source_dir))
                    if latest:
                        runner.source_json = str(latest)
                item = runner.scan_once()
                if item is not None:
                    qid = item.get("queue_id")
                    phase = item.get("phase")
                    log.info("Queued draft phase=%s id=%s", phase, qid)
                    if auto:
                        try:
                            result = runner.approve(qid, approval_note="auto-approved")
                            log.info("Auto-posted phase=%s telegram_id=%s", phase, result.get("telegram_message_id"))
                        except Exception as ae:  # noqa: BLE001
                            log.error("Auto-approve failed phase=%s: %s", phase, ae)
                    else:
                        print(json.dumps(item, indent=2), flush=True)
                else:
                    now_utc = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
                    log.info("scan ok — no new draft  [%s]", now_utc)
            except LiveStateError as e:
                log.warning("LiveStateError: %s", e)
            except Exception as e:  # noqa: BLE001
                log.error("Unexpected error: %s", e)
            if args.once:
                return 0
            time.sleep(args.interval_seconds)

    if args.command == "list":
        queue = SignalReviewQueue(queue_path)
        items = queue.list_items(status=args.status)
        print(json.dumps(items, indent=2))
        return 0

    if args.command == "approve":
        approved = runner.approve(args.queue_id, approval_note=args.note)
        print(json.dumps(approved, indent=2))
        return 0

    if args.command == "reject":
        rejected = runner.reject(args.queue_id, note=args.note)
        print(json.dumps(rejected, indent=2))
        return 0

    return 1


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _balls_remaining(overs: float, total_overs: float) -> int:
    whole = int(overs)
    part = int(round((overs - whole) * 10))
    completed = (whole * 6) + min(part, 5)
    return max(int(round(total_overs * 6)) - completed, 0)


def _determine_winner(main_state: dict[str, Any]) -> str | None:
    if not main_state.get("is_second_innings"):
        return None
    batting_team = main_state.get("batting_team")
    bowling_team = main_state.get("bowling_team")
    score = _safe_int(main_state.get("score"), 0) or 0
    wickets = _safe_int(main_state.get("wickets"), 0) or 0
    overs = _safe_float(main_state.get("overs"), 0.0) or 0.0
    total_overs = _safe_float(main_state.get("total_overs"), 20.0) or 20.0
    target = _safe_int(main_state.get("target"))
    if not target:
        return None
    if score >= target:
        return batting_team
    if wickets >= 10 or overs >= total_overs:
        return bowling_team
    return None


def _find_latest_state_json(state_dir: Path) -> Path | None:
    """Return the most-recently modified non-history/sidecar JSON in state_dir."""
    candidates = [
        p for p in state_dir.glob("*.json")
        if not p.stem.endswith("_history") and not p.stem.endswith("_livematch")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


if __name__ == "__main__":
    raise SystemExit(main())
