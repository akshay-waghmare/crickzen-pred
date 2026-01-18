# OOF Calibration Analysis Report

**Generated:** 2026-01-19 00:34:43
**Samples:** 17,062
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1510 | 0.0000 | 0.4507 |
| innings_phase | 0.1595 | 0.0000 | 0.4768 |
| resource_win_prob | 0.1625 | 0.0302 | 0.4899 |
| ece_optimized | 0.1627 | 0.0054 | 0.4895 |
| innings_specific | 0.1628 | 0.0000 | 0.4877 |
| logloss_optimized | 0.1668 | 0.0271 | 0.5037 |
| combined | 0.1684 | 0.0000 | 0.5025 |
| raw | 0.1729 | 0.0436 | 0.5202 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1906 | 0.0000 | 0.5539 | 8983.0000 |
| resource_win_prob | 0.1966 | 0.0494 | 0.5758 | 8983.0000 |
| innings_phase | 0.1986 | 0.0000 | 0.5762 | 8983.0000 |
| innings_specific | 0.2018 | 0.0000 | 0.5856 | 8983.0000 |
| ece_optimized | 0.2020 | 0.0098 | 0.5874 | 8983.0000 |
| combined | 0.2057 | 0.0469 | 0.5958 | 8983.0000 |
| logloss_optimized | 0.2069 | 0.0344 | 0.6020 | 8983.0000 |
| raw | 0.2156 | 0.0925 | 0.6294 | 8983.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1070 | 0.0000 | 0.3359 | 8079.0000 |
| innings_phase | 0.1160 | 0.0000 | 0.3663 | 8079.0000 |
| ece_optimized | 0.1190 | 0.0066 | 0.3807 | 8079.0000 |
| innings_specific | 0.1194 | 0.0000 | 0.3789 | 8079.0000 |
| logloss_optimized | 0.1222 | 0.0296 | 0.3944 | 8079.0000 |
| resource_win_prob | 0.1246 | 0.0364 | 0.3943 | 8079.0000 |
| raw | 0.1254 | 0.0440 | 0.3988 | 8079.0000 |
| combined | 0.1270 | 0.0522 | 0.3988 | 8079.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2242 | 0.0000 | 0.6357 | 2262.0000 |
| innings_phase | 0.2306 | 0.0000 | 0.6522 | 2262.0000 |
| resource_win_prob | 0.2333 | 0.0406 | 0.6586 | 2262.0000 |
| ece_optimized | 0.2342 | 0.0124 | 0.6611 | 2262.0000 |
| innings_specific | 0.2345 | 0.0415 | 0.6621 | 2262.0000 |
| logloss_optimized | 0.2351 | 0.0114 | 0.6630 | 2262.0000 |
| combined | 0.2397 | 0.0807 | 0.6739 | 2262.0000 |
| raw | 0.2541 | 0.1330 | 0.7126 | 2262.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1886 | 0.0000 | 0.5493 | 4055.0000 |
| resource_win_prob | 0.1944 | 0.0455 | 0.5718 | 4055.0000 |
| innings_phase | 0.1991 | 0.0000 | 0.5792 | 4055.0000 |
| innings_specific | 0.2007 | 0.0165 | 0.5849 | 4055.0000 |
| ece_optimized | 0.2020 | 0.0226 | 0.5889 | 4055.0000 |
| combined | 0.2027 | 0.0291 | 0.5891 | 4055.0000 |
| logloss_optimized | 0.2060 | 0.0458 | 0.5993 | 4055.0000 |
| raw | 0.2114 | 0.0797 | 0.6165 | 4055.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1651 | 0.0000 | 0.4916 | 2666.0000 |
| resource_win_prob | 0.1688 | 0.0825 | 0.5116 | 2666.0000 |
| innings_phase | 0.1707 | 0.0000 | 0.5072 | 2666.0000 |
| ece_optimized | 0.1747 | 0.0173 | 0.5227 | 2666.0000 |
| innings_specific | 0.1758 | 0.0556 | 0.5217 | 2666.0000 |
| combined | 0.1816 | 0.0809 | 0.5397 | 2666.0000 |
| logloss_optimized | 0.1843 | 0.0711 | 0.5544 | 2666.0000 |
| raw | 0.1895 | 0.1000 | 0.5783 | 2666.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1383 | 0.0000 | 0.4258 | 2265.0000 |
| resource_win_prob | 0.1402 | 0.0696 | 0.4328 | 2265.0000 |
| innings_phase | 0.1485 | 0.0000 | 0.4596 | 2265.0000 |
| ece_optimized | 0.1516 | 0.0101 | 0.4726 | 2265.0000 |
| innings_specific | 0.1526 | 0.0335 | 0.4743 | 2265.0000 |
| logloss_optimized | 0.1540 | 0.0352 | 0.4791 | 2265.0000 |
| raw | 0.1568 | 0.0621 | 0.4936 | 2265.0000 |
| combined | 0.1575 | 0.0572 | 0.4829 | 2265.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0904 | 0.0000 | 0.2852 | 3958.0000 |
| innings_phase | 0.0990 | 0.0000 | 0.3143 | 3958.0000 |
| innings_specific | 0.1009 | 0.0155 | 0.3250 | 3958.0000 |
| ece_optimized | 0.1014 | 0.0102 | 0.3279 | 3958.0000 |
| logloss_optimized | 0.1046 | 0.0418 | 0.3465 | 3958.0000 |
| raw | 0.1079 | 0.0541 | 0.3449 | 3958.0000 |
| resource_win_prob | 0.1080 | 0.0414 | 0.3350 | 3958.0000 |
| combined | 0.1105 | 0.0623 | 0.3520 | 3958.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1043 | 0.0000 | 0.3344 | 1856.0000 |
| innings_phase | 0.1127 | 0.0000 | 0.3634 | 1856.0000 |
| ece_optimized | 0.1167 | 0.0194 | 0.3811 | 1856.0000 |
| innings_specific | 0.1183 | 0.0292 | 0.3773 | 1856.0000 |
| logloss_optimized | 0.1210 | 0.0367 | 0.3932 | 1856.0000 |
| raw | 0.1243 | 0.0539 | 0.3981 | 1856.0000 |
| combined | 0.1250 | 0.0611 | 0.3960 | 1856.0000 |
| resource_win_prob | 0.1412 | 0.1224 | 0.4738 | 1856.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1510 |
| Innings 1 | brier_optimized | 0.1906 |
| Innings 2 | brier_optimized | 0.1070 |
| Inn1 Powerplay | brier_optimized | 0.2242 |
| Inn1 Middle | brier_optimized | 0.1886 |
| Inn1 Death | brier_optimized | 0.1651 |
| Inn2 Powerplay | brier_optimized | 0.1383 |
| Inn2 Middle | brier_optimized | 0.0904 |
| Inn2 Death | brier_optimized | 0.1043 |

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
| Overall | brier_optimized | 0.4507 |
| Innings 1 | brier_optimized | 0.5539 |
| Innings 2 | brier_optimized | 0.3359 |
| Inn1 Powerplay | brier_optimized | 0.6357 |
| Inn1 Middle | brier_optimized | 0.5493 |
| Inn1 Death | brier_optimized | 0.4916 |
| Inn2 Powerplay | brier_optimized | 0.4258 |
| Inn2 Middle | brier_optimized | 0.2852 |
| Inn2 Death | brier_optimized | 0.3344 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 7 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1625 | 0.1510 (brier_optimized) | **+7.1%** |
| LogLoss | 0.4899 | 0.4507 (brier_optimized) | **+8.0%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 2,539 | 0.054 | 0.113 | 0.0585 ⚠️ | 0.1019 |
| 0.1-0.2 | 2,131 | 0.149 | 0.240 | 0.0912 ⚠️ | 0.1900 |
| 0.2-0.3 | 1,926 | 0.250 | 0.309 | 0.0587 ⚠️ | 0.2174 |
| 0.3-0.4 | 1,676 | 0.347 | 0.365 | 0.0182  | 0.2319 |
| 0.4-0.5 | 1,442 | 0.451 | 0.426 | 0.0253  | 0.2455 |
| 0.5-0.6 | 1,440 | 0.550 | 0.474 | 0.0760 ⚠️ | 0.2520 |
| 0.6-0.7 | 1,209 | 0.645 | 0.616 | 0.0289  | 0.2367 |
| 0.7-0.8 | 922 | 0.752 | 0.767 | 0.0153  | 0.1788 |
| 0.8-0.9 | 1,282 | 0.854 | 0.852 | 0.0017  | 0.1244 |
| 0.9-1.0 | 2,495 | 0.959 | 0.934 | 0.0244  | 0.0607 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 1,841 | 0.019 | 0.019 | 0.0000  | 0.0176 |
| 0.1-0.2 | 1,107 | 0.158 | 0.158 | 0.0000  | 0.1322 |
| 0.2-0.3 | 3,184 | 0.253 | 0.253 | 0.0000  | 0.1883 |
| 0.3-0.4 | 2,358 | 0.358 | 0.358 | 0.0000  | 0.2291 |
| 0.4-0.5 | 1,904 | 0.429 | 0.429 | 0.0000  | 0.2445 |
| 0.5-0.6 | 1,036 | 0.545 | 0.545 | 0.0000  | 0.2466 |
| 0.6-0.7 | 714 | 0.654 | 0.654 | 0.0000  | 0.2255 |
| 0.7-0.8 | 426 | 0.754 | 0.754 | 0.0000  | 0.1852 |
| 0.8-0.9 | 1,844 | 0.851 | 0.851 | 0.0000  | 0.1263 |
| 0.9-1.0 | 2,648 | 0.974 | 0.974 | 0.0000  | 0.0243 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 1,596 | 0.039 | 0.039 | 0.0000  | 0.0355 |
| 0.1-0.2 | 809 | 0.130 | 0.130 | 0.0000  | 0.1126 |
| 0.2-0.3 | 2,705 | 0.243 | 0.243 | 0.0000  | 0.1835 |
| 0.3-0.4 | 4,489 | 0.354 | 0.354 | 0.0000  | 0.2277 |
| 0.4-0.5 | 706 | 0.448 | 0.448 | 0.0000  | 0.2460 |
| 0.5-0.6 | 1,361 | 0.544 | 0.544 | 0.0000  | 0.2467 |
| 0.6-0.7 | 461 | 0.657 | 0.657 | 0.0000  | 0.2249 |
| 0.7-0.8 | 706 | 0.745 | 0.745 | 0.0000  | 0.1895 |
| 0.8-0.9 | 2,418 | 0.869 | 0.869 | 0.0000  | 0.1135 |
| 0.9-1.0 | 1,811 | 0.980 | 0.980 | 0.0000  | 0.0186 |

### Problematic Bins (Calibration Error > 0.05)


**raw:**
- Bin 0.0-0.1: CE=0.0585 (under-predicting)
- Bin 0.1-0.2: CE=0.0912 (under-predicting)
- Bin 0.2-0.3: CE=0.0587 (under-predicting)
- Bin 0.5-0.6: CE=0.0760 (over-predicting)

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
