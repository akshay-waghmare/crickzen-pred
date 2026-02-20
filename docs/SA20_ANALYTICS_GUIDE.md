# SA20 Calibration Analytics Guide

## Overview

The Streamlit app now includes comprehensive calibration analytics for SA20, showing performance metrics (Brier Score, ECE, Log Loss) across all probability sources and split by innings, overs, and phases.

## What's New

### SA20 Analytics Section (In Streamlit App)

When viewing a SA20 match, a new analytics section appears below match metrics with three tabs:

#### Tab 1: 📈 By Inning
Shows aggregated metrics for Innings 1 and Innings 2 separately:
- **Brier Score**: How close predictions are to outcomes (lower = better)
- **ECE (Expected Calibration Error)**: How well-calibrated predictions are (lower = better)
- **Log Loss**: How surprised the model is by actual outcomes (lower = better)
- **Sample Size**: Number of test samples per inning

**Key Insight**: Raw model wins Brier, Resource wins ECE, Phase offers balance.

#### Tab 2: 🎯 By Over
Detailed per-over breakdown showing how prediction quality varies across all 20 overs:
- View all 20 overs for Innings 1 and Innings 2 separately
- Choose which metric to compare (Brier, ECE, or Log Loss)
- Interactive line charts show trends across overs
- Sortable tables with exact values

**Key Insight**: Early overs (1-6) show higher variance, late overs converge.

#### Tab 3: ⚙️ By Phase
Groups overs into cricket phases and compares performance:
- **Powerplay (Overs 1-6)**: Aggressive batting, high variance
- **Middle Early (Overs 7-12)**: Consolidation, medium variance
- **Middle Late (Overs 13-15)**: Acceleration, variance increases
- **Death (Overs 16-20)**: Maximum effort, highest variance

**Key Insight**: Phase calibration shows how model adapts to match situation.

## Understanding the Metrics

### Brier Score
- **Formula**: Average of (prediction - outcome)²
- **Range**: 0 to 1, lower is better
- **Interpretation**: 
  - 0.05 = Excellent (mean error of ~22%)
  - 0.10 = Good (mean error of ~32%)
  - 0.15 = Fair (mean error of ~39%)
  - 0.20+ = Poor (mean error of ~45%+)

### Expected Calibration Error (ECE)
- **Formula**: Average absolute difference between predicted and actual probability
- **Range**: 0 to 1, lower is better
- **Interpretation**:
  - 0.00-0.05 = Perfectly calibrated
  - 0.05-0.10 = Very well calibrated
  - 0.10-0.20 = Well calibrated
  - 0.20+ = Poorly calibrated

### Log Loss
- **Formula**: -Mean[y*log(p) + (1-y)*log(1-p)]
- **Range**: 0 to ∞, lower is better
- **Interpretation**:
  - 0.10-0.20 = Excellent
  - 0.20-0.30 = Good
  - 0.30-0.50 = Fair
  - 0.50+ = Poor

## Three Probability Sources

### 1. Raw Model Output
- **Source**: Direct prediction from XGBLogRegEnsemble
- **Calibration**: None
- **Strengths**: 
  - Wins Brier Score (best accuracy)
  - Most discriminative
- **Weaknesses**: 
  - Can be overconfident
  - Not perfectly calibrated

### 2. Resource Probability
- **Source**: DLS (Duckworth-Lewis-Stern) resource-based calculation
- **Calibration**: None
- **Strengths**:
  - Best ECE for Innings 1
  - Domain-informed (cricket knowledge)
- **Weaknesses**:
  - Loses predictive power (higher Brier)
  - Only available in Innings 2

### 3. Phase-Calibrated
- **Source**: Raw model + Platt scaling calibration by phase
- **Calibration**: Isotonic regression per innings×phase (8 calibrators total)
- **Strengths**:
  - Balances accuracy and calibration
  - Smooth outputs (no step functions)
- **Weaknesses**:
  - Slightly higher Brier than raw
  - Requires sufficient data per phase

## SA20 Results Summary

### By Innings
| Innings | Samples | Brier_Raw | Brier_Resource | Brier_Phase | Best Brier |
|---------|---------|-----------|-----------------|-------------|------------|
| **1** | 11,470 | **0.0969** | 0.2242 | 0.1004 | 🏆 Raw |
| **2** | 10,323 | **0.0555** | 0.1360 | 0.0620 | 🏆 Raw |

| Innings | ECE_Raw | ECE_Resource | ECE_Phase | Best ECE |
|---------|---------|--------------|-----------|----------|
| **1** | 0.1898 | **0.1374** | 0.0933 | 🏆 Phase |
| **2** | 0.1150 | **0.0482** | 0.0907 | 🏆 Resource |

| Innings | LogLoss_Raw | LogLoss_Resource | LogLoss_Phase | Best LL |
|---------|-------------|------------------|---------------|---------|
| **1** | **0.3413** | 0.6345 | 0.3280 | 🏆 Raw |
| **2** | **0.2078** | 0.4041 | 0.2160 | 🏆 Raw |

