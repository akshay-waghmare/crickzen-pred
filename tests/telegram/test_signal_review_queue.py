"""Tests for the Telegram signal review queue."""

from pathlib import Path

from bbl_pipeline.telegram.signal_review_queue import SignalReviewQueue


def test_enqueue_and_update_status(tmp_path):
    queue = SignalReviewQueue(tmp_path / "queue.json")

    item = queue.enqueue(
        phase="pre_match",
        match_id="ipl_live_ml",
        match="RR vs DC",
        source_json="data/ipl_live_ml.json",
        signal_snapshot={"match": "RR vs DC"},
        draft_message="IPL Pre-match Signal",
        tracker_action="open tracker row",
        source_checks=[{"name": "fixture", "passed": True, "detail": "Fixture verified."}],
        trigger_reason="pre-match state",
    )

    assert item["status"] == "pending"
    pending = queue.pending_for_match_phase("ipl_live_ml", "pre_match")
    assert pending is not None

    updated = queue.update_status(item["queue_id"], status="approved", telegram_message_id=42)

    assert updated["status"] == "approved"
    assert updated["telegram_message_id"] == 42
    assert queue.pending_for_match_phase("ipl_live_ml", "pre_match") is None
