"""
Proof page context builder and route tests.

Covers ready, stale, not-ready, and partial proof states,
segment rendering, ledger rendering, and CTA presence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ---- Fixtures ----


@pytest.fixture
def proof_snapshot_dir(tmp_path):
    """Set up a ready proof snapshot directory with all artifacts."""
    d = tmp_path / "dashboard_metrics"
    d.mkdir(parents=True)
    (d / "latest").mkdir()

    summary = {
        "league": "ipl",
        "window": "all_available",
        "status": "ready",
        "probability_metrics": {
            "brier": 0.1831,
            "ece": 0.0124,
            "log_loss": 0.5812,
            "sample_count": 18240,
            "excluded_rows": 12,
        },
        "accuracy_metrics": {
            "accuracy_pct": 61.5,
            "wins": 24,
            "losses": 15,
            "sample_count": 39,
            "excluded_rows": 2,
        },
        "freshness": {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "stale": False,
        },
        "definitions": {},
    }

    segments = [
        {"segment_type": "innings", "segment_key": "innings_1", "segment_label": "Innings 1", "brier": 0.175, "ece": 0.01, "log_loss": 0.56, "sample_count": 9000},
        {"segment_type": "innings", "segment_key": "innings_2", "segment_label": "Innings 2", "brier": 0.191, "ece": 0.015, "log_loss": 0.60, "sample_count": 9240},
        {"segment_type": "phase", "segment_key": "phase_powerplay", "segment_label": "Powerplay", "brier": 0.19, "ece": 0.015, "log_loss": 0.60, "sample_count": 4000},
        {"segment_type": "phase", "segment_key": "phase_middle", "segment_label": "Middle", "brier": 0.18, "ece": 0.013, "log_loss": 0.58, "sample_count": 5000},
        {"segment_type": "phase", "segment_key": "phase_death", "segment_label": "Death", "brier": 0.185, "ece": 0.012, "log_loss": 0.59, "sample_count": 9240},
    ]

    ledger = [
        {"match_label": "MI vs CSK", "league": "ipl", "predicted_side": "MI", "predicted_probability_pct": 58.0, "final_winner": "MI", "result_status": "correct", "timestamp": "2026-06-01T14:30:00+00:00"},
        {"match_label": "RCB vs KKR", "league": "ipl", "predicted_side": "KKR", "predicted_probability_pct": 55.0, "final_winner": "RCB", "result_status": "incorrect", "timestamp": "2026-06-02T10:00:00+00:00"},
        {"match_label": "DC vs SRH", "league": "ipl", "predicted_side": "DC", "predicted_probability_pct": 62.0, "final_winner": "DC", "result_status": "correct", "timestamp": "2026-06-03T14:30:00+00:00"},
    ]

    manifest = {"build_version": 1, "league": "ipl", "evaluation_window": "all_available", "built_at": datetime.now(timezone.utc).isoformat(), "status": "ready"}

    for name, data in [
        ("ipl_summary.json", summary),
        ("ipl_segments.json", segments),
        ("ipl_ledger.json", ledger),
        ("ipl_manifest.json", manifest),
    ]:
        with open(d / "latest" / name, "w") as f:
            json.dump(data, f)

    return d


@pytest.fixture
def partial_snapshot_dir(tmp_path):
    """Probability ready, accuracy not-ready."""
    d = tmp_path / "dashboard_metrics"
    d.mkdir(parents=True)
    (d / "latest").mkdir()

    summary = {
        "league": "ipl",
        "window": "all_available",
        "status": "ready",
        "probability_metrics": {"brier": 0.20, "ece": 0.03, "log_loss": 0.60, "sample_count": 500, "excluded_rows": 0},
        "accuracy_metrics": {"accuracy_pct": None, "wins": 0, "losses": 0, "sample_count": 0, "excluded_rows": 0},
        "freshness": {"built_at": datetime.now(timezone.utc).isoformat(), "stale": False},
        "definitions": {},
    }

    with open(d / "latest" / "ipl_summary.json", "w") as f:
        json.dump(summary, f)
    with open(d / "latest" / "ipl_segments.json", "w") as f:
        json.dump([], f)
    with open(d / "latest" / "ipl_ledger.json", "w") as f:
        json.dump([], f)
    with open(d / "latest" / "ipl_manifest.json", "w") as f:
        json.dump({"status": "ready"}, f)

    return d


@pytest.fixture
def stale_snapshot_dir(tmp_path):
    """Probability ready but stale."""
    d = tmp_path / "dashboard_metrics"
    d.mkdir(parents=True)
    (d / "latest").mkdir()

    summary = {
        "league": "ipl",
        "window": "all_available",
        "status": "ready",
        "probability_metrics": {"brier": 0.18, "ece": 0.02, "sample_count": 1000, "excluded_rows": 0},
        "accuracy_metrics": {"accuracy_pct": 60.0, "wins": 6, "losses": 4, "sample_count": 10, "excluded_rows": 0},
        "freshness": {"built_at": "2020-01-01T00:00:00+00:00", "stale": False},
        "definitions": {},
    }

    with open(d / "latest" / "ipl_summary.json", "w") as f:
        json.dump(summary, f)
    with open(d / "latest" / "ipl_segments.json", "w") as f:
        json.dump([], f)
    with open(d / "latest" / "ipl_ledger.json", "w") as f:
        json.dump([], f)
    with open(d / "latest" / "ipl_manifest.json", "w") as f:
        json.dump({"status": "ready"}, f)

    return d


# ---- Helper ----


def _build_context_in_dir(league: str, snapshot_dir: Path):
    """Build proof page context using a specific snapshot directory."""
    from app.proof_metrics import (
        load_latest_summary,
        load_latest_segments,
        load_latest_ledger,
        load_latest_manifest,
    )
    from app.proof_page import build_proof_page_context as _builder

    # Monkey-patch the loaders to use our test directory
    original_funcs = {}
    from app import proof_page as pp_module
    original_funcs["load_latest_summary"] = pp_module.load_latest_summary
    original_funcs["load_latest_segments"] = pp_module.load_latest_segments
    original_funcs["load_latest_ledger"] = pp_module.load_latest_ledger
    original_funcs["load_latest_manifest"] = pp_module.load_latest_manifest

    pp_module.load_latest_summary = lambda **kw: load_latest_summary(league=kw.get("league", league), snapshot_dir=snapshot_dir)
    pp_module.load_latest_segments = lambda **kw: load_latest_segments(league=kw.get("league", league), snapshot_dir=snapshot_dir)
    pp_module.load_latest_ledger = lambda **kw: load_latest_ledger(league=kw.get("league", league), snapshot_dir=snapshot_dir)
    pp_module.load_latest_manifest = lambda **kw: load_latest_manifest(league=kw.get("league", league), snapshot_dir=snapshot_dir)

    try:
        return pp_module.build_proof_page_context(league=league)
    finally:
        pp_module.load_latest_summary = original_funcs["load_latest_summary"]
        pp_module.load_latest_segments = original_funcs["load_latest_segments"]
        pp_module.load_latest_ledger = original_funcs["load_latest_ledger"]
        pp_module.load_latest_manifest = original_funcs["load_latest_manifest"]


# ---- Tests ----


class TestProofPageContext:
    """T028: Ready-state context."""

    def test_ready_state(self, proof_snapshot_dir):
        ctx = _build_context_in_dir("ipl", proof_snapshot_dir)
        assert ctx.status == "ready"
        assert ctx.freshness_label == "Fresh"
        assert ctx.stale is False
        assert ctx.evaluation_window == "all_available"
        assert len(ctx.summary_cards) >= 4

    def test_summary_cards_have_brier_ece_accuracy(self, proof_snapshot_dir):
        ctx = _build_context_in_dir("ipl", proof_snapshot_dir)
        labels = [c.label for c in ctx.summary_cards]
        assert "Brier Score" in labels
        assert "ECE" in labels
        assert "Accuracy" in labels
        assert "Sample Size" in labels

    def test_cards_show_values_when_ready(self, proof_snapshot_dir):
        ctx = _build_context_in_dir("ipl", proof_snapshot_dir)
        brier_card = next(c for c in ctx.summary_cards if c.label == "Brier Score")
        assert brier_card.not_ready is False
        assert brier_card.value is not None

    def test_segments_grouped_by_type(self, proof_snapshot_dir):
        ctx = _build_context_in_dir("ipl", proof_snapshot_dir)
        assert len(ctx.segments) >= 2
        group_types = [g.segment_type for g in ctx.segments]
        assert "innings" in group_types
        assert "phase" in group_types

    def test_ledger_rows_populated(self, proof_snapshot_dir):
        ctx = _build_context_in_dir("ipl", proof_snapshot_dir)
        assert len(ctx.ledger_rows) == 3
        assert ctx.ledger_rows[0].match == "MI vs CSK"
        assert ctx.ledger_rows[0].result_badge == "correct"

    def test_methodology_present(self, proof_snapshot_dir):
        ctx = _build_context_in_dir("ipl", proof_snapshot_dir)
        assert "brier" in ctx.methodology
        assert "ece" in ctx.methodology
        assert "accuracy" in ctx.methodology
        assert "calibration_vs_accuracy" in ctx.methodology


class TestStaleState:
    """T029: Stale-state rendering."""

    def test_stale_context(self, stale_snapshot_dir):
        ctx = _build_context_in_dir("ipl", stale_snapshot_dir)
        assert ctx.status == "stale"
        assert ctx.stale is True
        assert ctx.freshness_label == "Stale"
        assert "stale" in ctx.status_banner.lower()


class TestNotReadyState:
    """T030: Not-ready rendering."""

    def test_not_ready_when_no_artifacts(self):
        from app import proof_page as pp_module

        original = {}
        for name in ["load_latest_summary", "load_latest_segments", "load_latest_ledger", "load_latest_manifest"]:
            original[name] = getattr(pp_module, name)

        def _fake_summary(**kw):
            return {"status": "not_ready", "probability_metrics": None, "accuracy_metrics": None, "freshness": {}, "definitions": {}, "window": None}

        def _fake_empty(**kw):
            return []

        pp_module.load_latest_summary = _fake_summary
        pp_module.load_latest_segments = _fake_empty
        pp_module.load_latest_ledger = _fake_empty
        pp_module.load_latest_manifest = _fake_summary

        try:
            ctx = pp_module.build_proof_page_context(league="missing")
        finally:
            for name, func in original.items():
                setattr(pp_module, name, func)

        assert ctx.status == "not_ready"
        assert len(ctx.summary_cards) >= 4
        for card in ctx.summary_cards:
            assert card.not_ready is True


class TestPartialState:
    """T031: Partial-state rendering."""

    def test_partial_when_accuracy_missing(self, partial_snapshot_dir):
        ctx = _build_context_in_dir("ipl", partial_snapshot_dir)
        assert ctx.status == "partial"
        assert len(ctx.status_banner) > 0

        accuracy_card = next((c for c in ctx.summary_cards if c.label == "Accuracy"), None)
        assert accuracy_card is not None
        assert accuracy_card.not_ready is True

        brier_card = next(c for c in ctx.summary_cards if c.label == "Brier Score")
        assert brier_card.not_ready is False
        assert brier_card.value is not None


class TestSegmentRendering:
    """T032: Segment rendering."""

    def test_innings_segments(self, proof_snapshot_dir):
        ctx = _build_context_in_dir("ipl", proof_snapshot_dir)
        innings_group = next((g for g in ctx.segments if g.segment_type == "innings"), None)
        assert innings_group is not None
        assert len(innings_group.rows) >= 2

    def test_phase_segments(self, proof_snapshot_dir):
        ctx = _build_context_in_dir("ipl", proof_snapshot_dir)
        phase_group = next((g for g in ctx.segments if g.segment_type == "phase"), None)
        assert phase_group is not None
        assert len(phase_group.rows) >= 1


class TestLedgerRendering:
    """T033: Ledger rendering."""

    def test_ledger_deterministic_order(self, proof_snapshot_dir):
        ctx = _build_context_in_dir("ipl", proof_snapshot_dir)
        assert ctx.ledger_rows[0].match == "MI vs CSK"
        assert ctx.ledger_rows[1].match == "RCB vs KKR"
        assert ctx.ledger_rows[2].match == "DC vs SRH"

    def test_ledger_correct_and_incorrect_badges(self, proof_snapshot_dir):
        ctx = _build_context_in_dir("ipl", proof_snapshot_dir)
        badges = [r.result_badge for r in ctx.ledger_rows]
        assert "correct" in badges
        assert "incorrect" in badges

    def test_ledger_max_rows_limited(self, tmp_path):
        d = tmp_path / "dashboard_metrics"
        d.mkdir(parents=True)
        (d / "latest").mkdir()
        many_rows = [{"match_label": f"Match {i}", "league": "ipl", "predicted_side": "A", "predicted_probability_pct": 50, "final_winner": "A", "result_status": "correct", "timestamp": "2026-06-01"} for i in range(100)]
        summary = {"league": "ipl", "window": "all_available", "status": "ready", "probability_metrics": {"brier": 0.2, "ece": 0.02, "sample_count": 100}, "accuracy_metrics": {"accuracy_pct": 60, "wins": 6, "losses": 4, "sample_count": 10}, "freshness": {"built_at": datetime.now(timezone.utc).isoformat(), "stale": False}, "definitions": {}}
        with open(d / "latest" / "ipl_summary.json", "w") as f:
            json.dump(summary, f)
        with open(d / "latest" / "ipl_segments.json", "w") as f:
            json.dump([], f)
        with open(d / "latest" / "ipl_ledger.json", "w") as f:
            json.dump(many_rows, f)
        with open(d / "latest" / "ipl_manifest.json", "w") as f:
            json.dump({"status": "ready"}, f)

        ctx = _build_context_in_dir("ipl", d)
        assert len(ctx.ledger_rows) == 20


class TestStatusLogic:
    """Test _derive_page_status combinatorics."""

    def _status(self, prob, acc, ledger, stale):
        from app.proof_page import _derive_page_status
        return _derive_page_status(prob, acc, ledger, stale)

    def test_all_ready(self):
        assert self._status(True, True, 3, False) == "ready"

    def test_all_missing(self):
        assert self._status(False, False, 0, False) == "not_ready"

    def test_stale_overrides_partial(self):
        assert self._status(True, False, 0, True) == "stale"

    def test_prob_only_is_partial(self):
        assert self._status(True, False, 0, False) == "partial"

    def test_acc_only_is_partial(self):
        assert self._status(False, True, 0, False) == "partial"

    def test_acc_with_ledger_but_no_prob_is_partial(self):
        assert self._status(False, True, 3, False) == "partial"

    def test_ledger_alone_is_partial(self):
        assert self._status(False, False, 5, False) == "partial"


class TestRouteRendering:
    """Route-level tests: render the actual proof template with context."""

    def _render_template(self, ctx):
        from jinja2 import Environment, FileSystemLoader
        from pathlib import Path

        template_dir = Path(__file__).resolve().parent.parent / "dashboard" / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("proof.html")
        return template.render(
            ctx=ctx,
            settings={},
            seo={
                "title": "Model Proof | CrickenZen",
                "description": "Test",
                "canonical": "/proof",
                "noindex": False,
            },
            request=None,
        )

    def test_proof_route_renders_html(self):
        from app.proof_page import build_proof_page_context

        ctx = build_proof_page_context(league="ipl")
        html = self._render_template(ctx)
        assert "CrickenZen" in html or "proof" in html.lower() or "Model Trust" in html

    def test_proof_template_renders_with_ready_context(self, proof_snapshot_dir):
        ctx = _build_context_in_dir("ipl", proof_snapshot_dir)
        assert ctx.status == "ready"
        html = self._render_template(ctx)
        assert "0.1831" in html
        assert "Brier Score" in html
        assert "ECE" in html

    def test_proof_template_shows_not_ready_cards(self):
        from app.proof_page import build_proof_page_context

        ctx = build_proof_page_context(league="missing")
        html = self._render_template(ctx)
        assert "Not ready" in html


class TestCTAPresence:
    """Verify proof CTAs exist in the public page templates."""

    def test_public_html_contains_proof_link(self):
        template_path = Path(__file__).resolve().parent.parent / "dashboard" / "templates" / "public.html"
        html = template_path.read_text()
        assert 'href="/proof"' in html

    def test_match_public_html_contains_proof_link(self):
        template_path = Path(__file__).resolve().parent.parent / "dashboard" / "templates" / "match_public.html"
        html = template_path.read_text()
        assert 'href="/proof"' in html

    def test_pages_py_has_proof_route(self):
        router_path = Path(__file__).resolve().parent.parent / "dashboard" / "app" / "routers" / "pages.py"
        source = router_path.read_text()
        assert '/proof' in source
        assert 'proof.html' in source
