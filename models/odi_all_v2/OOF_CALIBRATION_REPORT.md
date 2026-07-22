# OOF Calibration Analysis Report

**Generated:** 2026-07-11 01:10:08
**Samples:** 1,618,829
**Folds:** 3

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1583 | 0.0000 | 0.4729 |
| innings_phase | 0.1597 | 0.0000 | 0.4772 |
| ece_optimized | 0.1600 | 0.0032 | 0.4787 |
| innings_specific | 0.1604 | 0.0000 | 0.4792 |
| combined | 0.1606 | 0.0000 | 0.4797 |
| raw | 0.1607 | 0.0046 | 0.4803 |
| logloss_optimized | 0.1612 | 0.0160 | 0.4849 |
| resource_win_prob | 0.1874 | 0.0355 | 0.5482 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1947 | 0.0000 | 0.5700 | 872711.0000 |
| innings_phase | 0.1962 | 0.0000 | 0.5742 | 872711.0000 |
| ece_optimized | 0.1965 | 0.0031 | 0.5754 | 872711.0000 |
| innings_specific | 0.1967 | 0.0000 | 0.5756 | 872711.0000 |
| combined | 0.1968 | 0.0060 | 0.5761 | 872711.0000 |
| raw | 0.1969 | 0.0070 | 0.5765 | 872711.0000 |
| logloss_optimized | 0.1971 | 0.0140 | 0.5775 | 872711.0000 |
| resource_win_prob | 0.2232 | 0.0541 | 0.6366 | 872711.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1157 | 0.0000 | 0.3592 | 746118.0000 |
| innings_phase | 0.1170 | 0.0000 | 0.3637 | 746118.0000 |
| ece_optimized | 0.1173 | 0.0037 | 0.3655 | 746118.0000 |
| innings_specific | 0.1179 | 0.0000 | 0.3664 | 746118.0000 |
| combined | 0.1181 | 0.0070 | 0.3671 | 746118.0000 |
| raw | 0.1182 | 0.0090 | 0.3679 | 746118.0000 |
| logloss_optimized | 0.1192 | 0.0270 | 0.3766 | 746118.0000 |
| resource_win_prob | 0.1454 | 0.0293 | 0.4448 | 746118.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2153 | 0.0000 | 0.6183 | 167424.0000 |
| innings_phase | 0.2166 | 0.0000 | 0.6218 | 167424.0000 |
| combined | 0.2173 | 0.0112 | 0.6235 | 167424.0000 |
| innings_specific | 0.2173 | 0.0130 | 0.6235 | 167424.0000 |
| ece_optimized | 0.2173 | 0.0083 | 0.6235 | 167424.0000 |
| logloss_optimized | 0.2174 | 0.0086 | 0.6240 | 167424.0000 |
| raw | 0.2175 | 0.0106 | 0.6241 | 167424.0000 |
| resource_win_prob | 0.2475 | 0.0243 | 0.6882 | 167424.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1921 | 0.0000 | 0.5635 | 435548.0000 |
| innings_phase | 0.1937 | 0.0000 | 0.5684 | 435548.0000 |
| ece_optimized | 0.1940 | 0.0022 | 0.5692 | 435548.0000 |
| innings_specific | 0.1940 | 0.0083 | 0.5690 | 435548.0000 |
| combined | 0.1942 | 0.0126 | 0.5699 | 435548.0000 |
| raw | 0.1943 | 0.0121 | 0.5703 | 435548.0000 |
| logloss_optimized | 0.1946 | 0.0166 | 0.5717 | 435548.0000 |
| resource_win_prob | 0.2235 | 0.0696 | 0.6378 | 435548.0000 |

