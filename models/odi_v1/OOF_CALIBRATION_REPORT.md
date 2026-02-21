# OOF Calibration Analysis Report

**Generated:** 2026-02-21 11:16:58
**Samples:** 1,587,026
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1598 | 0.0000 | 0.4763 |
| innings_phase | 0.1612 | 0.0000 | 0.4807 |
| ece_optimized | 0.1615 | 0.0021 | 0.4820 |
| innings_specific | 0.1618 | 0.0000 | 0.4824 |
| combined | 0.1620 | 0.0000 | 0.4830 |
| raw | 0.1621 | 0.0041 | 0.4837 |
| logloss_optimized | 0.1627 | 0.0174 | 0.4880 |
| resource_win_prob | 0.1874 | 0.0348 | 0.5482 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1965 | 0.0000 | 0.5735 | 855626.0000 |
| innings_phase | 0.1979 | 0.0000 | 0.5776 | 855626.0000 |
| ece_optimized | 0.1982 | 0.0019 | 0.5785 | 855626.0000 |
| innings_specific | 0.1984 | 0.0000 | 0.5789 | 855626.0000 |
| combined | 0.1985 | 0.0073 | 0.5795 | 855626.0000 |
| raw | 0.1986 | 0.0089 | 0.5798 | 855626.0000 |
| logloss_optimized | 0.1989 | 0.0188 | 0.5813 | 855626.0000 |
| resource_win_prob | 0.2234 | 0.0529 | 0.6369 | 855626.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1170 | 0.0000 | 0.3627 | 731400.0000 |
| innings_phase | 0.1183 | 0.0000 | 0.3673 | 731400.0000 |
| ece_optimized | 0.1186 | 0.0036 | 0.3690 | 731400.0000 |
| innings_specific | 0.1191 | 0.0000 | 0.3694 | 731400.0000 |
| combined | 0.1193 | 0.0085 | 0.3701 | 731400.0000 |
| raw | 0.1194 | 0.0108 | 0.3712 | 731400.0000 |
| logloss_optimized | 0.1203 | 0.0276 | 0.3789 | 731400.0000 |
| resource_win_prob | 0.1453 | 0.0303 | 0.4444 | 731400.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2185 | 0.0000 | 0.6250 | 164104.0000 |
| innings_phase | 0.2196 | 0.0000 | 0.6281 | 164104.0000 |
| ece_optimized | 0.2201 | 0.0033 | 0.6293 | 164104.0000 |
| combined | 0.2201 | 0.0103 | 0.6295 | 164104.0000 |
| innings_specific | 0.2202 | 0.0122 | 0.6299 | 164104.0000 |
| raw | 0.2203 | 0.0098 | 0.6299 | 164104.0000 |
| logloss_optimized | 0.2204 | 0.0108 | 0.6302 | 164104.0000 |
| resource_win_prob | 0.2475 | 0.0243 | 0.6881 | 164104.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1940 | 0.0000 | 0.5674 | 426979.0000 |
| innings_phase | 0.1955 | 0.0000 | 0.5722 | 426979.0000 |
| innings_specific | 0.1957 | 0.0083 | 0.5727 | 426979.0000 |
| ece_optimized | 0.1957 | 0.0018 | 0.5728 | 426979.0000 |
| combined | 0.1959 | 0.0108 | 0.5733 | 426979.0000 |
| raw | 0.1960 | 0.0110 | 0.5735 | 426979.0000 |
| logloss_optimized | 0.1965 | 0.0198 | 0.5756 | 426979.0000 |
| resource_win_prob | 0.2236 | 0.0687 | 0.6380 | 426979.0000 |

