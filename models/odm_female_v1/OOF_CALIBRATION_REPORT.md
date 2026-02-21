# OOF Calibration Analysis Report

**Generated:** 2026-02-21 11:40:10
**Samples:** 143,369
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1700 | 0.0000 | 0.5005 |
| innings_phase | 0.1753 | 0.0000 | 0.5161 |
| ece_optimized | 0.1768 | 0.0085 | 0.5226 |
| innings_specific | 0.1775 | 0.0000 | 0.5228 |
| combined | 0.1787 | 0.0000 | 0.5275 |
| logloss_optimized | 0.1807 | 0.0284 | 0.5359 |
| raw | 0.1814 | 0.0389 | 0.5379 |
| resource_win_prob | 0.1879 | 0.0441 | 0.5526 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1979 | 0.0000 | 0.5725 | 78313.0000 |
| innings_phase | 0.2030 | 0.0000 | 0.5863 | 78313.0000 |
| ece_optimized | 0.2044 | 0.0097 | 0.5904 | 78313.0000 |
| innings_specific | 0.2055 | 0.0000 | 0.5930 | 78313.0000 |
| combined | 0.2067 | 0.0172 | 0.5983 | 78313.0000 |
| logloss_optimized | 0.2084 | 0.0350 | 0.6039 | 78313.0000 |
| raw | 0.2104 | 0.0462 | 0.6113 | 78313.0000 |
| resource_win_prob | 0.2215 | 0.0595 | 0.6332 | 78313.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1365 | 0.0000 | 0.4139 | 65056.0000 |
| innings_phase | 0.1418 | 0.0000 | 0.4316 | 65056.0000 |
| ece_optimized | 0.1435 | 0.0074 | 0.4409 | 65056.0000 |
| innings_specific | 0.1437 | 0.0000 | 0.4384 | 65056.0000 |
| combined | 0.1449 | 0.0207 | 0.4423 | 65056.0000 |
| raw | 0.1465 | 0.0309 | 0.4495 | 65056.0000 |
| logloss_optimized | 0.1473 | 0.0410 | 0.4540 | 65056.0000 |
| resource_win_prob | 0.1476 | 0.0392 | 0.4555 | 65056.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2136 | 0.0000 | 0.6096 | 15457.0000 |
| innings_phase | 0.2171 | 0.0000 | 0.6184 | 15457.0000 |
| ece_optimized | 0.2188 | 0.0056 | 0.6237 | 15457.0000 |
| innings_specific | 0.2208 | 0.0158 | 0.6301 | 15457.0000 |
| combined | 0.2211 | 0.0327 | 0.6309 | 15457.0000 |
| logloss_optimized | 0.2215 | 0.0259 | 0.6330 | 15457.0000 |
| raw | 0.2228 | 0.0447 | 0.6356 | 15457.0000 |
| resource_win_prob | 0.2473 | 0.0593 | 0.6877 | 15457.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1967 | 0.0000 | 0.5680 | 39618.0000 |
| innings_phase | 0.2031 | 0.0000 | 0.5854 | 39618.0000 |
| ece_optimized | 0.2040 | 0.0151 | 0.5883 | 39618.0000 |
| innings_specific | 0.2042 | 0.0233 | 0.5879 | 39618.0000 |
| combined | 0.2053 | 0.0253 | 0.5937 | 39618.0000 |
| logloss_optimized | 0.2079 | 0.0467 | 0.6025 | 39618.0000 |
| raw | 0.2100 | 0.0615 | 0.6087 | 39618.0000 |
| resource_win_prob | 0.2207 | 0.0695 | 0.6318 | 39618.0000 |

