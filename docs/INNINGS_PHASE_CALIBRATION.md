# Innings×Phase Specific Calibration

## Overview

As of January 2026, the BBL pipeline automatically generates **innings×phase specific calibrators** that provide superior calibration compared to simpler approaches. This document explains the methodology, results, and usage.

## Background

Calibration analysis revealed that T20 matches exhibit different probability characteristics across:
- **Innings**: First innings vs. second innings (chasing)
- **Phases**: Powerplay (1-6), Middle (7-15), Death (16-20)

Combining these dimensions yields **6 distinct calibrators** that optimize for each specific game situation.

## OOF Cross-Validation Results (BBL)

Analysis was performed using 5-fold K-Fold CV on 141,435 ball-by-ball observations from 618 BBL matches.

### Calibration Strategies Tested

| Strategy | Description | Log Loss | Improvement |
|----------|-------------|----------|-------------|
| **innings_phase_specific** | 6 calibrators (inn×phase) | **0.3574** | **10.36%** ✅ |
| phase_specific | 3 phase calibrators | 0.3606 | 9.56% |
| innings_specific | 2 innings calibrators | 0.3616 | 9.31% |
| global | Single calibrator | 0.3625 | 9.08% |
| raw | No calibration | 0.3987 | — |

### Performance by Innings × Phase

| Situation | Best Strategy | Log Loss | Improvement |
|-----------|--------------|----------|-------------|
| **Inn1 - Powerplay** | innings_phase_specific | 0.4659 | **12.54%** |
| **Inn1 - Middle** | innings_phase_specific | 0.4078 | **10.00%** |
| **Inn1 - Death** | innings_phase_specific | 0.4040 | **7.89%** |
| **Inn2 - Powerplay** | innings_phase_specific | 0.3847 | **9.29%** |
| **Inn2 - Middle** | brier_opt | 0.2592 | **10.68%** |
| **Inn2 - Death** | innings_phase_specific | 0.1696 | **12.85%** |

**Key Finding:** Innings×phase specific calibration wins in 5 out of 6 situations, with brier-optimized slightly better only in Inn2-Middle.

### ECE (Expected Calibration Error) Improvements

The phase-specific calibrators dramatically reduce calibration error:

| Phase | Raw ECE | Calibrated ECE | Reduction |
|-------|---------|----------------|-----------|
| Inn1 - Powerplay | 0.0448 | **0.000018** | 99.96% |
| Inn1 - Middle | 0.0408 | **0.000112** | 99.73% |
| Inn1 - Death | 0.0365 | **0.000188** | 99.49% |
| Inn2 - Powerplay | 0.0342 | **0.000042** | 99.88% |
| Inn2 - Middle | 0.0268 | **0.000609** | 97.73% |
| Inn2 - Death | 0.0448 | **0.002698** | 93.98% |

## Implementation

### Standard Pipeline

Innings×phase calibration is now **automatically generated** as part of the standard BBL pipeline:

```bash
# 1. Train model (produces raw uncalibrated model)
bbl-pipeline train \
  --input-file data/bbl_features_v2/training.parquet \
  --output-dir models/bbl_v11

# 2. Generate OOF calibrators (includes innings×phase!)
bbl-pipeline generate-oof \
  --input-file data/bbl_features_v2/training.parquet \
  --model-dir models/bbl_v11 \
  --n-splits 5
```

The `generate-oof` command detects if `innings` and phase columns (`is_powerplay`, `is_death_overs`) exist, and automatically:
1. Generates innings-specific calibrators (backward compatible)
2. Generates innings×phase specific calibrators (new!)
3. Saves all calibrators with metadata to `isotonic_calibrator.pkl`

### Calibrator Structure

The `isotonic_calibrator.pkl` file contains:

