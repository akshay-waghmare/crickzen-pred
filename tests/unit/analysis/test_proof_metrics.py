"""
Unit tests for canonical proof metrics builder.

Covers:
- Brier/ECE snapshot computation
- Innings and phase segmentation
- No-completed-data behavior
- Exclusion counting
- Accuracy summary computation
- Stale snapshot detection
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.bbl_pipeline.analysis.proof_metrics import (
    _compute_probability_metrics,
    _compute_segment_metrics,
    _derive_accuracy_from_states,
    _ece_histogram,
    _filter_by_window,
    _safe_float,
    build_accuracy_ledger,
    build_probability_snapshot,
    build_unified_snapshot,
    compute_accuracy_from_prematch_rows,
    METRIC_DEFINITIONS,
    ProbabilityMetricsSummary,
    SegmentMetricRow,
    ProofLedgerRow,
)


@pytest.fixture
def temp_states_dir(tmp_path):
    d = tmp_path / "match_states" / "test_league"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def sample_states_df():
    np.random.seed(42)
    n = 200
    df = pd.DataFrame(
        {
            "match_id": ["m1"] * 100 + ["m2"] * 100,
            "league": "test",
            "innings": [1] * 50 + [2] * 50 + [1] * 50 + [2] * 50,
            "over_number": np.tile(np.arange(1, 21), 10),
            "ball_in_over": np.tile([1, 2], 100),
            "batting_team": ["TeamA"] * 100 + ["TeamB"] * 100,
            "bowling_team": ["TeamB"] * 100 + ["TeamA"] * 100,
            "match_phase": ["powerplay"] * 60 + ["middle"] * 80 + ["death"] * 60,
            "model_final_prob": np.clip(0.5 + np.random.normal(0, 0.2, n), 0.01, 0.99),
            "timestamp": pd.date_range("2026-06-01", periods=n, freq="5min", tz="UTC"),
            "batting_team_tier": ["top"] * 80 + ["mid"] * 80 + ["bottom"] * 40,
        }
    )
    return df


@pytest.fixture
def sample_metadata():
    return pd.DataFrame(
        [
            {"match_id": "m1", "winner": "TeamA"},
            {"match_id": "m2", "winner": "TeamA"},
        ]
    )


@pytest.fixture
def sample_accuracy_rows():
    return [
        {
            "match": "TeamA vs TeamB",
            "pre_match_favorite": "TeamA",
            "winner": "TeamA",
            "win_probability_pct": 62,
            "confidence": "Medium (62%)",
            "what_changed": "TeamA chased comfortably.",
        },
        {
            "match": "TeamC vs TeamD",
            "pre_match_favorite": "TeamC",
            "winner": "TeamD",
            "win_probability_pct": 55,
            "confidence": "Low (55%)",
            "what_changed": "TeamD pulled an upset in the death overs.",
        },
        {
            "match": "TeamE vs TeamF",
            "pre_match_favorite": "TeamE",
            "winner": "TeamE",
            "win_probability_pct": 70,
        },
        # Missing predicted side — should be excluded
        {
            "match": "TeamG vs TeamH",
            "winner": "TeamG",
        },
        # Missing winner — should be excluded
        {
            "match": "TeamI vs TeamJ",
            "pre_match_favorite": "TeamI",
        },
    ]


class TestECEFunction:
    def test_perfect_calibration(self):
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0.1, 0.9, 0.1, 0.9])
        ece = _ece_histogram(y_true, y_pred, n_bins=5)
        assert ece < 0.1

    def test_worst_calibration(self):
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0.9, 0.1, 0.9, 0.1])
        ece = _ece_histogram(y_true, y_pred, n_bins=5)
        assert ece > 0.5

    def test_empty_input(self):
        ece = _ece_histogram(np.array([]), np.array([]), n_bins=10)
        assert ece == 0.0


class TestComputeProbabilityMetrics:
    def test_returns_metrics(self, sample_states_df):
        sample_states_df["actual_win"] = (sample_states_df["batting_team"] == "TeamA").astype(int)
        result = _compute_probability_metrics(sample_states_df)
        assert result.brier is not None
        assert result.ece is not None
        assert result.log_loss is not None
        assert result.sample_count == 200

    def test_empty_df(self):
        result = _compute_probability_metrics(pd.DataFrame())
        assert result.brier is None
        assert result.sample_count == 0


class TestComputeSegmentMetrics:
    def test_innings_segments(self, sample_states_df):
        sample_states_df["actual_win"] = 1
        segments = _compute_segment_metrics(sample_states_df)
        keys = [s.segment_key for s in segments if s.segment_type == "innings"]
        assert "innings_1" in keys
        assert "innings_2" in keys

    def test_phase_segments(self, sample_states_df):
        sample_states_df["actual_win"] = 1
        segments = _compute_segment_metrics(sample_states_df)
        phase_keys = [s.segment_key for s in segments if s.segment_type == "phase"]
        assert len(phase_keys) >= 1

    def test_team_tier_segments(self, sample_states_df):
        sample_states_df["actual_win"] = 1
        segments = _compute_segment_metrics(sample_states_df)
        tier_keys = [s.segment_key for s in segments if s.segment_type == "team_tier"]
        assert len(tier_keys) >= 1

    def test_empty_df(self):
        segments = _compute_segment_metrics(pd.DataFrame())
        assert segments == []


class TestFilterByWindow:
    def test_all_available(self, sample_states_df):
        result = _filter_by_window(sample_states_df, "all_available")
        assert len(result) == len(sample_states_df)

    def test_last_7_days(self, sample_states_df):
        recent = sample_states_df.copy()
        recent["timestamp"] = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=1)
        result = _filter_by_window(recent, "last_7_days")
        assert len(result) == len(recent)

    def test_old_data_excluded(self, sample_states_df):
        old = sample_states_df.copy()
        old["timestamp"] = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=90)
        result = _filter_by_window(old, "last_7_days")
        assert len(result) == 0

    def test_unknown_window_falls_back_to_all(self, sample_states_df):
        result = _filter_by_window(sample_states_df, "unknown_window")
        assert len(result) == len(sample_states_df)


class TestSafeFloat:
    def test_normal(self):
        assert _safe_float(3.14) == 3.14

    def test_nan(self):
        assert _safe_float(float("nan")) is None

    def test_inf(self):
        assert _safe_float(float("inf")) is None

    def test_none(self):
        assert _safe_float(None) is None


class TestBuildProbabilitySnapshot:
    def test_ready_status(self, tmp_path, sample_states_df, sample_metadata):
        states_path = tmp_path / "states.parquet"
        metadata_path = tmp_path / "metadata.parquet"
        sample_states_df.to_parquet(states_path, index=False)
        sample_metadata.to_parquet(metadata_path, index=False)

        result = build_probability_snapshot(
            states_path=states_path,
            metadata_path=metadata_path,
            league="test",
            window="all_available",
        )

        assert result["summary"]["status"] == "ready"
        assert result["summary"]["probability_metrics"]["sample_count"] > 0
        assert result["summary"]["probability_metrics"]["brier"] is not None
        assert result["summary"]["probability_metrics"]["ece"] is not None
        assert len(result["segments"]) > 0

    def test_not_ready_when_no_data(self, tmp_path):
        empty_df = pd.DataFrame(
            columns=["match_id", "batting_team", "model_final_prob", "innings", "match_phase"]
        )
        states_path = tmp_path / "empty.parquet"
        empty_df.to_parquet(states_path, index=False)

        metadata_path = tmp_path / "meta.parquet"
        pd.DataFrame(columns=["match_id", "winner"]).to_parquet(metadata_path, index=False)

        result = build_probability_snapshot(
            states_path=states_path,
            metadata_path=metadata_path,
            league="test",
            window="all_available",
        )

        assert result["summary"]["status"] == "not_ready"
        assert result["summary"]["probability_metrics"]["sample_count"] == 0

    def test_not_ready_when_states_path_missing(self):
        result = build_probability_snapshot(
            states_path=Path("/nonexistent/states.parquet"),
            metadata_path=Path("/nonexistent/metadata.parquet"),
            league="test",
        )
        assert result["status"] == "not_ready"
        assert "reason" in result

    def test_excludes_rows_without_winner(self, tmp_path, sample_states_df, sample_metadata):
        # Make half the winners None
        meta = sample_metadata.copy()
        meta.loc[1, "winner"] = None
        states_path = tmp_path / "states.parquet"
        meta_path = tmp_path / "meta.parquet"
        sample_states_df.to_parquet(states_path, index=False)
        meta.to_parquet(meta_path, index=False)

        result = build_probability_snapshot(
            states_path=states_path,
            metadata_path=meta_path,
            league="test",
            window="all_available",
        )
        manifest = result["manifest"]
        assert manifest["excluded_rows_total"] > 0

    def test_output_dir_writes_files(self, tmp_path, sample_states_df, sample_metadata):
        states_path = tmp_path / "states.parquet"
        meta_path = tmp_path / "meta.parquet"
        sample_states_df.to_parquet(states_path, index=False)
        sample_metadata.to_parquet(meta_path, index=False)

        out_dir = tmp_path / "out"
        build_probability_snapshot(
            states_path=states_path,
            metadata_path=meta_path,
            league="test",
            window="all_available",
            output_dir=out_dir,
        )

        assert (out_dir / "test_all_available_summary.json").exists()
        assert (out_dir / "test_all_available_segments.json").exists()
        assert (out_dir / "latest").exists()


class TestBuildAccuracyLedger:
    def test_computes_accuracy(self, sample_accuracy_rows):
        result = build_accuracy_ledger(sample_accuracy_rows, league="test", window="all_available")
        acc = result["accuracy_summary"]["accuracy_metrics"]
        assert acc["wins"] == 2
        assert acc["losses"] == 1
        assert acc["accuracy_pct"] == pytest.approx(66.7, abs=0.1)
        assert acc["excluded_rows"] == 2
        assert acc["sample_count"] == 3

    def test_returns_not_ready_when_no_valid_rows(self):
        result = build_accuracy_ledger([], league="test")
        assert result["accuracy_summary"]["status"] == "not_ready"
        assert result["accuracy_summary"]["accuracy_metrics"]["sample_count"] == 0

    def test_ledger_rows_have_required_fields(self, sample_accuracy_rows):
        result = build_accuracy_ledger(sample_accuracy_rows, league="test")
        ledger = result["ledger"]
        assert len(ledger) == 3
        for row in ledger:
            assert "match_label" in row
            assert "predicted_side" in row
            assert "final_winner" in row
            assert "result_status" in row
            assert row["result_status"] in ("correct", "incorrect")

    def test_output_dir_writes_files(self, tmp_path, sample_accuracy_rows):
        out_dir = tmp_path / "acc_out"
        build_accuracy_ledger(sample_accuracy_rows, league="test", window="all_available", output_dir=out_dir)
        assert (out_dir / "test_all_available_accuracy.json").exists()
        assert (out_dir / "test_all_available_ledger.json").exists()

    def test_window_filtering_excludes_old_rows(self):
        old_rows = [
            {
                "match": "OldMatch",
                "pre_match_favorite": "TeamA",
                "winner": "TeamA",
                "date": "2020-01-01",
            }
        ]
        result = build_accuracy_ledger(old_rows, league="test", window="last_7_days")
        acc = result["accuracy_summary"]["accuracy_metrics"]
        assert acc["sample_count"] == 0
        assert acc["excluded_rows"] == 1

    def test_window_filtering_keeps_recent_rows(self):
        recent_rows = [
            {
                "match": "RecentMatch",
                "pre_match_favorite": "TeamA",
                "winner": "TeamA",
                "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
            }
        ]
        result = build_accuracy_ledger(recent_rows, league="test", window="last_7_days")
        acc = result["accuracy_summary"]["accuracy_metrics"]
        assert acc["sample_count"] == 1

    def test_window_filtering_excludes_rows_with_no_timestamp(self):
        undated_row = [
            {
                "match": "UndatedMatch",
                "pre_match_favorite": "TeamA",
                "winner": "TeamA",
            }
        ]
        result = build_accuracy_ledger(undated_row, league="test", window="last_7_days")
        acc = result["accuracy_summary"]["accuracy_metrics"]
        assert acc["sample_count"] == 0
        assert acc["excluded_rows"] == 1


class TestDeriveAccuracyFromStates:
    def test_derives_from_sample_data(self, tmp_path, sample_states_df, sample_metadata):
        states_path = tmp_path / "states.parquet"
        meta_path = tmp_path / "meta.parquet"
        sample_states_df.to_parquet(states_path, index=False)
        sample_metadata.to_parquet(meta_path, index=False)

        rows = _derive_accuracy_from_states(states_path, meta_path, league="test")
        assert len(rows) > 0
        for row in rows:
            assert "match_id" in row
            assert "predicted_side" in row
            assert "winner" in row

    def test_returns_empty_when_states_missing(self, tmp_path):
        rows = _derive_accuracy_from_states(
            tmp_path / "nonexistent.parquet",
            tmp_path / "nonexistent.parquet",
            league="test",
        )
        assert rows == []

    def test_returns_empty_when_no_winner(self, tmp_path, sample_states_df):
        states_path = tmp_path / "states.parquet"
        meta_path = tmp_path / "meta.parquet"
        sample_states_df.to_parquet(states_path, index=False)
        bad_meta = pd.DataFrame([{"match_id": "m1", "winner": None}])
        bad_meta.to_parquet(meta_path, index=False)

        rows = _derive_accuracy_from_states(states_path, meta_path, league="test")
        assert rows == []

    def test_window_filtering_applied(self, tmp_path, sample_states_df, sample_metadata):
        states_path = tmp_path / "states.parquet"
        meta_path = tmp_path / "meta.parquet"
        # Make data 90 days old
        old_df = sample_states_df.copy()
        old_df["timestamp"] = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=90)
        old_df.to_parquet(states_path, index=False)
        sample_metadata.to_parquet(meta_path, index=False)

        rows_all = _derive_accuracy_from_states(states_path, meta_path, league="test", window="all_available")
        rows_7d = _derive_accuracy_from_states(states_path, meta_path, league="test", window="last_7_days")
        assert len(rows_all) > 0
        assert len(rows_7d) == 0


class TestBuildUnifiedSnapshot:
    def test_merges_probability_and_accuracy(self, tmp_path, sample_states_df, sample_metadata, sample_accuracy_rows):
        states_path = tmp_path / "states.parquet"
        meta_path = tmp_path / "meta.parquet"
        sample_states_df.to_parquet(states_path, index=False)
        sample_metadata.to_parquet(meta_path, index=False)

        result = build_unified_snapshot(
            states_path=states_path,
            metadata_path=meta_path,
            league="test",
            window="all_available",
            accuracy_rows=sample_accuracy_rows,
        )

        assert result["summary"]["status"] == "ready"
        assert result["summary"]["probability_metrics"] is not None
        assert result["summary"]["accuracy_metrics"] is not None
        assert result["summary"]["accuracy_metrics"]["wins"] >= 1
        assert len(result["ledger"]) > 0

    def test_accuracy_auto_derived_from_states(self, tmp_path, sample_states_df, sample_metadata):
        states_path = tmp_path / "states.parquet"
        meta_path = tmp_path / "meta.parquet"
        sample_states_df.to_parquet(states_path, index=False)
        sample_metadata.to_parquet(meta_path, index=False)

        result = build_unified_snapshot(
            states_path=states_path,
            metadata_path=meta_path,
            league="test",
            window="all_available",
        )

        assert result["summary"]["probability_metrics"]["brier"] is not None
        assert result["summary"]["accuracy_metrics"]["sample_count"] > 0
        assert len(result["ledger"]) > 0


class TestComputeAccuracyFromPrematchRows:
    def test_with_results_dict(self):
        prematch = [
            {"match_id": "m1", "pre_match_favorite": "TeamA", "win_probability_pct": 60},
            {"match_id": "m2", "pre_match_favorite": "TeamB", "win_probability_pct": 55},
        ]
        results = {"m1": "TeamA", "m2": "TeamA"}
        result = compute_accuracy_from_prematch_rows(prematch, results, league="test")
        acc = result["accuracy_summary"]["accuracy_metrics"]
        assert acc["wins"] == 1
        assert acc["losses"] == 1


class TestMetricDefinitions:
    def test_brier_present(self):
        assert "brier" in METRIC_DEFINITIONS
        assert "Lower is better" in METRIC_DEFINITIONS["brier"]

    def test_ece_present(self):
        assert "ece" in METRIC_DEFINITIONS
        assert "Lower is better" in METRIC_DEFINITIONS["ece"]

    def test_accuracy_present(self):
        assert "accuracy" in METRIC_DEFINITIONS
        assert "discrete" in METRIC_DEFINITIONS["accuracy"].lower()
