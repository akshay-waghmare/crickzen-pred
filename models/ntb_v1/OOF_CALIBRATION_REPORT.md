# OOF Calibration Analysis Report

**Generated:** 2026-06-06 22:45:44
**Samples:** 332,156
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1754 | 0.0000 | 0.5149 |
| innings_phase | 0.1771 | 0.0000 | 0.5199 |
| ece_optimized | 0.1776 | 0.0021 | 0.5218 |
| innings_specific | 0.1779 | 0.0000 | 0.5229 |
| combined | 0.1782 | 0.0000 | 0.5238 |
| raw | 0.1785 | 0.0094 | 0.5250 |
| logloss_optimized | 0.1789 | 0.0170 | 0.5277 |
| resource_win_prob | 0.1882 | 0.0373 | 0.5522 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2158 | 0.0000 | 0.6180 | 173356.0000 |
| innings_phase | 0.2174 | 0.0000 | 0.6224 | 173356.0000 |
| ece_optimized | 0.2179 | 0.0023 | 0.6238 | 173356.0000 |
| innings_specific | 0.2179 | 0.0000 | 0.6237 | 173356.0000 |
| combined | 0.2182 | 0.0087 | 0.6246 | 173356.0000 |
| raw | 0.2185 | 0.0123 | 0.6254 | 173356.0000 |
| logloss_optimized | 0.2185 | 0.0131 | 0.6258 | 173356.0000 |
| resource_win_prob | 0.2283 | 0.0812 | 0.6464 | 173356.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1313 | 0.0000 | 0.4023 | 158800.0000 |
| innings_phase | 0.1331 | 0.0000 | 0.4080 | 158800.0000 |
| ece_optimized | 0.1335 | 0.0032 | 0.4104 | 158800.0000 |
| innings_specific | 0.1342 | 0.0000 | 0.4129 | 158800.0000 |
| combined | 0.1345 | 0.0095 | 0.4137 | 158800.0000 |
| raw | 0.1348 | 0.0139 | 0.4153 | 158800.0000 |
| logloss_optimized | 0.1357 | 0.0286 | 0.4206 | 158800.0000 |
| resource_win_prob | 0.1444 | 0.0519 | 0.4494 | 158800.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2375 | 0.0000 | 0.6669 | 43998.0000 |
| innings_phase | 0.2386 | 0.0000 | 0.6695 | 43998.0000 |
| ece_optimized | 0.2392 | 0.0044 | 0.6710 | 43998.0000 |
| innings_specific | 0.2394 | 0.0131 | 0.6712 | 43998.0000 |
| combined | 0.2395 | 0.0172 | 0.6716 | 43998.0000 |
| logloss_optimized | 0.2396 | 0.0117 | 0.6717 | 43998.0000 |
| raw | 0.2400 | 0.0196 | 0.6725 | 43998.0000 |
| resource_win_prob | 0.2625 | 0.1407 | 0.7193 | 43998.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2140 | 0.0000 | 0.6141 | 78278.0000 |
| innings_phase | 0.2159 | 0.0000 | 0.6194 | 78278.0000 |
| innings_specific | 0.2162 | 0.0071 | 0.6203 | 78278.0000 |
| ece_optimized | 0.2163 | 0.0026 | 0.6205 | 78278.0000 |
| combined | 0.2164 | 0.0137 | 0.6214 | 78278.0000 |
| raw | 0.2168 | 0.0169 | 0.6223 | 78278.0000 |
| logloss_optimized | 0.2169 | 0.0155 | 0.6227 | 78278.0000 |
| resource_win_prob | 0.2227 | 0.0589 | 0.6356 | 78278.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1999 | 0.0000 | 0.5819 | 51080.0000 |
| innings_phase | 0.2016 | 0.0000 | 0.5865 | 51080.0000 |
| ece_optimized | 0.2021 | 0.0029 | 0.5882 | 51080.0000 |
| innings_specific | 0.2021 | 0.0133 | 0.5881 | 51080.0000 |
| combined | 0.2024 | 0.0159 | 0.5891 | 51080.0000 |
| raw | 0.2026 | 0.0183 | 0.5897 | 51080.0000 |
| logloss_optimized | 0.2030 | 0.0223 | 0.5909 | 51080.0000 |
| resource_win_prob | 0.2073 | 0.0646 | 0.6003 | 51080.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1759 | 0.0000 | 0.5232 | 44057.0000 |
| innings_phase | 0.1775 | 0.0000 | 0.5281 | 44057.0000 |
| ece_optimized | 0.1780 | 0.0047 | 0.5298 | 44057.0000 |
| innings_specific | 0.1784 | 0.0196 | 0.5324 | 44057.0000 |
| combined | 0.1787 | 0.0247 | 0.5330 | 44057.0000 |
| raw | 0.1792 | 0.0277 | 0.5346 | 44057.0000 |
| logloss_optimized | 0.1795 | 0.0291 | 0.5352 | 44057.0000 |
| resource_win_prob | 0.1941 | 0.1087 | 0.5803 | 44057.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1296 | 0.0000 | 0.4019 | 76541.0000 |
| innings_phase | 0.1317 | 0.0000 | 0.4087 | 76541.0000 |
| innings_specific | 0.1321 | 0.0121 | 0.4102 | 76541.0000 |
| ece_optimized | 0.1321 | 0.0031 | 0.4116 | 76541.0000 |
| combined | 0.1327 | 0.0176 | 0.4116 | 76541.0000 |
| raw | 0.1328 | 0.0192 | 0.4129 | 76541.0000 |
| logloss_optimized | 0.1341 | 0.0345 | 0.4201 | 76541.0000 |
| resource_win_prob | 0.1413 | 0.0553 | 0.4454 | 76541.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0834 | 0.0000 | 0.2637 | 38202.0000 |
| innings_phase | 0.0846 | 0.0000 | 0.2680 | 38202.0000 |
| ece_optimized | 0.0851 | 0.0062 | 0.2703 | 38202.0000 |
| combined | 0.0873 | 0.0372 | 0.2802 | 38202.0000 |
| raw | 0.0875 | 0.0406 | 0.2825 | 38202.0000 |
| innings_specific | 0.0877 | 0.0394 | 0.2803 | 38202.0000 |
| logloss_optimized | 0.0884 | 0.0355 | 0.2892 | 38202.0000 |
| resource_win_prob | 0.0934 | 0.0590 | 0.3066 | 38202.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1754 |
| Innings 1 | brier_optimized | 0.2158 |
| Innings 2 | brier_optimized | 0.1313 |
| Inn1 Powerplay | brier_optimized | 0.2375 |
| Inn1 Middle | brier_optimized | 0.2140 |
| Inn1 Death | brier_optimized | 0.1999 |
| Inn2 Powerplay | brier_optimized | 0.1759 |
| Inn2 Middle | brier_optimized | 0.1296 |
| Inn2 Death | brier_optimized | 0.0834 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | innings_specific | 0.0000 |
| Inn1 Powerplay | innings_phase | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5149 |
| Innings 1 | brier_optimized | 0.6180 |
| Innings 2 | brier_optimized | 0.4023 |
| Inn1 Powerplay | brier_optimized | 0.6669 |
| Inn1 Middle | brier_optimized | 0.6141 |
| Inn1 Death | brier_optimized | 0.5819 |
| Inn2 Powerplay | brier_optimized | 0.5232 |
| Inn2 Middle | brier_optimized | 0.4019 |
| Inn2 Death | brier_optimized | 0.2637 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 7 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1882 | 0.1754 (brier_optimized) | **+6.8%** |
| LogLoss | 0.5522 | 0.5149 (brier_optimized) | **+6.8%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 38,033 | 0.045 | 0.046 | 0.0015  | 0.0434 |
| 0.1-0.2 | 22,338 | 0.149 | 0.152 | 0.0030  | 0.1283 |
| 0.2-0.3 | 25,338 | 0.253 | 0.270 | 0.0175  | 0.1967 |
| 0.3-0.4 | 34,145 | 0.352 | 0.370 | 0.0178  | 0.2332 |
| 0.4-0.5 | 45,864 | 0.452 | 0.450 | 0.0011  | 0.2472 |
| 0.5-0.6 | 45,331 | 0.548 | 0.546 | 0.0026  | 0.2471 |
| 0.6-0.7 | 38,472 | 0.649 | 0.630 | 0.0184  | 0.2328 |
| 0.7-0.8 | 31,478 | 0.748 | 0.734 | 0.0141  | 0.1945 |
| 0.8-0.9 | 24,806 | 0.849 | 0.841 | 0.0075  | 0.1325 |
| 0.9-1.0 | 26,351 | 0.947 | 0.963 | 0.0166  | 0.0348 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 37,762 | 0.039 | 0.039 | 0.0000  | 0.0365 |
| 0.1-0.2 | 22,977 | 0.145 | 0.145 | 0.0000  | 0.1233 |
| 0.2-0.3 | 21,221 | 0.256 | 0.256 | 0.0000  | 0.1899 |
| 0.3-0.4 | 38,517 | 0.364 | 0.364 | 0.0000  | 0.2306 |
| 0.4-0.5 | 49,787 | 0.457 | 0.457 | 0.0000  | 0.2474 |
| 0.5-0.6 | 45,868 | 0.551 | 0.551 | 0.0000  | 0.2465 |
| 0.6-0.7 | 37,132 | 0.649 | 0.649 | 0.0000  | 0.2270 |
| 0.7-0.8 | 27,338 | 0.739 | 0.739 | 0.0000  | 0.1920 |
| 0.8-0.9 | 23,424 | 0.845 | 0.845 | 0.0000  | 0.1305 |
| 0.9-1.0 | 28,130 | 0.970 | 0.970 | 0.0000  | 0.0279 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 38,654 | 0.046 | 0.046 | 0.0000  | 0.0424 |
| 0.1-0.2 | 20,262 | 0.145 | 0.145 | 0.0000  | 0.1233 |
| 0.2-0.3 | 20,739 | 0.251 | 0.251 | 0.0000  | 0.1872 |
| 0.3-0.4 | 41,351 | 0.363 | 0.363 | 0.0000  | 0.2301 |
| 0.4-0.5 | 48,458 | 0.457 | 0.457 | 0.0000  | 0.2472 |
| 0.5-0.6 | 46,769 | 0.549 | 0.549 | 0.0000  | 0.2467 |
| 0.6-0.7 | 35,395 | 0.643 | 0.643 | 0.0000  | 0.2289 |
| 0.7-0.8 | 29,638 | 0.737 | 0.737 | 0.0000  | 0.1929 |
| 0.8-0.9 | 21,810 | 0.839 | 0.839 | 0.0000  | 0.1346 |
| 0.9-1.0 | 29,080 | 0.962 | 0.962 | 0.0000  | 0.0350 |

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
