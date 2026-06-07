# Innings 2 Powerplay Diagnostics

- Focus variant: `regime_cluster_features`
- Holdout PP rows exported: 13,572
- Focus-variant PP rows: 6,786
- Overconfident wrong predictions: 499
- Recent PP rows (2025-2026): 2,697

## PP Reliability Bins

| Variant | Bin | N | Mean Pred | Mean Actual | Gap |
|---|---|---:|---:|---:|---:|
| `baseline_ipl_v6_features` | 0.0-0.1 | 1527 | 0.048 | 0.134 | -0.086 |
| `baseline_ipl_v6_features` | 0.1-0.2 | 714 | 0.148 | 0.211 | -0.063 |
| `baseline_ipl_v6_features` | 0.2-0.3 | 636 | 0.248 | 0.325 | -0.077 |
| `baseline_ipl_v6_features` | 0.3-0.4 | 532 | 0.350 | 0.539 | -0.189 |
| `baseline_ipl_v6_features` | 0.4-0.5 | 549 | 0.453 | 0.587 | -0.133 |
| `baseline_ipl_v6_features` | 0.5-0.6 | 530 | 0.550 | 0.732 | -0.182 |
| `baseline_ipl_v6_features` | 0.6-0.7 | 491 | 0.648 | 0.688 | -0.041 |
| `baseline_ipl_v6_features` | 0.7-0.8 | 478 | 0.750 | 0.799 | -0.049 |
| `baseline_ipl_v6_features` | 0.8-0.9 | 681 | 0.852 | 0.843 | +0.009 |
| `baseline_ipl_v6_features` | 0.9-1.0 | 648 | 0.956 | 0.923 | +0.033 |
| `regime_cluster_features` | 0.0-0.1 | 1492 | 0.048 | 0.137 | -0.089 |
| `regime_cluster_features` | 0.1-0.2 | 700 | 0.149 | 0.209 | -0.059 |
| `regime_cluster_features` | 0.2-0.3 | 641 | 0.247 | 0.281 | -0.034 |
| `regime_cluster_features` | 0.3-0.4 | 551 | 0.351 | 0.577 | -0.226 |
| `regime_cluster_features` | 0.4-0.5 | 534 | 0.453 | 0.601 | -0.148 |
| `regime_cluster_features` | 0.5-0.6 | 564 | 0.549 | 0.693 | -0.144 |
| `regime_cluster_features` | 0.6-0.7 | 509 | 0.648 | 0.678 | -0.030 |
| `regime_cluster_features` | 0.7-0.8 | 491 | 0.751 | 0.792 | -0.041 |
| `regime_cluster_features` | 0.8-0.9 | 666 | 0.850 | 0.854 | -0.004 |
| `regime_cluster_features` | 0.9-1.0 | 638 | 0.956 | 0.920 | +0.036 |

## Overconfident Wrong Predictions

| Row | Season | Over.Ball | Batting | Regime | Pred | Actual | Direction |
|---|---|---|---|---:|---:|---:|---|
| `1473468:2:5:5` | 2025 | 5.5 | Kolkata Knight Riders | 1 | 0.986 | 0 | false_positive |
| `1473468:2:5:4` | 2025 | 5.4 | Kolkata Knight Riders | 3 | 0.985 | 0 | false_positive |
| `1359489:2:4:4` | 2023 | 4.4 | Lucknow Super Giants | 0 | 0.015 | 1 | false_negative |
| `1359489:2:4:5` | 2023 | 4.5 | Lucknow Super Giants | 0 | 0.016 | 1 | false_negative |
| `1359489:2:4:3` | 2023 | 4.3 | Lucknow Super Giants | 0 | 0.016 | 1 | false_negative |
| `1359489:2:5:5` | 2023 | 5.5 | Lucknow Super Giants | 0 | 0.017 | 1 | false_negative |
| `1359489:2:4:2` | 2023 | 4.2 | Lucknow Super Giants | 0 | 0.018 | 1 | false_negative |
| `1473441:2:2:2` | 2025 | 2.2 | Delhi Capitals | 0 | 0.018 | 1 | false_negative |
| `1359489:2:5:4` | 2023 | 5.4 | Lucknow Super Giants | 0 | 0.018 | 1 | false_negative |
| `1359489:2:4:1` | 2023 | 4.1 | Lucknow Super Giants | 0 | 0.019 | 1 | false_negative |

## Cluster Assignment Behaviour

| Regime | Label | Rows | PP Share | Win Rate | Mean Conf | Stability |
|---:|---|---:|---:|---:|---:|---|
| 0 | pressure_state | 2077 | 6.13% | 0.055 | 0.130 | stable |
| 1 | pressure_state | 487 | 1.44% | 0.943 | 0.118 | borderline |
| 3 | pressure_state | 28642 | 84.54% | 0.591 | 0.160 | stable |
| 4 | pressure_state | 2672 | 7.89% | 0.338 | 0.140 | borderline |

## 2025-2026 Stability Check

Some PP regimes are borderline/unstable in 2025-2026.

| Regime | Label | Rows | Recent Share | Stability Std | Flag |
|---:|---|---:|---:|---:|---|
| 0 | pressure_state | 310 | 11.49% | 0.081 | borderline |
| 1 | pressure_state | 82 | 3.04% | 0.037 | stable |
| 3 | pressure_state | 2207 | 81.83% | 0.059 | stable |
| 4 | pressure_state | 98 | 3.63% | 0.087 | borderline |
