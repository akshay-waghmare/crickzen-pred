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
    # FIRST INNINGS CALIBRATION (from ILT20 EDA)
    # =========================================================================
    # Key finding: batting first wins only 37% overall in ILT20
    # Projected score -> win rate mapping:
    # < 120: 5%, 140-150: 24%, 160-170: 35%, 180-200: 58%, >200: 65%
    # This means PAR (160) = 35% win rate, not 50%!
    # To get 50% win rate, need to project ~185
    FIRST_INNINGS_SCORE_MIDPOINT = 185.0  # Score where win_prob = 50%
    FIRST_INNINGS_SCORE_BETA = 0.04  # Controls steepness
    
    # First innings wicket penalty (different from chase)
    # 0 wkt: 48%, 2 wkt: 36%, 4 wkt: 35%, 6 wkt: 23%
    FIRST_INNINGS_WICKET_PENALTY = {
        0: 1.00, 1: 0.95, 2: 0.85, 3: 0.80,
        4: 0.75, 5: 0.70, 6: 0.55, 7: 0.50,
        8: 0.30, 9: 0.20, 10: 0.05
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
    WICKET_PENALTY = {
        0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00,
        4: 0.75, 5: 0.50, 6: 0.35, 7: 0.25,
        8: 0.12, 9: 0.05, 10: 0.01
    }
    
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
        
        # -------------------------------------
        # INNINGS 1: Team batting first (Data-Calibrated)
        # -------------------------------------
        if innings == 1:
            # Base probability from projected score using logistic
            # Calibrated: 185 projected = 50% win, 160 = 35%, 200 = 65%
            score_diff = expected_final_score - self.FIRST_INNINGS_SCORE_MIDPOINT
            base_prob = 1.0 / (1.0 + np.exp(-self.FIRST_INNINGS_SCORE_BETA * score_diff))
            
            # Apply wicket penalty (different from chase - wickets hurt more in 1st innings)
            wicket_mult = self.FIRST_INNINGS_WICKET_PENALTY.get(actual_wickets_lost, 0.05)
            
            # Calculate overs bowled to weight wicket penalty
            # Early wickets are less concerning (can recover), late wickets are critical
            if balls_remaining is not None:
                overs_bowled = self.TOTAL_OVERS - (balls_remaining / 6.0)
            else:
                overs_bowled = (1 - resource_pct / 100.0) * self.TOTAL_OVERS
            
            # Phase weight: wicket penalty impact increases as innings progresses
            phase_weight = min(1.0, overs_bowled / 15.0)  # Full weight after 15 overs
            adjusted_wicket_mult = 1.0 - phase_weight * (1.0 - wicket_mult)
            
            win_prob = base_prob * adjusted_wicket_mult
            return float(max(0.05, min(0.95, win_prob)))

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
            
            # Reduce wicket penalty impact in easy endgame situations
            # At 0.5 rpb (3 off 6), even 5 down should be ~90%+
            # Scale penalty by difficulty: low rpb = reduced penalty
            wicket_mult = self.WICKET_PENALTY.get(actual_wickets_lost, 0.01)
            # Blend toward 1.0 as runs_per_ball_needed decreases
            # At rpb=0.5, penalty_weight=0.25; at rpb=1.5, penalty_weight=1.0
            penalty_weight = min(1.0, runs_per_ball_needed / 1.5)
            adjusted_wicket_mult = 1.0 - penalty_weight * (1.0 - wicket_mult)
            
            return float(max(0.05, min(0.95, endgame_prob * adjusted_wicket_mult)))

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
        base_prob = 1.0 / (1.0 + np.exp(self.RRR_BETA * (effective_rrr - self.RRR_MIDPOINT)))
        
        # -------------------------------------
        # WICKET PENALTY (Data-Calibrated)
        # -------------------------------------
        # Based on ILT20 EDA: significant drop in win rate after 4 wickets
        wicket_mult = self.WICKET_PENALTY.get(actual_wickets_lost, 0.01)
        
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
