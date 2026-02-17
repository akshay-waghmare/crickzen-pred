# Data Model: Match State Logging System

**Feature**: `001-match-state-logging`  
**Date**: February 17, 2026

## Entity Relationship

```
MatchMetadata (1) ──── (N) BallStateRecord
     │                        │
     │                        ├── RawMatchState (embedded)
     │                        ├── ComputedFeatures (embedded)
     │                        ├── CalibrationChain (embedded)
     │                        ├── MarketOdds (embedded)
     │                        └── DeviationMetrics (embedded)
     │
     └─── (1) MatchOutcome (appended post-match)

LeagueConfig (1) ──── (N) MatchMetadata
```

## Entities

### 1. BallStateRecord (primary entity — one row per ball)

**Storage**: `data/match_states/<league>/<match_id>.parquet`

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| **Identity** | | | |
| `match_id` | `str` | CREX URL / filename | Unique match identifier |
| `league` | `str` | `--league` arg | League code (bbl, sa20, ilt20, etc.) |
| `timestamp` | `datetime` | `datetime.now()` | When this state was captured |
| `innings` | `int` | MatchState | 1 or 2 |
| `over_number` | `int` | MatchState | 1-20 |
| `ball_in_over` | `int` | MatchState | 0-5 |
| **Raw Match State** | | | |
| `batting_team` | `str` | MatchState | Full team name |
| `bowling_team` | `str` | MatchState | Full team name |
| `total_runs` | `int` | MatchState | Cumulative runs scored |
| `wickets` | `int` | MatchState | Wickets fallen |
| `overs` | `float` | MatchState | e.g. 12.3 |
| `current_run_rate` | `float` | MatchState | CRR |
| `required_run_rate` | `float` | MatchState | RRR (0 if 1st innings) |
| `target` | `int` or `null` | MatchState | Target (2nd innings only) |
| `batsman1_name` | `str` | MatchState | Striker name |
| `batsman1_runs` | `int` | MatchState | Striker runs |
| `batsman1_balls` | `int` | MatchState | Striker balls faced |
| `batsman2_name` | `str` | MatchState | Non-striker name |
| `batsman2_runs` | `int` | MatchState | Non-striker runs |
| `batsman2_balls` | `int` | MatchState | Non-striker balls faced |
| `bowler_name` | `str` | MatchState | Current bowler |
| `venue` | `str` | MatchState | Venue name |
| `toss_winner` | `str` | MatchState | Toss winner |
| `toss_decision` | `str` | MatchState | "bat" or "bowl" |
| **Computed Features** (50+ cols) | | | |
| `resource_pct` | `float` | RealTimeFeatureMapper | DLS resource % remaining |
| `resource_win_prob` | `float` | RealTimeFeatureMapper | Resource-based win prob |
| `expected_final_score` | `float` | RealTimeFeatureMapper | Projected final score |
| `projected_score` | `float` | RealTimeFeatureMapper | Run-rate projected score |
| `projected_vs_venue_avg` | `float` | RealTimeFeatureMapper | Score vs venue average |
| `score_vs_par` | `float` | RealTimeFeatureMapper | Score vs DLS par |
| `pressure_index` | `float` | RealTimeFeatureMapper | RRR-based pressure metric |
| `dls_pressure_index` | `float` | RealTimeFeatureMapper | DLS-based pressure |
| `team_strength_diff` | `float` | RealTimeFeatureMapper | Batting WR - Bowling WR |
| `batting_team_win_rate` | `float` | RealTimeFeatureMapper | Historical win rate |
| `bowling_team_win_rate` | `float` | RealTimeFeatureMapper | Historical win rate |
| `batting_team_situation_wr` | `float` | RealTimeFeatureMapper | Situation-specific WR |
| `bowling_team_situation_wr` | `float` | RealTimeFeatureMapper | Situation-specific WR |
| `situation_advantage` | `float` | RealTimeFeatureMapper | Situation WR diff |
| `runs_last_12` | `int` | RealTimeFeatureMapper | Rolling runs (12 balls) |
| `runs_last_18` | `int` | RealTimeFeatureMapper | Rolling runs (18 balls) |
| `wickets_last_12` | `int` | RealTimeFeatureMapper | Rolling wickets (12 balls) |
| `wickets_last_30` | `int` | RealTimeFeatureMapper | Rolling wickets (30 balls) |
| `boundary_pct_last_18` | `float` | RealTimeFeatureMapper | Boundary % (18 balls) |
| `chase_difficulty` | `float` | RealTimeFeatureMapper | Chase difficulty index |
| `score_per_wicket` | `float` | RealTimeFeatureMapper | Runs / wickets ratio |
| `wickets_times_balls` | `float` | RealTimeFeatureMapper | Interaction feature |
| `rrr_times_wickets` | `float` | RealTimeFeatureMapper | Interaction feature |
| `batting_pair_strength` | `float` | RealTimeFeatureMapper | Current pair quality |
| `acceleration_potential` | `float` | RealTimeFeatureMapper | Scoring acceleration |
| `crr_times_res` | `float` | RealTimeFeatureMapper | CRR × resources |
| `resources_remaining` | `float` | RealTimeFeatureMapper | Resources left |
| `run_rate_diff` | `float` | RealTimeFeatureMapper | CRR - RRR |
| `is_powerplay` | `bool` | RealTimeFeatureMapper | Overs 1-6 |
| `is_death` | `bool` | RealTimeFeatureMapper | Overs 16-20 |
| `venue_avg_score` | `float` | FeatureStore | Venue average score |
| `venue_bat_first_wr` | `float` | FeatureStore | Venue bat-first WR |
| *(+ remaining features from mapper)* | | | |
| **Calibration Chain** | | | |
| `model_raw_prob` | `float` | Predictor | Raw XGB+LR ensemble output |
| `model_smoothed_prob` | `float` | Predictor | Blended raw+calibrated |
| `model_calibrated_combined` | `float` | Predictor | Single isotonic calibrator |
| `model_calibrated_innings` | `float` | Predictor | Innings-specific isotonic |
| `model_calibrated_phase` | `float` | Predictor | Innings×phase isotonic |
| `model_calibrated_per_over` | `float` | Predictor | Per-over brier-optimized |
| `model_league_calibrated` | `float` or `null` | Predictor | League temp/platt scaling |
| `model_final_prob` | `float` | Predictor | Final returned probability |
| **Market Odds** | | | |
| `market_fav_team` | `str` | CREX API | Which team is market favorite |
| `market_back_odds` | `float` | CREX API | Back odds (decimal) |
| `market_lay_odds` | `float` | CREX API | Lay odds (decimal) |
| `market_fav_prob` | `float` | CREX API | Implied prob (favorite) |
| `market_batting_team_prob` | `float` | Computed | Implied prob for batting team |
| `market_bowling_team_prob` | `float` | Computed | Implied prob for bowling team |
| **Deviation Metrics** | | | |
| `deviation` | `float` | Computed | model_final_prob - market_batting_team_prob (signed) |
| `deviation_abs` | `float` | Computed | abs(deviation) |
| `deviation_bucket` | `str` | Computed | "0.00-0.05", "0.05-0.10", ..., "0.30+" |
| `deviation_direction` | `str` | Computed | "model_higher" / "model_lower" / "aligned" |
| `model_prob_delta` | `float` | Computed | Change from previous ball's model_final_prob |
| `market_prob_delta` | `float` | Computed | Change from previous ball's market_batting_team_prob |
| **Team Strength Tier** | | | |
| `batting_team_tier` | `str` | FeatureStore | "top" / "mid" / "bottom" |
| `bowling_team_tier` | `str` | FeatureStore | "top" / "mid" / "bottom" |
| **Versioning** | | | |
| `model_version` | `str` | `--model-dir` basename | e.g. "t20_male_v2" |
| `feature_store_version` | `str` | `--feature-store-dir` basename | e.g. "t20_male_feature_store_v2" |
| `match_phase` | `str` | Computed | "powerplay" / "middle" / "death" |

