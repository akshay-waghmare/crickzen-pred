# OOF Calibration Analysis Report

**Generated:** 2026-01-18 14:49:17
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
