# BBL v8 Model Documentation

**Date:** December 14, 2025  
**Model Version:** bbl_v8  
**Training Data:** `data/bbl_features_v2/training.parquet`

## Overview

BBL v8 is a perfectly calibrated ensemble model for predicting T20 cricket match outcomes. It combines XGBoost and Logistic Regression with isotonic calibration to achieve zero Expected Calibration Error (ECE).

## Model Architecture

### Ensemble: XGBLogRegEnsemble
- **XGBoost Weight:** 50%
- **Logistic Regression Weight:** 50%
- **Calibration:** Isotonic Regression (CV-OOF fitted)

### XGBoost Hyperparameters
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

## Features (25 Total)

### Core Scoring Features
| Feature | Description |
|---------|-------------|
| `expected_final_score` | Projected final score based on current run rate |
| `projected_score` | Alternative projected score calculation |
| `score_vs_par` | Current score vs DLS par score |
| `projected_vs_venue_avg` | Projected score vs venue average |
| `score_per_wicket` | Runs per wicket lost |

### Chase/Pressure Features
| Feature | Description |
|---------|-------------|
| `resource_win_prob` | DLS-style resource-based win probability |
| `dls_pressure_index` | Pressure index based on DLS resources |
| `required_run_rate` | Required run rate to win (2nd innings) |
| `run_rate_diff` | Current RR - Required RR |
| `chase_difficulty` | Difficulty of the chase |
| `pressure_index` | Overall pressure index |
| `rrr_times_wickets` | RRR × wickets (interaction feature) |
| `wickets_times_balls` | Wickets × balls remaining |

### Team Strength Features
| Feature | Description |
|---------|-------------|
| `batting_team_win_rate` | Historical win rate of batting team |
| `bowling_team_win_rate` | Historical win rate of bowling team |
| `batting_team_situation_wr` | Situational win rate for batting team |
| `bowling_team_situation_wr` | Situational win rate for bowling team |
| `team_strength_diff` | Difference in team strengths |
| `situation_advantage` | Situational advantage |

### Rolling Stats (Ball History)
| Feature | Description |
|---------|-------------|
| `runs_last_12` | Runs scored in last 12 balls |
| `runs_last_18` | Runs scored in last 18 balls |
| `wickets_last_12` | Wickets lost in last 12 balls |
| `boundary_pct_last_18` | Boundary percentage in last 18 balls |

### Context Features
| Feature | Description |
|---------|-------------|
| `is_powerplay` | Whether in powerplay (overs 0-6) |
| `overs_remaining` | Overs remaining in innings |

## Performance Metrics

### Calibration
| Metric | Value |
|--------|-------|
| **Brier Score** | 0.1809 |
| **ECE (Expected Calibration Error)** | 0.0000 |

### Comparison with Previous Versions
| Model | Brier | ECE | Calibration |
|-------|-------|-----|-------------|
| bbl_v6 | 0.1798 | 0.0127 | None |
| bbl_v7 | 0.1807 | 0.0066 | Isotonic (leaky) |
| **bbl_v8** | **0.1809** | **0.0000** | Isotonic (CV-OOF) |

## Isotonic Calibration (CV-OOF)

### The Data Leakage Problem
Initial isotonic calibration (v7) showed suspiciously perfect ECE=0.0000 on training data because the calibrator was trained on the same data it was evaluated on.

### Solution: Cross-Validation Out-of-Fold (CV-OOF)
1. Split training data into 5 folds (temporal, no shuffle)
2. For each fold:
   - Train base model on other 4 folds
   - Get OOF predictions for held-out fold
3. Collect all OOF predictions
4. Fit isotonic calibrator on OOF predictions
5. Retrain final model on full data
6. Apply calibrator at inference time

### Implementation
```python
# Calibration is applied in predictor.py
raw_prob = base_model.predict_proba(X)[:, 1]
calibrated_prob = isotonic_calibrator.predict(raw_prob)
```

## Resource Win Probability Formula

The `resource_win_prob` feature uses a logistic function based on Required Run Rate:

```python
RRR_MIDPOINT = 9.5   # RRR where win prob = 50%
RRR_BETA = 0.7       # Steepness of the curve

base_prob = 1.0 / (1.0 + exp(RRR_BETA * (rrr - RRR_MIDPOINT)))
```

