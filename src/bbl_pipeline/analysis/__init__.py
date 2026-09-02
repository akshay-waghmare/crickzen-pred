"""
Analysis package for match state logging system.

This package provides post-match analysis capabilities for recorded match states,
including:
- Consolidation of per-match Parquet files
- Calibration metrics (Brier score, ECE, Log Loss)
- Volatility profile computation (model vs market)
- Signal event extraction with price reversion labels
- Deviation analysis by bucket/phase/tier
- Recovery premium analysis for strong teams

Primary class: StateAnalyzer
"""

from bbl_pipeline.analysis.state_analyzer import StateAnalyzer
from bbl_pipeline.analysis.market_promotion import (
    build_promotion_review,
    expected_calibration_error,
    load_recorded_states,
    write_promotion_review,
)

__all__ = [
    "StateAnalyzer",
    "build_promotion_review",
    "expected_calibration_error",
    "load_recorded_states",
    "write_promotion_review",
]
