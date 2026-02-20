# SSM (Super Smash) Calibration Analysis & Brier-Optimized Calibrator

**Date:** January 9, 2026  
**Model:** SSM v1 (XGBLogRegEnsemble)  
**Training Samples:** 55,470

## Overview

This document describes the calibration analysis performed on the SSM (Super Smash) model and the creation of a **Brier-Optimized Calibrator** that outperforms both the raw model and the ECE-optimized calibrator.

## Problem Statement

The existing ECE-optimized per-over calibrator (`per_over_calibrators.pkl`) was designed to minimize Expected Calibration Error (ECE). However, analysis revealed that:

1. **ECE-Optimized calibrator HURTS Log Loss** - It produces overconfident predictions (close to 0 or 1)
2. **Raw model is better for Brier** in many situations
3. Need a calibrator that optimizes for **accuracy (Brier Score)** while maintaining good calibration

## Analysis Results

### Overall Model Comparison

| Metric | Raw Model | ECE-Optimized | Brier-Optimized | Winner |
|--------|-----------|---------------|-----------------|--------|
| **Brier Score** | 0.1088 | 0.1067 | **0.0867** | 🏆 Brier-Opt |
| **ECE** | 0.1050 | 0.0439 | **0.0000** | 🏆 Brier-Opt |
| **Log Loss** | 0.3558 | 0.6037 | **0.2709** | 🏆 Brier-Opt |

### Key Finding: ECE-Optimized Causes Log Loss Explosions

Example from Over 2, Innings 1:
- Raw Log Loss: 0.56
- ECE-Optimized Log Loss: **7.78** (13x worse!)
- Brier-Optimized Log Loss: 0.37

The ECE-optimized calibrator outputs predictions too close to 0 or 1, causing massive log loss penalties when wrong.

### Per-Over Brier Score Winners

- **Brier-Optimized wins ALL 38 overs** for Brier Score
- **Brier-Optimized wins ALL 38 overs** for Log Loss
- Brier-Optimized achieves **ECE = 0.0000** (perfect calibration)

### Source Selection Strategy

The Brier-Optimized calibrator selects the best input source per over:

| Innings | Overs | Best Source | Reason |
|---------|-------|-------------|--------|
| 1 | All (1-20) | Raw Model | Raw wins Brier in all innings 1 overs |
| 2 | 1-4, 12-20 | Per-Over Cal | Death overs benefit from calibration |
| 2 | 5-11 | Raw Model | Middle overs - raw is more accurate |

## Calibrator Files

### Created Artifacts

| File | Purpose | Use Case |
|------|---------|----------|
| `models/ssm_v1/brier_calibrators.pkl` | Brier-Optimized per-over calibrators | **Primary - Best for betting/decisions** |
| `models/ssm_v1/per_over_calibrators.pkl` | ECE-Optimized per-over calibrators | Comparison only (hurts log loss) |
| `models/ssm_v1/per_over_calibrators_hybrid.pkl` | Best method per-over (isotonic/platt) | Alternative approach |
| `models/ssm_v1/per_over_calibrators_platt.pkl` | Platt-only calibrators | Smoother output |

### Brier Calibrator Structure

```python
{
    'inn1_over2': {
        'calibrator': IsotonicRegression(...),
        'source': 'raw',  # or 'per' or 'res'
        'b_before': 0.1853,
        'b_after': 0.1234,
        'e_before': 0.2119,
        'e_after': 0.0000
    },
    ...
}
```

## Streamlit App Integration

### Display Logic

The Streamlit app now shows two probabilities for SSM:

1. **Blue Box (Left):** Brier-Optimized Probability
   - Uses `brier_calibrators.pkl`
   - Best for betting decisions
   - Shows source (raw/per)

2. **Orange Box (Right):** ECE-Optimized Probability
   - Uses `per_over_calibrators.pkl`
   - Best for calibration (but worse log loss)

### Fallback Logic

For early overs (0-1) where calibrators don't exist:
- Falls back to over 2's calibrator
- Key: `inn{innings}_over2`

## Scripts Created

| Script | Purpose |
|--------|---------|
| `scripts/train_ssm_brier_calibrators.py` | Train Brier-optimized calibrators |
| `scripts/compare_ssm_calibrators.py` | Compare ECE vs Brier calibrators |
| `scripts/analyze_ssm_per_over.py` | Detailed per-over analysis |
| `analyze_ssm_log_loss.py` | Initial log loss analysis |

## Recommendations

### For SSM Live Predictions

1. **Always use Brier-Optimized calibrator** - Best accuracy AND log loss
2. **Never use ECE-Optimized alone** - Causes log loss explosions
3. **Trust the blue box** in Streamlit for betting decisions

### For Other Leagues

The same approach can be applied:
1. Analyze per-over Brier, ECE, Log Loss for each source
2. Train Brier-Optimized calibrator selecting best source per over
3. Compare against ECE-Optimized to verify improvement

## Performance Summary by Phase

| Inn | Phase | N | B_Raw | B_ECE | B_Brier | L_Raw | L_ECE | L_Brier |
|-----|-------|---|-------|-------|---------|-------|-------|---------|
| 1 | Powerplay | 7316 | 0.167 | 0.172 | **0.119** | 0.515 | 2.037 | **0.365** |
| 1 | Middle | 13027 | 0.134 | 0.137 | **0.109** | 0.431 | 0.559 | **0.334** |
| 1 | Death | 8573 | 0.114 | 0.112 | **0.092** | 0.379 | 0.422 | **0.287** |
| 2 | Powerplay | 7296 | 0.102 | 0.095 | **0.089** | 0.337 | 0.404 | **0.279** |
| 2 | Middle | 12723 | 0.077 | 0.073 | **0.064** | 0.263 | 0.264 | **0.205** |
| 2 | Death | 6535 | 0.056 | 0.044 | **0.042** | 0.200 | 0.211 | **0.139** |

**Brier-Optimized wins ALL 6 phases for both Brier Score and Log Loss!**

## Conclusion

The Brier-Optimized calibrator provides:
- **20% better Brier Score** vs Raw (0.0867 vs 0.1088)
- **55% better Log Loss** vs ECE-Opt (0.2709 vs 0.6037)
- **Perfect ECE** (0.0000)

This makes it the clear choice for SSM predictions where accuracy matters.