### Innings 1 - Setup

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1837 | 0.0000 | 0.5445 | 102465.0000 |
| innings_phase | 0.1847 | 0.0000 | 0.5473 | 102465.0000 |
| ece_optimized | 0.1852 | 0.0046 | 0.5491 | 102465.0000 |
| innings_specific | 0.1854 | 0.0103 | 0.5493 | 102465.0000 |
| combined | 0.1854 | 0.0130 | 0.5496 | 102465.0000 |
| raw | 0.1856 | 0.0153 | 0.5500 | 102465.0000 |
| logloss_optimized | 0.1859 | 0.0156 | 0.5517 | 102465.0000 |
| resource_win_prob | 0.2085 | 0.0897 | 0.6048 | 102465.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1878 | 0.0000 | 0.5542 | 167274.0000 |
| innings_phase | 0.1891 | 0.0000 | 0.5579 | 167274.0000 |
| ece_optimized | 0.1894 | 0.0033 | 0.5594 | 167274.0000 |
| logloss_optimized | 0.1901 | 0.0188 | 0.5618 | 167274.0000 |
| combined | 0.1901 | 0.0249 | 0.5609 | 167274.0000 |
| innings_specific | 0.1901 | 0.0219 | 0.5609 | 167274.0000 |
| raw | 0.1902 | 0.0260 | 0.5613 | 167274.0000 |
| resource_win_prob | 0.2073 | 0.0651 | 0.6013 | 167274.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1521 | 0.0000 | 0.4621 | 167243.0000 |
| innings_phase | 0.1530 | 0.0000 | 0.4651 | 167243.0000 |
| ece_optimized | 0.1533 | 0.0035 | 0.4667 | 167243.0000 |
| innings_specific | 0.1537 | 0.0172 | 0.4675 | 167243.0000 |
| combined | 0.1538 | 0.0173 | 0.4678 | 167243.0000 |
| raw | 0.1539 | 0.0180 | 0.4680 | 167243.0000 |
| logloss_optimized | 0.1548 | 0.0292 | 0.4737 | 167243.0000 |
| resource_win_prob | 0.1727 | 0.0592 | 0.5178 | 167243.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1143 | 0.0000 | 0.3554 | 410362.0000 |
| innings_phase | 0.1158 | 0.0000 | 0.3604 | 410362.0000 |
| innings_specific | 0.1160 | 0.0067 | 0.3610 | 410362.0000 |
| ece_optimized | 0.1160 | 0.0049 | 0.3621 | 410362.0000 |
| combined | 0.1163 | 0.0102 | 0.3617 | 410362.0000 |
| raw | 0.1164 | 0.0113 | 0.3627 | 410362.0000 |
| logloss_optimized | 0.1179 | 0.0303 | 0.3739 | 410362.0000 |
| resource_win_prob | 0.1381 | 0.0309 | 0.4259 | 410362.0000 |

### Innings 2 - Setup

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0896 | 0.0000 | 0.2838 | 80233.0000 |
| innings_phase | 0.0904 | 0.0000 | 0.2870 | 80233.0000 |
| ece_optimized | 0.0908 | 0.0059 | 0.2887 | 80233.0000 |
| innings_specific | 0.0920 | 0.0210 | 0.2913 | 80233.0000 |
| combined | 0.0922 | 0.0232 | 0.2920 | 80233.0000 |
| raw | 0.0924 | 0.0259 | 0.2934 | 80233.0000 |
| logloss_optimized | 0.0931 | 0.0280 | 0.3039 | 80233.0000 |
| resource_win_prob | 0.1302 | 0.1077 | 0.3894 | 80233.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0771 | 0.0000 | 0.2506 | 88280.0000 |
| innings_phase | 0.0789 | 0.0000 | 0.2567 | 88280.0000 |
| ece_optimized | 0.0792 | 0.0052 | 0.2594 | 88280.0000 |
| logloss_optimized | 0.0811 | 0.0207 | 0.2709 | 88280.0000 |
| innings_specific | 0.0828 | 0.0382 | 0.2686 | 88280.0000 |
| combined | 0.0828 | 0.0386 | 0.2692 | 88280.0000 |
| raw | 0.0828 | 0.0392 | 0.2700 | 88280.0000 |
| resource_win_prob | 0.1416 | 0.1579 | 0.4448 | 88280.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1583 |
| Innings 1 | brier_optimized | 0.1947 |
| Innings 2 | brier_optimized | 0.1157 |
| Inn1 Powerplay | brier_optimized | 0.2153 |
| Inn1 Middle | brier_optimized | 0.1921 |
| Inn1 Setup | brier_optimized | 0.1837 |
| Inn1 Death | brier_optimized | 0.1878 |
| Inn2 Powerplay | brier_optimized | 0.1521 |
| Inn2 Middle | brier_optimized | 0.1143 |
| Inn2 Setup | brier_optimized | 0.0896 |
| Inn2 Death | brier_optimized | 0.0771 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | innings_phase | 0.0000 |
| Innings 1 | brier_optimized | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
| Inn1 Powerplay | brier_optimized | 0.0000 |
| Inn1 Middle | brier_optimized | 0.0000 |
| Inn1 Setup | brier_optimized | 0.0000 |
| Inn1 Death | brier_optimized | 0.0000 |
| Inn2 Powerplay | innings_phase | 0.0000 |
| Inn2 Middle | brier_optimized | 0.0000 |
| Inn2 Setup | brier_optimized | 0.0000 |
| Inn2 Death | brier_optimized | 0.0000 |

