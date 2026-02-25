# OOF Calibration Analysis Report

**Generated:** 2026-02-25 17:57:58
**Samples:** 291,106
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1390 | 0.0000 | 0.4247 |
| innings_phase | 0.1426 | 0.0000 | 0.4360 |
| ece_optimized | 0.1435 | 0.0044 | 0.4404 |
| innings_specific | 0.1441 | 0.0000 | 0.4408 |
| combined | 0.1448 | 0.0000 | 0.4438 |
| raw | 0.1454 | 0.0148 | 0.4474 |
| logloss_optimized | 0.1459 | 0.0189 | 0.4489 |
| resource_win_prob | 0.1719 | 0.0491 | 0.5097 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1709 | 0.0000 | 0.5149 | 158563.0000 |
| innings_phase | 0.1745 | 0.0000 | 0.5253 | 158563.0000 |
| ece_optimized | 0.1755 | 0.0052 | 0.5287 | 158563.0000 |
| innings_specific | 0.1761 | 0.0000 | 0.5297 | 158563.0000 |
| combined | 0.1766 | 0.0172 | 0.5323 | 158563.0000 |
| logloss_optimized | 0.1768 | 0.0105 | 0.5327 | 158563.0000 |
| raw | 0.1778 | 0.0272 | 0.5396 | 158563.0000 |
| resource_win_prob | 0.2108 | 0.0823 | 0.6091 | 158563.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1008 | 0.0000 | 0.3168 | 132543.0000 |
| innings_phase | 0.1044 | 0.0000 | 0.3292 | 132543.0000 |
| ece_optimized | 0.1052 | 0.0051 | 0.3348 | 132543.0000 |
| innings_specific | 0.1058 | 0.0000 | 0.3343 | 132543.0000 |
| raw | 0.1066 | 0.0114 | 0.3371 | 132543.0000 |
| combined | 0.1067 | 0.0206 | 0.3379 | 132543.0000 |
| logloss_optimized | 0.1089 | 0.0407 | 0.3487 | 132543.0000 |
| resource_win_prob | 0.1253 | 0.0147 | 0.3907 | 132543.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1937 | 0.0000 | 0.5724 | 30687.0000 |
| innings_phase | 0.1963 | 0.0000 | 0.5795 | 30687.0000 |
| ece_optimized | 0.1974 | 0.0137 | 0.5823 | 30687.0000 |
| innings_specific | 0.1985 | 0.0355 | 0.5856 | 30687.0000 |
| logloss_optimized | 0.1991 | 0.0343 | 0.5871 | 30687.0000 |
| combined | 0.1995 | 0.0428 | 0.5892 | 30687.0000 |
| raw | 0.2005 | 0.0416 | 0.5936 | 30687.0000 |
| resource_win_prob | 0.2466 | 0.0762 | 0.6864 | 30687.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1698 | 0.0000 | 0.5138 | 79666.0000 |
| innings_phase | 0.1743 | 0.0000 | 0.5263 | 79666.0000 |
| innings_specific | 0.1749 | 0.0148 | 0.5282 | 79666.0000 |
| ece_optimized | 0.1749 | 0.0046 | 0.5286 | 79666.0000 |
| combined | 0.1755 | 0.0229 | 0.5310 | 79666.0000 |
| logloss_optimized | 0.1755 | 0.0126 | 0.5301 | 79666.0000 |
| raw | 0.1765 | 0.0316 | 0.5378 | 79666.0000 |
| resource_win_prob | 0.2124 | 0.1047 | 0.6143 | 79666.0000 |

