"""Tests for the pre-match serializer and factor helpers."""
from __future__ import annotations

import pytest
from app.prematch import (
    _build_conditions,
    _generate_pressure_zones,
    _generate_reasons,
    _lookup_venue_prior,
    _match_title,
    _pre_match_live_slug,
    _resolve_venue_from_candidate,
    _toss_sensitivity_label,
    _venue_bias_label,
    build_prematch_detail,
    build_prematch_summary,
    pre_match_slug,
    ConditionsStatus,
    PrematchBriefSummary,
    PrematchReason,
    PrematchService,
)


class TestVenueLookup:
    def test_known_venue(self):
        prior = _lookup_venue_prior("Wankhede Stadium, Mumbai")
        assert prior is not None
        assert prior["venue_avg_score"] == 178.0
        assert prior["venue_bat_first_win_rate"] == 0.47

    def test_unknown_venue(self):
        prior = _lookup_venue_prior("Unknown Ground, Nowhere")
        assert prior is None

    def test_none_venue(self):
        assert _lookup_venue_prior(None) is None


class TestVenueBiasLabel:
    def test_batting_friendly(self):
        assert _venue_bias_label(0.60) == "Batting-first friendly"

    def test_chase_friendly(self):
        assert _venue_bias_label(0.40) == "Chase-friendly"

    def test_balanced(self):
        assert _venue_bias_label(0.50) == "Balanced venue"

    def test_none(self):
        assert _venue_bias_label(None) == "Unknown venue bias"


class TestTossSensitivity:
    def test_high_leverage(self):
        label, _ = _toss_sensitivity_label(0.57, 5)
        assert label == "High leverage"

    def test_medium_leverage(self):
        label, _ = _toss_sensitivity_label(0.53, 10)
        assert label == "Medium leverage"

    def test_low_leverage(self):
        label, _ = _toss_sensitivity_label(0.51, 20)
        assert label == "Low leverage"

    def test_unknown(self):
        label, _ = _toss_sensitivity_label(None)
        assert label == "Unknown"


class TestPressureZones:
    def test_generates_three_zones(self):
        zones = _generate_pressure_zones(175.0)
        assert len(zones) == 3
        labels = [z.label for z in zones]
        assert "Above par" in labels
        assert "Par band" in labels
        assert "Below par" in labels

    def test_empty_for_none(self):
        assert _generate_pressure_zones(None) == []


class TestConditions:
    def test_returns_list(self):
        conditions = _build_conditions()
        assert len(conditions) >= 2
        for c in conditions:
            assert c.status == "not_ready"


class TestReasons:
    def test_produces_3_to_5_reasons(self):
        reasons = _generate_reasons(
            win_probability_pct=62,
            venue_label="Batting-first friendly",
            venue_avg_score=178,
            toss_label="Medium leverage",
            bat_first_wr=0.47,
        )
        assert 3 <= len(reasons) <= 5

    def test_close_match_produces_balanced_reason(self):
        reasons = _generate_reasons(win_probability_pct=52)
        titles = [r.title for r in reasons]
        assert any("Balanced" in t for t in titles)

    def test_clear_edge_produces_strong_reason(self):
        reasons = _generate_reasons(win_probability_pct=70)
        titles = [r.title for r in reasons]
        assert any("Clear" in t for t in titles)

    def test_minimal_input_still_produces_min_reasons(self):
        reasons = _generate_reasons()
        assert len(reasons) >= 3


class TestSlug:
    def test_stable_slug(self):
        slug = pre_match_slug("MI vs CSK", league="ipl")
        assert "mi-vs-csk" in slug
        assert "pre-match" in slug

    def test_with_date(self):
        slug = pre_match_slug("MI vs CSK", league="ipl", start_time="2026-06-07T14:30:00+00:00")
        assert "20260607" in slug or "mi-vs-csk" in slug


class TestBuildSummary:
    def test_from_candidate(self):
        candidate = {
            "url": "https://crex.live/cricket-live-score/mi-vs-csk-56th-match-indian-premier-league-2026",
            "label": "MI vs CSK on Jun 07, 2026 at 14:30 PM T20",
            "league": "IPL",
        }
        summary = build_prematch_summary(candidate)
        assert summary.slug
        assert "mi-vs-csk" in summary.slug.lower()
        assert summary.status == "upcoming"
        assert summary.league == "IPL"
        assert summary.detail_url


class TestBuildDetail:
    def test_detail_with_venue(self):
        summary = PrematchBriefSummary(
            slug="mi-vs-csk-ipl-pre-match-brief",
            title="MI vs CSK",
            league="IPL",
            status="upcoming",
            detail_url="/pre-match/mi-vs-csk-ipl-pre-match-brief",
        )
        detail = build_prematch_detail(
            summary,
            venue_name="Wankhede Stadium, Mumbai",
            win_probability_pct=58,
        )
        assert detail.venue_avg_score == 178
        assert detail.venue_bat_first_win_rate == 0.47
        assert detail.venue_label == "Balanced venue"
        assert detail.projected_first_innings is not None
        assert detail.toss_sensitivity_label is not None
        assert len(detail.reasons) >= 3
        assert len(detail.pressure_zones) == 3
        assert len(detail.conditions) >= 2
        assert detail.source_status == "ready"

    def test_detail_without_venue(self):
        summary = PrematchBriefSummary(
            slug="test",
            title="Test",
            league="IPL",
            status="upcoming",
            detail_url="/pre-match/test",
        )
        detail = build_prematch_detail(summary)
        assert detail.venue_avg_score is None
        assert detail.source_status == "partial"
        assert len(detail.reasons) >= 3


