"""
Real-time Feature Mapper
Transforms data from the real-time scraper into BBL model feature format.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from pathlib import Path

from .schema import MatchState
from ..features.store import InMemoryFeatureStore
from ..features.calculator import ResourceFeatureCalculator


class RealTimeFeatureMapper:
    """
    Maps real-time scraped data to BBL model input features.
    
    Handles:
    1. Field name mapping (innings_num -> innings, over_number -> over, etc.)
    2. Feature calculation (overs_remaining, wickets_remaining, etc.)
    3. Historical stat lookup from FeatureStore
    4. Resource-based feature generation (DLS, pressure, etc.)
    """
    
    def __init__(self, feature_store: InMemoryFeatureStore, global_stats: Dict[str, float]):
        """
        Initialize the mapper.
        
        Args:
            feature_store: Store for historical player/venue statistics
            global_stats: Global fallback statistics
        """
        self.feature_store = feature_store
        self.global_stats = global_stats
        self.resource_calculator = ResourceFeatureCalculator()
        self.ball_history = []
    
    def _update_history(self, current_ball_data: Dict[str, Any]):
        """Update ball history with current ball."""
        # Avoid duplicates based on over/ball/innings
        key = (current_ball_data.get('innings_num'), 
               current_ball_data.get('over_number'), 
               current_ball_data.get('ball_number'))
        
        # Check if last ball is same
        if self.ball_history:
            last = self.ball_history[-1]
            last_key = (last.get('innings_num'), last.get('over_number'), last.get('ball_number'))
            if key == last_key:
                return
        
        self.ball_history.append(current_ball_data)
        
        # Keep last 30 balls for rolling stats
        if len(self.ball_history) > 30:
            self.ball_history.pop(0)

    def _calculate_rolling_stats(self) -> Dict[str, float]:
        """Calculate rolling stats from history."""
        # If we don't have enough history for meaningful rolling stats,
        # return sensible defaults based on average T20 scoring
        if len(self.ball_history) < 6:  # Need at least an over of history
            return {
                'runs_last_12': 12.0,  # ~6 runs per over (2 overs) is typical
                'runs_last_18': 18.0,  # ~6 runs per over (3 overs)
                'wickets_last_12': 0.5, # ~1 wicket every 4 overs on average
                'boundary_pct_last_18': 0.15  # ~15% boundary rate typical
            }
            
        # Convert to DF for easier calc
        df = pd.DataFrame(self.ball_history)
        
        # Ensure columns exist
        if 'runs_scored' not in df.columns:
            # Try to infer from total_score diff
            df['runs_scored'] = df['total_score'].diff().fillna(0)  # First ball = 0, not cumulative
        
        if 'is_wicket' not in df.columns:
             df['is_wicket'] = df['total_wickets'].diff().fillna(0)  # First ball = 0, not cumulative
             
        if 'is_boundary' not in df.columns:
            df['is_boundary'] = df['runs_scored'].isin([4, 6]).astype(int)
            
        # Last 12 balls (approx 2 overs)
        last_12 = df.tail(12)
        runs_last_12 = last_12['runs_scored'].sum()
        wickets_last_12 = last_12['is_wicket'].sum()
        
        # Last 18 balls (approx 3 overs)
        last_18 = df.tail(18)
        runs_last_18 = last_18['runs_scored'].sum()
        boundaries = last_18['is_boundary'].sum()
        boundary_pct_last_18 = boundaries / len(last_18) if len(last_18) > 0 else 0
        
        return {
            'runs_last_12': runs_last_12,
            'runs_last_18': runs_last_18,
            'wickets_last_12': wickets_last_12,
            'boundary_pct_last_18': boundary_pct_last_18
        }

    def map_scraped_to_match_state(self, scraped_data: Dict[str, Any]) -> MatchState:
        """
        Convert scraped ball data to MatchState object.
        
        Args:
            scraped_data: Dictionary from real-time scraper
            
        Returns:
            MatchState object
        """
        # Map field names
        innings = scraped_data.get('innings_num', 1)
        over = scraped_data.get('over_number', 0)
        ball = scraped_data.get('ball_number', 0)
        current_score = scraped_data.get('total_score', 0)
        wickets_lost = scraped_data.get('total_wickets', 0)
        
        # Get target for 2nd innings
        target_runs = None
        first_innings_score = None
        if innings == 2:
            target_runs = scraped_data.get('target_score')
            first_innings_score = target_runs - 1 if target_runs else None
        
        # Player names
        batsman_1 = scraped_data.get('batsman1_name', 'Unknown')
        batsman_2 = scraped_data.get('batsman2_name', 'Unknown')
        bowler = scraped_data.get('bowler1_name', 'Unknown')
        
        return MatchState(
            match_id=scraped_data.get('match_id', 'live_match'),
            venue=scraped_data.get('venue', 'Unknown Venue'),
            batting_team=scraped_data.get('batting_team', 'Unknown'),
            bowling_team=scraped_data.get('bowling_team', 'Unknown'),
            innings=innings,
            over=over,
            ball=ball,
            current_score=current_score,
            wickets_lost=wickets_lost,
            batsman_1=batsman_1,
            batsman_2=batsman_2,
            bowler=bowler,
            target_runs=target_runs,
            first_innings_score=first_innings_score
        )
    
    def create_feature_dataframe(self, scraped_data: Dict[str, Any]) -> pd.DataFrame:
        """
        Create a complete feature DataFrame ready for model prediction.
        
        Args:
            scraped_data: Dictionary from real-time scraper
            
        Returns:
            DataFrame with all features required by the model
        """
        # Update history
        self._update_history(scraped_data)
        
        # Convert to MatchState first
        state = self.map_scraped_to_match_state(scraped_data)
        
        # --- Core Features (directly from scraper) ---
        innings = scraped_data.get('innings_num', 1)
        over = scraped_data.get('over_number', 0)
        ball = scraped_data.get('ball_number', 0)
        current_score = scraped_data.get('total_score', 0)
        wickets_lost = scraped_data.get('total_wickets', 0)
        
        # --- Calculated Basic Features ---
        overs_remaining = 20 - over - (ball / 6.0)
        balls_remaining = (20 * 6) - (over * 6 + ball)
        wickets_remaining = 10 - wickets_lost
        
        # --- Historical Player/Venue Stats (from FeatureStore) ---
        batsman_1_name = scraped_data.get('batsman1_name', 'Unknown')
        batsman_2_name = scraped_data.get('batsman2_name', 'Unknown')
        bowler_name = scraped_data.get('bowler1_name', 'Unknown')
        venue = scraped_data.get('venue', 'Unknown Venue')
        batting_team = scraped_data.get('batting_team', 'Unknown')
        bowling_team = scraped_data.get('bowling_team', 'Unknown')
        
        # Lookup historical stats
        batsman_1_stats = self.feature_store.get_player_stats(batsman_1_name) or {}
        batsman_2_stats = self.feature_store.get_player_stats(batsman_2_name) or {}
        bowler_stats = self.feature_store.get_player_stats(bowler_name) or {}
        venue_stats = self.feature_store.get_venue_stats(venue) or {}
        
        # Get with fallbacks
        batsman_rolling_avg = batsman_1_stats.get('batsman_rolling_avg', 
                                                   self.global_stats.get('global_batting_avg', 25.0))
        batsman_rolling_sr = batsman_1_stats.get('batsman_rolling_sr',
                                                  self.global_stats.get('global_batting_sr', 125.0))
        bowler_rolling_econ = bowler_stats.get('bowler_rolling_econ',
                                                self.global_stats.get('global_bowling_econ', 7.5))
        bowler_rolling_sr = bowler_stats.get('bowler_rolling_sr',
                                              self.global_stats.get('global_bowling_sr', 20.0))
        
        venue_avg_score = venue_stats.get('venue_avg_score', 160.0)
        venue_avg_wickets = venue_stats.get('venue_avg_wickets', 6.0)
        venue_bat_first_win_rate = venue_stats.get('venue_bat_first_win_rate', 0.5)
        
        # Team Stats (Placeholder - need to implement get_team_stats in FeatureStore)
        # For now, use defaults or try to get from feature store if available
        batting_team_win_rate = 0.5
        bowling_team_win_rate = 0.5
        team_strength_diff = 0.0
        
        if hasattr(self.feature_store, 'get_team_stats'):
             batting_stats = self.feature_store.get_team_stats(batting_team) or {}
             bowling_stats = self.feature_store.get_team_stats(bowling_team) or {}
             batting_team_win_rate = batting_stats.get('win_rate', 0.5)
             bowling_team_win_rate = bowling_stats.get('win_rate', 0.5)
             team_strength_diff = batting_team_win_rate - bowling_team_win_rate

        # --- Resource-based Features (DLS-style) ---
        target_runs = scraped_data.get('target_score') if innings == 2 else None
        
        resource_features = self.resource_calculator.calculate_all_features(
            innings=innings,
            over=over,
            ball=ball,
            current_score=current_score,
            wickets_lost=wickets_lost,
            target_runs=target_runs
        )
        
        # --- Rolling Stats ---
        rolling_stats = self._calculate_rolling_stats()
        
        # --- Rate Features ---
        # Use scraped values if available, otherwise use calculated
        current_run_rate = scraped_data.get('current_run_rate', 
                                            resource_features['current_run_rate'])
        required_run_rate = scraped_data.get('required_run_rate',
                                             resource_features['required_run_rate'])
        # Positive = batting team ahead (scoring faster than required)
        # This ensures scoring runs INCREASES this value
        run_rate_diff = current_run_rate - required_run_rate
        
        # --- Projected/Expected Scores ---
        expected_final_score = scraped_data.get('projected_score',
                                                resource_features['expected_final_score'])
        runs_required = scraped_data.get('runs_needed', 0) if innings == 2 else 0
        
        # --- Phase Features ---
        is_powerplay = int(scraped_data.get('powerplay', over < 6))
        is_middle_overs = int(scraped_data.get('middle_overs', (over >= 6 and over < 16)))
        is_death_overs = int(scraped_data.get('death_overs', over >= 16))
        
        # --- Pressure & Win Probability ---
        pressure_index = scraped_data.get('pressure_index', resource_features['pressure_index'])
        resource_win_prob = resource_features['resource_win_prob']
        
        # --- Derived Features for Model ---
        projected_score = expected_final_score
        
        # score_vs_par: For 2nd innings, compare against TARGET not venue average
        # This fixes the issue where easy chases show negative score_vs_par
        if innings == 2 and target_runs is not None and target_runs > 0:
            # Par score at this point = target * (resources used / 100)
            resources_used = 100 - resource_features.get('resource_pct', 100)
            par_at_this_point = target_runs * (resources_used / 100)
            score_vs_par = current_score - par_at_this_point
        else:
            # 1st innings: compare against venue average
            score_vs_par = current_score - (venue_avg_score * (1 - resource_features.get('resource_pct', 100)/100))
        
        projected_vs_venue_avg = projected_score - venue_avg_score
        score_per_wicket = current_score / (wickets_lost + 1)
        wickets_times_balls = wickets_lost * (120 - balls_remaining)
        rrr_times_wickets = required_run_rate * wickets_lost
        chase_difficulty = required_run_rate / (current_run_rate + 0.1) if innings == 2 else 0
        
        # Heuristics
        situation_advantage = (resource_win_prob - 0.5) * 2
        batting_team_situation_wr = resource_win_prob
        bowling_team_situation_wr = 1 - resource_win_prob
        
        # --- Construct Feature DataFrame ---
        features = {
            # Top 25 Features
            'expected_final_score': expected_final_score,
            'resource_win_prob': resource_win_prob,
            'score_vs_par': score_vs_par,
            'dls_pressure_index': pressure_index,
            'projected_vs_venue_avg': projected_vs_venue_avg,
            'projected_score': projected_score,
            'is_powerplay': is_powerplay,
            'score_per_wicket': score_per_wicket,
            'run_rate_diff': run_rate_diff,
            'required_run_rate': required_run_rate,
            'chase_difficulty': chase_difficulty,
            'wickets_times_balls': wickets_times_balls,
            'pressure_index': pressure_index,
            'team_strength_diff': team_strength_diff,
            'rrr_times_wickets': rrr_times_wickets,
            'overs_remaining': overs_remaining,
            'batting_team_win_rate': batting_team_win_rate,
            'bowling_team_win_rate': bowling_team_win_rate,
            'batting_team_situation_wr': batting_team_situation_wr,
            'situation_advantage': situation_advantage,
            'boundary_pct_last_18': rolling_stats['boundary_pct_last_18'],
            'bowling_team_situation_wr': bowling_team_situation_wr,
            'runs_last_12': rolling_stats['runs_last_12'],
            'runs_last_18': rolling_stats['runs_last_18'],
            'wickets_last_12': rolling_stats['wickets_last_12'],
            
            # Extra features (kept for completeness)
            'innings': innings,
            'over': over,
            'ball': ball,
            'current_score': current_score,
            'wickets_lost': wickets_lost,
            'batsman_rolling_avg': batsman_rolling_avg,
            'batsman_rolling_sr': batsman_rolling_sr,
            'bowler_rolling_econ': bowler_rolling_econ,
            'bowler_rolling_sr': bowler_rolling_sr,
            'venue_avg_score': venue_avg_score,
            'venue_avg_wickets': venue_avg_wickets,
            'venue_bat_first_win_rate': venue_bat_first_win_rate,
            'balls_remaining': balls_remaining,
            'wickets_remaining': wickets_remaining,
            'resource_pct': resource_features['resource_pct'],
            'current_run_rate': current_run_rate,
            'runs_required': runs_required,
            'is_middle_overs': is_middle_overs,
            'is_death_overs': is_death_overs,
        }
        
        return pd.DataFrame([features])
    
    def validate_features(self, df: pd.DataFrame, expected_features: list) -> pd.DataFrame:
        """
        Ensure DataFrame has all expected features, add missing ones with defaults.
        
        Args:
            df: Feature DataFrame
            expected_features: List of feature names the model expects
            
        Returns:
            DataFrame with all expected features
        """
        for feature in expected_features:
            if feature not in df.columns:
                # Add missing feature with appropriate default
                if 'rate' in feature.lower() or 'avg' in feature.lower():
                    df[feature] = 0.0
                elif 'is_' in feature or feature.endswith('_overs'):
                    df[feature] = 0
                elif 'pct' in feature or 'prob' in feature:
                    df[feature] = 0.5
                else:
                    df[feature] = 0.0
        
        # Return only expected features in correct order
        return df[expected_features]
