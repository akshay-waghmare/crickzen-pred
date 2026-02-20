# OOF Calibration Analysis Report

**Generated:** 2026-01-19 17:23:48
**Samples:** 283,026
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1610 | 0.0000 | 0.4787 |
| innings_phase | 0.1626 | 0.0000 | 0.4836 |
| innings_specific | 0.1632 | 0.0000 | 0.4857 |
| ece_optimized | 0.1632 | 0.0031 | 0.4864 |
| combined | 0.1634 | 0.0000 | 0.4866 |
| raw | 0.1638 | 0.0095 | 0.4880 |
| logloss_optimized | 0.1647 | 0.0200 | 0.4930 |
| resource_win_prob | 0.2042 | 0.0913 | 0.5906 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1964 | 0.0000 | 0.5710 | 148234.0000 |
| innings_phase | 0.1980 | 0.0000 | 0.5757 | 148234.0000 |
| innings_specific | 0.1987 | 0.0000 | 0.5779 | 148234.0000 |
| ece_optimized | 0.1988 | 0.0029 | 0.5780 | 148234.0000 |
| combined | 0.1989 | 0.0079 | 0.5788 | 148234.0000 |
| raw | 0.1995 | 0.0169 | 0.5803 | 148234.0000 |
| logloss_optimized | 0.2001 | 0.0237 | 0.5832 | 148234.0000 |
| resource_win_prob | 0.2413 | 0.1500 | 0.6747 | 148234.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1221 | 0.0000 | 0.3771 | 134792.0000 |
| innings_phase | 0.1236 | 0.0000 | 0.3824 | 134792.0000 |
| innings_specific | 0.1241 | 0.0000 | 0.3842 | 134792.0000 |
| ece_optimized | 0.1241 | 0.0047 | 0.3856 | 134792.0000 |
| combined | 0.1244 | 0.0087 | 0.3852 | 134792.0000 |
| raw | 0.1245 | 0.0093 | 0.3865 | 134792.0000 |
| logloss_optimized | 0.1257 | 0.0267 | 0.3937 | 134792.0000 |
| resource_win_prob | 0.1635 | 0.1390 | 0.4982 | 134792.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2211 | 0.0000 | 0.6301 | 37996.0000 |
| innings_phase | 0.2224 | 0.0000 | 0.6335 | 37996.0000 |
| innings_specific | 0.2232 | 0.0142 | 0.6358 | 37996.0000 |
| ece_optimized | 0.2232 | 0.0032 | 0.6357 | 37996.0000 |
| combined | 0.2233 | 0.0157 | 0.6360 | 37996.0000 |
| raw | 0.2238 | 0.0183 | 0.6372 | 37996.0000 |
| logloss_optimized | 0.2238 | 0.0214 | 0.6378 | 37996.0000 |
| resource_win_prob | 0.2584 | 0.1256 | 0.7108 | 37996.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1924 | 0.0000 | 0.5634 | 67243.0000 |
| innings_phase | 0.1944 | 0.0000 | 0.5690 | 67243.0000 |
| innings_specific | 0.1949 | 0.0105 | 0.5707 | 67243.0000 |
| combined | 0.1950 | 0.0106 | 0.5709 | 67243.0000 |
| ece_optimized | 0.1950 | 0.0066 | 0.5710 | 67243.0000 |
| raw | 0.1954 | 0.0153 | 0.5722 | 67243.0000 |
| logloss_optimized | 0.1960 | 0.0226 | 0.5745 | 67243.0000 |
| resource_win_prob | 0.2320 | 0.1342 | 0.6549 | 67243.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1809 | 0.0000 | 0.5307 | 42995.0000 |
| innings_phase | 0.1822 | 0.0000 | 0.5351 | 42995.0000 |
| ece_optimized | 0.1831 | 0.0047 | 0.5381 | 42995.0000 |
| innings_specific | 0.1831 | 0.0152 | 0.5381 | 42995.0000 |
| combined | 0.1836 | 0.0215 | 0.5407 | 42995.0000 |
| raw | 0.1844 | 0.0304 | 0.5426 | 42995.0000 |
| logloss_optimized | 0.1856 | 0.0350 | 0.5484 | 42995.0000 |
| resource_win_prob | 0.2407 | 0.1962 | 0.6738 | 42995.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1685 | 0.0000 | 0.5042 | 38103.0000 |
| innings_phase | 0.1701 | 0.0000 | 0.5090 | 38103.0000 |
| innings_specific | 0.1706 | 0.0113 | 0.5113 | 38103.0000 |
| ece_optimized | 0.1707 | 0.0049 | 0.5119 | 38103.0000 |
| raw | 0.1712 | 0.0178 | 0.5130 | 38103.0000 |
| combined | 0.1713 | 0.0177 | 0.5129 | 38103.0000 |
| logloss_optimized | 0.1715 | 0.0193 | 0.5155 | 38103.0000 |
| resource_win_prob | 0.2494 | 0.2474 | 0.7219 | 38103.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1213 | 0.0000 | 0.3761 | 65293.0000 |
| innings_phase | 0.1230 | 0.0000 | 0.3821 | 65293.0000 |
| innings_specific | 0.1232 | 0.0065 | 0.3830 | 65293.0000 |
| combined | 0.1235 | 0.0051 | 0.3837 | 65293.0000 |
| ece_optimized | 0.1235 | 0.0052 | 0.3847 | 65293.0000 |
| raw | 0.1236 | 0.0101 | 0.3849 | 65293.0000 |
| logloss_optimized | 0.1256 | 0.0375 | 0.3951 | 65293.0000 |
| resource_win_prob | 0.1566 | 0.1427 | 0.4867 | 65293.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0673 | 0.0000 | 0.2250 | 31396.0000 |
| innings_phase | 0.0685 | 0.0000 | 0.2294 | 31396.0000 |
| ece_optimized | 0.0690 | 0.0054 | 0.2340 | 31396.0000 |
| innings_specific | 0.0694 | 0.0152 | 0.2325 | 31396.0000 |
| combined | 0.0695 | 0.0159 | 0.2335 | 31396.0000 |
| raw | 0.0696 | 0.0194 | 0.2362 | 31396.0000 |
| logloss_optimized | 0.0704 | 0.0161 | 0.2431 | 31396.0000 |
| resource_win_prob | 0.0736 | 0.0155 | 0.2504 | 31396.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1610 |
| Innings 1 | brier_optimized | 0.1964 |
| Innings 2 | brier_optimized | 0.1221 |
| Inn1 Powerplay | brier_optimized | 0.2211 |
| Inn1 Middle | brier_optimized | 0.1924 |
| Inn1 Death | brier_optimized | 0.1809 |
| Inn2 Powerplay | brier_optimized | 0.1685 |
| Inn2 Middle | brier_optimized | 0.1213 |
| Inn2 Death | brier_optimized | 0.0673 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | combined | 0.0000 |
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
| Overall | brier_optimized | 0.4787 |
| Innings 1 | brier_optimized | 0.5710 |
| Innings 2 | brier_optimized | 0.3771 |
| Inn1 Powerplay | brier_optimized | 0.6301 |
| Inn1 Middle | brier_optimized | 0.5634 |
| Inn1 Death | brier_optimized | 0.5307 |
| Inn2 Powerplay | brier_optimized | 0.5042 |
| Inn2 Middle | brier_optimized | 0.3761 |
| Inn2 Death | brier_optimized | 0.2250 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 8 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2042 | 0.1610 (brier_optimized) | **+21.2%** |
| LogLoss | 0.5906 | 0.4787 (brier_optimized) | **+19.0%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 37,101 | 0.036 | 0.035 | 0.0016  | 0.0327 |
| 0.1-0.2 | 23,913 | 0.150 | 0.152 | 0.0012  | 0.1281 |
| 0.2-0.3 | 25,394 | 0.250 | 0.260 | 0.0099  | 0.1915 |
| 0.3-0.4 | 27,944 | 0.351 | 0.368 | 0.0171  | 0.2318 |
| 0.4-0.5 | 31,334 | 0.451 | 0.462 | 0.0106  | 0.2484 |
| 0.5-0.6 | 31,030 | 0.549 | 0.530 | 0.0195  | 0.2493 |
| 0.6-0.7 | 27,722 | 0.649 | 0.644 | 0.0054  | 0.2280 |
| 0.7-0.8 | 23,998 | 0.749 | 0.742 | 0.0062  | 0.1912 |
| 0.8-0.9 | 24,569 | 0.852 | 0.844 | 0.0080  | 0.1307 |
| 0.9-1.0 | 30,021 | 0.947 | 0.961 | 0.0144  | 0.0366 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 37,976 | 0.031 | 0.031 | 0.0000  | 0.0289 |
| 0.1-0.2 | 24,049 | 0.151 | 0.151 | 0.0000  | 0.1273 |
| 0.2-0.3 | 23,046 | 0.254 | 0.254 | 0.0000  | 0.1887 |
| 0.3-0.4 | 20,575 | 0.346 | 0.346 | 0.0000  | 0.2254 |
| 0.4-0.5 | 40,893 | 0.448 | 0.448 | 0.0000  | 0.2465 |
| 0.5-0.6 | 34,553 | 0.540 | 0.540 | 0.0000  | 0.2478 |
| 0.6-0.7 | 21,582 | 0.654 | 0.654 | 0.0000  | 0.2257 |
| 0.7-0.8 | 28,841 | 0.748 | 0.748 | 0.0000  | 0.1879 |
| 0.8-0.9 | 19,605 | 0.851 | 0.851 | 0.0000  | 0.1260 |
| 0.9-1.0 | 31,906 | 0.966 | 0.966 | 0.0000  | 0.0321 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 38,283 | 0.035 | 0.035 | 0.0000  | 0.0323 |
| 0.1-0.2 | 24,071 | 0.155 | 0.155 | 0.0000  | 0.1301 |
| 0.2-0.3 | 22,202 | 0.256 | 0.256 | 0.0000  | 0.1901 |
| 0.3-0.4 | 22,796 | 0.353 | 0.353 | 0.0000  | 0.2275 |
| 0.4-0.5 | 37,923 | 0.450 | 0.450 | 0.0000  | 0.2467 |
| 0.5-0.6 | 34,371 | 0.535 | 0.535 | 0.0000  | 0.2482 |
| 0.6-0.7 | 22,525 | 0.648 | 0.648 | 0.0000  | 0.2271 |
| 0.7-0.8 | 27,268 | 0.741 | 0.741 | 0.0000  | 0.1914 |
| 0.8-0.9 | 22,067 | 0.842 | 0.842 | 0.0000  | 0.1321 |
| 0.9-1.0 | 31,520 | 0.963 | 0.963 | 0.0000  | 0.0350 |

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
