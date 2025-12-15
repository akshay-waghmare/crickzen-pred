# Model Registry Maintenance Guide

## Overview

The `models/model_registry.json` file is the single source of truth for all active models and their associated feature stores. It tracks model versions, performance metrics, and feature store metadata.

---

## Registry Structure

### Top-Level Fields
- `last_updated`: Date when registry was last updated (ISO format: YYYY-MM-DD)
- `active_models`: Dictionary of active models by league (BBL, ILT20, etc.)

### Model Entry Structure

```json
{
  "BBL": {
    "path": "models/bbl_v8",
    "version": "v8",
    "description": "Model architecture + calibration + metrics",
    "feature_store": {
      "path": "data/bbl_feature_store_v2",
      "version": "v2",
      "generated_date": "2025-12-15",
      "training_data_matches": 600,
      "statistics": {
        "teams": 8,
        "players": 508,
        "venues": 31,
        "team_columns": [...],
        "player_columns": [...],
        "venue_columns": [...]
      },
      "recent_changes": {
        "date": "2025-12-15",
        "description": "What changed",
        "impact": "How it affects predictions"
      }
    }
  }
}
```

---

## When to Update the Registry

### 1. After Regenerating Feature Store

**Trigger**: Running the process command
```bash
bbl-pipeline process \
  --input-dir data/bbl_raw/matches \
  --output-dir data/bbl_features_v2 \
  --feature-store-dir data/bbl_feature_store_v2
```

**Update Steps**:
1. Extract feature store metadata:
   ```bash
   python -c "
   import pandas as pd
   import json
   from pathlib import Path
   
   fs_path = Path('data/bbl_feature_store_v2')
   
   # Get team stats
   teams = pd.read_parquet(fs_path / 'team_ratings.parquet')
   team_cols = teams.columns.tolist()
   team_count = len(teams)
   
   # Get player stats
   players = pd.read_parquet(fs_path / 'player_stats.parquet')
   player_cols = players.columns.tolist()
   player_count = len(players)
   
   # Get venue stats
   venues = pd.read_parquet(fs_path / 'venue_stats.parquet')
   venue_cols = venues.columns.tolist()
   venue_count = len(venues)
   
   print(f'Teams: {team_count}, Players: {player_count}, Venues: {venue_count}')
   print(f'Team columns: {team_cols}')
   print(f'Player columns: {player_cols}')
   print(f'Venue columns: {venue_cols}')
   "
   ```

2. Update `models/model_registry.json` with:
   - `generated_date`: Today's date
   - `training_data_matches`: Number of matches used to generate stats
   - `statistics`: Team/player/venue counts and column lists
   - `recent_changes`: Description of what changed and why

3. Commit changes:
   ```bash
   git add models/model_registry.json data/bbl_feature_store_v2/
   git commit -m "chore: updated BBL feature store to v2.1 with latest season data
   
   - Regenerated team/player/venue stats
   - Added bat_first_wr and bowl_first_wr columns
   - Training data: 600 matches (up from 580)
   - Player count: 508 (new players added this season)"
   ```

### 2. After Retraining Model

**Trigger**: Running the train command
```bash
bbl-pipeline train \
  --input-file data/bbl_features_v2/training.parquet \
  --output-dir models/bbl_v8 \
  --calibration
```

**Update Steps**:
1. Get model metrics:
   ```bash
   # Metrics are logged during training - extract from logs
   # Or use evaluation script
   ```

2. Update `description` field with new metrics:
   ```json
   "description": "XGBLogRegEnsemble (25 features) + CV-OOF Isotonic Calibration (Brier: 0.1798, ECE: 0.0058)"
   ```

3. Commit:
   ```bash
   git add models/bbl_v8/ models/model_registry.json
   git commit -m "chore: retrained BBL v8 model with latest features
   
   Metrics:
   - Brier Score: 0.1798 (improved from 0.1809)
   - ECE: 0.0058 (still excellent calibration)
   - Features: 25 (no change)
   
   Improvements:
   - Situation-specific win rates improve edge cases
   - Better handling of chase scenarios"
   ```

### 3. After Adding Feature Store Columns

**Trigger**: Modifying feature calculation (e.g., adding bat_first_wr)

**Update Steps**:
1. Update feature store column lists:
   ```json
   "team_columns": ["team", "win_rate", "matches", "bat_first_wr", "bowl_first_wr"]
   ```

2. Document the change in `recent_changes`:
   ```json
   "recent_changes": {
     "date": "2025-12-15",
     "description": "Added bat_first_wr and bowl_first_wr columns",
     "impact": "Enables situation_advantage to vary by innings (innings 1 vs 2)"
   }
   ```

