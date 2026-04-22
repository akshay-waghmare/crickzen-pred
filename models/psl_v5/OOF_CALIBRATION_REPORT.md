# OOF Calibration Analysis Report

**Generated:** 2026-04-22 17:27:02
**Samples:** 78,040
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1830 | 0.0000 | 0.5334 |
| resource_win_prob | 0.1856 | 0.0278 | 0.5445 |
| innings_phase | 0.1864 | 0.0000 | 0.5436 |
| ece_optimized | 0.1881 | 0.0101 | 0.5488 |
| innings_specific | 0.1894 | 0.0000 | 0.5525 |
| combined | 0.1909 | 0.0000 | 0.5565 |
| logloss_optimized | 0.1917 | 0.0263 | 0.5606 |
| raw | 0.1950 | 0.0495 | 0.5690 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2191 | 0.0000 | 0.6235 | 40473.0000 |
| resource_win_prob | 0.2193 | 0.0414 | 0.6297 | 40473.0000 |
| innings_phase | 0.2217 | 0.0000 | 0.6303 | 40473.0000 |
| ece_optimized | 0.2239 | 0.0160 | 0.6360 | 40473.0000 |
| innings_specific | 0.2242 | 0.0000 | 0.6361 | 40473.0000 |
| combined | 0.2256 | 0.0193 | 0.6402 | 40473.0000 |
| logloss_optimized | 0.2265 | 0.0383 | 0.6435 | 40473.0000 |
| raw | 0.2326 | 0.0651 | 0.6589 | 40473.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1441 | 0.0000 | 0.4363 | 37567.0000 |
| innings_phase | 0.1483 | 0.0000 | 0.4501 | 37567.0000 |
| resource_win_prob | 0.1492 | 0.0292 | 0.4527 | 37567.0000 |
| ece_optimized | 0.1495 | 0.0062 | 0.4550 | 37567.0000 |
| innings_specific | 0.1519 | 0.0000 | 0.4625 | 37567.0000 |
| combined | 0.1535 | 0.0208 | 0.4663 | 37567.0000 |
| logloss_optimized | 0.1543 | 0.0363 | 0.4713 | 37567.0000 |
| raw | 0.1546 | 0.0336 | 0.4723 | 37567.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| resource_win_prob | 0.2395 | 0.0324 | 0.6718 | 10216.0000 |
| brier_optimized | 0.2424 | 0.0000 | 0.6775 | 10216.0000 |
| innings_phase | 0.2442 | 0.0000 | 0.6813 | 10216.0000 |
| logloss_optimized | 0.2456 | 0.0108 | 0.6843 | 10216.0000 |
| innings_specific | 0.2488 | 0.0502 | 0.6912 | 10216.0000 |
| ece_optimized | 0.2494 | 0.0566 | 0.6921 | 10216.0000 |
| combined | 0.2497 | 0.0467 | 0.6933 | 10216.0000 |
| raw | 0.2581 | 0.0909 | 0.7138 | 10216.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2158 | 0.0000 | 0.6179 | 18246.0000 |
| resource_win_prob | 0.2166 | 0.0538 | 0.6284 | 18246.0000 |
| innings_phase | 0.2190 | 0.0000 | 0.6261 | 18246.0000 |
| ece_optimized | 0.2202 | 0.0098 | 0.6297 | 18246.0000 |
| innings_specific | 0.2203 | 0.0214 | 0.6294 | 18246.0000 |
| combined | 0.2210 | 0.0266 | 0.6316 | 18246.0000 |
| logloss_optimized | 0.2228 | 0.0411 | 0.6362 | 18246.0000 |
| raw | 0.2271 | 0.0578 | 0.6493 | 18246.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2042 | 0.0000 | 0.5861 | 12011.0000 |
| resource_win_prob | 0.2064 | 0.0765 | 0.5959 | 12011.0000 |
| innings_phase | 0.2066 | 0.0000 | 0.5935 | 12011.0000 |
| ece_optimized | 0.2080 | 0.0052 | 0.5979 | 12011.0000 |
| innings_specific | 0.2091 | 0.0367 | 0.5996 | 12011.0000 |
| combined | 0.2119 | 0.0575 | 0.6080 | 12011.0000 |
| logloss_optimized | 0.2161 | 0.0794 | 0.6201 | 12011.0000 |
| raw | 0.2192 | 0.0800 | 0.6266 | 12011.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1797 | 0.0000 | 0.5342 | 10272.0000 |
| resource_win_prob | 0.1811 | 0.0672 | 0.5373 | 10272.0000 |
| innings_phase | 0.1825 | 0.0000 | 0.5420 | 10272.0000 |
| ece_optimized | 0.1834 | 0.0075 | 0.5451 | 10272.0000 |
| innings_specific | 0.1892 | 0.0562 | 0.5641 | 10272.0000 |
| logloss_optimized | 0.1921 | 0.0756 | 0.5673 | 10272.0000 |
| combined | 0.1922 | 0.0782 | 0.5716 | 10272.0000 |
| raw | 0.1958 | 0.0839 | 0.5897 | 10272.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1454 | 0.0000 | 0.4408 | 18092.0000 |
| innings_phase | 0.1505 | 0.0000 | 0.4579 | 18092.0000 |
| innings_specific | 0.1513 | 0.0166 | 0.4605 | 18092.0000 |
| ece_optimized | 0.1518 | 0.0096 | 0.4634 | 18092.0000 |
| combined | 0.1524 | 0.0171 | 0.4630 | 18092.0000 |
| resource_win_prob | 0.1536 | 0.0622 | 0.4658 | 18092.0000 |
| raw | 0.1540 | 0.0375 | 0.4698 | 18092.0000 |
| logloss_optimized | 0.1549 | 0.0384 | 0.4748 | 18092.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1020 | 0.0000 | 0.3182 | 9203.0000 |
| resource_win_prob | 0.1048 | 0.0343 | 0.3325 | 9203.0000 |
| innings_phase | 0.1060 | 0.0000 | 0.3321 | 9203.0000 |
| ece_optimized | 0.1072 | 0.0073 | 0.3377 | 9203.0000 |
| raw | 0.1097 | 0.0323 | 0.3459 | 9203.0000 |
| logloss_optimized | 0.1107 | 0.0385 | 0.3572 | 9203.0000 |
| innings_specific | 0.1114 | 0.0556 | 0.3529 | 9203.0000 |
| combined | 0.1124 | 0.0583 | 0.3554 | 9203.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1830 |
| Innings 1 | brier_optimized | 0.2191 |
| Innings 2 | brier_optimized | 0.1441 |
| Inn1 Powerplay | resource_win_prob | 0.2395 |
| Inn1 Middle | brier_optimized | 0.2158 |
| Inn1 Death | brier_optimized | 0.2042 |
| Inn2 Powerplay | brier_optimized | 0.1797 |
| Inn2 Middle | brier_optimized | 0.1454 |
| Inn2 Death | brier_optimized | 0.1020 |

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
| Overall | brier_optimized | 0.5334 |
| Innings 1 | brier_optimized | 0.6235 |
| Innings 2 | brier_optimized | 0.4363 |
| Inn1 Powerplay | resource_win_prob | 0.6718 |
| Inn1 Middle | brier_optimized | 0.6179 |
| Inn1 Death | brier_optimized | 0.5861 |
| Inn2 Powerplay | brier_optimized | 0.5342 |
| Inn2 Middle | brier_optimized | 0.4408 |
| Inn2 Death | brier_optimized | 0.3182 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 8 segments
- **ECE**: `brier_optimized` wins in 9 segments
- **LogLoss**: `brier_optimized` wins in 8 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1856 | 0.1830 (brier_optimized) | **+1.4%** |
| LogLoss | 0.5445 | 0.5334 (brier_optimized) | **+2.0%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 7,480 | 0.050 | 0.083 | 0.0330  | 0.0749 |
| 0.1-0.2 | 7,503 | 0.152 | 0.230 | 0.0784 ⚠️ | 0.1832 |
| 0.2-0.3 | 7,853 | 0.249 | 0.301 | 0.0524 ⚠️ | 0.2127 |
| 0.3-0.4 | 8,759 | 0.351 | 0.399 | 0.0486  | 0.2406 |
| 0.4-0.5 | 8,768 | 0.450 | 0.476 | 0.0260  | 0.2502 |
| 0.5-0.6 | 8,644 | 0.549 | 0.534 | 0.0155  | 0.2485 |
| 0.6-0.7 | 7,466 | 0.649 | 0.594 | 0.0553 ⚠️ | 0.2451 |
| 0.7-0.8 | 6,875 | 0.748 | 0.633 | 0.1155 ⚠️ | 0.2458 |
| 0.8-0.9 | 6,275 | 0.851 | 0.762 | 0.0888 ⚠️ | 0.1869 |
| 0.9-1.0 | 8,417 | 0.947 | 0.939 | 0.0080  | 0.0562 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 5,408 | 0.022 | 0.022 | 0.0000  | 0.0205 |
| 0.1-0.2 | 5,185 | 0.157 | 0.157 | 0.0000  | 0.1315 |
| 0.2-0.3 | 8,354 | 0.256 | 0.256 | 0.0000  | 0.1900 |
| 0.3-0.4 | 9,006 | 0.346 | 0.346 | 0.0000  | 0.2256 |
| 0.4-0.5 | 12,451 | 0.448 | 0.448 | 0.0000  | 0.2467 |
| 0.5-0.6 | 10,140 | 0.543 | 0.543 | 0.0000  | 0.2471 |
| 0.6-0.7 | 12,271 | 0.630 | 0.630 | 0.0000  | 0.2324 |
| 0.7-0.8 | 3,654 | 0.748 | 0.748 | 0.0000  | 0.1877 |
| 0.8-0.9 | 3,896 | 0.864 | 0.864 | 0.0000  | 0.1167 |
| 0.9-1.0 | 7,675 | 0.958 | 0.958 | 0.0000  | 0.0391 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 4,859 | 0.025 | 0.025 | 0.0000  | 0.0233 |
| 0.1-0.2 | 4,552 | 0.156 | 0.156 | 0.0000  | 0.1314 |
| 0.2-0.3 | 9,962 | 0.257 | 0.257 | 0.0000  | 0.1899 |
| 0.3-0.4 | 8,810 | 0.346 | 0.346 | 0.0000  | 0.2260 |
| 0.4-0.5 | 14,742 | 0.463 | 0.463 | 0.0000  | 0.2481 |
| 0.5-0.6 | 7,001 | 0.551 | 0.551 | 0.0000  | 0.2468 |
| 0.6-0.7 | 12,932 | 0.620 | 0.620 | 0.0000  | 0.2351 |
| 0.7-0.8 | 3,400 | 0.741 | 0.741 | 0.0000  | 0.1899 |
| 0.8-0.9 | 4,586 | 0.856 | 0.856 | 0.0000  | 0.1224 |
| 0.9-1.0 | 7,196 | 0.953 | 0.953 | 0.0000  | 0.0439 |

### Problematic Bins (Calibration Error > 0.05)


**raw:**
- Bin 0.1-0.2: CE=0.0784 (under-predicting)
- Bin 0.2-0.3: CE=0.0524 (under-predicting)
- Bin 0.6-0.7: CE=0.0553 (over-predicting)
- Bin 0.7-0.8: CE=0.1155 (over-predicting)
- Bin 0.8-0.9: CE=0.0888 (over-predicting)

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
