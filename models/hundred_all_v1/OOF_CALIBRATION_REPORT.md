# OOF Calibration Analysis Report

**Generated:** 2026-07-22 01:33:04
**Samples:** 57,975
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1742 | 0.0001 | 0.5115 |
| innings_phase | 0.1783 | 0.0000 | 0.5237 |
| ece_optimized | 0.1800 | 0.0110 | 0.5299 |
| innings_specific | 0.1802 | 0.0000 | 0.5294 |
| combined | 0.1814 | 0.0000 | 0.5329 |
| logloss_optimized | 0.1836 | 0.0207 | 0.5421 |
| raw | 0.1839 | 0.0344 | 0.5410 |
| resource_win_prob | 0.2064 | 0.1087 | 0.5971 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2045 | 0.0001 | 0.5917 | 30106.0000 |
| innings_phase | 0.2081 | 0.0000 | 0.6010 | 30106.0000 |
| innings_specific | 0.2096 | 0.0000 | 0.6050 | 30106.0000 |
| ece_optimized | 0.2101 | 0.0175 | 0.6062 | 30106.0000 |
| combined | 0.2107 | 0.0201 | 0.6086 | 30106.0000 |
| logloss_optimized | 0.2116 | 0.0252 | 0.6113 | 30106.0000 |
| raw | 0.2133 | 0.0381 | 0.6168 | 30106.0000 |
| resource_win_prob | 0.2574 | 0.1949 | 0.7138 | 30106.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1415 | 0.0002 | 0.4248 | 27869.0000 |
| innings_phase | 0.1462 | 0.0000 | 0.4403 | 27869.0000 |
| ece_optimized | 0.1476 | 0.0059 | 0.4474 | 27869.0000 |
| innings_specific | 0.1484 | 0.0000 | 0.4477 | 27869.0000 |
| combined | 0.1498 | 0.0217 | 0.4512 | 27869.0000 |
| resource_win_prob | 0.1513 | 0.0743 | 0.4710 | 27869.0000 |
| raw | 0.1521 | 0.0414 | 0.4590 | 27869.0000 |
| logloss_optimized | 0.1533 | 0.0502 | 0.4673 | 27869.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2320 | 0.0004 | 0.6532 | 7717.0000 |
| innings_phase | 0.2356 | 0.0000 | 0.6620 | 7717.0000 |
| combined | 0.2381 | 0.0223 | 0.6684 | 7717.0000 |
| innings_specific | 0.2382 | 0.0281 | 0.6685 | 7717.0000 |
| logloss_optimized | 0.2382 | 0.0222 | 0.6689 | 7717.0000 |
| ece_optimized | 0.2388 | 0.0299 | 0.6691 | 7717.0000 |
| raw | 0.2415 | 0.0490 | 0.6769 | 7717.0000 |
| resource_win_prob | 0.2576 | 0.1316 | 0.7091 | 7717.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2024 | 0.0000 | 0.5882 | 13546.0000 |
| innings_phase | 0.2065 | 0.0000 | 0.5987 | 13546.0000 |
| innings_specific | 0.2071 | 0.0106 | 0.6006 | 13546.0000 |
| ece_optimized | 0.2080 | 0.0155 | 0.6028 | 13546.0000 |
| combined | 0.2090 | 0.0283 | 0.6057 | 13546.0000 |
| logloss_optimized | 0.2106 | 0.0415 | 0.6102 | 13546.0000 |
| raw | 0.2122 | 0.0478 | 0.6164 | 13546.0000 |
| resource_win_prob | 0.2564 | 0.2050 | 0.7144 | 13546.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1837 | 0.0000 | 0.5435 | 8843.0000 |
| innings_phase | 0.1864 | 0.0000 | 0.5510 | 8843.0000 |
| ece_optimized | 0.1881 | 0.0106 | 0.5565 | 8843.0000 |
| innings_specific | 0.1884 | 0.0237 | 0.5565 | 8843.0000 |
| combined | 0.1896 | 0.0387 | 0.5608 | 8843.0000 |
| logloss_optimized | 0.1900 | 0.0288 | 0.5629 | 8843.0000 |
| raw | 0.1904 | 0.0367 | 0.5650 | 8843.0000 |
| resource_win_prob | 0.2586 | 0.2395 | 0.7169 | 8843.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1728 | 0.0007 | 0.5092 | 7723.0000 |
| innings_phase | 0.1760 | 0.0000 | 0.5198 | 7723.0000 |
| ece_optimized | 0.1778 | 0.0074 | 0.5269 | 7723.0000 |
| innings_specific | 0.1789 | 0.0327 | 0.5300 | 7723.0000 |
| combined | 0.1821 | 0.0537 | 0.5379 | 7723.0000 |
| logloss_optimized | 0.1841 | 0.0600 | 0.5461 | 7723.0000 |
| raw | 0.1853 | 0.0657 | 0.5496 | 7723.0000 |
| resource_win_prob | 0.2037 | 0.1523 | 0.5949 | 7723.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1395 | 0.0000 | 0.4182 | 13387.0000 |
| resource_win_prob | 0.1425 | 0.0609 | 0.4518 | 13387.0000 |
| innings_phase | 0.1451 | 0.0000 | 0.4357 | 13387.0000 |
| innings_specific | 0.1462 | 0.0115 | 0.4387 | 13387.0000 |
| ece_optimized | 0.1464 | 0.0060 | 0.4430 | 13387.0000 |
| combined | 0.1477 | 0.0300 | 0.4425 | 13387.0000 |
| raw | 0.1508 | 0.0500 | 0.4527 | 13387.0000 |
| logloss_optimized | 0.1531 | 0.0598 | 0.4664 | 13387.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| resource_win_prob | 0.1089 | 0.0625 | 0.3675 | 6759.0000 |
| brier_optimized | 0.1097 | 0.0000 | 0.3414 | 6759.0000 |
| innings_phase | 0.1141 | 0.0000 | 0.3587 | 6759.0000 |
| ece_optimized | 0.1154 | 0.0133 | 0.3653 | 6759.0000 |
| raw | 0.1168 | 0.0243 | 0.3680 | 6759.0000 |
| combined | 0.1168 | 0.0311 | 0.3693 | 6759.0000 |
| innings_specific | 0.1179 | 0.0326 | 0.3712 | 6759.0000 |
| logloss_optimized | 0.1185 | 0.0388 | 0.3790 | 6759.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1742 |
| Innings 1 | brier_optimized | 0.2045 |
| Innings 2 | brier_optimized | 0.1415 |
| Inn1 Powerplay | brier_optimized | 0.2320 |
| Inn1 Middle | brier_optimized | 0.2024 |
| Inn1 Death | brier_optimized | 0.1837 |
| Inn2 Powerplay | brier_optimized | 0.1728 |
| Inn2 Middle | brier_optimized | 0.1395 |
| Inn2 Death | resource_win_prob | 0.1089 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | innings_specific | 0.0000 |
| Innings 1 | innings_phase | 0.0000 |
| Innings 2 | innings_specific | 0.0000 |
| Inn1 Powerplay | innings_phase | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | innings_phase | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5115 |
| Innings 1 | brier_optimized | 0.5917 |
| Innings 2 | brier_optimized | 0.4248 |
| Inn1 Powerplay | brier_optimized | 0.6532 |
| Inn1 Middle | brier_optimized | 0.5882 |
| Inn1 Death | brier_optimized | 0.5435 |
| Inn2 Powerplay | brier_optimized | 0.5092 |
| Inn2 Middle | brier_optimized | 0.4182 |
| Inn2 Death | brier_optimized | 0.3414 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 8 segments
- **ECE**: `brier_optimized` wins in 4 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2064 | 0.1742 (brier_optimized) | **+15.6%** |
| LogLoss | 0.5971 | 0.5115 (brier_optimized) | **+14.3%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 6,749 | 0.046 | 0.076 | 0.0302  | 0.0685 |
| 0.1-0.2 | 5,471 | 0.148 | 0.149 | 0.0004  | 0.1261 |
| 0.2-0.3 | 5,574 | 0.251 | 0.327 | 0.0756 ⚠️ | 0.2243 |
| 0.3-0.4 | 6,345 | 0.352 | 0.414 | 0.0628 ⚠️ | 0.2464 |
| 0.4-0.5 | 6,903 | 0.448 | 0.462 | 0.0139  | 0.2478 |
| 0.5-0.6 | 5,924 | 0.550 | 0.550 | 0.0004  | 0.2471 |
| 0.6-0.7 | 5,190 | 0.650 | 0.598 | 0.0524 ⚠️ | 0.2419 |
| 0.7-0.8 | 5,074 | 0.748 | 0.713 | 0.0358  | 0.2063 |
| 0.8-0.9 | 5,096 | 0.850 | 0.791 | 0.0591 ⚠️ | 0.1686 |
| 0.9-1.0 | 5,649 | 0.951 | 0.930 | 0.0207  | 0.0635 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 6,154 | 0.036 | 0.036 | 0.0001  | 0.0334 |
| 0.1-0.2 | 4,677 | 0.143 | 0.143 | 0.0001  | 0.1215 |
| 0.2-0.3 | 4,049 | 0.241 | 0.241 | 0.0001  | 0.1821 |
| 0.3-0.4 | 4,559 | 0.361 | 0.361 | 0.0000  | 0.2300 |
| 0.4-0.5 | 13,452 | 0.451 | 0.451 | 0.0000  | 0.2466 |
| 0.5-0.6 | 4,888 | 0.543 | 0.544 | 0.0003  | 0.2474 |
| 0.6-0.7 | 5,741 | 0.649 | 0.649 | 0.0001  | 0.2269 |
| 0.7-0.8 | 5,953 | 0.752 | 0.752 | 0.0001  | 0.1860 |
| 0.8-0.9 | 3,846 | 0.845 | 0.845 | 0.0002  | 0.1306 |
| 0.9-1.0 | 4,656 | 0.977 | 0.977 | 0.0000  | 0.0216 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 5,868 | 0.046 | 0.046 | 0.0000  | 0.0420 |
| 0.1-0.2 | 4,782 | 0.141 | 0.141 | 0.0000  | 0.1207 |
| 0.2-0.3 | 3,340 | 0.239 | 0.239 | 0.0000  | 0.1809 |
| 0.3-0.4 | 4,424 | 0.352 | 0.352 | 0.0000  | 0.2273 |
| 0.4-0.5 | 14,312 | 0.444 | 0.444 | 0.0000  | 0.2459 |
| 0.5-0.6 | 5,109 | 0.555 | 0.555 | 0.0000  | 0.2464 |
| 0.6-0.7 | 6,889 | 0.647 | 0.647 | 0.0000  | 0.2273 |
| 0.7-0.8 | 5,296 | 0.761 | 0.761 | 0.0000  | 0.1815 |
| 0.8-0.9 | 3,594 | 0.849 | 0.849 | 0.0000  | 0.1272 |
| 0.9-1.0 | 4,361 | 0.966 | 0.966 | 0.0000  | 0.0323 |

### Problematic Bins (Calibration Error > 0.05)


**raw:**
- Bin 0.2-0.3: CE=0.0756 (under-predicting)
- Bin 0.3-0.4: CE=0.0628 (under-predicting)
- Bin 0.6-0.7: CE=0.0524 (over-predicting)
- Bin 0.8-0.9: CE=0.0591 (over-predicting)

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