### 2. MatchMetadata (one row per match)

**Storage**: `data/match_states/<league>/match_metadata.parquet`

| Field | Type | Description |
|-------|------|-------------|
| `match_id` | `str` | Unique match identifier |
| `match_url` | `str` | CREX match URL |
| `league` | `str` | League code |
| `date` | `date` | Match date |
| `venue` | `str` | Venue name |
| `team_a` | `str` | Team batting first |
| `team_b` | `str` | Team batting second |
| `team_a_tier` | `str` | Strength tier at match time |
| `team_b_tier` | `str` | Strength tier at match time |
| `toss_winner` | `str` | Toss winner |
| `toss_decision` | `str` | "bat" or "bowl" |
| `winner` | `str` or `null` | Match winner (null if no result) |
| `team_a_score` | `str` or `null` | e.g. "185/4" |
| `team_b_score` | `str` or `null` | e.g. "170/8" |
| `result_type` | `str` | "completed" / "no_result" / "abandoned" |
| `model_version` | `str` | Model used for predictions |
| `feature_store_version` | `str` | Feature store used |
| `total_balls_recorded` | `int` | Number of ball states captured |
| `recording_start` | `datetime` | When recording started |
| `recording_end` | `datetime` | When recording ended |

### 3. VolatilityProfile (one row per match — computed post-match)

