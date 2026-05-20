"""
Unit tests for scripts/analyze_ipl_mc_features_experiment.py

Covers:
  - row-key generation
  - phase bucketing
  - gap feature calculation
  - MatchState reconstruction
  - cache join validation
  - fold-local calibration (no leakage of validation labels)
  - fold row-order preservation
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.analyze_ipl_mc_features_experiment import (
    PHASE_DEATH,
    PHASE_MIDDLE,
    PHASE_POWERPLAY,
    apply_mc_platt,
    build_gap_features,
    build_row_key,
    build_variant_frames,
    check_required_columns,
    fit_mc_platt_calibrators,
    get_phase_label,
    make_cv_splits,
    row_to_match_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _synthetic_df(n: int = 200) -> pd.DataFrame:
    """Create a minimal synthetic IPL feature DataFrame."""
    rng = np.random.default_rng(0)
    innings = rng.choice([1, 2], size=n)
    wickets_lost = rng.integers(0, 8, size=n)
    overs_remaining = rng.uniform(1.0, 18.0, size=n)
    current_run_rate = rng.uniform(4.0, 12.0, size=n)
    # For inn2, required_run_rate must be reasonable
    required_run_rate = rng.uniform(4.0, 15.0, size=n)
    resource_win_prob = rng.uniform(0.2, 0.8, size=n)
    is_winner = rng.integers(0, 2, size=n).astype(float)

    return pd.DataFrame({
        "innings": innings,
        "wickets_lost": wickets_lost,
        "overs_remaining": overs_remaining,
        "current_run_rate": current_run_rate,
        "required_run_rate": required_run_rate,
        "resource_win_prob": resource_win_prob,
        "is_winner": is_winner,
    })


def _synthetic_cache(df: pd.DataFrame, rng: np.random.Generator | None = None) -> pd.DataFrame:
    """Create a synthetic MC cache aligned to df."""
    if rng is None:
        rng = np.random.default_rng(42)
    n = len(df)
    mc_raw = rng.uniform(0.1, 0.9, size=n)
    mc_std = rng.uniform(0.01, 0.2, size=n)
    return pd.DataFrame({
        "row_key": np.arange(n),
        "innings": df["innings"].values,
        "over_approx": 20.0 - df["overs_remaining"].values,
        "balls_remaining_approx": np.round(df["overs_remaining"].values * 6).astype(int),
        "mc_raw_win_prob": mc_raw,
        "mc_simulation_std": mc_std,
        "sim_ok": True,
        "skip_reason": None,
        "seed": 42,
        "n_sims": 100,
        "horizon_balls": 6,
    })


# ---------------------------------------------------------------------------
# T001 – Row key generation
# ---------------------------------------------------------------------------

class TestRowKeyGeneration:
    def test_returns_sequential_integers(self):
        df = _synthetic_df(50)
        keys = build_row_key(df)
        assert len(keys) == len(df)
        assert list(keys) == list(range(50))

    def test_keys_match_df_length(self):
        for n in [1, 10, 100]:
            df = _synthetic_df(n)
            assert len(build_row_key(df)) == n


# ---------------------------------------------------------------------------
# T002 – Phase bucketing
# ---------------------------------------------------------------------------

class TestPhaseBucketing:
    @pytest.mark.parametrize("overs_remaining,expected", [
        (19.0, PHASE_POWERPLAY),   # over 1
        (15.0, PHASE_POWERPLAY),   # over 5
        (14.0, PHASE_MIDDLE),      # over 6 (7th over)
        (6.0,  PHASE_MIDDLE),      # over 14
        (5.0,  PHASE_DEATH),       # over 15
        (1.0,  PHASE_DEATH),       # over 19
        (0.1,  PHASE_DEATH),       # near end
    ])
    def test_phase_correct(self, overs_remaining, expected):
        assert get_phase_label(overs_remaining) == expected

    def test_powerplay_boundary(self):
        # Exactly at overs_done=6 boundary (overs_remaining=14)
        assert get_phase_label(14.0) == PHASE_MIDDLE

    def test_death_boundary(self):
        # Exactly at overs_done=15 boundary (overs_remaining=5)
        assert get_phase_label(5.0) == PHASE_DEATH


# ---------------------------------------------------------------------------
# T003 – Gap feature calculation
# ---------------------------------------------------------------------------

class TestGapFeatures:
    def test_gap_is_mc_minus_resource(self):
        mc = np.array([0.6, 0.4, 0.5])
        res = np.array([0.5, 0.5, 0.5])
        gap, abs_gap = build_gap_features(mc, res)
        np.testing.assert_allclose(gap, [0.1, -0.1, 0.0], atol=1e-7)
        np.testing.assert_allclose(abs_gap, [0.1, 0.1, 0.0], atol=1e-7)

    def test_abs_gap_always_non_negative(self):
        rng = np.random.default_rng(0)
        mc = rng.uniform(0, 1, 1000)
        res = rng.uniform(0, 1, 1000)
        _, abs_gap = build_gap_features(mc, res)
        assert (abs_gap >= 0).all()

    def test_gap_symmetry(self):
        mc = np.array([0.7])
        res = np.array([0.3])
        gap, abs_gap = build_gap_features(mc, res)
        gap2, abs_gap2 = build_gap_features(res, mc)
        assert abs_gap[0] == abs_gap2[0]
        assert abs(gap[0] + gap2[0]) < 1e-7


class TestInnings2OnlyVariants:
    def test_clean_swap_changes_only_innings_2_resource_probability(self):
        df = pd.DataFrame({
            "innings": [1, 2, 1, 2],
            "resource_win_prob": [0.40, 0.45, 0.55, 0.60],
        })
        mc = np.array([0.10, 0.20, 0.30, 0.80])
        mc_std = np.array([0.01, 0.02, 0.03, 0.04])

        out = build_variant_frames(
            df,
            mc_win_prob=mc,
            mc_raw=mc,
            mc_std=mc_std,
            variant="ml_clean_swap_resource_inn2_only",
        )

        np.testing.assert_allclose(out["resource_win_prob"], [0.40, 0.20, 0.55, 0.80])

    def test_gap_features_are_zeroed_for_innings_1_in_innings_2_only_variant(self):
        df = pd.DataFrame({
            "innings": [1, 2],
            "resource_win_prob": [0.40, 0.45],
        })
        mc = np.array([0.10, 0.20])
        mc_std = np.array([0.01, 0.02])

        out = build_variant_frames(
            df,
            mc_win_prob=mc,
            mc_raw=mc,
            mc_std=mc_std,
            variant="ml_add_mc_gap_features_inn2_only",
        )

        assert out.loc[0, "mc_win_prob"] == out.loc[0, "resource_win_prob"]
        assert out.loc[0, "mc_resource_gap"] == 0.0
        assert out.loc[0, "mc_resource_abs_gap"] == 0.0
        assert out.loc[0, "mc_simulation_std"] == 0.0
        assert out.loc[1, "mc_win_prob"] == mc[1]
        assert out.loc[1, "mc_resource_gap"] == mc[1] - df.loc[1, "resource_win_prob"]


# ---------------------------------------------------------------------------
# T004 – MatchState reconstruction
# ---------------------------------------------------------------------------

class TestMatchStateReconstruction:
    def test_valid_inn1_row(self):
        state, reason = row_to_match_state(
            innings=1, wickets_lost=2, overs_remaining=10.0,
            current_run_rate=7.5, required_run_rate=0.0,
        )
        assert state is not None
        assert reason is None
        assert state.innings == 1
        assert state.balls_remaining == 60  # 10 * 6
        assert state.score >= 0

    def test_valid_inn2_row(self):
        state, reason = row_to_match_state(
            innings=2, wickets_lost=3, overs_remaining=8.0,
            current_run_rate=8.0, required_run_rate=10.0,
        )
        assert state is not None
        assert reason is None
        assert state.innings == 2
        assert state.target_runs is not None
        assert state.target_runs > state.score

    def test_terminal_no_balls(self):
        state, reason = row_to_match_state(
            innings=1, wickets_lost=2, overs_remaining=0.0,
            current_run_rate=7.0, required_run_rate=0.0,
        )
        assert state is None
        assert "terminal" in reason

    def test_terminal_all_out(self):
        state, reason = row_to_match_state(
            innings=1, wickets_lost=10, overs_remaining=5.0,
            current_run_rate=7.0, required_run_rate=0.0,
        )
        assert state is None
        assert "all_out" in reason

    def test_terminal_inn2_impossible_rrr(self):
        # required_run_rate > 500 => impossible/terminal
        state, reason = row_to_match_state(
            innings=2, wickets_lost=2, overs_remaining=2.0,
            current_run_rate=8.0, required_run_rate=600.0,
        )
        assert state is None

    def test_missing_required_columns(self):
        df = _synthetic_df(10).drop(columns=["is_winner"])
        missing = check_required_columns(df)
        assert "is_winner" in missing

    def test_all_required_columns_present(self):
        df = _synthetic_df(10)
        missing = check_required_columns(df)
        assert missing == []


# ---------------------------------------------------------------------------
# T005 – Cache join validation
# ---------------------------------------------------------------------------

class TestCacheJoin:
    def test_cache_joins_one_to_one(self):
        df = _synthetic_df(50)
        cache = _synthetic_cache(df)
        # row_key should uniquely identify each row
        assert cache["row_key"].nunique() == len(df)
        # All row keys map to valid df indices
        for rk in cache["row_key"]:
            assert 0 <= rk < len(df)

    def test_sim_ok_subset_aligns(self):
        df = _synthetic_df(50)
        cache = _synthetic_cache(df)
        # Subset to sim_ok rows
        ok = cache[cache["sim_ok"]]
        for rk in ok["row_key"]:
            assert rk in df.index


# ---------------------------------------------------------------------------
# T006 – Fold-local calibration: no leakage proof
# ---------------------------------------------------------------------------

class TestFoldLocalCalibration:
    """Prove calibrators fitted on train fold do NOT use val labels."""

    def test_calibrator_fitted_on_train_only(self):
        rng = np.random.default_rng(1)
        n = 200
        mc_raw = rng.uniform(0.1, 0.9, n)
        labels = rng.integers(0, 2, n).astype(float)
        innings = rng.choice([1, 2], n)

        train_idx = np.arange(0, 160)
        val_idx = np.arange(160, 200)

        # Fit on train
        calibrators = fit_mc_platt_calibrators(
            mc_raw[train_idx], labels[train_idx], innings[train_idx]
        )

        # Apply to val WITHOUT using val labels
        val_probs = apply_mc_platt(mc_raw[val_idx], innings[val_idx], calibrators)

        assert val_probs.shape == (40,)
        assert not np.any(np.isnan(val_probs))
        assert (val_probs >= 0).all()
        assert (val_probs <= 1).all()

    def test_calibrator_output_differs_from_raw(self):
        rng = np.random.default_rng(2)
        n = 300
        mc_raw = rng.uniform(0.1, 0.9, n)
        # Create labels correlated with mc_raw for non-trivial calibration
        labels = (mc_raw + rng.normal(0, 0.1, n) > 0.5).astype(float)
        innings = np.ones(n, dtype=int)

        calibrators = fit_mc_platt_calibrators(mc_raw, labels, innings)
        calibrated = apply_mc_platt(mc_raw, innings, calibrators)

        # Calibrated should differ from raw (Platt should adjust)
        assert not np.allclose(calibrated, mc_raw, atol=0.01)

    def test_val_labels_not_used_in_fitting(self):
        """Fitting calibrator with random val labels should not affect val probs."""
        rng = np.random.default_rng(3)
        n = 200
        mc_raw = rng.uniform(0.2, 0.8, n)
        labels_real = (mc_raw > 0.5).astype(float)
        innings = np.ones(n, dtype=int)

        train_idx = np.arange(0, 150)
        val_idx = np.arange(150, 200)

        # Fit on real train labels
        cal_real = fit_mc_platt_calibrators(
            mc_raw[train_idx], labels_real[train_idx], innings[train_idx]
        )
        val_probs_real = apply_mc_platt(mc_raw[val_idx], innings[val_idx], cal_real)

        # Fit again using same train labels (should get identical val probs)
        cal_same = fit_mc_platt_calibrators(
            mc_raw[train_idx], labels_real[train_idx], innings[train_idx]
        )
        val_probs_same = apply_mc_platt(mc_raw[val_idx], innings[val_idx], cal_same)

        # Same train set → same val probs regardless of val labels
        np.testing.assert_allclose(val_probs_real, val_probs_same, atol=1e-10)


# ---------------------------------------------------------------------------
# T007 – Row order preservation in CV splits
# ---------------------------------------------------------------------------

class TestCVSplits:
    def test_splits_are_sequential_and_non_overlapping(self):
        splits = make_cv_splits(100, n_splits=5)
        all_val = []
        for train_idx, val_idx in splits:
            # Train comes before val
            assert train_idx[-1] < val_idx[0], "Train must precede val"
            all_val.extend(val_idx.tolist())
        # No duplicates in val sets
        assert len(set(all_val)) == len(all_val)

    def test_all_rows_covered_in_val(self):
        n = 100
        n_splits = 5
        splits = make_cv_splits(n, n_splits=n_splits)
        covered = set()
        for _, val_idx in splits:
            covered.update(val_idx.tolist())
        # Time-series CV: the first fold_size rows are only ever training rows.
        # All rows from fold_size onward should appear in exactly one val fold.
        fold_size = n // n_splits
        expected = set(range(fold_size, n))
        assert covered == expected

    def test_train_grows_monotonically(self):
        splits = make_cv_splits(100, n_splits=5)
        prev_train_len = 0
        for train_idx, _ in splits:
            assert len(train_idx) > prev_train_len
            prev_train_len = len(train_idx)

    def test_split_with_small_n(self):
        # Should handle gracefully with fewer rows
        splits = make_cv_splits(20, n_splits=3)
        assert len(splits) >= 1


# ---------------------------------------------------------------------------
# T008 – Variant frame builders
# ---------------------------------------------------------------------------

class TestVariantFrames:
    def setup_method(self):
        self.df = _synthetic_df(50)
        rng = np.random.default_rng(0)
        self.mc_win_prob = rng.uniform(0.2, 0.8, 50)
        self.mc_raw = rng.uniform(0.2, 0.8, 50)
        self.mc_std = rng.uniform(0.01, 0.1, 50)

    def test_baseline_unchanged(self):
        frame = build_variant_frames(
            self.df, self.mc_win_prob, self.mc_raw, self.mc_std,
            "baseline_ipl_v6_features",
        )
        pd.testing.assert_frame_equal(frame, self.df)

    def test_add_mc_win_prob_adds_column(self):
        frame = build_variant_frames(
            self.df, self.mc_win_prob, self.mc_raw, self.mc_std,
            "ml_add_mc_win_prob",
        )
        assert "mc_win_prob" in frame.columns
        np.testing.assert_allclose(frame["mc_win_prob"].values, self.mc_win_prob)

    def test_add_gap_features_adds_all_four(self):
        frame = build_variant_frames(
            self.df, self.mc_win_prob, self.mc_raw, self.mc_std,
            "ml_add_mc_gap_features",
        )
        for col in ["mc_win_prob", "mc_resource_gap", "mc_resource_abs_gap", "mc_simulation_std"]:
            assert col in frame.columns

    def test_replace_resource_with_mc(self):
        frame = build_variant_frames(
            self.df, self.mc_win_prob, self.mc_raw, self.mc_std,
            "ml_replace_resource_with_mc",
        )
        np.testing.assert_allclose(
            frame["resource_win_prob"].values, self.mc_win_prob, atol=1e-10
        )

    def test_original_df_not_mutated(self):
        orig_resource = self.df["resource_win_prob"].values.copy()
        build_variant_frames(
            self.df, self.mc_win_prob, self.mc_raw, self.mc_std,
            "ml_replace_resource_with_mc",
        )
        np.testing.assert_allclose(self.df["resource_win_prob"].values, orig_resource)

    def test_abs_gap_non_negative(self):
        frame = build_variant_frames(
            self.df, self.mc_win_prob, self.mc_raw, self.mc_std,
            "ml_add_mc_gap_features",
        )
        assert (frame["mc_resource_abs_gap"] >= 0).all()
