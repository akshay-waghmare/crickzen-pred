import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple

from bbl_pipeline.features.format_config import FormatConfig


class ResourceFeatureCalculator:
    """
    Calculates resource-based features inspired by DLS (Duckworth-Lewis-Stern) method.
    These features encode cricket domain knowledge about game state and expected outcomes.
    
    Key insight: The model benefits from understanding that the same score has very different
    implications depending on overs/wickets remaining. This helps especially for rare or 
    extreme game states the data rarely covers.

    Parameters
    ----------
    config : FormatConfig, optional
        Format-specific constants.  Defaults to ``FormatConfig.t20()`` so that
        all existing T20 call-sites keep working unchanged.
    """

    def __init__(self, config: Optional[FormatConfig] = None) -> None:
        if config is None:
            config = FormatConfig.t20()
        self.config = config

        # ── Expose every constant as an instance attribute so existing code
        #    that reads ``self.TOTAL_OVERS`` etc. keeps working.  The values
        #    come from the config rather than the class-level literals below
        #    (which are kept only for documentation purposes).
        self.TOTAL_OVERS = config.total_overs
        self.TOTAL_WICKETS = config.total_wickets
        self.BALLS_PER_OVER = config.balls_per_over
        self.TOTAL_BALLS = config.total_balls

        self.DLS_RESOURCE_TABLE = config.dls_resource_table

        self.PAR_SCORE_T20 = config.par_score

        self.HISTORICAL_BAT_FIRST_WIN_RATE = config.bat_first_win_rate
        self.LEAGUE_AVG_SCORE = config.league_avg_score
        self.WICKET_DECAY_ALPHA = config.wicket_decay_alpha

        self.SCORE_STD_EARLY = config.score_std_early
        self.SCORE_STD_LATE = config.score_std_late
        self.CONFIDENCE_FULL_OVERS = config.confidence_full_overs

        self.SQI_BETA = config.sqi_beta

        self.FIRST_INNINGS_SCORE_MIDPOINT = config.first_innings_score_midpoint
        self.FIRST_INNINGS_SCORE_BETA = config.first_innings_score_beta
        self.FIRST_INNINGS_WICKET_PENALTY = config.first_innings_wicket_penalty

        self.RRR_BETA = config.rrr_beta
        self.RRR_MIDPOINT = config.rrr_midpoint
        self.RRR_MIDPOINT_SLOPE = config.rrr_midpoint_slope
        self.CHASE_WICKET_WEIGHT = config.chase_wicket_weight
        # Target-category-aware sigmoid params (None = use single sigmoid)
        self.RRR_PARAMS_BY_TARGET_CAT = config.rrr_params_by_target_cat
        self.RRR_TARGET_CAT_BELOW = config.rrr_target_cat_below_threshold
        self.RRR_TARGET_CAT_ABOVE = config.rrr_target_cat_above_threshold

        self.WICKET_PENALTY = config.wicket_penalty

        self.CHASE_EASE_THRESHOLDS = config.chase_ease_thresholds
        self.WICKET_PENALTY_2D = config.chase_wicket_penalty_2d

        self.FIRST_INNINGS_PHASE_THRESHOLDS = config.phase_thresholds
        self.FIRST_INNINGS_EXPECTED_RR = config.expected_run_rates
        self.FIRST_INNINGS_EASE_THRESHOLDS = config.ease_thresholds
        self.FIRST_INNINGS_WICKET_PENALTY_3D = config.first_innings_wicket_penalty_3d

    # =====================================================================
    # CLASS-LEVEL CONSTANTS (kept for documentation only — __init__ above
    # overrides every attribute with config-driven values)
    # =====================================================================
    TOTAL_OVERS = 20
    TOTAL_WICKETS = 10
    BALLS_PER_OVER = 6
    TOTAL_BALLS = TOTAL_OVERS * BALLS_PER_OVER
    
    # DLS-style resource table (simplified version)
    # Format: wickets_lost -> {overs_remaining: resource_percentage}
    # Based on standard T20 resource percentages
    DLS_RESOURCE_TABLE = {
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
    }
    
    # Average T20 par score for resource calculation
    PAR_SCORE_T20 = 160.0
    
    # =========================================================================
    # FIRST INNINGS v2 CALIBRATION (Professional Model) - EDA VALIDATED
    # =========================================================================
    # Key insight: Don't jump directly to win probability.
    # Flow: Expected Score → Wicket Capability → Contextual Par → SQI → Win Prob
    
    # Historical batting first win rate (ILT20 EDA: 37.0%)
    HISTORICAL_BAT_FIRST_WIN_RATE = 0.37  # Validated from 12,361 first innings rows
    
    # League average score (ILT20 EDA: 165.0)
    LEAGUE_AVG_SCORE = 165.0  # Validated: avg=165.0, median=163.9
    
    # Wicket capability decay (affects future scoring potential, NOT probability)
    # wicket_capability = exp(-WICKET_DECAY_ALPHA * wickets_lost)
    # This reduces EXPECTED SCORE, not win probability directly
    # EDA: implied_alpha = 0.02-0.03 from actual score decay by wickets
    WICKET_DECAY_ALPHA = 0.025  # Gentle: 3 wkts = 0.93, 5 wkts = 0.88, 7 wkts = 0.84
    
    # Phase-dependent standard deviation for Score Quality Index
    # EDA INSIGHT: Variance INCREASES as innings progresses (not decreases!)
    # Powerplay std=14.3, Middle=23.5, Death=26.6
    # Early projections are formulaic (low variance), late scores have high variance
    SCORE_STD_EARLY = 15.0  # Low uncertainty early (projections are assumptions)
    SCORE_STD_LATE = 26.0   # High uncertainty late (actual variability in scores)
    
    # Confidence ramp-up for blending with historical prior
    # EDA: correlation plateaus around 12 overs (0.406 at 12 vs 0.348 at 4)
    CONFIDENCE_FULL_OVERS = 12.0  # Full model confidence after 12 overs
    
    # Score Quality Index (SQI) to Win Probability mapping
    # win_prob = sigmoid(SQI_BETA * SQI)
    # EDA: MSE minimized at beta=0.7-0.8 (tested 0.4-0.8)
    SQI_BETA = 0.75  # Controls steepness of SQI -> prob mapping
    
    # =========================================================================
    # FIRST INNINGS v1 CONSTANTS (kept for compatibility, used by v2)
    # =========================================================================
    # These are superseded by v2 professional model but kept as fallback
    FIRST_INNINGS_SCORE_MIDPOINT = 165.0  # Score where win_prob = 50%
    FIRST_INNINGS_SCORE_BETA = 0.04  # Logistic steepness
    FIRST_INNINGS_WICKET_PENALTY = {
        0: 1.00, 1: 1.00, 2: 0.95, 3: 0.85,
        4: 0.70, 5: 0.55, 6: 0.40, 7: 0.25,
        8: 0.12, 9: 0.05, 10: 0.01
    }
    
    # =========================================================================
    # SECOND INNINGS (CHASE) CALIBRATION (from ILT20 EDA)
    # =========================================================================
    # RRR-based logistic parameters
    # win_prob = 1 / (1 + exp(RRR_BETA * (RRR - RRR_MIDPOINT)))
    # At RRR=9.5, win_prob = 50%
    RRR_BETA = 0.7  # Controls steepness of transition
    RRR_MIDPOINT = 9.5  # RRR where win_prob = 50%
    
    # Wicket penalty factors for chase (calibrated from ILT20 EDA)
    # Based on actual win rates by wickets lost:
    # 0-3 wkts: 70-76% win rate (no penalty)
    # 4 wkts: 52% (25% penalty)
    # 5 wkts: 31% (50% penalty)
    # 6 wkts: 21% (65% penalty)
    # 7 wkts: 16% (75% penalty)
    # 8 wkts: 7% (88% penalty)
    # 9 wkts: 0% (95% penalty)
    # DEPRECATED: Use WICKET_PENALTY_2D for chase situations
    WICKET_PENALTY = {
        0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00,
        4: 0.75, 5: 0.50, 6: 0.35, 7: 0.25,
        8: 0.12, 9: 0.05, 10: 0.01
    }
    
    # =========================================================================
    # DYNAMIC 2D WICKET PENALTY (Jan 2026 - Empirically Calibrated from BBL Data)
    # =========================================================================
    # Wicket penalties vary SIGNIFICANTLY based on chase difficulty (CRR/RRR ratio)
    # 
    # Chase Ease Classification:
    #   very_easy:   CRR/RRR >= 3.0  (scoring 3x faster than needed)
    #   easy:        CRR/RRR >= 1.5  (scoring 1.5-3x faster than needed)
    #   comfortable: CRR/RRR >= 1.0  (on track to win)
    #   tough:       CRR/RRR >= 0.7  (slightly behind required rate)
    #   desperate:   CRR/RRR < 0.7   (way behind, unlikely to win)
    #
    # Key Insight: In easy chases, even 5+ wickets down barely affects win rate!
    #   - Very Easy, 5 wkts down: 83.2% win rate (vs 50% from flat penalty)
    #   - Easy, 7 wkts down: 88.1% win rate (vs 25% from flat penalty)
    # =========================================================================
    
    # Difficulty thresholds for CRR/RRR ratio
    CHASE_EASE_THRESHOLDS = {
        'very_easy': 3.0,    # CRR >= 3x RRR
        'easy': 1.5,         # CRR >= 1.5x RRR
        'comfortable': 1.0,  # CRR >= RRR (on track)
        'tough': 0.7,        # CRR >= 0.7x RRR
        'desperate': 0.0     # Below 0.7x (base case)
    }
    
    # 2D Wicket Penalty Table: [difficulty][wickets_lost] -> penalty multiplier
    # Derived from empirical BBL win rates (67,560 2nd innings samples)
    WICKET_PENALTY_2D = {
        'very_easy': {
            0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
            5: 0.88, 6: 0.76, 7: 0.56, 8: 0.24, 9: 0.05, 10: 0.00
        },
        'easy': {
            0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
            5: 1.00, 6: 1.00, 7: 1.00, 8: 0.44, 9: 0.22, 10: 0.00
        },
        'comfortable': {
            0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00,
            5: 1.00, 6: 1.00, 7: 1.00, 8: 0.62, 9: 0.74, 10: 0.00
        },
        'tough': {
            0: 1.00, 1: 0.93, 2: 0.90, 3: 0.88, 4: 0.76,
            5: 0.79, 6: 0.71, 7: 0.70, 8: 0.34, 9: 0.05, 10: 0.00
        },
        'desperate': {
            0: 1.00, 1: 0.72, 2: 0.46, 3: 0.35, 4: 0.21,
            5: 0.21, 6: 0.15, 7: 0.08, 8: 0.05, 9: 0.01, 10: 0.00
        }
    }
    
    def get_dynamic_wicket_penalty(
        self, 
        wickets_lost: int, 
        current_run_rate: float, 
        required_run_rate: float
    ) -> float:
        """
        Get wicket penalty with smooth interpolation based on chase difficulty.
        
        Uses CRR/RRR ratio to determine chase ease, then interpolates between
        adjacent difficulty levels for smooth transitions.
        
        Args:
            wickets_lost: Number of wickets fallen (0-10)
            current_run_rate: Current scoring rate
            required_run_rate: Required run rate to win
            
        Returns:
            Penalty multiplier (0.0 to 1.0)
        """
        wickets_lost = min(max(wickets_lost, 0), 10)
        
        # Handle edge cases
        if required_run_rate <= 0:
            # Already won or trivial chase - minimal penalty
            return self.WICKET_PENALTY_2D['very_easy'].get(wickets_lost, 0.01)
        
        if current_run_rate <= 0:
            # Not scoring - maximum penalty
            return self.WICKET_PENALTY_2D['desperate'].get(wickets_lost, 0.01)
        
        # Calculate chase ease ratio
        ease_ratio = current_run_rate / required_run_rate
        
        # Determine which two difficulty levels to interpolate between
        difficulty_levels = ['desperate', 'tough', 'comfortable', 'easy', 'very_easy']
        thresholds = [0.0, 0.7, 1.0, 1.5, 3.0]
        
        # Find the bracket
        lower_idx = 0
        for i, threshold in enumerate(thresholds):
            if ease_ratio >= threshold:
                lower_idx = i
        
        # Get the lower difficulty level
        lower_level = difficulty_levels[lower_idx]
        lower_penalty = self.WICKET_PENALTY_2D[lower_level].get(wickets_lost, 0.01)
        
        # If at the highest level or exactly on a boundary, return directly
        if lower_idx >= len(difficulty_levels) - 1:
            return lower_penalty
        
        # Get the upper difficulty level for interpolation
        upper_idx = lower_idx + 1
        upper_level = difficulty_levels[upper_idx]
        upper_penalty = self.WICKET_PENALTY_2D[upper_level].get(wickets_lost, 0.01)
        
        # Calculate interpolation weight (0 = lower, 1 = upper)
        lower_threshold = thresholds[lower_idx]
        upper_threshold = thresholds[upper_idx]
        
        if upper_threshold == lower_threshold:
            weight = 0.0
        else:
            weight = (ease_ratio - lower_threshold) / (upper_threshold - lower_threshold)
            weight = min(max(weight, 0.0), 1.0)
        
        # Linear interpolation
        interpolated_penalty = lower_penalty + weight * (upper_penalty - lower_penalty)
        
        return float(max(0.01, min(1.0, interpolated_penalty)))
    
    # =========================================================================
    # FIRST INNINGS 3D WICKET PENALTY (Jan 2026 - Empirically Calibrated)
    # =========================================================================
    # Wicket penalties vary by PHASE × SCORE POSITION × WICKETS
    # 
    # Phase Classification (by overs bowled):
    #   powerplay: 0-6 overs
    #   middle:    6-14 overs
    #   death:     14-18 overs
    #   final:     18-20 overs
    #
    # Score Position (ease = CRR / Expected RR):
    #   well_ahead: ease >= 1.15
    #   ahead:      ease >= 1.05
    #   par:        ease >= 0.95
    #   behind:     ease >= 0.85
    #   well_behind: ease < 0.85
    #
    # Key Insight: In death/final overs, wickets matter LESS, especially when
    # scoring above expected rate. The current score is "banked".
    # =========================================================================
    
    # Phase thresholds (overs bowled)
    FIRST_INNINGS_PHASE_THRESHOLDS = {
        'powerplay': 6,
        'middle': 14,
        'death': 18,
        'final': 20
    }
    
    # Expected run rate by phase (from BBL historical data)
    FIRST_INNINGS_EXPECTED_RR = {
        'powerplay': 7.5,
        'middle': 7.8,
        'death': 9.5,
        'final': 11.0
    }
    
    # Ease ratio thresholds for score position
    FIRST_INNINGS_EASE_THRESHOLDS = {
        'well_ahead': 1.15,
        'ahead': 1.05,
        'par': 0.95,
        'behind': 0.85,
        'well_behind': 0.0
    }
    
    # 3D Penalty Tables: PHASE -> EASE -> WICKETS -> penalty
    # Derived from BBL empirical win rates (73,875 first innings samples)
    FIRST_INNINGS_WICKET_PENALTY_3D = {
        'powerplay': {
            'well_ahead':  {0: 1.00, 1: 0.97, 2: 0.68, 3: 0.25, 4: 0.18, 5: 0.10, 6: 0.05, 7: 0.02, 8: 0.01, 9: 0.01, 10: 0.01},
            'ahead':       {0: 1.00, 1: 0.95, 2: 0.61, 3: 0.31, 4: 0.15, 5: 0.08, 6: 0.04, 7: 0.02, 8: 0.01, 9: 0.01, 10: 0.01},
            'par':         {0: 1.00, 1: 0.98, 2: 0.60, 3: 0.50, 4: 0.30, 5: 0.15, 6: 0.08, 7: 0.04, 8: 0.02, 9: 0.01, 10: 0.01},
            'behind':      {0: 1.00, 1: 0.91, 2: 0.67, 3: 0.47, 4: 0.11, 5: 0.05, 6: 0.02, 7: 0.01, 8: 0.01, 9: 0.01, 10: 0.01},
            'well_behind': {0: 1.00, 1: 0.90, 2: 0.56, 3: 0.31, 4: 0.05, 5: 0.01, 6: 0.01, 7: 0.01, 8: 0.01, 9: 0.01, 10: 0.01},
        },
        # =====================================================================
        # MIDDLE PHASE (overs 6-14): Empirically calibrated Jan 2026
        # Middle overs see less impact from wickets than previously modeled.
        # Projected scores remain stable even with 5-6 wickets down.
        # =====================================================================
        'middle': {
            'well_ahead':  {0: 1.00, 1: 0.98, 2: 0.96, 3: 0.97, 4: 0.96, 5: 0.91, 6: 0.85, 7: 0.75, 8: 0.60, 9: 0.40, 10: 0.01},
            'ahead':       {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.99, 5: 1.00, 6: 0.95, 7: 0.85, 8: 0.70, 9: 0.50, 10: 0.01},
            'par':         {0: 1.00, 1: 0.99, 2: 0.99, 3: 0.98, 4: 0.98, 5: 0.97, 6: 0.95, 7: 0.96, 8: 0.90, 9: 0.80, 10: 0.01},
            'behind':      {0: 1.00, 1: 0.99, 2: 0.99, 3: 0.98, 4: 0.98, 5: 0.97, 6: 0.98, 7: 1.00, 8: 0.96, 9: 0.90, 10: 0.01},
            'well_behind': {0: 1.00, 1: 1.00, 2: 1.00, 3: 0.97, 4: 0.97, 5: 0.97, 6: 0.89, 7: 0.87, 8: 0.98, 9: 0.95, 10: 0.01},
        },
        # =====================================================================
        # DEATH PHASE (overs 14-18): Empirically calibrated Jan 2026
        # Key insight: In death overs, wickets have MINIMAL impact on projected
        # score. The batters are set, and additional runs scale almost linearly
        # with balls remaining regardless of wickets lost.
        # =====================================================================
        'death': {
            'well_ahead':  {0: 1.00, 1: 1.00, 2: 1.00, 3: 0.95, 4: 0.96, 5: 0.94, 6: 0.92, 7: 0.90, 8: 0.85, 9: 0.80, 10: 0.01},
            'ahead':       {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 0.98, 8: 0.95, 9: 0.90, 10: 0.01},
            'par':         {0: 1.00, 1: 0.99, 2: 0.99, 3: 0.98, 4: 0.98, 5: 0.97, 6: 0.97, 7: 0.98, 8: 0.94, 9: 0.90, 10: 0.01},
            'behind':      {0: 1.00, 1: 1.00, 2: 0.99, 3: 0.99, 4: 0.99, 5: 0.98, 6: 0.98, 7: 0.97, 8: 1.00, 9: 0.95, 10: 0.01},
            'well_behind': {0: 1.00, 1: 1.00, 2: 1.00, 3: 0.95, 4: 0.95, 5: 0.93, 6: 0.88, 7: 0.88, 8: 0.86, 9: 0.81, 10: 0.01},
        },
        # =====================================================================
        # FINAL PHASE (overs 18-20): Empirically calibrated Jan 2026
        # In the final 2 overs, projected score is almost entirely determined
        # by banked runs. Additional runs from remaining balls are minimal,
        # so wickets matter even less than in death phase.
        # =====================================================================
        'final': {
            'well_ahead':  {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 0.99, 7: 0.98, 8: 0.95, 9: 0.90, 10: 0.01},
            'ahead':       {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 0.99, 7: 0.98, 8: 0.95, 9: 0.90, 10: 0.01},
            'par':         {0: 1.00, 1: 1.00, 2: 0.97, 3: 0.98, 4: 0.97, 5: 0.98, 6: 0.99, 7: 0.99, 8: 0.98, 9: 0.95, 10: 0.01},
            'behind':      {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 1.00, 8: 1.00, 9: 0.99, 10: 0.01},
            'well_behind': {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.98, 5: 0.96, 6: 0.93, 7: 0.91, 8: 0.88, 9: 0.84, 10: 0.01},
        },
    }
    
    def _get_venue_adjusted_midpoint(self, venue_avg_score: float = None) -> float:
        """Return venue-adjusted first-innings score midpoint.

        Formula: ``league_midpoint + 0.7 * (venue_avg - league_avg)``

        If *venue_avg_score* is ``None`` (unknown venue), the unadjusted
        league midpoint is returned.
        """
        midpoint = self.config.first_innings_score_midpoint
        if venue_avg_score is not None:
            midpoint = midpoint + 0.7 * (venue_avg_score - self.config.league_avg_score)
        return midpoint

    def get_first_innings_phase(self, overs_bowled: float) -> str:
        """Get the phase name for first innings based on overs bowled."""
        phase_names = self.config.phase_names
        thresholds = self.FIRST_INNINGS_PHASE_THRESHOLDS
        # Walk through phases in order; return first whose upper boundary
        # has not been reached yet, falling back to the last phase.
        for name in phase_names[:-1]:
            if overs_bowled < thresholds[name]:
                return name
        return phase_names[-1]
    
    def get_first_innings_ease_bucket(self, current_run_rate: float, phase: str) -> str:
        """
        Get the ease bucket based on CRR vs expected RR for the phase.
        
        Args:
            current_run_rate: Current scoring rate
            phase: Current phase name
            
        Returns:
            Ease bucket name ('well_ahead', 'ahead', 'par', 'behind', 'well_behind')
        """
        expected_rr = self.FIRST_INNINGS_EXPECTED_RR.get(phase, 8.0)
        
        if expected_rr <= 0:
            return 'par'
        
        ease_ratio = current_run_rate / expected_rr
        
        if ease_ratio >= self.FIRST_INNINGS_EASE_THRESHOLDS['well_ahead']:
            return 'well_ahead'
        elif ease_ratio >= self.FIRST_INNINGS_EASE_THRESHOLDS['ahead']:
            return 'ahead'
        elif ease_ratio >= self.FIRST_INNINGS_EASE_THRESHOLDS['par']:
            return 'par'
        elif ease_ratio >= self.FIRST_INNINGS_EASE_THRESHOLDS['behind']:
            return 'behind'
        else:
            return 'well_behind'
    
    def get_first_innings_dynamic_penalty(
        self,
        wickets_lost: int,
        overs_bowled: float,
        current_run_rate: float
    ) -> float:
        """
        Get first innings wicket penalty with smooth interpolation.
        
        Uses 3D lookup: PHASE × EASE × WICKETS with interpolation
        between phase boundaries and ease levels.
        
        Args:
            wickets_lost: Number of wickets fallen (0-10)
            overs_bowled: Overs completed (0-20)
            current_run_rate: Current scoring rate
            
        Returns:
            Penalty multiplier (0.0 to 1.0)
        """
        wickets_lost = min(max(wickets_lost, 0), 10)
        overs_bowled = min(max(overs_bowled, 0), self.TOTAL_OVERS)
        current_run_rate = max(0, current_run_rate)
        
        # Get current phase and ease bucket
        phase = self.get_first_innings_phase(overs_bowled)
        ease_bucket = self.get_first_innings_ease_bucket(current_run_rate, phase)
        
        # Get base penalty from 3D table
        phase_table = self.FIRST_INNINGS_WICKET_PENALTY_3D.get(phase, {})
        ease_table = phase_table.get(ease_bucket, {})
        base_penalty = ease_table.get(wickets_lost, 0.5)
        
        # Interpolate between phases for smoother transitions
        # Build phase_boundaries from config: [(name, start, end), ...]
        phase_boundaries = []
        prev_boundary = 0
        for pname in self.config.phase_names:
            upper = self.FIRST_INNINGS_PHASE_THRESHOLDS[pname]
            phase_boundaries.append((pname, prev_boundary, upper))
            prev_boundary = upper
        
        # Find if we're near a phase boundary (within 1 over)
        for i, (p_name, p_start, p_end) in enumerate(phase_boundaries):
            if p_name == phase:
                # Check if near the end of this phase
                if overs_bowled >= p_end - 1 and i < len(phase_boundaries) - 1:
                    next_phase = phase_boundaries[i + 1][0]
                    next_ease_bucket = self.get_first_innings_ease_bucket(current_run_rate, next_phase)
                    next_table = self.FIRST_INNINGS_WICKET_PENALTY_3D.get(next_phase, {})
                    next_ease_table = next_table.get(next_ease_bucket, {})
                    next_penalty = next_ease_table.get(wickets_lost, 0.5)
                    
                    # Blend based on proximity to boundary
                    blend_weight = (overs_bowled - (p_end - 1)) / 1.0
                    blend_weight = min(max(blend_weight, 0), 1)
                    base_penalty = base_penalty * (1 - blend_weight) + next_penalty * blend_weight
                break
        
        # Interpolate between ease levels for smoother transitions
        expected_rr = self.FIRST_INNINGS_EXPECTED_RR.get(phase, 8.0)
        if expected_rr > 0:
            ease_ratio = current_run_rate / expected_rr
            
            # Define ease levels and thresholds for interpolation
            ease_levels = ['well_behind', 'behind', 'par', 'ahead', 'well_ahead']
            ease_thresholds = [
                self.FIRST_INNINGS_EASE_THRESHOLDS.get('well_behind', 0.0),
                self.FIRST_INNINGS_EASE_THRESHOLDS.get('behind', 0.85),
                self.FIRST_INNINGS_EASE_THRESHOLDS.get('par', 0.95),
                self.FIRST_INNINGS_EASE_THRESHOLDS.get('ahead', 1.05),
                self.FIRST_INNINGS_EASE_THRESHOLDS.get('well_ahead', 1.15),
            ]
            
            # Find bracket for interpolation
            lower_idx = 0
            for i, threshold in enumerate(ease_thresholds):
                if ease_ratio >= threshold:
                    lower_idx = i
            
            if lower_idx < len(ease_levels) - 1:
                lower_ease = ease_levels[lower_idx]
                upper_ease = ease_levels[lower_idx + 1]
                
                lower_table = phase_table.get(lower_ease, {})
                upper_table = phase_table.get(upper_ease, {})
                
                lower_pen = lower_table.get(wickets_lost, 0.5)
                upper_pen = upper_table.get(wickets_lost, 0.5)
                
                lower_thresh = ease_thresholds[lower_idx]
                upper_thresh = ease_thresholds[lower_idx + 1]
                
                if upper_thresh > lower_thresh:
                    weight = (ease_ratio - lower_thresh) / (upper_thresh - lower_thresh)
                    weight = min(max(weight, 0), 1)
                    base_penalty = lower_pen + weight * (upper_pen - lower_pen)
        
        return float(max(0.01, min(1.0, base_penalty)))
    
    def calculate_resource_percentage(self, overs_remaining: float, wickets_lost: int) -> float:
        """
        Calculate the resource percentage remaining using interpolated DLS values.
        
        Args:
            overs_remaining: Overs remaining (can be fractional, e.g., 15.3 = 15 overs 3 balls)
            wickets_lost: Number of wickets lost (0-9)
            
        Returns:
            Resource percentage (0-100)
        """
        wickets_lost = min(max(wickets_lost, 0), 9)
        overs_remaining = max(0, min(overs_remaining, self.TOTAL_OVERS))
        
        # Get resource values for this wicket level
        resource_curve = self.DLS_RESOURCE_TABLE[wickets_lost]
        overs_keys = sorted(resource_curve.keys())
        
        # Linear interpolation between known points
        if overs_remaining >= overs_keys[-1]:
            return resource_curve[overs_keys[-1]]
        if overs_remaining <= overs_keys[0]:
            return resource_curve[overs_keys[0]]
            
        # Find surrounding points
        lower_over = max(k for k in overs_keys if k <= overs_remaining)
        upper_over = min(k for k in overs_keys if k >= overs_remaining)
        
        if lower_over == upper_over:
            return resource_curve[lower_over]
            
        # Interpolate
        lower_resource = resource_curve[lower_over]
        upper_resource = resource_curve[upper_over]
        
        ratio = (overs_remaining - lower_over) / (upper_over - lower_over)
        return lower_resource + ratio * (upper_resource - lower_resource)
    
    def calculate_expected_score(self, current_score: int, overs_bowled: float, 
                                  wickets_lost: int) -> float:
        """
        Calculate expected final score based on current state and resource remaining.
        
        Uses a projection based on current run rate weighted by resources consumed,
        WITH regression toward the mean. Early projections are heavily regressed
        toward par score (160) to avoid unrealistic projections like 400+.
        
        The regression factor increases as more overs are bowled (more data = more trust
        in the current run rate).
        """
        # If all out (10 wickets), the innings is over - return actual score
        if wickets_lost >= 10:
            return float(current_score)
        
        if overs_bowled <= 0:
            return self.PAR_SCORE_T20
        
        # If innings is complete (20 overs), return actual score
        if overs_bowled >= self.TOTAL_OVERS:
            return float(current_score)
            
        overs_remaining = self.TOTAL_OVERS - overs_bowled
        
        # Resources used and remaining
        resource_at_start = 100.0
        resource_remaining = self.calculate_resource_percentage(overs_remaining, wickets_lost)
        resource_used = resource_at_start - resource_remaining
        
        if resource_used <= 0:
            return self.PAR_SCORE_T20
            
        # Raw projection based on runs per resource
        runs_per_resource = current_score / resource_used
        raw_projection = current_score + (runs_per_resource * resource_remaining)
        
        # Regression toward the mean
        # Weight: how much to trust the current trajectory vs par score
        # Early overs (2-3): trust ~20% trajectory, 80% par
        # Middle overs (10): trust ~60% trajectory, 40% par  
        # Late overs (17+): trust ~95% trajectory, 5% par
        trajectory_weight = min(0.95, overs_bowled / 20.0)
        
        # Regressed projection
        regressed_projection = (trajectory_weight * raw_projection) + ((1 - trajectory_weight) * self.PAR_SCORE_T20)
        
        # Also cap the projection at reasonable bounds (config-driven)
        return max(self.config.score_cap_min, min(self.config.score_cap_max, regressed_projection))
    
    def calculate_match_phase(self, over: int) -> Tuple[str, int, int, int]:
        """
        Determine match phase and return one-hot encoded indicators.
        
        Uses a simplified 3-phase system (powerplay / middle / death)
        derived from the config's phase thresholds.  For T20 the boundaries
        are at overs 6 and 15; for ODI they follow config boundaries.
        
        Returns:
            Tuple of (phase_name, is_powerplay, is_middle, is_death)
        """
        pp_boundary = self.FIRST_INNINGS_PHASE_THRESHOLDS[self.config.phase_names[0]]
        # Death starts 1 over after the second phase's upper boundary
        mid_boundary = self.FIRST_INNINGS_PHASE_THRESHOLDS[self.config.phase_names[1]] + 1
        
        if over < pp_boundary:
            return ('powerplay', 1, 0, 0)
        elif over < mid_boundary:
            return ('middle', 0, 1, 0)
        else:
            return ('death', 0, 0, 1)
    
    def calculate_pressure_index(
        self,
        innings: int,
        current_score: int,
        overs_bowled: float,
        wickets_lost: int,
        target_runs: int = None,
        current_run_rate: float = None
    ) -> float:
        """
        Calculate a pressure index that captures match situation urgency.
        
        Key improvements:
        - Overs-weighted: Early deficits matter less than late deficits
        - CRR vs RRR ratio: Compares current momentum to required rate
        - Late wickets hurt more: Wicket pressure scales with match progress
        
        For 1st innings: Based on scoring rate relative to par, weighted by overs
        For 2nd innings: Based on RRR/CRR ratio and resources remaining
        
        Returns:
            Pressure index (0-1 scale, higher = more pressure on batting team)
        """
        overs_remaining = self.TOTAL_OVERS - overs_bowled
        overs_progress = overs_bowled / self.TOTAL_OVERS  # 0 to 1

        # -------------------------
        # FIRST INNINGS PRESSURE
        # -------------------------
        if innings == 1:
            # Expected score at this point based on par
            expected_score_so_far = self.PAR_SCORE_T20 * overs_progress
            score_diff = expected_score_so_far - current_score

            # Overs-weighted deficit: being 20 behind in over 2 is fine, 
            # being 20 behind in over 18 is bad
            run_pressure = max(0, (score_diff / 40) * overs_progress)

            # Wicket pressure weighted by overs (late wickets hurt more)
            # Losing 3 wickets in powerplay is recoverable, losing 3 in death is devastating
            wicket_pressure = overs_progress * (wickets_lost / self.TOTAL_WICKETS)

            pressure = (0.65 * run_pressure) + (0.35 * wicket_pressure)

            return min(1.0, max(0.0, pressure))

        # -------------------------
        # SECOND INNINGS PRESSURE
        # -------------------------
        if target_runs is None:
            return 0.5

        runs_required = target_runs - current_score

        if runs_required <= 0:
            return 0.0  # Already won

        if overs_remaining <= 0:
            return 1.0  # No overs left and haven't won

        required_rate = runs_required / overs_remaining

        # CRR vs RRR ratio - this is the key insight
        # If CRR > RRR, team is ahead of the game (low pressure)
        # If RRR > CRR, team needs to accelerate (high pressure)
        if current_run_rate is not None and current_run_rate > 0:
            # rr_ratio > 1 means RRR exceeds CRR (need to speed up)
            rr_ratio = required_rate / current_run_rate
            # Map ratio to pressure: 
            # ratio 1.0 = on track (0.0 pressure)
            # ratio 1.6 = need 60% more speed (1.0 pressure)
            rate_pressure = min(1.0, max(0.0, (rr_ratio - 1.0) / 0.6))
        else:
            # Fallback: absolute RRR-based pressure
            # RRR min = comfortable (0), RRR max = maximum pressure (1)
            rate_pressure = min(1.0, max(0.0, (required_rate - self.config.pressure_rrr_min) / (self.config.pressure_rrr_max - self.config.pressure_rrr_min)))

        # Check if chase is even feasible
        resource_pct = self.calculate_resource_percentage(overs_remaining, wickets_lost)
        max_gettable = (resource_pct / 100) * self.PAR_SCORE_T20 * 1.3

        if runs_required > max_gettable:
            return 1.0  # Practically impossible

        # Wickets matter more in late overs
        # 5 down in over 10 is survivable, 5 down in over 18 is critical
        wicket_pressure = overs_progress * (wickets_lost / self.TOTAL_WICKETS)

        # Weight more towards run rate in chases (it's the primary constraint)
        pressure = (0.75 * rate_pressure) + (0.25 * wicket_pressure)

        return min(1.0, max(0.0, pressure))
    
    def calculate_resource_win_probability(
        self,
        innings: int,
        expected_final_score: float,
        target_runs: float,
        resource_pct: float,
        current_run_rate: float,
        required_run_rate: float,
        current_score: float = 0,
        balls_remaining: int = None,
        wickets_lost: int = None,
        venue_avg_score: float = None
    ) -> float:
        """
        Returns a data-calibrated win probability estimate.
        
        For 2nd innings, uses Required Run Rate as the primary difficulty metric,
        with wicket penalty applied as a multiplier. Parameters calibrated from
        ILT20 historical data (EDA).
        
        Key findings from EDA:
        - RRR 7-8: 80% win rate
        - RRR 9-10: 44% win rate  
        - RRR 10-12: 37% win rate
        - Wicket penalty kicks in hard after 4 wickets
        
        Args:
            innings: Current innings (1 or 2)
            expected_final_score: Projected final score based on current trajectory
            target_runs: Target to chase (only relevant for 2nd innings)
            resource_pct: Remaining resource percentage (DLS-style)
            current_run_rate: Current run rate
            required_run_rate: Required run rate to win (2nd innings only)
            current_score: Current score
            balls_remaining: Actual balls remaining in innings (for endgame logic)
            wickets_lost: Number of wickets fallen (0-9)
            venue_avg_score: Average first-innings score at this venue (optional).
                If provided, the SQI contextual par is venue-adjusted.
            
        Returns:
            Win probability estimate (0.001 to 0.999)
        """
        # Get actual wickets (default to 0 if not provided)
        actual_wickets_lost = wickets_lost if wickets_lost is not None else 0
        
        # =====================================================================
        # INNINGS 1: Professional v2 Model (EDA-Calibrated)
        # =====================================================================
        # Key insight: Don't map score directly to probability.
        # Flow: Expected Score → Wicket Capability → SQI → Win Prob
        # Then blend with historical prior based on confidence (overs bowled)
        # =====================================================================
        if innings == 1:
            # Step 0: Calculate overs context
            if balls_remaining is not None:
                overs_bowled = self.TOTAL_OVERS - (balls_remaining / 6.0)
            else:
                overs_bowled = (1 - resource_pct / 100.0) * self.TOTAL_OVERS
            overs_progress = overs_bowled / self.TOTAL_OVERS  # 0 to 1
            
            # -----------------------------------------------------------------
            # Step 1: Wicket capability decay (PHASE + SCORE POSITION AWARE)
            # -----------------------------------------------------------------
            # CRITICAL FIX (Jan 2026): Use 3D empirical penalty tables
            # Wickets matter LESS in death overs when scoring above expected rate
            # The current score is "banked" - only penalize future potential
            if overs_bowled >= self.TOTAL_OVERS - 0.5:
                # Innings complete - use actual score directly, no wicket penalty
                adjusted_expected_score = expected_final_score
            else:
                # Get 3D dynamic penalty (Phase × Ease × Wickets)
                # This replaces the old phase_multiplier + exponential decay approach
                wicket_penalty = self.get_first_innings_dynamic_penalty(
                    wickets_lost=actual_wickets_lost,
                    overs_bowled=overs_bowled,
                    current_run_rate=current_run_rate
                )
                
                # Apply penalty ONLY to the remaining potential (future runs)
                # This ensures we never penalize runs already on the board
                additional_runs_projected = max(0, expected_final_score - current_score)
                adjusted_additional_runs = additional_runs_projected * wicket_penalty
                
                adjusted_expected_score = current_score + adjusted_additional_runs
            
            # -----------------------------------------------------------------
            # Step 2: Calculate Score Quality Index (SQI)
            # -----------------------------------------------------------------
            # SQI = (adjusted_score - contextual_par) / phase_std_dev
            # A z-score telling us how far above/below par we are
            
            # Improvement: Contextual par uses venue-adjusted midpoint when
            # venue data is available; otherwise falls back to league avg.
            contextual_par = self._get_venue_adjusted_midpoint(venue_avg_score)
            
            # Phase-dependent standard deviation (EDA: variance INCREASES with overs)
            # Powerplay: std=15 (projections are assumptions)
            # Death overs: std=26 (actual variability in outcomes)
            phase_std = self.SCORE_STD_EARLY + overs_progress * (self.SCORE_STD_LATE - self.SCORE_STD_EARLY)
            
            # Calculate SQI (score quality index)
            sqi = (adjusted_expected_score - contextual_par) / phase_std
            
            # -----------------------------------------------------------------
            # Step 3: SQI to Win Probability (sigmoid mapping)
            # -----------------------------------------------------------------
            # Improvement: Shift sigmoid center to encode bat-first disadvantage
            # Instead of SQI=0 → 50%, we shift left by 0.35 to reflect 37% baseline
            # This means SQI=0.35 → 50%, SQI=0 → ~43%
            sqi_shifted = sqi - self.config.sqi_shift
            sqi_based_prob = 1.0 / (1.0 + np.exp(-self.SQI_BETA * sqi_shifted))
            
            # -----------------------------------------------------------------
            # Step 4: Confidence-weighted blend with historical prior
            # -----------------------------------------------------------------
            # Early overs: lean toward historical bat-first win rate (37%)
            # Late overs: trust the SQI-based probability
            # EDA: confidence plateaus around 12 overs
            confidence = min(1.0, overs_bowled / self.CONFIDENCE_FULL_OVERS)
            
            # Blend: (1-conf)*prior + conf*model
            win_prob = (1 - confidence) * self.HISTORICAL_BAT_FIRST_WIN_RATE + confidence * sqi_based_prob
            
            # -----------------------------------------------------------------
            # Step 5: Dynamic clamp range (more expressive late)
            # -----------------------------------------------------------------
            # Late innings with dominant position (215 on board) should reach 97-98%
            lower_clamp = 0.05
            upper_clamp = 0.95 + 0.03 * confidence  # 0.95 early → 0.98 at full confidence
            
            return float(max(lower_clamp, min(upper_clamp, win_prob)))

        # -------------------------------------
        # INNINGS 2: Team chasing a target
        # -------------------------------------
        if target_runs is None:
            return 0.5

        runs_required = target_runs - current_score

        # If the chase is already over
        if runs_required <= 0:
            return 1.0
        
        # Use actual balls remaining if provided, otherwise estimate from resource_pct
        if balls_remaining is None:
            overs_remaining = (resource_pct / 100.0) * self.TOTAL_OVERS
            balls_remaining = int(overs_remaining * 6)

        # -------------------------------------
        # END-GAME SPECIAL CASE: Last 2 overs
        # -------------------------------------
        # Use empirical final-over lookup if available (balls <= 6)
        if (
            balls_remaining > 0
            and balls_remaining <= 6
            and self.config.final_over_lookup is not None
        ):
            runs_needed_key = min(int(runs_required), 20)
            wickets_in_hand = max(0, 10 - actual_wickets_lost)
            lookup = self.config.final_over_lookup
            if runs_needed_key in lookup and wickets_in_hand in lookup[runs_needed_key]:
                return float(max(0.02, min(0.98, lookup[runs_needed_key][wickets_in_hand])))

        if balls_remaining > 0 and balls_remaining <= self.config.endgame_balls and runs_required <= balls_remaining * 2:
            # Final over (<=6 balls): use empirical lookup table
            if balls_remaining <= 6:
                from .win_prob_lookup_tables import get_final_over_win_prob
                wickets_in_hand = 10 - actual_wickets_lost
                lookup_prob = get_final_over_win_prob(int(runs_required), wickets_in_hand)
                return float(max(0.05, min(0.95, lookup_prob)))

            # Existing sigmoid for overs 18-19 (balls > 6)
            runs_per_ball_needed = runs_required / balls_remaining
            # Logistic centered at 1.5 rpb
            endgame_prob = 1.0 / (1.0 + np.exp(4 * (runs_per_ball_needed - 1.5)))
            
            # Use dynamic wicket penalty based on chase ease
            # Calculate balls bowled from balls remaining
            balls_bowled_approx = self.TOTAL_BALLS - balls_remaining
            effective_crr = (current_score / max(1, balls_bowled_approx)) * 6.0 if balls_bowled_approx > 0 else current_run_rate
            effective_rrr = runs_per_ball_needed * 6.0  # Convert rpb to run rate
            wicket_mult = self.get_dynamic_wicket_penalty(
                actual_wickets_lost, effective_crr, effective_rrr
            )
            wicket_mult = 1.0 + self.CHASE_WICKET_WEIGHT * (wicket_mult - 1.0)
            
            return float(max(0.05, min(0.95, endgame_prob * wicket_mult)))

        # -------------------------------------
        # CRITICAL: Handle edge cases
        # -------------------------------------
        if resource_pct <= 0.1:
            return 1.0 if runs_required <= 0 else 0.001

        # If no balls remaining, match is effectively over
        if balls_remaining <= 0:
            return 1.0 if runs_required <= 0 else 0.001

        # -------------------------------------
        # RRR-BASED WIN PROBABILITY (Data-Calibrated)
        # -------------------------------------
        # Calculate effective RRR
        overs_remaining = balls_remaining / 6.0
        if overs_remaining > 0:
            effective_rrr = runs_required / overs_remaining
        else:
            effective_rrr = 50.0  # Effectively impossible
        
        # Base probability from RRR using logistic function
        # Select sigmoid params based on target category if configured.
        # Per-over adaptive midpoint: midpoint shifts up in later overs
        # (IPL teams sustain higher RRR in death overs)
        if self.RRR_PARAMS_BY_TARGET_CAT is not None and target_runs is not None:
            target_above_par = target_runs - self.PAR_SCORE_T20
            if target_above_par < self.RRR_TARGET_CAT_BELOW:
                cat = "below_par"
            elif target_above_par > self.RRR_TARGET_CAT_ABOVE:
                cat = "above_par"
            else:
                cat = "on_par"
            cat_p = self.RRR_PARAMS_BY_TARGET_CAT[cat]
            rrr_midpoint       = cat_p["midpoint"]
            rrr_midpoint_slope = cat_p["slope"]
            rrr_beta           = cat_p["beta"]
        else:
            rrr_midpoint       = self.RRR_MIDPOINT
            rrr_midpoint_slope = self.RRR_MIDPOINT_SLOPE
            rrr_beta           = self.RRR_BETA

        overs_bowled = self.TOTAL_OVERS - overs_remaining
        effective_midpoint = rrr_midpoint + rrr_midpoint_slope * overs_bowled
        exponent = rrr_beta * (effective_rrr - effective_midpoint)
        exponent = np.clip(exponent, -700, 700)
        base_prob = 1.0 / (1.0 + np.exp(exponent))
        
        # -------------------------------------
        # WICKET PENALTY (Dynamic 2D - Chase Difficulty Aware)
        # -------------------------------------
        # Uses CRR/RRR ratio to determine chase ease, then applies
        # appropriate wicket penalty from empirically-calibrated 2D table.
        # chase_wicket_weight scales the effect: 0.0 disables (IPL), 1.0 full.
        wicket_mult = self.get_dynamic_wicket_penalty(
            actual_wickets_lost, current_run_rate, effective_rrr
        )
        wicket_mult = 1.0 + self.CHASE_WICKET_WEIGHT * (wicket_mult - 1.0)
        
        # -------------------------------------
        # CURRENT RUN RATE ADJUSTMENT
        # -------------------------------------
        # If batting above required rate, slight boost; below, slight penalty
        # Effect is muted early in innings (CRR volatile).
        # Also scaled by chase_wicket_weight (same control knob).
        rate_factor = 1.0
        if self.CHASE_WICKET_WEIGHT > 0 and required_run_rate > 0 and current_run_rate > 0:
            overs_weight = min(1.0, overs_bowled / 10.0)
            rate_ratio = current_run_rate / required_run_rate
            # Bound the impact: between 0.90 and 1.10 multiplier
            raw_rate_factor = min(1.10, max(0.90, rate_ratio))
            rate_factor = 1.0 + (raw_rate_factor - 1.0) * overs_weight
        
        # -------------------------------------
        # COMBINE ALL FACTORS
        # -------------------------------------
        win_prob = base_prob * wicket_mult * rate_factor

        # Final clamp
        return float(max(0.001, min(0.999, win_prob)))
    
    def calculate_all_features(self, innings: int, over: int, ball: int,
                                current_score: int, wickets_lost: int,
                                target_runs: int = None) -> Dict[str, Any]:
        """
        Calculate all resource-based features for a given match state.
        
        Args:
            innings: Current innings (1 or 2)
            over: Current over (0-indexed, so over=5 means 6th over)
            ball: Ball number in current over (1-6)
            current_score: Runs scored so far
            wickets_lost: Wickets fallen (0-9)
            target_runs: Target to chase (only for 2nd innings)
            
        Returns:
            Dictionary of all resource-based features
        """
        # Basic derived features
        overs_bowled = over + (ball / self.BALLS_PER_OVER)
        balls_bowled = over * self.BALLS_PER_OVER + ball
        overs_remaining = self.TOTAL_OVERS - overs_bowled
        balls_remaining = self.TOTAL_BALLS - balls_bowled
        wickets_remaining = self.TOTAL_WICKETS - wickets_lost
        
        # Resource percentage
        resource_pct = self.calculate_resource_percentage(overs_remaining, wickets_lost)
        
        # Run rates
        current_run_rate = (current_score / overs_bowled) if overs_bowled > 0 else 0.0
        
        # Second innings specific
        required_run_rate = 0.0
        run_rate_differential = 0.0
        runs_required = 0
        
        if innings == 2 and target_runs is not None:
            runs_required = target_runs - current_score
            required_run_rate = (runs_required / overs_remaining) if overs_remaining > 0 else 99.0
            # Positive = batting team ahead (scoring faster than required)
            run_rate_differential = current_run_rate - required_run_rate
        
        # Match phase
        phase_name, is_powerplay, is_middle, is_death = self.calculate_match_phase(over)
        
        # Expected score projection
        expected_final_score = self.calculate_expected_score(current_score, overs_bowled, wickets_lost)
        
        # Pressure index - match training (processor.py) by NOT passing current_run_rate.
        # Training uses absolute RRR-based formula; passing CRR here causes train-serve skew
        # (early over high CRR makes pressure = 0 even when RRR is very high).
        pressure_index = self.calculate_pressure_index(
            innings, current_score, overs_bowled, wickets_lost, target_runs
        )
        
        # Win probability estimate using the dedicated method
        resource_win_prob = self.calculate_resource_win_probability(
            innings=innings,
            expected_final_score=expected_final_score,
            target_runs=target_runs,
            resource_pct=resource_pct,
            current_run_rate=current_run_rate,
            required_run_rate=required_run_rate,
            current_score=current_score,
            balls_remaining=balls_remaining,
            wickets_lost=wickets_lost
        )
        
        return {
            # Core resource features
            'overs_remaining': overs_remaining,
            'balls_remaining': balls_remaining,
            'wickets_remaining': wickets_remaining,
            'resource_pct': resource_pct,
            
            # Run rate features
            'current_run_rate': current_run_rate,
            'required_run_rate': required_run_rate,
            'run_rate_differential': run_rate_differential,
            
            # Projection features
            'expected_final_score': expected_final_score,
            'runs_required': runs_required,
            
            # Phase features
            'is_powerplay': is_powerplay,
            'is_middle_overs': is_middle,
            'is_death_overs': is_death,
            
            # Pressure and probability features
            'pressure_index': pressure_index,
            'resource_win_prob': resource_win_prob,
        }


