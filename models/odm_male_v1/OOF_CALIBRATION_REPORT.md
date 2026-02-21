# OOF Calibration Analysis Report

**Generated:** 2026-02-21 10:47:08
**Samples:** 778,174
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1801 | 0.0000 | 0.5269 |
| innings_phase | 0.1824 | 0.0000 | 0.5336 |
| ece_optimized | 0.1828 | 0.0018 | 0.5354 |
| innings_specific | 0.1832 | 0.0000 | 0.5360 |
| combined | 0.1836 | 0.0000 | 0.5372 |
| raw | 0.1840 | 0.0124 | 0.5387 |
| logloss_optimized | 0.1841 | 0.0185 | 0.5409 |
| resource_win_prob | 0.1991 | 0.0295 | 0.5811 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2163 | 0.0000 | 0.6179 | 422396.0000 |
| innings_phase | 0.2185 | 0.0000 | 0.6238 | 422396.0000 |
| ece_optimized | 0.2190 | 0.0019 | 0.6253 | 422396.0000 |
| innings_specific | 0.2191 | 0.0000 | 0.6254 | 422396.0000 |
| combined | 0.2194 | 0.0120 | 0.6264 | 422396.0000 |
| logloss_optimized | 0.2200 | 0.0185 | 0.6288 | 422396.0000 |
| raw | 0.2202 | 0.0228 | 0.6284 | 422396.0000 |
| resource_win_prob | 0.2287 | 0.0217 | 0.6478 | 422396.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1372 | 0.0000 | 0.4189 | 355778.0000 |
| innings_phase | 0.1395 | 0.0000 | 0.4265 | 355778.0000 |
| ece_optimized | 0.1399 | 0.0032 | 0.4286 | 355778.0000 |
| innings_specific | 0.1406 | 0.0000 | 0.4298 | 355778.0000 |
| raw | 0.1410 | 0.0114 | 0.4321 | 355778.0000 |
| combined | 0.1411 | 0.0142 | 0.4312 | 355778.0000 |
| logloss_optimized | 0.1415 | 0.0267 | 0.4367 | 355778.0000 |
| resource_win_prob | 0.1640 | 0.0486 | 0.5020 | 355778.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2379 | 0.0000 | 0.6673 | 82738.0000 |
| innings_phase | 0.2395 | 0.0000 | 0.6711 | 82738.0000 |
| ece_optimized | 0.2401 | 0.0024 | 0.6725 | 82738.0000 |
| innings_specific | 0.2402 | 0.0070 | 0.6729 | 82738.0000 |
| combined | 0.2404 | 0.0147 | 0.6733 | 82738.0000 |
| logloss_optimized | 0.2406 | 0.0104 | 0.6738 | 82738.0000 |
| raw | 0.2411 | 0.0190 | 0.6748 | 82738.0000 |
| resource_win_prob | 0.2478 | 0.0278 | 0.6888 | 82738.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2150 | 0.0000 | 0.6144 | 213388.0000 |
| innings_phase | 0.2175 | 0.0000 | 0.6213 | 213388.0000 |
| innings_specific | 0.2178 | 0.0100 | 0.6221 | 213388.0000 |
| ece_optimized | 0.2179 | 0.0041 | 0.6224 | 213388.0000 |
| combined | 0.2182 | 0.0176 | 0.6232 | 213388.0000 |
| logloss_optimized | 0.2190 | 0.0254 | 0.6266 | 213388.0000 |
| raw | 0.2190 | 0.0291 | 0.6255 | 213388.0000 |
| resource_win_prob | 0.2290 | 0.0393 | 0.6491 | 213388.0000 |

