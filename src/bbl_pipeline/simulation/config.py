"""
Configuration for Monte Carlo Simulation Engine.

Contains phase tables derived from 1.89M global T20 balls (research.md).
"""

import numpy as np
from typing import Dict, Tuple

# =============================================================================
# PHASE DEFINITIONS
# =============================================================================

PHASES = ("powerplay", "middle", "death")

# Phase boundaries (overs completed)
# Powerplay: overs 1-6 (balls_remaining 120-85)
# Middle: overs 7-15 (balls_remaining 84-31)
# Death: overs 16-20 (balls_remaining 30-1)

POWERPLAY_END_OVER = 6  # After over 6, middle begins
MIDDLE_END_OVER = 15    # After over 15, death begins


def get_scaled_phase_boundaries(total_overs: int) -> tuple:
    """
    Compute phase boundaries for reduced-over matches.
    
    Uses proportional scaling with minimums:
    - Powerplay: ~30% of total overs (min 2, max 6)
    - Death: last ~25% of overs (min 2 overs)
    - Middle: everything in between
    
    Args:
        total_overs: Total overs in innings (1-20)
        
    Returns:
        (powerplay_end, middle_end) over thresholds
    """
    if total_overs <= 2:
        # Super over or very short: everything is "death"
        return (0, 0)
    
    powerplay_end = max(2, min(6, round(total_overs * 0.30)))
    death_overs = max(2, round(total_overs * 0.25))
    death_start = total_overs - death_overs + 1
    middle_end = death_start - 1
    
    # Ensure middle_end >= powerplay_end (no empty middle phase)
    if middle_end < powerplay_end:
        middle_end = powerplay_end
    
    return (powerplay_end, middle_end)


def get_phase(balls_remaining: int, total_balls: int = 120) -> str:
    """
    Determine game phase based on balls remaining.
    
    Args:
        balls_remaining: Balls remaining in innings (1-total_balls)
        total_balls: Total balls in innings (120 for T20, 300 for ODI)
        
    Returns:
        Phase name: 'powerplay', 'middle', or 'death'
        
    Examples:
        >>> get_phase(120)  # Start of T20 innings
        'powerplay'
        >>> get_phase(84)   # After 6 overs
        'middle'
        >>> get_phase(30)   # After 15 overs
        'death'
    """
    if balls_remaining <= 0:
        return "death"  # Edge case: innings over
    
    overs_completed = (total_balls - balls_remaining) / 6
    
    # Use scaled boundaries for reduced-over matches; constants for standard T20
    if total_balls == 120:
        pp_end = POWERPLAY_END_OVER
        mid_end = MIDDLE_END_OVER
    else:
        total_overs = total_balls // 6
        pp_end, mid_end = get_scaled_phase_boundaries(total_overs)
    
    if overs_completed < pp_end:
        return "powerplay"
    elif overs_completed < mid_end:
        return "middle"
    else:
        return "death"


# =============================================================================
# RUN DISTRIBUTIONS BY PHASE
# =============================================================================
# Derived from 1.89M global T20 balls (research.md Section 2)
# Probabilities sum to 1.0 for each phase
# Keys: runs scored (0, 1, 2, 3, 4, 5, 6)

RUN_DIST: Dict[str, Dict[int, float]] = {
    "powerplay": {
        0: 0.4496,  # Dots
        1: 0.3106,  # Singles
        2: 0.0518,  # Twos
        3: 0.0064,  # Threes
        4: 0.1426,  # Fours
        5: 0.0026,  # Extras (simplified as 5)
        6: 0.0363,  # Sixes
    },
    "middle": {
        0: 0.3244,
        1: 0.4720,
        2: 0.0736,
        3: 0.0041,
        4: 0.0816,
        5: 0.0013,
        6: 0.0427,
    },
    "death": {
        0: 0.2868,
        1: 0.4315,
        2: 0.1003,
        3: 0.0053,
        4: 0.1052,
        5: 0.0018,
        6: 0.0684,
    },
}


# =============================================================================
# WICKET PROBABILITIES BY PHASE
# =============================================================================
# Base wicket probability per ball (research.md Section 3)
# Death overs have ~2x wicket rate

WICKET_PROB: Dict[str, float] = {
    "powerplay": 0.0440,
    "middle": 0.0471,
    "death": 0.0860,
}


# =============================================================================
# WICKET MULTIPLIER BY WICKETS DOWN
# =============================================================================
# Lower-order batters have higher wicket probability (research.md Section 4)
# Multiplier applied to base WICKET_PROB

WICKET_MULTIPLIER: Dict[int, float] = {
    0: 1.00,  # Openers
    1: 1.00,
    2: 0.98,
    3: 0.96,
    4: 0.99,
    5: 1.05,  # Lower order begins
    6: 1.20,
    7: 1.30,
    8: 1.40,
    9: 1.50,  # Tail-ender
}


# =============================================================================
# PRE-COMPUTED CUMULATIVE DISTRIBUTIONS FOR SAMPLING
# =============================================================================
# Used with np.searchsorted() for efficient sampling

def _build_cdf(dist: Dict[int, float]) -> Tuple[np.ndarray, np.ndarray]:
    """Build CDF arrays for np.searchsorted() sampling."""
    runs = np.array(sorted(dist.keys()))
    probs = np.array([dist[r] for r in runs])
    cdf = np.cumsum(probs)
    return runs, cdf


RUN_CDF: Dict[str, Tuple[np.ndarray, np.ndarray]] = {
    phase: _build_cdf(dist) for phase, dist in RUN_DIST.items()
}


# =============================================================================
# BETTING THRESHOLDS (Phase-Aware)
# =============================================================================
# Default thresholds from spec.md (FR-011)

EDGE_MIN_BY_PHASE: Dict[str, Dict[str, float]] = {
    "inn1": {"powerplay": 0.30, "middle": 0.30, "death": 0.25},
    "inn2": {"powerplay": 0.20, "middle": 0.18, "death": 0.15},
}

SIGMA_MAX_BY_PHASE: Dict[str, Dict[str, float]] = {
    "inn1": {"powerplay": 0.10, "middle": 0.10, "death": 0.10},
    "inn2": {"powerplay": 0.10, "middle": 0.10, "death": 0.10},
}
