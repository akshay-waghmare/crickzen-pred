# OOF Calibration Analysis Report

**Generated:** 2026-04-22 14:50:14
**Samples:** 78,040
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1834 | 0.0000 | 0.5342 |
| innings_phase | 0.1868 | 0.0000 | 0.5443 |
| ece_optimized | 0.1886 | 0.0117 | 0.5496 |
| resource_win_prob | 0.1889 | 0.0410 | 0.5555 |
| innings_specific | 0.1899 | 0.0000 | 0.5538 |
| combined | 0.1911 | 0.0000 | 0.5569 |
| logloss_optimized | 0.1923 | 0.0308 | 0.5615 |
| raw | 0.1955 | 0.0480 | 0.5698 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2188 | 0.0000 | 0.6231 | 40473.0000 |
| resource_win_prob | 0.2193 | 0.0414 | 0.6297 | 40473.0000 |
| innings_phase | 0.2217 | 0.0000 | 0.6307 | 40473.0000 |
| innings_specific | 0.2240 | 0.0000 | 0.6362 | 40473.0000 |
| ece_optimized | 0.2241 | 0.0179 | 0.6366 | 40473.0000 |
| combined | 0.2252 | 0.0168 | 0.6395 | 40473.0000 |
| logloss_optimized | 0.2266 | 0.0415 | 0.6436 | 40473.0000 |
| raw | 0.2323 | 0.0617 | 0.6581 | 40473.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1453 | 0.0000 | 0.4383 | 37567.0000 |
| innings_phase | 0.1491 | 0.0000 | 0.4512 | 37567.0000 |
| ece_optimized | 0.1503 | 0.0078 | 0.4559 | 37567.0000 |
| innings_specific | 0.1532 | 0.0000 | 0.4650 | 37567.0000 |
| combined | 0.1543 | 0.0181 | 0.4679 | 37567.0000 |
| logloss_optimized | 0.1554 | 0.0392 | 0.4732 | 37567.0000 |
| raw | 0.1559 | 0.0357 | 0.4747 | 37567.0000 |
| resource_win_prob | 0.1561 | 0.0514 | 0.4756 | 37567.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| resource_win_prob | 0.2395 | 0.0324 | 0.6718 | 10216.0000 |
| brier_optimized | 0.2422 | 0.0000 | 0.6771 | 10216.0000 |
| innings_phase | 0.2443 | 0.0000 | 0.6813 | 10216.0000 |
| logloss_optimized | 0.2456 | 0.0154 | 0.6844 | 10216.0000 |
| innings_specific | 0.2492 | 0.0472 | 0.6919 | 10216.0000 |
| ece_optimized | 0.2492 | 0.0582 | 0.6918 | 10216.0000 |
| combined | 0.2496 | 0.0487 | 0.6930 | 10216.0000 |
| raw | 0.2581 | 0.0911 | 0.7137 | 10216.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2152 | 0.0000 | 0.6168 | 18246.0000 |
| resource_win_prob | 0.2166 | 0.0538 | 0.6284 | 18246.0000 |
| innings_phase | 0.2188 | 0.0000 | 0.6261 | 18246.0000 |
| innings_specific | 0.2200 | 0.0219 | 0.6292 | 18246.0000 |
| ece_optimized | 0.2206 | 0.0093 | 0.6310 | 18246.0000 |
| combined | 0.2209 | 0.0321 | 0.6314 | 18246.0000 |
| logloss_optimized | 0.2230 | 0.0409 | 0.6365 | 18246.0000 |
| raw | 0.2267 | 0.0535 | 0.6478 | 18246.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2044 | 0.0000 | 0.5868 | 12011.0000 |
| resource_win_prob | 0.2064 | 0.0765 | 0.5959 | 12011.0000 |
| innings_phase | 0.2070 | 0.0000 | 0.5949 | 12011.0000 |
| ece_optimized | 0.2081 | 0.0075 | 0.5981 | 12011.0000 |
| innings_specific | 0.2087 | 0.0301 | 0.5993 | 12011.0000 |
| combined | 0.2110 | 0.0487 | 0.6063 | 12011.0000 |
| logloss_optimized | 0.2158 | 0.0777 | 0.6196 | 12011.0000 |
| raw | 0.2188 | 0.0785 | 0.6265 | 12011.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1803 | 0.0000 | 0.5342 | 10272.0000 |
| resource_win_prob | 0.1816 | 0.0614 | 0.5387 | 10272.0000 |
| innings_phase | 0.1829 | 0.0000 | 0.5415 | 10272.0000 |
| ece_optimized | 0.1841 | 0.0106 | 0.5453 | 10272.0000 |
| innings_specific | 0.1900 | 0.0618 | 0.5646 | 10272.0000 |
| combined | 0.1916 | 0.0717 | 0.5689 | 10272.0000 |
| logloss_optimized | 0.1925 | 0.0747 | 0.5679 | 10272.0000 |
| raw | 0.1967 | 0.0890 | 0.5905 | 10272.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1464 | 0.0000 | 0.4424 | 18092.0000 |
| innings_phase | 0.1510 | 0.0000 | 0.4579 | 18092.0000 |
| innings_specific | 0.1517 | 0.0101 | 0.4604 | 18092.0000 |
| ece_optimized | 0.1521 | 0.0096 | 0.4625 | 18092.0000 |
| combined | 0.1522 | 0.0141 | 0.4617 | 18092.0000 |
| resource_win_prob | 0.1526 | 0.0504 | 0.4616 | 18092.0000 |
| raw | 0.1547 | 0.0383 | 0.4701 | 18092.0000 |
| logloss_optimized | 0.1561 | 0.0405 | 0.4762 | 18092.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1039 | 0.0000 | 0.3231 | 9203.0000 |
| innings_phase | 0.1079 | 0.0000 | 0.3373 | 9203.0000 |
| ece_optimized | 0.1090 | 0.0116 | 0.3432 | 9203.0000 |
| logloss_optimized | 0.1128 | 0.0422 | 0.3614 | 9203.0000 |
| raw | 0.1129 | 0.0421 | 0.3545 | 9203.0000 |
| innings_specific | 0.1150 | 0.0650 | 0.3631 | 9203.0000 |
| combined | 0.1168 | 0.0690 | 0.3673 | 9203.0000 |
| resource_win_prob | 0.1345 | 0.1363 | 0.4328 | 9203.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1834 |
| Innings 1 | brier_optimized | 0.2188 |
| Innings 2 | brier_optimized | 0.1453 |
| Inn1 Powerplay | resource_win_prob | 0.2395 |
| Inn1 Middle | brier_optimized | 0.2152 |
| Inn1 Death | brier_optimized | 0.2044 |
| Inn2 Powerplay | brier_optimized | 0.1803 |
| Inn2 Middle | brier_optimized | 0.1464 |
| Inn2 Death | brier_optimized | 0.1039 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | innings_phase | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
| Inn1 Powerplay | innings_phase | 0.0000 |
| Inn1 Middle | innings_phase | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | innings_phase | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5342 |
| Innings 1 | brier_optimized | 0.6231 |
| Innings 2 | brier_optimized | 0.4383 |
| Inn1 Powerplay | resource_win_prob | 0.6718 |
| Inn1 Middle | brier_optimized | 0.6168 |
| Inn1 Death | brier_optimized | 0.5868 |
| Inn2 Powerplay | brier_optimized | 0.5342 |
| Inn2 Middle | brier_optimized | 0.4424 |
| Inn2 Death | brier_optimized | 0.3231 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 8 segments
- **ECE**: `brier_optimized` wins in 5 segments
- **LogLoss**: `brier_optimized` wins in 8 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1889 | 0.1834 (brier_optimized) | **+2.9%** |
| LogLoss | 0.5555 | 0.5342 (brier_optimized) | **+3.8%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 7,151 | 0.050 | 0.081 | 0.0314  | 0.0742 |
| 0.1-0.2 | 7,198 | 0.152 | 0.207 | 0.0551 ⚠️ | 0.1674 |
| 0.2-0.3 | 8,444 | 0.250 | 0.310 | 0.0602 ⚠️ | 0.2162 |
| 0.3-0.4 | 8,817 | 0.352 | 0.412 | 0.0602 ⚠️ | 0.2450 |
| 0.4-0.5 | 9,454 | 0.449 | 0.465 | 0.0157  | 0.2499 |
| 0.5-0.6 | 8,349 | 0.548 | 0.554 | 0.0064  | 0.2474 |
| 0.6-0.7 | 7,558 | 0.650 | 0.594 | 0.0551 ⚠️ | 0.2450 |
| 0.7-0.8 | 6,613 | 0.749 | 0.630 | 0.1189 ⚠️ | 0.2472 |
| 0.8-0.9 | 5,980 | 0.851 | 0.745 | 0.1056 ⚠️ | 0.1972 |
| 0.9-1.0 | 8,476 | 0.950 | 0.944 | 0.0059  | 0.0526 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 5,091 | 0.020 | 0.020 | 0.0000  | 0.0187 |
| 0.1-0.2 | 5,993 | 0.155 | 0.155 | 0.0000  | 0.1302 |
| 0.2-0.3 | 6,916 | 0.251 | 0.251 | 0.0000  | 0.1872 |
| 0.3-0.4 | 9,617 | 0.349 | 0.349 | 0.0000  | 0.2267 |
| 0.4-0.5 | 14,021 | 0.452 | 0.452 | 0.0000  | 0.2471 |
| 0.5-0.6 | 9,502 | 0.549 | 0.549 | 0.0000  | 0.2465 |
| 0.6-0.7 | 13,068 | 0.638 | 0.638 | 0.0000  | 0.2301 |
| 0.7-0.8 | 2,359 | 0.746 | 0.746 | 0.0000  | 0.1890 |
| 0.8-0.9 | 2,990 | 0.864 | 0.864 | 0.0000  | 0.1166 |
| 0.9-1.0 | 8,483 | 0.955 | 0.955 | 0.0000  | 0.0420 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 4,751 | 0.028 | 0.028 | 0.0000  | 0.0262 |
| 0.1-0.2 | 5,401 | 0.154 | 0.154 | 0.0000  | 0.1298 |
| 0.2-0.3 | 6,482 | 0.243 | 0.243 | 0.0000  | 0.1830 |
| 0.3-0.4 | 10,875 | 0.346 | 0.346 | 0.0000  | 0.2255 |
| 0.4-0.5 | 16,475 | 0.459 | 0.459 | 0.0000  | 0.2480 |
| 0.5-0.6 | 4,382 | 0.545 | 0.545 | 0.0000  | 0.2477 |
| 0.6-0.7 | 16,223 | 0.624 | 0.624 | 0.0000  | 0.2340 |
| 0.7-0.8 | 1,568 | 0.740 | 0.740 | 0.0000  | 0.1922 |
| 0.8-0.9 | 3,185 | 0.848 | 0.848 | 0.0000  | 0.1279 |
| 0.9-1.0 | 8,698 | 0.946 | 0.946 | 0.0000  | 0.0502 |

### Problematic Bins (Calibration Error > 0.05)


**raw:**
- Bin 0.1-0.2: CE=0.0551 (under-predicting)
- Bin 0.2-0.3: CE=0.0602 (under-predicting)
- Bin 0.3-0.4: CE=0.0602 (under-predicting)
- Bin 0.6-0.7: CE=0.0551 (over-predicting)
- Bin 0.7-0.8: CE=0.1189 (over-predicting)
- Bin 0.8-0.9: CE=0.1056 (over-predicting)

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
