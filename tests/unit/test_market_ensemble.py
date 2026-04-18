"""
Unit tests for blend_predictions() market ensemble blending.

Tests cover:
- Model-only fallback (no market data, stale data, invalid data)
- Valid ensemble blending
- Clamping to [0.001, 0.999]
- Pure market mode (alpha=0.0) and pure model mode (alpha=1.0)
- Invalid market_prob values
- FR-012: function NEVER raises exceptions
"""

import math
import pytest

from bbl_pipeline.inference.crex_live_predictor import blend_predictions


class TestBlendPredictionsModelOnly:
    """Tests where blend_predictions should return model_only."""

    def test_market_prob_none(self):
        """Returns (model_prob, 'model_only') when market_prob is None."""
        prob, source = blend_predictions(0.65, None, 10.0, alpha=0.5)
        assert prob == pytest.approx(0.65, abs=1e-6)
        assert source == "model_only"

    def test_market_age_none(self):
        """Returns (model_prob, 'model_only') when market_age_seconds is None."""
        prob, source = blend_predictions(0.65, 0.70, None, alpha=0.5)
        assert prob == pytest.approx(0.65, abs=1e-6)
        assert source == "model_only"

    def test_stale_market_data(self):
        """Returns (model_prob, 'model_only') when market_age_seconds > 60."""
        prob, source = blend_predictions(0.65, 0.70, 61.0, alpha=0.5)
        assert prob == pytest.approx(0.65, abs=1e-6)
        assert source == "model_only"

    def test_stale_at_exact_threshold(self):
        """Staleness threshold is exclusive — exactly 60s is NOT stale."""
        prob, source = blend_predictions(0.65, 0.70, 60.0, alpha=0.5)
        assert source == "ensemble"

    def test_stale_custom_threshold(self):
        """Custom staleness_threshold works."""
        prob, source = blend_predictions(0.65, 0.70, 31.0, alpha=0.5, staleness_threshold=30.0)
        assert source == "model_only"

    def test_invalid_market_prob_negative(self):
        """Returns model_only when market_prob < 0."""
        prob, source = blend_predictions(0.65, -0.1, 10.0, alpha=0.5)
        assert source == "model_only"
        assert prob == pytest.approx(0.65, abs=1e-6)

    def test_invalid_market_prob_above_one(self):
        """Returns model_only when market_prob > 1."""
        prob, source = blend_predictions(0.65, 1.5, 10.0, alpha=0.5)
        assert source == "model_only"
        assert prob == pytest.approx(0.65, abs=1e-6)


class TestBlendPredictionsEnsemble:
    """Tests for valid ensemble blending."""

    def test_basic_blend(self):
        """Valid market data returns blended probability with source='ensemble'."""
        prob, source = blend_predictions(0.60, 0.80, 10.0, alpha=0.5)
        assert source == "ensemble"
        assert prob == pytest.approx(0.70, abs=1e-6)

    def test_alpha_weighting(self):
        """Alpha=0.7 gives 70% model + 30% market."""
        prob, source = blend_predictions(0.60, 0.80, 5.0, alpha=0.7)
        expected = 0.7 * 0.60 + 0.3 * 0.80
        assert source == "ensemble"
        assert prob == pytest.approx(expected, abs=1e-6)

    def test_pure_market_mode(self):
        """Alpha=0.0 returns pure market probability."""
        prob, source = blend_predictions(0.60, 0.80, 5.0, alpha=0.0)
        assert source == "ensemble"
        assert prob == pytest.approx(0.80, abs=1e-6)

    def test_pure_model_mode(self):
        """Alpha=1.0 returns pure model probability (clamped)."""
        prob, source = blend_predictions(0.60, 0.80, 5.0, alpha=1.0)
        assert source == "ensemble"
        assert prob == pytest.approx(0.60, abs=1e-6)


class TestBlendPredictionsClamping:
    """Tests for clamping to [0.001, 0.999]."""

    def test_clamp_low(self):
        """Ensemble near 0 is clamped to 0.001."""
        prob, source = blend_predictions(0.001, 0.001, 5.0, alpha=0.5)
        assert prob >= 0.001
        assert source == "ensemble"

    def test_clamp_high(self):
        """Ensemble near 1 is clamped to 0.999."""
        prob, source = blend_predictions(0.999, 0.999, 5.0, alpha=0.5)
        assert prob <= 0.999
        assert source == "ensemble"

    def test_model_prob_clamped_on_fallback(self):
        """Model prob 0.0 is clamped to 0.001 when falling back."""
        prob, source = blend_predictions(0.0, None, None, alpha=0.5)
        assert prob == pytest.approx(0.001, abs=1e-6)
        assert source == "model_only"

    def test_model_prob_clamped_above(self):
        """Model prob 1.0 is clamped to 0.999 when falling back."""
        prob, source = blend_predictions(1.0, None, None, alpha=0.5)
        assert prob == pytest.approx(0.999, abs=1e-6)
        assert source == "model_only"


class TestBlendPredictionsNeverRaises:
    """FR-012: blend_predictions must NEVER raise exceptions."""

    def test_none_model_prob(self):
        prob, source = blend_predictions(None, 0.5, 10.0, alpha=0.5)
        assert isinstance(prob, float)
        assert source in ("model_only", "ensemble")

    def test_nan_model_prob(self):
        prob, source = blend_predictions(float('nan'), 0.5, 10.0, alpha=0.5)
        assert isinstance(prob, float)
        assert not math.isnan(prob)

    def test_nan_market_prob(self):
        prob, source = blend_predictions(0.6, float('nan'), 10.0, alpha=0.5)
        assert isinstance(prob, float)
        assert source == "model_only"

    def test_string_model_prob(self):
        prob, source = blend_predictions("bad", 0.5, 10.0, alpha=0.5)
        assert isinstance(prob, float)

    def test_string_market_prob(self):
        prob, source = blend_predictions(0.6, "bad", 10.0, alpha=0.5)
        assert isinstance(prob, float)
        assert source == "model_only"

    def test_string_market_age(self):
        prob, source = blend_predictions(0.6, 0.5, "old", alpha=0.5)
        assert isinstance(prob, float)
        assert source == "model_only"

    def test_negative_market_age(self):
        """Negative market_age_seconds should still blend (it's fresh)."""
        prob, source = blend_predictions(0.6, 0.5, -1.0, alpha=0.5)
        assert isinstance(prob, float)

    def test_all_none(self):
        prob, source = blend_predictions(None, None, None, alpha=0.5)
        assert isinstance(prob, float)
        assert source == "model_only"
