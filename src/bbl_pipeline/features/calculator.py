import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple


class ResourceFeatureCalculator:
    """
    Calculates resource-based features inspired by DLS (Duckworth-Lewis-Stern) method.
    These features encode cricket domain knowledge about game state and expected outcomes.
    
    Key insight: The model benefits from understanding that the same score has very different
    implications depending on overs/wickets remaining. This helps especially for rare or 
    extreme game states the data rarely covers.
    """
    
    # T20 match constants
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
        'middle': {
            'well_ahead':  {0: 0.97, 1: 1.00, 2: 0.96, 3: 0.85, 4: 0.76, 5: 0.84, 6: 0.60, 7: 0.40, 8: 0.20, 9: 0.10, 10: 0.01},
            'ahead':       {0: 0.98, 1: 1.00, 2: 0.93, 3: 0.72, 4: 0.60, 5: 0.74, 6: 0.50, 7: 0.30, 8: 0.15, 9: 0.08, 10: 0.01},
            'par':         {0: 1.00, 1: 0.95, 2: 0.78, 3: 0.72, 4: 0.64, 5: 0.48, 6: 0.25, 7: 0.12, 8: 0.05, 9: 0.02, 10: 0.01},
            'behind':      {0: 1.00, 1: 0.98, 2: 0.65, 3: 0.61, 4: 0.52, 5: 0.25, 6: 0.18, 7: 0.10, 8: 0.05, 9: 0.02, 10: 0.01},
            'well_behind': {0: 0.84, 1: 1.00, 2: 0.62, 3: 0.54, 4: 0.33, 5: 0.38, 6: 0.12, 7: 0.05, 8: 0.01, 9: 0.01, 10: 0.01},
        },
        'death': {
            'well_ahead':  {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.85, 5: 0.82, 6: 0.70, 7: 0.55, 8: 0.40, 9: 0.20, 10: 0.01},
            'ahead':       {0: 1.00, 1: 0.98, 2: 0.70, 3: 0.74, 4: 0.76, 5: 0.77, 6: 0.84, 7: 0.60, 8: 0.40, 9: 0.20, 10: 0.01},
            'par':         {0: 1.00, 1: 0.97, 2: 0.86, 3: 0.87, 4: 0.78, 5: 0.78, 6: 0.48, 7: 0.42, 8: 0.30, 9: 0.15, 10: 0.01},
            'behind':      {0: 1.00, 1: 0.97, 2: 0.92, 3: 0.81, 4: 0.76, 5: 0.70, 6: 0.63, 7: 0.55, 8: 0.40, 9: 0.25, 10: 0.01},
            'well_behind': {0: 1.00, 1: 1.00, 2: 0.64, 3: 0.47, 4: 0.42, 5: 0.33, 6: 0.22, 7: 0.14, 8: 0.11, 9: 0.06, 10: 0.01},
        },
        'final': {
            'well_ahead':  {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 0.95, 5: 0.90, 6: 0.85, 7: 0.80, 8: 0.70, 9: 0.50, 10: 0.01},
            'ahead':       {0: 1.00, 1: 1.00, 2: 0.95, 3: 0.90, 4: 0.85, 5: 0.80, 6: 0.75, 7: 0.70, 8: 0.50, 9: 0.35, 10: 0.01},
            'par':         {0: 1.00, 1: 1.00, 2: 1.00, 3: 0.97, 4: 0.75, 5: 0.90, 6: 0.85, 7: 0.80, 8: 0.50, 9: 0.35, 10: 0.01},
            'behind':      {0: 1.00, 1: 1.00, 2: 0.97, 3: 0.79, 4: 0.86, 5: 0.66, 6: 0.83, 7: 0.90, 8: 0.64, 9: 0.45, 10: 0.01},
            'well_behind': {0: 1.00, 1: 1.00, 2: 0.85, 3: 0.75, 4: 0.65, 5: 0.55, 6: 0.45, 7: 0.40, 8: 0.25, 9: 0.20, 10: 0.01},
        },
    }
    
    def get_first_innings_phase(self, overs_bowled: float) -> str:
        """Get the phase name for first innings based on overs bowled."""
        if overs_bowled < 6:
            return 'powerplay'
        elif overs_bowled < 14:
            return 'middle'
        elif overs_bowled < 18:
            return 'death'
        else:
            return 'final'
    
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
        overs_bowled = min(max(overs_bowled, 0), 20)
        current_run_rate = max(0, current_run_rate)
        
        # Get current phase and ease bucket
        phase = self.get_first_innings_phase(overs_bowled)
        ease_bucket = self.get_first_innings_ease_bucket(current_run_rate, phase)
        
        # Get base penalty from 3D table
        phase_table = self.FIRST_INNINGS_WICKET_PENALTY_3D.get(phase, {})
        ease_table = phase_table.get(ease_bucket, {})
        base_penalty = ease_table.get(wickets_lost, 0.5)
        
        # Interpolate between phases for smoother transitions
        phase_boundaries = [
            ('powerplay', 0, 6),
            ('middle', 6, 14),
            ('death', 14, 18),
            ('final', 18, 20)
        ]
        
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
            ease_thresholds = [0.0, 0.85, 0.95, 1.05, 1.15]
            
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
        
        # Also cap the projection at reasonable T20 bounds (100-280)
        return max(100.0, min(280.0, regressed_projection))
    
    def calculate_match_phase(self, over: int) -> Tuple[str, int, int, int]:
        """
        Determine match phase and return one-hot encoded indicators.
        
        Returns:
            Tuple of (phase_name, is_powerplay, is_middle, is_death)
        """
        if over < 6:  # Overs 0-5 (1-6 in cricket terms)
            return ('powerplay', 1, 0, 0)
        elif over < 15:  # Overs 6-14 (7-15 in cricket terms)
            return ('middle', 0, 1, 0)
        else:  # Overs 15-19 (16-20 in cricket terms)
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
            # RRR 7 = comfortable (0), RRR 15+ = maximum pressure (1)
            rate_pressure = min(1.0, max(0.0, (required_rate - 7) / 8))

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
        wickets_lost: int = None
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
            if overs_bowled >= 19.5:
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
            
            # Improvement: Contextual par blends venue avg with league avg
            # If venue_avg_score is available (passed via expected_final_score context),
            # use 60% venue + 40% league. Otherwise, fallback to league avg.
            # For now, we use league avg as venue data isn't passed to this method
            # TODO: Pass venue_avg_score when available for cross-venue calibration
            contextual_par = self.LEAGUE_AVG_SCORE
            
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
            sqi_shifted = sqi - 0.35
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
        if balls_remaining > 0 and balls_remaining <= 12 and runs_required <= balls_remaining * 2:
            # Use runs per ball needed vs typical death over scoring (~1.5 rpb)
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
        # Calibrated from ILT20 EDA: beta=0.7, mu=9.5
        # At RRR=7: ~80%, RRR=9.5: ~50%, RRR=12: ~20%
        # Clip exponent to prevent overflow (exp argument range: -700 to 700)
        exponent = self.RRR_BETA * (effective_rrr - self.RRR_MIDPOINT)
        exponent = np.clip(exponent, -700, 700)
        base_prob = 1.0 / (1.0 + np.exp(exponent))
        
        # -------------------------------------
        # WICKET PENALTY (Dynamic 2D - Chase Difficulty Aware)
        # -------------------------------------
        # Uses CRR/RRR ratio to determine chase ease, then applies
        # appropriate wicket penalty from empirically-calibrated 2D table
        wicket_mult = self.get_dynamic_wicket_penalty(
            actual_wickets_lost, current_run_rate, effective_rrr
        )
        
        # -------------------------------------
        # CURRENT RUN RATE ADJUSTMENT
        # -------------------------------------
        # If batting above required rate, slight boost; below, slight penalty
        # Effect is muted early in innings (CRR volatile)
        overs_bowled = self.TOTAL_OVERS - overs_remaining
        overs_weight = min(1.0, overs_bowled / 10.0)  # Full weight after 10 overs
        
        rate_factor = 1.0
        if required_run_rate > 0 and current_run_rate > 0:
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
        
        # Pressure index (now using current_run_rate for better CRR vs RRR comparison)
        pressure_index = self.calculate_pressure_index(
            innings, current_score, overs_bowled, wickets_lost, target_runs, current_run_rate
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
