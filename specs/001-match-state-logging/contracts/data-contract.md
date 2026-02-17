# Data Contract: Match State Parquet Schema

## BallStateRecord Schema

**File**: `data/match_states/<league>/<match_id>.parquet`  
**Format**: Apache Parquet  
**Compression**: snappy (default)

### Column Specification

```python
BALL_STATE_SCHEMA = {
    # Identity
    'match_id': 'string',
    'league': 'string',
    'timestamp': 'datetime64[ns]',
    'innings': 'int8',
    'over_number': 'int8',
    'ball_in_over': 'int8',
    'match_phase': 'string',  # "powerplay" / "middle" / "death"
    
    # Raw Match State
    'batting_team': 'string',
    'bowling_team': 'string',
    'total_runs': 'int16',
    'wickets': 'int8',
    'overs': 'float32',
    'current_run_rate': 'float32',
    'required_run_rate': 'float32',
    'target': 'Int16',  # nullable
    'batsman1_name': 'string',
    'batsman1_runs': 'int16',
    'batsman1_balls': 'int16',
    'batsman2_name': 'string',
    'batsman2_runs': 'int16',
    'batsman2_balls': 'int16',
    'bowler_name': 'string',
    'venue': 'string',
    'toss_winner': 'string',
    'toss_decision': 'string',
    
    # Computed Features (all float32, matching training schema)
    'resource_pct': 'float32',
    'resource_win_prob': 'float32',
    'expected_final_score': 'float32',
    'projected_score': 'float32',
    'projected_vs_venue_avg': 'float32',
    'score_vs_par': 'float32',
    'pressure_index': 'float32',
    'dls_pressure_index': 'float32',
    'team_strength_diff': 'float32',
    'batting_team_win_rate': 'float32',
    'bowling_team_win_rate': 'float32',
    'batting_team_situation_wr': 'float32',
    'bowling_team_situation_wr': 'float32',
    'situation_advantage': 'float32',
    'runs_last_12': 'float32',
    'runs_last_18': 'float32',
    'wickets_last_12': 'float32',
    'wickets_last_30': 'float32',
    'boundary_pct_last_18': 'float32',
    'chase_difficulty': 'float32',
    'score_per_wicket': 'float32',
    'wickets_times_balls': 'float32',
    'rrr_times_wickets': 'float32',
    'batting_pair_strength': 'float32',
    'acceleration_potential': 'float32',
    'crr_times_res': 'float32',
    'resources_remaining': 'float32',
    'run_rate_diff': 'float32',
    'is_powerplay': 'bool',
    'is_death': 'bool',
    'venue_avg_score': 'float32',
    'venue_avg_wickets': 'float32',
    'venue_bat_first_wr': 'float32',
    'batsman_venue_avg': 'float32',
    'batsman_venue_sr': 'float32',
    'batsman_vs_team_avg': 'float32',
    'bowler_venue_econ': 'float32',
    'bowler_venue_sr': 'float32',
    'bowler_vs_team_econ': 'float32',
    
    # Calibration Chain (all float32)
    'model_raw_prob': 'float32',
    'model_smoothed_prob': 'float32',
    'model_calibrated_combined': 'float32',
    'model_calibrated_innings': 'float32',
    'model_calibrated_phase': 'float32',
    'model_calibrated_per_over': 'float32',
    'model_league_calibrated': 'Float32',  # nullable
    'model_final_prob': 'float32',
    
    # Market Odds
    'market_fav_team': 'string',
    'market_back_odds': 'float32',
    'market_lay_odds': 'float32',
    'market_fav_prob': 'float32',
    'market_batting_team_prob': 'Float32',  # nullable (derived)
    'market_bowling_team_prob': 'Float32',  # nullable (derived)
    
    # Deviation Metrics
    'deviation': 'Float32',           # nullable (missing if no market odds)
    'deviation_abs': 'Float32',       # nullable
    'deviation_bucket': 'string',     # nullable
    'deviation_direction': 'string',  # nullable
    'model_prob_delta': 'Float32',    # nullable (null for first ball)
    'market_prob_delta': 'Float32',   # nullable
    
    # Team Strength Tier
    'batting_team_tier': 'string',
    'bowling_team_tier': 'string',
    
    # Versioning
    'model_version': 'string',
    'feature_store_version': 'string',
}
```

## MatchMetadata Schema

**File**: `data/match_states/<league>/match_metadata.parquet`

```python
MATCH_METADATA_SCHEMA = {
    'match_id': 'string',
    'match_url': 'string',
    'league': 'string',
    'date': 'datetime64[ns]',
    'venue': 'string',
    'team_a': 'string',           # Team batting first
    'team_b': 'string',           # Team batting second
    'team_a_tier': 'string',
    'team_b_tier': 'string',
    'toss_winner': 'string',
    'toss_decision': 'string',
    'winner': 'string',           # nullable — null if no result
    'team_a_score': 'string',     # nullable — e.g. "185/4"
    'team_b_score': 'string',     # nullable
    'result_type': 'string',      # "completed" / "no_result" / "in_progress"
    'model_version': 'string',
    'feature_store_version': 'string',
    'total_balls_recorded': 'int32',
    'recording_start': 'datetime64[ns]',
    'recording_end': 'datetime64[ns]',
}
```

## SignalEvent Schema (post-match computed)

**File**: `data/match_states/<league>/signal_events.parquet`

```python
SIGNAL_EVENT_SCHEMA = {
    'match_id': 'string',
    'league': 'string',
    'ball_index': 'int32',
    'innings': 'int8',
    'over_number': 'int8',
    'match_phase': 'string',
    'batting_team': 'string',
    'batting_team_tier': 'string',
    'deviation': 'float32',
    'deviation_bucket': 'string',
    'model_prob': 'float32',
    'market_prob': 'float32',
    'team_strength_diff': 'float32',
    'required_run_rate': 'float32',
    'wickets': 'int8',
    'resources_remaining': 'float32',
    'price_reverted': 'bool',
    'reversion_magnitude': 'float32',
    'balls_to_reversion': 'Int32',  # nullable
    'match_winner': 'string',
    'model_team_won': 'bool',
}
```

## VolatilityProfile Schema (post-match computed)

**File**: `data/match_states/<league>/volatility_profiles.parquet`

```python
VOLATILITY_PROFILE_SCHEMA = {
    'match_id': 'string',
    'league': 'string',
    'model_volatility': 'float32',
    'market_volatility': 'float32',
    'volatility_ratio': 'float32',
    'model_max_swing': 'float32',
    'market_max_swing': 'float32',
    'inn1_model_volatility': 'float32',
    'inn1_market_volatility': 'float32',
    'inn2_model_volatility': 'Float32',  # nullable (match may end in 1st innings)
    'inn2_market_volatility': 'Float32',
}
```
