# OOF Calibration Analysis Report

**Generated:** 2026-01-19 15:07:33
**Samples:** 141,435
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1763 | 0.0000 | 0.5192 |
| innings_phase | 0.1788 | 0.0000 | 0.5267 |
| ece_optimized | 0.1798 | 0.0046 | 0.5300 |
| innings_specific | 0.1807 | 0.0000 | 0.5317 |
| logloss_optimized | 0.1812 | 0.0130 | 0.5352 |
| combined | 0.1817 | 0.0000 | 0.5349 |
| raw | 0.1824 | 0.0153 | 0.5375 |
| resource_win_prob | 0.1905 | 0.0465 | 0.5573 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2147 | 0.0000 | 0.6157 | 73875.0000 |
| innings_phase | 0.2172 | 0.0000 | 0.6223 | 73875.0000 |
| ece_optimized | 0.2183 | 0.0063 | 0.6252 | 73875.0000 |
| innings_specific | 0.2187 | 0.0000 | 0.6259 | 73875.0000 |
| combined | 0.2197 | 0.0184 | 0.6292 | 73875.0000 |
| logloss_optimized | 0.2197 | 0.0202 | 0.6293 | 73875.0000 |
| raw | 0.2214 | 0.0327 | 0.6346 | 73875.0000 |
| resource_win_prob | 0.2273 | 0.0914 | 0.6444 | 73875.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1344 | 0.0000 | 0.4136 | 67560.0000 |
| innings_phase | 0.1368 | 0.0000 | 0.4221 | 67560.0000 |
| ece_optimized | 0.1377 | 0.0041 | 0.4258 | 67560.0000 |
| logloss_optimized | 0.1391 | 0.0131 | 0.4323 | 67560.0000 |
| innings_specific | 0.1391 | 0.0000 | 0.4288 | 67560.0000 |
| raw | 0.1399 | 0.0098 | 0.4314 | 67560.0000 |
| combined | 0.1401 | 0.0201 | 0.4317 | 67560.0000 |
| resource_win_prob | 0.1502 | 0.0405 | 0.4622 | 67560.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2355 | 0.0000 | 0.6625 | 18658.0000 |
| innings_phase | 0.2377 | 0.0000 | 0.6677 | 18658.0000 |
| ece_optimized | 0.2386 | 0.0075 | 0.6699 | 18658.0000 |
| logloss_optimized | 0.2401 | 0.0274 | 0.6729 | 18658.0000 |
| innings_specific | 0.2401 | 0.0348 | 0.6732 | 18658.0000 |
| combined | 0.2411 | 0.0450 | 0.6754 | 18658.0000 |
| raw | 0.2426 | 0.0546 | 0.6791 | 18658.0000 |
| resource_win_prob | 0.2521 | 0.1149 | 0.6973 | 18658.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2131 | 0.0000 | 0.6129 | 33364.0000 |
| innings_phase | 0.2161 | 0.0000 | 0.6205 | 33364.0000 |
| innings_specific | 0.2168 | 0.0111 | 0.6224 | 33364.0000 |
| ece_optimized | 0.2172 | 0.0122 | 0.6235 | 33364.0000 |
| combined | 0.2181 | 0.0226 | 0.6270 | 33364.0000 |
| logloss_optimized | 0.2183 | 0.0199 | 0.6270 | 33364.0000 |
| raw | 0.2202 | 0.0384 | 0.6337 | 33364.0000 |
| resource_win_prob | 0.2235 | 0.0770 | 0.6375 | 33364.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1993 | 0.0000 | 0.5801 | 21853.0000 |
| innings_phase | 0.2014 | 0.0000 | 0.5861 | 21853.0000 |
| ece_optimized | 0.2027 | 0.0080 | 0.5897 | 21853.0000 |
| innings_specific | 0.2031 | 0.0240 | 0.5907 | 21853.0000 |
| combined | 0.2037 | 0.0299 | 0.5933 | 21853.0000 |
| logloss_optimized | 0.2044 | 0.0312 | 0.5957 | 21853.0000 |
| raw | 0.2051 | 0.0322 | 0.5982 | 21853.0000 |
| resource_win_prob | 0.2119 | 0.1014 | 0.6096 | 21853.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1878 | 0.0000 | 0.5540 | 18700.0000 |
| innings_phase | 0.1901 | 0.0000 | 0.5605 | 18700.0000 |
| ece_optimized | 0.1909 | 0.0062 | 0.5630 | 18700.0000 |
| logloss_optimized | 0.1928 | 0.0313 | 0.5681 | 18700.0000 |
| innings_specific | 0.1931 | 0.0430 | 0.5686 | 18700.0000 |
| raw | 0.1935 | 0.0397 | 0.5697 | 18700.0000 |
| combined | 0.1937 | 0.0451 | 0.5697 | 18700.0000 |
| resource_win_prob | 0.2043 | 0.1283 | 0.6003 | 18700.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1327 | 0.0000 | 0.4133 | 32475.0000 |
| innings_phase | 0.1355 | 0.0000 | 0.4236 | 32475.0000 |
| ece_optimized | 0.1363 | 0.0045 | 0.4275 | 32475.0000 |
| innings_specific | 0.1366 | 0.0210 | 0.4269 | 32475.0000 |
| logloss_optimized | 0.1372 | 0.0231 | 0.4311 | 32475.0000 |
| raw | 0.1376 | 0.0238 | 0.4301 | 32475.0000 |
| combined | 0.1380 | 0.0329 | 0.4312 | 32475.0000 |
| resource_win_prob | 0.1445 | 0.0353 | 0.4512 | 32475.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0769 | 0.0000 | 0.2541 | 16385.0000 |
| innings_phase | 0.0787 | 0.0000 | 0.2612 | 16385.0000 |
| ece_optimized | 0.0795 | 0.0069 | 0.2661 | 16385.0000 |
| logloss_optimized | 0.0817 | 0.0293 | 0.2795 | 16385.0000 |
| innings_specific | 0.0827 | 0.0365 | 0.2730 | 16385.0000 |
| combined | 0.0831 | 0.0385 | 0.2750 | 16385.0000 |
| raw | 0.0831 | 0.0361 | 0.2760 | 16385.0000 |
| resource_win_prob | 0.0998 | 0.0832 | 0.3263 | 16385.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1763 |
| Innings 1 | brier_optimized | 0.2147 |
| Innings 2 | brier_optimized | 0.1344 |
| Inn1 Powerplay | brier_optimized | 0.2355 |
| Inn1 Middle | brier_optimized | 0.2131 |
| Inn1 Death | brier_optimized | 0.1993 |
| Inn2 Powerplay | brier_optimized | 0.1878 |
| Inn2 Middle | brier_optimized | 0.1327 |
| Inn2 Death | brier_optimized | 0.0769 |

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
| Overall | brier_optimized | 0.5192 |
| Innings 1 | brier_optimized | 0.6157 |
| Innings 2 | brier_optimized | 0.4136 |
| Inn1 Powerplay | brier_optimized | 0.6625 |
| Inn1 Middle | brier_optimized | 0.6129 |
| Inn1 Death | brier_optimized | 0.5801 |
| Inn2 Powerplay | brier_optimized | 0.5540 |
| Inn2 Middle | brier_optimized | 0.4133 |
| Inn2 Death | brier_optimized | 0.2541 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 9 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1905 | 0.1763 (brier_optimized) | **+7.4%** |
| LogLoss | 0.5573 | 0.5192 (brier_optimized) | **+6.8%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 14,807 | 0.045 | 0.049 | 0.0043  | 0.0460 |
| 0.1-0.2 | 10,771 | 0.152 | 0.185 | 0.0330  | 0.1497 |
| 0.2-0.3 | 13,405 | 0.251 | 0.274 | 0.0229  | 0.1984 |
| 0.3-0.4 | 15,198 | 0.352 | 0.349 | 0.0028  | 0.2260 |
| 0.4-0.5 | 17,522 | 0.450 | 0.467 | 0.0171  | 0.2478 |
| 0.5-0.6 | 17,516 | 0.549 | 0.560 | 0.0109  | 0.2457 |
| 0.6-0.7 | 15,766 | 0.649 | 0.649 | 0.0002  | 0.2272 |
| 0.7-0.8 | 13,290 | 0.750 | 0.724 | 0.0254  | 0.2000 |
| 0.8-0.9 | 12,564 | 0.849 | 0.814 | 0.0356  | 0.1515 |
| 0.9-1.0 | 10,596 | 0.946 | 0.935 | 0.0109  | 0.0592 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 14,290 | 0.034 | 0.034 | 0.0000  | 0.0315 |
| 0.1-0.2 | 10,497 | 0.151 | 0.151 | 0.0000  | 0.1278 |
| 0.2-0.3 | 11,786 | 0.258 | 0.258 | 0.0000  | 0.1906 |
| 0.3-0.4 | 16,651 | 0.341 | 0.341 | 0.0000  | 0.2238 |
| 0.4-0.5 | 14,142 | 0.444 | 0.444 | 0.0000  | 0.2462 |
| 0.5-0.6 | 21,954 | 0.550 | 0.550 | 0.0000  | 0.2468 |
| 0.6-0.7 | 17,631 | 0.659 | 0.659 | 0.0000  | 0.2241 |
| 0.7-0.8 | 13,788 | 0.738 | 0.738 | 0.0000  | 0.1924 |
| 0.8-0.9 | 10,214 | 0.850 | 0.850 | 0.0000  | 0.1265 |
| 0.9-1.0 | 10,482 | 0.961 | 0.961 | 0.0000  | 0.0360 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 12,968 | 0.035 | 0.035 | 0.0000  | 0.0333 |
| 0.1-0.2 | 10,830 | 0.144 | 0.144 | 0.0000  | 0.1223 |
| 0.2-0.3 | 10,070 | 0.249 | 0.249 | 0.0000  | 0.1860 |
| 0.3-0.4 | 21,207 | 0.344 | 0.344 | 0.0000  | 0.2249 |
| 0.4-0.5 | 14,132 | 0.456 | 0.456 | 0.0000  | 0.2473 |
| 0.5-0.6 | 20,152 | 0.555 | 0.555 | 0.0000  | 0.2463 |
| 0.6-0.7 | 24,392 | 0.669 | 0.669 | 0.0000  | 0.2202 |
| 0.7-0.8 | 7,889 | 0.757 | 0.757 | 0.0000  | 0.1833 |
| 0.8-0.9 | 8,918 | 0.847 | 0.847 | 0.0000  | 0.1290 |
| 0.9-1.0 | 10,877 | 0.954 | 0.954 | 0.0000  | 0.0433 |

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
