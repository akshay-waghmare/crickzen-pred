"""
Contract: Phase-Wise League Calibrator

Defines the interface changes to LeagueCalibrator for phase-wise Platt scaling
(6 calibrators replacing 2 temperature scalers).

This is a design contract, not executable code. Implementation modifies
src/bbl_pipeline/training/league_calibrator.py.
"""

from typing import Dict, Any


# --- Contract: LeagueCalibrator configuration ---

CALIBRATOR_CONFIG = {
    "method": "platt",           # Changed from 'temperature' to 'platt'
    "innings_specific": True,    # Unchanged - still fit per innings
    "phase_specific": True,      # Changed from False to True
    "min_samples": 500,          # Unchanged - fallback threshold

    # New: Phase mapping for routing
    "phase_mapping": {
        "powerplay": (1, 6),     # Overs 1-6
        "middle": (7, 14),       # Overs 7-14
        "death": (15, 20),       # Overs 15-20
    },
}


# --- Contract: Calibrator keys ---

REQUIRED_CALIBRATOR_KEYS = [
    # Phase-specific (primary)
    "inn1_powerplay",
    "inn1_middle",
    "inn1_death",
    "inn2_powerplay",
    "inn2_middle",
    "inn2_death",
    # Innings-level (fallback)
    "innings_1",
    "innings_2",
]


# --- Contract: Prediction routing ---

def predict_contract(
    df_row: Dict[str, Any],
    calibrators: Dict[str, Any],
) -> str:
    """
    Contract for calibrator routing logic.

    Args:
        df_row: Must contain 'innings' (int) and 'phase' (str) columns
        calibrators: Dict of fitted calibrators keyed by REQUIRED_CALIBRATOR_KEYS

    Returns:
        Key of the calibrator to use.

    Routing logic:
        1. Try phase-specific: f"inn{innings}_{phase}"
        2. If not found or not fitted: fall back to f"innings_{innings}"
        3. If not found: return raw probability (identity)
    """
    innings = df_row["innings"]
    phase = df_row["phase"]

    # Primary: phase-specific
    phase_key = f"inn{innings}_{phase}"
    if phase_key in calibrators:
        return phase_key

    # Fallback: innings-level
    innings_key = f"innings_{innings}"
    if innings_key in calibrators:
        return innings_key

    # Last resort: identity
    return "identity"


# --- Contract: Fit requirements ---

FIT_CONTRACT = {
    "required_columns": ["innings", "phase", "date"],
    "phase_values": ["powerplay", "middle", "death"],
    "innings_values": [1, 2],
    "min_samples_phase": 500,        # Below this: skip phase calibrator
    "min_samples_innings": 500,      # Below this: skip innings calibrator
    "calibrator_type": "PlattScaler",  # Not TemperatureScaler
    "reason": "Platt adds bias term (b) to correct systematic "
              "over/under-confidence per phase. Temperature only scales spread.",
}


# --- Contract: Metrics output ---

METRICS_CONTRACT = {
    "required_metrics": [
        "brier_raw",
        "brier_calibrated",
        "logloss_raw",
        "logloss_calibrated",
        "samples",
    ],
    "segmentation": [
        "overall",
        "by_innings",        # innings_1, innings_2
        "by_phase",          # powerplay, middle, death (per innings)
        "by_date",           # monthly breakdown
    ],
    "success_criteria": [
        "brier_calibrated < brier_raw for overall",
        "No phase regresses (brier_calibrated <= brier_raw + 0.005 per phase)",
        "Improvement greater than near-zero delta of current temperature approach",
    ],
}
