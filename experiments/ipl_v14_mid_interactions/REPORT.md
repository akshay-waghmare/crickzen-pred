# IPL v14 MID Interaction Experiment

Split: train seasons < 2025, test seasons >= 2025. This follow-up checks whether terminal chase signals need MID-specific interactions instead of being copied into the whole MID model.

## Decision

- Best full-MID calibrated Brier remains `baseline_mid` = `0.10370`.
- Terminal and interaction features are not safe as a broad MID replacement because they worsen full-MID Brier/log loss.
- The par 50-80 bucket remains the real weakness, so any model change should be a narrow specialist/correction instead of a router-wide MID feature expansion.

## Full MID Metrics

| candidate | n | n_features | brier_raw | brier_cal | logloss_cal | gap_pp |
| --- | --- | --- | --- | --- | --- | --- |
| baseline_mid | 5050 | 72 | 0.10268 | 0.10370 | 0.33744 | -1.72650 |
| terminal_mid | 5050 | 79 | 0.10301 | 0.10403 | 0.33873 | -1.79145 |
| terminal_interaction_mid | 5050 | 93 | 0.10361 | 0.10461 | 0.34001 | -2.03002 |
| interaction_mid | 5050 | 86 | 0.10423 | 0.10528 | 0.34138 | -2.05540 |

## Segment Metrics

| candidate | segment | n | brier_cal | logloss_cal | mean_pred | actual_wr | gap_pp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| terminal_mid | early_7_11 | 2856 | 0.12007 | 0.38660 | 0.51340 | 0.54622 | -3.28176 |
| baseline_mid | early_7_11 | 2856 | 0.12033 | 0.38615 | 0.51568 | 0.54622 | -3.05425 |
| terminal_interaction_mid | early_7_11 | 2856 | 0.12091 | 0.38833 | 0.51116 | 0.54622 | -3.50629 |
| interaction_mid | early_7_11 | 2856 | 0.12146 | 0.38934 | 0.51149 | 0.54622 | -3.47273 |
| baseline_mid | late_12_15 | 2194 | 0.08204 | 0.27402 | 0.52645 | 0.52644 | 0.00187 |
| terminal_mid | late_12_15 | 2194 | 0.08315 | 0.27641 | 0.52792 | 0.52644 | 0.14853 |
| terminal_interaction_mid | late_12_15 | 2194 | 0.08339 | 0.27711 | 0.52535 | 0.52644 | -0.10833 |
| interaction_mid | late_12_15 | 2194 | 0.08422 | 0.27895 | 0.52433 | 0.52644 | -0.21040 |
| interaction_mid | late_par_50_80 | 127 | 0.17997 | 0.54444 | 0.63739 | 0.77165 | -13.42635 |
| terminal_interaction_mid | late_par_50_80 | 133 | 0.18144 | 0.54879 | 0.62712 | 0.78195 | -15.48357 |
| terminal_mid | late_par_50_80 | 138 | 0.18188 | 0.54818 | 0.62985 | 0.77536 | -14.55112 |
| baseline_mid | late_par_50_80 | 148 | 0.18436 | 0.55360 | 0.62885 | 0.77703 | -14.81819 |
| terminal_interaction_mid | par_50_80 | 506 | 0.18721 | 0.56178 | 0.65810 | 0.77273 | -11.46276 |
| interaction_mid | par_50_80 | 485 | 0.18944 | 0.56633 | 0.66032 | 0.76082 | -10.05029 |
| terminal_mid | par_50_80 | 489 | 0.19069 | 0.56900 | 0.65760 | 0.76483 | -10.72311 |
| baseline_mid | par_50_80 | 498 | 0.19125 | 0.56970 | 0.65843 | 0.76305 | -10.46217 |

## Best Narrow Par Segments

| segment | candidate | n | brier_cal | logloss_cal | gap_pp |
| --- | --- | --- | --- | --- | --- |
| late_par_50_80 | interaction_mid | 127 | 0.17997 | 0.54444 | -13.42635 |
| par_50_80 | terminal_interaction_mid | 506 | 0.18721 | 0.56178 | -11.46276 |
