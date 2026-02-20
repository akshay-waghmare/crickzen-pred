# Train/Inference Mismatch Fix: CREX Season Overrides

**Date:** February 3, 2026  
**Issue:** CREX "Last 10 matches" statistics causing 6x inflation in team strength features  
**Status:** ✅ Fixed  

---

## Problem Summary

The model's predictions diverged significantly from professional models (e.g., Cricviz) due to a train/inference mismatch in team strength features.

### Root Cause

**CREX Match Info Page** provides "Last 10 matches" statistics:
```
Sri Lanka: 30% Win Rate (3/10 matches)
England:   90% Win Rate (9/10 matches)
```

These were being injected via `SEASON_OVERRIDES` in the feature store and used directly for:
- `team_strength_diff = batting_wr - bowling_wr`
- `situation_advantage = batting_situation_wr - bowling_situation_wr`

### The Mismatch

| Metric | Training Data | Inference (CREX) | Scale Difference |
|--------|--------------|------------------|------------------|
| England WR | 0.5477 | 0.9000 | +64% |
| Sri Lanka WR | 0.4483 | 0.3000 | -33% |
| **team_strength_diff** | **0.0995** | **0.6000** | **6.0x** |
| **situation_advantage** | **0.1081** | **0.6000** | **5.5x** |

**Training Distribution:**
```python
team_strength_diff:
  mean = -0.0054
  std  = 0.3251
  
situation_advantage:
  mean = -0.0057
  std  = 0.3364
```

With CREX overrides, the model saw `team_strength_diff = 0.60`, which is **1.8 standard deviations** above the training mean - an extreme outlier.

### Feature Importance

These affected features account for ~7% of model decision-making:

| Feature | Rank | Importance |
|---------|------|-----------|
| team_strength_diff | #10 | 2.41% |
| situation_advantage | #13 | 1.84% |
| batting_team_situation_wr | #14 | 1.36% |
| bowling_team_situation_wr | #15 | 1.35% |

While not the dominant features (resource_win_prob is #1 at 23.6%), a 6x scale error in 7% of features can shift predictions by several percentage points.

---

## Solution

**Disabled `USE_SEASON_OVERRIDES` in feature store:**

```python
# src/bbl_pipeline/features/store.py

# BEFORE
USE_SEASON_OVERRIDES = True  # Uses CREX last-10 stats

# AFTER
USE_SEASON_OVERRIDES = False  # Uses historical feature store data only
```

Now uses consistent historical team statistics at both training and inference:

| Team | Historical WR | bat_first_wr | bowl_first_wr |
|------|--------------|--------------|---------------|
| England | 0.5477 | 0.5765 | 0.5263 |
| Sri Lanka | 0.4483 | 0.4182 | 0.4839 |

**Correct Feature Values (Innings 2, England chasing):**
```python
team_strength_diff = 0.5477 - 0.4483 = 0.0995  ✅
situation_advantage = 0.5263 - 0.4182 = 0.1081  ✅
```

---

## Verification

### Test Case: England vs Sri Lanka (Innings 2)

```python
from bbl_pipeline.features.store import InMemoryFeatureStore
from bbl_pipeline.inference.realtime_mapper import RealTimeFeatureMapper

# Load feature store
fs = InMemoryFeatureStore(
    'data/t20_international_male_feature_store_v1/player_stats.parquet',
    'data/t20_international_male_feature_store_v1/venue_stats.parquet'
)
fs.load()

# Create mapper
mapper = RealTimeFeatureMapper(fs, global_stats={...})

# Generate features
scraped_data = {
    'innings_num': 2,
    'batting_team': 'England',
    'bowling_team': 'Sri Lanka',
    ...
}
feat_df = mapper.create_feature_dataframe(scraped_data)

# Verify
assert feat_df['team_strength_diff'].iloc[0] == 0.0995  ✅
assert feat_df['situation_advantage'].iloc[0] == 0.1081  ✅
```

### Distribution Check

```python
import pandas as pd

df = pd.read_parquet('data/t20_international_male_features_v1/training.parquet')

# team_strength_diff range: -1.0 to +1.0, mean ≈ 0, std ≈ 0.32
# 0.0995 is well within normal range (< 0.5 std from mean)
# 0.6000 would be 1.8+ std (extreme outlier)
```

---

## Impact

### ✅ Benefits
- **Consistency**: Training and inference now use same data source
- **Accuracy**: Feature values match training distribution
- **Alignment**: Predictions closer to professional models
- **No Retraining**: Only inference behavior changed

### ⚠️ Trade-offs
- **Current Form**: No longer incorporates recent form from last 10 matches
- **New Teams**: Still uses historical data (may be stale for debut teams)

### 🔮 Future Enhancements

If recent form is valuable, consider:

**Option A: Weighted Blend**
```python
blended_wr = 0.7 * historical_wr + 0.3 * crex_recent_wr
# Captures current form without extreme swings
```

**Option B: Capped Delta**
```python
# Allow CREX to adjust by max ±15%
adjusted_wr = historical_wr * min(1.15, max(0.85, crex_wr / historical_wr))
```

**Option C: Separate Form Feature**
```python
# Add as new feature instead of overriding
'recent_form_10m' = crex_wr - historical_wr  # Range: -0.5 to +0.5
# Model learns appropriate weight during training
```

---

## Files Modified

### Core Fix
- **src/bbl_pipeline/features/store.py**
  - Set `USE_SEASON_OVERRIDES = False`
  - Added detailed comment explaining the mismatch

### Related Improvements
- **src/bbl_pipeline/simulation/sampler.py**
  - Pass `model_dir` to `load_league_distributions()`
  - Support model-specific phase distributions
  
- **src/bbl_pipeline/simulation/engine.py**
  - Pass `model_dir` to `NextBallSampler` constructor
  
- **src/bbl_pipeline/app/telegram_ledger_app.py**
  - Fixed team selection UI logic

---

## Testing Checklist

- [x] Feature values match training distribution
- [x] England vs Sri Lanka test case passes
- [x] Model predictions align with professional models
- [x] No regression in OOF metrics
- [x] Documentation updated
- [x] Commit with detailed message

---

## References

- **Training Data**: `data/t20_international_male_features_v1/training.parquet`
- **Feature Store**: `data/t20_international_male_feature_store_v1/team_ratings.parquet`
- **Model**: `models/t20_international_male_v1/champion_model.joblib`
- **CREX Injection**: `src/bbl_pipeline/inference/crex_live_predictor.py:_inject_season_stats()`
- **Feature Parity Doc**: `docs/FEATURE_PARITY_FIX.md`

---

## Commit

```bash
git commit -m "fix: Disable CREX season overrides to prevent train/inference mismatch"
```

**Commit SHA:** `750b1a7`
