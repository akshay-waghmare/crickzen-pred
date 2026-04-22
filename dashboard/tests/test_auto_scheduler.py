"""Tests for automatic CREX match discovery helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.auto_scheduler import _label_mentions_date, extract_crex_match_candidates


def test_extracts_live_psl_match_link():
    html = """
    <a href="/cricket-live-score/lhq-vs-qtg-30th-match-pakistan-super-league-2026-match-updates-10XH">
      LHQ 58/1 6.0 Live QTG Yet to bat
    </a>
    """

    candidates = extract_crex_match_candidates(
        html,
        base_url="https://crex.com/series/pakistan-super-league-2026-2BK",
        target_league_key="PSL",
        source="test",
    )

    assert len(candidates) == 1
    assert candidates[0].league_key == "PSL"
    assert candidates[0].is_live is True
    assert candidates[0].url == (
        "https://crex.com/cricket-live-score/"
        "lhq-vs-qtg-30th-match-pakistan-super-league-2026-match-updates-10XH"
    )


def test_skips_finished_match_link():
    html = """
    <a href="/cricket-live-score/gt-vs-mi-30th-match-indian-premier-league-2026-match-updates-118B">
      GT 100 15.5 MI Won 30th IPL 2026 MI 199/5 20.0
    </a>
    """

    candidates = extract_crex_match_candidates(
        html,
        base_url="https://crex.com/series/indian-premier-league-2026-1PW",
        target_league_key="IPL",
        source="test",
    )

    assert candidates == []


def test_label_date_matching_keeps_today_only():
    today = datetime(2026, 4, 21, tzinfo=timezone.utc)

    assert _label_mentions_date("SRH 31st T20 on Apr 21, 2:00 PM DC", today)
    assert _label_mentions_date("Tuesday, 21 April, 7:30 PM", today)
    assert not _label_mentions_date("LSG 32nd T20 on Apr 22, 2:00 PM RR", today)
