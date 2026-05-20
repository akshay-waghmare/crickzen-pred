# OOF Calibration Analysis Report

**Generated:** 2026-05-03 00:03:43
**Samples:** 278,954
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1810 | 0.0000 | 0.5279 |
| innings_phase | 0.1827 | 0.0000 | 0.5330 |
| ece_optimized | 0.1833 | 0.0033 | 0.5350 |
| innings_specific | 0.1834 | 0.0000 | 0.5354 |
| combined | 0.1836 | 0.0000 | 0.5362 |
| raw | 0.1840 | 0.0123 | 0.5378 |
| logloss_optimized | 0.1845 | 0.0180 | 0.5410 |
| resource_win_prob | 0.2046 | 0.0749 | 0.5923 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2187 | 0.0000 | 0.6246 | 144340.0000 |
| innings_phase | 0.2205 | 0.0000 | 0.6290 | 144340.0000 |
| ece_optimized | 0.2211 | 0.0036 | 0.6306 | 144340.0000 |
| innings_specific | 0.2211 | 0.0000 | 0.6305 | 144340.0000 |
| combined | 0.2213 | 0.0072 | 0.6314 | 144340.0000 |
| logloss_optimized | 0.2215 | 0.0080 | 0.6326 | 144340.0000 |
| raw | 0.2218 | 0.0164 | 0.6330 | 144340.0000 |
| resource_win_prob | 0.2507 | 0.1336 | 0.7086 | 144340.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1405 | 0.0000 | 0.4242 | 134614.0000 |
| innings_phase | 0.1423 | 0.0000 | 0.4301 | 134614.0000 |
| ece_optimized | 0.1428 | 0.0033 | 0.4324 | 134614.0000 |
| innings_specific | 0.1431 | 0.0000 | 0.4335 | 134614.0000 |
| combined | 0.1433 | 0.0077 | 0.4341 | 134614.0000 |
| raw | 0.1435 | 0.0110 | 0.4359 | 134614.0000 |
| logloss_optimized | 0.1447 | 0.0320 | 0.4428 | 134614.0000 |
| resource_win_prob | 0.1552 | 0.0178 | 0.4676 | 134614.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2381 | 0.0000 | 0.6682 | 36260.0000 |
| innings_phase | 0.2392 | 0.0000 | 0.6706 | 36260.0000 |
| innings_specific | 0.2398 | 0.0066 | 0.6722 | 36260.0000 |
| ece_optimized | 0.2399 | 0.0050 | 0.6722 | 36260.0000 |
| combined | 0.2400 | 0.0100 | 0.6726 | 36260.0000 |
| logloss_optimized | 0.2402 | 0.0080 | 0.6730 | 36260.0000 |
| raw | 0.2406 | 0.0184 | 0.6738 | 36260.0000 |
| resource_win_prob | 0.2451 | 0.0360 | 0.6836 | 36260.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2170 | 0.0000 | 0.6211 | 64842.0000 |
| innings_phase | 0.2190 | 0.0000 | 0.6262 | 64842.0000 |
| innings_specific | 0.2194 | 0.0130 | 0.6273 | 64842.0000 |
| combined | 0.2195 | 0.0102 | 0.6277 | 64842.0000 |
| ece_optimized | 0.2195 | 0.0038 | 0.6276 | 64842.0000 |
| logloss_optimized | 0.2199 | 0.0120 | 0.6293 | 64842.0000 |
| raw | 0.2200 | 0.0170 | 0.6293 | 64842.0000 |
| resource_win_prob | 0.2677 | 0.1895 | 0.7565 | 64842.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2050 | 0.0000 | 0.5934 | 43238.0000 |
| innings_phase | 0.2069 | 0.0000 | 0.5983 | 43238.0000 |
| ece_optimized | 0.2076 | 0.0039 | 0.6003 | 43238.0000 |
| innings_specific | 0.2078 | 0.0207 | 0.6004 | 43238.0000 |
| combined | 0.2083 | 0.0265 | 0.6026 | 43238.0000 |
| logloss_optimized | 0.2084 | 0.0135 | 0.6036 | 43238.0000 |
| raw | 0.2088 | 0.0262 | 0.6042 | 43238.0000 |
| resource_win_prob | 0.2299 | 0.1324 | 0.6578 | 43238.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1803 | 0.0000 | 0.5323 | 36276.0000 |
| innings_phase | 0.1819 | 0.0000 | 0.5376 | 36276.0000 |
| ece_optimized | 0.1826 | 0.0043 | 0.5405 | 36276.0000 |
| innings_specific | 0.1826 | 0.0131 | 0.5416 | 36276.0000 |
| combined | 0.1827 | 0.0157 | 0.5415 | 36276.0000 |
| raw | 0.1830 | 0.0159 | 0.5415 | 36276.0000 |
| logloss_optimized | 0.1836 | 0.0238 | 0.5445 | 36276.0000 |
| resource_win_prob | 0.1938 | 0.0271 | 0.5671 | 36276.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1439 | 0.0000 | 0.4344 | 63812.0000 |
| innings_phase | 0.1459 | 0.0000 | 0.4414 | 63812.0000 |
| innings_specific | 0.1462 | 0.0090 | 0.4425 | 63812.0000 |
| combined | 0.1463 | 0.0098 | 0.4429 | 63812.0000 |
| ece_optimized | 0.1463 | 0.0048 | 0.4436 | 63812.0000 |
| raw | 0.1467 | 0.0135 | 0.4451 | 63812.0000 |
| logloss_optimized | 0.1486 | 0.0421 | 0.4554 | 63812.0000 |
| resource_win_prob | 0.1592 | 0.0296 | 0.4794 | 63812.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0926 | 0.0000 | 0.2916 | 34526.0000 |
| innings_phase | 0.0939 | 0.0000 | 0.2963 | 34526.0000 |
| ece_optimized | 0.0943 | 0.0047 | 0.2982 | 34526.0000 |
| innings_specific | 0.0957 | 0.0275 | 0.3033 | 34526.0000 |
| raw | 0.0962 | 0.0353 | 0.3078 | 34526.0000 |
| combined | 0.0962 | 0.0300 | 0.3048 | 34526.0000 |
| logloss_optimized | 0.0966 | 0.0276 | 0.3127 | 34526.0000 |
| resource_win_prob | 0.1073 | 0.0466 | 0.3413 | 34526.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1810 |
| Innings 1 | brier_optimized | 0.2187 |
| Innings 2 | brier_optimized | 0.1405 |
| Inn1 Powerplay | brier_optimized | 0.2381 |
| Inn1 Middle | brier_optimized | 0.2170 |
| Inn1 Death | brier_optimized | 0.2050 |
| Inn2 Powerplay | brier_optimized | 0.1803 |
| Inn2 Middle | brier_optimized | 0.1439 |
| Inn2 Death | brier_optimized | 0.0926 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | innings_specific | 0.0000 |
| Innings 1 | innings_phase | 0.0000 |
| Innings 2 | innings_phase | 0.0000 |
| Inn1 Powerplay | innings_phase | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5279 |
| Innings 1 | brier_optimized | 0.6246 |
| Innings 2 | brier_optimized | 0.4242 |
| Inn1 Powerplay | brier_optimized | 0.6682 |
| Inn1 Middle | brier_optimized | 0.6211 |
| Inn1 Death | brier_optimized | 0.5934 |
| Inn2 Powerplay | brier_optimized | 0.5323 |
| Inn2 Middle | brier_optimized | 0.4344 |
| Inn2 Death | brier_optimized | 0.2916 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 5 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2046 | 0.1810 (brier_optimized) | **+11.5%** |
| LogLoss | 0.5923 | 0.5279 (brier_optimized) | **+10.9%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,341 | 0.043 | 0.031 | 0.0116  | 0.0294 |
| 0.1-0.2 | 20,013 | 0.152 | 0.175 | 0.0226  | 0.1446 |
| 0.2-0.3 | 24,670 | 0.253 | 0.270 | 0.0172  | 0.1964 |
| 0.3-0.4 | 35,107 | 0.354 | 0.357 | 0.0028  | 0.2286 |
| 0.4-0.5 | 44,957 | 0.451 | 0.464 | 0.0136  | 0.2483 |
| 0.5-0.6 | 37,823 | 0.548 | 0.539 | 0.0089  | 0.2480 |
| 0.6-0.7 | 28,046 | 0.648 | 0.639 | 0.0092  | 0.2299 |
| 0.7-0.8 | 22,347 | 0.748 | 0.729 | 0.0192  | 0.1972 |
| 0.8-0.9 | 18,739 | 0.849 | 0.835 | 0.0142  | 0.1369 |
| 0.9-1.0 | 22,911 | 0.947 | 0.959 | 0.0120  | 0.0390 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,163 | 0.024 | 0.024 | 0.0000  | 0.0227 |
| 0.1-0.2 | 16,595 | 0.157 | 0.157 | 0.0000  | 0.1316 |
| 0.2-0.3 | 24,673 | 0.249 | 0.249 | 0.0000  | 0.1859 |
| 0.3-0.4 | 33,327 | 0.344 | 0.344 | 0.0000  | 0.2248 |
| 0.4-0.5 | 53,887 | 0.457 | 0.457 | 0.0000  | 0.2474 |
| 0.5-0.6 | 38,248 | 0.549 | 0.549 | 0.0000  | 0.2467 |
| 0.6-0.7 | 28,013 | 0.653 | 0.653 | 0.0000  | 0.2257 |
| 0.7-0.8 | 21,016 | 0.753 | 0.753 | 0.0000  | 0.1852 |
| 0.8-0.9 | 15,824 | 0.849 | 0.849 | 0.0000  | 0.1270 |
| 0.9-1.0 | 23,208 | 0.969 | 0.969 | 0.0000  | 0.0293 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,153 | 0.029 | 0.029 | 0.0000  | 0.0270 |
| 0.1-0.2 | 15,511 | 0.161 | 0.161 | 0.0000  | 0.1343 |
| 0.2-0.3 | 23,486 | 0.244 | 0.244 | 0.0000  | 0.1833 |
| 0.3-0.4 | 40,414 | 0.351 | 0.351 | 0.0000  | 0.2269 |
| 0.4-0.5 | 47,051 | 0.462 | 0.462 | 0.0000  | 0.2478 |
| 0.5-0.6 | 39,434 | 0.544 | 0.544 | 0.0000  | 0.2472 |
| 0.6-0.7 | 31,687 | 0.657 | 0.657 | 0.0000  | 0.2247 |
| 0.7-0.8 | 18,641 | 0.751 | 0.751 | 0.0000  | 0.1862 |
| 0.8-0.9 | 16,481 | 0.851 | 0.851 | 0.0000  | 0.1257 |
| 0.9-1.0 | 22,096 | 0.967 | 0.967 | 0.0000  | 0.0312 |

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
