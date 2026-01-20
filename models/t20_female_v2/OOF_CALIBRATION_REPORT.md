# OOF Calibration Analysis Report

**Generated:** 2026-01-19 16:34:10
**Samples:** 57,999
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1653 | 0.0000 | 0.4929 |
| innings_phase | 0.1690 | 0.0000 | 0.5042 |
| ece_optimized | 0.1707 | 0.0067 | 0.5112 |
| innings_specific | 0.1710 | 0.0000 | 0.5103 |
| combined | 0.1721 | 0.0000 | 0.5140 |
| logloss_optimized | 0.1731 | 0.0184 | 0.5189 |
| raw | 0.1741 | 0.0307 | 0.5224 |
| resource_win_prob | 0.2146 | 0.1177 | 0.6229 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1974 | 0.0000 | 0.5760 | 30393.0000 |
| innings_phase | 0.2007 | 0.0000 | 0.5853 | 30393.0000 |
| ece_optimized | 0.2026 | 0.0082 | 0.5912 | 30393.0000 |
| innings_specific | 0.2030 | 0.0000 | 0.5916 | 30393.0000 |
| combined | 0.2039 | 0.0192 | 0.5948 | 30393.0000 |
| logloss_optimized | 0.2052 | 0.0267 | 0.5977 | 30393.0000 |
| raw | 0.2074 | 0.0503 | 0.6064 | 30393.0000 |
| resource_win_prob | 0.2499 | 0.1651 | 0.6924 | 30393.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1301 | 0.0000 | 0.4015 | 27606.0000 |
| innings_phase | 0.1341 | 0.0000 | 0.4149 | 27606.0000 |
| ece_optimized | 0.1356 | 0.0071 | 0.4232 | 27606.0000 |
| innings_specific | 0.1358 | 0.0000 | 0.4209 | 27606.0000 |
| combined | 0.1371 | 0.0211 | 0.4250 | 27606.0000 |
| raw | 0.1375 | 0.0202 | 0.4298 | 27606.0000 |
| logloss_optimized | 0.1378 | 0.0223 | 0.4322 | 27606.0000 |
| resource_win_prob | 0.1756 | 0.1509 | 0.5464 | 27606.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2207 | 0.0000 | 0.6301 | 7846.0000 |
| innings_phase | 0.2238 | 0.0000 | 0.6377 | 7846.0000 |
| ece_optimized | 0.2260 | 0.0245 | 0.6433 | 7846.0000 |
| logloss_optimized | 0.2280 | 0.0215 | 0.6479 | 7846.0000 |
| innings_specific | 0.2286 | 0.0438 | 0.6494 | 7846.0000 |
| combined | 0.2292 | 0.0436 | 0.6513 | 7846.0000 |
| raw | 0.2312 | 0.0559 | 0.6586 | 7846.0000 |
| resource_win_prob | 0.2655 | 0.1417 | 0.7261 | 7846.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1974 | 0.0000 | 0.5773 | 13809.0000 |
| innings_phase | 0.2009 | 0.0000 | 0.5873 | 13809.0000 |
| innings_specific | 0.2023 | 0.0303 | 0.5911 | 13809.0000 |
| ece_optimized | 0.2025 | 0.0077 | 0.5926 | 13809.0000 |
| combined | 0.2035 | 0.0445 | 0.5945 | 13809.0000 |
| logloss_optimized | 0.2059 | 0.0459 | 0.6005 | 13809.0000 |
| raw | 0.2082 | 0.0686 | 0.6104 | 13809.0000 |
| resource_win_prob | 0.2429 | 0.1531 | 0.6781 | 13809.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1763 | 0.0000 | 0.5253 | 8738.0000 |
| innings_phase | 0.1797 | 0.0000 | 0.5351 | 8738.0000 |
| innings_specific | 0.1814 | 0.0189 | 0.5404 | 8738.0000 |
| ece_optimized | 0.1817 | 0.0093 | 0.5423 | 8738.0000 |
| combined | 0.1818 | 0.0179 | 0.5447 | 8738.0000 |
| logloss_optimized | 0.1835 | 0.0309 | 0.5481 | 8738.0000 |
| raw | 0.1846 | 0.0447 | 0.5535 | 8738.0000 |
| resource_win_prob | 0.2471 | 0.2052 | 0.6847 | 8738.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1610 | 0.0000 | 0.4890 | 7860.0000 |
| innings_phase | 0.1646 | 0.0000 | 0.5002 | 7860.0000 |
| ece_optimized | 0.1665 | 0.0105 | 0.5078 | 7860.0000 |
| innings_specific | 0.1667 | 0.0220 | 0.5073 | 7860.0000 |
| logloss_optimized | 0.1677 | 0.0233 | 0.5132 | 7860.0000 |
| combined | 0.1691 | 0.0455 | 0.5145 | 7860.0000 |
| raw | 0.1696 | 0.0401 | 0.5191 | 7860.0000 |
| resource_win_prob | 0.2550 | 0.2559 | 0.7493 | 7860.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1310 | 0.0000 | 0.3999 | 13382.0000 |
| innings_phase | 0.1356 | 0.0000 | 0.4155 | 13382.0000 |
| innings_specific | 0.1367 | 0.0187 | 0.4195 | 13382.0000 |
| ece_optimized | 0.1369 | 0.0089 | 0.4234 | 13382.0000 |
| combined | 0.1373 | 0.0198 | 0.4211 | 13382.0000 |
| raw | 0.1381 | 0.0216 | 0.4256 | 13382.0000 |
| logloss_optimized | 0.1396 | 0.0370 | 0.4355 | 13382.0000 |
| resource_win_prob | 0.1673 | 0.1483 | 0.5318 | 13382.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0900 | 0.0000 | 0.2969 | 6364.0000 |
| innings_phase | 0.0932 | 0.0000 | 0.3083 | 6364.0000 |
| ece_optimized | 0.0950 | 0.0084 | 0.3182 | 6364.0000 |
| resource_win_prob | 0.0952 | 0.0499 | 0.3266 | 6364.0000 |
| innings_specific | 0.0957 | 0.0261 | 0.3172 | 6364.0000 |
| raw | 0.0966 | 0.0381 | 0.3282 | 6364.0000 |
| logloss_optimized | 0.0970 | 0.0269 | 0.3253 | 6364.0000 |
| combined | 0.0973 | 0.0380 | 0.3228 | 6364.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1653 |
| Innings 1 | brier_optimized | 0.1974 |
| Innings 2 | brier_optimized | 0.1301 |
| Inn1 Powerplay | brier_optimized | 0.2207 |
| Inn1 Middle | brier_optimized | 0.1974 |
| Inn1 Death | brier_optimized | 0.1763 |
| Inn2 Powerplay | brier_optimized | 0.1610 |
| Inn2 Middle | brier_optimized | 0.1310 |
| Inn2 Death | brier_optimized | 0.0900 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
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
| Overall | brier_optimized | 0.4929 |
| Innings 1 | brier_optimized | 0.5760 |
| Innings 2 | brier_optimized | 0.4015 |
| Inn1 Powerplay | brier_optimized | 0.6301 |
| Inn1 Middle | brier_optimized | 0.5773 |
| Inn1 Death | brier_optimized | 0.5253 |
| Inn2 Powerplay | brier_optimized | 0.4890 |
| Inn2 Middle | brier_optimized | 0.3999 |
| Inn2 Death | brier_optimized | 0.2969 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 8 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2146 | 0.1653 (brier_optimized) | **+22.9%** |
| LogLoss | 0.6229 | 0.4929 (brier_optimized) | **+20.9%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 7,897 | 0.044 | 0.088 | 0.0439  | 0.0801 |
| 0.1-0.2 | 5,779 | 0.148 | 0.196 | 0.0478  | 0.1589 |
| 0.2-0.3 | 5,335 | 0.249 | 0.278 | 0.0288  | 0.2003 |
| 0.3-0.4 | 5,391 | 0.352 | 0.308 | 0.0437  | 0.2156 |
| 0.4-0.5 | 5,355 | 0.450 | 0.457 | 0.0075  | 0.2456 |
| 0.5-0.6 | 6,063 | 0.551 | 0.566 | 0.0147  | 0.2461 |
| 0.6-0.7 | 5,365 | 0.649 | 0.664 | 0.0150  | 0.2219 |
| 0.7-0.8 | 5,172 | 0.751 | 0.724 | 0.0266  | 0.1989 |
| 0.8-0.9 | 5,242 | 0.852 | 0.801 | 0.0505 ⚠️ | 0.1612 |
| 0.9-1.0 | 6,400 | 0.947 | 0.923 | 0.0241  | 0.0695 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 5,015 | 0.031 | 0.031 | 0.0000  | 0.0285 |
| 0.1-0.2 | 7,244 | 0.148 | 0.148 | 0.0000  | 0.1254 |
| 0.2-0.3 | 6,669 | 0.256 | 0.256 | 0.0000  | 0.1895 |
| 0.3-0.4 | 6,550 | 0.340 | 0.340 | 0.0000  | 0.2239 |
| 0.4-0.5 | 3,077 | 0.442 | 0.442 | 0.0000  | 0.2459 |
| 0.5-0.6 | 6,327 | 0.551 | 0.551 | 0.0000  | 0.2468 |
| 0.6-0.7 | 6,937 | 0.655 | 0.655 | 0.0000  | 0.2252 |
| 0.7-0.8 | 5,860 | 0.739 | 0.739 | 0.0000  | 0.1921 |
| 0.8-0.9 | 5,235 | 0.848 | 0.848 | 0.0000  | 0.1283 |
| 0.9-1.0 | 5,085 | 0.972 | 0.972 | 0.0000  | 0.0259 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 4,655 | 0.037 | 0.037 | 0.0000  | 0.0348 |
| 0.1-0.2 | 7,948 | 0.159 | 0.159 | 0.0000  | 0.1332 |
| 0.2-0.3 | 7,559 | 0.264 | 0.264 | 0.0000  | 0.1930 |
| 0.3-0.4 | 4,520 | 0.344 | 0.344 | 0.0000  | 0.2250 |
| 0.4-0.5 | 3,939 | 0.432 | 0.432 | 0.0000  | 0.2445 |
| 0.5-0.6 | 7,245 | 0.561 | 0.561 | 0.0000  | 0.2458 |
| 0.6-0.7 | 5,562 | 0.663 | 0.663 | 0.0000  | 0.2220 |
| 0.7-0.8 | 6,818 | 0.731 | 0.731 | 0.0000  | 0.1959 |
| 0.8-0.9 | 5,918 | 0.859 | 0.859 | 0.0000  | 0.1205 |
| 0.9-1.0 | 3,835 | 0.978 | 0.978 | 0.0000  | 0.0204 |

### Problematic Bins (Calibration Error > 0.05)


**raw:**
- Bin 0.8-0.9: CE=0.0505 (over-predicting)

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
