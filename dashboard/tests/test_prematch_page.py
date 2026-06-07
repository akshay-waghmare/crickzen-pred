"""Tests for the pre-match page context builder and template rendering."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def sample_detail():
    from app.prematch import (
        PrematchBriefDetail,
        ConditionsStatus,
        PressureZoneBand,
        PrematchReason,
    )
    return PrematchBriefDetail(
        slug="mi-vs-csk-ipl-pre-match-brief",
        title="MI vs CSK",
        league="IPL",
        status="upcoming",
        start_time="2026-06-07T14:30:00+00:00",
        venue="Wankhede Stadium, Mumbai",
        win_probability_pct=58,
        projected_first_innings="~178 par",
        toss_sensitivity_label="Medium leverage",
        insight="Pre-match brief: Balanced venue. Toss: medium leverage.",
        detail_url="/pre-match/mi-vs-csk-ipl-pre-match-brief",
        venue_avg_score=178,
        venue_bat_first_win_rate=0.47,
        venue_label="Balanced venue",
        conditions=[
            ConditionsStatus(label="Dew risk", status="not_ready", detail="Not available."),
            ConditionsStatus(label="Rain risk", status="not_ready", detail="Not available."),
        ],
        pressure_zones=[
            PressureZoneBand(label="Above par", description="Above expected.", range_text="183+"),
            PressureZoneBand(label="Par band", description="Expected range.", range_text="173-182"),
            PressureZoneBand(label="Below par", description="Below expected.", range_text="below 173"),
        ],
        reasons=[
            PrematchReason(title="Moderate model lean", body="The pre-match view leans one way at about 58%."),
            PrematchReason(title="Balanced venue profile", body="Expected par is 178."),
            PrematchReason(title="Toss: medium leverage", body="Toss has moderate effect."),
        ],
        source_status="ready",
        live_match_slug="mi-vs-csk-ipl-win-probability",
    )


class TestPrematchPageContext:
    def test_detail_context_builds_cards(self, sample_detail):
        from app.prematch_page import build_prematch_detail_context, _build_factor_cards

        cards = _build_factor_cards(sample_detail)
        assert len(cards) == 4
        labels = [c.label for c in cards]
        assert "Win probability" in labels
        assert "Projected first innings" in labels
        assert "Toss sensitivity" in labels
        assert "Venue profile" in labels

    def test_detail_context_cards_have_values(self, sample_detail):
        from app.prematch_page import _build_factor_cards

        cards = _build_factor_cards(sample_detail)
        prob_card = next(c for c in cards if c.label == "Win probability")
        assert prob_card.not_ready is False
        assert prob_card.value == "58%"

    def test_detail_context_handles_missing_probability(self):
        from app.prematch import PrematchBriefDetail
        from app.prematch_page import _build_factor_cards

        detail = PrematchBriefDetail(
            slug="test", title="Test", league="IPL", status="upcoming",
            win_probability_pct=None,
            projected_first_innings=None,
            toss_sensitivity_label="Unknown",
            venue_label="Unknown venue bias",
            detail_url="/pre-match/test",
            live_match_slug="test-ipl-win-probability",
        )
        cards = _build_factor_cards(detail)
        not_ready_cards = [c for c in cards if c.not_ready]
        assert len(not_ready_cards) >= 2

    def test_condition_cards_status_badges(self):
        from app.prematch import ConditionsStatus
        from app.prematch_page import _build_condition_cards

        conditions = [
            ConditionsStatus(label="Dew", status="ready", detail="Dew expected."),
            ConditionsStatus(label="Rain", status="not_ready", detail="No data."),
            ConditionsStatus(label="Wind", status="partial", detail="Partial data."),
        ]
        cards = _build_condition_cards(conditions)
        assert len(cards) == 3
        assert cards[0].badge_class != cards[1].badge_class
        assert cards[1].badge_class != cards[2].badge_class


class TestTemplateRendering:
    def _render(self, template_name: str, ctx):
        from jinja2 import Environment, FileSystemLoader

        template_dir = Path(__file__).resolve().parent.parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template(template_name)
        return template.render(
            ctx=ctx,
            settings={},
            seo={"title": "Test", "description": "Test", "canonical": "/test", "noindex": False},
            request=None,
        )

    def test_brief_list_renders(self):
        from app.prematch import PrematchBriefSummary
        from app.prematch_page import PrematchPageContext

        ctx = PrematchPageContext(
            league="ipl",
            status="ready",
            briefs=[
                PrematchBriefSummary(
                    slug="test", title="MI vs CSK", league="IPL", status="upcoming",
                    insight="Pre-match insight.", detail_url="/pre-match/test",
                ),
            ],
        )
        html = self._render("ipl_match_brief_today.html", ctx)
        assert "MI vs CSK" in html
        assert "upcoming" in html.lower()

    def test_brief_detail_renders(self, sample_detail):
        from app.prematch_page import (
            PrematchPageContext,
            _build_factor_cards,
            _build_condition_cards,
        )

        ctx = PrematchPageContext(
            league="ipl",
            status="ready",
            title=sample_detail.title,
            venue=sample_detail.venue,
            detail=sample_detail,
            summary_cards=_build_factor_cards(sample_detail),
            condition_cards=_build_condition_cards(sample_detail.conditions),
            pressure_zones=sample_detail.pressure_zones,
            reasons=sample_detail.reasons,
            methodology="Test methodology.",
        )
        html = self._render("prematch_brief.html", ctx)
        assert "MI vs CSK" in html
        assert "58%" in html
        assert "Pre-match factors" in html
        assert "Conditions" in html
        assert "Pressure zones" in html
        assert "Why the model leans" in html
        assert "How to read this brief" in html

    def test_not_ready_page_renders(self):
        from app.prematch_page import PrematchPageContext

        ctx = PrematchPageContext(league="ipl", status="not_ready")
        html = self._render("prematch_brief.html", ctx)
        assert "not available" in html.lower() or "not_ready" in html.lower()

    def test_list_empty_state_renders(self):
        from app.prematch_page import PrematchPageContext

        ctx = PrematchPageContext(league="ipl", status="not_ready", briefs=[])
        html = self._render("ipl_match_brief_today.html", ctx)
        assert "No upcoming IPL briefs" in html


class TestCTAPresence:
    def test_public_html_has_prematch_cta(self):
        template_path = Path(__file__).resolve().parent.parent / "templates" / "public.html"
        html = template_path.read_text()
        assert 'href="/ipl-match-brief-today"' in html

    def test_ipl_today_has_prematch_link(self):
        template_path = Path(__file__).resolve().parent.parent / "templates" / "ipl_today.html"
        html = template_path.read_text()
        assert 'href="/ipl-match-brief-today"' in html

    def test_detail_uses_live_match_slug_for_cta(self, sample_detail):
        from app.prematch_page import (
            PrematchPageContext,
            _build_factor_cards,
            _build_condition_cards,
        )
        from jinja2 import Environment, FileSystemLoader

        ctx = PrematchPageContext(
            league="ipl",
            status="ready",
            title=sample_detail.title,
            venue=sample_detail.venue,
            detail=sample_detail,
            summary_cards=_build_factor_cards(sample_detail),
            condition_cards=_build_condition_cards(sample_detail.conditions),
            pressure_zones=sample_detail.pressure_zones,
            reasons=sample_detail.reasons,
            methodology="Test methodology.",
        )
        template_dir = Path(__file__).resolve().parent.parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        html = env.get_template("prematch_brief.html").render(
            ctx=ctx,
            settings={},
            seo={"title": "Test", "description": "Test", "canonical": "/test", "noindex": False},
            request=None,
        )
        assert 'href="/match/mi-vs-csk-ipl-win-probability"' in html
        assert "Live prediction page" in html
