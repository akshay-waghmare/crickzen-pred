import pandas as pd
import numpy as np
from typing import Dict, Any

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
