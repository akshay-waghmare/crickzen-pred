"""Tests for CrickZen Telegram public signal drafting."""

from datetime import datetime, timezone

import pytest

from bbl_pipeline.telegram.signals import (
    NOT_READY_TO_PUBLISH,
    PHASE_CHASE_MIDPOINT,
    PHASE_FINAL_REVIEW,
    PHASE_POWERPLAY,
    PHASE_PRE_MATCH,
    PHASE_TOSS,
    READY_TO_PUBLISH,
    build_accuracy_tracker_row,
    confidence_label,
    draft_signal,
    is_fresh,
    SignalSnapshot,
)


NOW = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _fresh_timestamp() -> str:
    return "2026-05-01T11:50:00+00:00"


class TestConfidenceLabel:
    def test_low_confidence_band(self):
        assert confidence_label(53) == "Low"

    def test_medium_confidence_band(self):
        assert confidence_label(61) == "Medium"

    def test_high_confidence_band(self):
        assert confidence_label(72) == "High"


class TestFreshness:
    def test_recent_timestamp_is_fresh(self):
        assert is_fresh(_fresh_timestamp(), now=NOW, max_age_minutes=20) is True

    def test_stale_timestamp_is_not_fresh(self):
        assert is_fresh("2026-05-01T10:00:00+00:00", now=NOW, max_age_minutes=20) is False


