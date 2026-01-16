# BBL v12 Model Documentation

**Version:** 12  
**Date:** January 16, 2026  
**Brier Score:** 0.1825 (OOF)  
**Features:** data/bbl_features_v4/  

## Overview

BBL v12 introduces **empirically calibrated wicket penalties** for first innings, derived from actual projected score data rather than assumed penalty curves. This addresses the "tail event issue" where models were too pessimistic about high-wicket situations in death overs.

## Key Improvement: Empirical Wicket Penalties

### The Problem (v10-v11)

In first innings death overs (overs 14-20), the model was too pessimistic:
- 210/6 at 19 overs predicted lower win probability than 202/2 at 18 overs
- Wicket penalties were based on assumed curves, not actual data
- Predictions were systematically 10-15% below actual outcomes

### The Solution (v12)

Penalties are now derived from **empirical projected score ratios**:

```
For each (phase, ease_bucket, wickets) combination:
  penalty = mean(projected_score | wickets) / mean(projected_score | 0 wickets)
```

This follows the WASP dynamic programming approach where `V(b,w)` (expected additional runs) is learned from historical patterns.

### Death Phase Penalties (Before vs After)

| Wickets | Old (v11) | New (v12) | Actual Impact |
|---------|-----------|-----------|---------------|
| 5 | 0.33-0.78 | 0.93-1.00 | ~0.94 |
| 6 | 0.22-0.84 | 0.88-1.00 | ~0.92 |
| 7 | 0.14-0.60 | 0.88-0.98 | ~0.91 |
| 8 | 0.11-0.40 | 0.86-1.00 | ~0.89 |

**Key Insight:** In T20 death overs, wickets have minimal impact on final score because:
1. Batters are already set and accelerating
2. Banked runs dominate the projection
3. Remaining balls contribute minimal additional runs
4. Even 7-8 wickets down, teams maintain ~90% of projected output

## Performance Comparison

### v10 → v12 RAW Brier Scores

| Segment | v10 | v12 | Change |
|---------|-----|-----|--------|
| **Overall** | 0.1830 | 0.1825 | **-0.30%** ✅ |
| inn1_powerplay | 0.2414 | 0.2411 | -0.10% |
| inn1_middle | 0.2193 | 0.2188 | -0.23% |
| **inn1_death** | 0.2041 | 0.2033 | **-0.40%** ✅ |
| inn2_powerplay | 0.1943 | 0.1948 | +0.27% |
| inn2_middle | 0.1392 | 0.1390 | -0.12% |
| **inn2_death** | 0.0885 | 0.0859 | **-3.00%** ✅ |

### Calibrated Model Performance

| Method | Brier | ECE | LogLoss |
|--------|-------|-----|---------|
| brier_optimized | 0.1760 | 0.0000 | 0.5190 |
| innings_phase | 0.1787 | 0.0000 | 0.5269 |
| ece_optimized | 0.1796 | 0.0038 | 0.5300 |
| innings_specific | 0.1809 | 0.0000 | 0.5327 |
| raw | 0.1825 | 0.0162 | 0.5381 |

## Feature Importance

Top 10 features (from XGBLogRegEnsemble):

1. `resource_win_prob` - DLS-style resource probability
2. `score_vs_par` - Current score relative to expected
3. `projected_score` - Expected final score
4. `wickets_lost` - Current wickets down
5. `overs_remaining` - Balls left in innings
6. `current_run_rate` - Runs per over so far
7. `required_run_rate` - Target RRR (innings 2)
8. `run_rate_diff` - CRR minus RRR
9. `team_win_rate` - Historical team strength
10. `batting_team_rating` - Team batting ability

## Architecture

```
XGBLogRegEnsemble
├── XGBoost (50% weight)
│   └── 25 features, depth=4, n_estimators=100
└── Logistic Regression (50% weight)
    └── 25 features, regularization=1.0
```

## Files

- `models/bbl_v12/champion_model.joblib` - Trained model
- `models/bbl_v12/oof_calibrators.pkl` - OOF calibrators
- `models/bbl_v12/oof_calibration_results.csv` - Detailed metrics
- `models/bbl_v12/OOF_CALIBRATION_REPORT.md` - Auto-generated report

## Usage

```bash
# Training
bbl-pipeline train \
  --input-file data/bbl_features_v4/training.parquet \
  --output-dir models/bbl_v12

# OOF Analysis
bbl-pipeline analyze-oof \
  --input-file data/bbl_features_v4/training.parquet \
  --model-dir models/bbl_v12 \
  --n-splits 5

# Live Inference
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_URL" \
  --model-dir models/bbl_v12 \
  --feature-store-dir data/bbl_feature_store_v2
```

## Changelog

### v12 (January 2026)
- Empirically calibrated `FIRST_INNINGS_WICKET_PENALTY_3D` for death/middle phases
- Death penalties increased from 0.33-0.78 to 0.88-1.00 (less harsh)
- Overall Brier: 0.1825 (-0.30% vs v10)
- Inn1 death Brier: 0.2033 (-0.40% vs v10)
- Inn2 death Brier: 0.0859 (-3.00% vs v10)

### v11 (January 2026)
- Added 2D dynamic wicket penalty for 2nd innings (chase ease × wickets)
- Inn2 death improved by -2.76% Brier

### v10 (December 2025)
- Baseline model with flat wicket penalties
- Brier: 0.1830
