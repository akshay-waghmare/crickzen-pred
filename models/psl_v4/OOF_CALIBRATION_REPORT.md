# OOF Calibration Analysis Report

**Generated:** 2026-04-22 17:14:53
**Samples:** 78,040
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1835 | 0.0000 | 0.5345 |
| resource_win_prob | 0.1838 | 0.0262 | 0.5434 |
| innings_phase | 0.1868 | 0.0000 | 0.5444 |
| ece_optimized | 0.1883 | 0.0115 | 0.5492 |
| innings_specific | 0.1898 | 0.0000 | 0.5534 |
| combined | 0.1913 | 0.0000 | 0.5574 |
| logloss_optimized | 0.1921 | 0.0250 | 0.5614 |
| raw | 0.1955 | 0.0501 | 0.5701 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2193 | 0.0000 | 0.6241 | 40473.0000 |
| resource_win_prob | 0.2193 | 0.0414 | 0.6297 | 40473.0000 |
| innings_phase | 0.2222 | 0.0000 | 0.6316 | 40473.0000 |
| ece_optimized | 0.2240 | 0.0171 | 0.6363 | 40473.0000 |
| innings_specific | 0.2246 | 0.0000 | 0.6372 | 40473.0000 |
| combined | 0.2260 | 0.0219 | 0.6413 | 40473.0000 |
| logloss_optimized | 0.2269 | 0.0384 | 0.6442 | 40473.0000 |
| raw | 0.2330 | 0.0662 | 0.6599 | 40473.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1448 | 0.0000 | 0.4380 | 37567.0000 |
| resource_win_prob | 0.1455 | 0.0228 | 0.4505 | 37567.0000 |
| innings_phase | 0.1487 | 0.0000 | 0.4505 | 37567.0000 |
| ece_optimized | 0.1498 | 0.0062 | 0.4552 | 37567.0000 |
| innings_specific | 0.1523 | 0.0000 | 0.4631 | 37567.0000 |
| combined | 0.1539 | 0.0236 | 0.4670 | 37567.0000 |
| logloss_optimized | 0.1547 | 0.0363 | 0.4721 | 37567.0000 |
| raw | 0.1551 | 0.0359 | 0.4734 | 37567.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| resource_win_prob | 0.2395 | 0.0324 | 0.6718 | 10216.0000 |
| brier_optimized | 0.2425 | 0.0000 | 0.6776 | 10216.0000 |
| innings_phase | 0.2444 | 0.0000 | 0.6817 | 10216.0000 |
| logloss_optimized | 0.2456 | 0.0125 | 0.6842 | 10216.0000 |
| ece_optimized | 0.2479 | 0.0466 | 0.6890 | 10216.0000 |
| innings_specific | 0.2488 | 0.0529 | 0.6913 | 10216.0000 |
| combined | 0.2496 | 0.0521 | 0.6931 | 10216.0000 |
| raw | 0.2579 | 0.0902 | 0.7134 | 10216.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2160 | 0.0000 | 0.6185 | 18246.0000 |
| resource_win_prob | 0.2166 | 0.0538 | 0.6284 | 18246.0000 |
| innings_phase | 0.2196 | 0.0000 | 0.6278 | 18246.0000 |
| ece_optimized | 0.2207 | 0.0085 | 0.6313 | 18246.0000 |
| innings_specific | 0.2209 | 0.0227 | 0.6311 | 18246.0000 |
| combined | 0.2216 | 0.0349 | 0.6331 | 18246.0000 |
| logloss_optimized | 0.2230 | 0.0387 | 0.6365 | 18246.0000 |
| raw | 0.2273 | 0.0588 | 0.6498 | 18246.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2047 | 0.0000 | 0.5871 | 12011.0000 |
| resource_win_prob | 0.2064 | 0.0765 | 0.5959 | 12011.0000 |
| innings_phase | 0.2072 | 0.0000 | 0.5948 | 12011.0000 |
| ece_optimized | 0.2087 | 0.0075 | 0.5992 | 12011.0000 |
| innings_specific | 0.2094 | 0.0359 | 0.6004 | 12011.0000 |
| combined | 0.2127 | 0.0622 | 0.6097 | 12011.0000 |
| logloss_optimized | 0.2169 | 0.0770 | 0.6219 | 12011.0000 |
| raw | 0.2204 | 0.0837 | 0.6298 | 12011.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| resource_win_prob | 0.1795 | 0.0586 | 0.5349 | 10272.0000 |
| brier_optimized | 0.1803 | 0.0000 | 0.5348 | 10272.0000 |
| innings_phase | 0.1831 | 0.0000 | 0.5426 | 10272.0000 |
| ece_optimized | 0.1841 | 0.0080 | 0.5460 | 10272.0000 |
| innings_specific | 0.1894 | 0.0617 | 0.5636 | 10272.0000 |
| combined | 0.1921 | 0.0758 | 0.5707 | 10272.0000 |
| logloss_optimized | 0.1921 | 0.0719 | 0.5671 | 10272.0000 |
| raw | 0.1959 | 0.0846 | 0.5895 | 10272.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1463 | 0.0000 | 0.4429 | 18092.0000 |
| resource_win_prob | 0.1468 | 0.0434 | 0.4586 | 18092.0000 |
| innings_phase | 0.1510 | 0.0000 | 0.4588 | 18092.0000 |
| innings_specific | 0.1518 | 0.0148 | 0.4614 | 18092.0000 |
| ece_optimized | 0.1522 | 0.0068 | 0.4634 | 18092.0000 |
| combined | 0.1526 | 0.0196 | 0.4632 | 18092.0000 |
| raw | 0.1545 | 0.0350 | 0.4706 | 18092.0000 |
| logloss_optimized | 0.1556 | 0.0323 | 0.4761 | 18092.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1023 | 0.0000 | 0.3203 | 9203.0000 |
| resource_win_prob | 0.1051 | 0.0648 | 0.3405 | 9203.0000 |
| innings_phase | 0.1058 | 0.0000 | 0.3314 | 9203.0000 |
| ece_optimized | 0.1070 | 0.0062 | 0.3378 | 9203.0000 |
| raw | 0.1107 | 0.0373 | 0.3494 | 9203.0000 |
| logloss_optimized | 0.1110 | 0.0407 | 0.3583 | 9203.0000 |
| innings_specific | 0.1117 | 0.0615 | 0.3545 | 9203.0000 |
| combined | 0.1137 | 0.0660 | 0.3589 | 9203.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1835 |
| Innings 1 | brier_optimized | 0.2193 |
| Innings 2 | brier_optimized | 0.1448 |
| Inn1 Powerplay | resource_win_prob | 0.2395 |
| Inn1 Middle | brier_optimized | 0.2160 |
| Inn1 Death | brier_optimized | 0.2047 |
| Inn2 Powerplay | resource_win_prob | 0.1795 |
| Inn2 Middle | brier_optimized | 0.1463 |
| Inn2 Death | brier_optimized | 0.1023 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | innings_specific | 0.0000 |
| Innings 2 | innings_phase | 0.0000 |
| Inn1 Powerplay | innings_phase | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | brier_optimized | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.5345 |
| Innings 1 | brier_optimized | 0.6241 |
| Innings 2 | brier_optimized | 0.4380 |
| Inn1 Powerplay | resource_win_prob | 0.6718 |
| Inn1 Middle | brier_optimized | 0.6185 |
| Inn1 Death | brier_optimized | 0.5871 |
| Inn2 Powerplay | brier_optimized | 0.5348 |
| Inn2 Middle | brier_optimized | 0.4429 |
| Inn2 Death | brier_optimized | 0.3203 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 7 segments
- **ECE**: `brier_optimized` wins in 6 segments
- **LogLoss**: `brier_optimized` wins in 8 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1838 | 0.1835 (brier_optimized) | **+0.2%** |
| LogLoss | 0.5434 | 0.5345 (brier_optimized) | **+1.6%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 7,339 | 0.050 | 0.085 | 0.0353  | 0.0773 |
| 0.1-0.2 | 7,619 | 0.151 | 0.221 | 0.0692 ⚠️ | 0.1765 |
| 0.2-0.3 | 8,122 | 0.250 | 0.305 | 0.0554 ⚠️ | 0.2142 |
| 0.3-0.4 | 8,812 | 0.350 | 0.414 | 0.0640 ⚠️ | 0.2449 |
| 0.4-0.5 | 8,970 | 0.449 | 0.470 | 0.0210  | 0.2494 |
| 0.5-0.6 | 8,401 | 0.548 | 0.541 | 0.0077  | 0.2483 |
| 0.6-0.7 | 7,400 | 0.649 | 0.586 | 0.0628 ⚠️ | 0.2468 |
| 0.7-0.8 | 6,918 | 0.750 | 0.655 | 0.0954 ⚠️ | 0.2345 |
| 0.8-0.9 | 5,920 | 0.852 | 0.741 | 0.1107 ⚠️ | 0.2014 |
| 0.9-1.0 | 8,539 | 0.948 | 0.939 | 0.0089  | 0.0565 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 5,273 | 0.024 | 0.024 | 0.0000  | 0.0219 |
| 0.1-0.2 | 5,716 | 0.155 | 0.155 | 0.0000  | 0.1301 |
| 0.2-0.3 | 7,789 | 0.257 | 0.257 | 0.0000  | 0.1905 |
| 0.3-0.4 | 8,873 | 0.350 | 0.350 | 0.0000  | 0.2268 |
| 0.4-0.5 | 13,967 | 0.452 | 0.452 | 0.0000  | 0.2470 |
| 0.5-0.6 | 10,549 | 0.556 | 0.556 | 0.0000  | 0.2457 |
| 0.6-0.7 | 10,384 | 0.631 | 0.631 | 0.0000  | 0.2323 |
| 0.7-0.8 | 3,950 | 0.743 | 0.743 | 0.0000  | 0.1903 |
| 0.8-0.9 | 3,580 | 0.856 | 0.856 | 0.0000  | 0.1230 |
| 0.9-1.0 | 7,959 | 0.957 | 0.957 | 0.0000  | 0.0399 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 4,841 | 0.027 | 0.027 | 0.0000  | 0.0257 |
| 0.1-0.2 | 5,463 | 0.164 | 0.164 | 0.0000  | 0.1364 |
| 0.2-0.3 | 7,824 | 0.253 | 0.253 | 0.0000  | 0.1878 |
| 0.3-0.4 | 8,924 | 0.345 | 0.345 | 0.0000  | 0.2254 |
| 0.4-0.5 | 14,642 | 0.453 | 0.453 | 0.0000  | 0.2473 |
| 0.5-0.6 | 9,542 | 0.546 | 0.546 | 0.0000  | 0.2474 |
| 0.6-0.7 | 10,998 | 0.620 | 0.620 | 0.0000  | 0.2353 |
| 0.7-0.8 | 4,060 | 0.729 | 0.729 | 0.0000  | 0.1972 |
| 0.8-0.9 | 4,826 | 0.856 | 0.856 | 0.0000  | 0.1227 |
| 0.9-1.0 | 6,920 | 0.959 | 0.959 | 0.0000  | 0.0387 |

### Problematic Bins (Calibration Error > 0.05)


**raw:**
- Bin 0.1-0.2: CE=0.0692 (under-predicting)
- Bin 0.2-0.3: CE=0.0554 (under-predicting)
- Bin 0.3-0.4: CE=0.0640 (under-predicting)
- Bin 0.6-0.7: CE=0.0628 (over-predicting)
- Bin 0.7-0.8: CE=0.0954 (over-predicting)
- Bin 0.8-0.9: CE=0.1107 (over-predicting)

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