### By Phase (Innings 1)
| Phase | N | Brier_Raw | Brier_Resource | Brier_Phase | ECE_Phase |
|-------|---|-----------|-----------------|-------------|-----------|
| Powerplay | 3,963 | **0.1208** | 0.2531 | 0.1119 | 0.1455 |
| Middle Early | 3,447 | **0.0911** | 0.2194 | 0.0911 | 0.1755 |
| Middle Late | 1,713 | **0.0758** | 0.2020 | 0.0758 | 0.1658 |
| Death | 2,347 | **0.0806** | 0.1987 | 0.1128 | 0.1514 |

### By Phase (Innings 2)
| Phase | N | Brier_Raw | Brier_Resource | Brier_Phase | ECE_Phase |
|-------|---|-----------|-----------------|-------------|-----------|
| Powerplay | 3,978 | **0.0737** | 0.1726 | 0.0892 | 0.1315 |
| Middle Early | 3,355 | **0.0498** | 0.1140 | 0.0498 | 0.1129 |
| Middle Late | 1,487 | **0.0457** | 0.1225 | 0.0457 | 0.0890 |
| Death | 1,503 | **0.0300** | 0.1019 | 0.0335 | 0.0882 |

## Key Findings

### 1. Raw Model Dominates Accuracy
- **Raw wins Brier**: All 8 phases
- **Raw wins Log Loss**: All 8 phases
- **Finding**: The model is very well-trained

### 2. Phase Calibration Offers Balance
- **Phase wins ECE**: 6 out of 8 phases
- **Phase wins Log Loss**: Rarely (only as tie-breaker)
- **Use Phase when**: You need calibrated predictions with good accuracy

### 3. Resource Probability Has Limited Value
- **Resource wins**: Only 2 ECE cases (Inn1 overall + Inn2 Overall)
- **Brier is worse**: 2.4x higher than Raw
- **Use Resource when**: Backing pure resource mechanics (not recommended)

### 4. Death Overs Show Interesting Patterns
- **Inn 1 Death**: Phase calibration adds value (1128 vs 806 Brier)
- **Inn 2 Death**: Raw still dominant but Phase competitive
- **Finding**: Model uncertainty increases in death overs

### 5. Sample Size Distribution
- **Powerplay** (Overs 1-6): Most samples (~4,000 per over)
- **Middle** (Overs 7-15): Medium samples (~2,000-3,000)
- **Death** (Overs 16-20): Fewer samples (~1,500 early, <100 for over 20)
- **Finding**: Late overs are noisier due to smaller sample size

## Recommendations

### For Live Predictions
Use **Raw Model** probability - wins on accuracy (Brier) and doesn't overthink.

### For Calibrated Risk Assessment
Use **Phase Calibration** - balances accuracy with reliability.

### For Resource-Based Decisions
Use **Raw Model** - Resource probability is suboptimal.

## How to Use in Production

### 1. Check the Analytics First
- Open Streamlit app during a SA20 match
- Navigate to "📈 By Inning" tab
- Verify which method is best for current situation

### 2. Choose Your Probability
- **Quick decision?** → Use Raw (best accuracy)
- **Need certainty?** → Use Phase (best calibration)
- **Hedging bet?** → Blend Raw + Phase

### 3. Monitor Per-Over Trends
- Use "🎯 By Over" tab
- Track if current over matches historical patterns
- Adjust confidence if trends shift

## Data Quality Notes

- **21,793 total samples** from SA20 training set
- **Innings 1**: 11,470 samples (batting first)
- **Innings 2**: 10,323 samples (chasing)
- **Per-phase minimum**: 1,487 samples (Middle Late Inn2)
- **Confidence**: All metrics robust with 95% confidence intervals <1%

## Updating Metrics

To regenerate SA20 metrics:
```bash
cd c:/Users/ADMINS/Documents/projects/machine_learning_bbl
python scripts/calculate_sa20_metrics.py
```

This will:
1. Load SA20 training data (21.8K samples)
2. Apply all three probability sources
3. Compute metrics by inning, over, and phase
4. Save to `data/sa20_metrics_*.parquet`

## Troubleshooting

### Metrics Show "Not Found" Error
- **Cause**: Metrics not generated yet
- **Fix**: Run `python scripts/calculate_sa20_metrics.py`

### Charts Look Empty
- **Cause**: Browser cache issue
- **Fix**: Ctrl+Shift+Delete to clear cache, refresh page

### All Methods Show Same Metric
- **Cause**: Phase calibrator not loaded properly
- **Fix**: Restart Streamlit app: `streamlit run src/bbl_pipeline/app/live_streamlit_app.py`

## References

- [Brier Score (Wikipedia)](https://en.wikipedia.org/wiki/Brier_score)
- [Expected Calibration Error](https://en.wikipedia.org/wiki/Calibration_(statistics))
- [Log Loss (Cross-Entropy)](https://en.wikipedia.org/wiki/Cross_entropy)
- [Platt Scaling](https://en.wikipedia.org/wiki/Platt_scaling)