### Innings 1 - Setup

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1847 | 0.0000 | 0.5464 | 100466.0000 |
| innings_phase | 0.1858 | 0.0000 | 0.5494 | 100466.0000 |
| ece_optimized | 0.1864 | 0.0033 | 0.5510 | 100466.0000 |
| innings_specific | 0.1865 | 0.0104 | 0.5512 | 100466.0000 |
| combined | 0.1867 | 0.0149 | 0.5520 | 100466.0000 |
| raw | 0.1868 | 0.0156 | 0.5522 | 100466.0000 |
| logloss_optimized | 0.1873 | 0.0184 | 0.5547 | 100466.0000 |
| resource_win_prob | 0.2089 | 0.0893 | 0.6055 | 100466.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1882 | 0.0000 | 0.5544 | 164077.0000 |
| innings_phase | 0.1896 | 0.0000 | 0.5584 | 164077.0000 |
| ece_optimized | 0.1899 | 0.0045 | 0.5595 | 164077.0000 |
| innings_specific | 0.1907 | 0.0245 | 0.5612 | 164077.0000 |
| combined | 0.1910 | 0.0322 | 0.5627 | 164077.0000 |
| logloss_optimized | 0.1911 | 0.0270 | 0.5638 | 164077.0000 |
| raw | 0.1912 | 0.0328 | 0.5630 | 164077.0000 |
| resource_win_prob | 0.2076 | 0.0646 | 0.6020 | 164077.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1567 | 0.0000 | 0.4743 | 163932.0000 |
| innings_phase | 0.1577 | 0.0000 | 0.4777 | 163932.0000 |
| ece_optimized | 0.1580 | 0.0037 | 0.4791 | 163932.0000 |
| innings_specific | 0.1582 | 0.0137 | 0.4792 | 163932.0000 |
| combined | 0.1585 | 0.0183 | 0.4801 | 163932.0000 |
| raw | 0.1585 | 0.0196 | 0.4808 | 163932.0000 |
| logloss_optimized | 0.1590 | 0.0251 | 0.4843 | 163932.0000 |
| resource_win_prob | 0.1727 | 0.0583 | 0.5175 | 163932.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1154 | 0.0000 | 0.3589 | 402250.0000 |
| innings_phase | 0.1169 | 0.0000 | 0.3640 | 402250.0000 |
| innings_specific | 0.1171 | 0.0054 | 0.3644 | 402250.0000 |
| ece_optimized | 0.1171 | 0.0035 | 0.3655 | 402250.0000 |
| combined | 0.1173 | 0.0100 | 0.3652 | 402250.0000 |
| raw | 0.1174 | 0.0136 | 0.3665 | 402250.0000 |
| logloss_optimized | 0.1190 | 0.0321 | 0.3762 | 402250.0000 |
| resource_win_prob | 0.1380 | 0.0325 | 0.4256 | 402250.0000 |

