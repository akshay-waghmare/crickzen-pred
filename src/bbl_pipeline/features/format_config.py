"""
Format-specific configuration for cricket win probability models.

Bundles all format-dependent constants (T20: 20 overs, ODI: 50 overs) into a
frozen dataclass so one ResourceFeatureCalculator serves both formats.

Usage:
    from bbl_pipeline.features.format_config import FormatConfig

    t20_config = FormatConfig.t20()
    odi_config = FormatConfig.odi(gender='male')

    calculator = ResourceFeatureCalculator(config=t20_config)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional


def _interpolate_dls(overs_to_pct: Dict[int, float], overs: int) -> float:
    """Linearly interpolate a DLS resource table row for a given overs value.

    The DLS table stores resource percentages at discrete overs-remaining
    points (e.g. {0, 1, 5, 10, 15, 20}).  This helper interpolates for
    overs values between those points (e.g. 12 → interpolate between 10
    and 15).

    Parameters
    ----------
    overs_to_pct : dict
        Mapping of ``overs_remaining`` → ``resource_pct`` (0-100).
    overs : int
        The overs-remaining value to look up.

    Returns
    -------
    float
        Interpolated resource percentage.
    """
    if overs in overs_to_pct:
        return overs_to_pct[overs]

    keys = sorted(overs_to_pct.keys())
    # Clamp to table range
    if overs <= keys[0]:
        return overs_to_pct[keys[0]]
    if overs >= keys[-1]:
        return overs_to_pct[keys[-1]]

    # Find bracketing keys
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo < overs < hi:
            frac = (overs - lo) / (hi - lo)
            return overs_to_pct[lo] + frac * (overs_to_pct[hi] - overs_to_pct[lo])

    return overs_to_pct[keys[-1]]  # fallback


@dataclass(frozen=True)
class FormatConfig:
    """Immutable configuration holding all format-specific constants.

    Created once at pipeline start, passed through ingestion → processing →
    training → inference.  Factory class-methods provide validated presets.
    """

    # --- Identity -----------------------------------------------------------
    format_name: str
    gender: str  # "male" or "female"

    # --- Match structure ----------------------------------------------------
    total_overs: int
    total_balls: int
    balls_per_over: int
    total_wickets: int

    # --- Scoring benchmarks -------------------------------------------------
    par_score: float
    league_avg_score: float
    bat_first_win_rate: float

    # --- Phase system -------------------------------------------------------
    phase_thresholds: Dict[str, int]   # phase_name → over boundary (upper)
    phase_names: List[str]
    expected_run_rates: Dict[str, float]  # phase_name → expected RR

    # --- Ease thresholds (1st innings) --------------------------------------
    ease_thresholds: Dict[str, float]

    # --- DLS resource table -------------------------------------------------
    dls_resource_table: Dict[int, Dict[int, float]]  # wickets → {overs_rem: %}

    # --- First innings penalties --------------------------------------------
    first_innings_wicket_penalty_3d: Dict[str, Dict[str, Dict[int, float]]]
    first_innings_score_midpoint: float
    first_innings_score_beta: float
    first_innings_wicket_penalty: Dict[int, float]

    # --- Chase (2nd innings) penalties --------------------------------------
    chase_wicket_penalty_2d: Dict[str, Dict[int, float]]
    chase_ease_thresholds: Dict[str, float]
    wicket_penalty: Dict[int, float]  # flat chase penalty (deprecated, kept)

    # --- Chase parameters ---------------------------------------------------
    rrr_midpoint: float
    rrr_beta: float
    rrr_midpoint_slope: float  # per-over midpoint shift: midpoint(over) = rrr_midpoint + slope * over_0idx
    chase_wicket_weight: float  # scales wicket_mult: 0.0=disabled, 1.0=full penalty

    # --- SQI / confidence ---------------------------------------------------
    sqi_beta: float
    sqi_shift: float
    confidence_full_overs: float
    score_std_early: float
    score_std_late: float
    wicket_decay_alpha: float

    # --- Score projection caps ----------------------------------------------
    score_cap_min: float
    score_cap_max: float

    # --- Endgame / pressure -------------------------------------------------
    endgame_balls: int
    pressure_rrr_min: float
    pressure_rrr_max: float

    # --- Innings transition blend (0 = disabled) ----------------------------
    transition_blend_overs: int = 6  # Blend inn1 prior over first N inn2 overs; 0 disables

    # --- Final-over lookup (optional, None = use sigmoid fallback) ----------
    final_over_lookup: Optional[Dict[int, Dict[int, float]]] = None

    # ── Validation ──────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        if self.total_balls != self.total_overs * self.balls_per_over:
            raise ValueError(
                f"total_balls ({self.total_balls}) != "
                f"total_overs ({self.total_overs}) * balls_per_over ({self.balls_per_over})"
            )
        if self.total_wickets != 10:
            raise ValueError(f"total_wickets must be 10, got {self.total_wickets}")
        if len(self.phase_thresholds) != len(self.phase_names):
            raise ValueError(
                f"phase_thresholds ({len(self.phase_thresholds)}) and "
                f"phase_names ({len(self.phase_names)}) length mismatch"
            )
        last_phase = self.phase_names[-1]
        if self.phase_thresholds[last_phase] != self.total_overs:
            raise ValueError(
                f"Last phase '{last_phase}' threshold "
                f"({self.phase_thresholds[last_phase]}) != total_overs ({self.total_overs})"
            )
        if not (0 < self.bat_first_win_rate < 1):
            raise ValueError(
                f"bat_first_win_rate must be in (0, 1), got {self.bat_first_win_rate}"
            )
        if not (self.score_cap_min < self.par_score < self.score_cap_max):
            raise ValueError(
                f"score_cap_min ({self.score_cap_min}) < par_score ({self.par_score}) "
                f"< score_cap_max ({self.score_cap_max}) violated"
            )

    # ── Factory methods ─────────────────────────────────────────────────────

    @classmethod
    def t20(cls) -> FormatConfig:
        """Return T20 preset — exact copies of the values previously
        hardcoded in :class:`ResourceFeatureCalculator`.

        This is the **canonical** T20 configuration.  Any deviation from the
        literal values that lived in ``calculator.py`` is a regression.
        """
        return cls(
            format_name="t20",
            gender="male",

            # Match structure
            total_overs=20,
            total_balls=120,
            balls_per_over=6,
            total_wickets=10,

            # Scoring benchmarks
            par_score=160.0,
            league_avg_score=165.0,
            bat_first_win_rate=0.37,

            # Phase system (T20: powerplay/middle/death/final)
            phase_thresholds={
                "powerplay": 6,
                "middle": 14,
                "death": 18,
                "final": 20,
            },
            phase_names=["powerplay", "middle", "death", "final"],
            expected_run_rates={
                "powerplay": 7.5,
                "middle": 7.8,
                "death": 9.5,
                "final": 11.0,
            },

            # Ease thresholds (1st innings)
            ease_thresholds={
                "well_ahead": 1.15,
                "ahead": 1.05,
                "par": 0.95,
                "behind": 0.85,
                "well_behind": 0.0,
            },

            # DLS resource table (T20 simplified)
            dls_resource_table={
                0: {20: 100.0, 15: 84.4, 10: 63.4, 5: 35.4, 1: 8.2, 0: 0.0},
                1: {20: 95.3, 15: 81.5, 10: 61.6, 5: 34.5, 1: 8.0, 0: 0.0},
                2: {20: 88.9, 15: 77.4, 10: 59.0, 5: 33.2, 1: 7.7, 0: 0.0},
                3: {20: 80.6, 15: 71.8, 10: 55.5, 5: 31.4, 1: 7.3, 0: 0.0},
                4: {20: 70.6, 15: 64.5, 10: 50.8, 5: 28.8, 1: 6.7, 0: 0.0},
                5: {20: 59.1, 15: 55.5, 10: 44.7, 5: 25.5, 1: 5.9, 0: 0.0},
                6: {20: 46.1, 15: 44.5, 10: 37.0, 5: 21.3, 1: 4.9, 0: 0.0},
                7: {20: 32.4, 15: 32.0, 10: 27.5, 5: 16.1, 1: 3.7, 0: 0.0},
                8: {20: 18.4, 15: 18.4, 10: 16.6, 5: 10.0, 1: 2.3, 0: 0.0},
                9: {20: 5.5, 15: 5.5, 10: 5.5, 5: 4.1, 1: 0.9, 0: 0.0},
            },

            # First innings penalties
            first_innings_wicket_penalty_3d={
                "powerplay": {
                    "well_ahead":  {0: 1.00, 1: 0.97, 2: 0.68, 3: 0.25, 4: 0.18, 5: 0.10, 6: 0.05, 7: 0.02, 8: 0.01, 9: 0.01, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 0.95, 2: 0.61, 3: 0.31, 4: 0.15, 5: 0.08, 6: 0.04, 7: 0.02, 8: 0.01, 9: 0.01, 10: 0.01},
                    "par":         {0: 1.00, 1: 0.98, 2: 0.60, 3: 0.50, 4: 0.30, 5: 0.15, 6: 0.08, 7: 0.04, 8: 0.02, 9: 0.01, 10: 0.01},
                    "behind":      {0: 1.00, 1: 0.91, 2: 0.67, 3: 0.47, 4: 0.11, 5: 0.05, 6: 0.02, 7: 0.01, 8: 0.01, 9: 0.01, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 0.90, 2: 0.56, 3: 0.31, 4: 0.05, 5: 0.01, 6: 0.01, 7: 0.01, 8: 0.01, 9: 0.01, 10: 0.01},
                },
                "middle": {
                    "well_ahead":  {0: 1.00, 1: 0.98, 2: 0.96, 3: 0.97, 4: 0.96, 5: 0.91, 6: 0.85, 7: 0.75, 8: 0.60, 9: 0.40, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.99, 5: 1.00, 6: 0.95, 7: 0.85, 8: 0.70, 9: 0.50, 10: 0.01},
                    "par":         {0: 1.00, 1: 0.99, 2: 0.99, 3: 0.98, 4: 0.98, 5: 0.97, 6: 0.95, 7: 0.96, 8: 0.90, 9: 0.80, 10: 0.01},
                    "behind":      {0: 1.00, 1: 0.99, 2: 0.99, 3: 0.98, 4: 0.98, 5: 0.97, 6: 0.98, 7: 1.00, 8: 0.96, 9: 0.90, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 1.00, 2: 1.00, 3: 0.97, 4: 0.97, 5: 0.97, 6: 0.89, 7: 0.87, 8: 0.98, 9: 0.95, 10: 0.01},
                },
                "death": {
                    "well_ahead":  {0: 1.00, 1: 1.00, 2: 1.00, 3: 0.95, 4: 0.96, 5: 0.94, 6: 0.92, 7: 0.90, 8: 0.85, 9: 0.80, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 0.98, 8: 0.95, 9: 0.90, 10: 0.01},
                    "par":         {0: 1.00, 1: 0.99, 2: 0.99, 3: 0.98, 4: 0.98, 5: 0.97, 6: 0.97, 7: 0.98, 8: 0.94, 9: 0.90, 10: 0.01},
                    "behind":      {0: 1.00, 1: 1.00, 2: 0.99, 3: 0.99, 4: 0.99, 5: 0.98, 6: 0.98, 7: 0.97, 8: 1.00, 9: 0.95, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 1.00, 2: 1.00, 3: 0.95, 4: 0.95, 5: 0.93, 6: 0.88, 7: 0.88, 8: 0.86, 9: 0.81, 10: 0.01},
                },
                "final": {
                    "well_ahead":  {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 0.99, 7: 0.98, 8: 0.95, 9: 0.90, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 0.99, 7: 0.98, 8: 0.95, 9: 0.90, 10: 0.01},
                    "par":         {0: 1.00, 1: 1.00, 2: 0.97, 3: 0.98, 4: 0.97, 5: 0.98, 6: 0.99, 7: 0.99, 8: 0.98, 9: 0.95, 10: 0.01},
                    "behind":      {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 1.00, 8: 1.00, 9: 0.99, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.98, 5: 0.96, 6: 0.93, 7: 0.91, 8: 0.88, 9: 0.84, 10: 0.01},
                },
            },
            first_innings_score_midpoint=165.0,
            first_innings_score_beta=0.04,
            first_innings_wicket_penalty={
                0: 1.00, 1: 1.00, 2: 0.95, 3: 0.85,
                4: 0.70, 5: 0.55, 6: 0.40, 7: 0.25,
                8: 0.12, 9: 0.05, 10: 0.01,
            },

            # Chase penalties
            chase_wicket_penalty_2d={
                "very_easy": {
                    0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
                    5: 0.88, 6: 0.76, 7: 0.56, 8: 0.24, 9: 0.05, 10: 0.00,
                },
                "easy": {
                    0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
                    5: 1.00, 6: 1.00, 7: 1.00, 8: 0.44, 9: 0.22, 10: 0.00,
                },
                "comfortable": {
                    0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
                    5: 1.00, 6: 1.00, 7: 1.00, 8: 0.62, 9: 0.74, 10: 0.00,
                },
                "tough": {
                    0: 1.00, 1: 0.93, 2: 0.90, 3: 0.88, 4: 0.76,
                    5: 0.79, 6: 0.71, 7: 0.70, 8: 0.34, 9: 0.05, 10: 0.00,
                },
                "desperate": {
                    0: 1.00, 1: 0.72, 2: 0.46, 3: 0.35, 4: 0.21,
                    5: 0.21, 6: 0.15, 7: 0.08, 8: 0.05, 9: 0.01, 10: 0.00,
                },
            },
            chase_ease_thresholds={
                "very_easy": 3.0,
                "easy": 1.5,
                "comfortable": 1.0,
                "tough": 0.7,
                "desperate": 0.0,
            },
            wicket_penalty={
                0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00,
                4: 0.75, 5: 0.50, 6: 0.35, 7: 0.25,
                8: 0.12, 9: 0.05, 10: 0.01,
            },

            # Chase parameters
            rrr_midpoint=9.5,
            rrr_beta=0.7,
            rrr_midpoint_slope=0.0,      # 0 = fixed midpoint (backward compatible)
            chase_wicket_weight=1.0,      # 1.0 = full wicket penalty (backward compatible)

            # SQI / confidence
            sqi_beta=0.75,
            sqi_shift=0.35,
            confidence_full_overs=12.0,
            score_std_early=15.0,
            score_std_late=26.0,
            wicket_decay_alpha=0.025,

            # Score projection caps
            score_cap_min=100.0,
            score_cap_max=280.0,

            # Endgame / pressure
            endgame_balls=12,
            pressure_rrr_min=7.0,
            pressure_rrr_max=15.0,
        )

    @classmethod
    def ipl(cls) -> "FormatConfig":
        """Return an IPL-tuned T20 configuration.

        The IPL uses the same 20-over match structure as the default T20
        preset, but its first-innings scoring environment is materially higher.
        Wicket penalties, final-over lookup, and scoring midpoint are derived
        from 273,503 IPL training rows via ``scripts/derive_ipl_improvements.py``.
        """
        base = cls.t20()
        return replace(
            base,
            # IPL scoring environment (from training data averages)
            par_score=173.45,
            league_avg_score=167.28,
            bat_first_win_rate=0.4581,
            # IPL chase sigmoid: per-over adaptive midpoint.
            # Fitted on 20,451 per-over observations (1169 IPL matches):
            #   midpoint(over) = 8.56 + 0.134 * over_0idx
            # Death overs get higher midpoint (IPL teams sustain higher RRR),
            # reducing inn2 resource_win_prob ECE from 0.1075 to 0.0123 (-89%).
            rrr_beta=0.598,
            rrr_midpoint=8.56,             # IPL intercept (was 9.5)
            rrr_midpoint_slope=0.134,  # IPL-specific: midpoint increases per over
            chase_wicket_weight=0.0,   # IPL: wicket penalty HURTS Brier by +6.7%
            transition_blend_overs=0,  # IPL v4: blend HURTS inn2 PP by +0.9%
            expected_run_rates={
                "powerplay": 7.53,
                "middle": 7.51,
                "death": 9.02,
                "final": 10.68,
            },
            # IPL-specific first-innings scoring midpoint (from EDA: par_score ~173.45)
            first_innings_score_midpoint=173.0,
            first_innings_score_beta=0.04,
            # IPL-specific first-innings penalties (derived from 141K 1st-innings rows)
            first_innings_wicket_penalty_3d={
                "powerplay": {
                    "well_ahead":  {0: 1.00, 1: 0.51, 2: 0.51, 3: 0.51, 4: 0.48, 5: 0.00, 6: 0.00, 7: 0.00, 8: 0.00, 9: 0.00, 10: 0.00},
                    "ahead":       {0: 1.00, 1: 0.42, 2: 0.42, 3: 0.33, 4: 0.33, 5: 0.00, 6: 0.00, 7: 0.00, 8: 0.00, 9: 0.00, 10: 0.00},
                    "par":         {0: 1.00, 1: 0.43, 2: 0.36, 3: 0.32, 4: 0.00, 5: 0.00, 6: 0.00, 7: 0.00, 8: 0.00, 9: 0.00, 10: 0.00},
                    "behind":      {0: 1.00, 1: 0.39, 2: 0.35, 3: 0.21, 4: 0.12, 5: 0.00, 6: 0.00, 7: 0.00, 8: 0.00, 9: 0.00, 10: 0.00},
                    "well_behind": {0: 1.00, 1: 0.39, 2: 0.34, 3: 0.21, 4: 0.12, 5: 0.12, 6: 0.00, 7: 0.00, 8: 0.00, 9: 0.00, 10: 0.00},
                },
                "middle": {
                    "well_ahead":  {0: 1.00, 1: 0.64, 2: 0.64, 3: 0.60, 4: 0.60, 5: 0.41, 6: 0.32, 7: 0.00, 8: 0.00, 9: 0.00, 10: 0.00},
                    "ahead":       {0: 1.00, 1: 0.56, 2: 0.51, 3: 0.51, 4: 0.44, 5: 0.41, 6: 0.29, 7: 0.18, 8: 0.00, 9: 0.00, 10: 0.00},
                    "par":         {0: 1.00, 1: 0.50, 2: 0.43, 3: 0.42, 4: 0.32, 5: 0.32, 6: 0.32, 7: 0.18, 8: 0.18, 9: 0.00, 10: 0.00},
                    "behind":      {0: 1.00, 1: 0.50, 2: 0.44, 3: 0.37, 4: 0.23, 5: 0.23, 6: 0.13, 7: 0.00, 8: 0.00, 9: 0.00, 10: 0.00},
                    "well_behind": {0: 1.00, 1: 0.44, 2: 0.32, 3: 0.32, 4: 0.15, 5: 0.15, 6: 0.05, 7: 0.00, 8: 0.00, 9: 0.00, 10: 0.00},
                },
                "death": {
                    "well_ahead":  {0: 1.00, 1: 0.81, 2: 0.81, 3: 0.81, 4: 0.78, 5: 0.78, 6: 0.78, 7: 0.78, 8: 0.00, 9: 0.00, 10: 0.00},
                    "ahead":       {0: 1.00, 1: 0.76, 2: 0.76, 3: 0.76, 4: 0.72, 5: 0.72, 6: 0.59, 7: 0.59, 8: 0.00, 9: 0.00, 10: 0.00},
                    "par":         {0: 1.00, 1: 0.61, 2: 0.49, 3: 0.49, 4: 0.49, 5: 0.49, 6: 0.49, 7: 0.49, 8: 0.05, 9: 0.00, 10: 0.00},
                    "behind":      {0: 1.00, 1: 0.53, 2: 0.53, 3: 0.50, 4: 0.45, 5: 0.44, 6: 0.35, 7: 0.14, 8: 0.05, 9: 0.04, 10: 0.00},
                    "well_behind": {0: 1.00, 1: 0.32, 2: 0.32, 3: 0.32, 4: 0.32, 5: 0.29, 6: 0.24, 7: 0.14, 8: 0.04, 9: 0.04, 10: 0.00},
                },
                "final": {
                    "well_ahead":  {0: 1.00, 1: 1.00, 2: 0.92, 3: 0.92, 4: 0.90, 5: 0.90, 6: 0.65, 7: 0.65, 8: 0.00, 9: 0.00, 10: 0.00},
                    "ahead":       {0: 1.00, 1: 1.00, 2: 0.92, 3: 0.92, 4: 0.92, 5: 0.92, 6: 0.65, 7: 0.65, 8: 0.65, 9: 0.65, 10: 0.00},
                    "par":         {0: 1.00, 1: 0.72, 2: 0.72, 3: 0.72, 4: 0.72, 5: 0.72, 6: 0.72, 7: 0.70, 8: 0.67, 9: 0.46, 10: 0.00},
                    "behind":      {0: 1.00, 1: 0.97, 2: 0.55, 3: 0.55, 4: 0.55, 5: 0.55, 6: 0.55, 7: 0.55, 8: 0.55, 9: 0.46, 10: 0.00},
                    "well_behind": {0: 1.00, 1: 0.40, 2: 0.40, 3: 0.40, 4: 0.40, 5: 0.39, 6: 0.38, 7: 0.31, 8: 0.21, 9: 0.20, 10: 0.00},
                },
            },
            # IPL-specific chase penalties (derived from 132K 2nd-innings rows)
            chase_wicket_penalty_2d={
                "very_easy":   {0: 1.00, 1: 1.00, 2: 0.99, 3: 0.99, 4: 0.97, 5: 0.84, 6: 0.72, 7: 0.53, 8: 0.23, 9: 0.23, 10: 0.00},
                "easy":        {0: 1.00, 1: 0.96, 2: 0.96, 3: 0.96, 4: 0.96, 5: 0.96, 6: 0.95, 7: 0.79, 8: 0.42, 9: 0.42, 10: 0.00},
                "comfortable": {0: 1.00, 1: 0.78, 2: 0.77, 3: 0.77, 4: 0.77, 5: 0.77, 6: 0.77, 7: 0.74, 8: 0.45, 9: 0.45, 10: 0.00},
                "tough":       {0: 1.00, 1: 0.59, 2: 0.50, 3: 0.50, 4: 0.49, 5: 0.45, 6: 0.41, 7: 0.22, 8: 0.22, 9: 0.00, 10: 0.00},
                "desperate":   {0: 1.00, 1: 0.38, 2: 0.26, 3: 0.24, 4: 0.20, 5: 0.15, 6: 0.09, 7: 0.04, 8: 0.02, 9: 0.00, 10: 0.00},
            },
            # IPL final-over empirical lookup (runs_needed -> {wickets_in_hand -> p})
            # Validated: Brier 0.0973 -> 0.0632 on final-over states (-35%)
            final_over_lookup={
                0:  {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.0, 8: 1.0, 9: 1.0, 10: 1.0},
                1:  {0: 0.0, 1: 0.90, 2: 0.90, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.0, 8: 1.0, 9: 1.0, 10: 1.0},
                2:  {0: 0.0, 1: 0.20, 2: 0.90, 3: 0.92, 4: 0.92, 5: 1.0, 6: 1.0, 7: 1.0, 8: 1.0, 9: 1.0, 10: 1.0},
                3:  {0: 0.0, 1: 0.20, 2: 0.79, 3: 0.85, 4: 0.89, 5: 1.0, 6: 1.0, 7: 1.0, 8: 1.0, 9: 1.0, 10: 1.0},
                4:  {0: 0.0, 1: 0.20, 2: 0.58, 3: 0.71, 4: 0.88, 5: 0.88, 6: 0.96, 7: 0.96, 8: 0.96, 9: 0.96, 10: 0.97},
                5:  {0: 0.0, 1: 0.19, 2: 0.58, 3: 0.58, 4: 0.78, 5: 0.82, 6: 0.96, 7: 0.96, 8: 0.96, 9: 0.96, 10: 0.96},
                6:  {0: 0.0, 1: 0.19, 2: 0.30, 3: 0.53, 4: 0.65, 5: 0.65, 6: 0.77, 7: 0.86, 8: 0.86, 9: 0.88, 10: 0.88},
                7:  {0: 0.0, 1: 0.19, 2: 0.30, 3: 0.53, 4: 0.65, 5: 0.65, 6: 0.73, 7: 0.80, 8: 0.80, 9: 0.80, 10: 0.80},
                8:  {0: 0.0, 1: 0.10, 2: 0.30, 3: 0.42, 4: 0.65, 5: 0.65, 6: 0.68, 7: 0.80, 8: 0.80, 9: 0.80, 10: 0.80},
                9:  {0: 0.0, 1: 0.10, 2: 0.20, 3: 0.32, 4: 0.36, 5: 0.54, 6: 0.54, 7: 0.79, 8: 0.79, 9: 0.79, 10: 0.79},
                10: {0: 0.0, 1: 0.10, 2: 0.20, 3: 0.32, 4: 0.36, 5: 0.54, 6: 0.54, 7: 0.72, 8: 0.72, 9: 0.72, 10: 0.72},
                11: {0: 0.0, 1: 0.08, 2: 0.08, 3: 0.11, 4: 0.31, 5: 0.46, 6: 0.50, 7: 0.72, 8: 0.72, 9: 0.72, 10: 0.72},
                12: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.11, 4: 0.24, 5: 0.46, 6: 0.46, 7: 0.63, 8: 0.63, 9: 0.63, 10: 0.63},
                13: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.11, 4: 0.11, 5: 0.27, 6: 0.40, 7: 0.40, 8: 0.40, 9: 0.40, 10: 0.40},
                14: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.09, 4: 0.10, 5: 0.27, 6: 0.40, 7: 0.40, 8: 0.40, 9: 0.40, 10: 0.40},
                15: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.09, 4: 0.10, 5: 0.22, 6: 0.30, 7: 0.30, 8: 0.30, 9: 0.30, 10: 0.30},
                16: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.09, 4: 0.10, 5: 0.20, 6: 0.25, 7: 0.25, 8: 0.25, 9: 0.25, 10: 0.25},
                17: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.09, 4: 0.10, 5: 0.19, 6: 0.19, 7: 0.19, 8: 0.19, 9: 0.19, 10: 0.19},
                18: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.05, 4: 0.07, 5: 0.19, 6: 0.19, 7: 0.19, 8: 0.19, 9: 0.19, 10: 0.19},
                19: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.04, 5: 0.09, 6: 0.19, 7: 0.19, 8: 0.19, 9: 0.19, 10: 0.19},
                20: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.04, 5: 0.07, 6: 0.19, 7: 0.19, 8: 0.19, 9: 0.19, 10: 0.19},
            },
        )

    @classmethod
    def t20_reduced(cls, total_overs: int) -> "FormatConfig":
        """Return a T20 configuration scaled for reduced-over matches.

        Uses the standard T20 preset as the base and scales match-structure
        fields (overs, balls, par score, phase thresholds) using DLS resource
        curves and proportional phase scaling.

        Parameters
        ----------
        total_overs : int
            Total overs per innings (1–20).  ``t20_reduced(20)`` returns
            the same config as ``t20()``.

        Returns
        -------
        FormatConfig
            Frozen config scaled for the given number of overs.

        Raises
        ------
        ValueError
            If ``total_overs`` is not in [1, 20].

        Examples
        --------
        >>> FormatConfig.t20_reduced(15).total_balls
        90
        >>> FormatConfig.t20_reduced(20) == FormatConfig.t20()
        True
        """
        if not 1 <= total_overs <= 20:
            raise ValueError(
                f"total_overs must be 1-20, got {total_overs}"
            )

        # Identity case — avoid any rounding differences
        if total_overs == 20:
            return cls.t20()

        base = cls.t20()
        total_balls = total_overs * 6

        # --- Phase thresholds (proportional scaling) ---
        if total_overs <= 2:
            # Super over or 2-over match: all death
            phase_thresholds = {
                "powerplay": 0,
                "middle": 0,
                "death": max(total_overs - 1, 0),
                "final": total_overs,
            }
        else:
            pp_end = max(2, min(6, round(total_overs * 0.30)))
            death_overs = max(2, round(total_overs * 0.25))
            death_start_over = total_overs - death_overs + 1
            middle_end = death_start_over - 1
            if middle_end < pp_end:
                middle_end = pp_end
            phase_thresholds = {
                "powerplay": pp_end,
                "middle": middle_end,
                "death": total_overs - 1 if total_overs > 1 else total_overs,
                "final": total_overs,
            }

        # --- Par score via DLS resource table ---
        dls_table = base.dls_resource_table
        # Interpolate resource % for 0 wickets at total_overs remaining
        resource_pct = _interpolate_dls(dls_table[0], total_overs)
        par_score = base.par_score * resource_pct / 100.0

        # --- Scale other match-length-dependent fields ---
        overs_ratio = total_overs / 20.0
        confidence_full = max(3.0, base.confidence_full_overs * overs_ratio)
        endgame = max(6, round(base.endgame_balls * overs_ratio))

        # Score caps scaled proportionally
        score_cap_min = max(20.0, base.score_cap_min * overs_ratio)
        score_cap_max = base.score_cap_max * overs_ratio

        # Ensure score_cap_min < par_score < score_cap_max
        if par_score <= score_cap_min:
            score_cap_min = par_score - 5.0
        if par_score >= score_cap_max:
            score_cap_max = par_score + 20.0

        return cls(
            format_name="t20_reduced",
            gender=base.gender,
            total_overs=total_overs,
            total_balls=total_balls,
            balls_per_over=6,
            total_wickets=10,
            par_score=par_score,
            league_avg_score=base.league_avg_score * overs_ratio,
            bat_first_win_rate=base.bat_first_win_rate,
            phase_thresholds=phase_thresholds,
            phase_names=base.phase_names,
            expected_run_rates=base.expected_run_rates,
            ease_thresholds=base.ease_thresholds,
            dls_resource_table=base.dls_resource_table,
            first_innings_wicket_penalty_3d=base.first_innings_wicket_penalty_3d,
            first_innings_score_midpoint=par_score + 5.0,
            first_innings_score_beta=base.first_innings_score_beta,
            first_innings_wicket_penalty=base.first_innings_wicket_penalty,
            chase_wicket_penalty_2d=base.chase_wicket_penalty_2d,
            chase_ease_thresholds=base.chase_ease_thresholds,
            wicket_penalty=base.wicket_penalty,
            rrr_midpoint=base.rrr_midpoint,
            rrr_beta=base.rrr_beta,
            rrr_midpoint_slope=base.rrr_midpoint_slope,
            chase_wicket_weight=base.chase_wicket_weight,
            sqi_beta=base.sqi_beta,
            sqi_shift=base.sqi_shift,
            confidence_full_overs=confidence_full,
            score_std_early=base.score_std_early * overs_ratio,
            score_std_late=base.score_std_late * overs_ratio,
            wicket_decay_alpha=base.wicket_decay_alpha,
            score_cap_min=score_cap_min,
            score_cap_max=score_cap_max,
            endgame_balls=endgame,
            pressure_rrr_min=base.pressure_rrr_min,
            pressure_rrr_max=base.pressure_rrr_max,
        )

    @classmethod
    def odi(cls, gender: str = "male") -> FormatConfig:
        """Return ODI preset populated with empirical constants.

        Constants derived from ``scripts/analyze_odi_empirical.py`` on
        1,632 male and 506 female ODI matches (2010+, full 50 overs).

        Parameters
        ----------
        gender : str
            ``'male'`` (default) or ``'female'``.
        """
        if gender == "female":
            return cls._odi_female()
        return cls._odi_male()

    @classmethod
    def _odi_male(cls) -> FormatConfig:
        """Male ODI constants — 1,632 matches, 2010–2025."""
        return cls(
            format_name="odi",
            gender="male",

            # Match structure
            total_overs=50,
            total_balls=300,
            balls_per_over=6,
            total_wickets=10,

            # Scoring benchmarks (empirical: avg 257.7, median 260)
            par_score=257.7,
            league_avg_score=260.0,
            bat_first_win_rate=0.490,

            # Phase system — ODI 4 phases
            phase_thresholds={
                "powerplay": 10,
                "middle": 34,
                "setup": 40,
                "death": 50,
            },
            phase_names=["powerplay", "middle", "setup", "death"],
            expected_run_rates={
                "powerplay": 4.82,
                "middle": 4.90,
                "setup": 5.71,
                "death": 7.32,
            },

            # Ease thresholds (same as T20)
            ease_thresholds={
                "well_ahead": 1.15,
                "ahead": 1.05,
                "par": 0.95,
                "behind": 0.85,
                "well_behind": 0.0,
            },

            # DLS resource table (empirical, 11 overs-remaining points)
            dls_resource_table={
                0: {50: 100.0, 45: 91.2, 40: 81.0, 35: 72.8, 30: 64.3, 25: 57.1, 20: 48.6, 15: 40.3, 10: 26.3, 5: 13.4, 0: 0.0},
                1: {50: 100.0, 45: 91.3, 40: 81.3, 35: 73.2, 30: 64.6, 25: 57.4, 20: 48.6, 15: 39.5, 10: 30.5, 5: 16.0, 0: 0.0},
                2: {50:  98.5, 45: 90.8, 40: 82.0, 35: 73.0, 30: 64.7, 25: 56.1, 20: 48.3, 15: 39.4, 10: 28.7, 5: 15.5, 0: 0.0},
                3: {50:  97.9, 45: 91.4, 40: 80.5, 35: 70.7, 30: 63.6, 25: 54.8, 20: 46.8, 15: 38.3, 10: 28.7, 5: 17.0, 0: 0.0},
                4: {50:  92.2, 45: 91.7, 40: 80.1, 35: 69.1, 30: 60.1, 25: 52.5, 20: 45.0, 15: 37.4, 10: 28.2, 5: 16.5, 0: 0.0},
                5: {50: 100.0, 45: 84.7, 40: 79.4, 35: 66.6, 30: 57.3, 25: 50.8, 20: 42.5, 15: 34.8, 10: 26.8, 5: 16.2, 0: 0.0},
                6: {50:  86.9, 45: 86.9, 40: 73.9, 35: 62.6, 30: 52.4, 25: 45.5, 20: 37.5, 15: 31.4, 10: 24.3, 5: 15.1, 0: 0.0},
                7: {50: 100.0, 45: 90.0, 40: 66.2, 35: 66.2, 30: 42.3, 25: 36.5, 20: 30.9, 15: 27.0, 10: 20.1, 5: 14.1, 0: 0.0},
                8: {50: 100.0, 45: 90.0, 40: 80.0, 35: 67.2, 30: 46.8, 25: 29.2, 20: 21.4, 15: 19.5, 10: 16.5, 5: 11.0, 0: 0.0},
                9: {50: 100.0, 45: 90.0, 40: 80.0, 35: 39.2, 30: 23.7, 25:  8.1, 20: 11.3, 15: 11.2, 10:  7.3, 5:  5.2, 0: 0.0},
            },

            # First innings wicket penalties (3D: phase × ease × wickets)
            first_innings_wicket_penalty_3d={
                "powerplay": {
                    "well_ahead":  {0: 1.00, 1: 1.00, 2: 0.90, 3: 0.78, 4: 0.74, 5: 0.55, 6: 0.55, 7: 0.55, 8: 0.20, 9: 0.10, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 0.96, 2: 0.87, 3: 0.77, 4: 0.57, 5: 0.55, 6: 0.55, 7: 0.55, 8: 0.20, 9: 0.10, 10: 0.01},
                    "par":         {0: 1.00, 1: 0.99, 2: 0.89, 3: 0.88, 4: 0.77, 5: 0.76, 6: 0.78, 7: 0.59, 8: 0.59, 9: 0.59, 10: 0.01},
                    "behind":      {0: 1.00, 1: 0.94, 2: 0.90, 3: 0.89, 4: 0.81, 5: 0.85, 6: 0.62, 7: 0.63, 8: 0.63, 9: 0.63, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 0.92, 2: 0.83, 3: 0.81, 4: 0.71, 5: 0.57, 6: 0.88, 7: 0.69, 8: 0.69, 9: 0.69, 10: 0.01},
                },
                "middle": {
                    "well_ahead":  {0: 1.00, 1: 0.99, 2: 0.99, 3: 0.92, 4: 0.91, 5: 0.68, 6: 0.73, 7: 0.69, 8: 0.64, 9: 0.65, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 0.97, 2: 0.94, 3: 0.93, 4: 0.88, 5: 0.82, 6: 0.67, 7: 0.60, 8: 0.58, 9: 0.70, 10: 0.01},
                    "par":         {0: 1.00, 1: 0.99, 2: 0.96, 3: 0.92, 4: 0.88, 5: 0.85, 6: 0.74, 7: 0.67, 8: 0.65, 9: 0.54, 10: 0.01},
                    "behind":      {0: 1.00, 1: 0.98, 2: 0.97, 3: 0.89, 4: 0.86, 5: 0.79, 6: 0.75, 7: 0.74, 8: 0.59, 9: 0.55, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 1.00, 2: 0.98, 3: 0.90, 4: 0.86, 5: 0.84, 6: 0.72, 7: 0.71, 8: 0.60, 9: 0.48, 10: 0.47},
                },
                "setup": {
                    "well_ahead":  {0: 1.00, 1: 1.00, 2: 1.00, 3: 0.98, 4: 0.92, 5: 0.86, 6: 0.84, 7: 0.80, 8: 0.78, 9: 0.62, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 0.94, 2: 0.94, 3: 0.93, 4: 0.93, 5: 0.84, 6: 0.82, 7: 0.81, 8: 0.83, 9: 0.60, 10: 0.01},
                    "par":         {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.96, 5: 0.91, 6: 0.88, 7: 0.76, 8: 0.71, 9: 0.63, 10: 0.01},
                    "behind":      {0: 1.00, 1: 0.93, 2: 0.89, 3: 0.87, 4: 0.85, 5: 0.82, 6: 0.79, 7: 0.70, 8: 0.64, 9: 0.64, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 0.95, 2: 0.94, 3: 0.95, 4: 0.91, 5: 0.87, 6: 0.82, 7: 0.78, 8: 0.71, 9: 0.64, 10: 0.58},
                },
                "death": {
                    "well_ahead":  {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 0.90, 7: 0.90, 8: 0.90, 9: 0.10, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 1.00, 8: 1.00, 9: 0.90, 10: 0.01},
                    "par":         {0: 1.00, 1: 1.00, 2: 1.00, 3: 0.99, 4: 0.97, 5: 0.96, 6: 0.96, 7: 0.94, 8: 0.94, 9: 0.95, 10: 0.01},
                    "behind":      {0: 1.00, 1: 1.00, 2: 0.99, 3: 0.99, 4: 0.97, 5: 0.95, 6: 0.94, 7: 0.93, 8: 0.94, 9: 0.91, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.99, 5: 0.98, 6: 0.96, 7: 0.94, 8: 0.92, 9: 0.89, 10: 0.84},
                },
            },
            first_innings_score_midpoint=260.0,
            first_innings_score_beta=0.02,
            first_innings_wicket_penalty={
                0: 1.00, 1: 0.98, 2: 0.94, 3: 0.90,
                4: 0.85, 5: 0.78, 6: 0.70, 7: 0.60,
                8: 0.45, 9: 0.30, 10: 0.01,
            },

            # Chase penalties (2D: ease × wickets)
            chase_wicket_penalty_2d={
                "very_easy": {
                    0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.99,
                    5: 0.99, 6: 0.99, 7: 0.92, 8: 0.73, 9: 0.56, 10: 0.00,
                },
                "easy": {
                    0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
                    5: 0.98, 6: 0.89, 7: 0.88, 8: 0.62, 9: 0.12, 10: 0.00,
                },
                "comfortable": {
                    0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
                    5: 0.89, 6: 0.78, 7: 0.76, 8: 0.47, 9: 0.11, 10: 0.00,
                },
                "tough": {
                    0: 1.00, 1: 0.94, 2: 0.92, 3: 0.84, 4: 0.80,
                    5: 0.74, 6: 0.53, 7: 0.41, 8: 0.30, 9: 0.09, 10: 0.00,
                },
                "desperate": {
                    0: 1.00, 1: 0.74, 2: 0.58, 3: 0.47, 4: 0.35,
                    5: 0.24, 6: 0.20, 7: 0.12, 8: 0.05, 9: 0.04, 10: 0.00,
                },
            },
            chase_ease_thresholds={
                "very_easy": 3.0,
                "easy": 1.5,
                "comfortable": 1.0,
                "tough": 0.7,
                "desperate": 0.0,
            },
            wicket_penalty={
                0: 1.00, 1: 0.98, 2: 0.95, 3: 0.90,
                4: 0.82, 5: 0.72, 6: 0.60, 7: 0.45,
                8: 0.30, 9: 0.15, 10: 0.01,
            },

            # Chase parameters
            rrr_midpoint=5.5,
            rrr_beta=0.75,
            rrr_midpoint_slope=0.0,
            chase_wicket_weight=1.0,

            # SQI / confidence
            sqi_beta=0.45,
            sqi_shift=0.09,
            confidence_full_overs=25.0,
            score_std_early=89.8,
            score_std_late=23.8,
            wicket_decay_alpha=0.02,

            # Score projection caps (ODI range: runs rarely below 100)
            score_cap_min=100.0,
            score_cap_max=500.0,

            # Endgame / pressure (ODI: last 2 overs = 12 balls)
            endgame_balls=12,
            pressure_rrr_min=5.0,
            pressure_rrr_max=12.0,
        )

    @classmethod
    def _odi_female(cls) -> FormatConfig:
        """Female ODI constants — 506 matches, 2010–2025."""
        return cls(
            format_name="odi",
            gender="female",

            # Match structure
            total_overs=50,
            total_balls=300,
            balls_per_over=6,
            total_wickets=10,

            # Scoring benchmarks (empirical: avg 227.8, median 227)
            par_score=227.8,
            league_avg_score=227.0,
            bat_first_win_rate=0.508,

            # Phase system — ODI 4 phases
            phase_thresholds={
                "powerplay": 10,
                "middle": 34,
                "setup": 40,
                "death": 50,
            },
            phase_names=["powerplay", "middle", "setup", "death"],
            expected_run_rates={
                "powerplay": 4.17,
                "middle": 4.42,
                "setup": 4.98,
                "death": 6.12,
            },

            # Ease thresholds (same as T20)
            ease_thresholds={
                "well_ahead": 1.15,
                "ahead": 1.05,
                "par": 0.95,
                "behind": 0.85,
                "well_behind": 0.0,
            },

            # DLS resource table (empirical, 11 overs-remaining points)
            dls_resource_table={
                0: {50: 100.0, 45: 91.4, 40: 81.9, 35: 73.6, 30: 65.3, 25: 56.1, 20: 48.2, 15: 39.0, 10: 28.6, 5: 15.8, 0: 0.0},
                1: {50: 100.0, 45: 91.4, 40: 81.5, 35: 72.8, 30: 64.8, 25: 56.0, 20: 47.6, 15: 39.1, 10: 27.4, 5: 13.1, 0: 0.0},
                2: {50:  99.0, 45: 90.6, 40: 81.0, 35: 72.3, 30: 63.2, 25: 56.2, 20: 46.3, 15: 38.0, 10: 27.7, 5: 14.6, 0: 0.0},
                3: {50:  94.4, 45: 94.5, 40: 81.5, 35: 70.3, 30: 61.8, 25: 52.9, 20: 46.0, 15: 38.0, 10: 26.7, 5: 15.7, 0: 0.0},
                4: {50:  89.3, 45: 89.3, 40: 78.4, 35: 67.7, 30: 59.2, 25: 50.8, 20: 44.0, 15: 35.6, 10: 27.2, 5: 15.2, 0: 0.0},
                5: {50: 100.0, 45: 87.2, 40: 85.0, 35: 67.5, 30: 58.2, 25: 48.4, 20: 38.2, 15: 33.0, 10: 25.7, 5: 15.9, 0: 0.0},
                6: {50: 100.0, 45: 90.0, 40: 66.7, 35: 55.4, 30: 51.6, 25: 37.7, 20: 36.7, 15: 29.5, 10: 23.7, 5: 13.8, 0: 0.0},
                7: {50: 100.0, 45: 90.0, 40: 80.0, 35: 25.9, 30: 38.6, 25: 37.0, 20: 28.8, 15: 20.0, 10: 18.4, 5: 13.0, 0: 0.0},
                8: {50: 100.0, 45: 90.0, 40: 80.0, 35: 48.4, 30: 45.2, 25: 19.3, 20: 21.3, 15: 25.4, 10: 14.4, 5: 11.1, 0: 0.0},
                9: {50: 100.0, 45: 90.0, 40: 80.0, 35:  2.0, 30:  2.0, 25: 10.0, 20:  8.8, 15:  9.6, 10:  5.9, 5:  5.3, 0: 0.0},
            },

            # First innings wicket penalties (3D: phase × ease × wickets)
            first_innings_wicket_penalty_3d={
                "powerplay": {
                    "well_ahead":  {0: 1.00, 1: 1.00, 2: 0.92, 3: 1.00, 4: 0.87, 5: 0.87, 6: 0.87, 7: 0.30, 8: 0.20, 9: 0.10, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 0.94, 2: 0.84, 3: 0.72, 4: 0.71, 5: 0.72, 6: 0.72, 7: 0.72, 8: 0.20, 9: 0.10, 10: 0.01},
                    "par":         {0: 1.00, 1: 0.90, 2: 0.78, 3: 0.88, 4: 0.82, 5: 0.76, 6: 0.76, 7: 0.76, 8: 0.20, 9: 0.10, 10: 0.01},
                    "behind":      {0: 1.00, 1: 0.88, 2: 0.80, 3: 0.79, 4: 0.92, 5: 0.83, 6: 0.83, 7: 0.83, 8: 0.20, 9: 0.10, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 0.93, 2: 0.80, 3: 0.76, 4: 0.66, 5: 1.00, 6: 1.00, 7: 1.00, 8: 1.00, 9: 0.10, 10: 0.01},
                },
                "middle": {
                    "well_ahead":  {0: 1.00, 1: 0.96, 2: 0.94, 3: 0.93, 4: 0.87, 5: 0.83, 6: 0.64, 7: 0.50, 8: 0.47, 9: 0.48, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 0.96, 2: 0.96, 3: 0.94, 4: 0.90, 5: 0.92, 6: 0.64, 7: 0.66, 8: 0.54, 9: 0.56, 10: 0.01},
                    "par":         {0: 1.00, 1: 0.94, 2: 0.93, 3: 0.89, 4: 0.89, 5: 0.77, 6: 0.75, 7: 0.68, 8: 0.52, 9: 0.55, 10: 0.01},
                    "behind":      {0: 1.00, 1: 0.90, 2: 0.89, 3: 0.88, 4: 0.78, 5: 0.76, 6: 0.73, 7: 0.57, 8: 0.53, 9: 0.60, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 0.93, 2: 0.90, 3: 0.87, 4: 0.80, 5: 0.75, 6: 0.69, 7: 0.67, 8: 0.54, 9: 0.49, 10: 0.01},
                },
                "setup": {
                    "well_ahead":  {0: 1.00, 1: 0.93, 2: 0.92, 3: 0.90, 4: 0.89, 5: 0.84, 6: 0.84, 7: 0.74, 8: 0.78, 9: 0.78, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 0.98, 2: 0.99, 3: 0.96, 4: 0.98, 5: 0.91, 6: 0.82, 7: 0.81, 8: 0.80, 9: 0.91, 10: 0.01},
                    "par":         {0: 1.00, 1: 0.98, 2: 0.92, 3: 0.95, 4: 0.86, 5: 0.88, 6: 0.86, 7: 0.81, 8: 0.67, 9: 0.67, 10: 0.01},
                    "behind":      {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.97, 5: 0.95, 6: 0.92, 7: 0.72, 8: 0.70, 9: 0.80, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 0.94, 8: 0.90, 9: 0.79, 10: 0.76},
                },
                "death": {
                    "well_ahead":  {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 1.00, 8: 0.99, 9: 0.89, 10: 0.01},
                    "ahead":       {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 0.99, 8: 0.99, 9: 0.89, 10: 0.01},
                    "par":         {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 1.00, 8: 0.97, 9: 1.00, 10: 0.01},
                    "behind":      {0: 1.00, 1: 0.96, 2: 0.95, 3: 0.95, 4: 0.95, 5: 0.94, 6: 0.92, 7: 0.92, 8: 0.90, 9: 0.91, 10: 0.01},
                    "well_behind": {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 1.00, 8: 1.00, 9: 0.96, 10: 0.96},
                },
            },
            first_innings_score_midpoint=227.0,
            first_innings_score_beta=0.02,
            first_innings_wicket_penalty={
                0: 1.00, 1: 0.95, 2: 0.90, 3: 0.85,
                4: 0.80, 5: 0.73, 6: 0.65, 7: 0.55,
                8: 0.40, 9: 0.25, 10: 0.01,
            },

            # Chase penalties (2D: ease × wickets)
            chase_wicket_penalty_2d={
                "very_easy": {
                    0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
                    5: 1.00, 6: 0.98, 7: 0.84, 8: 0.90, 9: 0.25, 10: 0.00,
                },
                "easy": {
                    0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.96,
                    5: 0.94, 6: 0.94, 7: 0.78, 8: 0.58, 9: 0.39, 10: 0.00,
                },
                "comfortable": {
                    0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
                    5: 0.93, 6: 0.83, 7: 0.39, 8: 0.19, 9: 0.00, 10: 0.00,
                },
                "tough": {
                    0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.93,
                    5: 0.86, 6: 0.71, 7: 0.45, 8: 0.12, 9: 0.00, 10: 0.00,
                },
                "desperate": {
                    0: 1.00, 1: 0.73, 2: 0.43, 3: 0.23, 4: 0.26,
                    5: 0.33, 6: 0.16, 7: 0.13, 8: 0.04, 9: 0.01, 10: 0.00,
                },
            },
            chase_ease_thresholds={
                "very_easy": 3.0,
                "easy": 1.5,
                "comfortable": 1.0,
                "tough": 0.7,
                "desperate": 0.0,
            },
            wicket_penalty={
                0: 1.00, 1: 0.95, 2: 0.90, 3: 0.85,
                4: 0.78, 5: 0.68, 6: 0.55, 7: 0.40,
                8: 0.25, 9: 0.12, 10: 0.01,
            },

            # Chase parameters
            rrr_midpoint=5.0,
            rrr_beta=0.95,
            rrr_midpoint_slope=0.0,
            chase_wicket_weight=1.0,

            # SQI / confidence
            sqi_beta=0.50,
            sqi_shift=-0.06,
            confidence_full_overs=25.0,
            score_std_early=80.7,
            score_std_late=20.1,
            wicket_decay_alpha=0.02,

            # Score projection caps (ODI range)
            score_cap_min=80.0,
            score_cap_max=450.0,

            # Endgame / pressure
            endgame_balls=12,
            pressure_rrr_min=4.5,
            pressure_rrr_max=10.0,
        )

    @classmethod
    def from_league(cls, league: str) -> FormatConfig:
        """Resolve the appropriate FormatConfig for a league identifier.

        Mapping follows the ``format_type`` field in the CLI league config.

        Parameters
        ----------
        league : str
            League key (e.g. ``'bbl'``, ``'odi'``, ``'sa20'``).

        Returns
        -------
        FormatConfig
        """
        _ODI_LEAGUES = {"odi", "odis", "odi_male", "odi_female", "odm", "odm_male", "odm_female"}
        if league in _ODI_LEAGUES:
            gender = "female" if "female" in league else "male"
            return cls.odi(gender=gender)
        if league == "ipl":
            return cls.ipl()
        # All other leagues are T20
        return cls.t20()
