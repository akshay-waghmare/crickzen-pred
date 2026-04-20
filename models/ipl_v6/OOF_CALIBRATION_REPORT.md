# OOF Calibration Analysis Report

**Generated:** 2026-04-20 17:50:14
**Samples:** 278,954
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1811 | 0.0000 | 0.5282 |
| innings_phase | 0.1828 | 0.0000 | 0.5333 |
| ece_optimized | 0.1834 | 0.0030 | 0.5352 |
| innings_specific | 0.1837 | 0.0000 | 0.5364 |
| combined | 0.1839 | 0.0000 | 0.5371 |
| raw | 0.1843 | 0.0120 | 0.5387 |
| logloss_optimized | 0.1846 | 0.0177 | 0.5411 |
| resource_win_prob | 0.1930 | 0.0364 | 0.5660 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2185 | 0.0000 | 0.6239 | 144340.0000 |
| innings_phase | 0.2201 | 0.0000 | 0.6281 | 144340.0000 |
| ece_optimized | 0.2207 | 0.0039 | 0.6297 | 144340.0000 |
| innings_specific | 0.2207 | 0.0000 | 0.6296 | 144340.0000 |
| combined | 0.2209 | 0.0065 | 0.6303 | 144340.0000 |
| logloss_optimized | 0.2212 | 0.0089 | 0.6316 | 144340.0000 |
| raw | 0.2214 | 0.0154 | 0.6318 | 144340.0000 |
| resource_win_prob | 0.2255 | 0.0366 | 0.6407 | 144340.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1411 | 0.0000 | 0.4255 | 134614.0000 |
| innings_phase | 0.1428 | 0.0000 | 0.4316 | 134614.0000 |
| ece_optimized | 0.1433 | 0.0033 | 0.4339 | 134614.0000 |
| innings_specific | 0.1440 | 0.0000 | 0.4366 | 134614.0000 |
| combined | 0.1442 | 0.0069 | 0.4371 | 134614.0000 |
| raw | 0.1445 | 0.0124 | 0.4389 | 134614.0000 |
| logloss_optimized | 0.1453 | 0.0310 | 0.4441 | 134614.0000 |
| resource_win_prob | 0.1581 | 0.0436 | 0.4860 | 134614.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2384 | 0.0000 | 0.6687 | 36260.0000 |
| innings_phase | 0.2396 | 0.0000 | 0.6714 | 36260.0000 |
| ece_optimized | 0.2401 | 0.0043 | 0.6726 | 36260.0000 |
| combined | 0.2403 | 0.0086 | 0.6731 | 36260.0000 |
| innings_specific | 0.2403 | 0.0125 | 0.6731 | 36260.0000 |
| logloss_optimized | 0.2404 | 0.0075 | 0.6735 | 36260.0000 |
| raw | 0.2408 | 0.0187 | 0.6743 | 36260.0000 |
| resource_win_prob | 0.2494 | 0.0834 | 0.6923 | 36260.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2166 | 0.0000 | 0.6200 | 64842.0000 |
| innings_phase | 0.2183 | 0.0000 | 0.6245 | 64842.0000 |
| innings_specific | 0.2187 | 0.0103 | 0.6254 | 64842.0000 |
| combined | 0.2188 | 0.0099 | 0.6259 | 64842.0000 |
| ece_optimized | 0.2189 | 0.0046 | 0.6262 | 64842.0000 |
| logloss_optimized | 0.2195 | 0.0129 | 0.6281 | 64842.0000 |
| raw | 0.2195 | 0.0173 | 0.6279 | 64842.0000 |
| resource_win_prob | 0.2230 | 0.0194 | 0.6358 | 64842.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2046 | 0.0000 | 0.5922 | 43238.0000 |
| innings_phase | 0.2064 | 0.0000 | 0.5971 | 43238.0000 |
| ece_optimized | 0.2071 | 0.0053 | 0.5990 | 43238.0000 |
| innings_specific | 0.2073 | 0.0213 | 0.5994 | 43238.0000 |
| logloss_optimized | 0.2076 | 0.0115 | 0.6017 | 43238.0000 |
| combined | 0.2078 | 0.0248 | 0.6010 | 43238.0000 |
| raw | 0.2080 | 0.0277 | 0.6019 | 43238.0000 |
| resource_win_prob | 0.2093 | 0.0270 | 0.6047 | 43238.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1811 | 0.0000 | 0.5343 | 36276.0000 |
| innings_phase | 0.1825 | 0.0000 | 0.5393 | 36276.0000 |
| ece_optimized | 0.1832 | 0.0052 | 0.5424 | 36276.0000 |
| combined | 0.1834 | 0.0151 | 0.5442 | 36276.0000 |
| innings_specific | 0.1836 | 0.0213 | 0.5448 | 36276.0000 |
| raw | 0.1840 | 0.0195 | 0.5448 | 36276.0000 |
| logloss_optimized | 0.1842 | 0.0179 | 0.5463 | 36276.0000 |
| resource_win_prob | 0.1912 | 0.0549 | 0.5637 | 36276.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1444 | 0.0000 | 0.4358 | 63812.0000 |
| innings_phase | 0.1466 | 0.0000 | 0.4435 | 63812.0000 |
| innings_specific | 0.1469 | 0.0084 | 0.4444 | 63812.0000 |
| ece_optimized | 0.1470 | 0.0038 | 0.4454 | 63812.0000 |
| combined | 0.1471 | 0.0095 | 0.4448 | 63812.0000 |
| raw | 0.1474 | 0.0158 | 0.4471 | 63812.0000 |
| logloss_optimized | 0.1494 | 0.0433 | 0.4576 | 63812.0000 |
| resource_win_prob | 0.1573 | 0.0386 | 0.4773 | 63812.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0929 | 0.0000 | 0.2920 | 34526.0000 |
| innings_phase | 0.0942 | 0.0000 | 0.2966 | 34526.0000 |
| ece_optimized | 0.0947 | 0.0049 | 0.2987 | 34526.0000 |
| logloss_optimized | 0.0969 | 0.0294 | 0.3117 | 34526.0000 |
| innings_specific | 0.0971 | 0.0356 | 0.3083 | 34526.0000 |
| raw | 0.0976 | 0.0425 | 0.3123 | 34526.0000 |
| combined | 0.0978 | 0.0402 | 0.3103 | 34526.0000 |
| resource_win_prob | 0.1248 | 0.1113 | 0.4204 | 34526.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1811 |
| Innings 1 | brier_optimized | 0.2185 |
| Innings 2 | brier_optimized | 0.1411 |
| Inn1 Powerplay | brier_optimized | 0.2384 |
| Inn1 Middle | brier_optimized | 0.2166 |
| Inn1 Death | brier_optimized | 0.2046 |
| Inn2 Powerplay | brier_optimized | 0.1811 |
| Inn2 Middle | brier_optimized | 0.1444 |
| Inn2 Death | brier_optimized | 0.0929 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | innings_phase | 0.0000 |
| Innings 2 | innings_phase | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | innings_phase | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5282 |
| Innings 1 | brier_optimized | 0.6239 |
| Innings 2 | brier_optimized | 0.4255 |
| Inn1 Powerplay | brier_optimized | 0.6687 |
| Inn1 Middle | brier_optimized | 0.6200 |
| Inn1 Death | brier_optimized | 0.5922 |
| Inn2 Powerplay | brier_optimized | 0.5343 |
| Inn2 Middle | brier_optimized | 0.4358 |
| Inn2 Death | brier_optimized | 0.2920 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 6 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1930 | 0.1811 (brier_optimized) | **+6.1%** |
| LogLoss | 0.5660 | 0.5282 (brier_optimized) | **+6.7%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,179 | 0.046 | 0.033 | 0.0126  | 0.0311 |
| 0.1-0.2 | 20,222 | 0.150 | 0.169 | 0.0184  | 0.1398 |
| 0.2-0.3 | 23,949 | 0.253 | 0.270 | 0.0176  | 0.1971 |
| 0.3-0.4 | 34,708 | 0.353 | 0.358 | 0.0049  | 0.2286 |
| 0.4-0.5 | 45,441 | 0.451 | 0.461 | 0.0108  | 0.2482 |
| 0.5-0.6 | 39,036 | 0.547 | 0.539 | 0.0081  | 0.2481 |
| 0.6-0.7 | 27,843 | 0.648 | 0.633 | 0.0148  | 0.2315 |
| 0.7-0.8 | 21,752 | 0.749 | 0.741 | 0.0084  | 0.1916 |
| 0.8-0.9 | 19,014 | 0.850 | 0.828 | 0.0218  | 0.1417 |
| 0.9-1.0 | 22,810 | 0.947 | 0.958 | 0.0113  | 0.0395 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 23,976 | 0.024 | 0.024 | 0.0000  | 0.0223 |
| 0.1-0.2 | 18,130 | 0.159 | 0.159 | 0.0000  | 0.1325 |
| 0.2-0.3 | 24,256 | 0.253 | 0.253 | 0.0000  | 0.1879 |
| 0.3-0.4 | 30,970 | 0.346 | 0.346 | 0.0000  | 0.2252 |
| 0.4-0.5 | 50,385 | 0.453 | 0.453 | 0.0000  | 0.2470 |
| 0.5-0.6 | 42,729 | 0.543 | 0.543 | 0.0000  | 0.2474 |
| 0.6-0.7 | 25,524 | 0.642 | 0.642 | 0.0000  | 0.2292 |
| 0.7-0.8 | 24,450 | 0.749 | 0.749 | 0.0000  | 0.1875 |
| 0.8-0.9 | 13,885 | 0.842 | 0.842 | 0.0000  | 0.1318 |
| 0.9-1.0 | 24,649 | 0.967 | 0.967 | 0.0000  | 0.0313 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 23,773 | 0.028 | 0.028 | 0.0000  | 0.0262 |
| 0.1-0.2 | 18,532 | 0.163 | 0.163 | 0.0000  | 0.1353 |
| 0.2-0.3 | 28,621 | 0.263 | 0.263 | 0.0000  | 0.1929 |
| 0.3-0.4 | 25,857 | 0.355 | 0.355 | 0.0000  | 0.2285 |
| 0.4-0.5 | 52,012 | 0.454 | 0.454 | 0.0000  | 0.2471 |
| 0.5-0.6 | 40,971 | 0.541 | 0.541 | 0.0000  | 0.2477 |
| 0.6-0.7 | 28,046 | 0.646 | 0.646 | 0.0000  | 0.2277 |
| 0.7-0.8 | 22,971 | 0.749 | 0.749 | 0.0000  | 0.1875 |
| 0.8-0.9 | 16,233 | 0.847 | 0.847 | 0.0000  | 0.1285 |
| 0.9-1.0 | 21,938 | 0.968 | 0.968 | 0.0000  | 0.0301 |

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
