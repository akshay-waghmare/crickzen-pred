"""Tests for automatic CREX match discovery helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.auto_scheduler import (
    AutoPredictionScheduler,
    MatchCandidate,
    _label_mentions_date,
    extract_crex_match_candidates,
)
from app.config import Settings


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


def test_skips_discovered_match_when_url_does_not_resolve_to_target_league():
    html = """
    <a href="/cricket-live-score/den-vs-jsy-2nd-t20-jersey-tour-of-denmark-2026-match-updates-11TU">
      DEN Yet to bat Live JSY 148/7 19.3
    </a>
    """

    candidates = extract_crex_match_candidates(
        html,
        base_url="https://crex.com/cricket-live-score",
        target_league_key="IPL",
        source="test",
    )

    assert candidates == []


def test_label_date_matching_keeps_today_only():
    today = datetime(2026, 4, 21, tzinfo=timezone.utc)

    assert _label_mentions_date("SRH 31st T20 on Apr 21, 2:00 PM DC", today)
    assert _label_mentions_date("Tuesday, 21 April, 7:30 PM", today)
    assert not _label_mentions_date("LSG 32nd T20 on Apr 22, 2:00 PM RR", today)


class _FakeManager:
    def __init__(self):
        self.calls: list[str] = []
        self.started_names: tuple[str | None, str | None] | None = None

    def cleanup_expired(self, settings):
        self.calls.append("cleanup")
        return 0

    def find_active_by_url(self, url, league_key):
        self.calls.append("find")
        return None

    def start_match(self, user_id, match_url, league_key, team1_name=None, team2_name=None):
        self.calls.append("start")
        self.started_names = (team1_name, team2_name)

        class _Pred:
            id = "auto-1"

        return _Pred()


class _TestScheduler(AutoPredictionScheduler):
    async def discover_candidates(self):
        return [
            MatchCandidate(
                url="https://crex.com/cricket-live-score/mi-vs-pbks-ipl-match-updates-xyz",
                league_key="IPL",
                source="test",
                label="MI vs PBKS Live",
                is_live=True,
                team1_name="Mumbai Indians",
                team2_name="Punjab Kings",
            )
        ]


def test_scheduler_cleans_stale_predictions_before_duplicate_check():
    manager = _FakeManager()
    scheduler = _TestScheduler(
        manager=manager,
        settings=Settings(AUTO_PREDICTIONS_ENABLED=True, AUTO_LEAGUE_KEY="IPL"),
    )

    asyncio.run(scheduler.check_once())

    assert manager.calls[:3] == ["cleanup", "find", "start"]
    assert manager.started_names == ("Mumbai Indians", "Punjab Kings")
