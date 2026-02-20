# OOF Calibration Analysis Report

**Generated:** 2026-01-16 13:59:45
**Samples:** 141,435
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1763 | 0.0000 | 0.5193 |
| innings_phase | 0.1791 | 0.0000 | 0.5274 |
| ece_optimized | 0.1799 | 0.0037 | 0.5306 |
| logloss_optimized | 0.1813 | 0.0166 | 0.5355 |
| innings_specific | 0.1814 | 0.0000 | 0.5336 |
| combined | 0.1822 | 0.0000 | 0.5366 |
| raw | 0.1830 | 0.0172 | 0.5393 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2139 | 0.0000 | 0.6142 | 73875.0000 |
| innings_phase | 0.2165 | 0.0000 | 0.6210 | 73875.0000 |
| ece_optimized | 0.2175 | 0.0062 | 0.6237 | 73875.0000 |
| innings_specific | 0.2178 | 0.0000 | 0.6243 | 73875.0000 |
| combined | 0.2187 | 0.0169 | 0.6276 | 73875.0000 |
| logloss_optimized | 0.2189 | 0.0271 | 0.6277 | 73875.0000 |
| raw | 0.2204 | 0.0332 | 0.6327 | 73875.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1352 | 0.0000 | 0.4155 | 67560.0000 |
| innings_phase | 0.1382 | 0.0000 | 0.4250 | 67560.0000 |
| ece_optimized | 0.1389 | 0.0029 | 0.4288 | 67560.0000 |
| logloss_optimized | 0.1403 | 0.0127 | 0.4347 | 67560.0000 |
| innings_specific | 0.1415 | 0.0000 | 0.4345 | 67560.0000 |
| raw | 0.1421 | 0.0089 | 0.4371 | 67560.0000 |
| combined | 0.1423 | 0.0185 | 0.4370 | 67560.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2351 | 0.0000 | 0.6620 | 18658.0000 |
| innings_phase | 0.2370 | 0.0000 | 0.6663 | 18658.0000 |
| ece_optimized | 0.2379 | 0.0075 | 0.6683 | 18658.0000 |
| innings_specific | 0.2393 | 0.0350 | 0.6715 | 18658.0000 |
| logloss_optimized | 0.2394 | 0.0257 | 0.6716 | 18658.0000 |
| combined | 0.2402 | 0.0421 | 0.6737 | 18658.0000 |
| raw | 0.2414 | 0.0413 | 0.6768 | 18658.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2122 | 0.0000 | 0.6112 | 33364.0000 |
| innings_phase | 0.2153 | 0.0000 | 0.6192 | 33364.0000 |
| innings_specific | 0.2160 | 0.0164 | 0.6208 | 33364.0000 |
| ece_optimized | 0.2163 | 0.0115 | 0.6218 | 33364.0000 |
| logloss_optimized | 0.2174 | 0.0279 | 0.6250 | 33364.0000 |
| combined | 0.2174 | 0.0250 | 0.6262 | 33364.0000 |
| raw | 0.2193 | 0.0399 | 0.6325 | 33364.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1982 | 0.0000 | 0.5781 | 21853.0000 |
| innings_phase | 0.2006 | 0.0000 | 0.5850 | 21853.0000 |
| ece_optimized | 0.2019 | 0.0038 | 0.5884 | 21853.0000 |
| innings_specific | 0.2023 | 0.0274 | 0.5894 | 21853.0000 |
| combined | 0.2025 | 0.0262 | 0.5905 | 21853.0000 |
| logloss_optimized | 0.2038 | 0.0349 | 0.5944 | 21853.0000 |
| raw | 0.2041 | 0.0369 | 0.5952 | 21853.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1883 | 0.0000 | 0.5552 | 18700.0000 |
| innings_phase | 0.1906 | 0.0000 | 0.5622 | 18700.0000 |
| ece_optimized | 0.1914 | 0.0029 | 0.5645 | 18700.0000 |
| logloss_optimized | 0.1929 | 0.0307 | 0.5686 | 18700.0000 |
| raw | 0.1943 | 0.0451 | 0.5720 | 18700.0000 |
| combined | 0.1945 | 0.0430 | 0.5715 | 18700.0000 |
| innings_specific | 0.1946 | 0.0523 | 0.5729 | 18700.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1334 | 0.0000 | 0.4146 | 32475.0000 |
| innings_phase | 0.1372 | 0.0000 | 0.4265 | 32475.0000 |
| ece_optimized | 0.1380 | 0.0050 | 0.4309 | 32475.0000 |
| innings_specific | 0.1381 | 0.0161 | 0.4290 | 32475.0000 |
| logloss_optimized | 0.1390 | 0.0238 | 0.4349 | 32475.0000 |
| raw | 0.1392 | 0.0216 | 0.4330 | 32475.0000 |
| combined | 0.1393 | 0.0281 | 0.4329 | 32475.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0781 | 0.0000 | 0.2577 | 16385.0000 |
| innings_phase | 0.0802 | 0.0000 | 0.2657 | 16385.0000 |
| ece_optimized | 0.0808 | 0.0052 | 0.2697 | 16385.0000 |
| logloss_optimized | 0.0827 | 0.0307 | 0.2816 | 16385.0000 |
| innings_specific | 0.0877 | 0.0531 | 0.2874 | 16385.0000 |
| raw | 0.0885 | 0.0557 | 0.2914 | 16385.0000 |
| combined | 0.0887 | 0.0568 | 0.2919 | 16385.0000 |