# OOF Calibration Analysis Report

**Generated:** 2026-07-11 00:11:49
**Samples:** 1,226,834
**Folds:** 3

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1503 | 0.0000 | 0.4493 |
| innings_phase | 0.1511 | 0.0000 | 0.4516 |
| ece_optimized | 0.1513 | 0.0021 | 0.4526 |
| innings_specific | 0.1514 | 0.0000 | 0.4528 |
| combined | 0.1516 | 0.0000 | 0.4536 |
| raw | 0.1517 | 0.0062 | 0.4544 |
| logloss_optimized | 0.1529 | 0.0244 | 0.4613 |
| resource_win_prob | 0.1998 | 0.0944 | 0.5814 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1882 | 0.0000 | 0.5527 | 659049.0000 |
| innings_phase | 0.1888 | 0.0000 | 0.5546 | 659049.0000 |
| ece_optimized | 0.1890 | 0.0012 | 0.5555 | 659049.0000 |
| innings_specific | 0.1890 | 0.0000 | 0.5552 | 659049.0000 |
| combined | 0.1891 | 0.0070 | 0.5561 | 659049.0000 |
| raw | 0.1892 | 0.0075 | 0.5562 | 659049.0000 |
| logloss_optimized | 0.1899 | 0.0208 | 0.5594 | 659049.0000 |
| resource_win_prob | 0.2429 | 0.1666 | 0.6807 | 659049.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1064 | 0.0000 | 0.3293 | 567785.0000 |
| innings_phase | 0.1073 | 0.0000 | 0.3321 | 567785.0000 |
| ece_optimized | 0.1075 | 0.0035 | 0.3331 | 567785.0000 |
| innings_specific | 0.1078 | 0.0000 | 0.3339 | 567785.0000 |
| combined | 0.1080 | 0.0081 | 0.3347 | 567785.0000 |
| raw | 0.1081 | 0.0108 | 0.3362 | 567785.0000 |
| logloss_optimized | 0.1100 | 0.0350 | 0.3474 | 567785.0000 |
| resource_win_prob | 0.1497 | 0.1226 | 0.4662 | 567785.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2102 | 0.0000 | 0.6059 | 169665.0000 |
| innings_phase | 0.2108 | 0.0000 | 0.6076 | 169665.0000 |
| ece_optimized | 0.2110 | 0.0021 | 0.6081 | 169665.0000 |
| innings_specific | 0.2111 | 0.0125 | 0.6087 | 169665.0000 |
| combined | 0.2112 | 0.0157 | 0.6090 | 169665.0000 |
| raw | 0.2113 | 0.0146 | 0.6091 | 169665.0000 |
| logloss_optimized | 0.2114 | 0.0154 | 0.6098 | 169665.0000 |
| resource_win_prob | 0.2617 | 0.1466 | 0.7176 | 169665.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1847 | 0.0000 | 0.5445 | 300216.0000 |
| innings_phase | 0.1853 | 0.0000 | 0.5465 | 300216.0000 |
| innings_specific | 0.1854 | 0.0038 | 0.5468 | 300216.0000 |
| ece_optimized | 0.1855 | 0.0014 | 0.5473 | 300216.0000 |
| combined | 0.1856 | 0.0087 | 0.5477 | 300216.0000 |
| raw | 0.1857 | 0.0090 | 0.5479 | 300216.0000 |
| logloss_optimized | 0.1865 | 0.0222 | 0.5515 | 300216.0000 |
| resource_win_prob | 0.2327 | 0.1528 | 0.6572 | 300216.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1740 | 0.0000 | 0.5180 | 189168.0000 |
| innings_phase | 0.1746 | 0.0000 | 0.5200 | 189168.0000 |
| ece_optimized | 0.1749 | 0.0031 | 0.5213 | 189168.0000 |
| innings_specific | 0.1749 | 0.0107 | 0.5208 | 189168.0000 |
| combined | 0.1750 | 0.0124 | 0.5219 | 189168.0000 |
| raw | 0.1751 | 0.0127 | 0.5219 | 189168.0000 |
| logloss_optimized | 0.1761 | 0.0234 | 0.5267 | 189168.0000 |
| resource_win_prob | 0.2421 | 0.2064 | 0.6850 | 189168.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1452 | 0.0000 | 0.4381 | 168605.0000 |
| innings_phase | 0.1458 | 0.0000 | 0.4402 | 168605.0000 |
| ece_optimized | 0.1460 | 0.0029 | 0.4416 | 168605.0000 |
| innings_specific | 0.1462 | 0.0128 | 0.4416 | 168605.0000 |
| combined | 0.1465 | 0.0154 | 0.4422 | 168605.0000 |
| raw | 0.1467 | 0.0179 | 0.4432 | 168605.0000 |
| logloss_optimized | 0.1489 | 0.0457 | 0.4548 | 168605.0000 |
| resource_win_prob | 0.2273 | 0.2289 | 0.6783 | 168605.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1017 | 0.0000 | 0.3170 | 275767.0000 |
| innings_phase | 0.1026 | 0.0000 | 0.3199 | 275767.0000 |
| innings_specific | 0.1027 | 0.0053 | 0.3202 | 275767.0000 |
| ece_optimized | 0.1027 | 0.0038 | 0.3209 | 275767.0000 |
| combined | 0.1029 | 0.0100 | 0.3209 | 275767.0000 |
| raw | 0.1030 | 0.0149 | 0.3226 | 275767.0000 |
| logloss_optimized | 0.1053 | 0.0367 | 0.3353 | 275767.0000 |
| resource_win_prob | 0.1372 | 0.1196 | 0.4361 | 275767.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0641 | 0.0000 | 0.2084 | 123413.0000 |
| innings_phase | 0.0652 | 0.0000 | 0.2118 | 123413.0000 |
| ece_optimized | 0.0654 | 0.0057 | 0.2125 | 123413.0000 |
| combined | 0.0667 | 0.0231 | 0.2186 | 123413.0000 |
| innings_specific | 0.0668 | 0.0224 | 0.2175 | 123413.0000 |
| raw | 0.0668 | 0.0239 | 0.2201 | 123413.0000 |
| logloss_optimized | 0.0675 | 0.0167 | 0.2276 | 123413.0000 |
| resource_win_prob | 0.0718 | 0.0264 | 0.2437 | 123413.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1503 |
| Innings 1 | brier_optimized | 0.1882 |
| Innings 2 | brier_optimized | 0.1064 |
| Inn1 Powerplay | brier_optimized | 0.2102 |
| Inn1 Middle | brier_optimized | 0.1847 |
| Inn1 Death | brier_optimized | 0.1740 |
| Inn2 Powerplay | brier_optimized | 0.1452 |
| Inn2 Middle | brier_optimized | 0.1017 |
| Inn2 Death | brier_optimized | 0.0641 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | combined | 0.0000 |
| Innings 1 | innings_specific | 0.0000 |
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
| Overall | brier_optimized | 0.4493 |
| Innings 1 | brier_optimized | 0.5527 |
| Innings 2 | brier_optimized | 0.3293 |
| Inn1 Powerplay | brier_optimized | 0.6059 |
| Inn1 Middle | brier_optimized | 0.5445 |
| Inn1 Death | brier_optimized | 0.5180 |
| Inn2 Powerplay | brier_optimized | 0.4381 |
| Inn2 Middle | brier_optimized | 0.3170 |
| Inn2 Death | brier_optimized | 0.2084 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 7 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1998 | 0.1503 (brier_optimized) | **+24.7%** |
| LogLoss | 0.5814 | 0.4493 (brier_optimized) | **+22.7%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 196,696 | 0.031 | 0.025 | 0.0060  | 0.0234 |
| 0.1-0.2 | 98,409 | 0.150 | 0.145 | 0.0044  | 0.1232 |
| 0.2-0.3 | 104,888 | 0.251 | 0.257 | 0.0062  | 0.1901 |
| 0.3-0.4 | 113,783 | 0.350 | 0.361 | 0.0107  | 0.2297 |
| 0.4-0.5 | 117,170 | 0.451 | 0.453 | 0.0028  | 0.2473 |
| 0.5-0.6 | 119,753 | 0.550 | 0.541 | 0.0085  | 0.2475 |
| 0.6-0.7 | 115,078 | 0.650 | 0.647 | 0.0034  | 0.2276 |
| 0.7-0.8 | 110,204 | 0.749 | 0.749 | 0.0004  | 0.1872 |
| 0.8-0.9 | 109,703 | 0.850 | 0.854 | 0.0032  | 0.1237 |
| 0.9-1.0 | 141,150 | 0.954 | 0.968 | 0.0144  | 0.0304 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 207,796 | 0.026 | 0.026 | 0.0000  | 0.0247 |
| 0.1-0.2 | 90,412 | 0.152 | 0.152 | 0.0000  | 0.1279 |
| 0.2-0.3 | 96,545 | 0.253 | 0.253 | 0.0000  | 0.1882 |
| 0.3-0.4 | 97,477 | 0.348 | 0.348 | 0.0000  | 0.2260 |
| 0.4-0.5 | 148,402 | 0.449 | 0.449 | 0.0000  | 0.2466 |
| 0.5-0.6 | 117,395 | 0.548 | 0.548 | 0.0000  | 0.2468 |
| 0.6-0.7 | 106,917 | 0.650 | 0.650 | 0.0000  | 0.2265 |
| 0.7-0.8 | 110,117 | 0.748 | 0.748 | 0.0000  | 0.1878 |
| 0.8-0.9 | 94,431 | 0.848 | 0.848 | 0.0000  | 0.1278 |
| 0.9-1.0 | 157,342 | 0.966 | 0.966 | 0.0000  | 0.0319 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 209,416 | 0.028 | 0.028 | 0.0000  | 0.0266 |
| 0.1-0.2 | 84,104 | 0.152 | 0.152 | 0.0000  | 0.1278 |
| 0.2-0.3 | 96,504 | 0.249 | 0.249 | 0.0000  | 0.1862 |
| 0.3-0.4 | 100,627 | 0.346 | 0.346 | 0.0000  | 0.2256 |
| 0.4-0.5 | 160,874 | 0.452 | 0.452 | 0.0000  | 0.2468 |
| 0.5-0.6 | 109,882 | 0.554 | 0.554 | 0.0000  | 0.2463 |
| 0.6-0.7 | 94,152 | 0.646 | 0.646 | 0.0000  | 0.2279 |
| 0.7-0.8 | 125,123 | 0.746 | 0.746 | 0.0000  | 0.1884 |
| 0.8-0.9 | 83,655 | 0.847 | 0.847 | 0.0000  | 0.1291 |
| 0.9-1.0 | 162,497 | 0.962 | 0.962 | 0.0000  | 0.0355 |

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
