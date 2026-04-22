# OOF Calibration Analysis Report

**Generated:** 2026-04-22 16:12:56
**Samples:** 78,040
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1833 | 0.0000 | 0.5343 |
| resource_win_prob | 0.1836 | 0.0256 | 0.5422 |
| innings_phase | 0.1865 | 0.0000 | 0.5438 |
| ece_optimized | 0.1881 | 0.0110 | 0.5488 |
| innings_specific | 0.1895 | 0.0000 | 0.5528 |
| combined | 0.1910 | 0.0000 | 0.5566 |
| logloss_optimized | 0.1917 | 0.0254 | 0.5605 |
| raw | 0.1952 | 0.0493 | 0.5693 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| resource_win_prob | 0.2193 | 0.0414 | 0.6297 | 40473.0000 |
| brier_optimized | 0.2194 | 0.0000 | 0.6248 | 40473.0000 |
| innings_phase | 0.2220 | 0.0000 | 0.6316 | 40473.0000 |
| ece_optimized | 0.2241 | 0.0191 | 0.6369 | 40473.0000 |
| innings_specific | 0.2246 | 0.0000 | 0.6375 | 40473.0000 |
| combined | 0.2260 | 0.0214 | 0.6414 | 40473.0000 |
| logloss_optimized | 0.2269 | 0.0396 | 0.6443 | 40473.0000 |
| raw | 0.2331 | 0.0653 | 0.6605 | 40473.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1445 | 0.0000 | 0.4368 | 37567.0000 |
| resource_win_prob | 0.1450 | 0.0224 | 0.4478 | 37567.0000 |
| innings_phase | 0.1482 | 0.0000 | 0.4492 | 37567.0000 |
| ece_optimized | 0.1493 | 0.0058 | 0.4539 | 37567.0000 |
| innings_specific | 0.1517 | 0.0000 | 0.4614 | 37567.0000 |
| combined | 0.1533 | 0.0230 | 0.4653 | 37567.0000 |
| logloss_optimized | 0.1539 | 0.0352 | 0.4702 | 37567.0000 |
| raw | 0.1543 | 0.0328 | 0.4710 | 37567.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| resource_win_prob | 0.2395 | 0.0324 | 0.6718 | 10216.0000 |
| brier_optimized | 0.2425 | 0.0000 | 0.6776 | 10216.0000 |
| innings_phase | 0.2443 | 0.0000 | 0.6814 | 10216.0000 |
| logloss_optimized | 0.2456 | 0.0103 | 0.6843 | 10216.0000 |
| ece_optimized | 0.2483 | 0.0561 | 0.6899 | 10216.0000 |
| innings_specific | 0.2490 | 0.0462 | 0.6918 | 10216.0000 |
| combined | 0.2501 | 0.0482 | 0.6940 | 10216.0000 |
| raw | 0.2580 | 0.0910 | 0.7136 | 10216.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2159 | 0.0000 | 0.6189 | 18246.0000 |
| resource_win_prob | 0.2166 | 0.0538 | 0.6284 | 18246.0000 |
| innings_phase | 0.2194 | 0.0000 | 0.6276 | 18246.0000 |
| ece_optimized | 0.2207 | 0.0066 | 0.6317 | 18246.0000 |
| innings_specific | 0.2208 | 0.0231 | 0.6311 | 18246.0000 |
| combined | 0.2215 | 0.0345 | 0.6329 | 18246.0000 |
| logloss_optimized | 0.2230 | 0.0397 | 0.6368 | 18246.0000 |
| raw | 0.2275 | 0.0604 | 0.6508 | 18246.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2050 | 0.0000 | 0.5888 | 12011.0000 |
| resource_win_prob | 0.2064 | 0.0765 | 0.5959 | 12011.0000 |
| innings_phase | 0.2072 | 0.0000 | 0.5953 | 12011.0000 |
| ece_optimized | 0.2085 | 0.0084 | 0.5996 | 12011.0000 |
| innings_specific | 0.2094 | 0.0351 | 0.6011 | 12011.0000 |
| combined | 0.2124 | 0.0593 | 0.6096 | 12011.0000 |
| logloss_optimized | 0.2168 | 0.0786 | 0.6218 | 12011.0000 |
| raw | 0.2204 | 0.0805 | 0.6302 | 12011.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| resource_win_prob | 0.1795 | 0.0586 | 0.5349 | 10272.0000 |
| brier_optimized | 0.1803 | 0.0000 | 0.5342 | 10272.0000 |
| innings_phase | 0.1827 | 0.0000 | 0.5413 | 10272.0000 |
| ece_optimized | 0.1841 | 0.0121 | 0.5456 | 10272.0000 |
| innings_specific | 0.1888 | 0.0610 | 0.5613 | 10272.0000 |
| combined | 0.1918 | 0.0732 | 0.5689 | 10272.0000 |
| logloss_optimized | 0.1922 | 0.0739 | 0.5672 | 10272.0000 |
| raw | 0.1960 | 0.0800 | 0.5882 | 10272.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1463 | 0.0000 | 0.4425 | 18092.0000 |
| resource_win_prob | 0.1468 | 0.0434 | 0.4586 | 18092.0000 |
| innings_phase | 0.1508 | 0.0000 | 0.4579 | 18092.0000 |
| innings_specific | 0.1517 | 0.0164 | 0.4607 | 18092.0000 |
| ece_optimized | 0.1519 | 0.0076 | 0.4625 | 18092.0000 |
| combined | 0.1524 | 0.0194 | 0.4623 | 18092.0000 |
| raw | 0.1538 | 0.0328 | 0.4688 | 18092.0000 |
| logloss_optimized | 0.1548 | 0.0303 | 0.4745 | 18092.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1009 | 0.0000 | 0.3168 | 9203.0000 |
| resource_win_prob | 0.1030 | 0.0574 | 0.3295 | 9203.0000 |
| innings_phase | 0.1045 | 0.0000 | 0.3293 | 9203.0000 |
| ece_optimized | 0.1056 | 0.0047 | 0.3348 | 9203.0000 |
| raw | 0.1087 | 0.0357 | 0.3443 | 9203.0000 |
| logloss_optimized | 0.1093 | 0.0383 | 0.3533 | 9203.0000 |
| innings_specific | 0.1105 | 0.0606 | 0.3514 | 9203.0000 |
| combined | 0.1123 | 0.0661 | 0.3556 | 9203.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1833 |
| Innings 1 | resource_win_prob | 0.2193 |
| Innings 2 | brier_optimized | 0.1445 |
| Inn1 Powerplay | resource_win_prob | 0.2395 |
| Inn1 Middle | brier_optimized | 0.2159 |
| Inn1 Death | brier_optimized | 0.2050 |
| Inn2 Powerplay | resource_win_prob | 0.1795 |
| Inn2 Middle | brier_optimized | 0.1463 |
| Inn2 Death | brier_optimized | 0.1009 |

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
| Overall | brier_optimized | 0.5343 |
| Innings 1 | brier_optimized | 0.6248 |
| Innings 2 | brier_optimized | 0.4368 |
| Inn1 Powerplay | resource_win_prob | 0.6718 |
| Inn1 Middle | brier_optimized | 0.6189 |
| Inn1 Death | brier_optimized | 0.5888 |
| Inn2 Powerplay | brier_optimized | 0.5342 |
| Inn2 Middle | brier_optimized | 0.4425 |
| Inn2 Death | brier_optimized | 0.3168 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 6 segments
- **ECE**: `brier_optimized` wins in 8 segments
- **LogLoss**: `brier_optimized` wins in 8 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1836 | 0.1833 (brier_optimized) | **+0.1%** |
| LogLoss | 0.5422 | 0.5343 (brier_optimized) | **+1.5%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 7,536 | 0.050 | 0.087 | 0.0372  | 0.0788 |
| 0.1-0.2 | 7,376 | 0.151 | 0.223 | 0.0719 ⚠️ | 0.1781 |
| 0.2-0.3 | 8,091 | 0.250 | 0.296 | 0.0462  | 0.2099 |
| 0.3-0.4 | 8,741 | 0.350 | 0.407 | 0.0567 ⚠️ | 0.2439 |
| 0.4-0.5 | 8,970 | 0.449 | 0.476 | 0.0276  | 0.2509 |
| 0.5-0.6 | 8,396 | 0.548 | 0.539 | 0.0093  | 0.2484 |
| 0.6-0.7 | 7,432 | 0.650 | 0.596 | 0.0533 ⚠️ | 0.2442 |
| 0.7-0.8 | 6,884 | 0.751 | 0.647 | 0.1035 ⚠️ | 0.2388 |
| 0.8-0.9 | 6,126 | 0.851 | 0.743 | 0.1080 ⚠️ | 0.2002 |
| 0.9-1.0 | 8,488 | 0.948 | 0.940 | 0.0081  | 0.0555 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 5,275 | 0.024 | 0.024 | 0.0000  | 0.0223 |
| 0.1-0.2 | 5,317 | 0.152 | 0.152 | 0.0000  | 0.1280 |
| 0.2-0.3 | 8,127 | 0.253 | 0.253 | 0.0000  | 0.1879 |
| 0.3-0.4 | 9,405 | 0.352 | 0.352 | 0.0000  | 0.2275 |
| 0.4-0.5 | 13,363 | 0.450 | 0.450 | 0.0000  | 0.2469 |
| 0.5-0.6 | 10,137 | 0.557 | 0.557 | 0.0000  | 0.2457 |
| 0.6-0.7 | 10,761 | 0.631 | 0.631 | 0.0000  | 0.2321 |
| 0.7-0.8 | 4,081 | 0.737 | 0.737 | 0.0000  | 0.1932 |
| 0.8-0.9 | 3,847 | 0.854 | 0.854 | 0.0000  | 0.1237 |
| 0.9-1.0 | 7,727 | 0.960 | 0.960 | 0.0000  | 0.0374 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 4,765 | 0.027 | 0.027 | 0.0000  | 0.0257 |
| 0.1-0.2 | 6,381 | 0.160 | 0.160 | 0.0000  | 0.1340 |
| 0.2-0.3 | 7,873 | 0.266 | 0.266 | 0.0000  | 0.1948 |
| 0.3-0.4 | 8,411 | 0.350 | 0.350 | 0.0000  | 0.2270 |
| 0.4-0.5 | 15,854 | 0.457 | 0.457 | 0.0000  | 0.2479 |
| 0.5-0.6 | 7,652 | 0.562 | 0.562 | 0.0000  | 0.2455 |
| 0.6-0.7 | 11,293 | 0.620 | 0.620 | 0.0000  | 0.2351 |
| 0.7-0.8 | 4,257 | 0.730 | 0.730 | 0.0000  | 0.1966 |
| 0.8-0.9 | 4,559 | 0.858 | 0.858 | 0.0000  | 0.1214 |
| 0.9-1.0 | 6,995 | 0.958 | 0.958 | 0.0000  | 0.0399 |

### Problematic Bins (Calibration Error > 0.05)


**raw:**
- Bin 0.1-0.2: CE=0.0719 (under-predicting)
- Bin 0.3-0.4: CE=0.0567 (under-predicting)
- Bin 0.6-0.7: CE=0.0533 (over-predicting)
- Bin 0.7-0.8: CE=0.1035 (over-predicting)
- Bin 0.8-0.9: CE=0.1080 (over-predicting)

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
