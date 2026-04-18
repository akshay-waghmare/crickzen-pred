"""
Parquet schema definitions for match state logging system.

This module defines the schema contracts for all match state data files:
- BallStateRecord: Per-ball state with features, calibration chain, market odds
- MatchMetadata: Per-match summary with outcome and recording metadata  
- VolatilityProfile: Per-match volatility metrics (model vs market)
- SignalEvent: Deviation events with price reversion labels

All schemas use PyArrow types for strict validation during Parquet write operations.
"""

import pyarrow as pa


# BallStateRecord Schema (80+ columns)
# File: data/match_states/<league>/<match_id>.parquet
BALL_STATE_SCHEMA = pa.schema([
    # Identity
    ('match_id', pa.string()),
    ('league', pa.string()),
    ('timestamp', pa.timestamp('ns')),
    ('innings', pa.int8()),
    ('over_number', pa.int8()),
    ('ball_in_over', pa.int8()),
    ('match_phase', pa.string()),  # "powerplay" / "middle" / "death"
    
    # Raw Match State
    ('batting_team', pa.string()),
    ('bowling_team', pa.string()),
    ('total_runs', pa.int16()),
    ('wickets', pa.int8()),
    ('overs', pa.float32()),
    ('current_run_rate', pa.float32()),
    ('required_run_rate', pa.float32()),
    ('target', pa.int16()),  # nullable
    ('batsman1_name', pa.string()),
    ('batsman1_runs', pa.int16()),
    ('batsman1_balls', pa.int16()),
    ('batsman2_name', pa.string()),
    ('batsman2_runs', pa.int16()),
    ('batsman2_balls', pa.int16()),
    ('bowler_name', pa.string()),
    ('venue', pa.string()),
    ('toss_winner', pa.string()),
    ('toss_decision', pa.string()),
    
    # Computed Features (all float32, matching training schema)
    ('resource_pct', pa.float32()),
    ('resource_win_prob', pa.float32()),
    ('expected_final_score', pa.float32()),
    ('projected_score', pa.float32()),
    ('projected_vs_venue_avg', pa.float32()),
    ('score_vs_par', pa.float32()),
    ('pressure_index', pa.float32()),
    ('dls_pressure_index', pa.float32()),
    ('team_strength_diff', pa.float32()),
    ('batting_team_win_rate', pa.float32()),
    ('bowling_team_win_rate', pa.float32()),
    ('batting_team_situation_wr', pa.float32()),
    ('bowling_team_situation_wr', pa.float32()),
    ('situation_advantage', pa.float32()),
    ('runs_last_12', pa.float32()),
    ('runs_last_18', pa.float32()),
    ('wickets_last_12', pa.float32()),
    ('wickets_last_30', pa.float32()),
    ('boundary_pct_last_18', pa.float32()),
    ('chase_difficulty', pa.float32()),
    ('score_per_wicket', pa.float32()),
    ('wickets_times_balls', pa.float32()),
    ('rrr_times_wickets', pa.float32()),
    ('batting_pair_strength', pa.float32()),
    ('acceleration_potential', pa.float32()),
    ('crr_times_res', pa.float32()),
    ('resources_remaining', pa.float32()),
    ('run_rate_diff', pa.float32()),
    ('is_powerplay', pa.bool_()),
    ('is_death', pa.bool_()),
    ('venue_avg_score', pa.float32()),
    ('venue_avg_wickets', pa.float32()),
    ('venue_bat_first_wr', pa.float32()),
    ('batsman_venue_avg', pa.float32()),
    ('batsman_venue_sr', pa.float32()),
    ('batsman_vs_team_avg', pa.float32()),
    ('bowler_venue_econ', pa.float32()),
    ('bowler_venue_sr', pa.float32()),
    ('bowler_vs_team_econ', pa.float32()),
    
    # Calibration Chain (all float32)
    ('model_raw_prob', pa.float32()),
    ('model_smoothed_prob', pa.float32()),
    ('model_calibrated_combined', pa.float32()),
    ('model_calibrated_innings', pa.float32()),
    ('model_calibrated_phase', pa.float32()),
    ('model_calibrated_per_over', pa.float32()),
    ('model_league_calibrated', pa.float32()),  # nullable
    ('model_final_prob', pa.float32()),
    
    # Market Odds
    ('market_fav_team', pa.string()),
    ('market_back_odds', pa.float32()),
    ('market_lay_odds', pa.float32()),
    ('market_fav_prob', pa.float32()),
    ('market_batting_team_prob', pa.float32()),  # nullable
    ('market_bowling_team_prob', pa.float32()),  # nullable
    
    # Deviation Metrics
    ('deviation', pa.float32()),  # nullable
    ('deviation_abs', pa.float32()),  # nullable
    ('deviation_bucket', pa.string()),  # nullable
    ('deviation_direction', pa.string()),  # nullable
    ('model_prob_delta', pa.float32()),  # nullable
    ('market_prob_delta', pa.float32()),  # nullable
    
    # Team Strength Tier
    ('batting_team_tier', pa.string()),
    ('bowling_team_tier', pa.string()),
    
    # Reduced-over / DLS fields
    ('total_overs', pa.int16()),         # Total overs per innings (default 20)
    ('revised_target', pa.int16()),      # DLS revised target (nullable)
    
    # Ensemble blending
    ('ensemble_prob', pa.float32()),     # Blended model+market probability (nullable)
    ('ensemble_alpha', pa.float32()),    # Blending weight used (nullable)
    ('ensemble_source', pa.string()),    # "ensemble" or "model_only" (nullable)
    
    # Versioning
    ('model_version', pa.string()),
    ('feature_store_version', pa.string()),
])


