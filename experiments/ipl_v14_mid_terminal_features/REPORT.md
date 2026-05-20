# IPL v14 MID Terminal-Feature Experiment

Split: train seasons < 2025, test seasons >= 2025.

## Best Candidate

- Best overall calibrated Brier: `v14_baseline` = `0.11175`.

## Overall Metrics

| candidate | n | brier_raw | brier_cal | logloss_cal | gap_pp_cal |
| --- | --- | --- | --- | --- | --- |
| v14_baseline | 10047 | 0.10988 | 0.11175 | 0.37156 | -3.05904 |
| single_mid_terminal | 10047 | 0.11004 | 0.11192 | 0.37221 | -3.09169 |
| split_both_terminal | 10047 | 0.11102 | 0.11290 | 0.37468 | -3.03475 |
| split_late_terminal | 10047 | 0.11102 | 0.11294 | 0.37504 | -2.97390 |
| split_same_features | 10047 | 0.11133 | 0.11321 | 0.37570 | -2.92373 |

## MID Metrics

| candidate | phase | n | n_features | brier_raw | brier_cal | logloss_cal | gap_pp_cal |
| --- | --- | --- | --- | --- | --- | --- | --- |
| single_mid_terminal | mid | 5050 | 79.00000 | 0.10301 | 0.10403 | 0.33873 | -1.79145 |
| split_both_terminal | early_mid | 2856 | 79.00000 | 0.12033 | 0.12110 | 0.38965 | -4.06083 |
| split_both_terminal | late_mid | 2194 | 79.00000 | 0.08495 | 0.08629 | 0.28373 | 1.42340 |
| split_late_terminal | early_mid | 2856 | 72.00000 | 0.12031 | 0.12126 | 0.39093 | -3.84676 |
| split_late_terminal | late_mid | 2194 | 79.00000 | 0.08495 | 0.08629 | 0.28373 | 1.42340 |
| split_same_features | early_mid | 2856 | 72.00000 | 0.12031 | 0.12126 | 0.39093 | -3.84676 |
| split_same_features | late_mid | 2194 | 72.00000 | 0.08637 | 0.08753 | 0.28673 | 1.65314 |
| v14_baseline | mid | 5050 | 72.00000 | 0.10268 | 0.10370 | 0.33744 | -1.72650 |

## Terminal Feature EDA

| feature | in_current_mid | mean | std | corr_all_mid | corr_early_mid | corr_late_mid | abs_corr_late |
| --- | --- | --- | --- | --- | --- | --- | --- |
| required_rpb | False | 1.60229 | 0.62502 | -0.59092 | -0.56865 | -0.64679 | 0.64679 |
| death_chase_urgency | False | 1.30211 | 0.60759 | -0.55927 | -0.51873 | -0.61580 | 0.61580 |
| tight_finish_zone | False | 0.17515 | 0.38009 | 0.32444 |  | 0.59248 | 0.59248 |
| death_feasibility | False | 0.94563 | 0.71717 | 0.47193 | 0.46169 | 0.49235 | 0.49235 |
| runs_per_wkt_rem | False | 12.54587 | 9.69232 | -0.46246 | -0.49178 | -0.46450 | 0.46450 |
| balls_remaining | False | 50.77769 | 15.54413 | 0.01633 | 0.00306 | 0.01604 | 0.01604 |
| chase_completion | False | 0.00000 | 0.00000 |  |  |  |  |
