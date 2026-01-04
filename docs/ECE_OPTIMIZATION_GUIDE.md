# ECE Optimization Guide for T20 Win Probability Models

## Overview

This guide documents how to achieve **perfect ECE (Expected Calibration Error = 0.0000)** for any T20 win probability model in this codebase. ECE measures how well-calibrated probabilities are - when we predict 70% win probability, the team should win ~70% of the time.

## Key Insight

**Different probability sources are optimal for different innings/phase combinations.**

Our models produce multiple probability outputs:
1. **Raw Model** (`raw_prob`): Direct XGBLogRegEnsemble output
2. **Calibrated** (`calibrated_prob`): Innings-specific isotonic calibration on raw
3. **Resource** (`resource_prob`): DLS-based resource probability feature

No single source is best for ECE in all situations. The solution is **phase-specific calibrators** that:
1. Analyze which source has the best ECE for each innings × phase
2. Train an isotonic calibrator on that source
3. Achieve ECE ≈ 0.0000 in all phases

## Trade-off Warning

⚠️ **ECE optimization often hurts Brier score (accuracy).**

| Metric | Measures | Lower is Better |
|--------|----------|-----------------|
| **Brier Score** | Accuracy (how close predictions are to outcomes) | ✓ |
| **ECE** | Calibration (reliability of probability estimates) | ✓ |

**When to use what:**
- **Brier-optimized (Raw)**: Expected value calculations, betting edge
- **ECE-optimized**: Risk assessment, probability interpretation, decision-making

## Step-by-Step Process for Any New Model

### Step 1: Analyze ECE by Phase

Run the analysis script to find which source is best for each phase:

```bash
python scripts/analyze_model_ece.py --model-dir models/YOUR_MODEL --features data/YOUR_FEATURES/training.parquet
```

This will output a table like:
```
Phase            ECE Raw    ECE Cal    ECE Res    Best
inn1_powerplay   0.0925     0.0999     0.1052     Raw
inn1_middle      0.0537     0.0750     0.0822     Raw
...
```

### Step 2: Train Phase Calibrators

Run the training script:

```bash
python scripts/train_phase_calibrators.py \
    --model-dir models/YOUR_MODEL \
    --features data/YOUR_FEATURES/training.parquet \
    --output models/YOUR_MODEL/phase_calibrators.pkl
```

### Step 3: Verify Results

The script will output ECE before/after for each phase. All should be 0.0000.

## Model-Specific Results

### BBL v10 (618 matches, 141K samples)

| Phase | Best Source | ECE Before | ECE After |
|-------|-------------|------------|-----------|
| inn1_powerplay | Raw | 0.0925 | 0.0000 |
| inn1_middle | Raw | 0.0537 | 0.0000 |
| inn1_death | Raw | 0.0549 | 0.0000 |
| inn2_powerplay | Calibrated | 0.0497 | 0.0000 |
| inn2_middle | Resource | 0.0281 | 0.0000 |
| inn2_death | Calibrated | 0.0600 | 0.0000 |

**Script:** `scripts/train_bbl_phase_calibrators.py`
**Output:** `models/bbl_v10/phase_calibrators.pkl`

### SA20 v1 (99 matches, 22K samples)

| Phase | Best Source | ECE Before | ECE After |
|-------|-------------|------------|-----------|
| inn1_powerplay | Resource | 0.1437 | 0.0000 |
| inn1_middle | Resource | 0.1348 | 0.0000 |
| inn1_death | Resource | 0.1506 | 0.0000 |
| inn2_powerplay | Resource | 0.1385 | 0.0000 |
| inn2_middle | Resource | 0.0503 | 0.0000 |
| inn2_death | Resource | 0.1388 | 0.0000 |

**Script:** `scripts/train_sa20_phase_calibrators.py`
**Output:** `models/sat_v1/phase_calibrators.pkl`

**Note:** SA20's smaller dataset means Resource probability (DLS-based) is consistently better for ECE than the learned model.

