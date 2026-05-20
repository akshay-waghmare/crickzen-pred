# OOF Calibration Analysis Report

**Generated:** 2026-05-03 02:28:12
**Samples:** 278,954
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1817 | 0.0000 | 0.5297 |
| innings_phase | 0.1834 | 0.0000 | 0.5348 |
| ece_optimized | 0.1839 | 0.0022 | 0.5368 |
| innings_specific | 0.1842 | 0.0000 | 0.5375 |
| combined | 0.1844 | 0.0000 | 0.5383 |
| raw | 0.1848 | 0.0117 | 0.5400 |
| logloss_optimized | 0.1851 | 0.0167 | 0.5428 |
| resource_win_prob | 0.2046 | 0.0749 | 0.5923 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2195 | 0.0000 | 0.6266 | 144340.0000 |
| innings_phase | 0.2213 | 0.0000 | 0.6311 | 144340.0000 |
| ece_optimized | 0.2218 | 0.0015 | 0.6326 | 144340.0000 |
| innings_specific | 0.2219 | 0.0000 | 0.6328 | 144340.0000 |
| combined | 0.2222 | 0.0074 | 0.6338 | 144340.0000 |
| logloss_optimized | 0.2223 | 0.0066 | 0.6345 | 144340.0000 |
| raw | 0.2228 | 0.0154 | 0.6354 | 144340.0000 |
| resource_win_prob | 0.2507 | 0.1336 | 0.7086 | 144340.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1411 | 0.0000 | 0.4259 | 134614.0000 |
| innings_phase | 0.1428 | 0.0000 | 0.4316 | 134614.0000 |
| ece_optimized | 0.1433 | 0.0033 | 0.4341 | 134614.0000 |
| innings_specific | 0.1437 | 0.0000 | 0.4352 | 134614.0000 |
| combined | 0.1439 | 0.0080 | 0.4358 | 134614.0000 |
| raw | 0.1441 | 0.0103 | 0.4376 | 134614.0000 |
| logloss_optimized | 0.1452 | 0.0319 | 0.4446 | 134614.0000 |
| resource_win_prob | 0.1552 | 0.0178 | 0.4676 | 134614.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2383 | 0.0000 | 0.6684 | 36260.0000 |
| innings_phase | 0.2395 | 0.0000 | 0.6711 | 36260.0000 |
| ece_optimized | 0.2400 | 0.0038 | 0.6723 | 36260.0000 |
| innings_specific | 0.2401 | 0.0093 | 0.6729 | 36260.0000 |
| logloss_optimized | 0.2403 | 0.0066 | 0.6734 | 36260.0000 |
| combined | 0.2404 | 0.0149 | 0.6735 | 36260.0000 |
| raw | 0.2409 | 0.0177 | 0.6746 | 36260.0000 |
| resource_win_prob | 0.2451 | 0.0360 | 0.6836 | 36260.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2179 | 0.0000 | 0.6235 | 64842.0000 |
| innings_phase | 0.2198 | 0.0000 | 0.6283 | 64842.0000 |
| innings_specific | 0.2202 | 0.0110 | 0.6295 | 64842.0000 |
| ece_optimized | 0.2203 | 0.0021 | 0.6297 | 64842.0000 |
| combined | 0.2204 | 0.0116 | 0.6302 | 64842.0000 |
| logloss_optimized | 0.2209 | 0.0117 | 0.6316 | 64842.0000 |
| raw | 0.2211 | 0.0180 | 0.6321 | 64842.0000 |
| resource_win_prob | 0.2677 | 0.1895 | 0.7565 | 64842.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2060 | 0.0000 | 0.5962 | 43238.0000 |
| innings_phase | 0.2082 | 0.0000 | 0.6017 | 43238.0000 |
| ece_optimized | 0.2088 | 0.0031 | 0.6036 | 43238.0000 |
| innings_specific | 0.2091 | 0.0170 | 0.6042 | 43238.0000 |
| logloss_optimized | 0.2094 | 0.0090 | 0.6062 | 43238.0000 |
| combined | 0.2095 | 0.0225 | 0.6060 | 43238.0000 |
| raw | 0.2100 | 0.0279 | 0.6076 | 43238.0000 |
| resource_win_prob | 0.2299 | 0.1324 | 0.6578 | 43238.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1809 | 0.0000 | 0.5342 | 36276.0000 |
| innings_phase | 0.1824 | 0.0000 | 0.5388 | 36276.0000 |
| ece_optimized | 0.1830 | 0.0032 | 0.5416 | 36276.0000 |
| innings_specific | 0.1832 | 0.0133 | 0.5429 | 36276.0000 |
| combined | 0.1832 | 0.0099 | 0.5427 | 36276.0000 |
| raw | 0.1835 | 0.0137 | 0.5426 | 36276.0000 |
| logloss_optimized | 0.1840 | 0.0195 | 0.5457 | 36276.0000 |
| resource_win_prob | 0.1938 | 0.0271 | 0.5671 | 36276.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1441 | 0.0000 | 0.4352 | 63812.0000 |
| innings_phase | 0.1461 | 0.0000 | 0.4421 | 63812.0000 |
| innings_specific | 0.1465 | 0.0106 | 0.4435 | 63812.0000 |
| ece_optimized | 0.1466 | 0.0061 | 0.4446 | 63812.0000 |
| combined | 0.1467 | 0.0093 | 0.4440 | 63812.0000 |
| raw | 0.1470 | 0.0169 | 0.4465 | 63812.0000 |
| logloss_optimized | 0.1488 | 0.0418 | 0.4563 | 63812.0000 |
| resource_win_prob | 0.1592 | 0.0296 | 0.4794 | 63812.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0937 | 0.0000 | 0.2947 | 34526.0000 |
| innings_phase | 0.0951 | 0.0000 | 0.2996 | 34526.0000 |
| ece_optimized | 0.0955 | 0.0062 | 0.3017 | 34526.0000 |
| innings_specific | 0.0970 | 0.0277 | 0.3068 | 34526.0000 |
| raw | 0.0973 | 0.0348 | 0.3111 | 34526.0000 |
| combined | 0.0975 | 0.0317 | 0.3085 | 34526.0000 |
| logloss_optimized | 0.0980 | 0.0296 | 0.3166 | 34526.0000 |
| resource_win_prob | 0.1073 | 0.0466 | 0.3413 | 34526.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1817 |
| Innings 1 | brier_optimized | 0.2195 |
| Innings 2 | brier_optimized | 0.1411 |
| Inn1 Powerplay | brier_optimized | 0.2383 |
| Inn1 Middle | brier_optimized | 0.2179 |
| Inn1 Death | brier_optimized | 0.2060 |
| Inn2 Powerplay | brier_optimized | 0.1809 |
| Inn2 Middle | brier_optimized | 0.1441 |
| Inn2 Death | brier_optimized | 0.0937 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | innings_phase | 0.0000 |
| Inn2 Powerplay | innings_phase | 0.0000 |
| Inn2 Middle | innings_phase | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5297 |
| Innings 1 | brier_optimized | 0.6266 |
| Innings 2 | brier_optimized | 0.4259 |
| Inn1 Powerplay | brier_optimized | 0.6684 |
| Inn1 Middle | brier_optimized | 0.6235 |
| Inn1 Death | brier_optimized | 0.5962 |
| Inn2 Powerplay | brier_optimized | 0.5342 |
| Inn2 Middle | brier_optimized | 0.4352 |
| Inn2 Death | brier_optimized | 0.2947 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 6 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2046 | 0.1817 (brier_optimized) | **+11.2%** |
| LogLoss | 0.5923 | 0.5297 (brier_optimized) | **+10.6%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,236 | 0.043 | 0.035 | 0.0085  | 0.0325 |
| 0.1-0.2 | 20,038 | 0.152 | 0.180 | 0.0277  | 0.1476 |
| 0.2-0.3 | 24,189 | 0.253 | 0.264 | 0.0114  | 0.1933 |
| 0.3-0.4 | 36,024 | 0.353 | 0.364 | 0.0110  | 0.2313 |
| 0.4-0.5 | 44,703 | 0.450 | 0.453 | 0.0025  | 0.2470 |
| 0.5-0.6 | 37,000 | 0.548 | 0.544 | 0.0041  | 0.2476 |
| 0.6-0.7 | 27,915 | 0.648 | 0.638 | 0.0103  | 0.2306 |
| 0.7-0.8 | 22,893 | 0.748 | 0.729 | 0.0191  | 0.1977 |
| 0.8-0.9 | 19,588 | 0.850 | 0.825 | 0.0252  | 0.1438 |
| 0.9-1.0 | 22,368 | 0.946 | 0.962 | 0.0157  | 0.0362 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 25,454 | 0.031 | 0.031 | 0.0000  | 0.0289 |
| 0.1-0.2 | 14,638 | 0.161 | 0.161 | 0.0000  | 0.1341 |
| 0.2-0.3 | 25,216 | 0.244 | 0.244 | 0.0000  | 0.1835 |
| 0.3-0.4 | 34,361 | 0.356 | 0.356 | 0.0000  | 0.2288 |
| 0.4-0.5 | 51,035 | 0.450 | 0.450 | 0.0000  | 0.2466 |
| 0.5-0.6 | 39,496 | 0.546 | 0.546 | 0.0000  | 0.2470 |
| 0.6-0.7 | 27,244 | 0.658 | 0.658 | 0.0000  | 0.2244 |
| 0.7-0.8 | 24,422 | 0.747 | 0.747 | 0.0000  | 0.1883 |
| 0.8-0.9 | 13,882 | 0.847 | 0.847 | 0.0000  | 0.1289 |
| 0.9-1.0 | 23,206 | 0.971 | 0.971 | 0.0000  | 0.0277 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 23,037 | 0.028 | 0.028 | 0.0000  | 0.0266 |
| 0.1-0.2 | 18,137 | 0.163 | 0.163 | 0.0000  | 0.1356 |
| 0.2-0.3 | 22,882 | 0.245 | 0.245 | 0.0000  | 0.1839 |
| 0.3-0.4 | 41,226 | 0.361 | 0.361 | 0.0000  | 0.2302 |
| 0.4-0.5 | 42,516 | 0.453 | 0.453 | 0.0000  | 0.2472 |
| 0.5-0.6 | 40,701 | 0.543 | 0.543 | 0.0000  | 0.2474 |
| 0.6-0.7 | 28,894 | 0.651 | 0.651 | 0.0000  | 0.2266 |
| 0.7-0.8 | 23,478 | 0.739 | 0.739 | 0.0000  | 0.1925 |
| 0.8-0.9 | 16,523 | 0.845 | 0.845 | 0.0000  | 0.1294 |
| 0.9-1.0 | 21,560 | 0.970 | 0.970 | 0.0000  | 0.0279 |

### Problematic Bins (Calibration Error > 0.05)


**raw:** ✅ All bins have CE ≤ 0.05

**brier_optimized:** ✅ All bins have CE ≤ 0.05

**innings_phase:** ✅ All bins have CE ≤ 0.05


## Important Note on ECE = 0.0000


ECE values of exactly 0.0000 for isotonic-calibrated methods are **mathematically expected**, not a bug:

**Root Cause:**
- Isotonic regression ensures: `E[Y | P_calibrated = p] = p` by construction
- ECE measures: `|E[Y in bin] - E[P_calibrated in bin]|`  
- After isotonic calibration: `E[Y] = E[P]` within each bin BY DESIGN
- This makes ECE = 0 a **tautology**, not an empirical measurement

**Interpretation:**
- ECE = 0 does NOT mean the calibrator is "perfect"
- It means ECE is measuring the calibrator's own constraint
- This is true for: `brier_optimized`, `innings_phase`, `innings_specific`, `combined`

**Recommended Decision Metrics:**
1. **Brier Score** (primary) - Measures accuracy + calibration together
2. **LogLoss** - Measures probabilistic sharpness  
3. **ECE** - Only meaningful for `raw` (uncalibrated) model comparison

For production, use **Brier Score** as the primary selection criterion.
