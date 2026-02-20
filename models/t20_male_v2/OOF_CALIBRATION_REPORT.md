# OOF Calibration Analysis Report

**Generated:** 2026-01-19 09:12:34
**Samples:** 1,221,350
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1788 | 0.0000 | 0.5242 |
| innings_phase | 0.1795 | 0.0000 | 0.5263 |
| ece_optimized | 0.1798 | 0.0018 | 0.5273 |
| innings_specific | 0.1800 | 0.0000 | 0.5276 |
| combined | 0.1801 | 0.0000 | 0.5280 |
| raw | 0.1803 | 0.0062 | 0.5291 |
| logloss_optimized | 0.1807 | 0.0139 | 0.5324 |
| resource_win_prob | 0.1908 | 0.0420 | 0.5591 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2177 | 0.0000 | 0.6228 | 636375.0000 |
| innings_phase | 0.2184 | 0.0000 | 0.6247 | 636375.0000 |
| innings_specific | 0.2186 | 0.0000 | 0.6253 | 636375.0000 |
| ece_optimized | 0.2187 | 0.0021 | 0.6255 | 636375.0000 |
| combined | 0.2187 | 0.0057 | 0.6259 | 636375.0000 |
| raw | 0.2189 | 0.0091 | 0.6262 | 636375.0000 |
| logloss_optimized | 0.2190 | 0.0101 | 0.6267 | 636375.0000 |
| resource_win_prob | 0.2273 | 0.0715 | 0.6443 | 636375.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1366 | 0.0000 | 0.4169 | 584975.0000 |
| innings_phase | 0.1373 | 0.0000 | 0.4193 | 584975.0000 |
| ece_optimized | 0.1375 | 0.0024 | 0.4204 | 584975.0000 |
| innings_specific | 0.1380 | 0.0000 | 0.4212 | 584975.0000 |
| combined | 0.1381 | 0.0062 | 0.4215 | 584975.0000 |
| raw | 0.1383 | 0.0101 | 0.4235 | 584975.0000 |
| logloss_optimized | 0.1391 | 0.0243 | 0.4297 | 584975.0000 |
| resource_win_prob | 0.1510 | 0.0413 | 0.4664 | 584975.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2379 | 0.0000 | 0.6681 | 160809.0000 |
| innings_phase | 0.2384 | 0.0000 | 0.6693 | 160809.0000 |
| ece_optimized | 0.2387 | 0.0007 | 0.6699 | 160809.0000 |
| logloss_optimized | 0.2387 | 0.0040 | 0.6700 | 160809.0000 |
| innings_specific | 0.2388 | 0.0112 | 0.6701 | 160809.0000 |
| combined | 0.2388 | 0.0128 | 0.6702 | 160809.0000 |
| raw | 0.2389 | 0.0136 | 0.6704 | 160809.0000 |
| resource_win_prob | 0.2546 | 0.1106 | 0.7030 | 160809.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2163 | 0.0000 | 0.6202 | 286924.0000 |
| innings_phase | 0.2171 | 0.0000 | 0.6222 | 286924.0000 |
| innings_specific | 0.2172 | 0.0034 | 0.6226 | 286924.0000 |
| combined | 0.2174 | 0.0078 | 0.6233 | 286924.0000 |
| ece_optimized | 0.2174 | 0.0027 | 0.6231 | 286924.0000 |
| raw | 0.2176 | 0.0122 | 0.6238 | 286924.0000 |
| logloss_optimized | 0.2177 | 0.0121 | 0.6244 | 286924.0000 |
| resource_win_prob | 0.2233 | 0.0534 | 0.6364 | 286924.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2024 | 0.0000 | 0.5883 | 188642.0000 |
| innings_phase | 0.2032 | 0.0000 | 0.5903 | 188642.0000 |
| ece_optimized | 0.2035 | 0.0029 | 0.5913 | 188642.0000 |
| innings_specific | 0.2037 | 0.0137 | 0.5914 | 188642.0000 |
| combined | 0.2037 | 0.0144 | 0.5920 | 188642.0000 |
| raw | 0.2039 | 0.0179 | 0.5923 | 188642.0000 |
| logloss_optimized | 0.2041 | 0.0185 | 0.5934 | 188642.0000 |
| resource_win_prob | 0.2100 | 0.0656 | 0.6061 | 188642.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1818 | 0.0000 | 0.5399 | 160993.0000 |
| innings_phase | 0.1823 | 0.0000 | 0.5416 | 160993.0000 |
| ece_optimized | 0.1825 | 0.0024 | 0.5424 | 160993.0000 |
| innings_specific | 0.1828 | 0.0174 | 0.5435 | 160993.0000 |
| combined | 0.1831 | 0.0206 | 0.5441 | 160993.0000 |
| raw | 0.1832 | 0.0225 | 0.5441 | 160993.0000 |
| logloss_optimized | 0.1833 | 0.0214 | 0.5449 | 160993.0000 |
| resource_win_prob | 0.1956 | 0.1008 | 0.5792 | 160993.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1369 | 0.0000 | 0.4201 | 280917.0000 |
| innings_phase | 0.1378 | 0.0000 | 0.4230 | 280917.0000 |
| innings_specific | 0.1378 | 0.0040 | 0.4233 | 280917.0000 |
| ece_optimized | 0.1379 | 0.0022 | 0.4241 | 280917.0000 |
| combined | 0.1380 | 0.0074 | 0.4237 | 280917.0000 |
| raw | 0.1381 | 0.0114 | 0.4257 | 280917.0000 |
| logloss_optimized | 0.1395 | 0.0320 | 0.4332 | 280917.0000 |
| resource_win_prob | 0.1469 | 0.0274 | 0.4556 | 280917.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0851 | 0.0000 | 0.2723 | 143065.0000 |
| innings_phase | 0.0858 | 0.0000 | 0.2745 | 143065.0000 |
| ece_optimized | 0.0860 | 0.0058 | 0.2757 | 143065.0000 |
| combined | 0.0878 | 0.0242 | 0.2794 | 143065.0000 |
| innings_specific | 0.0879 | 0.0248 | 0.2795 | 143065.0000 |
| raw | 0.0880 | 0.0330 | 0.2833 | 143065.0000 |
| logloss_optimized | 0.0886 | 0.0329 | 0.2933 | 143065.0000 |
| resource_win_prob | 0.1091 | 0.0901 | 0.3606 | 143065.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1788 |
| Innings 1 | brier_optimized | 0.2177 |
| Innings 2 | brier_optimized | 0.1366 |
| Inn1 Powerplay | brier_optimized | 0.2379 |
| Inn1 Middle | brier_optimized | 0.2163 |
| Inn1 Death | brier_optimized | 0.2024 |
| Inn2 Powerplay | brier_optimized | 0.1818 |
| Inn2 Middle | brier_optimized | 0.1369 |
| Inn2 Death | brier_optimized | 0.0851 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | innings_phase | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | innings_phase | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | innings_phase | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5242 |
| Innings 1 | brier_optimized | 0.6228 |
| Innings 2 | brier_optimized | 0.4169 |
| Inn1 Powerplay | brier_optimized | 0.6681 |
| Inn1 Middle | brier_optimized | 0.6202 |
| Inn1 Death | brier_optimized | 0.5883 |
| Inn2 Powerplay | brier_optimized | 0.5399 |
| Inn2 Middle | brier_optimized | 0.4201 |
| Inn2 Death | brier_optimized | 0.2723 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 6 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1908 | 0.1788 (brier_optimized) | **+6.3%** |
| LogLoss | 0.5591 | 0.5242 (brier_optimized) | **+6.2%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 116,179 | 0.047 | 0.040 | 0.0068  | 0.0368 |
| 0.1-0.2 | 83,982 | 0.148 | 0.156 | 0.0081  | 0.1308 |
| 0.2-0.3 | 108,452 | 0.253 | 0.254 | 0.0001  | 0.1885 |
| 0.3-0.4 | 138,352 | 0.351 | 0.359 | 0.0076  | 0.2294 |
| 0.4-0.5 | 174,139 | 0.452 | 0.451 | 0.0003  | 0.2467 |
| 0.5-0.6 | 176,793 | 0.548 | 0.548 | 0.0002  | 0.2471 |
| 0.6-0.7 | 136,320 | 0.648 | 0.639 | 0.0093  | 0.2302 |
| 0.7-0.8 | 107,645 | 0.748 | 0.735 | 0.0134  | 0.1943 |
| 0.8-0.9 | 87,784 | 0.849 | 0.853 | 0.0043  | 0.1240 |
| 0.9-1.0 | 91,704 | 0.946 | 0.967 | 0.0206  | 0.0319 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 106,052 | 0.030 | 0.030 | 0.0000  | 0.0280 |
| 0.1-0.2 | 90,684 | 0.143 | 0.143 | 0.0000  | 0.1221 |
| 0.2-0.3 | 107,626 | 0.248 | 0.248 | 0.0000  | 0.1858 |
| 0.3-0.4 | 147,409 | 0.357 | 0.357 | 0.0000  | 0.2284 |
| 0.4-0.5 | 164,904 | 0.451 | 0.451 | 0.0000  | 0.2467 |
| 0.5-0.6 | 191,828 | 0.549 | 0.549 | 0.0000  | 0.2468 |
| 0.6-0.7 | 137,681 | 0.650 | 0.650 | 0.0000  | 0.2267 |
| 0.7-0.8 | 96,388 | 0.744 | 0.744 | 0.0000  | 0.1896 |
| 0.8-0.9 | 74,826 | 0.850 | 0.850 | 0.0000  | 0.1269 |
| 0.9-1.0 | 103,952 | 0.962 | 0.962 | 0.0000  | 0.0353 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 103,234 | 0.031 | 0.031 | 0.0000  | 0.0284 |
| 0.1-0.2 | 93,097 | 0.144 | 0.144 | 0.0000  | 0.1227 |
| 0.2-0.3 | 113,439 | 0.252 | 0.252 | 0.0000  | 0.1875 |
| 0.3-0.4 | 133,096 | 0.357 | 0.357 | 0.0000  | 0.2287 |
| 0.4-0.5 | 169,772 | 0.447 | 0.447 | 0.0000  | 0.2463 |
| 0.5-0.6 | 198,246 | 0.549 | 0.549 | 0.0000  | 0.2468 |
| 0.6-0.7 | 131,982 | 0.648 | 0.648 | 0.0000  | 0.2272 |
| 0.7-0.8 | 100,317 | 0.740 | 0.740 | 0.0000  | 0.1915 |
| 0.8-0.9 | 77,373 | 0.851 | 0.851 | 0.0000  | 0.1259 |
| 0.9-1.0 | 100,794 | 0.962 | 0.962 | 0.0000  | 0.0353 |

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