### EDA Findings
- Actual 50% crossover in training data: RRR ≈ 8.7
- For RRR < 5 with ≤2 wickets: actual win rate = 99.6%
- Model output is intentionally conservative for extreme cases

## Model Files

```
models/bbl_v8/
├── champion_model.joblib      # XGBLogRegEnsemble (uncalibrated base)
├── isotonic_calibrator.pkl    # CV-OOF fitted calibrator
└── champion_metadata.json     # Metadata including training config
```

## Live Prediction Fixes (Dec 14, 2025)

### Bug Fixes Applied to `crex_live_predictor.py`

#### 1. Wicket Detection - Wide Ball Fix
**Problem:** Wides ("WD", "1W") were being counted as wickets because `"W" in u_val.upper()` matched.

**Fix:**
```python
# Before (buggy)
is_wicket = u_val.upper() in ("W", "OUT") or "W" in u_val.upper() or has_wicket_field

# After (fixed)
is_wide = "WD" in u_upper or (u_upper.endswith("W") and u_upper != "W")
is_wicket = (u_upper in ("W", "OUT") or has_wicket_field) and not is_wide
```

#### 2. Rolling Stats Cross-Innings Contamination
**Problem:** Ball history from 1st innings was leaking into 2nd innings rolling stats.

**Fix:** Added innings boundary detection in `_build_ball_history_for_mapper()`:
- Detects when over numbers reset (e.g., over 19 → over 0)
- Filters out 1st innings balls when in 2nd innings

#### 3. Rolling Stats Returning 0.0
**Problem:** `balls_data` was being cleared on innings change, losing all ball history.

**Fix:** Removed the line that cleared `balls_data` on innings change. The `_build_ball_history_for_mapper()` function now handles innings filtering internally.

#### 4. Target Extraction for Level Scores
**Problem:** When scores are level (e.g., 113/5 chasing 114), the "need X runs" text disappears, causing `target=None`.

**Fix:** Added fallback target extraction from first innings score:
```python
first_innings_match = re.search(r'vs\s+[A-Za-z\s]+\s+(\d+)-\d+\s+\(\(', page_text)
if first_innings_match and self.match_state.target is None:
    first_innings_score = int(first_innings_match.group(1))
    self.match_state.target = first_innings_score + 1
```

#### 5. Early Overs Guardrails
**Problem:** Model predictions were being overridden by simple heuristics even in later overs.

**Fix:** Guardrails now only apply when `overs < 10` instead of always.

## Training Command

```bash
python -m bbl_pipeline.training.train \
    --training-data data/bbl_features_v2/training.parquet \
    --output-dir models/bbl_v8 \
    --model-type xgb_logreg_ensemble \
    --feature-set TOP_25 \
    --calibration isotonic_cv_oof
```

## Usage

### Offline Prediction
```python
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

predictor = Predictor.load('models/bbl_v8', 'data/bbl_feature_store_v2')

state = MatchState(
    match_id='test',
    innings=2, over=10, ball=0,
    current_score=100, wickets_lost=3,
    batsman_1='Player A', batsman_2='Player B', bowler='Player C',
    batting_team='Perth Scorchers', bowling_team='Sydney Sixers',
    venue='Perth Stadium', target_runs=156
)

win_prob = predictor.predict(state)
print(f"Win probability: {win_prob:.1%}")
```

### Live Prediction
```bash
python -m bbl_pipeline.inference.crex_live_predictor \
    --model-dir models/bbl_v8 \
    --feature-store-dir data/bbl_feature_store_v2 \
    --match-url "https://crex.com/scoreboard/..."
```

## Changelog

### v8 (Dec 14, 2025)
- ✅ Perfect calibration with CV-OOF isotonic regression (ECE=0.0000)
- ✅ Fixed wicket detection for wides
- ✅ Fixed rolling stats cross-innings contamination
- ✅ Fixed target extraction for level scores
- ✅ Improved guardrails (only apply in early overs)

### v7 (Dec 14, 2025)
- Added isotonic calibration (data leakage issue)

### v6 (Dec 14, 2025)
- Improved hyperparameters for feature importance
- Better model architecture

### v5 (Dec 14, 2025)
- XGBLogRegEnsemble with 25 features
- Initial training with new feature set
