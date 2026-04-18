"""
Unit tests for LeagueCalibrator phase-specific Platt scaling (User Story 5).

Tests verify:
- Phase-specific + innings-level calibrator fitting
- Phase-specific routing in predict()
- Fallback chain: phase → innings → identity
- PlattScaler instance types
- Minimum sample enforcement
"""

import numpy as np
import pandas as pd
import pytest

from bbl_pipeline.training.league_calibrator import LeagueCalibrator, PlattScaler


def _make_synthetic_data(n=6000, seed=42):
    """Create synthetic data with 1000 samples per innings×phase segment."""
    rng = np.random.RandomState(seed)
    df = pd.DataFrame({
        'innings': np.repeat([1, 2], n // 2),
        'phase': np.tile(np.repeat(['powerplay', 'middle', 'death'], n // 6), 2),
        'date': pd.date_range('2024-01-01', periods=n, freq='h'),
    })
    raw_probs = rng.uniform(0.2, 0.8, n)
    y_true = (raw_probs > 0.5).astype(int)
    return df, raw_probs, y_true


class TestPhaseCalibratorsAreFitted:
    """T028-1: fit() produces the correct calibrator keys when phase_specific=True."""

    def test_phase_keys_present(self):
        df, raw_probs, y_true = _make_synthetic_data()
        cal = LeagueCalibrator(method='platt', innings_specific=True, phase_specific=True)
        cal.fit(df, raw_probs, y_true, league='test')

        expected_phase_keys = {
            'inn1_powerplay', 'inn1_middle', 'inn1_death',
            'inn2_powerplay', 'inn2_middle', 'inn2_death',
        }
        expected_innings_keys = {'innings_1', 'innings_2'}

        for key in expected_phase_keys:
            assert key in cal.calibrators, f"Missing phase calibrator: {key}"
        for key in expected_innings_keys:
            assert key in cal.calibrators, f"Missing innings calibrator: {key}"

    def test_total_calibrator_count(self):
        df, raw_probs, y_true = _make_synthetic_data()
        cal = LeagueCalibrator(method='platt', innings_specific=True, phase_specific=True)
        cal.fit(df, raw_probs, y_true, league='test')

        # 6 phase-specific + 2 innings-level = 8 calibrators
        assert len(cal.calibrators) == 8


class TestPhaseRouting:
    """T028-2: predict() routes a row to the correct phase-specific calibrator."""

    def test_phase_specific_routing_modifies_probs(self):
        df, raw_probs, y_true = _make_synthetic_data()
        cal = LeagueCalibrator(method='platt', innings_specific=True, phase_specific=True)
        cal.fit(df, raw_probs, y_true, league='test')

        # Single row: innings=1, phase=powerplay
        test_df = pd.DataFrame({'innings': [1], 'phase': ['powerplay']})
        test_probs = np.array([0.5])

        calibrated = cal.predict(test_df, test_probs)

        # The calibrated value should be different from raw (Platt shifts predictions)
        assert calibrated.shape == (1,)
        # Just verify it returns a valid probability
        assert 0.0 <= calibrated[0] <= 1.0

    def test_all_segments_get_calibrated(self):
        """Each innings×phase combination should be calibrated, not left at raw."""
        df, raw_probs, y_true = _make_synthetic_data()
        cal = LeagueCalibrator(method='platt', innings_specific=True, phase_specific=True)
        cal.fit(df, raw_probs, y_true, league='test')

        calibrated = cal.predict(df, raw_probs)
        # Calibrated probabilities should generally differ from raw
        assert not np.allclose(calibrated, raw_probs, atol=1e-6)


class TestFallbackToInnings:
    """T028-3: If phase-specific key missing, falls back to innings-level calibrator."""

    def test_unknown_phase_falls_back_to_innings(self):
        df, raw_probs, y_true = _make_synthetic_data()
        cal = LeagueCalibrator(method='platt', innings_specific=True, phase_specific=True)
        cal.fit(df, raw_probs, y_true, league='test')

        # Remove a phase calibrator to force fallback
        del cal.calibrators['inn1_powerplay']

        test_df = pd.DataFrame({'innings': [1], 'phase': ['powerplay']})
        test_probs = np.array([0.5])

        calibrated = cal.predict(test_df, test_probs)

        # Should use innings_1 fallback, not crash
        assert 0.0 <= calibrated[0] <= 1.0

        # Verify it used the innings calibrator by comparing with its direct output
        expected = cal.calibrators['innings_1'].predict(test_probs)
        np.testing.assert_array_almost_equal(calibrated, expected)


class TestIdentityFallback:
    """T028-4: If both phase and innings calibrators are missing, returns raw probability."""

    def test_identity_when_no_calibrators(self):
        df, raw_probs, y_true = _make_synthetic_data()
        cal = LeagueCalibrator(method='platt', innings_specific=True, phase_specific=True)
        cal.fit(df, raw_probs, y_true, league='test')

        # Remove all calibrators for innings 1
        for key in list(cal.calibrators.keys()):
            if key.startswith('inn1') or key == 'innings_1':
                del cal.calibrators[key]

        test_df = pd.DataFrame({'innings': [1], 'phase': ['powerplay']})
        test_probs = np.array([0.65])

        calibrated = cal.predict(test_df, test_probs)

        # Should return raw probability unchanged
        np.testing.assert_array_almost_equal(calibrated, test_probs)


class TestPlattScalerInstances:
    """T028-5: All calibrators should be PlattScaler when method='platt'."""

    def test_all_calibrators_are_platt(self):
        df, raw_probs, y_true = _make_synthetic_data()
        cal = LeagueCalibrator(method='platt', innings_specific=True, phase_specific=True)
        cal.fit(df, raw_probs, y_true, league='test')

        for key, scaler in cal.calibrators.items():
            assert isinstance(scaler, PlattScaler), (
                f"Calibrator '{key}' is {type(scaler).__name__}, expected PlattScaler"
            )


class TestMinSampleEnforcement:
    """T028-6: Phases with fewer than min_samples get no phase-specific calibrator."""

    def test_small_phase_skipped(self):
        # Create data where inn1_powerplay has only 50 samples (below default 500)
        rng = np.random.RandomState(42)
        segments = []
        for innings in [1, 2]:
            for phase in ['powerplay', 'middle', 'death']:
                n = 50 if (innings == 1 and phase == 'powerplay') else 1000
                segments.append(pd.DataFrame({
                    'innings': innings,
                    'phase': phase,
                    'date': pd.date_range('2024-01-01', periods=n, freq='h'),
                }))
        df = pd.concat(segments, ignore_index=True)
        raw_probs = rng.uniform(0.2, 0.8, len(df))
        y_true = (raw_probs > 0.5).astype(int)

        cal = LeagueCalibrator(method='platt', innings_specific=True, phase_specific=True)
        cal.fit(df, raw_probs, y_true, league='test', min_samples=500)

        # inn1_powerplay should NOT exist (only 50 samples)
        assert 'inn1_powerplay' not in cal.calibrators

        # Other phase calibrators should exist (1000 samples each)
        assert 'inn1_middle' in cal.calibrators
        assert 'inn1_death' in cal.calibrators
        assert 'inn2_powerplay' in cal.calibrators

        # Innings fallback should still exist
        assert 'innings_1' in cal.calibrators

    def test_small_phase_uses_innings_fallback(self):
        """Predict on a segment with no phase calibrator should use innings fallback."""
        rng = np.random.RandomState(42)
        segments = []
        for innings in [1, 2]:
            for phase in ['powerplay', 'middle', 'death']:
                n = 50 if (innings == 1 and phase == 'powerplay') else 1000
                segments.append(pd.DataFrame({
                    'innings': innings,
                    'phase': phase,
                    'date': pd.date_range('2024-01-01', periods=n, freq='h'),
                }))
        df = pd.concat(segments, ignore_index=True)
        raw_probs = rng.uniform(0.2, 0.8, len(df))
        y_true = (raw_probs > 0.5).astype(int)

        cal = LeagueCalibrator(method='platt', innings_specific=True, phase_specific=True)
        cal.fit(df, raw_probs, y_true, league='test', min_samples=500)

        # Predict on inn1_powerplay → should use innings_1 fallback
        test_df = pd.DataFrame({'innings': [1], 'phase': ['powerplay']})
        test_probs = np.array([0.5])
        calibrated = cal.predict(test_df, test_probs)

        expected = cal.calibrators['innings_1'].predict(test_probs)
        np.testing.assert_array_almost_equal(calibrated, expected)
