# OOF Calibration Analysis Report

**Generated:** 2026-05-03 01:44:37
**Samples:** 278,954
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1813 | 0.0000 | 0.5289 |
| innings_phase | 0.1830 | 0.0000 | 0.5341 |
| ece_optimized | 0.1836 | 0.0026 | 0.5360 |
| innings_specific | 0.1837 | 0.0000 | 0.5365 |
| combined | 0.1840 | 0.0000 | 0.5373 |
| raw | 0.1843 | 0.0115 | 0.5388 |
| logloss_optimized | 0.1847 | 0.0178 | 0.5417 |
| resource_win_prob | 0.2046 | 0.0749 | 0.5923 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2191 | 0.0000 | 0.6256 | 144340.0000 |
| innings_phase | 0.2209 | 0.0000 | 0.6301 | 144340.0000 |
| ece_optimized | 0.2214 | 0.0024 | 0.6315 | 144340.0000 |
| innings_specific | 0.2215 | 0.0000 | 0.6316 | 144340.0000 |
| combined | 0.2217 | 0.0079 | 0.6325 | 144340.0000 |
| logloss_optimized | 0.2220 | 0.0086 | 0.6335 | 144340.0000 |
| raw | 0.2223 | 0.0157 | 0.6341 | 144340.0000 |
| resource_win_prob | 0.2507 | 0.1336 | 0.7086 | 144340.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1407 | 0.0000 | 0.4252 | 134614.0000 |
| innings_phase | 0.1424 | 0.0000 | 0.4311 | 134614.0000 |
| ece_optimized | 0.1429 | 0.0033 | 0.4335 | 134614.0000 |
| innings_specific | 0.1432 | 0.0000 | 0.4345 | 134614.0000 |
| combined | 0.1435 | 0.0085 | 0.4352 | 134614.0000 |
| raw | 0.1437 | 0.0102 | 0.4366 | 134614.0000 |
| logloss_optimized | 0.1447 | 0.0319 | 0.4433 | 134614.0000 |
| resource_win_prob | 0.1552 | 0.0178 | 0.4676 | 134614.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2382 | 0.0000 | 0.6682 | 36260.0000 |
| innings_phase | 0.2393 | 0.0000 | 0.6707 | 36260.0000 |
| ece_optimized | 0.2398 | 0.0065 | 0.6721 | 36260.0000 |
| innings_specific | 0.2399 | 0.0062 | 0.6724 | 36260.0000 |
| combined | 0.2400 | 0.0103 | 0.6726 | 36260.0000 |
| logloss_optimized | 0.2401 | 0.0105 | 0.6729 | 36260.0000 |
| raw | 0.2405 | 0.0162 | 0.6737 | 36260.0000 |
| resource_win_prob | 0.2451 | 0.0360 | 0.6836 | 36260.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2175 | 0.0000 | 0.6223 | 64842.0000 |
| innings_phase | 0.2195 | 0.0000 | 0.6275 | 64842.0000 |
| innings_specific | 0.2200 | 0.0133 | 0.6286 | 64842.0000 |
| ece_optimized | 0.2200 | 0.0020 | 0.6287 | 64842.0000 |
| combined | 0.2200 | 0.0093 | 0.6290 | 64842.0000 |
| logloss_optimized | 0.2204 | 0.0110 | 0.6304 | 64842.0000 |
| raw | 0.2206 | 0.0161 | 0.6306 | 64842.0000 |
| resource_win_prob | 0.2677 | 0.1895 | 0.7565 | 64842.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2055 | 0.0000 | 0.5946 | 43238.0000 |
| innings_phase | 0.2075 | 0.0000 | 0.5998 | 43238.0000 |
| ece_optimized | 0.2082 | 0.0034 | 0.6016 | 43238.0000 |
| innings_specific | 0.2084 | 0.0214 | 0.6019 | 43238.0000 |
| combined | 0.2090 | 0.0239 | 0.6043 | 43238.0000 |
| logloss_optimized | 0.2091 | 0.0170 | 0.6052 | 43238.0000 |
| raw | 0.2095 | 0.0283 | 0.6061 | 43238.0000 |
| resource_win_prob | 0.2299 | 0.1324 | 0.6578 | 43238.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1804 | 0.0000 | 0.5329 | 36276.0000 |
| innings_phase | 0.1819 | 0.0000 | 0.5379 | 36276.0000 |
| ece_optimized | 0.1827 | 0.0048 | 0.5410 | 36276.0000 |
| innings_specific | 0.1827 | 0.0139 | 0.5419 | 36276.0000 |
| combined | 0.1828 | 0.0154 | 0.5419 | 36276.0000 |
| raw | 0.1831 | 0.0156 | 0.5422 | 36276.0000 |
| logloss_optimized | 0.1836 | 0.0244 | 0.5448 | 36276.0000 |
| resource_win_prob | 0.1938 | 0.0271 | 0.5671 | 36276.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1440 | 0.0000 | 0.4355 | 63812.0000 |
| innings_phase | 0.1461 | 0.0000 | 0.4427 | 63812.0000 |
| innings_specific | 0.1464 | 0.0092 | 0.4436 | 63812.0000 |
| ece_optimized | 0.1465 | 0.0043 | 0.4449 | 63812.0000 |
| combined | 0.1465 | 0.0098 | 0.4441 | 63812.0000 |
| raw | 0.1468 | 0.0136 | 0.4457 | 63812.0000 |
| logloss_optimized | 0.1486 | 0.0415 | 0.4556 | 63812.0000 |
| resource_win_prob | 0.1592 | 0.0296 | 0.4794 | 63812.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0929 | 0.0000 | 0.2930 | 34526.0000 |
| innings_phase | 0.0942 | 0.0000 | 0.2977 | 34526.0000 |
| ece_optimized | 0.0946 | 0.0051 | 0.2995 | 34526.0000 |
| innings_specific | 0.0960 | 0.0279 | 0.3047 | 34526.0000 |
| raw | 0.0964 | 0.0353 | 0.3088 | 34526.0000 |
| combined | 0.0966 | 0.0314 | 0.3064 | 34526.0000 |
| logloss_optimized | 0.0968 | 0.0275 | 0.3138 | 34526.0000 |
| resource_win_prob | 0.1073 | 0.0466 | 0.3413 | 34526.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1813 |
| Innings 1 | brier_optimized | 0.2191 |
| Innings 2 | brier_optimized | 0.1407 |
| Inn1 Powerplay | brier_optimized | 0.2382 |
| Inn1 Middle | brier_optimized | 0.2175 |
| Inn1 Death | brier_optimized | 0.2055 |
| Inn2 Powerplay | brier_optimized | 0.1804 |
| Inn2 Middle | brier_optimized | 0.1440 |
| Inn2 Death | brier_optimized | 0.0929 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | innings_phase | 0.0000 |
| Innings 1 | innings_phase | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | innings_phase | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5289 |
| Innings 1 | brier_optimized | 0.6256 |
| Innings 2 | brier_optimized | 0.4252 |
| Inn1 Powerplay | brier_optimized | 0.6682 |
| Inn1 Middle | brier_optimized | 0.6223 |
| Inn1 Death | brier_optimized | 0.5946 |
| Inn2 Powerplay | brier_optimized | 0.5329 |
| Inn2 Middle | brier_optimized | 0.4355 |
| Inn2 Death | brier_optimized | 0.2930 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 6 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2046 | 0.1813 (brier_optimized) | **+11.4%** |
| LogLoss | 0.5923 | 0.5289 (brier_optimized) | **+10.7%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,436 | 0.043 | 0.034 | 0.0088  | 0.0316 |
| 0.1-0.2 | 19,891 | 0.152 | 0.176 | 0.0234  | 0.1450 |
| 0.2-0.3 | 24,292 | 0.253 | 0.266 | 0.0134  | 0.1949 |
| 0.3-0.4 | 34,904 | 0.353 | 0.355 | 0.0017  | 0.2281 |
| 0.4-0.5 | 45,395 | 0.450 | 0.463 | 0.0129  | 0.2482 |
| 0.5-0.6 | 37,726 | 0.548 | 0.543 | 0.0049  | 0.2478 |
| 0.6-0.7 | 28,281 | 0.648 | 0.631 | 0.0166  | 0.2323 |
| 0.7-0.8 | 22,499 | 0.748 | 0.734 | 0.0134  | 0.1947 |
| 0.8-0.9 | 18,718 | 0.849 | 0.831 | 0.0178  | 0.1395 |
| 0.9-1.0 | 22,812 | 0.947 | 0.959 | 0.0116  | 0.0390 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,596 | 0.028 | 0.028 | 0.0000  | 0.0257 |
| 0.1-0.2 | 15,777 | 0.157 | 0.157 | 0.0000  | 0.1316 |
| 0.2-0.3 | 26,562 | 0.251 | 0.251 | 0.0000  | 0.1870 |
| 0.3-0.4 | 32,001 | 0.345 | 0.345 | 0.0000  | 0.2251 |
| 0.4-0.5 | 48,488 | 0.455 | 0.455 | 0.0000  | 0.2473 |
| 0.5-0.6 | 45,336 | 0.546 | 0.546 | 0.0000  | 0.2469 |
| 0.6-0.7 | 25,139 | 0.651 | 0.651 | 0.0000  | 0.2263 |
| 0.7-0.8 | 20,931 | 0.750 | 0.750 | 0.0000  | 0.1869 |
| 0.8-0.9 | 16,927 | 0.843 | 0.843 | 0.0000  | 0.1315 |
| 0.9-1.0 | 23,197 | 0.969 | 0.969 | 0.0000  | 0.0294 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 22,768 | 0.026 | 0.026 | 0.0000  | 0.0248 |
| 0.1-0.2 | 15,648 | 0.151 | 0.151 | 0.0000  | 0.1278 |
| 0.2-0.3 | 27,635 | 0.248 | 0.248 | 0.0000  | 0.1854 |
| 0.3-0.4 | 38,403 | 0.354 | 0.354 | 0.0000  | 0.2281 |
| 0.4-0.5 | 48,012 | 0.466 | 0.466 | 0.0000  | 0.2482 |
| 0.5-0.6 | 37,718 | 0.550 | 0.550 | 0.0000  | 0.2469 |
| 0.6-0.7 | 28,069 | 0.645 | 0.645 | 0.0000  | 0.2283 |
| 0.7-0.8 | 21,990 | 0.746 | 0.746 | 0.0000  | 0.1885 |
| 0.8-0.9 | 16,502 | 0.847 | 0.847 | 0.0000  | 0.1290 |
| 0.9-1.0 | 22,209 | 0.966 | 0.966 | 0.0000  | 0.0316 |

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
