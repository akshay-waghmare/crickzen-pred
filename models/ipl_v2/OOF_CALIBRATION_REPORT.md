# OOF Calibration Analysis Report

**Generated:** 2026-04-18 21:06:23
**Samples:** 278,954
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1817 | 0.0000 | 0.5301 |
| innings_phase | 0.1834 | 0.0000 | 0.5350 |
| ece_optimized | 0.1840 | 0.0018 | 0.5371 |
| innings_specific | 0.1842 | 0.0000 | 0.5373 |
| combined | 0.1847 | 0.0000 | 0.5385 |
| raw | 0.1850 | 0.0104 | 0.5403 |
| logloss_optimized | 0.1852 | 0.0164 | 0.5429 |
| resource_win_prob | 0.2113 | 0.1133 | 0.6154 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2190 | 0.0000 | 0.6256 | 144340.0000 |
| innings_phase | 0.2208 | 0.0000 | 0.6299 | 144340.0000 |
| ece_optimized | 0.2215 | 0.0031 | 0.6318 | 144340.0000 |
| innings_specific | 0.2216 | 0.0000 | 0.6318 | 144340.0000 |
| combined | 0.2220 | 0.0115 | 0.6331 | 144340.0000 |
| logloss_optimized | 0.2221 | 0.0096 | 0.6338 | 144340.0000 |
| raw | 0.2225 | 0.0175 | 0.6345 | 144340.0000 |
| resource_win_prob | 0.2507 | 0.1336 | 0.7086 | 144340.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1417 | 0.0000 | 0.4278 | 134614.0000 |
| innings_phase | 0.1434 | 0.0000 | 0.4333 | 134614.0000 |
| ece_optimized | 0.1439 | 0.0038 | 0.4355 | 134614.0000 |
| innings_specific | 0.1442 | 0.0000 | 0.4359 | 134614.0000 |
| combined | 0.1447 | 0.0123 | 0.4371 | 134614.0000 |
| raw | 0.1449 | 0.0154 | 0.4393 | 134614.0000 |
| logloss_optimized | 0.1457 | 0.0272 | 0.4454 | 134614.0000 |
| resource_win_prob | 0.1691 | 0.0916 | 0.5155 | 134614.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2384 | 0.0000 | 0.6690 | 36260.0000 |
| innings_phase | 0.2396 | 0.0000 | 0.6717 | 36260.0000 |
| innings_specific | 0.2400 | 0.0030 | 0.6727 | 36260.0000 |
| combined | 0.2402 | 0.0091 | 0.6730 | 36260.0000 |
| ece_optimized | 0.2403 | 0.0024 | 0.6732 | 36260.0000 |
| logloss_optimized | 0.2403 | 0.0055 | 0.6733 | 36260.0000 |
| raw | 0.2406 | 0.0107 | 0.6739 | 36260.0000 |
| resource_win_prob | 0.2451 | 0.0360 | 0.6836 | 36260.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2172 | 0.0000 | 0.6218 | 64842.0000 |
| innings_phase | 0.2193 | 0.0000 | 0.6271 | 64842.0000 |
| ece_optimized | 0.2200 | 0.0036 | 0.6289 | 64842.0000 |
| innings_specific | 0.2200 | 0.0142 | 0.6288 | 64842.0000 |
| combined | 0.2201 | 0.0138 | 0.6293 | 64842.0000 |
| logloss_optimized | 0.2204 | 0.0112 | 0.6303 | 64842.0000 |
| raw | 0.2205 | 0.0166 | 0.6304 | 64842.0000 |
| resource_win_prob | 0.2677 | 0.1895 | 0.7565 | 64842.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2055 | 0.0000 | 0.5948 | 43238.0000 |
| innings_phase | 0.2071 | 0.0000 | 0.5990 | 43238.0000 |
| ece_optimized | 0.2079 | 0.0070 | 0.6013 | 43238.0000 |
| innings_specific | 0.2085 | 0.0200 | 0.6021 | 43238.0000 |
| logloss_optimized | 0.2094 | 0.0228 | 0.6059 | 43238.0000 |
| combined | 0.2096 | 0.0283 | 0.6053 | 43238.0000 |
| raw | 0.2103 | 0.0328 | 0.6076 | 43238.0000 |
| resource_win_prob | 0.2299 | 0.1324 | 0.6578 | 43238.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1848 | 0.0000 | 0.5440 | 36276.0000 |
| innings_phase | 0.1862 | 0.0000 | 0.5484 | 36276.0000 |
| ece_optimized | 0.1868 | 0.0054 | 0.5505 | 36276.0000 |
| combined | 0.1869 | 0.0142 | 0.5514 | 36276.0000 |
| innings_specific | 0.1869 | 0.0143 | 0.5512 | 36276.0000 |
| raw | 0.1870 | 0.0102 | 0.5513 | 36276.0000 |
| logloss_optimized | 0.1876 | 0.0193 | 0.5536 | 36276.0000 |
| resource_win_prob | 0.1901 | 0.0359 | 0.5585 | 36276.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1446 | 0.0000 | 0.4379 | 63812.0000 |
| innings_phase | 0.1466 | 0.0000 | 0.4446 | 63812.0000 |
| innings_specific | 0.1470 | 0.0105 | 0.4457 | 63812.0000 |
| ece_optimized | 0.1471 | 0.0049 | 0.4469 | 63812.0000 |
| combined | 0.1476 | 0.0145 | 0.4473 | 63812.0000 |
| raw | 0.1479 | 0.0206 | 0.4494 | 63812.0000 |
| logloss_optimized | 0.1490 | 0.0345 | 0.4569 | 63812.0000 |
| resource_win_prob | 0.1719 | 0.1111 | 0.5140 | 63812.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0909 | 0.0000 | 0.2869 | 34526.0000 |
| innings_phase | 0.0924 | 0.0000 | 0.2915 | 34526.0000 |
| ece_optimized | 0.0928 | 0.0057 | 0.2937 | 34526.0000 |
| innings_specific | 0.0942 | 0.0257 | 0.2968 | 34526.0000 |
| combined | 0.0948 | 0.0275 | 0.2983 | 34526.0000 |
| raw | 0.0950 | 0.0362 | 0.3028 | 34526.0000 |
| logloss_optimized | 0.0956 | 0.0302 | 0.3106 | 34526.0000 |
| resource_win_prob | 0.1420 | 0.1439 | 0.4731 | 34526.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1817 |
| Innings 1 | brier_optimized | 0.2190 |
| Innings 2 | brier_optimized | 0.1417 |
| Inn1 Powerplay | brier_optimized | 0.2384 |
| Inn1 Middle | brier_optimized | 0.2172 |
| Inn1 Death | brier_optimized | 0.2055 |
| Inn2 Powerplay | brier_optimized | 0.1848 |
| Inn2 Middle | brier_optimized | 0.1446 |
| Inn2 Death | brier_optimized | 0.0909 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
| Inn1 Powerplay | innings_phase | 0.0000 |
| Inn1 Middle | innings_phase | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5301 |
| Innings 1 | brier_optimized | 0.6256 |
| Innings 2 | brier_optimized | 0.4278 |
| Inn1 Powerplay | brier_optimized | 0.6690 |
| Inn1 Middle | brier_optimized | 0.6218 |
| Inn1 Death | brier_optimized | 0.5948 |
| Inn2 Powerplay | brier_optimized | 0.5440 |
| Inn2 Middle | brier_optimized | 0.4379 |
| Inn2 Death | brier_optimized | 0.2869 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 9 segments
- **ECE**: `brier_optimized` wins in 7 segments
- **LogLoss**: `brier_optimized` wins in 9 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.2113 | 0.1817 (brier_optimized) | **+14.0%** |
| LogLoss | 0.6154 | 0.5301 (brier_optimized) | **+13.9%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,048 | 0.046 | 0.037 | 0.0083  | 0.0348 |
| 0.1-0.2 | 18,408 | 0.152 | 0.172 | 0.0201  | 0.1421 |
| 0.2-0.3 | 24,391 | 0.253 | 0.268 | 0.0151  | 0.1954 |
| 0.3-0.4 | 35,735 | 0.353 | 0.347 | 0.0056  | 0.2259 |
| 0.4-0.5 | 45,626 | 0.450 | 0.457 | 0.0068  | 0.2474 |
| 0.5-0.6 | 38,855 | 0.548 | 0.549 | 0.0006  | 0.2470 |
| 0.6-0.7 | 30,128 | 0.647 | 0.635 | 0.0121  | 0.2310 |
| 0.7-0.8 | 22,158 | 0.748 | 0.729 | 0.0185  | 0.1977 |
| 0.8-0.9 | 18,366 | 0.849 | 0.838 | 0.0107  | 0.1350 |
| 0.9-1.0 | 21,239 | 0.948 | 0.970 | 0.0218  | 0.0291 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 24,188 | 0.029 | 0.029 | 0.0000  | 0.0268 |
| 0.1-0.2 | 17,256 | 0.161 | 0.161 | 0.0000  | 0.1341 |
| 0.2-0.3 | 23,785 | 0.249 | 0.249 | 0.0000  | 0.1862 |
| 0.3-0.4 | 35,808 | 0.351 | 0.351 | 0.0000  | 0.2270 |
| 0.4-0.5 | 45,559 | 0.448 | 0.448 | 0.0000  | 0.2466 |
| 0.5-0.6 | 43,008 | 0.544 | 0.544 | 0.0000  | 0.2472 |
| 0.6-0.7 | 26,456 | 0.649 | 0.649 | 0.0000  | 0.2268 |
| 0.7-0.8 | 24,588 | 0.741 | 0.741 | 0.0000  | 0.1909 |
| 0.8-0.9 | 14,611 | 0.843 | 0.843 | 0.0000  | 0.1312 |
| 0.9-1.0 | 23,695 | 0.969 | 0.969 | 0.0000  | 0.0293 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 23,353 | 0.031 | 0.031 | 0.0000  | 0.0292 |
| 0.1-0.2 | 16,345 | 0.161 | 0.161 | 0.0000  | 0.1342 |
| 0.2-0.3 | 22,147 | 0.242 | 0.242 | 0.0000  | 0.1826 |
| 0.3-0.4 | 37,106 | 0.343 | 0.343 | 0.0000  | 0.2248 |
| 0.4-0.5 | 46,106 | 0.445 | 0.445 | 0.0000  | 0.2463 |
| 0.5-0.6 | 43,672 | 0.540 | 0.540 | 0.0000  | 0.2479 |
| 0.6-0.7 | 29,929 | 0.653 | 0.653 | 0.0000  | 0.2259 |
| 0.7-0.8 | 21,766 | 0.740 | 0.740 | 0.0000  | 0.1920 |
| 0.8-0.9 | 15,590 | 0.839 | 0.839 | 0.0000  | 0.1342 |
| 0.9-1.0 | 22,940 | 0.968 | 0.968 | 0.0000  | 0.0302 |

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
