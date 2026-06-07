"""
Contract and loader tests for dashboard proof metrics.

Validates:
- Dashboard loader reads snapshot artifacts correctly
- Proof API endpoints return expected payloads
- Not-ready states are returned when artifacts are missing
- Stale snapshots are detected
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest


@pytest.fixture
def snapshot_dir(tmp_path):
    d = tmp_path / "dashboard_metrics"
    d.mkdir(parents=True)
    (d / "latest").mkdir()
    (d / "windows").mkdir()

    summary = {
        "league": "test",
        "window": "all_available",
        "status": "ready",
        "probability_metrics": {
            "brier": 0.1831,
            "ece": 0.0124,
            "log_loss": 0.5812,
            "sample_count": 18240,
            "excluded_rows": 0,
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
        "definitions": {
            "brier": "Lower is better. Measures probability error.",
            "ece": "Lower is better. Measures calibration gap.",
            "accuracy": "Higher is better. Measures discrete call hit rate.",
        },
    }

    segments = [
        {
            "segment_type": "innings",
            "segment_key": "innings_1",
            "segment_label": "Innings 1",
            "brier": 0.175,
            "ece": 0.01,
            "log_loss": 0.56,
            "sample_count": 9000,
        },
        {
            "segment_type": "phase",
            "segment_key": "phase_powerplay",
            "segment_label": "Powerplay",
            "brier": 0.19,
            "ece": 0.015,
            "log_loss": 0.60,
            "sample_count": 4000,
        },
    ]

    ledger = [
        {
            "match_label": "TeamA vs TeamB",
            "league": "test",
            "timestamp": "2026-06-01T12:00:00+00:00",
            "predicted_side": "TeamA",
            "predicted_probability_pct": 62.0,
            "confidence_band": "Medium",
            "final_winner": "TeamA",
            "result_status": "correct",
            "what_changed": "Comfortable chase.",
            "source_note": None,
        },
    ]

    manifest = {
        "build_version": 1,
        "league": "test",
        "evaluation_window": "all_available",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
    }

    for name, data in [
        ("test_summary.json", summary),
        ("test_segments.json", segments),
        ("test_ledger.json", ledger),
        ("test_manifest.json", manifest),
    ]:
        with open(d / "latest" / name, "w") as f:
            json.dump(data, f)

    return d


class TestDashboardLoader:
    def test_load_latest_summary_returns_payload(self, snapshot_dir):
        from app.proof_metrics import load_latest_summary

        result = load_latest_summary(league="test", snapshot_dir=snapshot_dir)
        assert result["status"] == "ready"
        assert result["probability_metrics"]["brier"] == 0.1831
        assert result["accuracy_metrics"]["wins"] == 24

    def test_load_latest_summary_not_ready_when_missing(self, tmp_path):
        from app.proof_metrics import load_latest_summary

        result = load_latest_summary(league="missing_league", snapshot_dir=tmp_path)
        assert result["status"] == "not_ready"
        assert result["probability_metrics"] is None

    def test_load_latest_segments(self, snapshot_dir):
        from app.proof_metrics import load_latest_segments

        result = load_latest_segments(league="test", snapshot_dir=snapshot_dir)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_load_latest_segments_empty_when_missing(self, tmp_path):
        from app.proof_metrics import load_latest_segments

        result = load_latest_segments(league="missing_league", snapshot_dir=tmp_path)
        assert result == []

    def test_load_latest_ledger(self, snapshot_dir):
        from app.proof_metrics import load_latest_ledger

        result = load_latest_ledger(league="test", snapshot_dir=snapshot_dir)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["result_status"] == "correct"

    def test_load_latest_ledger_empty_when_missing(self, tmp_path):
        from app.proof_metrics import load_latest_ledger

        result = load_latest_ledger(league="missing_league", snapshot_dir=tmp_path)
        assert result == []

    def test_load_latest_manifest(self, snapshot_dir):
        from app.proof_metrics import load_latest_manifest

        result = load_latest_manifest(league="test", snapshot_dir=snapshot_dir)
        assert result["status"] == "ready"
        assert result["build_version"] == 1

    def test_load_latest_manifest_not_ready_when_missing(self, tmp_path):
        from app.proof_metrics import load_latest_manifest

        result = load_latest_manifest(league="missing_league", snapshot_dir=tmp_path)
        assert result["status"] == "not_ready"

    def test_stale_detection(self, snapshot_dir):
        from app.proof_metrics import load_latest_summary

        stale_summary = {
            "league": "test",
            "window": "all_available",
            "status": "ready",
            "probability_metrics": {"brier": 0.2, "ece": 0.02, "sample_count": 100},
            "accuracy_metrics": None,
            "freshness": {
                "built_at": "2020-01-01T00:00:00+00:00",
                "stale": False,
            },
            "definitions": {},
        }
        with open(snapshot_dir / "latest" / "test_summary.json", "w") as f:
            json.dump(stale_summary, f)

        result = load_latest_summary(league="test", snapshot_dir=snapshot_dir)
        assert result["freshness"]["stale"] is True

    def test_accuracy_summary(self, snapshot_dir):
        from app.proof_metrics import load_accuracy_summary

        acc_data = {
            "league": "test",
            "window": "all_available",
            "status": "ready",
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
        with open(snapshot_dir / "latest" / "test_accuracy.json", "w") as f:
            json.dump(acc_data, f)

        result = load_accuracy_summary(league="test", snapshot_dir=snapshot_dir)
        assert result["accuracy_metrics"]["wins"] == 24

    def test_accuracy_summary_not_ready_when_missing(self, tmp_path):
        from app.proof_metrics import load_accuracy_summary

        result = load_accuracy_summary(league="missing_league", snapshot_dir=tmp_path)
        assert result["status"] == "not_ready"


@pytest.fixture
def proof_client():
    try:
        from app.main import create_app
        from app.config import Settings
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("FastAPI or app dependencies not available")

    settings = Settings(
        JWT_SECRET="test-secret-key-for-testing-only",
        DOMAIN="localhost",
        ADMIN_EMAIL="admin@test.com",
        ADMIN_PASSWORD="testpassword123",
        DATABASE_URL="sqlite://",
        SESSION_CAP=50,
        MAX_USER_MATCHES=2,
        MAX_TOTAL_MATCHES=6,
        AUTO_PREDICTIONS_ENABLED=False,
        REGISTRATION_OPEN=True,
    )
    app = create_app(settings_override=settings)
    with TestClient(app) as c:
        yield c


class TestProofAPIEndpoints:
    def test_summary_endpoint(self, proof_client):
        resp = proof_client.get("/api/proof/summary?league=ipl")
        assert resp.status_code in (200, 404)
        data = resp.json()
        assert "status" in data

    def test_segments_endpoint(self, proof_client):
        resp = proof_client.get("/api/proof/segments?league=ipl")
        assert resp.status_code in (200, 404)
        data = resp.json()
        assert "segments" in data or "detail" in data

    def test_ledger_endpoint(self, proof_client):
        resp = proof_client.get("/api/proof/ledger?league=ipl")
        assert resp.status_code in (200, 404)
        data = resp.json()
        assert "ledger" in data or "detail" in data

    def test_manifest_endpoint(self, proof_client):
        resp = proof_client.get("/api/proof/manifest?league=ipl")
        assert resp.status_code in (200, 404)
        data = resp.json()
        assert "status" in data

    def test_summary_default_league(self, proof_client):
        resp = proof_client.get("/api/proof/summary")
        assert resp.status_code in (200, 404)
        data = resp.json()
        assert "status" in data

    def test_not_ready_response_when_no_snapshots(self, proof_client):
        resp = proof_client.get("/api/proof/summary?league=unknown_league_xyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_ready"
        assert data["probability_metrics"] is None


class TestProofPayloadStructure:
    def test_summary_contract_shape(self, snapshot_dir):
        from app.proof_metrics import load_latest_summary

        result = load_latest_summary(league="test", snapshot_dir=snapshot_dir)
        assert "league" in result
        assert "window" in result
        assert "status" in result
        assert "probability_metrics" in result
        assert "accuracy_metrics" in result
        assert "freshness" in result
        assert "definitions" in result

    def test_summary_has_separate_metric_families(self, snapshot_dir):
        from app.proof_metrics import load_latest_summary

        result = load_latest_summary(league="test", snapshot_dir=snapshot_dir)
        prob = result["probability_metrics"]
        acc = result["accuracy_metrics"]
        assert "brier" in prob
        assert "ece" in prob
        assert "wins" in acc
        assert "losses" in acc
        assert "accuracy_pct" in acc

    def test_segments_sorted_contract(self, snapshot_dir):
        from app.proof_metrics import load_latest_segments

        result = load_latest_segments(league="test", snapshot_dir=snapshot_dir)
        for seg in result:
            assert "segment_type" in seg
            assert "segment_key" in seg
            assert "segment_label" in seg
            assert "sample_count" in seg

    def test_ledger_contract_shape(self, snapshot_dir):
        from app.proof_metrics import load_latest_ledger

        result = load_latest_ledger(league="test", snapshot_dir=snapshot_dir)
        for row in result:
            assert "match_label" in row
            assert "predicted_side" in row
            assert "final_winner" in row
            assert "result_status" in row
