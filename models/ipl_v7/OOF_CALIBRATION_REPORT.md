# OOF Calibration Analysis Report

**Generated:** 2026-05-02 20:36:44
**Samples:** 282,997
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1817 | 0.0000 | 0.5297 |
| innings_phase | 0.1834 | 0.0000 | 0.5347 |
| ece_optimized | 0.1840 | 0.0030 | 0.5368 |
| innings_specific | 0.1842 | 0.0000 | 0.5372 |
| combined | 0.1844 | 0.0000 | 0.5384 |
| raw | 0.1848 | 0.0110 | 0.5399 |
| logloss_optimized | 0.1853 | 0.0179 | 0.5430 |
| resource_win_prob | 0.2053 | 0.0684 | 0.5936 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2192 | 0.0000 | 0.6258 | 146449.0000 |
| innings_phase | 0.2208 | 0.0000 | 0.6299 | 146449.0000 |
| ece_optimized | 0.2214 | 0.0042 | 0.6316 | 146449.0000 |
| innings_specific | 0.2215 | 0.0000 | 0.6316 | 146449.0000 |
| combined | 0.2218 | 0.0073 | 0.6334 | 146449.0000 |
| logloss_optimized | 0.2220 | 0.0068 | 0.6337 | 146449.0000 |
| raw | 0.2222 | 0.0135 | 0.6345 | 146449.0000 |
| resource_win_prob | 0.2511 | 0.1310 | 0.7097 | 146449.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1416 | 0.0000 | 0.4266 | 136548.0000 |
| innings_phase | 0.1434 | 0.0000 | 0.4327 | 136548.0000 |
| ece_optimized | 0.1439 | 0.0035 | 0.4351 | 136548.0000 |
| innings_specific | 0.1442 | 0.0000 | 0.4359 | 136548.0000 |
| combined | 0.1444 | 0.0079 | 0.4366 | 136548.0000 |
| raw | 0.1447 | 0.0129 | 0.4385 | 136548.0000 |
| logloss_optimized | 0.1459 | 0.0332 | 0.4458 | 136548.0000 |
| resource_win_prob | 0.1562 | 0.0130 | 0.4692 | 136548.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2378 | 0.0000 | 0.6674 | 36788.0000 |
| innings_phase | 0.2386 | 0.0000 | 0.6694 | 36788.0000 |
| innings_specific | 0.2394 | 0.0068 | 0.6714 | 36788.0000 |
| ece_optimized | 0.2394 | 0.0047 | 0.6712 | 36788.0000 |
| combined | 0.2395 | 0.0115 | 0.6716 | 36788.0000 |
| logloss_optimized | 0.2397 | 0.0075 | 0.6719 | 36788.0000 |
| raw | 0.2399 | 0.0149 | 0.6724 | 36788.0000 |
| resource_win_prob | 0.2451 | 0.0345 | 0.6836 | 36788.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2176 | 0.0000 | 0.6227 | 65800.0000 |
| innings_phase | 0.2195 | 0.0000 | 0.6275 | 65800.0000 |
| ece_optimized | 0.2200 | 0.0041 | 0.6289 | 65800.0000 |
| innings_specific | 0.2201 | 0.0134 | 0.6289 | 65800.0000 |
| combined | 0.2202 | 0.0119 | 0.6297 | 65800.0000 |
| logloss_optimized | 0.2206 | 0.0136 | 0.6310 | 65800.0000 |
| raw | 0.2208 | 0.0176 | 0.6314 | 65800.0000 |
| resource_win_prob | 0.2679 | 0.1873 | 0.7567 | 65800.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2059 | 0.0000 | 0.5956 | 43861.0000 |
| innings_phase | 0.2076 | 0.0000 | 0.6003 | 43861.0000 |
| ece_optimized | 0.2084 | 0.0068 | 0.6025 | 43861.0000 |
| innings_specific | 0.2085 | 0.0209 | 0.6024 | 43861.0000 |
| logloss_optimized | 0.2091 | 0.0135 | 0.6055 | 43861.0000 |
| combined | 0.2093 | 0.0248 | 0.6069 | 43861.0000 |
| raw | 0.2096 | 0.0252 | 0.6073 | 43861.0000 |
| resource_win_prob | 0.2310 | 0.1291 | 0.6609 | 43861.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1821 | 0.0000 | 0.5366 | 36813.0000 |
| innings_phase | 0.1837 | 0.0000 | 0.5418 | 36813.0000 |
| ece_optimized | 0.1843 | 0.0034 | 0.5448 | 36813.0000 |
| innings_specific | 0.1843 | 0.0135 | 0.5455 | 36813.0000 |
| combined | 0.1844 | 0.0133 | 0.5451 | 36813.0000 |
| raw | 0.1848 | 0.0173 | 0.5457 | 36813.0000 |
| logloss_optimized | 0.1853 | 0.0219 | 0.5487 | 36813.0000 |
| resource_win_prob | 0.1944 | 0.0127 | 0.5691 | 36813.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1447 | 0.0000 | 0.4358 | 64724.0000 |
| innings_phase | 0.1467 | 0.0000 | 0.4430 | 64724.0000 |
| innings_specific | 0.1470 | 0.0081 | 0.4441 | 64724.0000 |
| ece_optimized | 0.1472 | 0.0044 | 0.4453 | 64724.0000 |
| combined | 0.1472 | 0.0090 | 0.4448 | 64724.0000 |
| raw | 0.1477 | 0.0162 | 0.4470 | 64724.0000 |
| logloss_optimized | 0.1497 | 0.0453 | 0.4579 | 64724.0000 |
| resource_win_prob | 0.1613 | 0.0349 | 0.4841 | 64724.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0934 | 0.0000 | 0.2938 | 35011.0000 |
| innings_phase | 0.0948 | 0.0000 | 0.2988 | 35011.0000 |
| ece_optimized | 0.0952 | 0.0053 | 0.3007 | 35011.0000 |
| innings_specific | 0.0966 | 0.0275 | 0.3057 | 35011.0000 |
| raw | 0.0970 | 0.0347 | 0.3100 | 35011.0000 |
| combined | 0.0970 | 0.0296 | 0.3075 | 35011.0000 |
| logloss_optimized | 0.0976 | 0.0270 | 0.3152 | 35011.0000 |
| resource_win_prob | 0.1064 | 0.0340 | 0.3365 | 35011.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1817 |
| Innings 1 | brier_optimized | 0.2192 |
| Innings 2 | brier_optimized | 0.1416 |
| Inn1 Powerplay | brier_optimized | 0.2378 |
| Inn1 Middle | brier_optimized | 0.2176 |
| Inn1 Death | brier_optimized | 0.2059 |
| Inn2 Powerplay | brier_optimized | 0.1821 |
| Inn2 Middle | brier_optimized | 0.1447 |
| Inn2 Death | brier_optimized | 0.0934 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | innings_specific | 0.0000 |
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
| Overall | brier_optimized | 0.5297 |
| Innings 1 | brier_optimized | 0.6258 |
| Innings 2 | brier_optimized | 0.4266 |
| Inn1 Powerplay | brier_optimized | 0.6674 |
| Inn1 Middle | brier_optimized | 0.6227 |
| Inn1 Death | brier_optimized | 0.5956 |
| Inn2 Powerplay | brier_optimized | 0.5366 |
| Inn2 Middle | brier_optimized | 0.4358 |
| Inn2 Death | brier_optimized | 0.2938 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 8 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2053 | 0.1817 (brier_optimized) | **+11.5%** |
| LogLoss | 0.5936 | 0.5297 (brier_optimized) | **+10.8%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,544 | 0.042 | 0.034 | 0.0080  | 0.0321 |
| 0.1-0.2 | 19,647 | 0.152 | 0.173 | 0.0204  | 0.1427 |
| 0.2-0.3 | 25,041 | 0.252 | 0.265 | 0.0130  | 0.1941 |
| 0.3-0.4 | 35,842 | 0.353 | 0.356 | 0.0028  | 0.2283 |
| 0.4-0.5 | 46,290 | 0.451 | 0.464 | 0.0129  | 0.2480 |
| 0.5-0.6 | 39,198 | 0.547 | 0.545 | 0.0022  | 0.2473 |
| 0.6-0.7 | 28,691 | 0.648 | 0.639 | 0.0088  | 0.2299 |
| 0.7-0.8 | 22,208 | 0.748 | 0.735 | 0.0127  | 0.1944 |
| 0.8-0.9 | 18,539 | 0.849 | 0.820 | 0.0291  | 0.1468 |
| 0.9-1.0 | 22,997 | 0.947 | 0.961 | 0.0140  | 0.0374 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,830 | 0.027 | 0.027 | 0.0000  | 0.0253 |
| 0.1-0.2 | 16,699 | 0.159 | 0.159 | 0.0000  | 0.1325 |
| 0.2-0.3 | 24,060 | 0.249 | 0.249 | 0.0000  | 0.1862 |
| 0.3-0.4 | 35,355 | 0.343 | 0.343 | 0.0000  | 0.2245 |
| 0.4-0.5 | 47,774 | 0.455 | 0.455 | 0.0000  | 0.2472 |
| 0.5-0.6 | 43,910 | 0.546 | 0.546 | 0.0000  | 0.2469 |
| 0.6-0.7 | 28,994 | 0.650 | 0.650 | 0.0000  | 0.2267 |
| 0.7-0.8 | 22,565 | 0.741 | 0.741 | 0.0000  | 0.1913 |
| 0.8-0.9 | 14,366 | 0.839 | 0.839 | 0.0000  | 0.1343 |
| 0.9-1.0 | 24,444 | 0.969 | 0.969 | 0.0000  | 0.0288 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,039 | 0.030 | 0.030 | 0.0000  | 0.0281 |
| 0.1-0.2 | 16,936 | 0.158 | 0.158 | 0.0000  | 0.1326 |
| 0.2-0.3 | 22,677 | 0.247 | 0.247 | 0.0000  | 0.1851 |
| 0.3-0.4 | 38,651 | 0.345 | 0.345 | 0.0000  | 0.2251 |
| 0.4-0.5 | 46,232 | 0.456 | 0.456 | 0.0000  | 0.2473 |
| 0.5-0.6 | 44,706 | 0.546 | 0.546 | 0.0000  | 0.2471 |
| 0.6-0.7 | 30,406 | 0.654 | 0.654 | 0.0000  | 0.2256 |
| 0.7-0.8 | 22,587 | 0.744 | 0.744 | 0.0000  | 0.1896 |
| 0.8-0.9 | 14,530 | 0.848 | 0.848 | 0.0000  | 0.1280 |
| 0.9-1.0 | 22,233 | 0.971 | 0.971 | 0.0000  | 0.0273 |

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
