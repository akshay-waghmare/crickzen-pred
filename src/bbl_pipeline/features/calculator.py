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
        0: {20: 100.0, 15: 84.4, 10: 63.4, 5: 35.4, 1: 8.2},
        1: {20: 95.3, 15: 81.5, 10: 61.6, 5: 34.5, 1: 8.0},
        2: {20: 88.9, 15: 77.4, 10: 59.0, 5: 33.2, 1: 7.7},
        3: {20: 80.6, 15: 71.8, 10: 55.5, 5: 31.4, 1: 7.3},
        4: {20: 70.6, 15: 64.5, 10: 50.8, 5: 28.8, 1: 6.7},
        5: {20: 59.1, 15: 55.5, 10: 44.7, 5: 25.5, 1: 5.9},
        6: {20: 46.1, 15: 44.5, 10: 37.0, 5: 21.3, 1: 4.9},
        7: {20: 32.4, 15: 32.0, 10: 27.5, 5: 16.1, 1: 3.7},
        8: {20: 18.4, 15: 18.4, 10: 16.6, 5: 10.0, 1: 2.3},
        9: {20: 5.5, 15: 5.5, 10: 5.5, 5: 4.1, 1: 0.9},
    }
    
    # Average T20 par score for resource calculation
    PAR_SCORE_T20 = 160.0
    
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
        
        Uses a projection based on current run rate weighted by resources consumed.
        """
        if overs_bowled <= 0:
            return self.PAR_SCORE_T20
            
        overs_remaining = self.TOTAL_OVERS - overs_bowled
        
        # Resources used and remaining
        resource_at_start = 100.0
        resource_remaining = self.calculate_resource_percentage(overs_remaining, wickets_lost)
        resource_used = resource_at_start - resource_remaining
        
        if resource_used <= 0:
            return self.PAR_SCORE_T20
            
        # Runs per resource point
        runs_per_resource = current_score / resource_used
        
        # Expected additional runs
        expected_additional = runs_per_resource * resource_remaining
        
        return current_score + expected_additional
    
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
    
    def calculate_pressure_index(self, innings: int, current_score: int, 
                                  overs_bowled: float, wickets_lost: int,
                                  target_runs: int = None) -> float:
        """
        Calculate a pressure index that captures match situation urgency.
        
        For 1st innings: Based on scoring rate relative to par
        For 2nd innings: Based on required rate and resources remaining
        
        Returns:
            Pressure index (0-1 scale, higher = more pressure on batting team)
        """
        overs_remaining = self.TOTAL_OVERS - overs_bowled
        
        if innings == 1:
            # First innings: Pressure based on being behind par score
            expected_at_this_point = self.PAR_SCORE_T20 * (overs_bowled / self.TOTAL_OVERS)
            score_diff = expected_at_this_point - current_score
            
            # Also factor in wickets
            wicket_pressure = wickets_lost / self.TOTAL_WICKETS
            
            # Combine: behind on runs + losing wickets = high pressure
            run_pressure = max(0, score_diff / 50)  # Normalize to 0-1 range roughly
            pressure = 0.6 * run_pressure + 0.4 * wicket_pressure
            
            return min(1.0, max(0.0, pressure))
        else:
            # Second innings: Pressure based on required rate
            if target_runs is None:
                return 0.5  # Unknown target
                
            runs_required = target_runs - current_score
            
            if runs_required <= 0:
                return 0.0  # Already won
                
            if overs_remaining <= 0:
                return 1.0  # No overs left and haven't won
                
            required_rate = runs_required / overs_remaining
            
            # Resource-based feasibility
            resource_remaining = self.calculate_resource_percentage(overs_remaining, wickets_lost)
            max_gettable = (resource_remaining / 100) * self.PAR_SCORE_T20 * 1.3  # 130% of par as upper bound
            
            if runs_required > max_gettable:
                return 1.0  # Practically impossible
                
            # Pressure scales with required rate
            # RRR of 6 = low pressure, RRR of 12 = moderate, RRR of 18+ = very high
            rate_pressure = min(1.0, (required_rate - 6) / 12)
            wicket_pressure = wickets_lost / self.TOTAL_WICKETS
            
            # Weight towards run rate pressure in chase
            pressure = 0.7 * max(0, rate_pressure) + 0.3 * wicket_pressure
            
            return min(1.0, max(0.0, pressure))
    
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
            run_rate_differential = required_run_rate - current_run_rate
        
        # Match phase
        phase_name, is_powerplay, is_middle, is_death = self.calculate_match_phase(over)
        
        # Expected score projection
        expected_final_score = self.calculate_expected_score(current_score, overs_bowled, wickets_lost)
        
        # Pressure index
        pressure_index = self.calculate_pressure_index(
            innings, current_score, overs_bowled, wickets_lost, target_runs
        )
        
        # Win probability estimate (simple resource-based)
        # This gives the model a baseline "expected" probability from cricket knowledge
        if innings == 1:
            # First innings: Win prob based on expected score vs par
            score_advantage = (expected_final_score - self.PAR_SCORE_T20) / 50
            resource_win_prob = 0.5 + 0.2 * np.tanh(score_advantage)
        else:
            # Second innings: Win prob based on resources vs runs required
            if target_runs is not None:
                runs_required = target_runs - current_score
                max_gettable = (resource_pct / 100) * self.PAR_SCORE_T20 * 1.3
                
                if runs_required <= 0:
                    resource_win_prob = 1.0
                elif runs_required > max_gettable:
                    resource_win_prob = 0.0
                else:
                    # Probability based on feasibility
                    feasibility = 1 - (runs_required / max_gettable)
                    resource_win_prob = 0.3 + 0.6 * feasibility
            else:
                resource_win_prob = 0.5
        
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