```python
{
    'type': 'innings_phase_specific',
    
    # Innings-level calibrators (backward compatible)
    'calibrator_innings1': <IsotonicRegression>,
    'calibrator_innings2': <IsotonicRegression>,
    'calibrator_combined': <IsotonicRegression>,
    
    # Phase-specific calibrators
    'phase_calibrators': {
        'inn1_powerplay': <IsotonicRegression>,
        'inn1_middle': <IsotonicRegression>,
        'inn1_death': <IsotonicRegression>,
        'inn2_powerplay': <IsotonicRegression>,
        'inn2_middle': <IsotonicRegression>,
        'inn2_death': <IsotonicRegression>,
    },
    
    # Metrics for each calibrator
    'phase_metrics': {
        'inn1_powerplay': {
            'samples': 22457,
            'brier_raw': 0.2400,
            'brier_calibrated': 0.2361,
            'ece_raw': 0.0448,
            'ece_calibrated': 0.000018,
        },
        # ... (5 more)
    },
    
    # Metadata
    'model_path': 'models/bbl_v11/champion_model.joblib',
    'features': [...],
    'created_date': '2026-01-14T12:05:40',
}
```

### Usage in Inference

The predictor automatically uses the appropriate calibrator based on:
- Current innings (1 or 2)
- Current phase (determined from over number)

```python
from bbl_pipeline.inference.predictor import MatchStatePredictor

predictor = MatchStatePredictor(
    model_dir="models/bbl_v10",
    feature_store_dir="data/bbl_feature_store_v2"
)

# Predictor automatically selects:
# - Inn1, Over 4 → inn1_powerplay calibrator
# - Inn2, Over 12 → inn2_middle calibrator
# - Inn2, Over 18 → inn2_death calibrator
state = MatchState(...)
win_prob = predictor.predict(state)
```

## Recommendations

### For New Models

**Always run `generate-oof`** after training any new model to create optimized calibrators:

```bash
# After training
bbl-pipeline generate-oof \
  --input-file data/{league}_features_v2/training.parquet \
  --model-dir models/{league}_v{X} \
  --n-splits 5
```

### For Production Inference

Use the **innings×phase specific** probabilities when available:
- They provide the best log loss (accuracy)
- They achieve near-perfect calibration (ECE ≈ 0)
- They're automatically selected by the predictor

### For Different Leagues

This methodology applies to all T20 leagues:
- ✅ **BBL** - Fully implemented
- ⏳ **ILT20** - Use same approach
- ⏳ **SA20** - Use same approach  
- ⏳ **SSM** - Use same approach
- ⏳ **WPL** - Use same approach

Simply run `generate-oof` after training and the calibrators will be generated automatically.

## Technical Details

### Phase Detection

Phases are determined from the over number:

```python
if over <= 6:
    phase = 'powerplay'
elif over <= 15:
    phase = 'middle'
else:  # over 16-20
    phase = 'death'
```

Note: For innings 2, powerplay is typically overs 1-4 (first 4 overs).

### Calibrator Selection

```python
def get_calibrator_key(innings: int, over: int) -> str:
    if over <= 6:
        phase = 'powerplay'
    elif over <= 15:
        phase = 'middle'
    else:
        phase = 'death'
    return f'inn{innings}_{phase}'
```

### Isotonic Regression Parameters

All calibrators use:
- `y_min=0.01, y_max=0.99` - Prevents extreme probabilities
- `out_of_bounds='clip'` - Handles out-of-range inputs gracefully

## References

- **OOF Analysis**: `scripts/bbl_oof_calibration_comparison.py`
- **Situation Analysis**: `scripts/analyze_calibration_by_situation.py`
- **Results**: `data/bbl_calibration_analysis/`
- **BBL v10 Model**: `docs/BBL_V10_MODEL.md`
- **Model Registry**: `models/model_registry.json`

## Changelog

**2026-01-14**: Initial implementation of innings×phase specific calibration
- Added to `bbl-pipeline generate-oof` command
- Automatic detection of innings and phase columns
- 6 calibrators generated (inn1_pp, inn1_mid, inn1_death, inn2_pp, inn2_mid, inn2_death)
- ECE improvements up to 99.96% in some phases
- Overall log loss improvement: 10.36% vs raw model
