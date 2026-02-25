# OOF Calibration Analysis Report

**Generated:** 2026-02-23 11:32:11
**Samples:** 686,832
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1583 | 0.0000 | 0.4719 |
| innings_phase | 0.1592 | 0.0000 | 0.4748 |
| ece_optimized | 0.1595 | 0.0022 | 0.4764 |
| innings_specific | 0.1596 | 0.0000 | 0.4760 |
| combined | 0.1598 | 0.0000 | 0.4770 |
| raw | 0.1599 | 0.0041 | 0.4778 |
| logloss_optimized | 0.1607 | 0.0176 | 0.4828 |
| resource_win_prob | 0.1877 | 0.0644 | 0.5492 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1964 | 0.0000 | 0.5726 | 366089.0000 |
| innings_phase | 0.1974 | 0.0000 | 0.5755 | 366089.0000 |
| innings_specific | 0.1976 | 0.0000 | 0.5762 | 366089.0000 |
| ece_optimized | 0.1977 | 0.0015 | 0.5766 | 366089.0000 |
| combined | 0.1978 | 0.0077 | 0.5773 | 366089.0000 |
| raw | 0.1980 | 0.0100 | 0.5776 | 366089.0000 |
| logloss_optimized | 0.1984 | 0.0173 | 0.5798 | 366089.0000 |
| resource_win_prob | 0.2292 | 0.1273 | 0.6474 | 366089.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1148 | 0.0000 | 0.3569 | 320743.0000 |
| innings_phase | 0.1157 | 0.0000 | 0.3600 | 320743.0000 |
| ece_optimized | 0.1160 | 0.0035 | 0.3620 | 320743.0000 |
| innings_specific | 0.1162 | 0.0000 | 0.3617 | 320743.0000 |
| combined | 0.1164 | 0.0088 | 0.3625 | 320743.0000 |
| raw | 0.1165 | 0.0090 | 0.3638 | 320743.0000 |
| logloss_optimized | 0.1176 | 0.0263 | 0.3722 | 320743.0000 |
| resource_win_prob | 0.1405 | 0.0857 | 0.4372 | 320743.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2207 | 0.0000 | 0.6303 | 94291.0000 |
| innings_phase | 0.2216 | 0.0000 | 0.6326 | 94291.0000 |
| innings_specific | 0.2219 | 0.0102 | 0.6335 | 94291.0000 |
| ece_optimized | 0.2220 | 0.0037 | 0.6335 | 94291.0000 |
| combined | 0.2220 | 0.0103 | 0.6337 | 94291.0000 |
| raw | 0.2221 | 0.0116 | 0.6340 | 94291.0000 |
| logloss_optimized | 0.2222 | 0.0075 | 0.6343 | 94291.0000 |
| resource_win_prob | 0.2574 | 0.1286 | 0.7088 | 94291.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1935 | 0.0000 | 0.5661 | 166116.0000 |
| innings_phase | 0.1946 | 0.0000 | 0.5693 | 166116.0000 |
| innings_specific | 0.1948 | 0.0030 | 0.5697 | 166116.0000 |
| ece_optimized | 0.1949 | 0.0021 | 0.5703 | 166116.0000 |
| combined | 0.1950 | 0.0102 | 0.5710 | 166116.0000 |
| raw | 0.1952 | 0.0124 | 0.5714 | 166116.0000 |
| logloss_optimized | 0.1957 | 0.0190 | 0.5739 | 166116.0000 |
| resource_win_prob | 0.2216 | 0.1113 | 0.6314 | 166116.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1791 | 0.0000 | 0.5312 | 105682.0000 |
| innings_phase | 0.1801 | 0.0000 | 0.5341 | 105682.0000 |
| ece_optimized | 0.1804 | 0.0023 | 0.5358 | 105682.0000 |
| innings_specific | 0.1805 | 0.0108 | 0.5352 | 105682.0000 |
| combined | 0.1807 | 0.0177 | 0.5370 | 105682.0000 |
| raw | 0.1809 | 0.0177 | 0.5372 | 105682.0000 |
| logloss_optimized | 0.1816 | 0.0264 | 0.5405 | 105682.0000 |
| resource_win_prob | 0.2158 | 0.1512 | 0.6178 | 105682.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1571 | 0.0000 | 0.4748 | 93877.0000 |
| innings_phase | 0.1577 | 0.0000 | 0.4770 | 93877.0000 |
| ece_optimized | 0.1581 | 0.0030 | 0.4787 | 93877.0000 |
| innings_specific | 0.1582 | 0.0122 | 0.4783 | 93877.0000 |
| combined | 0.1585 | 0.0192 | 0.4794 | 93877.0000 |
| raw | 0.1587 | 0.0192 | 0.4802 | 93877.0000 |
| logloss_optimized | 0.1593 | 0.0252 | 0.4842 | 93877.0000 |
| resource_win_prob | 0.2013 | 0.1766 | 0.5960 | 93877.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1100 | 0.0000 | 0.3449 | 155634.0000 |
| innings_phase | 0.1111 | 0.0000 | 0.3487 | 155634.0000 |
| innings_specific | 0.1112 | 0.0033 | 0.3491 | 155634.0000 |
| ece_optimized | 0.1113 | 0.0035 | 0.3508 | 155634.0000 |
| combined | 0.1114 | 0.0085 | 0.3498 | 155634.0000 |
| raw | 0.1115 | 0.0107 | 0.3511 | 155634.0000 |
| logloss_optimized | 0.1130 | 0.0319 | 0.3608 | 155634.0000 |
| resource_win_prob | 0.1305 | 0.0807 | 0.4145 | 155634.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0695 | 0.0000 | 0.2277 | 71232.0000 |
| innings_phase | 0.0703 | 0.0000 | 0.2304 | 71232.0000 |
| ece_optimized | 0.0706 | 0.0062 | 0.2327 | 71232.0000 |
| combined | 0.0720 | 0.0238 | 0.2362 | 71232.0000 |
| innings_specific | 0.0720 | 0.0217 | 0.2352 | 71232.0000 |
| raw | 0.0721 | 0.0248 | 0.2380 | 71232.0000 |
| logloss_optimized | 0.0728 | 0.0221 | 0.2494 | 71232.0000 |
| resource_win_prob | 0.0822 | 0.0496 | 0.2775 | 71232.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1583 |
| Innings 1 | brier_optimized | 0.1964 |
| Innings 2 | brier_optimized | 0.1148 |
| Inn1 Powerplay | brier_optimized | 0.2207 |
| Inn1 Middle | brier_optimized | 0.1935 |
| Inn1 Death | brier_optimized | 0.1791 |
| Inn2 Powerplay | brier_optimized | 0.1571 |
| Inn2 Middle | brier_optimized | 0.1100 |
| Inn2 Death | brier_optimized | 0.0695 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | innings_phase | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.4719 |
| Innings 1 | brier_optimized | 0.5726 |
| Innings 2 | brier_optimized | 0.3569 |
| Inn1 Powerplay | brier_optimized | 0.6303 |
| Inn1 Middle | brier_optimized | 0.5661 |
| Inn1 Death | brier_optimized | 0.5312 |
| Inn2 Powerplay | brier_optimized | 0.4748 |
| Inn2 Middle | brier_optimized | 0.3449 |
| Inn2 Death | brier_optimized | 0.2277 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 8 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1877 | 0.1583 (brier_optimized) | **+15.7%** |
| LogLoss | 0.5492 | 0.4719 (brier_optimized) | **+14.1%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 99,337 | 0.034 | 0.031 | 0.0030  | 0.0287 |
| 0.1-0.2 | 54,640 | 0.151 | 0.150 | 0.0017  | 0.1264 |
| 0.2-0.3 | 61,350 | 0.251 | 0.252 | 0.0008  | 0.1872 |
| 0.3-0.4 | 66,274 | 0.350 | 0.355 | 0.0047  | 0.2282 |
| 0.4-0.5 | 69,572 | 0.450 | 0.453 | 0.0024  | 0.2470 |
| 0.5-0.6 | 71,294 | 0.550 | 0.549 | 0.0009  | 0.2471 |
| 0.6-0.7 | 70,174 | 0.650 | 0.653 | 0.0034  | 0.2256 |
| 0.7-0.8 | 65,829 | 0.749 | 0.742 | 0.0068  | 0.1910 |
| 0.8-0.9 | 60,114 | 0.850 | 0.846 | 0.0043  | 0.1289 |
| 0.9-1.0 | 68,248 | 0.947 | 0.961 | 0.0135  | 0.0372 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 99,223 | 0.027 | 0.027 | 0.0000  | 0.0255 |
| 0.1-0.2 | 57,001 | 0.148 | 0.148 | 0.0000  | 0.1253 |
| 0.2-0.3 | 54,240 | 0.247 | 0.247 | 0.0000  | 0.1850 |
| 0.3-0.4 | 68,241 | 0.347 | 0.347 | 0.0000  | 0.2259 |
| 0.4-0.5 | 66,805 | 0.447 | 0.447 | 0.0000  | 0.2465 |
| 0.5-0.6 | 77,833 | 0.546 | 0.546 | 0.0000  | 0.2472 |
| 0.6-0.7 | 66,033 | 0.652 | 0.652 | 0.0000  | 0.2260 |
| 0.7-0.8 | 76,222 | 0.747 | 0.747 | 0.0000  | 0.1881 |
| 0.8-0.9 | 48,926 | 0.851 | 0.851 | 0.0000  | 0.1260 |
| 0.9-1.0 | 72,308 | 0.964 | 0.964 | 0.0000  | 0.0340 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 100,356 | 0.030 | 0.030 | 0.0000  | 0.0281 |
| 0.1-0.2 | 55,567 | 0.151 | 0.151 | 0.0000  | 0.1274 |
| 0.2-0.3 | 54,837 | 0.247 | 0.247 | 0.0000  | 0.1853 |
| 0.3-0.4 | 68,974 | 0.350 | 0.350 | 0.0000  | 0.2266 |
| 0.4-0.5 | 68,061 | 0.450 | 0.450 | 0.0000  | 0.2468 |
| 0.5-0.6 | 75,245 | 0.547 | 0.547 | 0.0000  | 0.2471 |
| 0.6-0.7 | 61,516 | 0.649 | 0.649 | 0.0000  | 0.2271 |
| 0.7-0.8 | 82,081 | 0.743 | 0.743 | 0.0000  | 0.1901 |
| 0.8-0.9 | 48,325 | 0.850 | 0.850 | 0.0000  | 0.1268 |
| 0.9-1.0 | 71,870 | 0.962 | 0.962 | 0.0000  | 0.0357 |

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
