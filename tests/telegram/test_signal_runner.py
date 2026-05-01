"""Tests for signal phase detection and queue/approval workflow."""

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from bbl_pipeline.telegram.bot_client import PostResult
from bbl_pipeline.telegram.signal_publisher import PublicSignalPublisher
from bbl_pipeline.telegram.signal_review_queue import SignalReviewQueue
from bbl_pipeline.telegram.signal_runner import SignalAutomationRunner, detect_current_phase
from bbl_pipeline.telegram.storage import PredictionStorage


def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _success_post_result() -> PostResult:
    return PostResult(success=True, message_id=77, timestamp=datetime(2026, 5, 1, 12, 0, 0))


def test_detect_current_phase_progression():
    assert detect_current_phase({"score": 0, "overs": 0.0, "is_second_innings": False})[0] == "pre_match"
    assert detect_current_phase({"score": 12, "overs": 1.5, "is_second_innings": False}, {"state": {"toss_winner": "DC", "toss_decision": "bowl"}})[0] == "toss"
    assert detect_current_phase({"score": 42, "overs": 6.0, "is_second_innings": False})[0] == "powerplay"
    assert detect_current_phase({"score": 78, "overs": 10.0, "is_second_innings": False})[0] == "mid_innings"
    assert detect_current_phase({"score": 0, "overs": 0.2, "target": 176, "is_second_innings": True})[0] == "innings_break"
    assert detect_current_phase({"score": 109, "overs": 13.0, "target": 176, "total_overs": 20, "is_second_innings": True})[0] == "chase_midpoint"
    assert detect_current_phase({"score": 176, "overs": 19.2, "target": 176, "batting_team": "DC", "is_second_innings": True})[0] == "final_review"


def test_scan_once_queues_current_phase_and_approve_posts():
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        source_json = tmp / "ipl_live_ml.json"
        source_sidecar = tmp / "ipl_live_ml_livematch.json"
        now_iso = datetime.now(timezone.utc).isoformat()
        _write_json(
            source_json,
            {
                "timestamp": now_iso,
                "batting_team": "RR",
                "bowling_team": "DC",
                "score": 0,
                "wickets": 0,
                "overs": 0.0,
                "is_second_innings": False,
                "bat_win_prob": 0.57,
                "bowl_win_prob": 0.43,
                "history": [{"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.57}],
            },
        )
        _write_json(source_sidecar, {"state": {}})

        storage = PredictionStorage(tmp / "records.jsonl", tracker_path=tmp / "tracker.csv")
        client = MagicMock()
        client.send_message.return_value = _success_post_result()
        publisher = PublicSignalPublisher(
            client,
            storage,
            dashboard_base_url="https://app.crickzen.com/dashboard",
        )
        runner = SignalAutomationRunner(
            source_json=str(source_json),
            queue_path=str(tmp / "queue.json"),
            storage=storage,
            publisher=publisher,
            dashboard_url="https://app.crickzen.com/dashboard",
        )

        queued = runner.scan_once()

        assert queued is not None
        assert queued["phase"] == "pre_match"
        assert "IPL Pre-match Signal" in queued["draft_message"]

        approved = runner.approve(queued["queue_id"], approval_note="ok to post")

        assert approved["status"] == "approved"
        assert approved["telegram_message_id"] == 77
        records = storage.read_all_records()
        assert len(records) == 1
        assert records[0]["phase"] == "pre_match"
        assert storage.read_tracker_rows()[0]["pre_match_favorite"] == "RR"


def test_scan_once_skips_duplicate_pending_phase():
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        source_json = tmp / "ipl_live_ml.json"
        now_iso = datetime.now(timezone.utc).isoformat()
        _write_json(
            source_json,
            {
                "timestamp": now_iso,
                "batting_team": "RR",
                "bowling_team": "DC",
                "score": 42,
                "wickets": 2,
                "overs": 6.0,
                "is_second_innings": False,
                "bat_win_prob": 0.63,
                "bowl_win_prob": 0.37,
                "history": [
                    {"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.54},
                    {"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.63},
                ],
            },
        )

        storage = PredictionStorage(tmp / "records.jsonl", tracker_path=tmp / "tracker.csv")
        publisher = PublicSignalPublisher(MagicMock(), storage, dashboard_base_url="https://app.crickzen.com/dashboard")
        runner = SignalAutomationRunner(
            source_json=str(source_json),
            queue_path=str(tmp / "queue.json"),
            storage=storage,
            publisher=publisher,
            dashboard_url="https://app.crickzen.com/dashboard",
        )

        first = runner.scan_once()
        second = runner.scan_once()

        assert first is not None
        assert second is None
        queue = SignalReviewQueue(tmp / "queue.json")
        assert len(queue.list_items(status="pending")) == 1


def test_approve_stale_draft_bypasses_freshness():
    """Approval must succeed even when the snapshot timestamp is older than DEFAULT_FRESHNESS_MINUTES."""
    from datetime import timedelta

    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        source_json = tmp / "ipl_live_ml.json"

        # Timestamp 60 minutes old — well past the 20-min freshness window.
        stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        _write_json(
            source_json,
            {
                "timestamp": stale_ts,
                "batting_team": "RR",
                "bowling_team": "DC",
                "score": 0,
                "wickets": 0,
                "overs": 0.0,
                "is_second_innings": False,
                "bat_win_prob": 0.87,
                "bowl_win_prob": 0.13,
                "history": [{"innings": 1, "batting_team": "RR", "bowling_team": "DC", "win_probability": 0.87}],
            },
        )
        _write_json(tmp / "ipl_live_ml_livematch.json", {"state": {}})

        storage = PredictionStorage(tmp / "records.jsonl", tracker_path=tmp / "tracker.csv")
        client = MagicMock()
        client.send_message.return_value = _success_post_result()
        publisher = PublicSignalPublisher(client, storage, dashboard_base_url="https://app.crickzen.com")
        runner = SignalAutomationRunner(
            source_json=str(source_json),
            queue_path=str(tmp / "queue.json"),
            storage=storage,
            publisher=publisher,
            dashboard_url="https://app.crickzen.com",
        )

        # scan_once with stale timestamp: freshness check fails → NOT queued via normal path.
        # We simulate an already-queued stale item by manually injecting it.
        queue = SignalReviewQueue(tmp / "queue.json")
        queue.enqueue(
            phase="innings_break",
            match="RR vs DC",
            match_id="test_stale",
            source_json=str(source_json),
            signal_snapshot={"match": "RR vs DC", "model_favorite": "RR", "win_probability_pct": 87},
            source_checks=[{"name": "freshness", "passed": True, "detail": "was fresh at queue time"}],
            draft_message="Innings Break\nMatch: RR vs DC\nTarget: 226\nChase favorite: RR (87%)",
            tracker_action="no action",
            trigger_reason="second innings started",
        )
        pending = queue.list_items(status="pending")
        assert len(pending) == 1

        # Approve should succeed even though the snapshot timestamp is stale.
        approved = runner.approve(pending[0]["queue_id"])
        assert approved["status"] == "approved"
        assert approved["telegram_message_id"] == 77
        # Verify the exact stored draft_message was posted, not a re-generated one.
        posted_text = client.send_message.call_args[0][0]
        assert "Innings Break" in posted_text
        assert "RR vs DC" in posted_text
