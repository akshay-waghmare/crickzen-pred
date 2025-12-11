# WBBL Model v3 Documentation

## Overview

WBBL Model v3 is an XGBoost-based win probability prediction model for Women's Big Bash League (WBBL) cricket matches. This version includes critical bug fixes that significantly improved model accuracy.

## Model Performance

| Version | Test Brier Score | Improvement |
|---------|-----------------|-------------|
| v1 | 0.1836 | Baseline |
| v2 | 0.1828 | 0.4% better |
| **v3** | **0.1737** | **5.0% better than v2** |

## Key Fixes in v3

### 1. Duplicate Row Removal

**Problem:** The raw ball-by-ball data had every row duplicated (229,824 rows → 114,912 unique rows).

**Impact:** 
- Model saw each training example twice, reducing effective data diversity
- Venue statistics were inflated (counting runs twice)

**Fix:** Added deduplication in `src/bbl_pipeline/data/processor.py`:
```python
df = df.drop_duplicates(subset=['match_id', 'innings', 'over', 'ball', 'batter_id', 'bowler_id'])
```

### 2. Venue Average Score Correction

**Problem:** `venue_avg_score` was calculated using total match runs (both innings) instead of first innings only.

| Venue | Before Fix | After Fix |
|-------|-----------|-----------|
| North Sydney Oval | ~310 | ~148 |
| Adelaide Oval | ~252 | ~126 |
| Average | ~280 | ~136 |

**Impact:** The `score_vs_par` feature was completely wrong (e.g., -106 instead of -5), confusing the model about how well a team was performing relative to venue expectations.

**Fix:** Created `scripts/fix_venue_stats.py` to recalculate using first innings scores only.

### 3. Player-Venue & Player-vs-Team Lookup Tables

**Problem:** Live inference was using default values (0.0) for player-specific features because the feature store didn't have the necessary lookup tables.

**Solution:** Created four new lookup tables in the feature store:
- `player_venue_batting.parquet` (3,312 player-venue combinations)
- `player_vs_team_batting.parquet` (1,479 player-team combinations)
- `player_venue_bowling.parquet` (2,479 bowler-venue combinations)
- `player_vs_team_bowling.parquet` (1,089 bowler-team combinations)

### 4. WBBL Team Abbreviation Mapping

**Problem:** Team names from live scraper (e.g., "SYS-W") didn't match historical data (e.g., "Sydney Sixers").

**Fix:** Added `WBBL_TEAM_ALIASES` mapping in `src/bbl_pipeline/features/store.py`:
```python
WBBL_TEAM_ALIASES = {
    "SYS-W": "Sydney Sixers",
    "PRS-W": "Perth Scorchers",
    "ADL-W": "Adelaide Strikers",
    "HBH-W": "Hobart Hurricanes",
    "BRH-W": "Brisbane Heat",
    "MLR-W": "Melbourne Renegades",
    "MLS-W": "Melbourne Stars",
    "STR-W": "Sydney Thunder"
}
```

## Model Architecture

- **Algorithm:** XGBoost Classifier
- **Objective:** Binary classification (win/loss)
- **Calibration:** None (raw probabilities performed best)

### Hyperparameters

```python
{
    'subsample': 0.8,
    'reg_lambda': 2,
    'reg_alpha': 1,
    'n_estimators': 500,
    'min_child_weight': 5,
    'max_depth': 4,
    'learning_rate': 0.01,
    'colsample_bytree': 0.4
}
```

## Features (44 total)

### Match Situation Features
- `current_run_rate` - Current scoring rate
- `required_run_rate` - Rate needed to win (2nd innings)
- `run_rate_diff` - Difference between CRR and RRR
- `overs_remaining` - Overs left in innings
- `wickets_times_balls` - Wickets lost × balls faced
- `score_per_wicket` - Runs per wicket lost

### DLS Resource Features
- `resources_remaining` - Remaining batting resources (0-1)
- `resource_pct` - Resources as percentage
- `resource_win_prob` - Win probability based on resources
- `dls_pressure_index` - Pressure based on resources

### Phase Features
- `is_powerplay` - First 6 overs
- `is_middle_overs` - Overs 7-15
- `is_death_overs` - Final 5 overs

### Recent Form Features
- `runs_last_12` - Runs in last 12 balls
- `runs_last_18` - Runs in last 18 balls
- `boundary_pct_last_18` - Boundary percentage
- `wickets_last_12` - Wickets in last 12 balls
- `wickets_last_30` - Wickets in last 30 balls

### Player Features
- `batsman_rolling_avg` - Striker's recent average
- `batsman_rolling_sr` - Striker's recent strike rate
- `batsman_venue_avg` - Striker's average at this venue
- `batsman_venue_sr` - Striker's strike rate at this venue
- `batsman_vs_team_avg` - Striker's average vs this bowling team
- `bowler_rolling_econ` - Bowler's recent economy
- `bowler_rolling_sr` - Bowler's recent strike rate
- `bowler_venue_econ` - Bowler's economy at this venue
- `bowler_vs_team_econ` - Bowler's economy vs this batting team

### Team Features
- `batting_team_win_rate` - Batting team's historical win rate
- `bowling_team_win_rate` - Bowling team's historical win rate
- `batting_team_situation_wr` - Situational win rate
- `bowling_team_situation_wr` - Situational win rate
- `team_strength_diff` - Difference in team strengths

### Projection Features
- `projected_score` - Expected final score
- `expected_final_score` - Alternative projection
- `projected_vs_venue_avg` - Projected vs venue average
- `chase_difficulty` - How hard is the chase (2nd innings)

## File Locations

### Model Files
```
models/wbbl_champion_v3/
├── champion_model.joblib      # Trained XGBoost model
├── champion_metadata.json     # Model metadata
└── feature_names.json         # Feature list
```

### Feature Store v3
```
data/wbbl_feature_store_v3/
├── venue_stats.parquet              # Venue statistics
├── player_stats.parquet             # Player rolling stats
├── player_venue_batting.parquet     # Player-venue batting stats
├── player_vs_team_batting.parquet   # Player-vs-team batting stats
├── player_venue_bowling.parquet     # Bowler-venue stats
└── player_vs_team_bowling.parquet   # Bowler-vs-team stats
```

### Training Data
```
data/wbbl_features_v3/
├── training.parquet           # Full training data
└── training_sampled.parquet   # Sampled (18,710 rows)
```

## Usage

### Live Inference

```bash
python -m bbl_pipeline.inference.crex_live_predictor \
  --match-url "https://crex.com/scoreboard/..." \
  --model-dir models/wbbl_champion_v3 \
  --feature-store-dir data/wbbl_feature_store_v3
```

### Streamlit App

```bash
streamlit run src/bbl_pipeline/app/streamlit_app.py
```

## Changelog

### v3 (December 2025)
- Fixed duplicate row issue (5% Brier score improvement)
- Corrected venue_avg_score calculation
- Added player-venue and player-vs-team lookup tables
- Added WBBL team abbreviation mapping
- Created Streamlit visualization app

### v2 (December 2025)
- Hyperparameter tuning with Optuna
- Feature selection optimization
- 0.4% improvement over v1

### v1 (November 2025)
- Initial XGBoost model
- Basic feature engineering
