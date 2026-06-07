# Innings 2 Powerplay Diagnostics

- Focus variant: `regime_cluster_features`
- Holdout PP rows exported: 4,680
- Focus-variant PP rows: 936
- Overconfident wrong predictions: 64
- Recent PP rows (2025-2026): 372

## PP Reliability Bins

| Variant | Bin | N | Mean Pred | Mean Actual | Gap |
|---|---|---:|---:|---:|---:|
| `baseline_ipl_v6_features` | 0.0-0.1 | 205 | 0.050 | 0.127 | -0.077 |
| `baseline_ipl_v6_features` | 0.1-0.2 | 84 | 0.145 | 0.202 | -0.057 |
| `baseline_ipl_v6_features` | 0.2-0.3 | 97 | 0.246 | 0.289 | -0.042 |
| `baseline_ipl_v6_features` | 0.3-0.4 | 73 | 0.345 | 0.507 | -0.162 |
| `baseline_ipl_v6_features` | 0.4-0.5 | 70 | 0.452 | 0.643 | -0.191 |
| `baseline_ipl_v6_features` | 0.5-0.6 | 88 | 0.546 | 0.727 | -0.181 |
| `baseline_ipl_v6_features` | 0.6-0.7 | 69 | 0.652 | 0.667 | -0.015 |
| `baseline_ipl_v6_features` | 0.7-0.8 | 61 | 0.749 | 0.770 | -0.021 |
| `baseline_ipl_v6_features` | 0.8-0.9 | 89 | 0.851 | 0.820 | +0.031 |
| `baseline_ipl_v6_features` | 0.9-1.0 | 100 | 0.950 | 0.930 | +0.020 |
| `regime_cluster_features` | 0.0-0.1 | 205 | 0.051 | 0.127 | -0.076 |
| `regime_cluster_features` | 0.1-0.2 | 83 | 0.146 | 0.205 | -0.059 |
| `regime_cluster_features` | 0.2-0.3 | 90 | 0.246 | 0.267 | -0.021 |
| `regime_cluster_features` | 0.3-0.4 | 80 | 0.342 | 0.525 | -0.183 |
| `regime_cluster_features` | 0.4-0.5 | 82 | 0.452 | 0.598 | -0.146 |
| `regime_cluster_features` | 0.5-0.6 | 78 | 0.546 | 0.756 | -0.210 |
| `regime_cluster_features` | 0.6-0.7 | 68 | 0.647 | 0.676 | -0.029 |
| `regime_cluster_features` | 0.7-0.8 | 66 | 0.751 | 0.758 | -0.007 |
| `regime_cluster_features` | 0.8-0.9 | 87 | 0.848 | 0.839 | +0.009 |
| `regime_cluster_features` | 0.9-1.0 | 97 | 0.950 | 0.928 | +0.022 |
| `v18A_hard_pp_fallback` | 0.0-0.1 | 205 | 0.050 | 0.127 | -0.077 |
| `v18A_hard_pp_fallback` | 0.1-0.2 | 84 | 0.145 | 0.202 | -0.057 |
| `v18A_hard_pp_fallback` | 0.2-0.3 | 97 | 0.246 | 0.289 | -0.042 |
| `v18A_hard_pp_fallback` | 0.3-0.4 | 73 | 0.345 | 0.507 | -0.162 |
| `v18A_hard_pp_fallback` | 0.4-0.5 | 70 | 0.452 | 0.643 | -0.191 |
| `v18A_hard_pp_fallback` | 0.5-0.6 | 88 | 0.546 | 0.727 | -0.181 |
| `v18A_hard_pp_fallback` | 0.6-0.7 | 69 | 0.652 | 0.667 | -0.015 |
| `v18A_hard_pp_fallback` | 0.7-0.8 | 61 | 0.749 | 0.770 | -0.021 |
| `v18A_hard_pp_fallback` | 0.8-0.9 | 89 | 0.851 | 0.820 | +0.031 |
| `v18A_hard_pp_fallback` | 0.9-1.0 | 100 | 0.950 | 0.930 | +0.020 |
| `v18B_confidence_cap` | 0.0-0.1 | 205 | 0.051 | 0.127 | -0.076 |
| `v18B_confidence_cap` | 0.1-0.2 | 83 | 0.146 | 0.205 | -0.059 |
| `v18B_confidence_cap` | 0.2-0.3 | 92 | 0.247 | 0.272 | -0.025 |
| `v18B_confidence_cap` | 0.3-0.4 | 78 | 0.343 | 0.526 | -0.183 |
| `v18B_confidence_cap` | 0.4-0.5 | 81 | 0.451 | 0.605 | -0.153 |
| `v18B_confidence_cap` | 0.5-0.6 | 80 | 0.546 | 0.750 | -0.204 |
| `v18B_confidence_cap` | 0.6-0.7 | 67 | 0.648 | 0.672 | -0.024 |
| `v18B_confidence_cap` | 0.7-0.8 | 66 | 0.751 | 0.758 | -0.007 |
| `v18B_confidence_cap` | 0.8-0.9 | 87 | 0.848 | 0.839 | +0.009 |
| `v18B_confidence_cap` | 0.9-1.0 | 97 | 0.950 | 0.928 | +0.022 |
| `v18C_dominant_cluster_only` | 0.0-0.1 | 205 | 0.050 | 0.127 | -0.077 |
| `v18C_dominant_cluster_only` | 0.1-0.2 | 84 | 0.145 | 0.202 | -0.057 |
| `v18C_dominant_cluster_only` | 0.2-0.3 | 97 | 0.246 | 0.289 | -0.042 |
| `v18C_dominant_cluster_only` | 0.3-0.4 | 73 | 0.345 | 0.507 | -0.162 |
| `v18C_dominant_cluster_only` | 0.4-0.5 | 70 | 0.452 | 0.643 | -0.191 |
| `v18C_dominant_cluster_only` | 0.5-0.6 | 88 | 0.546 | 0.727 | -0.181 |
| `v18C_dominant_cluster_only` | 0.6-0.7 | 69 | 0.652 | 0.667 | -0.015 |
| `v18C_dominant_cluster_only` | 0.7-0.8 | 61 | 0.749 | 0.770 | -0.021 |
| `v18C_dominant_cluster_only` | 0.8-0.9 | 89 | 0.851 | 0.820 | +0.031 |
| `v18C_dominant_cluster_only` | 0.9-1.0 | 100 | 0.950 | 0.930 | +0.020 |

