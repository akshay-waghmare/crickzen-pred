# IPL State Embeddings Offline Pilot Report

**Mode**: `full`
**Corpus coverage**: 90.76%
**Retrieval coverage**: 96.06%

## Overall Metrics

| Variant | N | Brier | Log Loss | ECE | ΔBrier | ΔLogLoss | ΔECE |
|---|---:|---:|---:|---:|---:|---:|---:|
| `baseline_ipl_v6_features` | 50635 | 0.1786 | 0.5295 | 0.0241 | +0.0000 | +0.0000 | +0.0000 |
| `regime_retrieval_features` | 50635 | 0.1788 | 0.5304 | 0.0249 | +0.0001 | +0.0009 | +0.0008 |
| `regime_cluster_features` | 50635 | 0.1784 | 0.5294 | 0.0238 | -0.0002 | -0.0002 | -0.0003 |
| `regime_hybrid_features` | 50635 | 0.1790 | 0.5308 | 0.0231 | +0.0003 | +0.0013 | -0.0010 |

## Season-Slice Validation (Cluster-Only)

| Slice | Variant | N | Brier | Log Loss | ECE | ΔBrier | ΔLogLoss | ΔECE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `season_2024` | `baseline_ipl_v6_features` | 15363 | 0.1686 | 0.5016 | 0.0163 | +0.0000 | +0.0000 | +0.0000 |
| `season_2024` | `regime_cluster_features` | 15363 | 0.1685 | 0.5012 | 0.0177 | -0.0001 | -0.0004 | +0.0014 |
| `season_2025` | `baseline_ipl_v6_features` | 15043 | 0.1709 | 0.5115 | 0.0275 | +0.0000 | +0.0000 | +0.0000 |
| `season_2025` | `regime_cluster_features` | 15043 | 0.1693 | 0.5084 | 0.0295 | -0.0016 | -0.0031 | +0.0020 |
| `season_2026` | `baseline_ipl_v6_features` | 4874 | 0.1377 | 0.4295 | 0.0881 | +0.0000 | +0.0000 | +0.0000 |
| `season_2026` | `regime_cluster_features` | 4874 | 0.1382 | 0.4313 | 0.0940 | +0.0005 | +0.0017 | +0.0059 |

## Segment Metrics

| Variant | Segment | Brier | Log Loss | ECE |
|---|---|---:|---:|---:|
| `baseline_ipl_v6_features` | overall | 0.1786 | 0.5295 | 0.0241 |
| `baseline_ipl_v6_features` | innings_1 | 0.2190 | 0.6285 | 0.0394 |
| `baseline_ipl_v6_features` | innings_1_powerplay | 0.2386 | 0.6685 | 0.0553 |
| `baseline_ipl_v6_features` | innings_1_middle | 0.2137 | 0.6174 | 0.0396 |
| `baseline_ipl_v6_features` | innings_1_death | 0.2094 | 0.6094 | 0.1070 |
| `baseline_ipl_v6_features` | innings_2 | 0.1355 | 0.4238 | 0.0525 |
| `baseline_ipl_v6_features` | innings_2_powerplay | 0.1740 | 0.5296 | 0.0834 |
| `baseline_ipl_v6_features` | innings_2_middle | 0.1378 | 0.4329 | 0.0559 |
| `baseline_ipl_v6_features` | innings_2_death | 0.0815 | 0.2679 | 0.0472 |
| `regime_retrieval_features` | overall | 0.1788 | 0.5304 | 0.0249 |
| `regime_retrieval_features` | innings_1 | 0.2180 | 0.6265 | 0.0379 |
| `regime_retrieval_features` | innings_1_powerplay | 0.2370 | 0.6650 | 0.0540 |
| `regime_retrieval_features` | innings_1_middle | 0.2128 | 0.6155 | 0.0391 |
| `regime_retrieval_features` | innings_1_death | 0.2088 | 0.6087 | 0.1097 |
| `regime_retrieval_features` | innings_2 | 0.1369 | 0.4277 | 0.0538 |
| `regime_retrieval_features` | innings_2_powerplay | 0.1751 | 0.5334 | 0.0837 |
| `regime_retrieval_features` | innings_2_middle | 0.1390 | 0.4366 | 0.0570 |
| `regime_retrieval_features` | innings_2_death | 0.0832 | 0.2728 | 0.0469 |
| `regime_cluster_features` | overall | 0.1784 | 0.5294 | 0.0238 |
| `regime_cluster_features` | innings_1 | 0.2178 | 0.6260 | 0.0353 |
| `regime_cluster_features` | innings_1_powerplay | 0.2366 | 0.6644 | 0.0486 |
| `regime_cluster_features` | innings_1_middle | 0.2130 | 0.6158 | 0.0388 |
| `regime_cluster_features` | innings_1_death | 0.2081 | 0.6069 | 0.1044 |
| `regime_cluster_features` | innings_2 | 0.1363 | 0.4261 | 0.0508 |
| `regime_cluster_features` | innings_2_powerplay | 0.1742 | 0.5303 | 0.0799 |
| `regime_cluster_features` | innings_2_middle | 0.1387 | 0.4355 | 0.0499 |
| `regime_cluster_features` | innings_2_death | 0.0826 | 0.2714 | 0.0503 |
| `regime_hybrid_features` | overall | 0.1790 | 0.5308 | 0.0231 |
| `regime_hybrid_features` | innings_1 | 0.2188 | 0.6285 | 0.0378 |
| `regime_hybrid_features` | innings_1_powerplay | 0.2381 | 0.6676 | 0.0513 |
| `regime_hybrid_features` | innings_1_middle | 0.2140 | 0.6185 | 0.0408 |
| `regime_hybrid_features` | innings_1_death | 0.2086 | 0.6081 | 0.1046 |
| `regime_hybrid_features` | innings_2 | 0.1364 | 0.4265 | 0.0518 |
| `regime_hybrid_features` | innings_2_powerplay | 0.1747 | 0.5319 | 0.0816 |
| `regime_hybrid_features` | innings_2_middle | 0.1386 | 0.4354 | 0.0531 |
| `regime_hybrid_features` | innings_2_death | 0.0827 | 0.2719 | 0.0490 |

## Regime Quality

| Regime | Label | Rows | Coverage | Win Rate | Separation | Stability |
|---:|---|---:|---:|---:|---:|---|
| 0 | pressure_state | 32788 | 12.95% | 0.128 | 5.602 | stable |
| 1 | pressure_state | 62810 | 24.81% | 0.705 | 4.672 | stable |
| 2 | pressure_state | 41033 | 16.21% | 0.582 | 4.910 | stable |
| 3 | pressure_state | 58928 | 23.28% | 0.533 | 4.672 | stable |
| 4 | pressure_state | 57024 | 22.52% | 0.351 | 5.047 | stable |
| 5 | pressure_state | 591 | 0.23% | 0.000 | 32.079 | stable |

## Reliability Coverage

- Saved 40 reliability-bin rows.

## Verdict

**GO**: `regime_cluster_features` beat the baseline on both Brier and log loss without material segment regressions.

### Gate failures
- [regime_retrieval_features] Brier did not improve (delta=+0.0001)
- [regime_retrieval_features] Log loss did not improve (delta=+0.0009)
- [regime_retrieval_features] ECE worsened beyond tolerance (delta=+0.0008)
- [regime_hybrid_features] Brier did not improve (delta=+0.0003)
- [regime_hybrid_features] Log loss did not improve (delta=+0.0013)
