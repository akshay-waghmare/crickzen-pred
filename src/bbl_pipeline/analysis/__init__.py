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

__all__ = ["StateAnalyzer"]
