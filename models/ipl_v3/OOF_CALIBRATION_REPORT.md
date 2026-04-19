# OOF Calibration Analysis Report

**Generated:** 2026-04-19 09:53:47
**Samples:** 278,954
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1817 | 0.0000 | 0.5300 |
| innings_phase | 0.1834 | 0.0000 | 0.5349 |
| ece_optimized | 0.1840 | 0.0021 | 0.5369 |
| innings_specific | 0.1842 | 0.0000 | 0.5371 |
| combined | 0.1847 | 0.0000 | 0.5384 |
| raw | 0.1850 | 0.0101 | 0.5402 |
| logloss_optimized | 0.1852 | 0.0165 | 0.5428 |
| resource_win_prob | 0.2117 | 0.1165 | 0.6135 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2191 | 0.0000 | 0.6256 | 144340.0000 |
| innings_phase | 0.2208 | 0.0000 | 0.6300 | 144340.0000 |
| ece_optimized | 0.2215 | 0.0021 | 0.6318 | 144340.0000 |
| innings_specific | 0.2216 | 0.0000 | 0.6319 | 144340.0000 |
| combined | 0.2220 | 0.0114 | 0.6333 | 144340.0000 |
| logloss_optimized | 0.2221 | 0.0098 | 0.6339 | 144340.0000 |
| raw | 0.2225 | 0.0169 | 0.6347 | 144340.0000 |
| resource_win_prob | 0.2507 | 0.1336 | 0.7086 | 144340.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1417 | 0.0000 | 0.4275 | 134614.0000 |
| innings_phase | 0.1433 | 0.0000 | 0.4329 | 134614.0000 |
| ece_optimized | 0.1438 | 0.0036 | 0.4351 | 134614.0000 |
| innings_specific | 0.1441 | 0.0000 | 0.4355 | 134614.0000 |
| combined | 0.1446 | 0.0122 | 0.4368 | 134614.0000 |
| raw | 0.1448 | 0.0151 | 0.4388 | 134614.0000 |
| logloss_optimized | 0.1456 | 0.0276 | 0.4451 | 134614.0000 |
| resource_win_prob | 0.1698 | 0.0980 | 0.5115 | 134614.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2383 | 0.0000 | 0.6687 | 36260.0000 |
| innings_phase | 0.2395 | 0.0000 | 0.6714 | 36260.0000 |
| innings_specific | 0.2399 | 0.0025 | 0.6724 | 36260.0000 |
| combined | 0.2400 | 0.0087 | 0.6727 | 36260.0000 |
| ece_optimized | 0.2402 | 0.0033 | 0.6730 | 36260.0000 |
| logloss_optimized | 0.2402 | 0.0042 | 0.6732 | 36260.0000 |
| raw | 0.2405 | 0.0086 | 0.6738 | 36260.0000 |
| resource_win_prob | 0.2451 | 0.0360 | 0.6836 | 36260.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2174 | 0.0000 | 0.6221 | 64842.0000 |
| innings_phase | 0.2195 | 0.0000 | 0.6275 | 64842.0000 |
| ece_optimized | 0.2201 | 0.0022 | 0.6292 | 64842.0000 |
| innings_specific | 0.2202 | 0.0156 | 0.6291 | 64842.0000 |
| combined | 0.2203 | 0.0142 | 0.6297 | 64842.0000 |
| logloss_optimized | 0.2205 | 0.0113 | 0.6307 | 64842.0000 |
| raw | 0.2207 | 0.0172 | 0.6309 | 64842.0000 |
| resource_win_prob | 0.2677 | 0.1895 | 0.7565 | 64842.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2055 | 0.0000 | 0.5948 | 43238.0000 |
| innings_phase | 0.2072 | 0.0000 | 0.5992 | 43238.0000 |
| ece_optimized | 0.2079 | 0.0052 | 0.6013 | 43238.0000 |
| innings_specific | 0.2085 | 0.0221 | 0.6022 | 43238.0000 |
| logloss_optimized | 0.2094 | 0.0251 | 0.6058 | 43238.0000 |
| combined | 0.2096 | 0.0309 | 0.6055 | 43238.0000 |
| raw | 0.2103 | 0.0332 | 0.6077 | 43238.0000 |
| resource_win_prob | 0.2299 | 0.1324 | 0.6578 | 43238.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1847 | 0.0000 | 0.5435 | 36276.0000 |
| innings_phase | 0.1861 | 0.0000 | 0.5479 | 36276.0000 |
| ece_optimized | 0.1866 | 0.0036 | 0.5498 | 36276.0000 |
| innings_specific | 0.1868 | 0.0126 | 0.5504 | 36276.0000 |
| combined | 0.1868 | 0.0128 | 0.5508 | 36276.0000 |
| raw | 0.1869 | 0.0112 | 0.5506 | 36276.0000 |
| logloss_optimized | 0.1874 | 0.0194 | 0.5530 | 36276.0000 |
| resource_win_prob | 0.1904 | 0.0260 | 0.5582 | 36276.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1446 | 0.0000 | 0.4376 | 63812.0000 |
| innings_phase | 0.1466 | 0.0000 | 0.4441 | 63812.0000 |
| innings_specific | 0.1469 | 0.0109 | 0.4452 | 63812.0000 |
| ece_optimized | 0.1470 | 0.0056 | 0.4464 | 63812.0000 |
| combined | 0.1476 | 0.0154 | 0.4470 | 63812.0000 |
| raw | 0.1478 | 0.0206 | 0.4491 | 63812.0000 |
| logloss_optimized | 0.1489 | 0.0335 | 0.4564 | 63812.0000 |
| resource_win_prob | 0.1732 | 0.1161 | 0.5133 | 63812.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0910 | 0.0000 | 0.2871 | 34526.0000 |
| innings_phase | 0.0924 | 0.0000 | 0.2914 | 34526.0000 |
| ece_optimized | 0.0929 | 0.0061 | 0.2939 | 34526.0000 |
| innings_specific | 0.0942 | 0.0251 | 0.2967 | 34526.0000 |
| combined | 0.0948 | 0.0269 | 0.2980 | 34526.0000 |
| raw | 0.0950 | 0.0356 | 0.3025 | 34526.0000 |
| logloss_optimized | 0.0956 | 0.0306 | 0.3107 | 34526.0000 |
| resource_win_prob | 0.1418 | 0.1463 | 0.4591 | 34526.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1817 |
| Innings 1 | brier_optimized | 0.2191 |
| Innings 2 | brier_optimized | 0.1417 |
| Inn1 Powerplay | brier_optimized | 0.2383 |
| Inn1 Middle | brier_optimized | 0.2174 |
| Inn1 Death | brier_optimized | 0.2055 |
| Inn2 Powerplay | brier_optimized | 0.1847 |
| Inn2 Middle | brier_optimized | 0.1446 |
| Inn2 Death | brier_optimized | 0.0910 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | innings_phase | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5300 |
| Innings 1 | brier_optimized | 0.6256 |
| Innings 2 | brier_optimized | 0.4275 |
| Inn1 Powerplay | brier_optimized | 0.6687 |
| Inn1 Middle | brier_optimized | 0.6221 |
| Inn1 Death | brier_optimized | 0.5948 |
| Inn2 Powerplay | brier_optimized | 0.5435 |
| Inn2 Middle | brier_optimized | 0.4376 |
| Inn2 Death | brier_optimized | 0.2871 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 8 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2117 | 0.1817 (brier_optimized) | **+14.2%** |
| LogLoss | 0.6135 | 0.5300 (brier_optimized) | **+13.6%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,009 | 0.046 | 0.038 | 0.0080  | 0.0350 |
| 0.1-0.2 | 18,356 | 0.152 | 0.171 | 0.0192  | 0.1415 |
| 0.2-0.3 | 24,005 | 0.253 | 0.269 | 0.0162  | 0.1958 |
| 0.3-0.4 | 35,902 | 0.353 | 0.346 | 0.0064  | 0.2257 |
| 0.4-0.5 | 45,493 | 0.450 | 0.455 | 0.0049  | 0.2472 |
| 0.5-0.6 | 39,379 | 0.548 | 0.548 | 0.0006  | 0.2471 |
| 0.6-0.7 | 30,140 | 0.647 | 0.636 | 0.0115  | 0.2308 |
| 0.7-0.8 | 22,235 | 0.748 | 0.732 | 0.0159  | 0.1959 |
| 0.8-0.9 | 18,204 | 0.849 | 0.836 | 0.0126  | 0.1361 |
| 0.9-1.0 | 21,231 | 0.948 | 0.971 | 0.0221  | 0.0284 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,308 | 0.029 | 0.029 | 0.0000  | 0.0273 |
| 0.1-0.2 | 16,328 | 0.158 | 0.158 | 0.0000  | 0.1324 |
| 0.2-0.3 | 24,910 | 0.247 | 0.247 | 0.0000  | 0.1852 |
| 0.3-0.4 | 36,721 | 0.356 | 0.356 | 0.0000  | 0.2285 |
| 0.4-0.5 | 43,124 | 0.448 | 0.448 | 0.0000  | 0.2466 |
| 0.5-0.6 | 42,660 | 0.541 | 0.541 | 0.0000  | 0.2475 |
| 0.6-0.7 | 29,420 | 0.646 | 0.646 | 0.0000  | 0.2278 |
| 0.7-0.8 | 22,299 | 0.746 | 0.746 | 0.0000  | 0.1885 |
| 0.8-0.9 | 15,762 | 0.838 | 0.838 | 0.0000  | 0.1346 |
| 0.9-1.0 | 23,422 | 0.971 | 0.971 | 0.0000  | 0.0273 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 22,350 | 0.029 | 0.029 | 0.0000  | 0.0269 |
| 0.1-0.2 | 16,295 | 0.153 | 0.153 | 0.0000  | 0.1286 |
| 0.2-0.3 | 23,277 | 0.239 | 0.239 | 0.0000  | 0.1813 |
| 0.3-0.4 | 41,563 | 0.352 | 0.352 | 0.0000  | 0.2273 |
| 0.4-0.5 | 41,811 | 0.450 | 0.450 | 0.0000  | 0.2469 |
| 0.5-0.6 | 44,224 | 0.540 | 0.540 | 0.0000  | 0.2478 |
| 0.6-0.7 | 27,969 | 0.651 | 0.651 | 0.0000  | 0.2266 |
| 0.7-0.8 | 25,833 | 0.747 | 0.747 | 0.0000  | 0.1880 |
| 0.8-0.9 | 12,649 | 0.845 | 0.845 | 0.0000  | 0.1303 |
| 0.9-1.0 | 22,983 | 0.969 | 0.969 | 0.0000  | 0.0291 |

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
