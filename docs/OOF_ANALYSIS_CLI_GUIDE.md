# OOF Calibration Analysis CLI Guide

## Overview
The `analyze-oof` command provides comprehensive Out-of-Fold (OOF) cross-validation analysis comparing 7 different calibration strategies. This tool helps determine the best calibration approach for your model by evaluating performance across multiple metrics and data segments.

## Quick Start

```bash
bbl-pipeline analyze-oof \
  --input-file data/bbl_features_v2/training.parquet \
  --model-dir models/bbl_v10 \
  --n-splits 5
```

## Command Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--input-file` | Yes | - | Path to training dataset (parquet) |
| `--model-dir` | Yes | - | Model directory containing champion_model.joblib |
| `--n-splits` | No | 5 | Number of folds for cross-validation |
| `--target-col` | No | is_winner | Target column name |
| `--innings-col` | No | innings | Innings column name (optional) |
| `--overs-col` | No | overs_remaining | Overs remaining column (optional, for phase analysis) |

## Calibration Methods Compared

### 1. Raw (Baseline)
- **Description:** Uncalibrated base model predictions
- **Calibrators:** 0
- **Use Case:** Baseline for comparison

### 2. Combined
- **Description:** Single isotonic calibrator for all predictions
- **Calibrators:** 1
- **Use Case:** Simplest calibration approach, minimal overfitting risk

### 3. Innings-Specific
- **Description:** Separate isotonic calibrator per innings (1st, 2nd)
- **Calibrators:** 2
- **Use Case:** Captures different dynamics between batting first vs chasing

### 4. Innings×Phase
- **Description:** Isotonic calibrator for each innings × phase combination
- **Calibrators:** 6 (powerplay/middle/death × 2 innings)
- **Use Case:** Captures changing dynamics throughout the match

### 5. Brier-Optimized
- **Description:** Per-over isotonic calibrators (40 total for T20)
- **Calibrators:** 40 (one per over)
- **Use Case:** Maximally granular, but risk of overfitting
- **Warning:** May hurt LogLoss despite improving Brier

### 6. ECE-Optimized
- **Description:** Histogram binning (15 bins) + isotonic per innings×phase
- **Calibrators:** 6
- **Method:** Groups predictions into bins, fits isotonic to bin centers
- **Use Case:** Best overall balance of metrics

### 7. LogLoss-Optimized
- **Description:** Platt scaling (logistic regression) per innings×phase
- **Calibrators:** 6
- **Method:** Parametric approach, less prone to overfitting than isotonic
- **Use Case:** When probabilistic sharpness is critical

## Output Files

### 1. oof_calibration_results.csv
Detailed metrics for each method × segment combination.

**Columns:**
- `method` - Calibration method name
- `segment` - Data segment (overall, innings_1, innings_2, inn1_powerplay, etc.)
- `brier` - Brier Score (lower is better)
- `ece` - Expected Calibration Error (lower is better, 0.0000 is perfect)
- `logloss` - Log Loss (lower is better)
- `n_samples` - Number of samples in segment

### 2. oof_calibrators.pkl
Dictionary containing trained calibrators for all 7 methods.

**Structure:**
```python
{
    'raw': None,
    'combined': IsotonicRegression(),
    'innings_specific': {1: IsotonicRegression(), 2: IsotonicRegression()},
    'innings_phase': {
        'inn1_powerplay': IsotonicRegression(),
        'inn1_middle': IsotonicRegression(),
        'inn1_death': IsotonicRegression(),
        'inn2_powerplay': IsotonicRegression(),
        'inn2_middle': IsotonicRegression(),
        'inn2_death': IsotonicRegression()
    },
    'brier_optimized': {1: IsotonicRegression(), ..., 40: IsotonicRegression()},
    'ece_optimized': {
        'inn1_powerplay': IsotonicRegression(),
        ...
    },
    'logloss_optimized': {
        'inn1_powerplay': LogisticRegression(),
        ...
    }
}
```

### 3. OOF_CALIBRATION_REPORT.md
Formatted markdown report with:
- Executive summary with overall rankings
- Per-innings breakdown
- Per-innings×phase breakdown

## Evaluation Metrics

### Brier Score
- **Formula:** `mean((predicted_prob - actual_outcome)^2)`
- **Range:** [0, 1], lower is better
- **Interpretation:** Overall prediction accuracy

### Expected Calibration Error (ECE)
- **Method:** 10-bin equal-frequency binning
- **Formula:** `sum(|avg_predicted - avg_actual| * bin_size)`
- **Range:** [0, 1], lower is better, 0.0000 is perfectly calibrated
- **Interpretation:** How well predicted probabilities match actual frequencies

### Log Loss
- **Formula:** `-mean(actual * log(pred) + (1-actual) * log(1-pred))`
- **Range:** [0, ∞], lower is better
- **Interpretation:** Probabilistic sharpness, penalizes confident wrong predictions

## Example Output

