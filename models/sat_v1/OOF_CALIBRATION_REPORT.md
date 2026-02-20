# OOF Calibration Analysis Report

**Generated:** 2026-01-16 21:48:56
**Samples:** 21,793
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1685 | 0.0000 | 0.4874 |
| innings_phase | 0.1765 | 0.0000 | 0.5106 |
| ece_optimized | 0.1788 | 0.0139 | 0.5192 |
| innings_specific | 0.1825 | 0.0000 | 0.5256 |
| combined | 0.1848 | 0.0000 | 0.5335 |
| logloss_optimized | 0.1860 | 0.0373 | 0.5453 |
| raw | 0.1935 | 0.0655 | 0.5581 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2089 | 0.0000 | 0.5949 | 11470.0000 |
| innings_phase | 0.2162 | 0.0000 | 0.6141 | 11470.0000 |
| ece_optimized | 0.2187 | 0.0185 | 0.6217 | 11470.0000 |
| innings_specific | 0.2216 | 0.0000 | 0.6263 | 11470.0000 |
| logloss_optimized | 0.2229 | 0.0234 | 0.6350 | 11470.0000 |
| combined | 0.2236 | 0.0282 | 0.6342 | 11470.0000 |
| raw | 0.2347 | 0.0901 | 0.6621 | 11470.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1237 | 0.0000 | 0.3678 | 10323.0000 |
| innings_phase | 0.1324 | 0.0000 | 0.3956 | 10323.0000 |
| ece_optimized | 0.1345 | 0.0123 | 0.4053 | 10323.0000 |
| innings_specific | 0.1391 | 0.0000 | 0.4137 | 10323.0000 |
| combined | 0.1417 | 0.0313 | 0.4216 | 10323.0000 |
| logloss_optimized | 0.1449 | 0.0710 | 0.4457 | 10323.0000 |
| raw | 0.1477 | 0.0503 | 0.4425 | 10323.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2399 | 0.0000 | 0.6686 | 2900.0000 |
| innings_phase | 0.2440 | 0.0000 | 0.6791 | 2900.0000 |
| ece_optimized | 0.2474 | 0.0516 | 0.6865 | 2900.0000 |
| logloss_optimized | 0.2495 | 0.0000 | 0.6922 | 2900.0000 |
| innings_specific | 0.2530 | 0.0920 | 0.6983 | 2900.0000 |
| combined | 0.2561 | 0.1027 | 0.7049 | 2900.0000 |
| raw | 0.2821 | 0.1869 | 0.7657 | 2900.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2077 | 0.0000 | 0.5927 | 5174.0000 |
| innings_phase | 0.2179 | 0.0000 | 0.6182 | 5174.0000 |
| ece_optimized | 0.2197 | 0.0123 | 0.6244 | 5174.0000 |
| innings_specific | 0.2204 | 0.0273 | 0.6244 | 5174.0000 |
| combined | 0.2230 | 0.0401 | 0.6355 | 5174.0000 |
| logloss_optimized | 0.2245 | 0.0378 | 0.6396 | 5174.0000 |
| raw | 0.2309 | 0.0852 | 0.6567 | 5174.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1842 | 0.0000 | 0.5354 | 3396.0000 |
| innings_phase | 0.1897 | 0.0000 | 0.5524 | 3396.0000 |
| ece_optimized | 0.1925 | 0.0094 | 0.5623 | 3396.0000 |
| innings_specific | 0.1965 | 0.0550 | 0.5677 | 3396.0000 |
| combined | 0.1968 | 0.0477 | 0.5720 | 3396.0000 |
| logloss_optimized | 0.1979 | 0.0578 | 0.5792 | 3396.0000 |
| raw | 0.1999 | 0.0671 | 0.5819 | 3396.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1691 | 0.0000 | 0.4868 | 2898.0000 |
| innings_phase | 0.1758 | 0.0000 | 0.5067 | 2898.0000 |
| ece_optimized | 0.1786 | 0.0202 | 0.5177 | 2898.0000 |
| innings_specific | 0.1796 | 0.0436 | 0.5184 | 2898.0000 |
| combined | 0.1846 | 0.0724 | 0.5321 | 2898.0000 |
| logloss_optimized | 0.1916 | 0.0722 | 0.5638 | 2898.0000 |
| raw | 0.1952 | 0.0998 | 0.5632 | 2898.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1199 | 0.0000 | 0.3585 | 5041.0000 |
| innings_phase | 0.1293 | 0.0000 | 0.3897 | 5041.0000 |
| innings_specific | 0.1307 | 0.0176 | 0.3943 | 5041.0000 |
| ece_optimized | 0.1308 | 0.0159 | 0.3961 | 5041.0000 |
| combined | 0.1351 | 0.0473 | 0.4058 | 5041.0000 |
| raw | 0.1403 | 0.0538 | 0.4265 | 5041.0000 |
| logloss_optimized | 0.1428 | 0.1003 | 0.4405 | 5041.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0765 | 0.0000 | 0.2430 | 2384.0000 |
| innings_phase | 0.0863 | 0.0000 | 0.2732 | 2384.0000 |
| ece_optimized | 0.0889 | 0.0188 | 0.2881 | 2384.0000 |
| logloss_optimized | 0.0927 | 0.0448 | 0.3130 | 2384.0000 |
| combined | 0.1035 | 0.0667 | 0.3207 | 2384.0000 |
| raw | 0.1054 | 0.0773 | 0.3298 | 2384.0000 |
| innings_specific | 0.1077 | 0.0698 | 0.3275 | 2384.0000 |