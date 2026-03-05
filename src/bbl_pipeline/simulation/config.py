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

# ODI uses 4 phases including "setup" (acceleration phase, overs 35-40)
ODI_PHASES = ("powerplay", "middle", "setup", "death")

# Phase boundaries (overs completed)
# Powerplay: overs 1-6 (balls_remaining 120-85)
# Middle: overs 7-15 (balls_remaining 84-31)
# Death: overs 16-20 (balls_remaining 30-1)

POWERPLAY_END_OVER = 6  # After over 6, middle begins
MIDDLE_END_OVER = 15    # After over 15, death begins

# ODI phase boundaries (overs completed)
ODI_POWERPLAY_END_OVER = 10   # After over 10, middle begins
ODI_MIDDLE_END_OVER = 34      # After over 34, setup begins
ODI_SETUP_END_OVER = 40       # After over 40, death begins


def get_odi_phase_boundaries() -> tuple:
    """
    Return ODI phase boundaries as (pp_end, mid_end, setup_end) over thresholds.
    
    Returns:
        (10, 34, 40) — overs completed thresholds for ODI phases
    """
    return (ODI_POWERPLAY_END_OVER, ODI_MIDDLE_END_OVER, ODI_SETUP_END_OVER)


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
    
    For T20 (total_balls <= 120): returns 'powerplay', 'middle', or 'death'
    For ODI (total_balls > 120): returns 'powerplay', 'middle', 'setup', or 'death'
    
    Args:
        balls_remaining: Balls remaining in innings (1-total_balls)
        total_balls: Total balls in innings (120 for T20, 300 for ODI)
        
    Returns:
        Phase name
        
    Examples:
        >>> get_phase(120)  # Start of T20 innings
        'powerplay'
        >>> get_phase(84)   # After 6 overs
        'middle'
        >>> get_phase(30)   # After 15 overs
        'death'
        >>> get_phase(240, total_balls=300)  # ODI after 10 overs
        'middle'
        >>> get_phase(90, total_balls=300)   # ODI after 35 overs
        'setup'
    """
    if balls_remaining <= 0:
        return "death"  # Edge case: innings over
    
    overs_completed = (total_balls - balls_remaining) / 6
    
    # ODI format: 4-phase system
    if total_balls > 120:
        pp_end, mid_end, setup_end = get_odi_phase_boundaries()
        if overs_completed < pp_end:
            return "powerplay"
        elif overs_completed < mid_end:
            return "middle"
        elif overs_completed < setup_end:
            return "setup"
        else:
            return "death"
    
    # T20 format: 3-phase system
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
# ODI RUN DISTRIBUTIONS BY PHASE (4 phases)
# =============================================================================
# Empirically derived from 1,760 male ODI matches (2010+), 935K balls.
# Extracted via scripts/extract_odi_phase_distributions.py.

ODI_RUN_DIST: Dict[str, Dict[int, float]] = {
    "powerplay": {  # Overs 1-10, ~4.68 RPO
        0: 0.6350,
        1: 0.2020,
        2: 0.0420,
        3: 0.0100,
        4: 0.1000,
        5: 0.0020,
        6: 0.0090,
    },
    "middle": {  # Overs 11-34, ~4.80 RPO
        0: 0.5080,
        1: 0.3640,
        2: 0.0480,
        3: 0.0050,
        4: 0.0620,
        5: 0.0010,
        6: 0.0120,
    },
    "setup": {  # Overs 35-40, ~5.61 RPO
        0: 0.4581,
        1: 0.3850,
        2: 0.0570,
        3: 0.0050,
        4: 0.0750,
        5: 0.0010,
        6: 0.0189,
    },
    "death": {  # Overs 41-50, ~7.10 RPO
        0: 0.3641,
        1: 0.4230,
        2: 0.0810,
        3: 0.0050,
        4: 0.0890,
        5: 0.0010,
        6: 0.0369,
    },
}


# =============================================================================
# ODI WICKET PROBABILITIES BY PHASE
# =============================================================================
# Empirically derived from 935K balls across 1,760 male ODIs (2010+).

ODI_WICKET_PROB: Dict[str, float] = {
    "powerplay": 0.0230,
    "middle": 0.0215,
    "setup": 0.0305,
    "death": 0.0547,
}


# =============================================================================
# ODI WICKET MULTIPLIER BY WICKETS DOWN
# =============================================================================
# Empirically derived. Clamped to [0.5, 2.0] per data-model validation rules.
# Openers/top-order have lower base rate; tail is more vulnerable.

ODI_WICKET_MULTIPLIER: Dict[int, float] = {
    0: 0.84,
    1: 0.79,
    2: 0.75,
    3: 0.82,
    4: 0.95,
    5: 1.12,
    6: 1.39,
    7: 1.77,
    8: 2.00,  # Clamped from 2.09
    9: 2.00,  # Clamped from 2.61
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

ODI_RUN_CDF: Dict[str, Tuple[np.ndarray, np.ndarray]] = {
    phase: _build_cdf(dist) for phase, dist in ODI_RUN_DIST.items()
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
