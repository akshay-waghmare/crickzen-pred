"""
BBL Pipeline - T20 Cricket Win Probability Models.

This package provides tools for training, evaluating, and deploying
win probability models for T20 cricket matches.

Submodules:
    - ingestion: Parse Cricsheet JSON files to Parquet
    - processing: Feature engineering
    - training: Model training with XGBLogRegEnsemble
    - inference: Real-time prediction engine
    - simulation: Monte Carlo simulation for uncertainty quantification
"""

# Expose simulation module for convenience
from . import simulation

__all__ = [
    "simulation",
]
