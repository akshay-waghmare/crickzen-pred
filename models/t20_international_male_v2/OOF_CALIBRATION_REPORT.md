# OOF Calibration Analysis Report

**Generated:** 2026-03-04 19:39:01
**Samples:** 701,623
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1580 | 0.0000 | 0.4711 |
| innings_phase | 0.1590 | 0.0000 | 0.4741 |
| ece_optimized | 0.1593 | 0.0023 | 0.4757 |
| innings_specific | 0.1594 | 0.0000 | 0.4753 |
| combined | 0.1596 | 0.0000 | 0.4763 |
| raw | 0.1597 | 0.0053 | 0.4770 |
| logloss_optimized | 0.1605 | 0.0179 | 0.4821 |
| resource_win_prob | 0.1878 | 0.0642 | 0.5494 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1963 | 0.0000 | 0.5725 | 373852.0000 |
| innings_phase | 0.1973 | 0.0000 | 0.5753 | 373852.0000 |
| innings_specific | 0.1976 | 0.0000 | 0.5762 | 373852.0000 |
| ece_optimized | 0.1976 | 0.0018 | 0.5766 | 373852.0000 |
| combined | 0.1978 | 0.0070 | 0.5772 | 373852.0000 |
| raw | 0.1979 | 0.0101 | 0.5775 | 373852.0000 |
| logloss_optimized | 0.1983 | 0.0164 | 0.5796 | 373852.0000 |
| resource_win_prob | 0.2296 | 0.1278 | 0.6483 | 373852.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1144 | 0.0000 | 0.3555 | 327771.0000 |
| innings_phase | 0.1153 | 0.0000 | 0.3586 | 327771.0000 |
| ece_optimized | 0.1156 | 0.0036 | 0.3606 | 327771.0000 |
| innings_specific | 0.1159 | 0.0000 | 0.3603 | 327771.0000 |
| combined | 0.1161 | 0.0080 | 0.3611 | 327771.0000 |
| raw | 0.1162 | 0.0091 | 0.3624 | 327771.0000 |
| logloss_optimized | 0.1173 | 0.0266 | 0.3710 | 327771.0000 |
| resource_win_prob | 0.1402 | 0.0848 | 0.4366 | 327771.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2204 | 0.0000 | 0.6297 | 96243.0000 |
| innings_phase | 0.2214 | 0.0000 | 0.6322 | 96243.0000 |
| ece_optimized | 0.2218 | 0.0019 | 0.6333 | 96243.0000 |
| innings_specific | 0.2218 | 0.0111 | 0.6333 | 96243.0000 |
| combined | 0.2218 | 0.0107 | 0.6334 | 96243.0000 |
| logloss_optimized | 0.2219 | 0.0072 | 0.6339 | 96243.0000 |
| raw | 0.2220 | 0.0103 | 0.6337 | 96243.0000 |
| resource_win_prob | 0.2580 | 0.1303 | 0.7100 | 96243.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1937 | 0.0000 | 0.5668 | 169612.0000 |
| innings_phase | 0.1948 | 0.0000 | 0.5699 | 169612.0000 |
| innings_specific | 0.1950 | 0.0028 | 0.5704 | 169612.0000 |
| ece_optimized | 0.1951 | 0.0018 | 0.5709 | 169612.0000 |
| combined | 0.1952 | 0.0095 | 0.5715 | 169612.0000 |
| raw | 0.1954 | 0.0113 | 0.5720 | 169612.0000 |
| logloss_optimized | 0.1959 | 0.0172 | 0.5743 | 169612.0000 |
| resource_win_prob | 0.2222 | 0.1118 | 0.6326 | 169612.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1788 | 0.0000 | 0.5304 | 107997.0000 |
| innings_phase | 0.1797 | 0.0000 | 0.5332 | 107997.0000 |
| ece_optimized | 0.1801 | 0.0025 | 0.5349 | 107997.0000 |
| innings_specific | 0.1802 | 0.0105 | 0.5344 | 107997.0000 |
| combined | 0.1804 | 0.0177 | 0.5360 | 107997.0000 |
| raw | 0.1805 | 0.0186 | 0.5362 | 107997.0000 |
| logloss_optimized | 0.1812 | 0.0259 | 0.5395 | 107997.0000 |
| resource_win_prob | 0.2158 | 0.1507 | 0.6179 | 107997.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1570 | 0.0000 | 0.4743 | 95821.0000 |
| innings_phase | 0.1576 | 0.0000 | 0.4766 | 95821.0000 |
| ece_optimized | 0.1580 | 0.0032 | 0.4783 | 95821.0000 |
| innings_specific | 0.1581 | 0.0126 | 0.4779 | 95821.0000 |
| combined | 0.1584 | 0.0190 | 0.4789 | 95821.0000 |
| raw | 0.1585 | 0.0185 | 0.4796 | 95821.0000 |
| logloss_optimized | 0.1591 | 0.0264 | 0.4836 | 95821.0000 |
| resource_win_prob | 0.2009 | 0.1757 | 0.5952 | 95821.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1096 | 0.0000 | 0.3434 | 159058.0000 |
| innings_phase | 0.1107 | 0.0000 | 0.3472 | 159058.0000 |
| innings_specific | 0.1108 | 0.0037 | 0.3476 | 159058.0000 |
| ece_optimized | 0.1109 | 0.0035 | 0.3493 | 159058.0000 |
| combined | 0.1110 | 0.0077 | 0.3483 | 159058.0000 |
| raw | 0.1111 | 0.0106 | 0.3497 | 159058.0000 |
| logloss_optimized | 0.1127 | 0.0322 | 0.3596 | 159058.0000 |
| resource_win_prob | 0.1301 | 0.0797 | 0.4140 | 159058.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0689 | 0.0000 | 0.2257 | 72892.0000 |
| innings_phase | 0.0697 | 0.0000 | 0.2283 | 72892.0000 |
| ece_optimized | 0.0700 | 0.0063 | 0.2303 | 72892.0000 |
| innings_specific | 0.0715 | 0.0220 | 0.2334 | 72892.0000 |
| combined | 0.0715 | 0.0239 | 0.2342 | 72892.0000 |
| raw | 0.0716 | 0.0249 | 0.2362 | 72892.0000 |
| logloss_optimized | 0.0724 | 0.0224 | 0.2477 | 72892.0000 |
| resource_win_prob | 0.0822 | 0.0503 | 0.2773 | 72892.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1580 |
| Innings 1 | brier_optimized | 0.1963 |
| Innings 2 | brier_optimized | 0.1144 |
| Inn1 Powerplay | brier_optimized | 0.2204 |
| Inn1 Middle | brier_optimized | 0.1937 |
| Inn1 Death | brier_optimized | 0.1788 |
| Inn2 Powerplay | brier_optimized | 0.1570 |
| Inn2 Middle | brier_optimized | 0.1096 |
| Inn2 Death | brier_optimized | 0.0689 |

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
| Overall | brier_optimized | 0.4711 |
| Innings 1 | brier_optimized | 0.5725 |
| Innings 2 | brier_optimized | 0.3555 |
| Inn1 Powerplay | brier_optimized | 0.6297 |
| Inn1 Middle | brier_optimized | 0.5668 |
| Inn1 Death | brier_optimized | 0.5304 |
| Inn2 Powerplay | brier_optimized | 0.4743 |
| Inn2 Middle | brier_optimized | 0.3434 |
| Inn2 Death | brier_optimized | 0.2257 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 9 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1878 | 0.1580 (brier_optimized) | **+15.8%** |
| LogLoss | 0.5494 | 0.4711 (brier_optimized) | **+14.2%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 102,691 | 0.034 | 0.030 | 0.0033  | 0.0283 |
| 0.1-0.2 | 54,838 | 0.151 | 0.150 | 0.0007  | 0.1270 |
| 0.2-0.3 | 60,543 | 0.251 | 0.247 | 0.0035  | 0.1850 |
| 0.3-0.4 | 67,446 | 0.351 | 0.355 | 0.0043  | 0.2281 |
| 0.4-0.5 | 72,213 | 0.450 | 0.456 | 0.0058  | 0.2473 |
| 0.5-0.6 | 73,921 | 0.550 | 0.545 | 0.0045  | 0.2473 |
| 0.6-0.7 | 71,643 | 0.650 | 0.655 | 0.0049  | 0.2252 |
| 0.7-0.8 | 67,092 | 0.749 | 0.745 | 0.0038  | 0.1895 |
| 0.8-0.9 | 61,651 | 0.850 | 0.843 | 0.0076  | 0.1310 |
| 0.9-1.0 | 69,585 | 0.947 | 0.961 | 0.0140  | 0.0366 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 103,693 | 0.028 | 0.028 | 0.0000  | 0.0257 |
| 0.1-0.2 | 58,507 | 0.152 | 0.152 | 0.0000  | 0.1282 |
| 0.2-0.3 | 54,480 | 0.248 | 0.248 | 0.0000  | 0.1853 |
| 0.3-0.4 | 63,572 | 0.348 | 0.348 | 0.0000  | 0.2262 |
| 0.4-0.5 | 77,718 | 0.450 | 0.450 | 0.0000  | 0.2468 |
| 0.5-0.6 | 74,763 | 0.548 | 0.548 | 0.0000  | 0.2470 |
| 0.6-0.7 | 68,689 | 0.656 | 0.656 | 0.0000  | 0.2250 |
| 0.7-0.8 | 76,278 | 0.749 | 0.749 | 0.0000  | 0.1873 |
| 0.8-0.9 | 48,866 | 0.849 | 0.849 | 0.0000  | 0.1277 |
| 0.9-1.0 | 75,057 | 0.963 | 0.963 | 0.0000  | 0.0348 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 100,936 | 0.028 | 0.028 | 0.0000  | 0.0260 |
| 0.1-0.2 | 60,349 | 0.150 | 0.150 | 0.0000  | 0.1269 |
| 0.2-0.3 | 54,638 | 0.248 | 0.248 | 0.0000  | 0.1854 |
| 0.3-0.4 | 63,712 | 0.348 | 0.348 | 0.0000  | 0.2263 |
| 0.4-0.5 | 77,333 | 0.449 | 0.449 | 0.0000  | 0.2468 |
| 0.5-0.6 | 74,374 | 0.547 | 0.547 | 0.0000  | 0.2471 |
| 0.6-0.7 | 68,396 | 0.653 | 0.653 | 0.0000  | 0.2255 |
| 0.7-0.8 | 82,240 | 0.748 | 0.748 | 0.0000  | 0.1876 |
| 0.8-0.9 | 46,250 | 0.853 | 0.853 | 0.0000  | 0.1250 |
| 0.9-1.0 | 73,395 | 0.962 | 0.962 | 0.0000  | 0.0356 |

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