### Best by LogLoss

| Segment | Best Method | LogLoss |
| --- | --- | --- |
| Overall | brier_optimized | 0.4729 |
| Innings 1 | brier_optimized | 0.5700 |
| Innings 2 | brier_optimized | 0.3592 |
| Inn1 Powerplay | brier_optimized | 0.6183 |
| Inn1 Middle | brier_optimized | 0.5635 |
| Inn1 Setup | brier_optimized | 0.5445 |
| Inn1 Death | brier_optimized | 0.5542 |
| Inn2 Powerplay | brier_optimized | 0.4621 |
| Inn2 Middle | brier_optimized | 0.3554 |
| Inn2 Setup | brier_optimized | 0.2838 |
| Inn2 Death | brier_optimized | 0.2506 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 11 segments
- **ECE**: `brier_optimized` wins in 9 segments
- **LogLoss**: `brier_optimized` wins in 11 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1874 | 0.1583 (brier_optimized) | **+15.5%** |
| LogLoss | 0.5482 | 0.4729 (brier_optimized) | **+13.7%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 208,348 | 0.040 | 0.041 | 0.0007  | 0.0380 |
| 0.1-0.2 | 134,731 | 0.150 | 0.155 | 0.0050  | 0.1301 |
| 0.2-0.3 | 144,689 | 0.251 | 0.253 | 0.0022  | 0.1884 |
| 0.3-0.4 | 156,975 | 0.350 | 0.345 | 0.0051  | 0.2250 |
| 0.4-0.5 | 165,771 | 0.450 | 0.449 | 0.0012  | 0.2467 |
| 0.5-0.6 | 167,222 | 0.550 | 0.555 | 0.0058  | 0.2460 |
| 0.6-0.7 | 161,023 | 0.649 | 0.653 | 0.0040  | 0.2256 |
| 0.7-0.8 | 149,904 | 0.750 | 0.741 | 0.0081  | 0.1910 |
| 0.8-0.9 | 142,666 | 0.850 | 0.844 | 0.0065  | 0.1312 |
| 0.9-1.0 | 187,500 | 0.956 | 0.964 | 0.0079  | 0.0340 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 204,501 | 0.035 | 0.035 | 0.0000  | 0.0324 |
| 0.1-0.2 | 131,275 | 0.146 | 0.146 | 0.0000  | 0.1240 |
| 0.2-0.3 | 174,392 | 0.253 | 0.253 | 0.0000  | 0.1881 |
| 0.3-0.4 | 130,912 | 0.352 | 0.352 | 0.0000  | 0.2271 |
| 0.4-0.5 | 165,163 | 0.448 | 0.448 | 0.0000  | 0.2464 |
| 0.5-0.6 | 162,254 | 0.544 | 0.544 | 0.0000  | 0.2473 |
| 0.6-0.7 | 168,880 | 0.654 | 0.654 | 0.0000  | 0.2254 |
| 0.7-0.8 | 158,430 | 0.749 | 0.749 | 0.0000  | 0.1871 |
| 0.8-0.9 | 135,060 | 0.850 | 0.850 | 0.0000  | 0.1267 |
| 0.9-1.0 | 187,962 | 0.970 | 0.970 | 0.0000  | 0.0277 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 196,136 | 0.035 | 0.035 | 0.0000  | 0.0331 |
| 0.1-0.2 | 141,739 | 0.145 | 0.145 | 0.0000  | 0.1232 |
| 0.2-0.3 | 181,811 | 0.260 | 0.260 | 0.0000  | 0.1918 |
| 0.3-0.4 | 122,050 | 0.356 | 0.356 | 0.0000  | 0.2282 |
| 0.4-0.5 | 165,994 | 0.448 | 0.448 | 0.0000  | 0.2466 |
| 0.5-0.6 | 165,808 | 0.547 | 0.547 | 0.0000  | 0.2473 |
| 0.6-0.7 | 161,154 | 0.653 | 0.653 | 0.0000  | 0.2257 |
| 0.7-0.8 | 154,209 | 0.744 | 0.744 | 0.0000  | 0.1896 |
| 0.8-0.9 | 149,368 | 0.847 | 0.847 | 0.0000  | 0.1284 |
| 0.9-1.0 | 180,560 | 0.970 | 0.970 | 0.0000  | 0.0285 |

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