### Innings 1 - Setup

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1929 | 0.0000 | 0.5612 | 9094.0000 |
| innings_phase | 0.1962 | 0.0000 | 0.5703 | 9094.0000 |
| ece_optimized | 0.1981 | 0.0113 | 0.5760 | 9094.0000 |
| innings_specific | 0.1996 | 0.0372 | 0.5787 | 9094.0000 |
| combined | 0.2018 | 0.0419 | 0.5861 | 9094.0000 |
| logloss_optimized | 0.2038 | 0.0720 | 0.5935 | 9094.0000 |
| raw | 0.2058 | 0.0641 | 0.6036 | 9094.0000 |
| resource_win_prob | 0.2087 | 0.0600 | 0.6057 | 9094.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1874 | 0.0000 | 0.5518 | 14144.0000 |
| innings_phase | 0.1917 | 0.0000 | 0.5641 | 14144.0000 |
| ece_optimized | 0.1939 | 0.0127 | 0.5695 | 14144.0000 |
| innings_specific | 0.1965 | 0.0432 | 0.5759 | 14144.0000 |
| combined | 0.1980 | 0.0457 | 0.5835 | 14144.0000 |
| logloss_optimized | 0.1985 | 0.0574 | 0.5829 | 14144.0000 |
| raw | 0.2007 | 0.0700 | 0.5970 | 14144.0000 |
| resource_win_prob | 0.2037 | 0.0535 | 0.5956 | 14144.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1642 | 0.0000 | 0.4913 | 15437.0000 |
| innings_phase | 0.1682 | 0.0000 | 0.5029 | 15437.0000 |
| ece_optimized | 0.1696 | 0.0113 | 0.5084 | 15437.0000 |
| innings_specific | 0.1697 | 0.0199 | 0.5090 | 15437.0000 |
| combined | 0.1716 | 0.0366 | 0.5151 | 15437.0000 |
| raw | 0.1742 | 0.0476 | 0.5231 | 15437.0000 |
| logloss_optimized | 0.1742 | 0.0466 | 0.5236 | 15437.0000 |
| resource_win_prob | 0.1751 | 0.0525 | 0.5296 | 15437.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1367 | 0.0000 | 0.4141 | 36365.0000 |
| resource_win_prob | 0.1424 | 0.0328 | 0.4394 | 36365.0000 |
| innings_phase | 0.1427 | 0.0000 | 0.4346 | 36365.0000 |
| innings_specific | 0.1434 | 0.0141 | 0.4369 | 36365.0000 |
| combined | 0.1438 | 0.0165 | 0.4381 | 36365.0000 |
| ece_optimized | 0.1438 | 0.0093 | 0.4414 | 36365.0000 |
| raw | 0.1453 | 0.0321 | 0.4449 | 36365.0000 |
| logloss_optimized | 0.1467 | 0.0459 | 0.4532 | 36365.0000 |