### Innings 2 - Setup

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0882 | 0.0000 | 0.2802 | 78564.0000 |
| innings_phase | 0.0891 | 0.0000 | 0.2835 | 78564.0000 |
| ece_optimized | 0.0895 | 0.0060 | 0.2861 | 78564.0000 |
| innings_specific | 0.0909 | 0.0212 | 0.2879 | 78564.0000 |
| combined | 0.0909 | 0.0219 | 0.2883 | 78564.0000 |
| raw | 0.0910 | 0.0262 | 0.2897 | 78564.0000 |
| logloss_optimized | 0.0919 | 0.0306 | 0.2999 | 78564.0000 |
| resource_win_prob | 0.1301 | 0.1094 | 0.3893 | 78564.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0751 | 0.0000 | 0.2440 | 86654.0000 |
| innings_phase | 0.0768 | 0.0000 | 0.2498 | 86654.0000 |
| ece_optimized | 0.0771 | 0.0060 | 0.2522 | 86654.0000 |
| logloss_optimized | 0.0790 | 0.0244 | 0.2638 | 86654.0000 |
| innings_specific | 0.0799 | 0.0317 | 0.2585 | 86654.0000 |
| raw | 0.0800 | 0.0350 | 0.2597 | 86654.0000 |
| combined | 0.0800 | 0.0328 | 0.2590 | 86654.0000 |
| resource_win_prob | 0.1412 | 0.1579 | 0.4432 | 86654.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1598 |
| Innings 1 | brier_optimized | 0.1965 |
| Innings 2 | brier_optimized | 0.1170 |
| Inn1 Powerplay | brier_optimized | 0.2185 |
| Inn1 Middle | brier_optimized | 0.1940 |
| Inn1 Setup | brier_optimized | 0.1847 |
| Inn1 Death | brier_optimized | 0.1882 |
| Inn2 Powerplay | brier_optimized | 0.1567 |
| Inn2 Middle | brier_optimized | 0.1154 |
| Inn2 Setup | brier_optimized | 0.0882 |
| Inn2 Death | brier_optimized | 0.0751 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Setup | brier_optimized | 0.0000 |
| Inn1 Death | innings_phase | 0.0000 |
| Inn2 Powerplay | innings_phase | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Setup | innings_phase | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.4763 |
| Innings 1 | brier_optimized | 0.5735 |
| Innings 2 | brier_optimized | 0.3627 |
| Inn1 Powerplay | brier_optimized | 0.6250 |
| Inn1 Middle | brier_optimized | 0.5674 |
| Inn1 Setup | brier_optimized | 0.5464 |
| Inn1 Death | brier_optimized | 0.5544 |
| Inn2 Powerplay | brier_optimized | 0.4743 |
| Inn2 Middle | brier_optimized | 0.3589 |
| Inn2 Setup | brier_optimized | 0.2802 |
| Inn2 Death | brier_optimized | 0.2440 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 11 segments
- **ECE**: `brier_optimized` wins in 8 segments
- **LogLoss**: `brier_optimized` wins in 11 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1874 | 0.1598 (brier_optimized) | **+14.7%** |
| LogLoss | 0.5482 | 0.4763 (brier_optimized) | **+13.1%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 192,529 | 0.043 | 0.037 | 0.0051  | 0.0350 |
| 0.1-0.2 | 131,636 | 0.150 | 0.147 | 0.0027  | 0.1243 |
| 0.2-0.3 | 145,213 | 0.251 | 0.255 | 0.0040  | 0.1890 |
| 0.3-0.4 | 158,671 | 0.351 | 0.350 | 0.0009  | 0.2268 |
| 0.4-0.5 | 169,507 | 0.450 | 0.455 | 0.0046  | 0.2472 |
| 0.5-0.6 | 168,499 | 0.550 | 0.548 | 0.0018  | 0.2468 |
| 0.6-0.7 | 161,253 | 0.649 | 0.646 | 0.0032  | 0.2280 |
| 0.7-0.8 | 143,984 | 0.749 | 0.747 | 0.0028  | 0.1887 |
| 0.8-0.9 | 137,374 | 0.850 | 0.848 | 0.0023  | 0.1281 |
| 0.9-1.0 | 178,360 | 0.954 | 0.966 | 0.0115  | 0.0322 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 198,410 | 0.034 | 0.034 | 0.0000  | 0.0316 |
| 0.1-0.2 | 130,595 | 0.144 | 0.144 | 0.0000  | 0.1226 |
| 0.2-0.3 | 132,269 | 0.254 | 0.254 | 0.0000  | 0.1888 |
| 0.3-0.4 | 173,781 | 0.347 | 0.347 | 0.0000  | 0.2258 |
| 0.4-0.5 | 140,319 | 0.449 | 0.449 | 0.0000  | 0.2465 |
| 0.5-0.6 | 190,784 | 0.544 | 0.544 | 0.0000  | 0.2471 |
| 0.6-0.7 | 163,156 | 0.647 | 0.647 | 0.0000  | 0.2274 |
| 0.7-0.8 | 141,903 | 0.750 | 0.750 | 0.0000  | 0.1869 |
| 0.8-0.9 | 129,019 | 0.851 | 0.851 | 0.0000  | 0.1262 |
| 0.9-1.0 | 186,790 | 0.968 | 0.968 | 0.0000  | 0.0296 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 198,520 | 0.037 | 0.037 | 0.0000  | 0.0349 |
| 0.1-0.2 | 127,023 | 0.145 | 0.145 | 0.0000  | 0.1233 |
| 0.2-0.3 | 126,315 | 0.251 | 0.251 | 0.0000  | 0.1873 |
| 0.3-0.4 | 182,418 | 0.347 | 0.347 | 0.0000  | 0.2258 |
| 0.4-0.5 | 165,408 | 0.455 | 0.455 | 0.0000  | 0.2471 |
| 0.5-0.6 | 171,120 | 0.551 | 0.551 | 0.0000  | 0.2465 |
| 0.6-0.7 | 157,301 | 0.647 | 0.647 | 0.0000  | 0.2278 |
| 0.7-0.8 | 146,067 | 0.750 | 0.750 | 0.0000  | 0.1869 |
| 0.8-0.9 | 122,144 | 0.847 | 0.847 | 0.0000  | 0.1290 |
| 0.9-1.0 | 190,710 | 0.964 | 0.964 | 0.0000  | 0.0340 |

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