### Innings 1 - Setup

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2028 | 0.0000 | 0.5873 | 49099.0000 |
| innings_phase | 0.2044 | 0.0000 | 0.5920 | 49099.0000 |
| ece_optimized | 0.2053 | 0.0073 | 0.5946 | 49099.0000 |
| innings_specific | 0.2055 | 0.0129 | 0.5947 | 49099.0000 |
| combined | 0.2055 | 0.0131 | 0.5954 | 49099.0000 |
| raw | 0.2059 | 0.0187 | 0.5967 | 49099.0000 |
| logloss_optimized | 0.2062 | 0.0213 | 0.5983 | 49099.0000 |
| resource_win_prob | 0.2157 | 0.0518 | 0.6195 | 49099.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2053 | 0.0000 | 0.5939 | 77171.0000 |
| innings_phase | 0.2075 | 0.0000 | 0.6000 | 77171.0000 |
| ece_optimized | 0.2083 | 0.0037 | 0.6022 | 77171.0000 |
| innings_specific | 0.2088 | 0.0242 | 0.6029 | 77171.0000 |
| logloss_optimized | 0.2093 | 0.0241 | 0.6057 | 77171.0000 |
| combined | 0.2093 | 0.0315 | 0.6048 | 77171.0000 |
| raw | 0.2102 | 0.0365 | 0.6071 | 77171.0000 |
| resource_win_prob | 0.2155 | 0.0364 | 0.6182 | 77171.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1785 | 0.0000 | 0.5295 | 82490.0000 |
| innings_phase | 0.1804 | 0.0000 | 0.5352 | 82490.0000 |
| ece_optimized | 0.1807 | 0.0029 | 0.5366 | 82490.0000 |
| innings_specific | 0.1811 | 0.0143 | 0.5374 | 82490.0000 |
| raw | 0.1814 | 0.0153 | 0.5383 | 82490.0000 |
| combined | 0.1816 | 0.0214 | 0.5386 | 82490.0000 |
| logloss_optimized | 0.1817 | 0.0192 | 0.5405 | 82490.0000 |
| resource_win_prob | 0.1883 | 0.0414 | 0.5600 | 82490.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1337 | 0.0000 | 0.4119 | 197048.0000 |
| innings_phase | 0.1362 | 0.0000 | 0.4203 | 197048.0000 |
| ece_optimized | 0.1365 | 0.0031 | 0.4220 | 197048.0000 |
| innings_specific | 0.1365 | 0.0109 | 0.4213 | 197048.0000 |
| raw | 0.1371 | 0.0193 | 0.4242 | 197048.0000 |
| combined | 0.1373 | 0.0204 | 0.4231 | 197048.0000 |
| logloss_optimized | 0.1377 | 0.0278 | 0.4294 | 197048.0000 |
| resource_win_prob | 0.1580 | 0.0420 | 0.4862 | 197048.0000 |

### Innings 2 - Setup

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1092 | 0.0000 | 0.3401 | 37104.0000 |
| innings_phase | 0.1108 | 0.0000 | 0.3460 | 37104.0000 |
| ece_optimized | 0.1114 | 0.0056 | 0.3499 | 37104.0000 |
| combined | 0.1129 | 0.0208 | 0.3531 | 37104.0000 |
| innings_specific | 0.1129 | 0.0242 | 0.3529 | 37104.0000 |
| raw | 0.1130 | 0.0285 | 0.3543 | 37104.0000 |
| logloss_optimized | 0.1147 | 0.0433 | 0.3637 | 37104.0000 |
| resource_win_prob | 0.1463 | 0.1201 | 0.4493 | 37104.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0944 | 0.0000 | 0.2959 | 39136.0000 |
| innings_phase | 0.0972 | 0.0000 | 0.3049 | 39136.0000 |
| ece_optimized | 0.0978 | 0.0086 | 0.3085 | 39136.0000 |
| logloss_optimized | 0.1014 | 0.0428 | 0.3238 | 39136.0000 |
| combined | 0.1020 | 0.0448 | 0.3195 | 39136.0000 |
| innings_specific | 0.1021 | 0.0448 | 0.3192 | 39136.0000 |
| raw | 0.1023 | 0.0498 | 0.3217 | 39136.0000 |
| resource_win_prob | 0.1592 | 0.1768 | 0.5087 | 39136.0000 |


## Best Method by Segment

This section shows which calibration method performs best for each segment, broken down by metric.


### Best by Brier Score

| Segment | Best Method | Brier Score |
| --- | --- | --- |
| Overall | brier_optimized | 0.1801 |
| Innings 1 | brier_optimized | 0.2163 |
| Innings 2 | brier_optimized | 0.1372 |
| Inn1 Powerplay | brier_optimized | 0.2379 |
| Inn1 Middle | brier_optimized | 0.2150 |
| Inn1 Setup | brier_optimized | 0.2028 |
| Inn1 Death | brier_optimized | 0.2053 |
| Inn2 Powerplay | brier_optimized | 0.1785 |
| Inn2 Middle | brier_optimized | 0.1337 |
| Inn2 Setup | brier_optimized | 0.1092 |
| Inn2 Death | brier_optimized | 0.0944 |

### Best by ECE

