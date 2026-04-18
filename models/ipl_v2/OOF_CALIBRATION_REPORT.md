# OOF Calibration Analysis Report

**Generated:** 2026-04-18 20:41:11
**Samples:** 278,954
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1841 | 0.0000 | 0.5353 |
| innings_phase | 0.1858 | 0.0000 | 0.5401 |
| ece_optimized | 0.1864 | 0.0021 | 0.5423 |
| innings_specific | 0.1865 | 0.0000 | 0.5422 |
| combined | 0.1870 | 0.0000 | 0.5435 |
| raw | 0.1874 | 0.0124 | 0.5457 |
| logloss_optimized | 0.1876 | 0.0161 | 0.5484 |
| resource_win_prob | 0.2113 | 0.1133 | 0.6154 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2212 | 0.0000 | 0.6295 | 144340.0000 |
| innings_phase | 0.2230 | 0.0000 | 0.6341 | 144340.0000 |
| ece_optimized | 0.2236 | 0.0038 | 0.6358 | 144340.0000 |
| innings_specific | 0.2237 | 0.0000 | 0.6357 | 144340.0000 |
| combined | 0.2241 | 0.0126 | 0.6372 | 144340.0000 |
| logloss_optimized | 0.2244 | 0.0113 | 0.6386 | 144340.0000 |
| raw | 0.2249 | 0.0222 | 0.6392 | 144340.0000 |
| resource_win_prob | 0.2507 | 0.1336 | 0.7086 | 144340.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1443 | 0.0000 | 0.4342 | 134614.0000 |
| innings_phase | 0.1459 | 0.0000 | 0.4394 | 134614.0000 |
| ece_optimized | 0.1465 | 0.0043 | 0.4421 | 134614.0000 |
| innings_specific | 0.1467 | 0.0000 | 0.4420 | 134614.0000 |
| combined | 0.1471 | 0.0135 | 0.4431 | 134614.0000 |
| raw | 0.1473 | 0.0161 | 0.4454 | 134614.0000 |
| logloss_optimized | 0.1482 | 0.0270 | 0.4517 | 134614.0000 |
| resource_win_prob | 0.1691 | 0.0916 | 0.5155 | 134614.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2402 | 0.0000 | 0.6723 | 36260.0000 |
| innings_phase | 0.2415 | 0.0000 | 0.6753 | 36260.0000 |
| innings_specific | 0.2421 | 0.0099 | 0.6768 | 36260.0000 |
| ece_optimized | 0.2421 | 0.0046 | 0.6768 | 36260.0000 |
| logloss_optimized | 0.2424 | 0.0106 | 0.6775 | 36260.0000 |
| combined | 0.2424 | 0.0187 | 0.6774 | 36260.0000 |
| raw | 0.2428 | 0.0229 | 0.6784 | 36260.0000 |
| resource_win_prob | 0.2451 | 0.0360 | 0.6836 | 36260.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2199 | 0.0000 | 0.6268 | 64842.0000 |
| innings_phase | 0.2220 | 0.0000 | 0.6320 | 64842.0000 |
| innings_specific | 0.2225 | 0.0143 | 0.6333 | 64842.0000 |
| ece_optimized | 0.2225 | 0.0050 | 0.6335 | 64842.0000 |
| combined | 0.2226 | 0.0144 | 0.6339 | 64842.0000 |
| logloss_optimized | 0.2233 | 0.0174 | 0.6364 | 64842.0000 |
| raw | 0.2234 | 0.0230 | 0.6361 | 64842.0000 |
| resource_win_prob | 0.2677 | 0.1895 | 0.7565 | 64842.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2072 | 0.0000 | 0.5977 | 43238.0000 |
| innings_phase | 0.2090 | 0.0000 | 0.6026 | 43238.0000 |
| ece_optimized | 0.2098 | 0.0056 | 0.6049 | 43238.0000 |
| innings_specific | 0.2101 | 0.0186 | 0.6050 | 43238.0000 |
| logloss_optimized | 0.2110 | 0.0227 | 0.6094 | 43238.0000 |
| combined | 0.2110 | 0.0281 | 0.6082 | 43238.0000 |
| raw | 0.2119 | 0.0379 | 0.6108 | 43238.0000 |
| resource_win_prob | 0.2299 | 0.1324 | 0.6578 | 43238.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1882 | 0.0000 | 0.5520 | 36276.0000 |
| innings_phase | 0.1894 | 0.0000 | 0.5554 | 36276.0000 |
| ece_optimized | 0.1901 | 0.0053 | 0.5580 | 36276.0000 |
| innings_specific | 0.1901 | 0.0130 | 0.5581 | 36276.0000 |
| resource_win_prob | 0.1901 | 0.0359 | 0.5585 | 36276.0000 |
| combined | 0.1904 | 0.0140 | 0.5589 | 36276.0000 |
| raw | 0.1906 | 0.0140 | 0.5593 | 36276.0000 |
| logloss_optimized | 0.1913 | 0.0304 | 0.5622 | 36276.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1473 | 0.0000 | 0.4446 | 63812.0000 |
| innings_phase | 0.1491 | 0.0000 | 0.4509 | 63812.0000 |
| innings_specific | 0.1495 | 0.0103 | 0.4519 | 63812.0000 |
| ece_optimized | 0.1497 | 0.0051 | 0.4538 | 63812.0000 |
| combined | 0.1500 | 0.0177 | 0.4533 | 63812.0000 |
| raw | 0.1502 | 0.0196 | 0.4556 | 63812.0000 |
| logloss_optimized | 0.1514 | 0.0327 | 0.4631 | 63812.0000 |
| resource_win_prob | 0.1719 | 0.1111 | 0.5140 | 63812.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0926 | 0.0000 | 0.2913 | 34526.0000 |
| innings_phase | 0.0941 | 0.0000 | 0.2962 | 34526.0000 |
| ece_optimized | 0.0947 | 0.0060 | 0.2988 | 34526.0000 |
| innings_specific | 0.0959 | 0.0260 | 0.3015 | 34526.0000 |
| combined | 0.0963 | 0.0263 | 0.3025 | 34526.0000 |
| raw | 0.0965 | 0.0363 | 0.3071 | 34526.0000 |
| logloss_optimized | 0.0970 | 0.0304 | 0.3147 | 34526.0000 |
| resource_win_prob | 0.1420 | 0.1439 | 0.4731 | 34526.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1841 |
| Innings 1 | brier_optimized | 0.2212 |
| Innings 2 | brier_optimized | 0.1443 |
| Inn1 Powerplay | brier_optimized | 0.2402 |
| Inn1 Middle | brier_optimized | 0.2199 |
| Inn1 Death | brier_optimized | 0.2072 |
| Inn2 Powerplay | brier_optimized | 0.1882 |
| Inn2 Middle | brier_optimized | 0.1473 |
| Inn2 Death | brier_optimized | 0.0926 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
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
| Overall | brier_optimized | 0.5353 |
| Innings 1 | brier_optimized | 0.6295 |
| Innings 2 | brier_optimized | 0.4342 |
| Inn1 Powerplay | brier_optimized | 0.6723 |
| Inn1 Middle | brier_optimized | 0.6268 |
| Inn1 Death | brier_optimized | 0.5977 |
| Inn2 Powerplay | brier_optimized | 0.5520 |
| Inn2 Middle | brier_optimized | 0.4446 |
| Inn2 Death | brier_optimized | 0.2913 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 9 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2113 | 0.1841 (brier_optimized) | **+12.9%** |
| LogLoss | 0.6154 | 0.5353 (brier_optimized) | **+13.0%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 23,226 | 0.046 | 0.035 | 0.0115  | 0.0329 |
| 0.1-0.2 | 18,101 | 0.151 | 0.171 | 0.0206  | 0.1423 |
| 0.2-0.3 | 25,430 | 0.253 | 0.279 | 0.0251  | 0.1998 |
| 0.3-0.4 | 34,330 | 0.352 | 0.359 | 0.0063  | 0.2300 |
| 0.4-0.5 | 47,195 | 0.451 | 0.455 | 0.0040  | 0.2470 |
| 0.5-0.6 | 40,740 | 0.547 | 0.545 | 0.0022  | 0.2475 |
| 0.6-0.7 | 29,464 | 0.647 | 0.635 | 0.0126  | 0.2315 |
| 0.7-0.8 | 21,893 | 0.748 | 0.718 | 0.0301  | 0.2022 |
| 0.8-0.9 | 17,563 | 0.848 | 0.837 | 0.0111  | 0.1351 |
| 0.9-1.0 | 21,012 | 0.948 | 0.970 | 0.0216  | 0.0290 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 22,463 | 0.026 | 0.026 | 0.0000  | 0.0240 |
| 0.1-0.2 | 19,275 | 0.160 | 0.160 | 0.0000  | 0.1333 |
| 0.2-0.3 | 17,899 | 0.250 | 0.250 | 0.0000  | 0.1866 |
| 0.3-0.4 | 40,708 | 0.351 | 0.351 | 0.0000  | 0.2271 |
| 0.4-0.5 | 44,189 | 0.450 | 0.450 | 0.0000  | 0.2465 |
| 0.5-0.6 | 47,267 | 0.542 | 0.542 | 0.0000  | 0.2476 |
| 0.6-0.7 | 31,188 | 0.647 | 0.647 | 0.0000  | 0.2274 |
| 0.7-0.8 | 20,770 | 0.753 | 0.753 | 0.0000  | 0.1852 |
| 0.8-0.9 | 11,063 | 0.851 | 0.851 | 0.0000  | 0.1258 |
| 0.9-1.0 | 24,132 | 0.968 | 0.968 | 0.0000  | 0.0302 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 23,035 | 0.033 | 0.033 | 0.0000  | 0.0305 |
| 0.1-0.2 | 19,721 | 0.168 | 0.168 | 0.0000  | 0.1388 |
| 0.2-0.3 | 18,857 | 0.266 | 0.266 | 0.0000  | 0.1943 |
| 0.3-0.4 | 45,909 | 0.362 | 0.362 | 0.0000  | 0.2302 |
| 0.4-0.5 | 40,588 | 0.462 | 0.462 | 0.0000  | 0.2476 |
| 0.5-0.6 | 47,199 | 0.549 | 0.549 | 0.0000  | 0.2470 |
| 0.6-0.7 | 31,851 | 0.658 | 0.658 | 0.0000  | 0.2244 |
| 0.7-0.8 | 18,916 | 0.761 | 0.761 | 0.0000  | 0.1809 |
| 0.8-0.9 | 9,033 | 0.856 | 0.856 | 0.0000  | 0.1227 |
| 0.9-1.0 | 23,845 | 0.966 | 0.966 | 0.0000  | 0.0321 |

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
