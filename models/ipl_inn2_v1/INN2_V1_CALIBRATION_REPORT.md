# IPL Inn2 Phase Models — Calibrated OOF Report

## Summary

Phase-specific inn2 models (PP / Mid / Death) with per-over isotonic calibration
vs v7 global model (brier_optimized calibrated).

### OOF Brier Comparison

| Phase | Rows | Raw OOF | Cal (per-over) | v7 Raw | v7 Cal | vs v7-raw | vs v7-cal |
|-------|-----:|:-------:|:--------------:|:------:|:------:|:---------:|:---------:|
| Inn2-PP    | 43,551 | 0.1734 | **0.1704** | 0.1830 | 0.1803 | -5.3% | -5.5% |
| Inn2-Mid   | 62,736 | 0.1335 | **0.1307** | 0.1467 | 0.1439 | -9.0% | -9.2% |
| Inn2-Death | 20,972 | 0.0791 | **0.0771** | 0.0962 | 0.0926 | -17.7% | -16.8% |
| **Inn2 Routing** | 127,259 | 0.1382 | **0.1354** | 0.1435 | 0.1405 | -3.7% | **-3.6%** |

### Key Insight: Calibration Gap

Calibration closes the gap between raw and v7-cal baselines:

| Phase | Raw vs v7-cal | Cal vs v7-cal | Calibration Gain |
|-------|:-------------:|:-------------:|:----------------:|
| PP    | -3.8% | -5.5% | +1.6pp |
| Mid   | -7.2% | -9.2% | +2.0pp |
| Death | -14.5% | -16.8% | +2.2pp |

### Production Path → ipl_v11

- **Inn1**: Keep v7 global model (best overall: 0.18099)  
- **Inn2**: Route to phase model by over:
  - Overs 1–6 → inn2_pp model + per-over calibrator
  - Overs 7–15 → inn2_mid model + per-over calibrator
  - Overs 16–20 → inn2_death model + per-over calibrator

Calibrators saved: `models/ipl_inn2_v1/phase_oof_calibrators.pkl`
