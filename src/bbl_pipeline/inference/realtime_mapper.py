"""
Real-time Feature Mapper
Transforms data from the real-time scraper into BBL model feature format.
"""
import pandas as pd
import numpy as np
import structlog
from typing import Dict, Any, Optional
from pathlib import Path

from .schema import MatchState
from ..features.store import InMemoryFeatureStore
from ..features.calculator import ResourceFeatureCalculator
from ..features.format_config import FormatConfig

logger = structlog.get_logger()


class RealTimeFeatureMapper:
    """
    Maps real-time scraped data to BBL model input features.
    
    Handles:
    1. Field name mapping (innings_num -> innings, over_number -> over, etc.)
    2. Feature calculation (overs_remaining, wickets_remaining, etc.)
    3. Historical stat lookup from FeatureStore
    4. Resource-based feature generation (DLS, pressure, etc.)
    """
    
    def __init__(self, feature_store: InMemoryFeatureStore, global_stats: Dict[str, float],
                 format_config: FormatConfig = None):
        """
        Initialize the mapper.
        
        Args:
            feature_store: Store for historical player/venue statistics
            global_stats: Global fallback statistics
            format_config: Format configuration (T20 or ODI). Defaults to T20.
        """
        self.feature_store = feature_store
        self.global_stats = global_stats
        self.format_config = format_config or FormatConfig.t20()
        self.resource_calculator = ResourceFeatureCalculator(config=self.format_config)
        self.ball_history = []
        self._balls_since_wicket: int = 0   # Persistent partnership counter
        self._current_innings: int = None   # Track innings for counter reset
    
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
        
        # Maintain balls_since_wicket counter (reset on innings change or wicket)
        new_innings = current_ball_data.get('innings_num', 1)
        if new_innings != self._current_innings:
            self._current_innings = new_innings
            self._balls_since_wicket = 0
        is_wicket = int(current_ball_data.get('is_wicket', 0))
        if is_wicket:
            self._balls_since_wicket = 0
        else:
            self._balls_since_wicket += 1
        
        # Keep last 30 balls for rolling stats
        if len(self.ball_history) > 30:
            self.ball_history.pop(0)

    def _calculate_rolling_stats(self, current_innings: int = None, total_balls_in_match: int = None) -> Dict[str, float]:
        """Calculate rolling stats from history.
        
        Args:
            current_innings: The current innings number (1 or 2). If provided,
                           only balls from this innings are used.
            total_balls_in_match: Total balls bowled in current innings so far.
                                 Used to detect incomplete ball history.
        """
        # If we don't have any history, return sensible defaults
        if len(self.ball_history) == 0:
            return {
                'runs_last_12': 12.0,
                'runs_last_18': 18.0,
                'wickets_last_12': 0.5,
                'boundary_pct_last_18': 0.15,
                'dot_pct_last_12': 0.35,
                'wickets_last_6': 0.25,
            }
            
        # Convert to DF for easier calc (use whatever history we have)
        df = pd.DataFrame(self.ball_history)
        
        # CRITICAL: Filter to current innings only to avoid cross-innings contamination
        if current_innings is not None and 'innings_num' in df.columns:
            df = df[df['innings_num'] == current_innings]
            
        # If no balls in current innings, return sensible defaults (not zeros!)
        # At innings start, we should assume average performance, not worst case
        if len(df) == 0:
            return {
                'runs_last_12': 12.0,
                'runs_last_18': 18.0,
                'wickets_last_12': 0.5,
                'boundary_pct_last_18': 0.15,
                'dot_pct_last_12': 0.35,
                'wickets_last_6': 0.25,
            }
        
        # Check if ball history is incomplete (missing data from scraper)
        # If we're 50 balls into the match but only have 20 balls of history, data is sparse
        history_completeness = 1.0  # Default: assume complete
        if total_balls_in_match is not None and total_balls_in_match > 0:
            balls_in_history = len(df)
            if balls_in_history < total_balls_in_match:
                history_completeness = min(balls_in_history / total_balls_in_match, 1.0)
                # Log sparse data warning
                if history_completeness < 0.7:
                    logger.warning(
                        f"Sparse ball history detected: {balls_in_history}/{total_balls_in_match} balls "
                        f"({history_completeness:.1%} complete)"
                    )
        
        # If data is too sparse (< 30% complete), return sensible defaults
        # Using incomplete rolling stats creates feature mismatch vs training
        if history_completeness < 0.3:
            logger.info("Ball history too sparse - using default rolling stats")
            return {
                'runs_last_12': 12.0,
                'runs_last_18': 18.0,
                'wickets_last_12': 0.5,
                'boundary_pct_last_18': 0.15,
                'dot_pct_last_12': 0.35,
                'wickets_last_6': 0.25,
            }
        
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
        wickets_last_12_raw = last_12['is_wicket'].sum()
        
        # CONSISTENCY WITH TRAINING: During training, wickets_last_12 is an integer count
        # We should NOT scale it - just use actual count from available data
        # If data is very sparse (< 30% complete), use defaults instead
        if history_completeness < 0.3:
            # Too sparse - use defaults (approx 0.5 wickets per 12 balls)
            wickets_last_12 = 0.5
        else:
            # Use actual count from available ball history (matches training distribution)
            wickets_last_12 = float(wickets_last_12_raw)
        
        # Last 18 balls (approx 3 overs)
        last_18 = df.tail(18)
        runs_last_18 = last_18['runs_scored'].sum()

        # True boundary ball rate: boundaries in last 18 balls / actual balls faced
        boundaries_last_18 = last_18['is_boundary'].sum()
        n_last_18 = max(len(last_18), 1)
        boundary_pct_last_18 = boundaries_last_18 / n_last_18

        # Dot ball rate: dots in last 12 balls / actual balls faced
        dots_last_12 = (last_12['runs_scored'] == 0).sum()
        n_last_12 = max(len(last_12), 1)
        dot_pct_last_12 = dots_last_12 / n_last_12

        # Wickets in last 6 balls (immediate collapse signal)
        last_6 = current_innings[-6:] if len(current_innings) >= 6 else current_innings
        wickets_last_6 = last_6['is_wicket'].sum()
        
        return {
            'runs_last_12': runs_last_12,
            'runs_last_18': runs_last_18,
            'wickets_last_12': wickets_last_12,
            'boundary_pct_last_18': boundary_pct_last_18,
            'dot_pct_last_12': dot_pct_last_12,
            'wickets_last_6': wickets_last_6,
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
        total_overs = self.format_config.total_overs
        overs_remaining = total_overs - over - (ball / 6.0)
        balls_remaining = (total_overs * 6) - (over * 6 + ball)
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
        
        venue_avg_score = venue_stats.get('venue_avg_score', self.format_config.par_score)
        venue_avg_wickets = venue_stats.get('venue_avg_wickets', 6.0)
        venue_bat_first_win_rate = venue_stats.get('venue_bat_first_win_rate', 0.5)
        
        # Team Stats - Overall and Situation-Specific Win Rates
        batting_team_win_rate = 0.5
        bowling_team_win_rate = 0.5
        batting_team_bat_first_wr = 0.5
        batting_team_bowl_first_wr = 0.5
        bowling_team_bat_first_wr = 0.5
        bowling_team_bowl_first_wr = 0.5
        team_strength_diff = 0.0
        
        if hasattr(self.feature_store, 'get_team_stats'):
             batting_stats = self.feature_store.get_team_stats(batting_team) or {}
             bowling_stats = self.feature_store.get_team_stats(bowling_team) or {}

             batting_team_win_rate = batting_stats.get('win_rate', 0.5)
             bowling_team_win_rate = bowling_stats.get('win_rate', 0.5)
             batting_team_bat_first_wr = batting_stats.get('bat_first_wr', 0.5)
             batting_team_bowl_first_wr = batting_stats.get('bowl_first_wr', 0.5)
             bowling_team_bat_first_wr = bowling_stats.get('bat_first_wr', 0.5)
             bowling_team_bowl_first_wr = bowling_stats.get('bowl_first_wr', 0.5)
             team_strength_diff = batting_team_win_rate - bowling_team_win_rate
        else:
             logger.warning("Feature store does not have get_team_stats method")

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
        # Calculate total balls bowled in current innings
        total_balls_in_innings = over * 6 + ball
        # Pass current innings and total balls to detect incomplete ball history
        rolling_stats = self._calculate_rolling_stats(
            current_innings=innings,
            total_balls_in_match=total_balls_in_innings
        )
        
        # --- Rate Features ---
        # Use scraped values if available, otherwise use calculated
        current_run_rate = scraped_data.get('current_run_rate', 
                                            resource_features['current_run_rate'])
        required_run_rate = scraped_data.get('required_run_rate',
                                             resource_features['required_run_rate'])
        
        # run_rate_diff only makes sense in innings 2 (chasing)
        # In innings 1, there's no target, so run_rate_diff should be 0
        # This matches training data calculation in processor.py
        if innings == 1:
            run_rate_diff = 0.0
        elif total_balls_in_innings == 0:
            # At the very start of innings 2, use neutral value
            run_rate_diff = 0.0
        else:
            # Innings 2: Positive = batting team ahead (scoring faster than required)
            run_rate_diff = current_run_rate - required_run_rate
        
        # --- Projected/Expected Scores ---
        # expected_final_score is the DLS/resource projection used in training.
        expected_final_score = resource_features['expected_final_score']
        runs_required = scraped_data.get('runs_needed', 0) if innings == 2 else 0
        
        # --- Phase Features ---
        thresholds = self.format_config.phase_thresholds
        pp_limit = thresholds.get('powerplay', 6)
        mid_limit = thresholds.get('middle', 15)
        death_limit = thresholds.get('death', total_overs)
        is_powerplay = int(scraped_data.get('powerplay', over < pp_limit))
        is_middle_overs = int(scraped_data.get('middle_overs', (over >= pp_limit and over < mid_limit)))
        is_death_overs = int(scraped_data.get('death_overs', over >= mid_limit))
        
        # --- Pressure Index ---
        # Match training calculation: RRR * (1 + wickets_lost * 0.15) for innings 2
        # wickets_lost * 0.5 for innings 1
        if innings == 2:
            pressure_index = required_run_rate * (1 + wickets_lost * 0.15)
        else:
            pressure_index = wickets_lost * 0.5
        
        # DLS pressure index from resource calculator (different calculation)
        dls_pressure_index = resource_features['pressure_index']
        resource_win_prob = resource_features['resource_win_prob']
        
        # --- Derived Features for Model ---
        # Match processor.py: projected_score is a simple innings-1 linear
        # projection and is zero for innings 2.
        if innings == 1:
            projected_score = current_score + (current_run_rate * balls_remaining / 6.0)
            projected_vs_venue_avg = projected_score - venue_avg_score
        else:
            projected_score = 0.0
            projected_vs_venue_avg = 0.0

        # Training resources_remaining is not DLS resource_pct; it is the simple
        # balls-and-wickets resource proxy used by processor.py.
        resources_remaining = (balls_remaining / self.format_config.total_balls) * (wickets_remaining / 10.0)
        resources_used = 1.0 - resources_remaining
        first_innings_score_for_par = scraped_data.get('first_innings_score')
        if first_innings_score_for_par is None and target_runs is not None:
            first_innings_score_for_par = target_runs - 1
        if innings == 2 and first_innings_score_for_par is not None:
            par_score = float(first_innings_score_for_par) * resources_used
        else:
            par_score = venue_avg_score * resources_used
        score_vs_par = current_score - par_score

        score_per_wicket = current_score / (wickets_lost + 1)
        wickets_times_balls = wickets_lost * (self.format_config.total_balls - balls_remaining)
        rrr_times_wickets = required_run_rate * wickets_lost
        if innings == 2 and resources_remaining > 0 and first_innings_score_for_par is not None:
            chase_difficulty = runs_required / (resources_remaining * float(first_innings_score_for_par) + 1)
        else:
            chase_difficulty = 0.0
        
        # Team situation win rates - based on batting/bowling first
        # Innings 1: batting_team bats first, bowling_team bowls first
        # Innings 2: batting_team bowls first (chasing), bowling_team bats first (set target)
        if innings == 1:
            batting_team_situation_wr = batting_team_bat_first_wr
            bowling_team_situation_wr = bowling_team_bowl_first_wr
        else:  # innings == 2
            batting_team_situation_wr = batting_team_bowl_first_wr
            bowling_team_situation_wr = bowling_team_bat_first_wr
        
        situation_advantage = batting_team_situation_wr - bowling_team_situation_wr
        
        # --- Venue-specific and vs-team stats (using feature store with fuzzy matching) ---
        # Look up player-venue batting stats
        batsman_venue_stats = self.feature_store.get_player_venue_batting_stats(batsman_1_name, venue) if hasattr(self.feature_store, 'get_player_venue_batting_stats') else None
        batsman_venue_avg = batsman_venue_stats.get('batsman_venue_avg', 38.0) if batsman_venue_stats else 38.0
        batsman_venue_sr = batsman_venue_stats.get('batsman_venue_sr', 61.0) if batsman_venue_stats else 61.0
        
        # Look up player-vs-team batting stats
        batsman_vs_team_stats = self.feature_store.get_player_vs_team_batting_stats(batsman_1_name, bowling_team) if hasattr(self.feature_store, 'get_player_vs_team_batting_stats') else None
        batsman_vs_team_avg = batsman_vs_team_stats.get('batsman_vs_team_avg', 31.5) if batsman_vs_team_stats else 31.5
        
        # Look up player-venue bowling stats
        bowler_venue_stats = self.feature_store.get_player_venue_bowling_stats(bowler_name, venue) if hasattr(self.feature_store, 'get_player_venue_bowling_stats') else None
        bowler_venue_econ = bowler_venue_stats.get('bowler_venue_econ', 4.2) if bowler_venue_stats else 4.2
        bowler_venue_sr = bowler_venue_stats.get('bowler_venue_sr', 516.0) if bowler_venue_stats else 516.0
        
        # Look up player-vs-team bowling stats
        bowler_vs_team_stats = self.feature_store.get_player_vs_team_bowling_stats(bowler_name, batting_team) if hasattr(self.feature_store, 'get_player_vs_team_bowling_stats') else None
        bowler_vs_team_econ = bowler_vs_team_stats.get('bowler_vs_team_econ', 5.7) if bowler_vs_team_stats else 5.7
        
        # Batting pair strength = sum of both batsmen's rolling averages
        b1_avg = batsman_1_stats.get('batsman_rolling_avg', 25.0)
        b2_avg = batsman_2_stats.get('batsman_rolling_avg', 25.0) if batsman_2_stats else 25.0
        batting_pair_strength = b1_avg + b2_avg  # ~50 for two average batters
        
        # Acceleration potential (how much faster can they score)
        # Typically SR - CRR, capped at reasonable value
        acceleration_potential = max(0, batsman_rolling_sr - current_run_rate * 16.67) if current_run_rate > 0 else 0
        
        # wickets_last_30: wickets in last 30 balls (5 overs)
        wickets_last_30 = 0.0
        if len(self.ball_history) >= 6:
            df_hist = pd.DataFrame(self.ball_history)
            if 'is_wicket' in df_hist.columns:
                last_30 = df_hist.tail(30)
                wickets_last_30 = last_30['is_wicket'].sum()
        
        # CRR times resources remaining
        crr_times_res = current_run_rate * resources_remaining
        
        # --- Inn1 Carryover Features (v6+) ---
        # These bridge the innings transition by carrying inn1 context into inn2.
        first_innings_score = scraped_data.get('first_innings_score')
        
        # venue_chase_success: fraction of chases won at this venue
        venue_chase_success = 1.0 - venue_bat_first_win_rate
        
        # target_above_par: how far inn1 score is above/below venue average
        if innings == 2 and first_innings_score is not None:
            target_above_par = first_innings_score - venue_avg_score
        else:
            target_above_par = 0.0
        
        # batting_won_toss: whether current batting team won the toss
        toss_winner = scraped_data.get('toss_winner')
        if toss_winner:
            batting_won_toss = int(batting_team == toss_winner)
        else:
            batting_won_toss = 0.5  # Unknown toss → neutral
        
        # Inn1 stats from crex live predictor (or defaults matching training)
        if innings == 2:
            inn1_wickets_lost = scraped_data.get('inn1_wickets_lost')
            inn1_wickets_lost = float(inn1_wickets_lost) if inn1_wickets_lost is not None else 5.0
            
            inn1_pp_runs = scraped_data.get('inn1_pp_runs')
            inn1_pp_runs = float(inn1_pp_runs) if inn1_pp_runs is not None else 45.0
            
            inn1_death_rr = scraped_data.get('inn1_death_rr')
            inn1_death_rr = float(inn1_death_rr) if inn1_death_rr is not None else 9.0
        else:
            inn1_wickets_lost = 5.0   # Default for inn1 (matches training)
            inn1_pp_runs = 45.0
            inn1_death_rr = 9.0
        
        # inn1_defendability: resource_win_prob at end of inn1
        if innings == 2 and first_innings_score is not None:
            inn1_wkts_for_defend = int(inn1_wickets_lost) if inn1_wickets_lost != 5.0 else 5
            defend_features = self.resource_calculator.calculate_all_features(
                innings=1, over=19, ball=5,
                current_score=first_innings_score,
                wickets_lost=inn1_wkts_for_defend,
                target_runs=None
            )
            inn1_defendability = defend_features.get('resource_win_prob', 0.5)
        else:
            inn1_defendability = 0.5
        
        # --- Construct Feature DataFrame ---
        features = {
            # Top 25 Features
            'expected_final_score': expected_final_score,
            'resource_win_prob': resource_win_prob,
            'score_vs_par': score_vs_par,
            'dls_pressure_index': dls_pressure_index,  # DLS-based pressure
            'projected_vs_venue_avg': projected_vs_venue_avg,
            'projected_score': projected_score,
            'is_powerplay': is_powerplay,
            'score_per_wicket': score_per_wicket,
            'run_rate_diff': run_rate_diff,
            'required_run_rate': required_run_rate,
            'chase_difficulty': chase_difficulty,
            'wickets_times_balls': wickets_times_balls,
            'pressure_index': pressure_index,  # RRR-based pressure (matches training)
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
            'dot_pct_last_12': rolling_stats['dot_pct_last_12'],
            'set_batter_exposure': float(max(
                scraped_data.get('batsman1_balls', 0) or 0,
                scraped_data.get('batsman2_balls', 0) or 0,
            )),
            'balls_since_wicket': float(self._balls_since_wicket),
            'wickets_last_6': rolling_stats['wickets_last_6'],
            
            # Player-venue and player-vs-team stats
            'batsman_venue_avg': batsman_venue_avg,
            'batsman_venue_sr': batsman_venue_sr,
            'batsman_vs_team_avg': batsman_vs_team_avg,
            'bowler_venue_econ': bowler_venue_econ,
            'bowler_venue_sr': bowler_venue_sr,
            'bowler_vs_team_econ': bowler_vs_team_econ,
            'batting_pair_strength': batting_pair_strength,
            
            # Additional derived features
            'acceleration_potential': acceleration_potential,
            'wickets_last_30': wickets_last_30,
            'crr_times_res': crr_times_res,
            'resources_remaining': resources_remaining,
            
            # Inn1 carryover features (v6+)
            'venue_chase_success': venue_chase_success,
            'target_above_par': target_above_par,
            'batting_won_toss': batting_won_toss,
            'inn1_wickets_lost': inn1_wickets_lost,
            'inn1_pp_runs': inn1_pp_runs,
            'inn1_death_rr': inn1_death_rr,
            'inn1_defendability': inn1_defendability,
            
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
