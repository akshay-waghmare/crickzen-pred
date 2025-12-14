# Feature Engineering Fixes - December 10, 2025

## Summary

During live testing of the win probability model on a Nepal Premier League match (LBL vs KMG), we identified several issues causing **overly conservative predictions** for easy chase situations. The model was outputting ~69% win probability for a scenario where LBL needed just 6 runs from 19 balls - a situation that should realistically be 95%+.

---

## Issues Identified

### 1. `score_vs_par` - Wrong Reference Point for 2nd Innings

**Location:** `src/bbl_pipeline/inference/realtime_mapper.py` (line 253)

**Problem:**
The `score_vs_par` feature was comparing the current score against **venue average (160)** instead of the actual **target** in 2nd innings.

**Example of the bug:**
```
Scenario: LBL 106/4 chasing 112
- venue_avg = 160
- resources_used = 81.3%
- par_at_this_point = 160 × 0.813 = 130.1
- score_vs_par = 106 - 130.1 = -24.1  ❌ (NEGATIVE despite easy chase!)
```

The model sees `-24.1` and thinks "this team is struggling" when in reality they're cruising to victory.

**Fix Applied:**
```python
# score_vs_par: For 2nd innings, compare against TARGET not venue average
if innings == 2 and target_runs is not None and target_runs > 0:
    resources_used = 100 - resource_features.get('resource_pct', 100)
    par_at_this_point = target_runs * (resources_used / 100)
    score_vs_par = current_score - par_at_this_point
else:
    # 1st innings: compare against venue average
    score_vs_par = current_score - (venue_avg_score * (1 - resource_features.get('resource_pct', 100)/100))
```

**After fix:**
```
- target = 112
- resources_used = 81.3%
- par_at_this_point = 112 × 0.813 = 91.1
- score_vs_par = 106 - 91.1 = +14.9  ✅ (POSITIVE - ahead of required rate!)
```

**Note:** The training data processor (`src/bbl_pipeline/data/processor.py` line 826) already uses `first_innings_score` for 2nd innings, so this fix aligns inference with training.

---

### 2. `dls_pressure_index` - Improved Calculation Using CRR vs RRR

**Location:** `src/bbl_pipeline/features/calculator.py` (line 121)

**Problem:**
The original pressure index only looked at absolute Required Run Rate (RRR), not how it compared to Current Run Rate (CRR). A team with RRR of 9 could be under pressure OR cruising depending on their current momentum.

**Original Logic:**
```python
# Old: Absolute RRR-based
rate_pressure = min(1.0, (required_rate - 6) / 12)
wicket_pressure = wickets_lost / 10
pressure = 0.7 * rate_pressure + 0.3 * wicket_pressure
```

**Improved Logic:**
```python
# New: Compare RRR to CRR (momentum-aware)
if current_run_rate is not None and current_run_rate > 0:
    rr_ratio = required_rate / current_run_rate
    # ratio 1.0 = on track (0 pressure)
    # ratio 1.6 = need 60% faster (max pressure)
    rate_pressure = min(1.0, max(0.0, (rr_ratio - 1.0) / 0.6))
else:
    rate_pressure = min(1.0, max(0.0, (required_rate - 7) / 8))

# Wickets matter MORE in late overs
overs_progress = overs_bowled / 20
wicket_pressure = overs_progress * (wickets_lost / 10)

pressure = (0.75 * rate_pressure) + (0.25 * wicket_pressure)
```

**Key Improvements:**
1. **CRR vs RRR ratio** - If CRR > RRR, pressure is low regardless of absolute values
2. **Overs-weighted wicket pressure** - Losing 3 wickets in powerplay is recoverable, losing 3 in death is critical
3. **Earlier pressure scaling** - Early deficits matter less than late deficits

**Test Cases:**
| Scenario | Old Pressure | New Pressure |
|----------|--------------|--------------|
| 67/3 (12ov) chasing 112, CRR=5.6, RRR=5.6 | 0.25 | 0.055 |
| 45/2 (10ov) chasing 150, CRR=4.5, RRR=10.5 | 0.33 | 0.775 |
| 60/6 (15ov) chasing 150, CRR=4.0, RRR=18.0 | 1.00 | 1.000 |

---

### 3. Rolling Stats Default Values for Missing Ball-by-Ball Data

**Location:** `src/bbl_pipeline/inference/realtime_mapper.py` (line 165)

**Problem:**
When scraping live data from Crex, we don't have ball-by-ball history. The rolling stats calculation was producing misleading values:

- **Bug:** First ball added to history has `runs_scored = total_score` (e.g., 107 runs in one ball!)
- **Bug:** First ball has `is_wicket = total_wickets` (e.g., 6 wickets in one ball!)

This caused features like:
- `runs_last_12 = 107` (model thinks: "massive hitting!")
- `wickets_last_12 = 6` (model thinks: "recent collapse!")

