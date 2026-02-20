# League-Specific Calibration Guide

## Overview

This guide explains how to adapt the global unified T20 model to specific leagues using Temperature or Platt scaling calibration.

**Recommended Approach:**
1. **Global model** trained on all T20s (frozen)
2. **League adaptation** via Temperature/Platt scaling (NOT isotonic - too steppy)
3. **Innings-wise calibrators** for stability (2 calibrators per league)

## Quick Start

```bash
# Calibrate a league from the global model
bbl-pipeline calibrate-league \
  --global-model models/t20_male_v1 \
  --input-file data/<league>_features/training.parquet \
  --league <league> \
  --method temperature  # or platt
```

## Generated Files

The command generates three files per league:

```
models/t20_male_v1/league_calibrators/<league>/
├── league_calibrator.pkl      # Native LeagueCalibrator object
├── calibration_metrics.json   # Detailed Brier/LogLoss metrics
└── isotonic_calibrator.pkl    # OOF-compatible format for Streamlit
```

## Usage in Code

### Option 1: LeagueCalibrator (Recommended)

```python
from bbl_pipeline.training.league_calibrator import LeagueCalibrator

# Load calibrator
calibrator = LeagueCalibrator.load('models/t20_male_v1/league_calibrators/bbl')

# Get raw predictions from global model
raw_probs = global_model.predict_proba(X)[:, 1]

# Apply league calibration
calibrated = calibrator.predict(df, raw_probs)
# df must have 'innings' column (1 or 2)
```

### Option 2: OOF-Compatible Format (Streamlit App)

```python
import joblib

# Load in OOF format
cal_data = joblib.load('models/t20_male_v1/league_calibrators/bbl/isotonic_calibrator.pkl')

# Access innings calibrators
cal_inn1 = cal_data['calibrator_innings1']  # TemperatureScaler object
cal_inn2 = cal_data['calibrator_innings2']  # TemperatureScaler object

# Apply calibration
calibrated_inn1 = cal_inn1.predict(raw_probs[innings==1])
calibrated_inn2 = cal_inn2.predict(raw_probs[innings==2])

# Or use combined (falls back to innings 1)
cal_combined = cal_data['calibrator_combined']
```

## Calibration Methods

### Temperature Scaling

Single parameter `T` that divides logits before sigmoid:

```
calibrated_p = sigmoid(logit(p) / T)
```

- **T > 1**: Softer predictions (moved toward 0.5)
- **T < 1**: Sharper predictions (moved toward 0 or 1)
- **T = 1**: No change

**When to use:** Simple, stable, works well with limited data (200+ matches)

### Platt Scaling

Two parameters `a` and `b` for logistic transformation:

```
calibrated_p = sigmoid(a * logit(p) + b)
```

- **a > 1**: Sharper predictions
- **a < 1**: Softer predictions
- **b ≠ 0**: Shifts the decision boundary

**When to use:** More flexible, better for larger datasets (500+ matches)

## Current League Calibrators

| League | Samples | Brier Δ | LogLoss Δ | T (Inn 1) | T (Inn 2) |
|--------|---------|---------|-----------|-----------|-----------|
| **BBL** | 141,435 | +0.4% | +0.5% | 0.847 | 0.830 |
| **SA20** | 26,121 | +0.4% | +0.9% | 0.899 | 0.765 |
| **SSM** | 55,470 | +0.2% | +0.3% | 0.877 | 0.888 |

### Key Insights

- **All leagues**: T < 1 means sharper predictions vs global model
- **SA20 Innings 2**: T = 0.765 (very sharp) - SA20 chases are highly predictable
- **SSM**: T similar for both innings (~0.88) - balanced league dynamics
- **BBL**: Consistent sharpening (~0.83-0.85)

## Metrics Logged

The `calibration_metrics.json` contains detailed performance tracking:

```json
{
  "league": "bbl",
  "method": "temperature",
  "fitted_at": "2026-01-19T00:20:29",
  "overall": {
    "brier_raw": 0.1721,
    "brier_calibrated": 0.1713,
    "logloss_raw": 0.5107,
    "logloss_calibrated": 0.5080,
    "samples": 141435
  },
  "by_innings": {
    "innings_1": { "brier_raw": 0.2081, "brier_calibrated": 0.2076, ... },
    "innings_2": { "brier_raw": 0.1327, "brier_calibrated": 0.1316, ... }
  },
  "by_phase": {},
  "by_date": []  // Populated if 'date' column available
}
```

## When to Recalibrate

Recalibrate when:
1. **New season starts** - Team compositions change
2. **LogLoss increases >5%** - Model drift detected
3. **200+ new matches** available for the league

## Integration with Streamlit App

The `isotonic_calibrator.pkl` file is compatible with the existing Streamlit app calibrator loading:

```python
# In live_streamlit_app.py
cal_data = joblib.load('models/t20_male_v1/league_calibrators/bbl/isotonic_calibrator.pkl')

# Access like standard OOF calibrators
cal_inn1 = cal_data['calibrator_innings1']
cal_inn2 = cal_data['calibrator_innings2']
cal_combined = cal_data['calibrator_combined']
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     GLOBAL T20 MODEL                            │
│                  (5,353 matches, 1.9M samples)                  │
│                     models/t20_male_v1/                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ predict_proba(X) → raw_probs
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │ BBL League  │    │ SA20 League │    │ SSM League  │
    │ Calibrator  │    │ Calibrator  │    │ Calibrator  │
    │ T₁=0.847    │    │ T₁=0.899    │    │ T₁=0.877    │
    │ T₂=0.830    │    │ T₂=0.765    │    │ T₂=0.888    │
    └─────────────┘    └─────────────┘    └─────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
    calibrated_probs    calibrated_probs    calibrated_probs
```

## Comparison: Isotonic vs Temperature/Platt

| Aspect | Isotonic | Temperature/Platt |
|--------|----------|-------------------|
| **Smoothness** | Steppy | Smooth |
| **Parameters** | Non-parametric | 1-2 params |
| **Data needed** | 5,000+ samples | 500+ samples |
| **Overfitting** | Higher risk | Lower risk |
| **Interpretability** | Low | High (T value) |
| **Recommended for** | Global OOF | League adaptation |

## Troubleshooting

### "No 'league' column - using all data"

This warning is **benign** when using league-specific feature files:
- `data/bbl_features_v4/` contains only BBL data
- `data/sat_features_v2/` contains only SA20 data

The warning matters only when using unified feature files that mix leagues.

### Low improvement (<0.5%)

Expected for well-calibrated global models. The benefit is:
1. Slight LogLoss improvement
2. Better uncertainty estimates for edge cases
3. Adaptation to league-specific chase dynamics
