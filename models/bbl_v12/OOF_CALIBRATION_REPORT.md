# OOF Calibration Analysis Report

**Generated:** 2026-01-17 10:24:18
**Samples:** 141,435
**Folds:** 5

---

## Overall Performance

| method | brier | ece | logloss |
| --- | --- | --- | --- |
| brier_optimized | 0.1760 | 0.0000 | 0.5190 |
| innings_phase | 0.1787 | 0.0000 | 0.5269 |
| ece_optimized | 0.1796 | 0.0038 | 0.5300 |
| innings_specific | 0.1809 | 0.0000 | 0.5327 |
| logloss_optimized | 0.1810 | 0.0145 | 0.5349 |
| combined | 0.1817 | 0.0000 | 0.5356 |
| raw | 0.1825 | 0.0162 | 0.5381 |


## Per-Innings Breakdown


### Innings 1

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2134 | 0.0000 | 0.6130 | 73875.0000 |
| innings_phase | 0.2160 | 0.0000 | 0.6199 | 73875.0000 |
| ece_optimized | 0.2171 | 0.0058 | 0.6226 | 73875.0000 |
| innings_specific | 0.2173 | 0.0000 | 0.6230 | 73875.0000 |
| combined | 0.2182 | 0.0168 | 0.6263 | 73875.0000 |
| logloss_optimized | 0.2183 | 0.0211 | 0.6264 | 73875.0000 |
| raw | 0.2199 | 0.0328 | 0.6314 | 73875.0000 |

### Innings 2

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1352 | 0.0000 | 0.4161 | 67560.0000 |
| innings_phase | 0.1379 | 0.0000 | 0.4251 | 67560.0000 |
| ece_optimized | 0.1387 | 0.0033 | 0.4287 | 67560.0000 |
| logloss_optimized | 0.1401 | 0.0127 | 0.4349 | 67560.0000 |
| innings_specific | 0.1410 | 0.0000 | 0.4339 | 67560.0000 |
| raw | 0.1416 | 0.0063 | 0.4361 | 67560.0000 |
| combined | 0.1418 | 0.0184 | 0.4364 | 67560.0000 |


## Per-Innings × Phase Breakdown


### Innings 1 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2348 | 0.0000 | 0.6612 | 18658.0000 |
| innings_phase | 0.2366 | 0.0000 | 0.6654 | 18658.0000 |
| ece_optimized | 0.2376 | 0.0067 | 0.6679 | 18658.0000 |
| innings_specific | 0.2387 | 0.0337 | 0.6703 | 18658.0000 |
| logloss_optimized | 0.2389 | 0.0235 | 0.6705 | 18658.0000 |
| combined | 0.2397 | 0.0389 | 0.6726 | 18658.0000 |
| raw | 0.2411 | 0.0483 | 0.6763 | 18658.0000 |

### Innings 1 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.2117 | 0.0000 | 0.6098 | 33364.0000 |
| innings_phase | 0.2149 | 0.0000 | 0.6181 | 33364.0000 |
| innings_specific | 0.2156 | 0.0164 | 0.6196 | 33364.0000 |
| ece_optimized | 0.2159 | 0.0115 | 0.6208 | 33364.0000 |
| logloss_optimized | 0.2168 | 0.0240 | 0.6239 | 33364.0000 |
| combined | 0.2170 | 0.0233 | 0.6251 | 33364.0000 |
| raw | 0.2188 | 0.0341 | 0.6314 | 33364.0000 |

### Innings 1 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1977 | 0.0000 | 0.5769 | 21853.0000 |
| innings_phase | 0.2002 | 0.0000 | 0.5837 | 21853.0000 |
| ece_optimized | 0.2012 | 0.0031 | 0.5867 | 21853.0000 |
| innings_specific | 0.2017 | 0.0256 | 0.5878 | 21853.0000 |
| combined | 0.2017 | 0.0240 | 0.5885 | 21853.0000 |
| logloss_optimized | 0.2030 | 0.0358 | 0.5926 | 21853.0000 |
| raw | 0.2033 | 0.0375 | 0.5932 | 21853.0000 |

### Innings 2 - Powerplay

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1889 | 0.0000 | 0.5570 | 18700.0000 |
| innings_phase | 0.1910 | 0.0000 | 0.5632 | 18700.0000 |
| ece_optimized | 0.1918 | 0.0043 | 0.5655 | 18700.0000 |
| logloss_optimized | 0.1932 | 0.0287 | 0.5695 | 18700.0000 |
| raw | 0.1948 | 0.0431 | 0.5737 | 18700.0000 |
| innings_specific | 0.1949 | 0.0520 | 0.5736 | 18700.0000 |
| combined | 0.1951 | 0.0484 | 0.5734 | 18700.0000 |

### Innings 2 - Middle

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.1336 | 0.0000 | 0.4160 | 32475.0000 |
| innings_phase | 0.1370 | 0.0000 | 0.4275 | 32475.0000 |
| ece_optimized | 0.1377 | 0.0053 | 0.4312 | 32475.0000 |
| innings_specific | 0.1380 | 0.0188 | 0.4305 | 32475.0000 |
| logloss_optimized | 0.1387 | 0.0257 | 0.4349 | 32475.0000 |
| raw | 0.1390 | 0.0236 | 0.4339 | 32475.0000 |
| combined | 0.1392 | 0.0308 | 0.4344 | 32475.0000 |

### Innings 2 - Death

| method | brier | ece | logloss | n_samples |
| --- | --- | --- | --- | --- |
| brier_optimized | 0.0773 | 0.0000 | 0.2557 | 16385.0000 |
| innings_phase | 0.0792 | 0.0000 | 0.2629 | 16385.0000 |
| ece_optimized | 0.0800 | 0.0054 | 0.2676 | 16385.0000 |
| logloss_optimized | 0.0823 | 0.0329 | 0.2812 | 16385.0000 |
| innings_specific | 0.0854 | 0.0473 | 0.2812 | 16385.0000 |
| raw | 0.0859 | 0.0480 | 0.2835 | 16385.0000 |
| combined | 0.0860 | 0.0496 | 0.2841 | 16385.0000 |