class TestDraftSignal:
    def test_rr_vs_dc_prematch_is_ready(self):
        snapshot = SignalSnapshot(
            match="RR vs DC",
            team_a="RR",
            team_b="DC",
            model_favorite="RR",
            win_probability_pct=57,
            source_timestamp=_fresh_timestamp(),
            reason="RR hold the stronger pre-toss edge in the current model snapshot.",
            dashboard_url="https://crickzen.example/match/rr-vs-dc",
        )

        draft = draft_signal(PHASE_PRE_MATCH, snapshot, expected_match="RR vs DC", now=NOW)

        assert draft.status == READY_TO_PUBLISH
        assert draft.tracker_action == "open tracker row"
        assert "IPL Pre-match Signal" in draft.message
        assert "Model favorite: RR" in draft.message
        assert "Confidence: Medium (57%)" in draft.message
        assert "Full dashboard: https://crickzen.example/match/rr-vs-dc" in draft.message

    def test_csk_vs_mi_before_toss_uses_internal_note_when_stale(self):
        snapshot = SignalSnapshot(
            match="CSK vs MI",
            team_a="CSK",
            team_b="MI",
            model_favorite="CSK",
            win_probability_pct=54,
            source_timestamp="2026-05-01T09:00:00+00:00",
        )

        draft = draft_signal(PHASE_PRE_MATCH, snapshot, expected_match="CSK vs MI", now=NOW)

        assert draft.status == NOT_READY_TO_PUBLISH
        assert draft.tracker_action == "no action"
        assert "Internal note only." in draft.message
        assert "Model state is stale or missing a timestamp." in draft.message

    def test_toss_update_reports_change(self):
        snapshot = SignalSnapshot(
            match="RR vs DC",
            team_a="RR",
            team_b="DC",
            pre_match_favorite="RR",
            model_favorite="DC",
            win_probability_pct=56,
            source_timestamp=_fresh_timestamp(),
            toss_winner="DC",
            toss_decision="bowl",
            probability_delta_pct=-7,
            reason="The toss pushes the chase setup toward DC in this venue profile.",
            dashboard_url="https://crickzen.example/match/rr-vs-dc",
        )

        draft = draft_signal(PHASE_TOSS, snapshot, expected_match="RR vs DC", now=NOW)

        assert draft.status == READY_TO_PUBLISH
        assert "Pre-match favorite: RR" in draft.message
        assert "Current favorite: DC (56%)" in draft.message
        assert "Change: -7 pts" in draft.message

    def test_powerplay_update_formats_score_context(self):
        snapshot = SignalSnapshot(
            match="RR vs DC",
            team_a="RR",
            team_b="DC",
            model_favorite="DC",
            win_probability_pct=63,
            source_timestamp=_fresh_timestamp(),
            score="42/2",
            overs="6",
            probability_delta_pct=6,
            what_changed="DC struck twice in the powerplay and shifted the balance early.",
        )

        draft = draft_signal(PHASE_POWERPLAY, snapshot, expected_match="RR vs DC", now=NOW)

        assert draft.status == READY_TO_PUBLISH
        assert "Score: 42/2 after 6 overs" in draft.message
        assert "Current favorite: DC (63%)" in draft.message
        assert "Move since pre-match: +6 pts" in draft.message

    def test_chase_midpoint_requires_pressure_fields(self):
        snapshot = SignalSnapshot(
            match="RR vs DC",
            team_a="RR",
            team_b="DC",
            model_favorite="DC",
            win_probability_pct=58,
            source_timestamp=_fresh_timestamp(),
            runs_needed=67,
            balls_remaining=42,
            wickets_in_hand=6,
            reason="The chase is still controlled but one wicket can flip the edge.",
        )

        draft = draft_signal(PHASE_CHASE_MIDPOINT, snapshot, expected_match="RR vs DC", now=NOW)

        assert draft.status == READY_TO_PUBLISH
        assert "Chase state: 67 from 42, 6 wickets left" in draft.message
        assert "Pressure read: The chase is still controlled but one wicket can flip the edge." in draft.message

    def test_fixture_mismatch_blocks_publish(self):
        snapshot = SignalSnapshot(
            match="SRH vs KKR",
            team_a="SRH",
            team_b="KKR",
            model_favorite="SRH",
            win_probability_pct=59,
            source_timestamp=_fresh_timestamp(),
        )

        draft = draft_signal(PHASE_PRE_MATCH, snapshot, expected_match="RR vs DC", now=NOW)

        assert draft.status == NOT_READY_TO_PUBLISH
        assert any(check.name == "fixture" and not check.passed for check in draft.source_checks)

    def test_final_review_updates_tracker(self):
        snapshot = SignalSnapshot(
            match="RR vs DC",
            team_a="RR",
            team_b="DC",
            pre_match_favorite="RR",
            winner="DC",
            source_timestamp=_fresh_timestamp(),
            what_changed="DC won the powerplay battle and kept RR behind par all night.",
            review="The pre-match edge was real, but RR lost too much value inside the first six overs.",
            dashboard_url="https://crickzen.example/match/rr-vs-dc",
        )

        draft = draft_signal(PHASE_FINAL_REVIEW, snapshot, expected_match="RR vs DC", now=NOW)

        assert draft.status == READY_TO_PUBLISH
        assert draft.tracker_action == "update tracker row"
        assert "Winner: DC" in draft.message
        assert "Model call: Wrong" in draft.message
        assert "Tracker updated." in draft.message


class TestAccuracyTracker:
    def test_build_tracker_row_for_wrong_call(self):
        pre_match = SignalSnapshot(
            match="RR vs DC",
            team_a="RR",
            team_b="DC",
            model_favorite="RR",
            win_probability_pct=57,
            source_timestamp="2026-05-01T11:20:00+00:00",
        )
        final = SignalSnapshot(
            match="RR vs DC",
            winner="DC",
            what_changed="DC powerplay wickets moved the chase pressure far earlier than expected.",
        )

        row = build_accuracy_tracker_row(pre_match, final, now=NOW)

        assert row.date == "2026-05-01"
        assert row.match == "RR vs DC"
        assert row.pre_match_favorite == "RR"
        assert row.final_result == "DC"
        assert row.confidence == "Medium (57%)"
        assert "powerplay wickets" in row.what_changed

    def test_missing_winner_raises(self):
        pre_match = SignalSnapshot(match="RR vs DC", model_favorite="RR", win_probability_pct=57)
        final = SignalSnapshot(match="RR vs DC")

        with pytest.raises(ValueError, match="missing winner"):
            build_accuracy_tracker_row(pre_match, final, now=NOW)