```
================================================================================
OOF CALIBRATION ANALYSIS COMPLETE
================================================================================

📊 OVERALL PERFORMANCE:

           method  brier    ece  logloss
  brier_optimized 0.1763 0.0000   0.5186
    innings_phase 0.1791 0.0000   0.5269
    ece_optimized 0.1799 0.0037   0.5305
logloss_optimized 0.1813 0.0166   0.5355
 innings_specific 0.1814 0.0000   0.5334
         combined 0.1822 0.0000   0.5363
              raw 0.1830 0.0172   0.5393

🏆 RANKINGS:

Best Brier:   brier_optimized (0.1763)
Best ECE:     brier_optimized (0.0000)
Best LogLoss: brier_optimized (0.5186)

✅ Results saved to: models\bbl_v10
   - oof_calibration_results.csv (detailed metrics)
   - oof_calibrators.pkl (trained calibrators)
   - OOF_CALIBRATION_REPORT.md (markdown report)
```

## Usage Examples

### BBL Model Analysis
```bash
bbl-pipeline analyze-oof \
  --input-file data/bbl_features_v2/training.parquet \
  --model-dir models/bbl_v10
```

### ILT20 Model Analysis
```bash
bbl-pipeline analyze-oof \
  --input-file data/ilt_features_v3/training.parquet \
  --model-dir models/ilt20_v5
```

### SSM Model Analysis
```bash
bbl-pipeline analyze-oof \
  --input-file data/ssm_features_v1/training.parquet \
  --model-dir models/ssm_v1
```

### Custom Splits
```bash
bbl-pipeline analyze-oof \
  --input-file data/bbl_features_v2/training.parquet \
  --model-dir models/bbl_v10 \
  --n-splits 10
```

## Interpretation Guidelines

### Choosing the Best Method

**For Overall Accuracy:**
- Prioritize Brier Score
- Look at overall segment performance
- Consider `brier_optimized` or `ece_optimized`

**For Calibration Quality:**
- Prioritize ECE
- Methods with ECE ≈ 0.0000 are perfectly calibrated
- `innings_phase` and `innings_specific` often achieve ECE = 0.0000

**For Probabilistic Sharpness:**
- Prioritize Log Loss
- Lower values indicate better probability estimates
- `logloss_optimized` typically performs best here

**For Robustness:**
- Choose methods with fewer calibrators to reduce overfitting risk
- `combined` (1 calibrator) or `innings_specific` (2 calibrators)
- Check per-innings and per-phase consistency

### Red Flags

⚠️ **Brier-Optimized Hurting LogLoss:**
- If per-over calibrators improve Brier but hurt LogLoss, it's overfitting
- Example: Brier 0.1763 (best) but LogLoss 0.5186 vs Raw LogLoss 0.5393

⚠️ **Large ECE Gaps Between Training and OOF:**
- Indicates calibrator overfitting
- Prefer simpler calibration strategies

⚠️ **Wildly Different Performance by Segment:**
- Check if calibration helps consistently across innings and phases
- Inconsistent performance suggests instability

## Technical Details

### Cross-Validation Strategy
- **Method:** K-Fold (default K=5)
- **Shuffle:** No (preserves temporal order)
- **Clone:** Each fold uses a fresh model clone to prevent information leakage

### Phase Definitions
- **Powerplay:** Overs 1-6
- **Middle:** Overs 7-16
- **Death:** Overs 17-20

### Feature Alignment
- Automatically aligns features with model's `selected_features_` or `feature_names_in_`
- Drops non-numeric columns and fills NaNs with 0
- Drops internal columns (starting with `__`)

## Integration with Pipeline

The `analyze-oof` command complements the existing pipeline:

1. **`ingest`** - JSON → Parquet
2. **`process`** - Parquet → Features
3. **`train`** - Features → Model
4. **`analyze-oof`** ← **NEW** - Model + Features → Calibration Analysis
5. **`generate-oof`** - Model + Features → OOF Calibrators
6. **`evaluate`** - Model + Features → Performance Metrics
7. **`predict`** - Model + Match State → Live Predictions

## Best Practices

1. **Run After Training:**
   - Analyze calibration after every model training
   - Compare methods before deciding on production calibrator

2. **Use OOF, Not In-Sample:**
   - This tool uses proper cross-validation
   - OOF metrics are unbiased estimates of generalization

3. **Consider All Metrics:**
   - Don't optimize for Brier alone
   - Balance Brier, ECE, and LogLoss
   - Check consistency across segments

4. **Document Your Choice:**
   - Save the analysis report with your model
   - Justify why you chose a particular calibration method
   - Update model documentation

5. **Re-analyze After Retraining:**
   - Calibration performance can change with new data
   - Best method may shift over time

## Related Documentation

- [BBL v10 Model Documentation](BBL_V10_MODEL.md)
- [ECE Optimization Guide](ECE_OPTIMIZATION_GUIDE.md)
- [BBL Comprehensive OOF Analysis](../BBL_CALIBRATION_OOF_ANALYSIS.md)
- [Feature Store Guide](FEATURE_STORE.md)
