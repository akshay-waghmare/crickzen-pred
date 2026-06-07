# IPL State Embeddings Offline Pilot Report

**Mode**: `full`
**Corpus coverage**: 90.46%
**Retrieval coverage**: 100.00%

## Overall Metrics

| Variant | N | Brier | Log Loss | ECE | ΔBrier vs Base | ΔLogLoss vs Base | ΔECE vs Base | ΔBrier vs Cluster | ΔLogLoss vs Cluster | ΔECE vs Cluster |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline_ipl_v6_features` | 8244 | 0.1750 | 0.5193 | 0.0216 | +0.0000 | +0.0000 | +0.0000 | +0.0005 | +0.0015 | +0.0006 |
| `regime_retrieval_features` | 8244 | 0.1755 | 0.5199 | 0.0237 | +0.0005 | +0.0006 | +0.0021 | +0.0010 | +0.0021 | +0.0027 |
| `regime_cluster_features` | 8244 | 0.1745 | 0.5178 | 0.0210 | -0.0005 | -0.0015 | -0.0006 | +0.0000 | +0.0000 | +0.0000 |
| `regime_hybrid_features` | 8244 | 0.1741 | 0.5166 | 0.0217 | -0.0009 | -0.0027 | +0.0002 | -0.0004 | -0.0012 | +0.0008 |
| `guarded_regime_phase_calibration` | 8244 | 0.1895 | 0.8628 | 0.0900 | +0.0145 | +0.3435 | +0.0684 | +0.0150 | +0.3451 | +0.0690 |
| `v18A_hard_pp_fallback` | 8244 | 0.1746 | 0.5180 | 0.0206 | -0.0005 | -0.0013 | -0.0010 | +0.0000 | +0.0003 | -0.0004 |
| `v18B_confidence_cap` | 8244 | 0.1745 | 0.5178 | 0.0209 | -0.0005 | -0.0015 | -0.0007 | +0.0000 | +0.0000 | -0.0001 |
| `v18C_dominant_cluster_only` | 8244 | 0.1746 | 0.5180 | 0.0206 | -0.0005 | -0.0013 | -0.0010 | +0.0000 | +0.0003 | -0.0004 |

## Season-Slice Validation

| Slice | Variant | N | Brier | Log Loss | ECE | ΔBrier vs Base | ΔLogLoss vs Base | ΔECE vs Base | ΔBrier vs Cluster | ΔLogLoss vs Cluster | ΔECE vs Cluster |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `season_2024` | `baseline_ipl_v6_features` | 2504 | 0.1639 | 0.4881 | 0.0195 | +0.0000 | +0.0000 | +0.0000 | -0.0011 | -0.0031 | +0.0019 |
| `season_2024` | `guarded_regime_phase_calibration` | 2504 | 0.1727 | 0.6651 | 0.0681 | +0.0088 | +0.1770 | +0.0485 | +0.0077 | +0.1739 | +0.0505 |
| `season_2024` | `regime_cluster_features` | 2504 | 0.1650 | 0.4911 | 0.0176 | +0.0011 | +0.0031 | -0.0019 | +0.0000 | +0.0000 | +0.0000 |
| `season_2024` | `v18A_hard_pp_fallback` | 2504 | 0.1648 | 0.4907 | 0.0197 | +0.0009 | +0.0026 | +0.0002 | -0.0002 | -0.0005 | +0.0022 |
| `season_2024` | `v18B_confidence_cap` | 2504 | 0.1650 | 0.4912 | 0.0176 | +0.0011 | +0.0031 | -0.0019 | +0.0000 | +0.0000 | +0.0000 |
| `season_2024` | `v18C_dominant_cluster_only` | 2504 | 0.1648 | 0.4907 | 0.0197 | +0.0009 | +0.0026 | +0.0002 | -0.0002 | -0.0005 | +0.0022 |
| `season_2025` | `baseline_ipl_v6_features` | 2455 | 0.1681 | 0.5046 | 0.0300 | +0.0000 | +0.0000 | +0.0000 | +0.0001 | +0.0011 | -0.0082 |
| `season_2025` | `guarded_regime_phase_calibration` | 2455 | 0.1793 | 0.7297 | 0.0655 | +0.0112 | +0.2250 | +0.0355 | +0.0113 | +0.2261 | +0.0274 |
| `season_2025` | `regime_cluster_features` | 2455 | 0.1680 | 0.5035 | 0.0382 | -0.0001 | -0.0011 | +0.0082 | +0.0000 | +0.0000 | +0.0000 |
| `season_2025` | `v18A_hard_pp_fallback` | 2455 | 0.1678 | 0.5035 | 0.0377 | -0.0003 | -0.0011 | +0.0077 | -0.0002 | -0.0000 | -0.0005 |
| `season_2025` | `v18B_confidence_cap` | 2455 | 0.1680 | 0.5036 | 0.0381 | -0.0001 | -0.0011 | +0.0081 | +0.0000 | +0.0000 | -0.0000 |
| `season_2025` | `v18C_dominant_cluster_only` | 2455 | 0.1678 | 0.5035 | 0.0377 | -0.0003 | -0.0011 | +0.0077 | -0.0002 | -0.0000 | -0.0005 |
| `season_2026` | `baseline_ipl_v6_features` | 798 | 0.1342 | 0.4203 | 0.1006 | +0.0000 | +0.0000 | +0.0000 | +0.0014 | +0.0039 | +0.0023 |
| `season_2026` | `guarded_regime_phase_calibration` | 798 | 0.1352 | 0.4695 | 0.0764 | +0.0010 | +0.0491 | -0.0242 | +0.0024 | +0.0531 | -0.0219 |
| `season_2026` | `regime_cluster_features` | 798 | 0.1328 | 0.4164 | 0.0983 | -0.0014 | -0.0039 | -0.0023 | +0.0000 | +0.0000 | +0.0000 |
| `season_2026` | `v18A_hard_pp_fallback` | 798 | 0.1331 | 0.4170 | 0.0988 | -0.0011 | -0.0033 | -0.0018 | +0.0003 | +0.0006 | +0.0005 |
| `season_2026` | `v18B_confidence_cap` | 798 | 0.1328 | 0.4163 | 0.0983 | -0.0014 | -0.0040 | -0.0023 | -0.0000 | -0.0001 | -0.0000 |
| `season_2026` | `v18C_dominant_cluster_only` | 798 | 0.1331 | 0.4170 | 0.0988 | -0.0011 | -0.0033 | -0.0018 | +0.0003 | +0.0006 | +0.0005 |

## Segment Metrics

| Variant | Segment | Brier | Log Loss | ECE | ΔBrier vs Base | ΔLogLoss vs Base | ΔECE vs Base | ΔBrier vs Cluster | ΔLogLoss vs Cluster | ΔECE vs Cluster |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline_ipl_v6_features` | overall | 0.1750 | 0.5193 | 0.0216 | +0.0000 | +0.0000 | +0.0000 | +0.0005 | +0.0015 | +0.0006 |
| `baseline_ipl_v6_features` | innings_1 | 0.2170 | 0.6242 | 0.0362 | +0.0000 | +0.0000 | +0.0000 | +0.0002 | +0.0003 | +0.0000 |
| `baseline_ipl_v6_features` | innings_1_powerplay | 0.2367 | 0.6645 | 0.0565 | +0.0000 | +0.0000 | +0.0000 | +0.0004 | +0.0008 | -0.0027 |
| `baseline_ipl_v6_features` | innings_1_middle | 0.2138 | 0.6171 | 0.0400 | +0.0000 | +0.0000 | +0.0000 | +0.0002 | +0.0003 | -0.0026 |
| `baseline_ipl_v6_features` | innings_1_death | 0.2070 | 0.6044 | 0.1017 | +0.0000 | +0.0000 | +0.0000 | +0.0001 | -0.0001 | +0.0011 |
| `baseline_ipl_v6_features` | innings_2 | 0.1317 | 0.4111 | 0.0473 | +0.0000 | +0.0000 | +0.0000 | +0.0008 | +0.0027 | -0.0013 |
| `baseline_ipl_v6_features` | innings_2_powerplay | 0.1731 | 0.5224 | 0.0779 | +0.0000 | +0.0000 | +0.0000 | +0.0003 | +0.0023 | +0.0025 |
| `baseline_ipl_v6_features` | innings_2_middle | 0.1398 | 0.4369 | 0.0456 | +0.0000 | +0.0000 | +0.0000 | +0.0010 | +0.0028 | -0.0031 |
| `baseline_ipl_v6_features` | innings_2_death | 0.0786 | 0.2602 | 0.0474 | +0.0000 | +0.0000 | +0.0000 | +0.0010 | +0.0030 | +0.0011 |
| `regime_retrieval_features` | overall | 0.1755 | 0.5199 | 0.0237 | +0.0005 | +0.0006 | +0.0021 | +0.0010 | +0.0021 | +0.0027 |
| `regime_retrieval_features` | innings_1 | 0.2187 | 0.6276 | 0.0389 | +0.0017 | +0.0034 | +0.0027 | +0.0019 | +0.0038 | +0.0028 |
| `regime_retrieval_features` | innings_1_powerplay | 0.2380 | 0.6671 | 0.0699 | +0.0013 | +0.0026 | +0.0134 | +0.0016 | +0.0034 | +0.0107 |
| `regime_retrieval_features` | innings_1_middle | 0.2153 | 0.6202 | 0.0427 | +0.0015 | +0.0031 | +0.0027 | +0.0018 | +0.0035 | +0.0001 |
| `regime_retrieval_features` | innings_1_death | 0.2092 | 0.6090 | 0.1028 | +0.0022 | +0.0046 | +0.0011 | +0.0023 | +0.0045 | +0.0021 |
| `regime_retrieval_features` | innings_2 | 0.1310 | 0.4089 | 0.0487 | -0.0007 | -0.0023 | +0.0014 | +0.0001 | +0.0005 | +0.0001 |
| `regime_retrieval_features` | innings_2_powerplay | 0.1730 | 0.5213 | 0.0777 | -0.0001 | -0.0010 | -0.0002 | +0.0002 | +0.0012 | +0.0023 |
| `regime_retrieval_features` | innings_2_middle | 0.1388 | 0.4339 | 0.0453 | -0.0010 | -0.0030 | -0.0003 | -0.0000 | -0.0001 | -0.0034 |
| `regime_retrieval_features` | innings_2_death | 0.0780 | 0.2582 | 0.0531 | -0.0006 | -0.0020 | +0.0056 | +0.0004 | +0.0010 | +0.0068 |
| `regime_cluster_features` | overall | 0.1745 | 0.5178 | 0.0210 | -0.0005 | -0.0015 | -0.0006 | +0.0000 | +0.0000 | +0.0000 |
| `regime_cluster_features` | innings_1 | 0.2168 | 0.6238 | 0.0361 | -0.0002 | -0.0003 | -0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `regime_cluster_features` | innings_1_powerplay | 0.2364 | 0.6637 | 0.0592 | -0.0004 | -0.0008 | +0.0027 | +0.0000 | +0.0000 | +0.0000 |
| `regime_cluster_features` | innings_1_middle | 0.2136 | 0.6167 | 0.0427 | -0.0002 | -0.0003 | +0.0026 | +0.0000 | +0.0000 | +0.0000 |
| `regime_cluster_features` | innings_1_death | 0.2069 | 0.6045 | 0.1007 | -0.0001 | +0.0001 | -0.0011 | +0.0000 | +0.0000 | +0.0000 |
| `regime_cluster_features` | innings_2 | 0.1309 | 0.4084 | 0.0486 | -0.0008 | -0.0027 | +0.0013 | +0.0000 | +0.0000 | +0.0000 |
| `regime_cluster_features` | innings_2_powerplay | 0.1728 | 0.5201 | 0.0754 | -0.0003 | -0.0023 | -0.0025 | +0.0000 | +0.0000 | +0.0000 |
| `regime_cluster_features` | innings_2_middle | 0.1388 | 0.4340 | 0.0487 | -0.0010 | -0.0028 | +0.0031 | +0.0000 | +0.0000 | +0.0000 |
| `regime_cluster_features` | innings_2_death | 0.0776 | 0.2572 | 0.0463 | -0.0010 | -0.0030 | -0.0011 | +0.0000 | +0.0000 | +0.0000 |
| `regime_hybrid_features` | overall | 0.1741 | 0.5166 | 0.0217 | -0.0009 | -0.0027 | +0.0002 | -0.0004 | -0.0012 | +0.0008 |
| `regime_hybrid_features` | innings_1 | 0.2172 | 0.6244 | 0.0403 | +0.0002 | +0.0002 | +0.0041 | +0.0004 | +0.0005 | +0.0042 |
| `regime_hybrid_features` | innings_1_powerplay | 0.2366 | 0.6640 | 0.0547 | -0.0001 | -0.0005 | -0.0018 | +0.0002 | +0.0003 | -0.0044 |
| `regime_hybrid_features` | innings_1_middle | 0.2140 | 0.6174 | 0.0373 | +0.0002 | +0.0003 | -0.0028 | +0.0005 | +0.0007 | -0.0054 |
| `regime_hybrid_features` | innings_1_death | 0.2073 | 0.6049 | 0.1005 | +0.0002 | +0.0005 | -0.0013 | +0.0004 | +0.0004 | -0.0002 |
| `regime_hybrid_features` | innings_2 | 0.1297 | 0.4054 | 0.0479 | -0.0020 | -0.0058 | +0.0006 | -0.0012 | -0.0030 | -0.0007 |
| `regime_hybrid_features` | innings_2_powerplay | 0.1719 | 0.5185 | 0.0752 | -0.0012 | -0.0039 | -0.0027 | -0.0009 | -0.0017 | -0.0003 |
| `regime_hybrid_features` | innings_2_middle | 0.1374 | 0.4305 | 0.0455 | -0.0024 | -0.0064 | -0.0001 | -0.0014 | -0.0036 | -0.0031 |
| `regime_hybrid_features` | innings_2_death | 0.0765 | 0.2541 | 0.0496 | -0.0021 | -0.0061 | +0.0022 | -0.0011 | -0.0031 | +0.0033 |
| `guarded_regime_phase_calibration` | overall | 0.1895 | 0.8628 | 0.0900 | +0.0145 | +0.3435 | +0.0684 | +0.0150 | +0.3451 | +0.0690 |
| `guarded_regime_phase_calibration` | innings_1 | 0.2295 | 0.8706 | 0.0904 | +0.0125 | +0.2465 | +0.0542 | +0.0127 | +0.2468 | +0.0543 |
| `guarded_regime_phase_calibration` | innings_1_powerplay | 0.2471 | 0.7449 | 0.0921 | +0.0103 | +0.0804 | +0.0356 | +0.0107 | +0.0812 | +0.0329 |
| `guarded_regime_phase_calibration` | innings_1_middle | 0.2279 | 0.7946 | 0.1025 | +0.0142 | +0.1775 | +0.0624 | +0.0144 | +0.1779 | +0.0598 |
| `guarded_regime_phase_calibration` | innings_1_death | 0.2183 | 1.1113 | 0.1224 | +0.0113 | +0.5069 | +0.0207 | +0.0114 | +0.5068 | +0.0217 |
| `guarded_regime_phase_calibration` | innings_2 | 0.1483 | 0.8548 | 0.1068 | +0.0165 | +0.4437 | +0.0595 | +0.0174 | +0.4464 | +0.0582 |
| `guarded_regime_phase_calibration` | innings_2_powerplay | 0.1901 | 1.0391 | 0.1454 | +0.0171 | +0.5167 | +0.0675 | +0.0174 | +0.5190 | +0.0700 |
| `guarded_regime_phase_calibration` | innings_2_middle | 0.1617 | 1.0062 | 0.1193 | +0.0219 | +0.5693 | +0.0737 | +0.0229 | +0.5722 | +0.0706 |
| `guarded_regime_phase_calibration` | innings_2_death | 0.0840 | 0.3883 | 0.0579 | +0.0054 | +0.1281 | +0.0104 | +0.0064 | +0.1311 | +0.0116 |
| `v18A_hard_pp_fallback` | overall | 0.1746 | 0.5180 | 0.0206 | -0.0005 | -0.0013 | -0.0010 | +0.0000 | +0.0003 | -0.0004 |
| `v18A_hard_pp_fallback` | innings_1 | 0.2168 | 0.6238 | 0.0361 | -0.0002 | -0.0003 | -0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `v18A_hard_pp_fallback` | innings_1_powerplay | 0.2364 | 0.6637 | 0.0592 | -0.0004 | -0.0008 | +0.0027 | +0.0000 | +0.0000 | +0.0000 |
| `v18A_hard_pp_fallback` | innings_1_middle | 0.2136 | 0.6167 | 0.0427 | -0.0002 | -0.0003 | +0.0026 | +0.0000 | +0.0000 | +0.0000 |
| `v18A_hard_pp_fallback` | innings_1_death | 0.2069 | 0.6045 | 0.1007 | -0.0001 | +0.0001 | -0.0011 | +0.0000 | +0.0000 | +0.0000 |
| `v18A_hard_pp_fallback` | innings_2 | 0.1310 | 0.4089 | 0.0479 | -0.0008 | -0.0022 | +0.0006 | +0.0001 | +0.0005 | -0.0007 |
| `v18A_hard_pp_fallback` | innings_2_powerplay | 0.1731 | 0.5224 | 0.0779 | +0.0000 | +0.0000 | +0.0000 | +0.0003 | +0.0023 | +0.0025 |
| `v18A_hard_pp_fallback` | innings_2_middle | 0.1388 | 0.4340 | 0.0487 | -0.0010 | -0.0028 | +0.0031 | +0.0000 | +0.0000 | +0.0000 |
| `v18A_hard_pp_fallback` | innings_2_death | 0.0776 | 0.2572 | 0.0463 | -0.0010 | -0.0030 | -0.0011 | +0.0000 | +0.0000 | +0.0000 |
| `v18B_confidence_cap` | overall | 0.1745 | 0.5178 | 0.0209 | -0.0005 | -0.0015 | -0.0007 | +0.0000 | +0.0000 | -0.0001 |
| `v18B_confidence_cap` | innings_1 | 0.2168 | 0.6238 | 0.0361 | -0.0002 | -0.0003 | -0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `v18B_confidence_cap` | innings_1_powerplay | 0.2364 | 0.6637 | 0.0592 | -0.0004 | -0.0008 | +0.0027 | +0.0000 | +0.0000 | +0.0000 |
| `v18B_confidence_cap` | innings_1_middle | 0.2136 | 0.6167 | 0.0427 | -0.0002 | -0.0003 | +0.0026 | +0.0000 | +0.0000 | +0.0000 |
| `v18B_confidence_cap` | innings_1_death | 0.2069 | 0.6045 | 0.1007 | -0.0001 | +0.0001 | -0.0011 | +0.0000 | +0.0000 | +0.0000 |
| `v18B_confidence_cap` | innings_2 | 0.1309 | 0.4084 | 0.0484 | -0.0008 | -0.0027 | +0.0011 | +0.0000 | +0.0000 | -0.0002 |
| `v18B_confidence_cap` | innings_2_powerplay | 0.1729 | 0.5203 | 0.0755 | -0.0002 | -0.0021 | -0.0025 | +0.0001 | +0.0002 | +0.0000 |
| `v18B_confidence_cap` | innings_2_middle | 0.1388 | 0.4340 | 0.0487 | -0.0010 | -0.0028 | +0.0031 | +0.0000 | +0.0000 | +0.0000 |
| `v18B_confidence_cap` | innings_2_death | 0.0776 | 0.2572 | 0.0463 | -0.0010 | -0.0030 | -0.0011 | +0.0000 | +0.0000 | +0.0000 |
| `v18C_dominant_cluster_only` | overall | 0.1746 | 0.5180 | 0.0206 | -0.0005 | -0.0013 | -0.0010 | +0.0000 | +0.0003 | -0.0004 |
| `v18C_dominant_cluster_only` | innings_1 | 0.2168 | 0.6238 | 0.0361 | -0.0002 | -0.0003 | -0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `v18C_dominant_cluster_only` | innings_1_powerplay | 0.2364 | 0.6637 | 0.0592 | -0.0004 | -0.0008 | +0.0027 | +0.0000 | +0.0000 | +0.0000 |
| `v18C_dominant_cluster_only` | innings_1_middle | 0.2136 | 0.6167 | 0.0427 | -0.0002 | -0.0003 | +0.0026 | +0.0000 | +0.0000 | +0.0000 |
| `v18C_dominant_cluster_only` | innings_1_death | 0.2069 | 0.6045 | 0.1007 | -0.0001 | +0.0001 | -0.0011 | +0.0000 | +0.0000 | +0.0000 |
| `v18C_dominant_cluster_only` | innings_2 | 0.1310 | 0.4089 | 0.0479 | -0.0008 | -0.0022 | +0.0006 | +0.0001 | +0.0005 | -0.0007 |
| `v18C_dominant_cluster_only` | innings_2_powerplay | 0.1731 | 0.5224 | 0.0779 | +0.0000 | +0.0000 | +0.0000 | +0.0003 | +0.0023 | +0.0025 |
| `v18C_dominant_cluster_only` | innings_2_middle | 0.1388 | 0.4340 | 0.0487 | -0.0010 | -0.0028 | +0.0031 | +0.0000 | +0.0000 | +0.0000 |
| `v18C_dominant_cluster_only` | innings_2_death | 0.0776 | 0.2572 | 0.0463 | -0.0010 | -0.0030 | -0.0011 | +0.0000 | +0.0000 | +0.0000 |