**Storage**: Computed from BallStateRecord, stored in `data/match_states/<league>/volatility_profiles.parquet`

| Field | Type | Description |
|-------|------|-------------|
| `match_id` | `str` | Match identifier |
| `league` | `str` | League code |
| `model_volatility` | `float` | Std dev of model_prob_delta across all balls |
| `market_volatility` | `float` | Std dev of market_prob_delta across all balls |
| `volatility_ratio` | `float` | model_volatility / market_volatility |
| `model_max_swing` | `float` | Max single-ball model probability change |
| `market_max_swing` | `float` | Max single-ball market probability change |
| `inn1_model_volatility` | `float` | 1st innings model volatility |
| `inn1_market_volatility` | `float` | 1st innings market volatility |
| `inn2_model_volatility` | `float` | 2nd innings model volatility |
| `inn2_market_volatility` | `float` | 2nd innings market volatility |

### 4. SignalEvent (deviation events exceeding threshold — computed post-match)

**Storage**: Computed from BallStateRecord, stored in `data/match_states/<league>/signal_events.parquet`

| Field | Type | Description |
|-------|------|-------------|
| `match_id` | `str` | Match identifier |
| `league` | `str` | League code |
| `ball_index` | `int` | Ball number in match (0-indexed) |
| `innings` | `int` | 1 or 2 |
| `over_number` | `int` | Over |
| `match_phase` | `str` | "powerplay" / "middle" / "death" |
| `batting_team` | `str` | Team batting |
| `batting_team_tier` | `str` | "top" / "mid" / "bottom" |
| `deviation` | `float` | Signed deviation |
| `deviation_bucket` | `str` | Size bucket |
| `model_prob` | `float` | Model probability at event |
| `market_prob` | `float` | Market probability at event |
| `team_strength_diff` | `float` | Feature value at event |
| `required_run_rate` | `float` | RRR at event (0 if 1st innings) |
| `wickets` | `int` | Wickets at event |
| `resources_remaining` | `float` | DLS resources at event |
| `price_reverted` | `bool` | Did market subsequently move toward model? |
| `reversion_magnitude` | `float` | How far market moved toward model (0.0-1.0) |
| `balls_to_reversion` | `int` or `null` | Balls until reversion (null if never) |
| `match_winner` | `str` | Actual match winner |
| `model_team_won` | `bool` | Did the team the model favored win? |

## Validation Rules

1. `innings` must be 1 or 2
2. `over_number` must be 1-20
3. `ball_in_over` must be 0-5
4. `wickets` must be 0-10
5. `model_final_prob` must be 0.0-1.0
6. `market_batting_team_prob` must be 0.0-1.0 (or null if unavailable)
7. `deviation_bucket` must be one of: "0.00-0.05", "0.05-0.10", "0.10-0.20", "0.20-0.30", "0.30+"
8. `deviation_direction` must be one of: "model_higher", "model_lower", "aligned"
9. `batting_team_tier` must be one of: "top", "mid", "bottom"
10. `match_phase` must be one of: "powerplay", "middle", "death"

## State Transitions

```
Match Lifecycle:
  IDLE → RECORDING (--record-states flag + match starts)
    → per ball: append BallStateRecord
    → on innings break: flush buffer to disk
  RECORDING → COMPLETED (match ends)
    → write MatchMetadata
    → flush final buffer
  COMPLETED → ANALYZED (post-match processing)
    → compute VolatilityProfile
    → compute SignalEvents (with price reversion labels)
    → consolidate into league-level files
```
