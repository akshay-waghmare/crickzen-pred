"""Tests for the public signal publishing workflow."""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from bbl_pipeline.telegram.bot_client import PostResult
from bbl_pipeline.telegram.signal_publisher import PublicSignalPublisher
from bbl_pipeline.telegram.signals import PHASE_FINAL_REVIEW, PHASE_PRE_MATCH, SignalSnapshot
from bbl_pipeline.telegram.storage import PredictionStorage


def _success_post_result() -> PostResult:
    return PostResult(
        success=True,
        message_id=4321,
        timestamp=datetime(2026, 5, 1, 12, 0, 0),
    )


class TestPublicSignalPublisher:
    def test_publish_prematch_persists_record_and_tracker(self):
        with TemporaryDirectory() as tmpdir:
            storage = PredictionStorage(
                Path(tmpdir) / "records.jsonl",
                tracker_path=Path(tmpdir) / "tracker.csv",
            )
            client = MagicMock()
            client.send_message.return_value = _success_post_result()
            publisher = PublicSignalPublisher(
                client,
                storage,
                dashboard_base_url="https://app.crickzen.com/dashboard",
            )

            snapshot = SignalSnapshot(
                match_id="rr-dc-001",
                match="RR vs DC",
                team_a="RR",
                team_b="DC",
                model_favorite="RR",
                win_probability_pct=57,
                source_timestamp="2026-05-01T11:50:00+00:00",
                reason="RR hold the stronger pre-toss edge.",
            )

            result = publisher.publish(PHASE_PRE_MATCH, snapshot, now=datetime(2026, 5, 1, 12, 0, 0))

            assert result.success is True
            assert result.tracker_row is not None
            assert result.tracker_row.pre_match_favorite == "RR"
            records = storage.read_all_records()
            assert len(records) == 1
            assert records[0]["post_type"] == "public_signal"
            assert records[0]["phase"] == "pre_match"
            assert "https://app.crickzen.com/dashboard" in records[0]["message"]
            tracker_rows = storage.read_tracker_rows()
            assert len(tracker_rows) == 1
            assert tracker_rows[0]["match"] == "RR vs DC"

    def test_publish_final_review_updates_existing_tracker_row(self):
        with TemporaryDirectory() as tmpdir:
            storage = PredictionStorage(
                Path(tmpdir) / "records.jsonl",
                tracker_path=Path(tmpdir) / "tracker.csv",
            )
            storage.upsert_tracker_row(
                {
                    "date": "2026-05-01",
                    "match": "RR vs DC",
                    "pre_match_favorite": "RR",
                    "final_result": "",
                    "confidence": "Medium (57%)",
                    "what_changed": "",
                }
            )
            client = MagicMock()
            client.send_message.return_value = _success_post_result()
            publisher = PublicSignalPublisher(client, storage)

            snapshot = SignalSnapshot(
                match="RR vs DC",
                pre_match_favorite="RR",
                winner="DC",
                source_timestamp="2026-05-01T12:10:00+00:00",
                what_changed="DC owned the powerplay.",
                review="RR started with the edge and lost it inside six overs.",
            )

            result = publisher.publish(PHASE_FINAL_REVIEW, snapshot, now=datetime(2026, 5, 1, 12, 15, 0))

            assert result.success is True
            tracker_rows = storage.read_tracker_rows()
            assert len(tracker_rows) == 1
            assert tracker_rows[0]["final_result"] == "DC"
            assert tracker_rows[0]["what_changed"] == "DC owned the powerplay."

    def test_publish_blocks_when_draft_not_ready(self):
        with TemporaryDirectory() as tmpdir:
            storage = PredictionStorage(
                Path(tmpdir) / "records.jsonl",
                tracker_path=Path(tmpdir) / "tracker.csv",
            )
            client = MagicMock()
            publisher = PublicSignalPublisher(client, storage)

            snapshot = SignalSnapshot(
                match="RR vs DC",
                model_favorite="RR",
                win_probability_pct=57,
                source_timestamp="2026-05-01T09:00:00+00:00",
            )

            result = publisher.publish(PHASE_PRE_MATCH, snapshot, now=datetime(2026, 5, 1, 12, 0, 0))

            assert result.success is False
            assert result.post_result is None
            assert len(storage.read_all_records()) == 0
            client.send_message.assert_not_called()