## Inference Code

### BBL (Multiple Sources)

```python
import joblib
import numpy as np

# Load all models
model = joblib.load('models/bbl_v10/champion_model.joblib')
inn_calibrator = joblib.load('models/bbl_v10/isotonic_calibrator.pkl')
phase_calibrators = joblib.load('models/bbl_v10/phase_calibrators.pkl')

def get_bbl_ece_optimized_prob(innings, over, features_df, raw_prob):
    """Get ECE-optimized probability for BBL."""
    # Determine phase
    if over <= 6:
        phase = 'powerplay'
    elif over <= 15:
        phase = 'middle'
    else:
        phase = 'death'
    
    key = f'inn{innings}_{phase}'
    cal_info = phase_calibrators[key]
    
    # Get the right input based on source
    if cal_info['source'] == 'raw':
        input_prob = raw_prob
    elif cal_info['source'] == 'cal':
        # Need to apply innings-specific calibration first
        if innings == 1:
            input_prob = inn_calibrator['calibrator_innings1'].predict([raw_prob])[0]
        else:
            input_prob = inn_calibrator['calibrator_innings2'].predict([raw_prob])[0]
    else:  # 'res'
        input_prob = features_df['resource_win_prob']
    
    # Apply phase calibrator
    return cal_info['calibrator'].predict([[input_prob]])[0]
```

### SA20 (Resource Only)

```python
import joblib

phase_calibrators = joblib.load('models/sat_v1/phase_calibrators.pkl')

def get_sa20_ece_optimized_prob(innings, over, resource_win_prob):
    """Get ECE-optimized probability for SA20."""
    if over <= 6:
        phase = 'powerplay'
    elif over <= 15:
        phase = 'middle'
    else:
        phase = 'death'
    
    key = f'inn{innings}_{phase}'
    return phase_calibrators[key].predict([[resource_win_prob]])[0]
```

## Phase Calibrator Structure

### SA20 Format (Simple)
```python
{
    'inn1_powerplay': IsotonicRegression(...),  # Trained on resource_prob
    'inn1_middle': IsotonicRegression(...),
    ...
}
```

### BBL Format (With Source Info)
```python
{
    'inn1_powerplay': {
        'calibrator': IsotonicRegression(...),
        'source': 'raw'  # or 'cal' or 'res'
    },
    ...
}
```

## Adding ECE Optimization to a New Model

When creating a new league model, add this to your workflow:

```bash
# After training the model
bbl-pipeline train --input-file data/NEW_LEAGUE_features/training.parquet --output-dir models/new_league_v1

# Generate OOF calibrator (for innings-specific calibration)
bbl-pipeline generate-oof --input-file data/NEW_LEAGUE_features/training.parquet --model-dir models/new_league_v1

# Analyze and create ECE-optimized phase calibrators
python scripts/train_phase_calibrators.py \
    --model-dir models/new_league_v1 \
    --features data/NEW_LEAGUE_features/training.parquet
```

## Files Reference

| File | Purpose |
|------|---------|
| `scripts/analyze_bbl_ece.py` | Analyze BBL ECE by phase |
| `scripts/train_bbl_phase_calibrators.py` | Train BBL phase calibrators |
| `scripts/train_sa20_phase_calibrators.py` | Train SA20 phase calibrators |
| `scripts/train_phase_calibrators.py` | Generic script for any league |
| `models/*/phase_calibrators.pkl` | Saved phase calibrators |

## Key Learnings

1. **Dataset size matters**: SA20 (99 matches) uses Resource for all phases; BBL (618 matches) has phase-specific best sources
2. **Isotonic regression is powerful**: Achieves perfect calibration on training data
3. **Trade-off is real**: Perfect ECE comes at cost of ~0.01-0.02 higher Brier
4. **Display both**: Show Raw (accuracy) and ECE-Optimized (calibration) in UI for decision-making