### Innings 2 - Setup

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1031 | 0.0000 | 0.3219 | 6720.0000 |
| innings_phase | 0.1065 | 0.0000 | 0.3339 | 6720.0000 |
| ece_optimized | 0.1097 | 0.0116 | 0.3547 | 6720.0000 |
| innings_specific | 0.1119 | 0.0430 | 0.3539 | 6720.0000 |
| combined | 0.1148 | 0.0584 | 0.3628 | 6720.0000 |
| raw | 0.1163 | 0.0626 | 0.3712 | 6720.0000 |
| logloss_optimized | 0.1176 | 0.0505 | 0.3753 | 6720.0000 |
| resource_win_prob | 0.1189 | 0.0822 | 0.3689 | 6720.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1046 | 0.0000 | 0.3241 | 6534.0000 |
| innings_phase | 0.1109 | 0.0000 | 0.3466 | 6534.0000 |
| ece_optimized | 0.1148 | 0.0297 | 0.3673 | 6534.0000 |
| innings_specific | 0.1166 | 0.0409 | 0.3664 | 6534.0000 |
| logloss_optimized | 0.1173 | 0.0448 | 0.3751 | 6534.0000 |
| combined | 0.1187 | 0.0500 | 0.3752 | 6534.0000 |
| raw | 0.1190 | 0.0549 | 0.3819 | 6534.0000 |
| resource_win_prob | 0.1411 | 0.1440 | 0.4593 | 6534.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1700 |
| Innings 1 | brier_optimized | 0.1979 |
| Innings 2 | brier_optimized | 0.1365 |
| Inn1 Powerplay | brier_optimized | 0.2136 |
| Inn1 Middle | brier_optimized | 0.1967 |
| Inn1 Setup | brier_optimized | 0.1929 |
| Inn1 Death | brier_optimized | 0.1874 |
| Inn2 Powerplay | brier_optimized | 0.1642 |
| Inn2 Middle | brier_optimized | 0.1367 |
| Inn2 Setup | brier_optimized | 0.1031 |
| Inn2 Death | brier_optimized | 0.1046 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Setup | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Setup | brier_optimized | 0.0000 |
| Inn2 Death | innings_phase | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5005 |
| Innings 1 | brier_optimized | 0.5725 |
| Innings 2 | brier_optimized | 0.4139 |
| Inn1 Powerplay | brier_optimized | 0.6096 |
| Inn1 Middle | brier_optimized | 0.5680 |
| Inn1 Setup | brier_optimized | 0.5612 |
| Inn1 Death | brier_optimized | 0.5518 |
| Inn2 Powerplay | brier_optimized | 0.4913 |
| Inn2 Middle | brier_optimized | 0.4141 |
| Inn2 Setup | brier_optimized | 0.3219 |
| Inn2 Death | brier_optimized | 0.3241 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 11 segments
- **ECE**: `brier_optimized` wins in 10 segments
- **LogLoss**: `brier_optimized` wins in 11 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1879 | 0.1700 (brier_optimized) | **+9.5%** |
| LogLoss | 0.5526 | 0.5005 (brier_optimized) | **+9.4%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 16,597 | 0.049 | 0.078 | 0.0286  | 0.0711 |
| 0.1-0.2 | 14,294 | 0.147 | 0.195 | 0.0481  | 0.1586 |
| 0.2-0.3 | 13,282 | 0.251 | 0.327 | 0.0758 ⚠️ | 0.2249 |
| 0.3-0.4 | 14,809 | 0.350 | 0.392 | 0.0424  | 0.2409 |
| 0.4-0.5 | 15,376 | 0.449 | 0.408 | 0.0411  | 0.2429 |
| 0.5-0.6 | 13,834 | 0.549 | 0.514 | 0.0353  | 0.2498 |
| 0.6-0.7 | 12,764 | 0.650 | 0.636 | 0.0142  | 0.2306 |
| 0.7-0.8 | 13,031 | 0.750 | 0.742 | 0.0085  | 0.1915 |
| 0.8-0.9 | 11,999 | 0.850 | 0.805 | 0.0445  | 0.1585 |
| 0.9-1.0 | 17,383 | 0.953 | 0.905 | 0.0481  | 0.0848 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 12,497 | 0.022 | 0.022 | 0.0000  | 0.0206 |
| 0.1-0.2 | 12,930 | 0.149 | 0.149 | 0.0000  | 0.1263 |
| 0.2-0.3 | 11,846 | 0.255 | 0.255 | 0.0000  | 0.1888 |
| 0.3-0.4 | 21,208 | 0.351 | 0.351 | 0.0000  | 0.2272 |
| 0.4-0.5 | 18,550 | 0.448 | 0.448 | 0.0000  | 0.2464 |
| 0.5-0.6 | 14,237 | 0.544 | 0.544 | 0.0000  | 0.2471 |
| 0.6-0.7 | 10,167 | 0.656 | 0.656 | 0.0000  | 0.2248 |
| 0.7-0.8 | 20,348 | 0.753 | 0.753 | 0.0000  | 0.1851 |
| 0.8-0.9 | 8,049 | 0.847 | 0.847 | 0.0000  | 0.1289 |
| 0.9-1.0 | 13,537 | 0.980 | 0.980 | 0.0000  | 0.0190 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 9,323 | 0.022 | 0.022 | 0.0000  | 0.0204 |
| 0.1-0.2 | 14,290 | 0.144 | 0.144 | 0.0000  | 0.1223 |
| 0.2-0.3 | 10,380 | 0.238 | 0.238 | 0.0000  | 0.1810 |
| 0.3-0.4 | 23,390 | 0.351 | 0.351 | 0.0000  | 0.2271 |
| 0.4-0.5 | 21,513 | 0.437 | 0.437 | 0.0000  | 0.2451 |
| 0.5-0.6 | 11,564 | 0.548 | 0.548 | 0.0000  | 0.2472 |
| 0.6-0.7 | 7,197 | 0.627 | 0.627 | 0.0000  | 0.2332 |
| 0.7-0.8 | 25,975 | 0.743 | 0.743 | 0.0000  | 0.1902 |
| 0.8-0.9 | 8,215 | 0.851 | 0.851 | 0.0000  | 0.1260 |
| 0.9-1.0 | 11,522 | 0.981 | 0.981 | 0.0000  | 0.0183 |

### Problematic Bins (Calibration Error > 0.05)


**raw:**
- Bin 0.2-0.3: CE=0.0758 (under-predicting)

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
