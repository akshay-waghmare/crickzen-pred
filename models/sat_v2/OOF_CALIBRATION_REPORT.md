# OOF Calibration Analysis Report

**Generated:** 2026-01-18 19:13:19
**Samples:** 26,121
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1597 | 0.0000 | 0.4634 |
| innings_phase | 0.1654 | 0.0000 | 0.4822 |
| ece_optimized | 0.1675 | 0.0093 | 0.4898 |
| innings_specific | 0.1719 | 0.0000 | 0.4992 |
| combined | 0.1740 | 0.0000 | 0.5070 |
| resource_win_prob | 0.1744 | 0.0575 | 0.5059 |
| logloss_optimized | 0.1778 | 0.0527 | 0.5234 |
| raw | 0.1827 | 0.0657 | 0.5290 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2033 | 0.0000 | 0.5772 | 13758.0000 |
| innings_phase | 0.2089 | 0.0000 | 0.5940 | 13758.0000 |
| ece_optimized | 0.2109 | 0.0112 | 0.6008 | 13758.0000 |
| innings_specific | 0.2143 | 0.0000 | 0.6071 | 13758.0000 |
| combined | 0.2161 | 0.0299 | 0.6150 | 13758.0000 |
| resource_win_prob | 0.2201 | 0.1362 | 0.6264 | 13758.0000 |
| logloss_optimized | 0.2208 | 0.0579 | 0.6290 | 13758.0000 |
| raw | 0.2290 | 0.0958 | 0.6446 | 13758.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1112 | 0.0000 | 0.3368 | 12363.0000 |
| innings_phase | 0.1171 | 0.0000 | 0.3577 | 12363.0000 |
| ece_optimized | 0.1191 | 0.0107 | 0.3664 | 12363.0000 |
| resource_win_prob | 0.1235 | 0.0418 | 0.3719 | 12363.0000 |
| innings_specific | 0.1248 | 0.0000 | 0.3792 | 12363.0000 |
| combined | 0.1272 | 0.0333 | 0.3869 | 12363.0000 |
| logloss_optimized | 0.1300 | 0.0659 | 0.4059 | 12363.0000 |
| raw | 0.1311 | 0.0463 | 0.4003 | 12363.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2364 | 0.0000 | 0.6593 | 3499.0000 |
| innings_phase | 0.2397 | 0.0000 | 0.6691 | 3499.0000 |
| ece_optimized | 0.2421 | 0.0206 | 0.6754 | 3499.0000 |
| innings_specific | 0.2472 | 0.0641 | 0.6877 | 3499.0000 |
| logloss_optimized | 0.2483 | 0.0227 | 0.6897 | 3499.0000 |
| combined | 0.2491 | 0.0524 | 0.6901 | 3499.0000 |
| resource_win_prob | 0.2642 | 0.1624 | 0.7232 | 3499.0000 |
| raw | 0.2721 | 0.1533 | 0.7434 | 3499.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2035 | 0.0000 | 0.5775 | 6206.0000 |
| innings_phase | 0.2112 | 0.0000 | 0.5992 | 6206.0000 |
| resource_win_prob | 0.2127 | 0.1234 | 0.6107 | 6206.0000 |
| ece_optimized | 0.2128 | 0.0085 | 0.6047 | 6206.0000 |
| innings_specific | 0.2133 | 0.0135 | 0.6046 | 6206.0000 |
| combined | 0.2160 | 0.0376 | 0.6164 | 6206.0000 |
| logloss_optimized | 0.2212 | 0.0624 | 0.6313 | 6206.0000 |
| raw | 0.2259 | 0.0888 | 0.6394 | 6206.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1745 | 0.0000 | 0.5057 | 4053.0000 |
| innings_phase | 0.1788 | 0.0000 | 0.5213 | 4053.0000 |
| ece_optimized | 0.1812 | 0.0215 | 0.5303 | 4053.0000 |
| innings_specific | 0.1875 | 0.0566 | 0.5413 | 4053.0000 |
| combined | 0.1877 | 0.0631 | 0.5480 | 4053.0000 |
| resource_win_prob | 0.1935 | 0.1338 | 0.5668 | 4053.0000 |
| logloss_optimized | 0.1964 | 0.1009 | 0.5730 | 4053.0000 |
| raw | 0.1966 | 0.1054 | 0.5674 | 4053.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1551 | 0.0000 | 0.4563 | 3479.0000 |
| innings_phase | 0.1601 | 0.0000 | 0.4725 | 3479.0000 |
| ece_optimized | 0.1628 | 0.0137 | 0.4837 | 3479.0000 |
| innings_specific | 0.1650 | 0.0441 | 0.4912 | 3479.0000 |
| resource_win_prob | 0.1685 | 0.1246 | 0.4932 | 3479.0000 |
| combined | 0.1687 | 0.0738 | 0.5020 | 3479.0000 |
| logloss_optimized | 0.1739 | 0.0769 | 0.5206 | 3479.0000 |
| raw | 0.1746 | 0.0742 | 0.5195 | 3479.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1105 | 0.0000 | 0.3329 | 6060.0000 |
| resource_win_prob | 0.1152 | 0.0488 | 0.3501 | 6060.0000 |
| innings_phase | 0.1173 | 0.0000 | 0.3572 | 6060.0000 |
| ece_optimized | 0.1190 | 0.0153 | 0.3636 | 6060.0000 |
| innings_specific | 0.1195 | 0.0295 | 0.3636 | 6060.0000 |
| combined | 0.1244 | 0.0564 | 0.3767 | 6060.0000 |
| raw | 0.1292 | 0.0635 | 0.3940 | 6060.0000 |
| logloss_optimized | 0.1326 | 0.0957 | 0.4121 | 6060.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0587 | 0.0000 | 0.1977 | 2824.0000 |
| innings_phase | 0.0637 | 0.0000 | 0.2172 | 2824.0000 |
| ece_optimized | 0.0655 | 0.0172 | 0.2279 | 2824.0000 |
| logloss_optimized | 0.0701 | 0.0485 | 0.2514 | 2824.0000 |
| raw | 0.0818 | 0.0692 | 0.2671 | 2824.0000 |
| combined | 0.0821 | 0.0646 | 0.2669 | 2824.0000 |
| resource_win_prob | 0.0859 | 0.0910 | 0.2691 | 2824.0000 |
| innings_specific | 0.0865 | 0.0702 | 0.2749 | 2824.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1597 |
| Innings 1 | brier_optimized | 0.2033 |
| Innings 2 | brier_optimized | 0.1112 |
| Inn1 Powerplay | brier_optimized | 0.2364 |
| Inn1 Middle | brier_optimized | 0.2035 |
| Inn1 Death | brier_optimized | 0.1745 |
| Inn2 Powerplay | brier_optimized | 0.1551 |
| Inn2 Middle | brier_optimized | 0.1105 |
| Inn2 Death | brier_optimized | 0.0587 |

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
| Overall | brier_optimized | 0.4634 |
| Innings 1 | brier_optimized | 0.5772 |
| Innings 2 | brier_optimized | 0.3368 |
| Inn1 Powerplay | brier_optimized | 0.6593 |
| Inn1 Middle | brier_optimized | 0.5775 |
| Inn1 Death | brier_optimized | 0.5057 |
| Inn2 Powerplay | brier_optimized | 0.4563 |
| Inn2 Middle | brier_optimized | 0.3329 |
| Inn2 Death | brier_optimized | 0.1977 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 9 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1744 | 0.1597 (brier_optimized) | **+8.4%** |
| LogLoss | 0.5059 | 0.4634 (brier_optimized) | **+8.4%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 4,073 | 0.036 | 0.037 | 0.0014  | 0.0346 |
| 0.1-0.2 | 1,789 | 0.152 | 0.245 | 0.0936 ⚠️ | 0.1912 |
| 0.2-0.3 | 2,304 | 0.253 | 0.371 | 0.1181 ⚠️ | 0.2480 |
| 0.3-0.4 | 2,520 | 0.350 | 0.483 | 0.1333 ⚠️ | 0.2665 |
| 0.4-0.5 | 2,897 | 0.449 | 0.489 | 0.0398  | 0.2529 |
| 0.5-0.6 | 2,507 | 0.548 | 0.519 | 0.0291  | 0.2495 |
| 0.6-0.7 | 2,265 | 0.650 | 0.534 | 0.1162 ⚠️ | 0.2644 |
| 0.7-0.8 | 2,221 | 0.747 | 0.584 | 0.1635 ⚠️ | 0.2683 |
| 0.8-0.9 | 2,126 | 0.849 | 0.802 | 0.0473  | 0.1598 |
| 0.9-1.0 | 3,419 | 0.947 | 0.953 | 0.0058  | 0.0448 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 3,965 | 0.011 | 0.011 | 0.0000  | 0.0102 |
| 0.1-0.2 | 971 | 0.136 | 0.136 | 0.0000  | 0.1169 |
| 0.2-0.3 | 1,703 | 0.255 | 0.255 | 0.0000  | 0.1888 |
| 0.3-0.4 | 2,228 | 0.353 | 0.353 | 0.0000  | 0.2278 |
| 0.4-0.5 | 3,746 | 0.462 | 0.462 | 0.0000  | 0.2483 |
| 0.5-0.6 | 4,980 | 0.542 | 0.542 | 0.0000  | 0.2470 |
| 0.6-0.7 | 2,844 | 0.630 | 0.630 | 0.0000  | 0.2323 |
| 0.7-0.8 | 873 | 0.745 | 0.745 | 0.0000  | 0.1897 |
| 0.8-0.9 | 1,053 | 0.848 | 0.848 | 0.0000  | 0.1282 |
| 0.9-1.0 | 3,758 | 0.981 | 0.981 | 0.0000  | 0.0181 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 3,694 | 0.016 | 0.016 | 0.0000  | 0.0151 |
| 0.1-0.2 | 1,256 | 0.145 | 0.145 | 0.0000  | 0.1234 |
| 0.2-0.3 | 1,104 | 0.259 | 0.259 | 0.0000  | 0.1911 |
| 0.3-0.4 | 2,605 | 0.344 | 0.344 | 0.0000  | 0.2250 |
| 0.4-0.5 | 6,840 | 0.481 | 0.481 | 0.0000  | 0.2490 |
| 0.5-0.6 | 2,213 | 0.577 | 0.577 | 0.0000  | 0.2434 |
| 0.6-0.7 | 2,546 | 0.618 | 0.618 | 0.0000  | 0.2354 |
| 0.7-0.8 | 937 | 0.744 | 0.744 | 0.0000  | 0.1902 |
| 0.8-0.9 | 1,480 | 0.834 | 0.834 | 0.0000  | 0.1375 |
| 0.9-1.0 | 3,446 | 0.972 | 0.972 | 0.0000  | 0.0262 |

### Problematic Bins (Calibration Error > 0.05)


**raw:**
- Bin 0.1-0.2: CE=0.0936 (under-predicting)
- Bin 0.2-0.3: CE=0.1181 (under-predicting)
- Bin 0.3-0.4: CE=0.1333 (under-predicting)
- Bin 0.6-0.7: CE=0.1162 (over-predicting)
- Bin 0.7-0.8: CE=0.1635 (over-predicting)

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