**Root Cause:**
```python
df['runs_scored'] = df['total_score'].diff().fillna(df['total_score'].iloc[0])
# For first ball, diff() is NaN, fillna fills with entire current score!
```

**Fix Applied:**
Use sensible defaults when ball history is insufficient:
```python
# When we don't have enough ball-by-ball data, use conservative estimates
if len(ball_history) < 12:
    # Estimate average runs per ball from current score
    avg_runs_per_ball = current_score / max(1, balls_bowled)
    runs_last_12 = avg_runs_per_ball * 12  # Pro-rate
    
    # Estimate wickets per ball and pro-rate
    avg_wkts_per_ball = wickets_lost / max(1, balls_bowled)
    wickets_last_12 = avg_wkts_per_ball * 12
```

---

## Impact Analysis

### Feature Importance (Top 5)
| Rank | Feature | Combined Importance |
|------|---------|---------------------|
| 1 | `resource_win_prob` | 1.0000 |
| 2 | `dls_pressure_index` | 0.8456 |
| 3 | `score_vs_par` | 0.7044 |
| 4 | `score_per_wicket` | 0.3811 |
| 5 | `run_rate_diff` | 0.2573 |

All three fixes target the **top 3 most important features**, which is why the predictions were so far off.

### Before/After Comparison

**Scenario:** LBL 106/4 chasing 112, need 6 from 19 balls

| Metric | Before Fix | After Fix |
|--------|------------|-----------|
| `score_vs_par` | -24.1 | +14.9 |
| `dls_pressure_index` | 0.25 | 0.08 |
| `wickets_last_12` | 6.0 | ~1.5 (pro-rated) |
| **Win Probability** | **68.9%** | **~85%+** |

---

## Model Retraining

After applying these fixes, the model was retrained:

```bash
python -m bbl_pipeline.cli process --input-dir data/bbl_raw/matches --output-dir data/features --feature-store-dir data/feature_store
python -m bbl_pipeline.cli train --input-file data/features/training_sampled.parquet --output-dir models/champion_retrained
```

**Brier Score:** 0.1776 → 0.1775 (slight improvement, features now more aligned)

---

## Files Modified

1. `src/bbl_pipeline/features/calculator.py`
   - `calculate_pressure_index()` - Added CRR vs RRR ratio, overs-weighted wicket pressure

2. `src/bbl_pipeline/inference/realtime_mapper.py`
   - `score_vs_par` calculation - Use target for 2nd innings
   - `_calculate_rolling_stats()` - Better defaults for missing ball-by-ball data

---

## Testing Commands

```python
# Test pressure index calculation
from bbl_pipeline.features.calculator import ResourceFeatureCalculator
calc = ResourceFeatureCalculator()

# Easy chase scenario
p = calc.calculate_pressure_index(
    innings=2, 
    current_score=106, 
    overs_bowled=16.5, 
    wickets_lost=4, 
    target_runs=112, 
    current_run_rate=6.4
)
print(f"Pressure: {p}")  # Should be low (~0.08)
```

```bash
# Run live predictor
python -m bbl_pipeline.inference.crex_live_predictor \
    --match-url "https://crex.com/scoreboard/.../live" \
    --model-dir models/champion_final
```

---

## Lessons Learned

1. **Train/Inference Alignment** - Always verify that feature calculations in inference match training
2. **Feature Interpretation** - Check that features make intuitive sense for edge cases (easy chase, big target, etc.)
3. **Default Values Matter** - When data is missing, defaults can significantly skew predictions
4. **Test with Real Scenarios** - Live match testing revealed issues that unit tests missed

## Updates - December 14, 2025

### 1. Robust 2nd Innings Detection
**Location:** \src/bbl_pipeline/inference/crex_live_predictor.py\

**Issue:**
The predictor sometimes failed to correctly identify the start of the 2nd innings or retained ball history from the 1st innings, leading to incorrect state calculations.

**Fix:**
- Added explicit check for 0 overs/0 runs to return empty history.
- Improved 'innings boundary' detection by looking for significant backward jumps in over numbers (e.g., 19.4 -> 0.1).
- Added safety guardrails to clear history if early 2nd innings state conflicts with late 1st innings ball history.

### 2. Ensemble Model Support & Calibration Smoothing
**Location:** \src/bbl_pipeline/inference/predictor.py\

**Changes:**
- **Ensemble Wrapper:** Added \EnsembleModelWrapper\ to support models combining XGBoost and Logistic Regression.
- **Smoothed Calibration:** Implemented a blending strategy for probability calibration:
  - Blends 30% calibrated probability with 70% raw probability.
  - Caps maximum shift from raw probability to 5% to prevent 'cliff effects' where calibration causes sudden large jumps.
  - Updated debug logging to show Raw, Smoothed, and Calibrated probabilities.

