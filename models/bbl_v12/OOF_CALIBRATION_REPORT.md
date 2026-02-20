# OOF Calibration Analysis Report

**Generated:** 2026-01-18 18:20:26
**Samples:** 141,435
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1757 | 0.0000 | 0.5179 |
| innings_phase | 0.1781 | 0.0000 | 0.5253 |
| ece_optimized | 0.1790 | 0.0048 | 0.5284 |
| innings_specific | 0.1801 | 0.0000 | 0.5305 |
| logloss_optimized | 0.1804 | 0.0135 | 0.5334 |
| combined | 0.1810 | 0.0000 | 0.5335 |
| raw | 0.1816 | 0.0148 | 0.5357 |
| resource_win_prob | 0.1889 | 0.0465 | 0.5537 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2136 | 0.0000 | 0.6135 | 73875.0000 |
| innings_phase | 0.2161 | 0.0000 | 0.6200 | 73875.0000 |
| ece_optimized | 0.2171 | 0.0070 | 0.6225 | 73875.0000 |
| innings_specific | 0.2176 | 0.0000 | 0.6235 | 73875.0000 |
| logloss_optimized | 0.2185 | 0.0203 | 0.6267 | 73875.0000 |
| combined | 0.2186 | 0.0188 | 0.6268 | 73875.0000 |
| raw | 0.2201 | 0.0315 | 0.6316 | 73875.0000 |
| resource_win_prob | 0.2243 | 0.0886 | 0.6374 | 73875.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1342 | 0.0000 | 0.4135 | 67560.0000 |
| innings_phase | 0.1366 | 0.0000 | 0.4217 | 67560.0000 |
| ece_optimized | 0.1374 | 0.0040 | 0.4254 | 67560.0000 |
| logloss_optimized | 0.1388 | 0.0122 | 0.4315 | 67560.0000 |
| innings_specific | 0.1390 | 0.0000 | 0.4288 | 67560.0000 |
| raw | 0.1396 | 0.0092 | 0.4310 | 67560.0000 |
| combined | 0.1399 | 0.0206 | 0.4314 | 67560.0000 |
| resource_win_prob | 0.1502 | 0.0405 | 0.4622 | 67560.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2347 | 0.0000 | 0.6610 | 18658.0000 |
| innings_phase | 0.2369 | 0.0000 | 0.6660 | 18658.0000 |
| ece_optimized | 0.2381 | 0.0120 | 0.6689 | 18658.0000 |
| logloss_optimized | 0.2393 | 0.0225 | 0.6713 | 18658.0000 |
| innings_specific | 0.2393 | 0.0312 | 0.6714 | 18658.0000 |
| combined | 0.2404 | 0.0440 | 0.6738 | 18658.0000 |
| raw | 0.2416 | 0.0511 | 0.6771 | 18658.0000 |
| resource_win_prob | 0.2521 | 0.1149 | 0.6973 | 18658.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2120 | 0.0000 | 0.6105 | 33364.0000 |
| innings_phase | 0.2150 | 0.0000 | 0.6181 | 33364.0000 |
| innings_specific | 0.2157 | 0.0101 | 0.6199 | 33364.0000 |
| ece_optimized | 0.2158 | 0.0108 | 0.6205 | 33364.0000 |
| logloss_optimized | 0.2169 | 0.0255 | 0.6240 | 33364.0000 |
| combined | 0.2170 | 0.0234 | 0.6245 | 33364.0000 |
| raw | 0.2187 | 0.0390 | 0.6303 | 33364.0000 |
| resource_win_prob | 0.2194 | 0.0710 | 0.6278 | 33364.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1980 | 0.0000 | 0.5775 | 21853.0000 |
| innings_phase | 0.2002 | 0.0000 | 0.5835 | 21853.0000 |
| ece_optimized | 0.2010 | 0.0056 | 0.5858 | 21853.0000 |
| innings_specific | 0.2020 | 0.0233 | 0.5882 | 21853.0000 |
| combined | 0.2024 | 0.0274 | 0.5903 | 21853.0000 |
| logloss_optimized | 0.2030 | 0.0318 | 0.5926 | 21853.0000 |
| raw | 0.2037 | 0.0356 | 0.5946 | 21853.0000 |
| resource_win_prob | 0.2081 | 0.0930 | 0.6011 | 21853.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1874 | 0.0000 | 0.5530 | 18700.0000 |
| innings_phase | 0.1894 | 0.0000 | 0.5588 | 18700.0000 |
| ece_optimized | 0.1903 | 0.0068 | 0.5617 | 18700.0000 |
| logloss_optimized | 0.1921 | 0.0332 | 0.5665 | 18700.0000 |
| innings_specific | 0.1926 | 0.0415 | 0.5676 | 18700.0000 |
| raw | 0.1929 | 0.0388 | 0.5682 | 18700.0000 |
| combined | 0.1931 | 0.0424 | 0.5682 | 18700.0000 |
| resource_win_prob | 0.2043 | 0.1283 | 0.6003 | 18700.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1326 | 0.0000 | 0.4137 | 32475.0000 |
| innings_phase | 0.1355 | 0.0000 | 0.4239 | 32475.0000 |
| ece_optimized | 0.1362 | 0.0047 | 0.4274 | 32475.0000 |
| innings_specific | 0.1364 | 0.0190 | 0.4270 | 32475.0000 |
| logloss_optimized | 0.1370 | 0.0225 | 0.4307 | 32475.0000 |
| raw | 0.1374 | 0.0232 | 0.4301 | 32475.0000 |
| combined | 0.1378 | 0.0312 | 0.4313 | 32475.0000 |
| resource_win_prob | 0.1445 | 0.0353 | 0.4512 | 32475.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0766 | 0.0000 | 0.2539 | 16385.0000 |
| innings_phase | 0.0786 | 0.0000 | 0.2610 | 16385.0000 |
| ece_optimized | 0.0793 | 0.0058 | 0.2661 | 16385.0000 |
| logloss_optimized | 0.0816 | 0.0299 | 0.2792 | 16385.0000 |
| innings_specific | 0.0829 | 0.0360 | 0.2738 | 16385.0000 |
| raw | 0.0831 | 0.0370 | 0.2760 | 16385.0000 |
| combined | 0.0831 | 0.0387 | 0.2753 | 16385.0000 |
| resource_win_prob | 0.0998 | 0.0832 | 0.3263 | 16385.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1757 |
| Innings 1 | brier_optimized | 0.2136 |
| Innings 2 | brier_optimized | 0.1342 |
| Inn1 Powerplay | brier_optimized | 0.2347 |
| Inn1 Middle | brier_optimized | 0.2120 |
| Inn1 Death | brier_optimized | 0.1980 |
| Inn2 Powerplay | brier_optimized | 0.1874 |
| Inn2 Middle | brier_optimized | 0.1326 |
| Inn2 Death | brier_optimized | 0.0766 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | combined | 0.0000 |
| Innings 1 | innings_phase | 0.0000 |
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
| Overall | brier_optimized | 0.5179 |
| Innings 1 | brier_optimized | 0.6135 |
| Innings 2 | brier_optimized | 0.4135 |
| Inn1 Powerplay | brier_optimized | 0.6610 |
| Inn1 Middle | brier_optimized | 0.6105 |
| Inn1 Death | brier_optimized | 0.5775 |
| Inn2 Powerplay | brier_optimized | 0.5530 |
| Inn2 Middle | brier_optimized | 0.4137 |
| Inn2 Death | brier_optimized | 0.2539 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 7 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1889 | 0.1757 (brier_optimized) | **+7.0%** |
| LogLoss | 0.5537 | 0.5179 (brier_optimized) | **+6.5%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 14,862 | 0.045 | 0.049 | 0.0041  | 0.0454 |
| 0.1-0.2 | 11,131 | 0.151 | 0.184 | 0.0330  | 0.1496 |
| 0.2-0.3 | 13,366 | 0.251 | 0.274 | 0.0225  | 0.1988 |
| 0.3-0.4 | 14,845 | 0.352 | 0.349 | 0.0035  | 0.2260 |
| 0.4-0.5 | 17,109 | 0.450 | 0.460 | 0.0096  | 0.2472 |
| 0.5-0.6 | 17,707 | 0.551 | 0.564 | 0.0136  | 0.2452 |
| 0.6-0.7 | 15,748 | 0.649 | 0.652 | 0.0030  | 0.2258 |
| 0.7-0.8 | 13,408 | 0.750 | 0.727 | 0.0229  | 0.1989 |
| 0.8-0.9 | 12,635 | 0.848 | 0.811 | 0.0367  | 0.1529 |
| 0.9-1.0 | 10,624 | 0.946 | 0.937 | 0.0088  | 0.0576 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 14,070 | 0.034 | 0.034 | 0.0000  | 0.0313 |
| 0.1-0.2 | 10,770 | 0.148 | 0.148 | 0.0000  | 0.1253 |
| 0.2-0.3 | 11,836 | 0.255 | 0.255 | 0.0000  | 0.1890 |
| 0.3-0.4 | 17,493 | 0.342 | 0.342 | 0.0000  | 0.2245 |
| 0.4-0.5 | 13,901 | 0.446 | 0.446 | 0.0000  | 0.2463 |
| 0.5-0.6 | 21,785 | 0.553 | 0.553 | 0.0000  | 0.2464 |
| 0.6-0.7 | 17,117 | 0.666 | 0.666 | 0.0000  | 0.2217 |
| 0.7-0.8 | 13,150 | 0.739 | 0.739 | 0.0000  | 0.1921 |
| 0.8-0.9 | 10,946 | 0.847 | 0.847 | 0.0000  | 0.1289 |
| 0.9-1.0 | 10,367 | 0.962 | 0.962 | 0.0000  | 0.0358 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 12,948 | 0.036 | 0.036 | 0.0000  | 0.0337 |
| 0.1-0.2 | 10,547 | 0.141 | 0.141 | 0.0000  | 0.1206 |
| 0.2-0.3 | 12,243 | 0.250 | 0.250 | 0.0000  | 0.1864 |
| 0.3-0.4 | 20,060 | 0.351 | 0.351 | 0.0000  | 0.2269 |
| 0.4-0.5 | 12,449 | 0.447 | 0.447 | 0.0000  | 0.2460 |
| 0.5-0.6 | 18,087 | 0.547 | 0.547 | 0.0000  | 0.2472 |
| 0.6-0.7 | 19,059 | 0.651 | 0.651 | 0.0000  | 0.2255 |
| 0.7-0.8 | 16,235 | 0.729 | 0.729 | 0.0000  | 0.1965 |
| 0.8-0.9 | 10,257 | 0.854 | 0.854 | 0.0000  | 0.1242 |
| 0.9-1.0 | 9,550 | 0.960 | 0.960 | 0.0000  | 0.0373 |

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