## Regime-Conditioned Calibration Guardrails

| Split | Variant | Min Samples | Candidate Slices | Fitted Slices | Applied Rows | Applied Share | Fallback Share | Skip Reasons |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `holdout` | `guarded_regime_phase_calibration` | 200 | 26 | 19 | 8033 | 97.44% | 2.56% | min_samples<200:7 |
| `season_2024` | `guarded_regime_phase_calibration` | 200 | 25 | 20 | 2490 | 99.44% | 0.56% | min_samples<200:5 |
| `season_2025` | `guarded_regime_phase_calibration` | 200 | 25 | 20 | 2446 | 99.63% | 0.37% | min_samples<200:5 |
| `season_2026` | `guarded_regime_phase_calibration` | 200 | 25 | 20 | 791 | 99.12% | 0.88% | min_samples<200:5 |

## Regime Quality

| Regime | Label | Rows | Coverage | Win Rate | Separation | Stability |
|---:|---|---:|---:|---:|---:|---|
| 0 | collapse_risk | 5839 | 14.17% | 0.616 | 4.797 | stable |
| 1 | pressure_state | 8820 | 21.40% | 0.501 | 4.711 | stable |
| 2 | pressure_state | 8549 | 20.74% | 0.629 | 4.711 | stable |
| 3 | pressure_state | 8714 | 21.14% | 0.289 | 5.334 | stable |
| 4 | pressure_state | 4652 | 11.29% | 0.848 | 4.963 | stable |
| 5 | pressure_state | 4642 | 11.26% | 0.113 | 6.176 | stable |

