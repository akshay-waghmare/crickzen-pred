# OOF Calibration Analysis Report

**Generated:** 2026-01-15 20:03:05
**Samples:** 15,141
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1529 | 0.0000 | 0.4529 |
| innings_phase | 0.1614 | 0.0000 | 0.4784 |
| ece_optimized | 0.1651 | 0.0106 | 0.4909 |
| innings_specific | 0.1660 | 0.0000 | 0.4910 |
| combined | 0.1679 | 0.0000 | 0.4969 |
| logloss_optimized | 0.1694 | 0.0262 | 0.5068 |
| raw | 0.1732 | 0.0447 | 0.5131 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1905 | 0.0000 | 0.5545 | 7985.0000 |
| innings_phase | 0.1974 | 0.0000 | 0.5744 | 7985.0000 |
| ece_optimized | 0.2019 | 0.0115 | 0.5879 | 7985.0000 |
| innings_specific | 0.2022 | 0.0000 | 0.5863 | 7985.0000 |
| combined | 0.2034 | 0.0213 | 0.5904 | 7985.0000 |
| logloss_optimized | 0.2047 | 0.0407 | 0.5956 | 7985.0000 |
| raw | 0.2124 | 0.0699 | 0.6162 | 7985.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1109 | 0.0000 | 0.3396 | 7156.0000 |
| innings_phase | 0.1213 | 0.0000 | 0.3712 | 7156.0000 |
| ece_optimized | 0.1240 | 0.0125 | 0.3826 | 7156.0000 |
| innings_specific | 0.1255 | 0.0000 | 0.3846 | 7156.0000 |
| combined | 0.1282 | 0.0238 | 0.3927 | 7156.0000 |
| raw | 0.1295 | 0.0297 | 0.3981 | 7156.0000 |
| logloss_optimized | 0.1299 | 0.0318 | 0.4078 | 7156.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2293 | 0.0000 | 0.6480 | 2013.0000 |
| innings_phase | 0.2335 | 0.0000 | 0.6586 | 2013.0000 |
| ece_optimized | 0.2375 | 0.0233 | 0.6678 | 2013.0000 |
| logloss_optimized | 0.2375 | 0.0120 | 0.6680 | 2013.0000 |
| innings_specific | 0.2441 | 0.0727 | 0.6834 | 2013.0000 |
| combined | 0.2458 | 0.1091 | 0.6866 | 2013.0000 |
| raw | 0.2630 | 0.1645 | 0.7292 | 2013.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1843 | 0.0000 | 0.5403 | 3607.0000 |
| innings_phase | 0.1925 | 0.0000 | 0.5639 | 3607.0000 |
| innings_specific | 0.1954 | 0.0296 | 0.5711 | 3607.0000 |
| combined | 0.1961 | 0.0395 | 0.5747 | 3607.0000 |
| ece_optimized | 0.1970 | 0.0190 | 0.5771 | 3607.0000 |
| logloss_optimized | 0.2005 | 0.0615 | 0.5865 | 3607.0000 |
| raw | 0.2024 | 0.0670 | 0.5943 | 3607.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1668 | 0.0000 | 0.4964 | 2365.0000 |
| innings_phase | 0.1741 | 0.0000 | 0.5188 | 2365.0000 |
| innings_specific | 0.1770 | 0.0285 | 0.5270 | 2365.0000 |
| combined | 0.1784 | 0.0474 | 0.5324 | 2365.0000 |
| ece_optimized | 0.1790 | 0.0316 | 0.5363 | 2365.0000 |
| logloss_optimized | 0.1833 | 0.0529 | 0.5477 | 2365.0000 |
| raw | 0.1845 | 0.0679 | 0.5532 | 2365.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1390 | 0.0000 | 0.4191 | 2018.0000 |
| innings_phase | 0.1486 | 0.0000 | 0.4477 | 2018.0000 |
| ece_optimized | 0.1512 | 0.0130 | 0.4582 | 2018.0000 |
| innings_specific | 0.1535 | 0.0455 | 0.4603 | 2018.0000 |
| combined | 0.1557 | 0.0484 | 0.4674 | 2018.0000 |
| logloss_optimized | 0.1581 | 0.0516 | 0.4829 | 2018.0000 |
| raw | 0.1586 | 0.0634 | 0.4769 | 2018.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0930 | 0.0000 | 0.2869 | 3519.0000 |
| innings_phase | 0.1052 | 0.0000 | 0.3237 | 3519.0000 |
| innings_specific | 0.1072 | 0.0224 | 0.3326 | 3519.0000 |
| ece_optimized | 0.1073 | 0.0115 | 0.3330 | 3519.0000 |
| combined | 0.1090 | 0.0327 | 0.3393 | 3519.0000 |
| raw | 0.1098 | 0.0334 | 0.3423 | 3519.0000 |
| logloss_optimized | 0.1118 | 0.0370 | 0.3581 | 3519.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1146 | 0.0000 | 0.3553 | 1619.0000 |
| innings_phase | 0.1221 | 0.0000 | 0.3790 | 1619.0000 |
| ece_optimized | 0.1263 | 0.0261 | 0.3961 | 1619.0000 |
| innings_specific | 0.1306 | 0.0578 | 0.4033 | 1619.0000 |
| logloss_optimized | 0.1339 | 0.0413 | 0.4223 | 1619.0000 |
| combined | 0.1357 | 0.0674 | 0.4156 | 1619.0000 |
| raw | 0.1360 | 0.0662 | 0.4213 | 1619.0000 |