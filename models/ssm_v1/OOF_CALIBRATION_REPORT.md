# OOF Calibration Analysis Report

**Generated:** 2026-01-16 11:01:27
**Samples:** 55,470
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1743 | 0.0000 | 0.5112 |
| innings_phase | 0.1787 | 0.0000 | 0.5250 |
| ece_optimized | 0.1803 | 0.0086 | 0.5306 |
| innings_specific | 0.1817 | 0.0000 | 0.5334 |
| logloss_optimized | 0.1831 | 0.0187 | 0.5407 |
| combined | 0.1834 | 0.0000 | 0.5390 |
| raw | 0.1867 | 0.0416 | 0.5492 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2136 | 0.0000 | 0.6087 | 28916.0000 |
| innings_phase | 0.2180 | 0.0000 | 0.6200 | 28916.0000 |
| ece_optimized | 0.2197 | 0.0129 | 0.6247 | 28916.0000 |
| innings_specific | 0.2206 | 0.0000 | 0.6261 | 28916.0000 |
| combined | 0.2222 | 0.0272 | 0.6322 | 28916.0000 |
| logloss_optimized | 0.2230 | 0.0308 | 0.6351 | 28916.0000 |
| raw | 0.2287 | 0.0693 | 0.6482 | 28916.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1314 | 0.0000 | 0.4051 | 26554.0000 |
| innings_phase | 0.1359 | 0.0000 | 0.4216 | 26554.0000 |
| ece_optimized | 0.1374 | 0.0052 | 0.4281 | 26554.0000 |
| innings_specific | 0.1393 | 0.0000 | 0.4325 | 26554.0000 |
| logloss_optimized | 0.1397 | 0.0233 | 0.4380 | 26554.0000 |
| raw | 0.1410 | 0.0239 | 0.4414 | 26554.0000 |
| combined | 0.1412 | 0.0296 | 0.4375 | 26554.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2408 | 0.0000 | 0.6732 | 7316.0000 |
| innings_phase | 0.2441 | 0.0000 | 0.6805 | 7316.0000 |
| ece_optimized | 0.2457 | 0.0147 | 0.6843 | 7316.0000 |
| logloss_optimized | 0.2481 | 0.0217 | 0.6893 | 7316.0000 |
| innings_specific | 0.2486 | 0.0427 | 0.6901 | 7316.0000 |
| combined | 0.2507 | 0.0485 | 0.6948 | 7316.0000 |
| raw | 0.2618 | 0.1126 | 0.7200 | 7316.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2142 | 0.0000 | 0.6088 | 13027.0000 |
| innings_phase | 0.2191 | 0.0000 | 0.6220 | 13027.0000 |
| innings_specific | 0.2200 | 0.0140 | 0.6244 | 13027.0000 |
| ece_optimized | 0.2207 | 0.0137 | 0.6261 | 13027.0000 |
| combined | 0.2227 | 0.0410 | 0.6339 | 13027.0000 |
| logloss_optimized | 0.2253 | 0.0543 | 0.6410 | 13027.0000 |
| raw | 0.2304 | 0.0820 | 0.6539 | 13027.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1897 | 0.0000 | 0.5534 | 8573.0000 |
| innings_phase | 0.1940 | 0.0000 | 0.5654 | 8573.0000 |
| ece_optimized | 0.1961 | 0.0135 | 0.5715 | 8573.0000 |
| combined | 0.1971 | 0.0373 | 0.5764 | 8573.0000 |
| innings_specific | 0.1977 | 0.0407 | 0.5742 | 8573.0000 |
| raw | 0.1977 | 0.0364 | 0.5783 | 8573.0000 |
| logloss_optimized | 0.1979 | 0.0367 | 0.5799 | 8573.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1571 | 0.0000 | 0.4741 | 7296.0000 |
| innings_phase | 0.1612 | 0.0000 | 0.4874 | 7296.0000 |
| ece_optimized | 0.1627 | 0.0118 | 0.4926 | 7296.0000 |
| innings_specific | 0.1644 | 0.0409 | 0.4967 | 7296.0000 |
| logloss_optimized | 0.1657 | 0.0428 | 0.5046 | 7296.0000 |
| combined | 0.1670 | 0.0503 | 0.5030 | 7296.0000 |
| raw | 0.1673 | 0.0579 | 0.5082 | 7296.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1351 | 0.0000 | 0.4165 | 12723.0000 |
| innings_phase | 0.1400 | 0.0000 | 0.4339 | 12723.0000 |
| innings_specific | 0.1409 | 0.0133 | 0.4369 | 12723.0000 |
| ece_optimized | 0.1415 | 0.0063 | 0.4414 | 12723.0000 |
| combined | 0.1429 | 0.0330 | 0.4423 | 12723.0000 |
| logloss_optimized | 0.1436 | 0.0365 | 0.4501 | 12723.0000 |
| raw | 0.1437 | 0.0357 | 0.4528 | 12723.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0956 | 0.0000 | 0.3059 | 6535.0000 |
| innings_phase | 0.0998 | 0.0000 | 0.3241 | 6535.0000 |
| ece_optimized | 0.1011 | 0.0098 | 0.3302 | 6535.0000 |
| logloss_optimized | 0.1031 | 0.0353 | 0.3399 | 6535.0000 |
| raw | 0.1064 | 0.0499 | 0.3445 | 6535.0000 |
| innings_specific | 0.1083 | 0.0567 | 0.3521 | 6535.0000 |
| combined | 0.1091 | 0.0560 | 0.3553 | 6535.0000 |