class _FakeScheduler:
    def __init__(self, last_candidates=None):
        self._last_candidates = last_candidates or []

    def status(self):
        return {"last_candidates": self._last_candidates, "enabled": True}


class TestMatchTitle:
    def test_crex_label_with_format(self):
        title = _match_title(label="MI vs CSK on Jun 07, 2026 at 14:30 PM T20")
        assert title == "MI vs CSK"

    def test_crex_label_teams_before_date(self):
        title = _match_title(label="Chennai Super Kings on Jun 07, 2026 at 18:00 PM IPL")
        assert "Chennai Super Kings" in title

    def test_crex_label_no_format(self):
        title = _match_title(label="KKR vs RCB on May 15, 2026 at 20:00 PM")
        assert "KKR" in title
        assert "RCB" in title

    def test_url_fallback(self):
        title = _match_title(
            url="https://crex.live/cricket-live-score/mi-vs-csk-56th-match-indian-premier-league-2026-match-updates",
            label="",
        )
        assert "MI" in title
        assert "CSK" in title

    def test_unknown_label_returns_truncated(self):
        title = _match_title(label="Some random text without a recognisable pattern")
        assert len(title) <= 72


class TestResolveVenue:
    def test_venue_in_label(self):
        candidate = {
            "url": "https://crex.live/cricket-live-score/mi-vs-csk-match-updates",
            "label": "MI vs CSK at Wankhede Stadium, Mumbai on Jun 07, 2026 at 14:30 PM T20",
            "league": "IPL",
        }
        venue = _resolve_venue_from_candidate(candidate)
        assert venue == "Wankhede Stadium, Mumbai"

    def test_venue_short_name_in_label(self):
        candidate = {
            "url": "",
            "label": "KKR vs RCB at Chinnaswamy, Bengaluru",
            "league": "IPL",
        }
        venue = _resolve_venue_from_candidate(candidate)
        assert venue == "M Chinnaswamy Stadium, Bengaluru"

    def test_venue_in_url(self):
        candidate = {
            "url": "https://crex.live/cricket-live-score/kkr-vs-rcb-eden-gardens-match-updates",
            "label": "",
            "league": "IPL",
        }
        venue = _resolve_venue_from_candidate(candidate)
        assert venue == "Eden Gardens, Kolkata"

    def test_no_venue(self):
        candidate = {"url": "", "label": "MI vs CSK on Jun 07", "league": "IPL"}
        venue = _resolve_venue_from_candidate(candidate)
        assert venue is None


class TestLiveMatchSlug:
    def test_matches_public_slug_pattern(self):
        slug = _pre_match_live_slug("MI vs CSK", "IPL")
        assert "mi-vs-csk" in slug
        assert "win-probability" in slug
        assert "pre-match-brief" not in slug

    def test_different_from_prematch_slug(self):
        pre_slug = pre_match_slug("MI vs CSK", league="ipl")
        live_slug = _pre_match_live_slug("MI vs CSK", "IPL")
        assert pre_slug != live_slug
        assert "pre-match-brief" not in live_slug


class TestPrematchService:
    def test_get_detail_resolves_venue_from_candidate(self, monkeypatch):
        mock_scheduler = _FakeScheduler(
            last_candidates=[
                {
                    "url": "https://crex.live/cricket-live-score/mi-vs-csk-wankhede-match-updates",
                    "label": "MI vs CSK on Jun 07, 2026 at 14:30 PM T20",
                    "league": "IPL",
                }
            ]
        )
        service = PrematchService(scheduler=mock_scheduler)
        detail = service.get_detail("mi-vs-csk-ipl-pre-match-brief")

        assert detail is not None
        assert detail.venue == "Wankhede Stadium, Mumbai"
        assert detail.title == "MI vs CSK"
        assert detail.live_match_slug is not None
        assert "win-probability" in detail.live_match_slug

    def test_get_detail_no_venue_is_partial(self, monkeypatch):
        mock_scheduler = _FakeScheduler(
            last_candidates=[
                {
                    "url": "https://crex.live/cricket-live-score/unk-vs-unk-match-updates",
                    "label": "UNK vs UNK on Jun 07, 2026 at 14:30 PM T20",
                    "league": "IPL",
                }
            ]
        )
        service = PrematchService(scheduler=mock_scheduler)
        detail = service.get_detail("unk-vs-unk-ipl-pre-match-brief")

        assert detail is not None
        assert detail.venue is None
        assert detail.source_status == "partial"

    def test_get_detail_missing_slug_returns_none(self, monkeypatch):
        mock_scheduler = _FakeScheduler(last_candidates=[])
        service = PrematchService(scheduler=mock_scheduler)
        assert service.get_detail("nonexistent") is None

    def test_list_upcoming_with_candidates(self, monkeypatch):
        mock_scheduler = _FakeScheduler(
            last_candidates=[
                {
                    "url": "https://crex.live/cricket-live-score/a-vs-b-match-updates",
                    "label": "A vs B on Jun 07, 2026 at 14:30 PM T20",
                    "league": "IPL",
                },
                {
                    "url": "https://crex.live/cricket-live-score/c-vs-d-match-updates",
                    "label": "C vs D on Jun 07, 2026 at 18:00 PM T20",
                    "league": "IPL",
                },
                {
                    "url": "https://crex.live/cricket-live-score/e-vs-f-match-updates",
                    "label": "E vs F on Jun 07, 2026 at 20:00 PM T20",
                    "league": "BBL",
                },
            ]
        )
        service = PrematchService(scheduler=mock_scheduler)
        summaries = service.list_upcoming(league="ipl")
        assert len(summaries) == 2
        assert all(s.league == "IPL" for s in summaries)
