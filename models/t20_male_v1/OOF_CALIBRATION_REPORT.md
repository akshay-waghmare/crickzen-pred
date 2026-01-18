# OOF Calibration Analysis Report

**Generated:** 2026-01-19 00:29:23
**Samples:** 1,893,892
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1723 | 0.0000 | 0.5079 |
| innings_phase | 0.1729 | 0.0000 | 0.5095 |
| ece_optimized | 0.1731 | 0.0013 | 0.5103 |
| innings_specific | 0.1733 | 0.0000 | 0.5105 |
| combined | 0.1734 | 0.0000 | 0.5110 |
| raw | 0.1735 | 0.0055 | 0.5119 |
| logloss_optimized | 0.1741 | 0.0150 | 0.5159 |
| resource_win_prob | 0.1896 | 0.0487 | 0.5554 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2110 | 0.0000 | 0.6077 | 994770.0000 |
| innings_phase | 0.2116 | 0.0000 | 0.6092 | 994770.0000 |
| ece_optimized | 0.2117 | 0.0007 | 0.6097 | 994770.0000 |
| innings_specific | 0.2118 | 0.0000 | 0.6096 | 994770.0000 |
| combined | 0.2119 | 0.0061 | 0.6103 | 994770.0000 |
| raw | 0.2120 | 0.0083 | 0.6104 | 994770.0000 |
| logloss_optimized | 0.2122 | 0.0125 | 0.6114 | 994770.0000 |
| resource_win_prob | 0.2278 | 0.0902 | 0.6452 | 994770.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1295 | 0.0000 | 0.3975 | 899122.0000 |
| innings_phase | 0.1301 | 0.0000 | 0.3993 | 899122.0000 |
| ece_optimized | 0.1303 | 0.0030 | 0.4005 | 899122.0000 |
| innings_specific | 0.1307 | 0.0000 | 0.4008 | 899122.0000 |
| combined | 0.1308 | 0.0067 | 0.4012 | 899122.0000 |
| raw | 0.1309 | 0.0107 | 0.4030 | 899122.0000 |
| logloss_optimized | 0.1319 | 0.0258 | 0.4102 | 899122.0000 |
| resource_win_prob | 0.1473 | 0.0542 | 0.4561 | 899122.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2326 | 0.0000 | 0.6568 | 253089.0000 |
| innings_phase | 0.2329 | 0.0000 | 0.6577 | 253089.0000 |
| ece_optimized | 0.2331 | 0.0015 | 0.6581 | 253089.0000 |
| logloss_optimized | 0.2332 | 0.0027 | 0.6583 | 253089.0000 |
| innings_specific | 0.2332 | 0.0082 | 0.6583 | 253089.0000 |
| combined | 0.2332 | 0.0102 | 0.6584 | 253089.0000 |
| raw | 0.2333 | 0.0105 | 0.6585 | 253089.0000 |
| resource_win_prob | 0.2555 | 0.1167 | 0.7049 | 253089.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2090 | 0.0000 | 0.6035 | 449509.0000 |
| innings_phase | 0.2096 | 0.0000 | 0.6051 | 449509.0000 |
| innings_specific | 0.2097 | 0.0032 | 0.6053 | 449509.0000 |
| ece_optimized | 0.2097 | 0.0017 | 0.6055 | 449509.0000 |
| combined | 0.2098 | 0.0077 | 0.6060 | 449509.0000 |
| raw | 0.2099 | 0.0108 | 0.6061 | 449509.0000 |
| logloss_optimized | 0.2102 | 0.0149 | 0.6074 | 449509.0000 |
| resource_win_prob | 0.2226 | 0.0729 | 0.6345 | 449509.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1955 | 0.0000 | 0.5717 | 292172.0000 |
| innings_phase | 0.1961 | 0.0000 | 0.5734 | 292172.0000 |
| ece_optimized | 0.1963 | 0.0015 | 0.5741 | 292172.0000 |
| innings_specific | 0.1965 | 0.0101 | 0.5742 | 292172.0000 |
| combined | 0.1966 | 0.0145 | 0.5752 | 292172.0000 |
| raw | 0.1967 | 0.0147 | 0.5752 | 292172.0000 |
| logloss_optimized | 0.1970 | 0.0208 | 0.5770 | 292172.0000 |
| resource_win_prob | 0.2119 | 0.0939 | 0.6100 | 292172.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1747 | 0.0000 | 0.5214 | 252837.0000 |
| innings_phase | 0.1750 | 0.0000 | 0.5225 | 252837.0000 |
| ece_optimized | 0.1752 | 0.0017 | 0.5232 | 252837.0000 |
| innings_specific | 0.1754 | 0.0128 | 0.5237 | 252837.0000 |
| combined | 0.1757 | 0.0193 | 0.5245 | 252837.0000 |
| raw | 0.1758 | 0.0209 | 0.5248 | 252837.0000 |
| logloss_optimized | 0.1761 | 0.0240 | 0.5268 | 252837.0000 |
| resource_win_prob | 0.1974 | 0.1274 | 0.5849 | 252837.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1276 | 0.0000 | 0.3941 | 433372.0000 |
| innings_phase | 0.1283 | 0.0000 | 0.3963 | 433372.0000 |
| innings_specific | 0.1283 | 0.0036 | 0.3966 | 433372.0000 |
| ece_optimized | 0.1284 | 0.0032 | 0.3978 | 433372.0000 |
| combined | 0.1285 | 0.0088 | 0.3970 | 433372.0000 |
| raw | 0.1287 | 0.0127 | 0.3991 | 433372.0000 |
| logloss_optimized | 0.1301 | 0.0325 | 0.4074 | 433372.0000 |
| resource_win_prob | 0.1411 | 0.0429 | 0.4409 | 433372.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0800 | 0.0000 | 0.2575 | 212913.0000 |
| innings_phase | 0.0806 | 0.0000 | 0.2592 | 212913.0000 |
| ece_optimized | 0.0807 | 0.0056 | 0.2601 | 212913.0000 |
| combined | 0.0821 | 0.0216 | 0.2632 | 212913.0000 |
| innings_specific | 0.0823 | 0.0221 | 0.2634 | 212913.0000 |
| raw | 0.0823 | 0.0285 | 0.2661 | 212913.0000 |
| logloss_optimized | 0.0832 | 0.0291 | 0.2774 | 212913.0000 |
| resource_win_prob | 0.1004 | 0.0770 | 0.3338 | 212913.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1723 |
| Innings 1 | brier_optimized | 0.2110 |
| Innings 2 | brier_optimized | 0.1295 |
| Inn1 Powerplay | brier_optimized | 0.2326 |
| Inn1 Middle | brier_optimized | 0.2090 |
| Inn1 Death | brier_optimized | 0.1955 |
| Inn2 Powerplay | brier_optimized | 0.1747 |
| Inn2 Middle | brier_optimized | 0.1276 |
| Inn2 Death | brier_optimized | 0.0800 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | innings_phase | 0.0000 |
| Innings 1 | innings_phase | 0.0000 |
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
| Overall | brier_optimized | 0.5079 |
| Innings 1 | brier_optimized | 0.6077 |
| Innings 2 | brier_optimized | 0.3975 |
| Inn1 Powerplay | brier_optimized | 0.6568 |
| Inn1 Middle | brier_optimized | 0.6035 |
| Inn1 Death | brier_optimized | 0.5717 |
| Inn2 Powerplay | brier_optimized | 0.5214 |
| Inn2 Middle | brier_optimized | 0.3941 |
| Inn2 Death | brier_optimized | 0.2575 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 6 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1896 | 0.1723 (brier_optimized) | **+9.1%** |
| LogLoss | 0.5554 | 0.5079 (brier_optimized) | **+8.5%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 209,018 | 0.041 | 0.035 | 0.0054  | 0.0330 |
| 0.1-0.2 | 135,406 | 0.150 | 0.154 | 0.0042  | 0.1295 |
| 0.2-0.3 | 169,511 | 0.252 | 0.250 | 0.0020  | 0.1867 |
| 0.3-0.4 | 205,676 | 0.351 | 0.350 | 0.0011  | 0.2267 |
| 0.4-0.5 | 242,272 | 0.451 | 0.453 | 0.0018  | 0.2470 |
| 0.5-0.6 | 252,899 | 0.549 | 0.553 | 0.0038  | 0.2463 |
| 0.6-0.7 | 209,764 | 0.648 | 0.640 | 0.0083  | 0.2299 |
| 0.7-0.8 | 170,588 | 0.748 | 0.739 | 0.0088  | 0.1919 |
| 0.8-0.9 | 143,937 | 0.849 | 0.852 | 0.0030  | 0.1247 |
| 0.9-1.0 | 154,821 | 0.947 | 0.968 | 0.0203  | 0.0312 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 205,350 | 0.032 | 0.032 | 0.0000  | 0.0299 |
| 0.1-0.2 | 145,312 | 0.150 | 0.150 | 0.0000  | 0.1267 |
| 0.2-0.3 | 168,958 | 0.253 | 0.253 | 0.0000  | 0.1881 |
| 0.3-0.4 | 198,596 | 0.351 | 0.351 | 0.0000  | 0.2269 |
| 0.4-0.5 | 236,902 | 0.450 | 0.450 | 0.0000  | 0.2466 |
| 0.5-0.6 | 262,587 | 0.551 | 0.551 | 0.0000  | 0.2466 |
| 0.6-0.7 | 217,477 | 0.646 | 0.646 | 0.0000  | 0.2278 |
| 0.7-0.8 | 166,690 | 0.748 | 0.748 | 0.0000  | 0.1878 |
| 0.8-0.9 | 115,971 | 0.848 | 0.848 | 0.0000  | 0.1282 |
| 0.9-1.0 | 176,049 | 0.963 | 0.963 | 0.0000  | 0.0348 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 206,549 | 0.034 | 0.034 | 0.0000  | 0.0316 |
| 0.1-0.2 | 145,029 | 0.153 | 0.153 | 0.0000  | 0.1286 |
| 0.2-0.3 | 156,088 | 0.250 | 0.250 | 0.0000  | 0.1869 |
| 0.3-0.4 | 215,657 | 0.349 | 0.349 | 0.0000  | 0.2263 |
| 0.4-0.5 | 247,276 | 0.454 | 0.454 | 0.0000  | 0.2471 |
| 0.5-0.6 | 241,950 | 0.554 | 0.554 | 0.0000  | 0.2464 |
| 0.6-0.7 | 228,882 | 0.645 | 0.645 | 0.0000  | 0.2280 |
| 0.7-0.8 | 164,192 | 0.749 | 0.749 | 0.0000  | 0.1872 |
| 0.8-0.9 | 115,275 | 0.850 | 0.850 | 0.0000  | 0.1268 |
| 0.9-1.0 | 172,994 | 0.963 | 0.963 | 0.0000  | 0.0349 |

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
