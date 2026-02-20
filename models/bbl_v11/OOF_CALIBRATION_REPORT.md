# OOF Calibration Analysis Report

**Generated:** 2026-01-16 18:07:48
**Samples:** 141,435
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1763 | 0.0000 | 0.5198 |
| innings_phase | 0.1789 | 0.0000 | 0.5275 |
| ece_optimized | 0.1799 | 0.0038 | 0.5308 |
| innings_specific | 0.1811 | 0.0000 | 0.5336 |
| logloss_optimized | 0.1812 | 0.0133 | 0.5355 |
| combined | 0.1820 | 0.0000 | 0.5365 |
| raw | 0.1828 | 0.0160 | 0.5391 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2138 | 0.0000 | 0.6145 | 73875.0000 |
| innings_phase | 0.2165 | 0.0000 | 0.6213 | 73875.0000 |
| ece_optimized | 0.2175 | 0.0048 | 0.6242 | 73875.0000 |
| innings_specific | 0.2179 | 0.0000 | 0.6251 | 73875.0000 |
| logloss_optimized | 0.2188 | 0.0195 | 0.6276 | 73875.0000 |
| combined | 0.2189 | 0.0172 | 0.6285 | 73875.0000 |
| raw | 0.2205 | 0.0336 | 0.6335 | 73875.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1353 | 0.0000 | 0.4163 | 67560.0000 |
| innings_phase | 0.1379 | 0.0000 | 0.4250 | 67560.0000 |
| ece_optimized | 0.1387 | 0.0045 | 0.4288 | 67560.0000 |
| logloss_optimized | 0.1401 | 0.0128 | 0.4349 | 67560.0000 |
| innings_specific | 0.1409 | 0.0000 | 0.4335 | 67560.0000 |
| raw | 0.1415 | 0.0078 | 0.4359 | 67560.0000 |
| combined | 0.1416 | 0.0188 | 0.4360 | 67560.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2354 | 0.0000 | 0.6626 | 18658.0000 |
| innings_phase | 0.2372 | 0.0000 | 0.6666 | 18658.0000 |
| ece_optimized | 0.2382 | 0.0049 | 0.6689 | 18658.0000 |
| logloss_optimized | 0.2395 | 0.0210 | 0.6718 | 18658.0000 |
| innings_specific | 0.2395 | 0.0356 | 0.6720 | 18658.0000 |
| combined | 0.2405 | 0.0387 | 0.6744 | 18658.0000 |
| raw | 0.2416 | 0.0435 | 0.6773 | 18658.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2120 | 0.0000 | 0.6111 | 33364.0000 |
| innings_phase | 0.2153 | 0.0000 | 0.6197 | 33364.0000 |
| innings_specific | 0.2161 | 0.0185 | 0.6217 | 33364.0000 |
| ece_optimized | 0.2163 | 0.0094 | 0.6224 | 33364.0000 |
| logloss_optimized | 0.2170 | 0.0154 | 0.6245 | 33364.0000 |
| combined | 0.2175 | 0.0242 | 0.6273 | 33364.0000 |
| raw | 0.2195 | 0.0391 | 0.6339 | 33364.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1982 | 0.0000 | 0.5786 | 21853.0000 |
| innings_phase | 0.2006 | 0.0000 | 0.5852 | 21853.0000 |
| ece_optimized | 0.2018 | 0.0056 | 0.5886 | 21853.0000 |
| innings_specific | 0.2024 | 0.0292 | 0.5903 | 21853.0000 |
| combined | 0.2026 | 0.0291 | 0.5910 | 21853.0000 |
| logloss_optimized | 0.2038 | 0.0344 | 0.5946 | 21853.0000 |
| raw | 0.2042 | 0.0373 | 0.5955 | 21853.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1889 | 0.0000 | 0.5570 | 18700.0000 |
| innings_phase | 0.1909 | 0.0000 | 0.5630 | 18700.0000 |
| ece_optimized | 0.1918 | 0.0044 | 0.5654 | 18700.0000 |
| logloss_optimized | 0.1933 | 0.0291 | 0.5697 | 18700.0000 |
| innings_specific | 0.1946 | 0.0490 | 0.5726 | 18700.0000 |
| raw | 0.1946 | 0.0401 | 0.5732 | 18700.0000 |
| combined | 0.1947 | 0.0449 | 0.5722 | 18700.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1335 | 0.0000 | 0.4161 | 32475.0000 |
| innings_phase | 0.1369 | 0.0000 | 0.4272 | 32475.0000 |
| ece_optimized | 0.1376 | 0.0058 | 0.4310 | 32475.0000 |
| innings_specific | 0.1379 | 0.0191 | 0.4302 | 32475.0000 |
| logloss_optimized | 0.1385 | 0.0247 | 0.4344 | 32475.0000 |
| raw | 0.1388 | 0.0234 | 0.4336 | 32475.0000 |
| combined | 0.1390 | 0.0309 | 0.4338 | 32475.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0775 | 0.0000 | 0.2560 | 16385.0000 |
| innings_phase | 0.0794 | 0.0000 | 0.2631 | 16385.0000 |
| ece_optimized | 0.0802 | 0.0080 | 0.2683 | 16385.0000 |
| logloss_optimized | 0.0826 | 0.0332 | 0.2819 | 16385.0000 |
| innings_specific | 0.0857 | 0.0455 | 0.2814 | 16385.0000 |
| raw | 0.0861 | 0.0476 | 0.2841 | 16385.0000 |
| combined | 0.0863 | 0.0493 | 0.2849 | 16385.0000 |