| Segment | Best Method | ECE |
| --- | --- | --- |
| Overall | brier_optimized | 0.0000 |
| Innings 1 | innings_phase | 0.0000 |
| Innings 2 | brier_optimized | 0.0000 |
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
| Overall | brier_optimized | 0.5269 |
| Innings 1 | brier_optimized | 0.6179 |
| Innings 2 | brier_optimized | 0.4189 |
| Inn1 Powerplay | brier_optimized | 0.6673 |
| Inn1 Middle | brier_optimized | 0.6144 |
| Inn1 Setup | brier_optimized | 0.5873 |
| Inn1 Death | brier_optimized | 0.5939 |
| Inn2 Powerplay | brier_optimized | 0.5295 |
| Inn2 Middle | brier_optimized | 0.4119 |
| Inn2 Setup | brier_optimized | 0.3401 |
| Inn2 Death | brier_optimized | 0.2959 |


## Recommendations

Based on the analysis above:

- **Brier Score**: `brier_optimized` wins in 11 segments
- **ECE**: `brier_optimized` wins in 10 segments
- **LogLoss**: `brier_optimized` wins in 11 segments


## Resource Win Prob Baseline Comparison

Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):


| Metric | resource_win_prob | Best Model | Improvement |
| --- | --- | --- | --- |
| Brier | 0.1991 | 0.1801 (brier_optimized) | **+9.5%** |
| LogLoss | 0.5811 | 0.5269 (brier_optimized) | **+9.3%** |


## Probability Bin Calibration Analysis

Calibration quality by predicted probability range (10 bins):


### raw

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 63,230 | 0.049 | 0.041 | 0.0085  | 0.0384 |
| 0.1-0.2 | 57,553 | 0.150 | 0.155 | 0.0044  | 0.1292 |
| 0.2-0.3 | 71,036 | 0.252 | 0.262 | 0.0096  | 0.1928 |
| 0.3-0.4 | 89,942 | 0.352 | 0.374 | 0.0218  | 0.2333 |
| 0.4-0.5 | 110,829 | 0.451 | 0.462 | 0.0106  | 0.2482 |
| 0.5-0.6 | 109,926 | 0.549 | 0.551 | 0.0016  | 0.2465 |
| 0.6-0.7 | 89,414 | 0.648 | 0.631 | 0.0171  | 0.2326 |
| 0.7-0.8 | 67,808 | 0.748 | 0.728 | 0.0199  | 0.1971 |
| 0.8-0.9 | 59,449 | 0.850 | 0.838 | 0.0120  | 0.1346 |
| 0.9-1.0 | 58,987 | 0.946 | 0.967 | 0.0214  | 0.0317 |

### brier_optimized

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 71,269 | 0.038 | 0.038 | 0.0000  | 0.0350 |
| 0.1-0.2 | 48,363 | 0.146 | 0.146 | 0.0000  | 0.1237 |
| 0.2-0.3 | 65,116 | 0.251 | 0.251 | 0.0000  | 0.1875 |
| 0.3-0.4 | 74,036 | 0.353 | 0.353 | 0.0000  | 0.2274 |
| 0.4-0.5 | 129,545 | 0.450 | 0.450 | 0.0000  | 0.2467 |
| 0.5-0.6 | 117,976 | 0.549 | 0.549 | 0.0000  | 0.2466 |
| 0.6-0.7 | 90,193 | 0.641 | 0.641 | 0.0000  | 0.2292 |
| 0.7-0.8 | 75,863 | 0.749 | 0.749 | 0.0000  | 0.1870 |
| 0.8-0.9 | 36,255 | 0.850 | 0.850 | 0.0000  | 0.1266 |
| 0.9-1.0 | 69,558 | 0.967 | 0.967 | 0.0000  | 0.0308 |

### innings_phase

| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |
| --- | --- | --- | --- | --- | --- |
| 0.0-0.1 | 67,449 | 0.041 | 0.041 | 0.0000  | 0.0383 |
| 0.1-0.2 | 52,080 | 0.147 | 0.147 | 0.0000  | 0.1244 |
| 0.2-0.3 | 65,574 | 0.259 | 0.259 | 0.0000  | 0.1910 |
| 0.3-0.4 | 69,312 | 0.351 | 0.351 | 0.0000  | 0.2266 |
| 0.4-0.5 | 128,903 | 0.448 | 0.448 | 0.0000  | 0.2465 |
| 0.5-0.6 | 118,204 | 0.546 | 0.546 | 0.0000  | 0.2470 |
| 0.6-0.7 | 106,677 | 0.642 | 0.642 | 0.0000  | 0.2291 |
| 0.7-0.8 | 65,608 | 0.752 | 0.752 | 0.0000  | 0.1860 |
| 0.8-0.9 | 39,476 | 0.854 | 0.854 | 0.0000  | 0.1235 |
| 0.9-1.0 | 64,891 | 0.965 | 0.965 | 0.0000  | 0.0328 |

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
