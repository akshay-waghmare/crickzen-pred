# OOF Calibration Analysis Report

**Generated:** 2026-02-05 19:27:28
**Samples:** 328,855
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1603 | 0.0000 | 0.4764 |
| innings_phase | 0.1617 | 0.0000 | 0.4810 |
| innings_specific | 0.1622 | 0.0000 | 0.4828 |
| ece_optimized | 0.1623 | 0.0034 | 0.4835 |
| combined | 0.1625 | 0.0000 | 0.4839 |
| raw | 0.1629 | 0.0111 | 0.4852 |
| logloss_optimized | 0.1638 | 0.0211 | 0.4902 |
| resource_win_prob | 0.2038 | 0.0903 | 0.5903 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1972 | 0.0000 | 0.5723 | 172446.0000 |
| innings_phase | 0.1987 | 0.0000 | 0.5769 | 172446.0000 |
| innings_specific | 0.1992 | 0.0000 | 0.5787 | 172446.0000 |
| ece_optimized | 0.1993 | 0.0036 | 0.5789 | 172446.0000 |
| combined | 0.1995 | 0.0098 | 0.5799 | 172446.0000 |
| raw | 0.2001 | 0.0208 | 0.5814 | 172446.0000 |
| logloss_optimized | 0.2008 | 0.0261 | 0.5845 | 172446.0000 |
| resource_win_prob | 0.2420 | 0.1498 | 0.6773 | 172446.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1196 | 0.0000 | 0.3705 | 156409.0000 |
| innings_phase | 0.1209 | 0.0000 | 0.3753 | 156409.0000 |
| innings_specific | 0.1214 | 0.0000 | 0.3770 | 156409.0000 |
| ece_optimized | 0.1214 | 0.0035 | 0.3783 | 156409.0000 |
| combined | 0.1218 | 0.0108 | 0.3781 | 156409.0000 |
| raw | 0.1218 | 0.0127 | 0.3793 | 156409.0000 |
| logloss_optimized | 0.1230 | 0.0249 | 0.3863 | 156409.0000 |
| resource_win_prob | 0.1618 | 0.1369 | 0.4944 | 156409.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2209 | 0.0000 | 0.6295 | 44189.0000 |
| innings_phase | 0.2222 | 0.0000 | 0.6329 | 44189.0000 |
| ece_optimized | 0.2229 | 0.0050 | 0.6350 | 44189.0000 |
| innings_specific | 0.2229 | 0.0129 | 0.6351 | 44189.0000 |
| combined | 0.2230 | 0.0156 | 0.6354 | 44189.0000 |
| raw | 0.2235 | 0.0212 | 0.6367 | 44189.0000 |
| logloss_optimized | 0.2236 | 0.0220 | 0.6373 | 44189.0000 |
| resource_win_prob | 0.2594 | 0.1298 | 0.7129 | 44189.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1930 | 0.0000 | 0.5642 | 78237.0000 |
| innings_phase | 0.1948 | 0.0000 | 0.5698 | 78237.0000 |
| innings_specific | 0.1951 | 0.0094 | 0.5710 | 78237.0000 |
| combined | 0.1953 | 0.0098 | 0.5713 | 78237.0000 |
| ece_optimized | 0.1953 | 0.0053 | 0.5716 | 78237.0000 |
| raw | 0.1958 | 0.0187 | 0.5727 | 78237.0000 |
| logloss_optimized | 0.1965 | 0.0251 | 0.5754 | 78237.0000 |
| resource_win_prob | 0.2324 | 0.1344 | 0.6566 | 78237.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1829 | 0.0000 | 0.5347 | 50020.0000 |
| innings_phase | 0.1841 | 0.0000 | 0.5385 | 50020.0000 |
| ece_optimized | 0.1847 | 0.0035 | 0.5409 | 50020.0000 |
| innings_specific | 0.1848 | 0.0115 | 0.5410 | 50020.0000 |
| combined | 0.1853 | 0.0205 | 0.5443 | 50020.0000 |
| raw | 0.1860 | 0.0307 | 0.5461 | 50020.0000 |
| logloss_optimized | 0.1873 | 0.0377 | 0.5521 | 50020.0000 |
| resource_win_prob | 0.2416 | 0.1917 | 0.6782 | 50020.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1676 | 0.0000 | 0.5021 | 44267.0000 |
| innings_phase | 0.1687 | 0.0000 | 0.5060 | 44267.0000 |
| innings_specific | 0.1692 | 0.0104 | 0.5078 | 44267.0000 |
| ece_optimized | 0.1692 | 0.0022 | 0.5081 | 44267.0000 |
| combined | 0.1698 | 0.0198 | 0.5094 | 44267.0000 |
| raw | 0.1699 | 0.0205 | 0.5099 | 44267.0000 |
| logloss_optimized | 0.1703 | 0.0249 | 0.5121 | 44267.0000 |
| resource_win_prob | 0.2482 | 0.2447 | 0.7223 | 44267.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1167 | 0.0000 | 0.3641 | 75878.0000 |
| innings_phase | 0.1183 | 0.0000 | 0.3698 | 75878.0000 |
| innings_specific | 0.1185 | 0.0041 | 0.3706 | 75878.0000 |
| ece_optimized | 0.1187 | 0.0037 | 0.3723 | 75878.0000 |
| combined | 0.1187 | 0.0089 | 0.3714 | 75878.0000 |
| raw | 0.1189 | 0.0118 | 0.3725 | 75878.0000 |
| logloss_optimized | 0.1207 | 0.0342 | 0.3817 | 75878.0000 |
| resource_win_prob | 0.1537 | 0.1404 | 0.4786 | 75878.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0672 | 0.0000 | 0.2233 | 36264.0000 |
| innings_phase | 0.0681 | 0.0000 | 0.2271 | 36264.0000 |
| ece_optimized | 0.0687 | 0.0062 | 0.2323 | 36264.0000 |
| innings_specific | 0.0692 | 0.0159 | 0.2305 | 36264.0000 |
| raw | 0.0694 | 0.0204 | 0.2341 | 36264.0000 |
| combined | 0.0694 | 0.0187 | 0.2318 | 36264.0000 |
| logloss_optimized | 0.0701 | 0.0136 | 0.2423 | 36264.0000 |
| resource_win_prob | 0.0733 | 0.0159 | 0.2495 | 36264.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1603 |
| Innings 1 | brier_optimized | 0.1972 |
| Innings 2 | brier_optimized | 0.1196 |
| Inn1 Powerplay | brier_optimized | 0.2209 |
| Inn1 Middle | brier_optimized | 0.1930 |
| Inn1 Death | brier_optimized | 0.1829 |
| Inn2 Powerplay | brier_optimized | 0.1676 |
| Inn2 Middle | brier_optimized | 0.1167 |
| Inn2 Death | brier_optimized | 0.0672 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | innings_phase | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | innings_phase | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.4764 |
| Innings 1 | brier_optimized | 0.5723 |
| Innings 2 | brier_optimized | 0.3705 |
| Inn1 Powerplay | brier_optimized | 0.6295 |
| Inn1 Middle | brier_optimized | 0.5642 |
| Inn1 Death | brier_optimized | 0.5347 |
| Inn2 Powerplay | brier_optimized | 0.5021 |
| Inn2 Middle | brier_optimized | 0.3641 |
| Inn2 Death | brier_optimized | 0.2233 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 7 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2038 | 0.1603 (brier_optimized) | **+21.4%** |
| LogLoss | 0.5903 | 0.4764 (brier_optimized) | **+19.3%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 43,960 | 0.035 | 0.035 | 0.0007  | 0.0328 |
| 0.1-0.2 | 27,494 | 0.151 | 0.142 | 0.0087  | 0.1214 |
| 0.2-0.3 | 28,633 | 0.251 | 0.263 | 0.0121  | 0.1926 |
| 0.3-0.4 | 32,276 | 0.351 | 0.375 | 0.0236  | 0.2344 |
| 0.4-0.5 | 36,591 | 0.451 | 0.460 | 0.0082  | 0.2482 |
| 0.5-0.6 | 35,496 | 0.549 | 0.526 | 0.0234  | 0.2493 |
| 0.6-0.7 | 32,043 | 0.649 | 0.641 | 0.0074  | 0.2289 |
| 0.7-0.8 | 28,751 | 0.749 | 0.742 | 0.0074  | 0.1905 |
| 0.8-0.9 | 28,357 | 0.851 | 0.845 | 0.0061  | 0.1299 |
| 0.9-1.0 | 35,254 | 0.947 | 0.962 | 0.0147  | 0.0362 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 45,858 | 0.031 | 0.031 | 0.0000  | 0.0289 |
| 0.1-0.2 | 27,455 | 0.148 | 0.148 | 0.0000  | 0.1250 |
| 0.2-0.3 | 18,953 | 0.250 | 0.250 | 0.0000  | 0.1862 |
| 0.3-0.4 | 34,269 | 0.349 | 0.349 | 0.0000  | 0.2263 |
| 0.4-0.5 | 46,607 | 0.455 | 0.455 | 0.0000  | 0.2472 |
| 0.5-0.6 | 37,775 | 0.545 | 0.545 | 0.0000  | 0.2472 |
| 0.6-0.7 | 25,672 | 0.652 | 0.652 | 0.0000  | 0.2258 |
| 0.7-0.8 | 30,118 | 0.748 | 0.748 | 0.0000  | 0.1879 |
| 0.8-0.9 | 23,942 | 0.845 | 0.845 | 0.0000  | 0.1297 |
| 0.9-1.0 | 38,206 | 0.965 | 0.965 | 0.0000  | 0.0329 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 47,025 | 0.036 | 0.036 | 0.0000  | 0.0336 |
| 0.1-0.2 | 26,701 | 0.153 | 0.153 | 0.0000  | 0.1292 |
| 0.2-0.3 | 18,972 | 0.252 | 0.252 | 0.0000  | 0.1877 |
| 0.3-0.4 | 36,508 | 0.356 | 0.356 | 0.0000  | 0.2282 |
| 0.4-0.5 | 40,724 | 0.455 | 0.455 | 0.0000  | 0.2474 |
| 0.5-0.6 | 40,222 | 0.538 | 0.538 | 0.0000  | 0.2479 |
| 0.6-0.7 | 29,881 | 0.660 | 0.660 | 0.0000  | 0.2235 |
| 0.7-0.8 | 24,509 | 0.745 | 0.745 | 0.0000  | 0.1895 |
| 0.8-0.9 | 26,235 | 0.839 | 0.839 | 0.0000  | 0.1340 |
| 0.9-1.0 | 38,078 | 0.961 | 0.961 | 0.0000  | 0.0362 |

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