### Innings 1 - Setup

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1608 | 0.0000 | 0.4878 | 18656.0000 |
| innings_phase | 0.1633 | 0.0000 | 0.4950 | 18656.0000 |
| ece_optimized | 0.1648 | 0.0094 | 0.5007 | 18656.0000 |
| combined | 0.1659 | 0.0283 | 0.5034 | 18656.0000 |
| innings_specific | 0.1659 | 0.0266 | 0.5023 | 18656.0000 |
| logloss_optimized | 0.1668 | 0.0289 | 0.5070 | 18656.0000 |
| raw | 0.1673 | 0.0435 | 0.5132 | 18656.0000 |
| resource_win_prob | 0.1900 | 0.0793 | 0.5641 | 18656.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1565 | 0.0000 | 0.4754 | 29554.0000 |
| innings_phase | 0.1597 | 0.0000 | 0.4855 | 29554.0000 |
| ece_optimized | 0.1610 | 0.0090 | 0.4908 | 29554.0000 |
| innings_specific | 0.1624 | 0.0300 | 0.4935 | 29554.0000 |
| combined | 0.1626 | 0.0330 | 0.4952 | 29554.0000 |
| logloss_optimized | 0.1634 | 0.0297 | 0.4996 | 29554.0000 |
| raw | 0.1644 | 0.0466 | 0.5053 | 29554.0000 |
| resource_win_prob | 0.1826 | 0.0592 | 0.5433 | 29554.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1344 | 0.0000 | 0.4178 | 30620.0000 |
| innings_phase | 0.1372 | 0.0000 | 0.4275 | 30620.0000 |
| ece_optimized | 0.1380 | 0.0045 | 0.4315 | 30620.0000 |
| raw | 0.1383 | 0.0160 | 0.4330 | 30620.0000 |
| combined | 0.1383 | 0.0183 | 0.4328 | 30620.0000 |
| innings_specific | 0.1386 | 0.0229 | 0.4328 | 30620.0000 |
| logloss_optimized | 0.1390 | 0.0270 | 0.4352 | 30620.0000 |
| resource_win_prob | 0.1549 | 0.0675 | 0.4714 | 30620.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0950 | 0.0000 | 0.2996 | 73985.0000 |
| innings_phase | 0.0990 | 0.0000 | 0.3135 | 73985.0000 |
| innings_specific | 0.0994 | 0.0101 | 0.3148 | 73985.0000 |
| ece_optimized | 0.0996 | 0.0050 | 0.3182 | 73985.0000 |
| raw | 0.1003 | 0.0158 | 0.3179 | 73985.0000 |
| combined | 0.1005 | 0.0262 | 0.3196 | 73985.0000 |
| logloss_optimized | 0.1034 | 0.0446 | 0.3323 | 73985.0000 |
| resource_win_prob | 0.1181 | 0.0303 | 0.3699 | 73985.0000 |

