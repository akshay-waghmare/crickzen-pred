"""
Contract: Market Ensemble Blending

Defines the interface for blending model predictions with market odds
to produce ensemble predictions (User Story 6).

This is a design contract, not executable code. Implementation extends
src/bbl_pipeline/inference/crex_live_predictor.py.
"""

from typing import Optional, Tuple


# --- Contract: Configuration ---

ENSEMBLE_CONFIG = {
    "alpha_range": (0.0, 1.0),      # Blending weight range
    "default_alpha": 0.3,            # Initial guess (model-leaning)
    "staleness_threshold_sec": 60,   # Max age of market data
    "clamp_range": (0.001, 0.999),   # Output probability bounds
    "optimal_alpha_source": "Sweep on validation set (510 observations)",
}


# --- Contract: Blending function ---

def blend_predictions(
    model_prob: float,
    market_prob: Optional[float],
    market_age_seconds: Optional[float],
    alpha: float,
    staleness_threshold: float = 60.0,
) -> Tuple[float, str]:
    """
    Blend model and market predictions.

    Args:
        model_prob: Calibrated model win probability [0, 1]
        market_prob: Market implied probability [0, 1] or None if unavailable
        market_age_seconds: Seconds since market data was captured, or None
        alpha: Blending weight. 1.0 = pure model, 0.0 = pure market.
        staleness_threshold: Max acceptable age in seconds

    Returns:
        Tuple of (ensemble_prob, source_label)
        - ensemble_prob: Blended probability in [0.001, 0.999]
        - source_label: "ensemble" or "model_only"

    Contract:
        1. If market_prob is None → return (model_prob, "model_only")
        2. If market_age_seconds is None or > staleness_threshold → return (model_prob, "model_only")
        3. Otherwise → return (alpha * model_prob + (1-alpha) * market_prob, "ensemble")
        4. Output always clamped to [0.001, 0.999]
        5. MUST NOT raise any exception regardless of input (FR-012)
    """
    ...


# --- Contract: Alpha sweep for optimal weight ---

ALPHA_SWEEP_CONTRACT = {
    "method": "Grid search alpha from 0.0 to 1.0 in steps of 0.05",
    "metric": "Brier score on validation set",
    "data": "data/ipl_model_vs_market.parquet (510 observations)",
    "required_columns": ["model_prob", "market_prob", "actual_outcome"],
    "output": "Optimal alpha + Brier scores at each alpha",
    "success_criteria": [
        "Optimal alpha Brier < pure model Brier (0.1977)",
        "Optimal alpha Brier < pure market Brier (0.1546)",
        "If no alpha beats both baselines: report and use alpha=0.0 (pure market) as ceiling",
    ],
}


# --- Contract: Logging requirements ---

LOGGING_CONTRACT = {
    "fields_to_log": [
        "model_prob",       # Raw model prediction (pre-ensemble)
        "ensemble_prob",    # Final blended prediction
        "market_prob",      # Market implied probability
        "alpha",            # Blending weight used
        "source",           # "ensemble" or "model_only"
    ],
    "destination": "match_state_logger.py → Parquet schema",
    "rationale": "FR-013: Preserve traceability of both model-only and ensemble outputs",
}


# --- Contract: Graceful degradation ---

FALLBACK_SCENARIOS = {
    "market_data_missing": {
        "trigger": "market_prob is None",
        "behavior": "Return model_prob, source='model_only'",
        "test": "test_market_ensemble.py::test_missing_market_data",
    },
    "market_data_stale": {
        "trigger": "market_age_seconds > staleness_threshold",
        "behavior": "Return model_prob, source='model_only'",
        "test": "test_market_ensemble.py::test_stale_market_data",
    },
    "market_prob_invalid": {
        "trigger": "market_prob < 0 or market_prob > 1",
        "behavior": "Return model_prob, source='model_only'",
        "test": "test_market_ensemble.py::test_invalid_market_prob",
    },
    "alpha_zero": {
        "trigger": "alpha == 0.0",
        "behavior": "Return market_prob (pure market), source='ensemble'",
        "test": "test_market_ensemble.py::test_pure_market_mode",
    },
}
