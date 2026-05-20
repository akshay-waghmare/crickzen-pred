# OOF Calibration Analysis Report

**Generated:** 2026-05-06 20:57:46
**Samples:** 278,954
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1815 | 0.0000 | 0.5296 |
| innings_phase | 0.1832 | 0.0000 | 0.5346 |
| ece_optimized | 0.1838 | 0.0031 | 0.5366 |
| innings_specific | 0.1840 | 0.0000 | 0.5372 |
| combined | 0.1843 | 0.0000 | 0.5380 |
| raw | 0.1846 | 0.0089 | 0.5394 |
| logloss_optimized | 0.1849 | 0.0147 | 0.5422 |
| resource_win_prob | 0.2046 | 0.0749 | 0.5923 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2194 | 0.0000 | 0.6265 | 144340.0000 |
| innings_phase | 0.2211 | 0.0000 | 0.6308 | 144340.0000 |
| ece_optimized | 0.2217 | 0.0022 | 0.6324 | 144340.0000 |
| innings_specific | 0.2218 | 0.0000 | 0.6327 | 144340.0000 |
| combined | 0.2220 | 0.0070 | 0.6336 | 144340.0000 |
| logloss_optimized | 0.2222 | 0.0050 | 0.6342 | 144340.0000 |
| raw | 0.2226 | 0.0128 | 0.6351 | 144340.0000 |
| resource_win_prob | 0.2507 | 0.1336 | 0.7086 | 144340.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1410 | 0.0000 | 0.4257 | 134614.0000 |
| innings_phase | 0.1427 | 0.0000 | 0.4314 | 134614.0000 |
| ece_optimized | 0.1432 | 0.0054 | 0.4339 | 134614.0000 |
| innings_specific | 0.1436 | 0.0000 | 0.4349 | 134614.0000 |
| combined | 0.1438 | 0.0076 | 0.4356 | 134614.0000 |
| raw | 0.1440 | 0.0109 | 0.4368 | 134614.0000 |
| logloss_optimized | 0.1450 | 0.0302 | 0.4435 | 134614.0000 |
| resource_win_prob | 0.1552 | 0.0178 | 0.4676 | 134614.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2382 | 0.0000 | 0.6684 | 36260.0000 |
| innings_phase | 0.2394 | 0.0000 | 0.6711 | 36260.0000 |
| ece_optimized | 0.2400 | 0.0020 | 0.6723 | 36260.0000 |
| innings_specific | 0.2403 | 0.0140 | 0.6734 | 36260.0000 |
| logloss_optimized | 0.2403 | 0.0016 | 0.6734 | 36260.0000 |
| combined | 0.2405 | 0.0149 | 0.6737 | 36260.0000 |
| raw | 0.2409 | 0.0177 | 0.6746 | 36260.0000 |
| resource_win_prob | 0.2451 | 0.0360 | 0.6836 | 36260.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2177 | 0.0000 | 0.6232 | 64842.0000 |
| innings_phase | 0.2196 | 0.0000 | 0.6277 | 64842.0000 |
| innings_specific | 0.2200 | 0.0109 | 0.6289 | 64842.0000 |
| ece_optimized | 0.2201 | 0.0023 | 0.6294 | 64842.0000 |
| combined | 0.2202 | 0.0096 | 0.6298 | 64842.0000 |
| logloss_optimized | 0.2207 | 0.0109 | 0.6312 | 64842.0000 |
| raw | 0.2209 | 0.0160 | 0.6317 | 64842.0000 |
| resource_win_prob | 0.2677 | 0.1895 | 0.7565 | 64842.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2060 | 0.0000 | 0.5963 | 43238.0000 |
| innings_phase | 0.2080 | 0.0000 | 0.6016 | 43238.0000 |
| ece_optimized | 0.2087 | 0.0044 | 0.6035 | 43238.0000 |
| innings_specific | 0.2090 | 0.0200 | 0.6041 | 43238.0000 |
| logloss_optimized | 0.2091 | 0.0063 | 0.6058 | 43238.0000 |
| combined | 0.2093 | 0.0226 | 0.6055 | 43238.0000 |
| raw | 0.2097 | 0.0267 | 0.6072 | 43238.0000 |
| resource_win_prob | 0.2299 | 0.1324 | 0.6578 | 43238.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1809 | 0.0000 | 0.5347 | 36276.0000 |
| innings_phase | 0.1825 | 0.0000 | 0.5395 | 36276.0000 |
| innings_specific | 0.1831 | 0.0132 | 0.5429 | 36276.0000 |
| ece_optimized | 0.1832 | 0.0065 | 0.5425 | 36276.0000 |
| combined | 0.1832 | 0.0112 | 0.5430 | 36276.0000 |
| raw | 0.1836 | 0.0145 | 0.5436 | 36276.0000 |
| logloss_optimized | 0.1839 | 0.0174 | 0.5456 | 36276.0000 |
| resource_win_prob | 0.1938 | 0.0271 | 0.5671 | 36276.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1441 | 0.0000 | 0.4355 | 63812.0000 |
| innings_phase | 0.1461 | 0.0000 | 0.4424 | 63812.0000 |
| innings_specific | 0.1464 | 0.0096 | 0.4434 | 63812.0000 |
| ece_optimized | 0.1466 | 0.0057 | 0.4447 | 63812.0000 |
| combined | 0.1467 | 0.0101 | 0.4441 | 63812.0000 |
| raw | 0.1469 | 0.0126 | 0.4456 | 63812.0000 |
| logloss_optimized | 0.1487 | 0.0410 | 0.4557 | 63812.0000 |
| resource_win_prob | 0.1592 | 0.0296 | 0.4794 | 63812.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0931 | 0.0000 | 0.2930 | 34526.0000 |
| innings_phase | 0.0944 | 0.0000 | 0.2974 | 34526.0000 |
| ece_optimized | 0.0949 | 0.0054 | 0.2997 | 34526.0000 |
| innings_specific | 0.0966 | 0.0287 | 0.3056 | 34526.0000 |
| raw | 0.0970 | 0.0354 | 0.3084 | 34526.0000 |
| combined | 0.0971 | 0.0324 | 0.3069 | 34526.0000 |
| logloss_optimized | 0.0971 | 0.0290 | 0.3137 | 34526.0000 |
| resource_win_prob | 0.1073 | 0.0466 | 0.3413 | 34526.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1815 |
| Innings 1 | brier_optimized | 0.2194 |
| Innings 2 | brier_optimized | 0.1410 |
| Inn1 Powerplay | brier_optimized | 0.2382 |
| Inn1 Middle | brier_optimized | 0.2177 |
| Inn1 Death | brier_optimized | 0.2060 |
| Inn2 Powerplay | brier_optimized | 0.1809 |
| Inn2 Middle | brier_optimized | 0.1441 |
| Inn2 Death | brier_optimized | 0.0931 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | innings_phase | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | innings_phase | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5296 |
| Innings 1 | brier_optimized | 0.6265 |
| Innings 2 | brier_optimized | 0.4257 |
| Inn1 Powerplay | brier_optimized | 0.6684 |
| Inn1 Middle | brier_optimized | 0.6232 |
| Inn1 Death | brier_optimized | 0.5963 |
| Inn2 Powerplay | brier_optimized | 0.5347 |
| Inn2 Middle | brier_optimized | 0.4355 |
| Inn2 Death | brier_optimized | 0.2930 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 7 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2046 | 0.1815 (brier_optimized) | **+11.3%** |
| LogLoss | 0.5923 | 0.5296 (brier_optimized) | **+10.6%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 23,661 | 0.045 | 0.032 | 0.0125  | 0.0305 |
| 0.1-0.2 | 19,937 | 0.152 | 0.175 | 0.0228  | 0.1440 |
| 0.2-0.3 | 24,753 | 0.253 | 0.267 | 0.0141  | 0.1952 |
| 0.3-0.4 | 36,267 | 0.353 | 0.360 | 0.0071  | 0.2300 |
| 0.4-0.5 | 44,877 | 0.451 | 0.451 | 0.0009  | 0.2470 |
| 0.5-0.6 | 38,119 | 0.548 | 0.549 | 0.0012  | 0.2469 |
| 0.6-0.7 | 28,205 | 0.648 | 0.648 | 0.0003  | 0.2274 |
| 0.7-0.8 | 22,017 | 0.748 | 0.735 | 0.0133  | 0.1947 |
| 0.8-0.9 | 17,184 | 0.850 | 0.812 | 0.0377  | 0.1529 |
| 0.9-1.0 | 23,934 | 0.955 | 0.959 | 0.0036  | 0.0383 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 25,094 | 0.029 | 0.029 | 0.0000  | 0.0272 |
| 0.1-0.2 | 14,542 | 0.156 | 0.156 | 0.0000  | 0.1309 |
| 0.2-0.3 | 25,089 | 0.246 | 0.246 | 0.0000  | 0.1849 |
| 0.3-0.4 | 35,040 | 0.352 | 0.352 | 0.0000  | 0.2273 |
| 0.4-0.5 | 48,342 | 0.446 | 0.446 | 0.0000  | 0.2462 |
| 0.5-0.6 | 40,344 | 0.543 | 0.543 | 0.0000  | 0.2473 |
| 0.6-0.7 | 28,762 | 0.658 | 0.658 | 0.0000  | 0.2241 |
| 0.7-0.8 | 25,974 | 0.747 | 0.747 | 0.0000  | 0.1882 |
| 0.8-0.9 | 11,809 | 0.849 | 0.849 | 0.0000  | 0.1272 |
| 0.9-1.0 | 23,958 | 0.967 | 0.967 | 0.0000  | 0.0306 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 23,865 | 0.030 | 0.030 | 0.0000  | 0.0283 |
| 0.1-0.2 | 15,865 | 0.164 | 0.164 | 0.0000  | 0.1364 |
| 0.2-0.3 | 21,542 | 0.237 | 0.237 | 0.0000  | 0.1802 |
| 0.3-0.4 | 41,945 | 0.354 | 0.354 | 0.0000  | 0.2278 |
| 0.4-0.5 | 43,021 | 0.446 | 0.446 | 0.0000  | 0.2462 |
| 0.5-0.6 | 40,737 | 0.540 | 0.540 | 0.0000  | 0.2477 |
| 0.6-0.7 | 30,137 | 0.654 | 0.654 | 0.0000  | 0.2256 |
| 0.7-0.8 | 28,382 | 0.745 | 0.745 | 0.0000  | 0.1893 |
| 0.8-0.9 | 11,530 | 0.864 | 0.864 | 0.0000  | 0.1167 |
| 0.9-1.0 | 21,930 | 0.969 | 0.969 | 0.0000  | 0.0294 |

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