### Innings 2 - Setup

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0787 | 0.0000 | 0.2501 | 13503.0000 |
| innings_phase | 0.0806 | 0.0000 | 0.2583 | 13503.0000 |
| ece_optimized | 0.0822 | 0.0145 | 0.2669 | 13503.0000 |
| innings_specific | 0.0848 | 0.0248 | 0.2714 | 13503.0000 |
| combined | 0.0862 | 0.0380 | 0.2774 | 13503.0000 |
| raw | 0.0864 | 0.0282 | 0.2763 | 13503.0000 |
| logloss_optimized | 0.0896 | 0.0503 | 0.2935 | 13503.0000 |
| resource_win_prob | 0.1014 | 0.0753 | 0.3113 | 13503.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0800 | 0.0000 | 0.2531 | 14435.0000 |
| innings_phase | 0.0842 | 0.0000 | 0.2677 | 14435.0000 |
| ece_optimized | 0.0856 | 0.0099 | 0.2786 | 14435.0000 |
| innings_specific | 0.0890 | 0.0385 | 0.2840 | 14435.0000 |
| combined | 0.0903 | 0.0361 | 0.2873 | 14435.0000 |
| raw | 0.0904 | 0.0415 | 0.2893 | 14435.0000 |
| logloss_optimized | 0.0914 | 0.0476 | 0.3009 | 14435.0000 |
| resource_win_prob | 0.1220 | 0.1271 | 0.4007 | 14435.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1390 |
| Innings 1 | brier_optimized | 0.1709 |
| Innings 2 | brier_optimized | 0.1008 |
| Inn1 Powerplay | brier_optimized | 0.1937 |
| Inn1 Middle | brier_optimized | 0.1698 |
| Inn1 Setup | brier_optimized | 0.1608 |
| Inn1 Death | brier_optimized | 0.1565 |
| Inn2 Powerplay | brier_optimized | 0.1344 |
| Inn2 Middle | brier_optimized | 0.0950 |
| Inn2 Setup | brier_optimized | 0.0787 |
| Inn2 Death | brier_optimized | 0.0800 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | innings_phase | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Setup | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Setup | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.4247 |
| Innings 1 | brier_optimized | 0.5149 |
| Innings 2 | brier_optimized | 0.3168 |
| Inn1 Powerplay | brier_optimized | 0.5724 |
| Inn1 Middle | brier_optimized | 0.5138 |
| Inn1 Setup | brier_optimized | 0.4878 |
| Inn1 Death | brier_optimized | 0.4754 |
| Inn2 Powerplay | brier_optimized | 0.4178 |
| Inn2 Middle | brier_optimized | 0.2996 |
| Inn2 Setup | brier_optimized | 0.2501 |
| Inn2 Death | brier_optimized | 0.2531 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 11 segments
- **ECE**: `brier_optimized` wins in 10 segments
- **LogLoss**: `brier_optimized` wins in 11 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1719 | 0.1390 (brier_optimized) | **+19.2%** |
| LogLoss | 0.5097 | 0.4247 (brier_optimized) | **+16.7%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 55,962 | 0.038 | 0.064 | 0.0253  | 0.0586 |
| 0.1-0.2 | 27,083 | 0.148 | 0.154 | 0.0064  | 0.1298 |
| 0.2-0.3 | 22,971 | 0.250 | 0.268 | 0.0181  | 0.1962 |
| 0.3-0.4 | 20,411 | 0.350 | 0.343 | 0.0067  | 0.2251 |
| 0.4-0.5 | 20,459 | 0.450 | 0.453 | 0.0032  | 0.2464 |
| 0.5-0.6 | 21,203 | 0.550 | 0.544 | 0.0059  | 0.2464 |
| 0.6-0.7 | 21,114 | 0.652 | 0.670 | 0.0185  | 0.2210 |
| 0.7-0.8 | 25,990 | 0.750 | 0.734 | 0.0163  | 0.1956 |
| 0.8-0.9 | 28,894 | 0.851 | 0.827 | 0.0240  | 0.1429 |
| 0.9-1.0 | 47,019 | 0.958 | 0.948 | 0.0101  | 0.0485 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 46,523 | 0.031 | 0.031 | 0.0000  | 0.0293 |
| 0.1-0.2 | 34,132 | 0.148 | 0.148 | 0.0000  | 0.1257 |
| 0.2-0.3 | 27,184 | 0.241 | 0.241 | 0.0000  | 0.1822 |
| 0.3-0.4 | 15,939 | 0.350 | 0.350 | 0.0000  | 0.2268 |
| 0.4-0.5 | 20,377 | 0.442 | 0.442 | 0.0000  | 0.2460 |
| 0.5-0.6 | 22,673 | 0.546 | 0.546 | 0.0000  | 0.2470 |
| 0.6-0.7 | 19,699 | 0.653 | 0.653 | 0.0000  | 0.2257 |
| 0.7-0.8 | 36,136 | 0.751 | 0.751 | 0.0000  | 0.1860 |
| 0.8-0.9 | 21,964 | 0.845 | 0.845 | 0.0000  | 0.1303 |
| 0.9-1.0 | 46,479 | 0.963 | 0.963 | 0.0000  | 0.0342 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 40,330 | 0.031 | 0.031 | 0.0000  | 0.0288 |
| 0.1-0.2 | 37,147 | 0.137 | 0.137 | 0.0000  | 0.1176 |
| 0.2-0.3 | 27,669 | 0.246 | 0.246 | 0.0000  | 0.1842 |
| 0.3-0.4 | 22,172 | 0.347 | 0.347 | 0.0000  | 0.2260 |
| 0.4-0.5 | 15,411 | 0.440 | 0.440 | 0.0000  | 0.2457 |
| 0.5-0.6 | 24,048 | 0.542 | 0.542 | 0.0000  | 0.2475 |
| 0.6-0.7 | 21,923 | 0.659 | 0.659 | 0.0000  | 0.2237 |
| 0.7-0.8 | 37,111 | 0.757 | 0.757 | 0.0000  | 0.1834 |
| 0.8-0.9 | 22,513 | 0.849 | 0.849 | 0.0000  | 0.1271 |
| 0.9-1.0 | 42,782 | 0.961 | 0.961 | 0.0000  | 0.0365 |

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