## Overconfident Wrong Predictions

| Row | Season | Over.Ball | Batting | Regime | Pred | Actual | Direction |
|---|---|---|---|---:|---:|---:|---|
| `1359489:2:4:6` | 2023 | 4.6 | Lucknow Super Giants | 5 | 0.026 | 1 | false_negative |
| `1473441:2:1:6` | 2025 | 1.6 | Delhi Capitals | 3 | 0.032 | 1 | false_negative |
| `1426277:2:4:6` | 2024 | 4.6 | Lucknow Super Giants | 5 | 0.034 | 1 | false_negative |
| `1473441:2:2:6` | 2025 | 2.6 | Delhi Capitals | 3 | 0.039 | 1 | false_negative |
| `1426277:2:1:6` | 2024 | 1.6 | Lucknow Super Giants | 1 | 0.042 | 1 | false_negative |
| `1359489:2:3:6` | 2023 | 3.6 | Lucknow Super Giants | 5 | 0.050 | 1 | false_negative |
| `1473468:2:4:6` | 2025 | 4.6 | Kolkata Knight Riders | 4 | 0.949 | 0 | false_positive |
| `1359504:2:4:6` | 2023 | 4.6 | Lucknow Super Giants | 1 | 0.946 | 0 | false_positive |
| `1426277:2:2:6` | 2024 | 2.6 | Lucknow Super Giants | 1 | 0.056 | 1 | false_negative |
| `1426277:2:3:6` | 2024 | 3.6 | Lucknow Super Giants | 1 | 0.060 | 1 | false_negative |

## Cluster Assignment Behaviour

| Regime | Label | Rows | PP Share | Win Rate | Mean Conf | Stability |
|---:|---|---:|---:|---:|---:|---|
| 1 | pressure_state | 3317 | 70.89% | 0.526 | 0.160 | borderline |
| 2 | pressure_state | 6 | 0.13% | 1.000 | 0.095 | unstable |
| 3 | pressure_state | 363 | 7.76% | 0.209 | 0.138 | borderline |
| 4 | pressure_state | 870 | 18.59% | 0.817 | 0.152 | borderline |
| 5 | pressure_state | 123 | 2.63% | 0.041 | 0.120 | stable |

## 2025-2026 Stability Check

Some PP regimes are borderline/unstable in 2025-2026.

| Regime | Label | Rows | Recent Share | Stability Std | Flag |
|---:|---|---:|---:|---:|---|
| 1 | pressure_state | 278 | 74.73% | 0.060 | stable |
| 2 | pressure_state | 2 | 0.54% | 0.000 | unstable |
| 3 | pressure_state | 26 | 6.99% | 0.094 | unstable |
| 4 | pressure_state | 45 | 12.10% | 0.094 | unstable |
| 5 | pressure_state | 21 | 5.65% | 0.000 | unstable |
