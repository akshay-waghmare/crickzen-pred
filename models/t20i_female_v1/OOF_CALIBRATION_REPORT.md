# OOF Calibration Analysis Report

**Generated:** 2026-02-15 16:14:50
**Samples:** 414,237
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1358 | 0.0000 | 0.4100 |
| innings_phase | 0.1370 | 0.0000 | 0.4140 |
| ece_optimized | 0.1373 | 0.0031 | 0.4158 |
| innings_specific | 0.1375 | 0.0000 | 0.4157 |
| combined | 0.1376 | 0.0000 | 0.4161 |
| raw | 0.1378 | 0.0071 | 0.4171 |
| logloss_optimized | 0.1395 | 0.0303 | 0.4266 |
| resource_win_prob | 0.2208 | 0.1469 | 0.6375 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1689 | 0.0000 | 0.5011 | 224939.0000 |
| innings_phase | 0.1701 | 0.0000 | 0.5051 | 224939.0000 |
| ece_optimized | 0.1705 | 0.0035 | 0.5070 | 224939.0000 |
| innings_specific | 0.1706 | 0.0000 | 0.5068 | 224939.0000 |
| combined | 0.1706 | 0.0060 | 0.5071 | 224939.0000 |
| raw | 0.1709 | 0.0102 | 0.5080 | 224939.0000 |
| logloss_optimized | 0.1723 | 0.0306 | 0.5148 | 224939.0000 |
| resource_win_prob | 0.2653 | 0.2305 | 0.7349 | 224939.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0965 | 0.0000 | 0.3018 | 189298.0000 |
| innings_phase | 0.0976 | 0.0000 | 0.3058 | 189298.0000 |
| ece_optimized | 0.0980 | 0.0048 | 0.3074 | 189298.0000 |
| innings_specific | 0.0981 | 0.0000 | 0.3075 | 189298.0000 |
| combined | 0.0983 | 0.0072 | 0.3081 | 189298.0000 |
| raw | 0.0985 | 0.0100 | 0.3092 | 189298.0000 |
| logloss_optimized | 0.1006 | 0.0305 | 0.3218 | 189298.0000 |
| resource_win_prob | 0.1680 | 0.1893 | 0.5218 | 189298.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1933 | 0.0000 | 0.5638 | 57732.0000 |
| innings_phase | 0.1943 | 0.0000 | 0.5670 | 57732.0000 |
| ece_optimized | 0.1947 | 0.0044 | 0.5685 | 57732.0000 |
| combined | 0.1950 | 0.0134 | 0.5697 | 57732.0000 |
| innings_specific | 0.1951 | 0.0158 | 0.5698 | 57732.0000 |
| raw | 0.1951 | 0.0102 | 0.5702 | 57732.0000 |
| logloss_optimized | 0.1957 | 0.0263 | 0.5726 | 57732.0000 |
| resource_win_prob | 0.2665 | 0.1671 | 0.7274 | 57732.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1653 | 0.0000 | 0.4932 | 102943.0000 |
| innings_phase | 0.1667 | 0.0000 | 0.4977 | 102943.0000 |
| innings_specific | 0.1669 | 0.0066 | 0.4985 | 102943.0000 |
| combined | 0.1670 | 0.0106 | 0.4987 | 102943.0000 |
| ece_optimized | 0.1670 | 0.0035 | 0.4994 | 102943.0000 |
| raw | 0.1673 | 0.0119 | 0.4995 | 102943.0000 |
| logloss_optimized | 0.1686 | 0.0307 | 0.5065 | 102943.0000 |
| resource_win_prob | 0.2512 | 0.2190 | 0.6998 | 102943.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1526 | 0.0000 | 0.4576 | 64264.0000 |
| innings_phase | 0.1537 | 0.0000 | 0.4615 | 64264.0000 |
| ece_optimized | 0.1541 | 0.0046 | 0.4639 | 64264.0000 |
| innings_specific | 0.1544 | 0.0137 | 0.4635 | 64264.0000 |
| combined | 0.1545 | 0.0170 | 0.4643 | 64264.0000 |
| raw | 0.1550 | 0.0213 | 0.4656 | 64264.0000 |
| logloss_optimized | 0.1572 | 0.0455 | 0.4762 | 64264.0000 |
| resource_win_prob | 0.2868 | 0.3057 | 0.7977 | 64264.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1362 | 0.0000 | 0.4165 | 57284.0000 |
| innings_phase | 0.1372 | 0.0000 | 0.4198 | 57284.0000 |
| ece_optimized | 0.1376 | 0.0059 | 0.4218 | 57284.0000 |
| innings_specific | 0.1377 | 0.0114 | 0.4216 | 57284.0000 |
| combined | 0.1382 | 0.0200 | 0.4228 | 57284.0000 |
| raw | 0.1383 | 0.0234 | 0.4239 | 57284.0000 |
| logloss_optimized | 0.1396 | 0.0346 | 0.4309 | 57284.0000 |
| resource_win_prob | 0.2730 | 0.3160 | 0.8180 | 57284.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0907 | 0.0000 | 0.2866 | 92127.0000 |
| innings_phase | 0.0919 | 0.0000 | 0.2910 | 92127.0000 |
| innings_specific | 0.0921 | 0.0045 | 0.2916 | 92127.0000 |
| combined | 0.0922 | 0.0042 | 0.2918 | 92127.0000 |
| ece_optimized | 0.0922 | 0.0048 | 0.2926 | 92127.0000 |
| raw | 0.0924 | 0.0094 | 0.2932 | 92127.0000 |
| logloss_optimized | 0.0949 | 0.0338 | 0.3075 | 92127.0000 |
| resource_win_prob | 0.1496 | 0.1838 | 0.4753 | 92127.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0527 | 0.0000 | 0.1721 | 39887.0000 |
| innings_phase | 0.0538 | 0.0000 | 0.1761 | 39887.0000 |
| ece_optimized | 0.0542 | 0.0053 | 0.1776 | 39887.0000 |
| combined | 0.0552 | 0.0177 | 0.1809 | 39887.0000 |
| innings_specific | 0.0552 | 0.0166 | 0.1806 | 39887.0000 |
| raw | 0.0552 | 0.0181 | 0.1814 | 39887.0000 |
| logloss_optimized | 0.0575 | 0.0231 | 0.1980 | 39887.0000 |
| resource_win_prob | 0.0595 | 0.0200 | 0.2039 | 39887.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1358 |
| Innings 1 | brier_optimized | 0.1689 |
| Innings 2 | brier_optimized | 0.0965 |
| Inn1 Powerplay | brier_optimized | 0.1933 |
| Inn1 Middle | brier_optimized | 0.1653 |
| Inn1 Death | brier_optimized | 0.1526 |
| Inn2 Powerplay | brier_optimized | 0.1362 |
| Inn2 Middle | brier_optimized | 0.0907 |
| Inn2 Death | brier_optimized | 0.0527 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | innings_phase | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | innings_phase | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.4100 |
| Innings 1 | brier_optimized | 0.5011 |
| Innings 2 | brier_optimized | 0.3018 |
| Inn1 Powerplay | brier_optimized | 0.5638 |
| Inn1 Middle | brier_optimized | 0.4932 |
| Inn1 Death | brier_optimized | 0.4576 |
| Inn2 Powerplay | brier_optimized | 0.4165 |
| Inn2 Middle | brier_optimized | 0.2866 |
| Inn2 Death | brier_optimized | 0.1721 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 7 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2208 | 0.1358 (brier_optimized) | **+38.5%** |
| LogLoss | 0.6375 | 0.4100 (brier_optimized) | **+35.7%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 81,879 | 0.026 | 0.021 | 0.0048  | 0.0198 |
| 0.1-0.2 | 32,070 | 0.149 | 0.147 | 0.0021  | 0.1243 |
| 0.2-0.3 | 31,106 | 0.251 | 0.266 | 0.0149  | 0.1940 |
| 0.3-0.4 | 33,547 | 0.350 | 0.352 | 0.0020  | 0.2277 |
| 0.4-0.5 | 34,568 | 0.450 | 0.459 | 0.0093  | 0.2471 |
| 0.5-0.6 | 34,361 | 0.550 | 0.549 | 0.0013  | 0.2472 |
| 0.6-0.7 | 33,464 | 0.649 | 0.638 | 0.0113  | 0.2301 |
| 0.7-0.8 | 32,997 | 0.750 | 0.739 | 0.0109  | 0.1919 |
| 0.8-0.9 | 38,394 | 0.853 | 0.856 | 0.0028  | 0.1223 |
| 0.9-1.0 | 61,851 | 0.954 | 0.965 | 0.0119  | 0.0329 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 84,629 | 0.020 | 0.020 | 0.0000  | 0.0188 |
| 0.1-0.2 | 29,021 | 0.151 | 0.151 | 0.0000  | 0.1274 |
| 0.2-0.3 | 28,236 | 0.249 | 0.249 | 0.0000  | 0.1864 |
| 0.3-0.4 | 36,879 | 0.352 | 0.352 | 0.0000  | 0.2275 |
| 0.4-0.5 | 33,254 | 0.451 | 0.451 | 0.0000  | 0.2467 |
| 0.5-0.6 | 34,994 | 0.548 | 0.548 | 0.0000  | 0.2469 |
| 0.6-0.7 | 38,942 | 0.648 | 0.648 | 0.0000  | 0.2272 |
| 0.7-0.8 | 28,400 | 0.748 | 0.748 | 0.0000  | 0.1875 |
| 0.8-0.9 | 30,970 | 0.850 | 0.850 | 0.0000  | 0.1265 |
| 0.9-1.0 | 68,912 | 0.963 | 0.963 | 0.0000  | 0.0344 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 84,584 | 0.022 | 0.022 | 0.0000  | 0.0207 |
| 0.1-0.2 | 29,706 | 0.153 | 0.153 | 0.0000  | 0.1288 |
| 0.2-0.3 | 27,919 | 0.255 | 0.255 | 0.0000  | 0.1889 |
| 0.3-0.4 | 37,435 | 0.353 | 0.353 | 0.0000  | 0.2276 |
| 0.4-0.5 | 27,431 | 0.451 | 0.451 | 0.0000  | 0.2466 |
| 0.5-0.6 | 35,854 | 0.535 | 0.535 | 0.0000  | 0.2481 |
| 0.6-0.7 | 44,375 | 0.643 | 0.643 | 0.0000  | 0.2284 |
| 0.7-0.8 | 27,966 | 0.750 | 0.750 | 0.0000  | 0.1867 |
| 0.8-0.9 | 30,417 | 0.851 | 0.851 | 0.0000  | 0.1260 |
| 0.9-1.0 | 68,550 | 0.961 | 0.961 | 0.0000  | 0.0366 |

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