# MatchMetadata Schema
# File: data/match_states/<league>/match_metadata.parquet
MATCH_METADATA_SCHEMA = pa.schema([
    ('match_id', pa.string()),
    ('match_url', pa.string()),
    ('league', pa.string()),
    ('date', pa.timestamp('ns')),
    ('venue', pa.string()),
    ('team_a', pa.string()),  # Team batting first
    ('team_b', pa.string()),  # Team batting second
    ('team_a_tier', pa.string()),
    ('team_b_tier', pa.string()),
    ('toss_winner', pa.string()),
    ('toss_decision', pa.string()),
    ('winner', pa.string()),  # nullable
    ('team_a_score', pa.string()),  # nullable
    ('team_b_score', pa.string()),  # nullable
    ('result_type', pa.string()),  # "completed" / "no_result" / "in_progress"
    ('model_version', pa.string()),
    ('feature_store_version', pa.string()),
    ('total_balls_recorded', pa.int32()),
    ('recording_start', pa.timestamp('ns')),
    ('recording_end', pa.timestamp('ns')),
])


# SignalEvent Schema (post-match computed)
# File: data/match_states/<league>/signal_events.parquet
SIGNAL_EVENT_SCHEMA = pa.schema([
    ('match_id', pa.string()),
    ('league', pa.string()),
    ('ball_index', pa.int32()),
    ('innings', pa.int8()),
    ('over_number', pa.int8()),
    ('match_phase', pa.string()),
    ('batting_team', pa.string()),
    ('batting_team_tier', pa.string()),
    ('deviation', pa.float32()),
    ('deviation_bucket', pa.string()),
    ('model_prob', pa.float32()),
    ('market_prob', pa.float32()),
    ('team_strength_diff', pa.float32()),
    ('required_run_rate', pa.float32()),
    ('wickets', pa.int8()),
    ('resources_remaining', pa.float32()),
    ('price_reverted', pa.bool_()),
    ('reversion_magnitude', pa.float32()),
    ('balls_to_reversion', pa.int32()),  # nullable
    ('match_winner', pa.string()),
    ('model_team_won', pa.bool_()),
])


# VolatilityProfile Schema (post-match computed)
# File: data/match_states/<league>/volatility_profiles.parquet
VOLATILITY_PROFILE_SCHEMA = pa.schema([
    ('match_id', pa.string()),
    ('league', pa.string()),
    ('model_volatility', pa.float32()),
    ('market_volatility', pa.float32()),
    ('volatility_ratio', pa.float32()),
    ('model_max_swing', pa.float32()),
    ('market_max_swing', pa.float32()),
    ('inn1_model_volatility', pa.float32()),
    ('inn1_market_volatility', pa.float32()),
    ('inn2_model_volatility', pa.float32()),  # nullable
    ('inn2_market_volatility', pa.float32()),  # nullable
])


# Deviation buckets (0.05 increments)
DEVIATION_BUCKETS = [
    (0.00, 0.05, "0.00-0.05"),
    (0.05, 0.10, "0.05-0.10"),
    (0.10, 0.15, "0.10-0.15"),
    (0.15, 0.20, "0.15-0.20"),
    (0.20, 0.25, "0.20-0.25"),
    (0.25, 0.30, "0.25-0.30"),
    (0.30, float('inf'), "0.30+"),
]


def get_deviation_bucket(deviation_abs: float) -> str:
    """
    Classifies absolute deviation into bucket string.
    
    Args:
        deviation_abs: Absolute value of model-market deviation
        
    Returns:
        Bucket string (e.g., "0.10-0.15", "0.30+")
    """
    for lower, upper, label in DEVIATION_BUCKETS:
        if lower <= deviation_abs < upper:
            return label
    return "0.30+"  # Fallback for edge cases


def get_deviation_direction(deviation: float, threshold: float = 0.02) -> str:
    """
    Classifies deviation direction.
    
    Args:
        deviation: Signed deviation (model_prob - market_prob)
        threshold: Alignment threshold (default 0.02)
        
    Returns:
        "model_higher" | "model_lower" | "aligned"
    """
    if abs(deviation) <= threshold:
        return "aligned"
    return "model_higher" if deviation > 0 else "model_lower"
