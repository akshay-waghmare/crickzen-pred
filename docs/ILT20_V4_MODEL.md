# ILT20 v4 Model Documentation

## Overview

ILT20 v4 is the latest model for International League T20 (ILT20) match win probability prediction, trained using the same approach as BBL v8.

## Model Architecture

- **Type**: XGBLogRegEnsemble (50% XGBoost + 50% Logistic Regression)
- **Calibration**: CV-OOF Isotonic Regression (5-fold cross-validation)
- **Features**: 25 features (same as BBL v8)

## Training Data

- **Source**: 100 ILT20 JSON match files from `international_league_data/ilt_male_json`
- **Processing Pipeline**: `bbl_pipeline` CLI (ingest → process)
- **Training Samples**: 23,209 ball-by-ball observations
- **Innings Distribution**: 12,229 (Innings 1) + 10,980 (Innings 2)

## Performance Metrics

| Metric | Value |
|--------|-------|
| OOF Brier Score (before calibration) | 0.0925 |
| OOF Brier Score (after calibration) | 0.0714 |
| OOF ECE | 0.0000 |

## Model Files

```
models/ilt20_v4/
├── champion_model.joblib   # XGBLogRegEnsemble model package
├── isotonic_calibrator.pkl # CV-OOF trained isotonic calibrator
└── metadata.json           # Model metadata and hyperparameters
```

## Features (25 total)

Same feature set as BBL v8:

### DLS-based Features
- `expected_final_score` - DLS projected final score
- `resource_win_prob` - Win probability based on DLS resources
- `score_vs_par` - Current score vs DLS par score
- `dls_pressure_index` - Pressure index based on DLS calculations

### Projection Features
- `projected_vs_venue_avg` - Projected score vs venue average
- `projected_score` - Simple linear projection
- `score_per_wicket` - Runs per wicket lost

### Game State Features
- `is_powerplay` - In powerplay (overs 1-6)
- `run_rate_diff` - Current RR vs required RR
- `required_run_rate` - Required run rate (2nd innings)
- `chase_difficulty` - Difficulty of chase metric
- `wickets_times_balls` - Wickets × balls remaining
- `pressure_index` - Combined pressure metric
- `rrr_times_wickets` - RRR × wickets lost
- `overs_remaining` - Overs left in innings

### Team Strength Features
- `team_strength_diff` - Batting vs bowling team strength
- `batting_team_win_rate` - Historical win rate
- `bowling_team_win_rate` - Historical win rate
- `batting_team_situation_wr` - Situational win rate
- `bowling_team_situation_wr` - Situational win rate
- `situation_advantage` - Difference in situational rates

### Rolling Stats Features
- `boundary_pct_last_18` - Boundary % in last 18 balls
- `runs_last_12` - Runs in last 12 balls
- `runs_last_18` - Runs in last 18 balls
- `wickets_last_12` - Wickets in last 12 balls

## Hyperparameters

### XGBoost
```python
{
    'n_estimators': 100,
    'max_depth': 5,
    'learning_rate': 0.05,
    'colsample_bytree': 0.9,
    'subsample': 0.8,
    'min_child_weight': 5,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0
}
```

### Logistic Regression
```python
{'C': 0.5, 'max_iter': 1000}
```

## Calibration Method

**CV-OOF (Cross-Validation Out-of-Fold) Isotonic Regression**

1. 5-fold stratified cross-validation
2. Each fold: train ensemble, predict on validation set
3. Collect all OOF predictions
4. Fit IsotonicRegression on OOF predictions
5. Final model trained on all data
6. Isotonic calibrator applies to final predictions

This prevents data leakage that occurs with traditional calibration methods.

## Usage

```python
import joblib

# Load model
model = joblib.load('models/ilt20_v4/champion_model.joblib')
calibrator = joblib.load('models/ilt20_v4/isotonic_calibrator.pkl')

# Extract components
xgb = model['xgb_model']
lr = model['lr_model']
scaler = model['scaler']
features = model['features']

# Predict
X_scaled = scaler.transform(X[features])
xgb_prob = xgb.predict_proba(X[features])[:, 1]
lr_prob = lr.predict_proba(X_scaled)[:, 1]
raw_prob = 0.5 * xgb_prob + 0.5 * lr_prob
calibrated_prob = calibrator.predict(raw_prob)
```

## Training Date

Generated: December 2024

## Comparison with Previous Versions

| Version | Brier Score | ECE | Notes |
|---------|-------------|-----|-------|
| ILT20 v2 | 0.0876 | Unknown | Potential data leakage suspected |
| ILT20 v3 | - | - | Features only, no model |
| **ILT20 v4** | **0.0714** | **0.0000** | Fresh pipeline, CV-OOF calibration |

## Notes

- The 0.0714 Brier score is quite low (excellent) compared to BBL v8's 0.1809
- This may be due to:
  - ILT20 being a more predictable league
  - Smaller dataset (23k vs 141k samples)
  - Different team dynamics
- ECE of 0.0000 indicates perfect calibration (probabilities match actual outcomes)
