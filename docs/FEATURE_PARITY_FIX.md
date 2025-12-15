# Feature Parity Fix: situation_advantage vs team_strength_diff

## Problem
The `situation_advantage` and `team_strength_diff` features were identical at inference time, both calculating the same value:
```
situation_advantage = -0.0452
team_strength_diff = -0.0452
```

This indicated duplicate logic instead of the intended situation-specific calculation.

## Root Cause
The `situation_advantage` feature was using overall team win rates instead of situation-specific win rates:
- **Expected behavior**: Use batting/bowling first win rates based on the match situation (innings)
- **Actual behavior**: Both features used overall win rates from `team_ratings.parquet`

## Solution

### 1. Extended `team_ratings.parquet` with Situation-Specific Win Rates
**File**: `src/bbl_pipeline/data/processor.py` (lines 1157-1183)

Added two new columns to track team performance by situation:
- `bat_first_wr`: Win rate when batting first (innings 1)
- `bowl_first_wr`: Win rate when bowling first (defending a score)

```python
# Calculate bat first win rate (when team is batting_team)
bat_first_matches = matches[matches['batting_team'] == team]
bat_first_wins = bat_first_matches[bat_first_matches['winner'] == team].shape[0]
bat_first_total = bat_first_matches.shape[0]
bat_first_wr = bat_first_wins / bat_first_total if bat_first_total > 0 else 0.5

# Calculate bowl first win rate (when team is bowling_team)
bowl_first_matches = matches[matches['bowling_team'] == team]
bowl_first_wins = bowl_first_matches[bowl_first_matches['winner'] == team].shape[0]
bowl_first_total = bowl_first_matches.shape[0]
bowl_first_wr = bowl_first_wins / bowl_first_total if bowl_first_total > 0 else 0.5
```

### 2. Updated Inference to Use Situation-Specific Win Rates
**File**: `src/bbl_pipeline/inference/realtime_mapper.py` (lines 222-310)

Modified the feature calculation to:
1. Load all four win rate columns from feature store: `bat_first_wr`, `bowl_first_wr` for both teams
2. Select the appropriate win rate based on current innings:
   - **Innings 1**: Batting team uses `bat_first_wr`, Bowling team uses `bowl_first_wr`
   - **Innings 2**: Batting team uses `bowl_first_wr` (chasing), Bowling team uses `bat_first_wr`

```python
if innings == 1:
    batting_team_situation_wr = batting_team_bat_first_wr
    bowling_team_situation_wr = bowling_team_bowl_first_wr
else:  # innings == 2
    batting_team_situation_wr = batting_team_bowl_first_wr
    bowling_team_situation_wr = bowling_team_bat_first_wr

situation_advantage = batting_team_situation_wr - bowling_team_situation_wr
```

### 3. Enhanced Venue Alias Mapping
**File**: `src/bbl_pipeline/features/store.py` (lines 7-45)

Updated venue aliases with more accurate canonical names:
- Simonds Stadium → "Simonds Stadium, South Geelong, Victoria"
- GMHBA Stadium → "GMHBA Stadium, South Geelong, Victoria"
- Other venues mapped to their canonical feature store names

## Verification

**Melbourne Renegades vs Perth Scorchers (Innings 2)**

Team Win Rates:
```
Melbourne Renegades:
  Overall WR: 0.4082 | Bat first: 0.3433 | Bowl first: 0.4625

Perth Scorchers:
  Overall WR: 0.6188 | Bat first: 0.6000 | Bowl first: 0.6400
```

Feature Calculations:
```
team_strength_diff (overall):
  0.4082 - 0.6188 = -0.2106

situation_advantage (innings 2, situation-specific):
  0.4625 - 0.6000 = -0.1375

Difference: 0.0731 ✓ (Features now correctly differ)
```

## Impact

- **Correctness**: Features now capture situation-specific team performance
- **Model Quality**: situation_advantage is a TOP_25 feature; correct values improve prediction accuracy
- **No Retraining Required**: Only feature store regeneration and inference code update needed
- **Backward Compatible**: Changes only affect new predictions; existing trained models remain valid

## Files Modified

1. `src/bbl_pipeline/data/processor.py` - Added bat/bowl first win rate calculation
2. `src/bbl_pipeline/inference/realtime_mapper.py` - Updated situation_advantage logic
3. `src/bbl_pipeline/features/store.py` - Enhanced venue alias mapping
4. `data/bbl_feature_store_v2/team_ratings.parquet` - Regenerated with new columns

## Testing

Verified with live prediction output showing distinct feature values:
- `situation_advantage: -0.1060` (for Melbourne Renegades in innings 1)
- `team_strength_diff: -0.0452` (overall comparison)