class StatsCalculator:
    """
    Calculates rolling statistics and global averages for players and venues.
    Ensures strict temporal separation by shifting statistics to use only past data.
    """

    def calculate_rolling_batting_stats(self, df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
        """
        Calculates rolling batting stats (runs, balls, dismissals) for each batsman.
        Assumes df has columns: ['match_id', 'start_date', 'batsman', 'runs', 'balls_faced', 'is_out']
        """
        # Ensure sorted by date
        df = df.sort_values('start_date')
        
        # Group by batsman
        grouped = df.groupby('batsman')
        
        # Calculate rolling sums (shifted by 1 to exclude current match)
        # We need to aggregate per match first if the input is ball-by-ball
        # Assuming input is already aggregated per batsman-match for this calculation
        
        rolling_stats = grouped[['runs', 'balls_faced', 'is_out']].apply(
            lambda x: x.shift(1).rolling(window=window, min_periods=1).sum()
        )
        
        # Calculate metrics
        # Avoid division by zero
        batting_avg = rolling_stats['runs'] / rolling_stats['is_out'].replace(0, np.nan)
        strike_rate = (rolling_stats['runs'] / rolling_stats['balls_faced'].replace(0, np.nan)) * 100
        
        # Fill NaNs (first match or no dismissals)
        # For avg with 0 dismissals, use runs (infinity in theory, but runs is a proxy) or NaN?
        # Usually we handle this with a fallback or keep as NaN to be filled later.
        
        result = pd.DataFrame({
            'batsman_rolling_avg': batting_avg,
            'batsman_rolling_sr': strike_rate
        })
        
        # Reset index to match original df (drop the grouping key)
        if isinstance(result.index, pd.MultiIndex):
            result = result.reset_index(level=0, drop=True)
        
        return result

    def calculate_rolling_bowling_stats(self, df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
        """
        Calculates rolling bowling stats (runs_conceded, balls_bowled, wickets) for each bowler.
        Assumes df has columns: ['match_id', 'start_date', 'bowler', 'runs_conceded', 'balls_bowled', 'wickets']
        """
        df = df.sort_values('start_date')
        grouped = df.groupby('bowler')
        
        rolling_stats = grouped[['runs_conceded', 'balls_bowled', 'wickets']].apply(
            lambda x: x.shift(1).rolling(window=window, min_periods=1).sum()
        )
        
        # Calculate metrics
        economy_rate = (rolling_stats['runs_conceded'] / rolling_stats['balls_bowled'].replace(0, np.nan)) * 6
        strike_rate = rolling_stats['balls_bowled'] / rolling_stats['wickets'].replace(0, np.nan)
        
        result = pd.DataFrame({
            'bowler_rolling_econ': economy_rate,
            'bowler_rolling_sr': strike_rate
        })
        
        # Reset index to match original df
        if isinstance(result.index, pd.MultiIndex):
            result = result.reset_index(level=0, drop=True)
        
        return result

    def calculate_global_averages(self, df_batting: pd.DataFrame, df_bowling: pd.DataFrame) -> Dict[str, float]:
        """
        Calculates global averages for fallbacks.
        """
        global_batting_avg = df_batting['runs'].sum() / df_batting['is_out'].sum()
        global_batting_sr = (df_batting['runs'].sum() / df_batting['balls_faced'].sum()) * 100
        
        global_bowling_econ = (df_bowling['runs_conceded'].sum() / df_bowling['balls_bowled'].sum()) * 6
        global_bowling_sr = df_bowling['balls_bowled'].sum() / df_bowling['wickets'].sum()
        
        return {
            'global_batting_avg': global_batting_avg,
            'global_batting_sr': global_batting_sr,
            'global_bowling_econ': global_bowling_econ,
            'global_bowling_sr': global_bowling_sr
        }

    def calculate_venue_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates historical venue stats.
        Assumes df is match-level with columns: ['venue', 'first_innings_score', 'wickets_total', 'bat_first_win']
        """
        # Expanding mean (cumulative average) shifted by 1
        df = df.sort_values('start_date')
        grouped = df.groupby('venue')
        
        venue_stats = grouped[['first_innings_score', 'wickets_total', 'bat_first_win']].apply(
            lambda x: x.shift(1).expanding().mean()
        )
        
        venue_stats.columns = ['venue_avg_score', 'venue_avg_wickets', 'venue_bat_first_win_rate']
        
        # Reset index to match original df
        if isinstance(venue_stats.index, pd.MultiIndex):
            venue_stats = venue_stats.reset_index(level=0, drop=True)
            
        return venue_stats
