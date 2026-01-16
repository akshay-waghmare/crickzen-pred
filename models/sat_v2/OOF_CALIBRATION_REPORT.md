# OOF Calibration Analysis Report

**Generated:** 2026-01-16 21:48:12
**Samples:** 21,793
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1677 | 0.0000 | 0.4852 |
| innings_phase | 0.1749 | 0.0000 | 0.5071 |
| ece_optimized | 0.1772 | 0.0120 | 0.5160 |
| innings_specific | 0.1806 | 0.0000 | 0.5220 |
| combined | 0.1832 | 0.0000 | 0.5304 |
| logloss_optimized | 0.1841 | 0.0360 | 0.5410 |
| raw | 0.1908 | 0.0610 | 0.5515 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2079 | 0.0000 | 0.5914 | 11470.0000 |
| innings_phase | 0.2145 | 0.0000 | 0.6094 | 11470.0000 |
| ece_optimized | 0.2171 | 0.0166 | 0.6173 | 11470.0000 |
| innings_specific | 0.2196 | 0.0000 | 0.6210 | 11470.0000 |
| logloss_optimized | 0.2217 | 0.0305 | 0.6319 | 11470.0000 |
| combined | 0.2218 | 0.0292 | 0.6293 | 11470.0000 |
| raw | 0.2325 | 0.0837 | 0.6563 | 11470.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1231 | 0.0000 | 0.3672 | 10323.0000 |
| innings_phase | 0.1308 | 0.0000 | 0.3935 | 10323.0000 |
| ece_optimized | 0.1327 | 0.0108 | 0.4035 | 10323.0000 |
| innings_specific | 0.1373 | 0.0000 | 0.4121 | 10323.0000 |
| combined | 0.1404 | 0.0325 | 0.4205 | 10323.0000 |
| logloss_optimized | 0.1424 | 0.0658 | 0.4400 | 10323.0000 |
| raw | 0.1444 | 0.0485 | 0.4350 | 10323.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2406 | 0.0000 | 0.6700 | 2900.0000 |
| innings_phase | 0.2441 | 0.0000 | 0.6794 | 2900.0000 |
| ece_optimized | 0.2475 | 0.0465 | 0.6869 | 2900.0000 |
| logloss_optimized | 0.2495 | 0.0000 | 0.6922 | 2900.0000 |
| innings_specific | 0.2543 | 0.0966 | 0.7013 | 2900.0000 |
| combined | 0.2554 | 0.1021 | 0.7035 | 2900.0000 |
| raw | 0.2819 | 0.1688 | 0.7660 | 2900.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2054 | 0.0000 | 0.5861 | 5174.0000 |
| innings_phase | 0.2151 | 0.0000 | 0.6111 | 5174.0000 |
| ece_optimized | 0.2172 | 0.0144 | 0.6177 | 5174.0000 |
| innings_specific | 0.2178 | 0.0379 | 0.6178 | 5174.0000 |
| combined | 0.2208 | 0.0473 | 0.6293 | 5174.0000 |
| logloss_optimized | 0.2224 | 0.0456 | 0.6351 | 5174.0000 |
| raw | 0.2275 | 0.0816 | 0.6482 | 5174.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1837 | 0.0000 | 0.5326 | 3396.0000 |
| innings_phase | 0.1884 | 0.0000 | 0.5469 | 3396.0000 |
| ece_optimized | 0.1911 | 0.0096 | 0.5574 | 3396.0000 |
| innings_specific | 0.1927 | 0.0485 | 0.5571 | 3396.0000 |
| combined | 0.1945 | 0.0482 | 0.5658 | 3396.0000 |
| logloss_optimized | 0.1967 | 0.0684 | 0.5756 | 3396.0000 |
| raw | 0.1979 | 0.0555 | 0.5748 | 3396.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1711 | 0.0000 | 0.4937 | 2898.0000 |
| innings_phase | 0.1777 | 0.0000 | 0.5145 | 2898.0000 |
| ece_optimized | 0.1797 | 0.0159 | 0.5233 | 2898.0000 |
| innings_specific | 0.1823 | 0.0432 | 0.5290 | 2898.0000 |
| combined | 0.1848 | 0.0695 | 0.5357 | 2898.0000 |
| logloss_optimized | 0.1897 | 0.0682 | 0.5598 | 2898.0000 |
| raw | 0.1936 | 0.0996 | 0.5612 | 2898.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1188 | 0.0000 | 0.3565 | 5041.0000 |
| innings_phase | 0.1270 | 0.0000 | 0.3856 | 5041.0000 |
| innings_specific | 0.1287 | 0.0191 | 0.3911 | 5041.0000 |
| ece_optimized | 0.1287 | 0.0138 | 0.3930 | 5041.0000 |
| combined | 0.1347 | 0.0535 | 0.4067 | 5041.0000 |
| raw | 0.1381 | 0.0551 | 0.4202 | 5041.0000 |
| logloss_optimized | 0.1406 | 0.0992 | 0.4348 | 5041.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0738 | 0.0000 | 0.2360 | 2384.0000 |
| innings_phase | 0.0818 | 0.0000 | 0.2633 | 2384.0000 |
| ece_optimized | 0.0841 | 0.0141 | 0.2801 | 2384.0000 |
| logloss_optimized | 0.0887 | 0.0474 | 0.3051 | 2384.0000 |
| raw | 0.0979 | 0.0667 | 0.3130 | 2384.0000 |
| combined | 0.0987 | 0.0592 | 0.3097 | 2384.0000 |
| innings_specific | 0.1010 | 0.0627 | 0.3146 | 2384.0000 |