3. Commit:
   ```bash
   git add models/model_registry.json data/bbl_feature_store_v2/
   git commit -m "feat: added situation-specific win rates to BBL feature store
   
   New columns in team_ratings.parquet:
   - bat_first_wr: Win rate when batting first
   - bowl_first_wr: Win rate when bowling first
   
   Impact: situation_advantage now correctly reflects team performance
   in their specific role (batting vs defending)"
   ```

---

## Registry Update Checklist

When regenerating any feature store, use this checklist:

- [ ] Feature store regeneration completed successfully
- [ ] Extract metadata (teams, players, venues count)
- [ ] List all columns in each parquet file
- [ ] Note number of matches used for training data
- [ ] Document what changed (new columns, bug fixes, etc.)
- [ ] Describe impact on predictions/features
- [ ] Update `last_updated` date
- [ ] Update feature store `generated_date`
- [ ] Update `statistics` section with new counts
- [ ] Update `team_columns`, `player_columns`, `venue_columns`
- [ ] Update `recent_changes` section
- [ ] Test feature store loads correctly
- [ ] Commit with descriptive message
- [ ] Push to repository

---

## Querying the Registry

### Get Feature Store Path for a League

```bash
python -c "
import json
registry = json.load(open('models/model_registry.json'))
print(registry['active_models']['BBL']['feature_store']['path'])
# Output: data/bbl_feature_store_v2
"
```

### List All Feature Store Versions

```bash
python -c "
import json
registry = json.load(open('models/model_registry.json'))
for league, model in registry['active_models'].items():
    fs = model['feature_store']
    print(f'{league}: {fs[\"path\"]} (v{fs[\"version\"]}) - {fs[\"generated_date\"]}')"
# Output:
# BBL: data/bbl_feature_store_v2 (v2) - 2025-12-15
# ILT20: data/ilt_feature_store_v3 (v3) - 2025-12-14
"
```

### Check Feature Store Coverage

```bash
python -c "
import json
registry = json.load(open('models/model_registry.json'))
for league, model in registry['active_models'].items():
    stats = model['feature_store']['statistics']
    print(f'{league}:')
    print(f'  Teams: {stats[\"teams\"]}, Players: {stats[\"players\"]}, Venues: {stats[\"venues\"]}')"
# Output:
# BBL:
#   Teams: 8, Players: 508, Venues: 31
# ILT20:
#   Teams: 6, Players: 320, Venues: 3
"
```

---

## Best Practices

1. **Always update together**: Feature store changes + registry updates go in same commit
2. **Be descriptive**: `recent_changes` should explain the "why" not just the "what"
3. **Keep metrics current**: Update description with latest model metrics after retraining
4. **Date everything**: Use ISO date format (YYYY-MM-DD) consistently
5. **Document impact**: Always note how changes affect prediction behavior
6. **Test before commit**: Verify feature store loads and has expected columns/counts

---

## Examples

### Example: Adding New Columns to Feature Store

```bash
# 1. Regenerate feature store
bbl-pipeline process --input-dir data/bbl_raw/matches \
  --output-dir data/bbl_features_v2 \
  --feature-store-dir data/bbl_feature_store_v2

# 2. Extract new column list
python -c "
import pandas as pd
teams = pd.read_parquet('data/bbl_feature_store_v2/team_ratings.parquet')
print('Team columns:', teams.columns.tolist())"

# 3. Update registry (edit models/model_registry.json)
# Change team_columns from:
#   ["team", "win_rate", "matches"]
# To:
#   ["team", "win_rate", "matches", "bat_first_wr", "bowl_first_wr"]

# 4. Commit
git add models/model_registry.json data/bbl_feature_store_v2/
git commit -m "feat: added situation-specific win rates to BBL feature store"
```

### Example: Retraining Model with New Feature Store

```bash
# 1. Train model with new feature store
bbl-pipeline train --input-file data/bbl_features_v2/training.parquet \
  --output-dir models/bbl_v8 --calibration

# Note: Model will use new columns automatically

# 2. Get new metrics (check logs)
# Brier: 0.1798, ECE: 0.0058

# 3. Update registry description with new metrics
# "description": "XGBLogRegEnsemble (25 features) + CV-OOF Isotonic Calibration (Brier: 0.1798, ECE: 0.0058)"

# 4. Commit
git add models/bbl_v8/ models/model_registry.json
git commit -m "chore: retrained BBL v8 with new situation-specific features"
```

---

## Related Documentation

- [FEATURE_STORE.md](FEATURE_STORE.md) - Detailed feature store schema
- [BBL_V8_MODEL.md](BBL_V8_MODEL.md) - Model architecture details
- [ILT20_V4_MODEL.md](ILT20_V4_MODEL.md) - ILT20 model documentation
- [TRAINING_OPTIMIZATION.md](TRAINING_OPTIMIZATION.md) - Training pipeline guide
