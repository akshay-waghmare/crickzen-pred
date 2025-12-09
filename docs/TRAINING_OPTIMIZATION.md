# BBL Win Probability Model - Training Optimization Findings

## Summary

After extensive experimentation (December 2025), the following optimizations were implemented to achieve the best Brier score for win probability predictions.

**Final Result: Brier Score = 0.1795** (5-fold time-series cross-validation)

## Key Findings

### 1. Post-Hoc Calibration HURTS Performance ⚠️

**This was the most significant finding.**

| Calibration Method | Brier Score |
|-------------------|-------------|
| No calibration    | **0.1795** ✅ |
| Temperature scaling | 0.1814 |
| Beta calibration  | 0.1809 |
| Platt (sigmoid)   | 0.1820 |
| Isotonic          | 0.1854 ❌ |

**Why?** XGBoost with `objective='binary:logistic'` already produces well-calibrated probabilities. Post-hoc calibration:
1. Takes data away from training (calibration set)
2. Can overfit to the calibration set (especially isotonic)
3. Adds unnecessary complexity

**Action:** Default training now uses `--no-calibration`. Use `--calibration` flag only if you have a specific reason.

### 2. Optimal Hyperparameters

After grid search, these hyperparameters are optimal:

```python
XGBClassifier(
    objective='binary:logistic',
    eval_metric='logloss',
    n_estimators=700,
    max_depth=2,           # Shallow trees prevent overfitting
    learning_rate=0.01,    # Slow learning for stability
    subsample=0.45,
    colsample_bytree=0.45,
    min_child_weight=30,   # Heavy regularization
    reg_alpha=3.5,
    reg_lambda=4.5,
    tree_method='hist'
)
```

**Key insight:** Shallow trees (max_depth=2) with heavy regularization work best for probability estimation.

### 3. Sampling Strategy

| Strategy | Samples | Brier Score |
|----------|---------|-------------|
| End-of-over | 23,499 | **0.1795** ✅ |
| Every 2nd ball | 71,639 | 0.1897 |
| Every 3rd ball | 47,760 | 0.1897 |
| Full ball-by-ball | 143,278 | 0.1895 |

**Why end-of-over works best:**
- Less temporal autocorrelation between samples
- More meaningful decision points (after each over)
- Better class balance

### 4. Feature Importance (DLS Features Dominate)

Top 10 features by XGBoost importance:

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | resource_win_prob | 10.6% |
| 2 | expected_final_score | 8.8% |
| 3 | projected_vs_venue_avg | 7.1% |
| 4 | score_vs_par | 6.4% |
| 5 | dls_pressure_index | 6.1% |
| 6 | required_run_rate | 4.2% |
| 7 | projected_score | 4.0% |
| 8 | score_per_wicket | 4.0% |
| 9 | chase_difficulty | 3.3% |
| 10 | run_rate_diff | 2.9% |

**Key insight:** DLS-style resource features (cricket domain knowledge) are the most predictive. Additional team/venue features added noise, not signal.

### 5. What Didn't Help

| Approach | Result |
|----------|--------|
| Team form features (recent 3-match win rate) | +0.0045 worse |
| Venue-specific features | +0.0035 worse |
| Home/away indicators | No improvement |
| Sample weighting by game phase | No improvement |
| Polynomial/interaction features | No improvement |
| Bagging (multiple random seeds) | No improvement |

### 6. Ensemble Blending

Blending multiple models achieves slight improvement but adds complexity:

| Model | Brier Score |
|-------|-------------|
| XGBoost alone | 0.1795 |
| XGB + LGBM + LogReg blend | 0.1787 |

Optimal blend weights: XGB=50%, LGBM=20%, LogReg=30%

**Recommendation:** Use single XGBoost for simplicity unless the 0.0008 improvement justifies ensemble complexity.

## Usage

### Training (Default - Best Performance)
```bash
python -m bbl_pipeline.cli train \
    --input-file data/training_sampled.parquet \
    --output-dir models/champion
```

### Training with Calibration (if needed)
```bash
python -m bbl_pipeline.cli train \
    --input-file data/training_sampled.parquet \
    --output-dir models/champion \
    --calibration
```

## Model Location

Best model saved at: `models/champion_uncalibrated/`
- `champion_model.joblib` - Trained XGBoost model
- `champion_metadata.json` - Model metadata and Brier score

## Future Improvements

To push below 0.17 Brier, consider:
1. **More training data** - Additional seasons, other T20 leagues
2. **Neural networks** - May capture complex non-linear patterns
3. **Live data features** - Ball-tracking data, real-time player form
4. **Domain expertise** - Cricket analysts may identify missing signals