## Reliability Coverage

- Saved 80 reliability-bin rows.

## Verdict

**GO**: `regime_cluster_features` beat the baseline on both Brier and log loss without material segment regressions.

### Gate failures
- [regime_retrieval_features] Brier did not improve (delta=+0.0005)
- [regime_retrieval_features] Log loss did not improve (delta=+0.0006)
- [regime_retrieval_features] ECE worsened beyond tolerance (delta=+0.0021)
- [regime_hybrid_features] ECE worsened beyond tolerance (delta=+0.0002)
- [guarded_regime_phase_calibration] Brier did not improve (delta=+0.0145)
- [guarded_regime_phase_calibration] Log loss did not improve (delta=+0.3435)
- [guarded_regime_phase_calibration] ECE worsened beyond tolerance (delta=+0.0684)
- [guarded_regime_phase_calibration] Segment overall Brier regressed by +0.0145
- [guarded_regime_phase_calibration] Segment overall log loss regressed by +0.3435
- [guarded_regime_phase_calibration] Segment innings_1 Brier regressed by +0.0125
- [guarded_regime_phase_calibration] Segment innings_1 log loss regressed by +0.2465
- [guarded_regime_phase_calibration] Segment innings_1_powerplay Brier regressed by +0.0103
- [guarded_regime_phase_calibration] Segment innings_1_powerplay log loss regressed by +0.0804
- [guarded_regime_phase_calibration] Segment innings_1_middle Brier regressed by +0.0142
- [guarded_regime_phase_calibration] Segment innings_1_middle log loss regressed by +0.1775
- [guarded_regime_phase_calibration] Segment innings_1_death Brier regressed by +0.0113
- [guarded_regime_phase_calibration] Segment innings_1_death log loss regressed by +0.5069
- [guarded_regime_phase_calibration] Segment innings_2 Brier regressed by +0.0165
- [guarded_regime_phase_calibration] Segment innings_2 log loss regressed by +0.4437
- [guarded_regime_phase_calibration] Segment innings_2_powerplay Brier regressed by +0.0171
- [guarded_regime_phase_calibration] Segment innings_2_powerplay log loss regressed by +0.5167
- [guarded_regime_phase_calibration] Segment innings_2_middle Brier regressed by +0.0219
- [guarded_regime_phase_calibration] Segment innings_2_middle log loss regressed by +0.5693
- [guarded_regime_phase_calibration] Segment innings_2_death Brier regressed by +0.0054
- [guarded_regime_phase_calibration] Segment innings_2_death log loss regressed by +0.1281
