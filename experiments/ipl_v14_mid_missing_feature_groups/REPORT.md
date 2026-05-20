# IPL v14 MID Missing Feature Groups

Split: train seasons < 2025, test seasons >= 2025.

## Decision

- Best full-MID calibrated Brier: `baseline_mid` = `0.10370`.
- This tests the actual v14 DEATH-not-MID gap and the important v7 features missing from v14 MID.

## Full MID Metrics

| candidate | n | n_features | brier_raw | brier_cal | logloss_cal | mean_pred | actual_wr | gap_pp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_mid | 5050 | 72 | 0.10268 | 0.10370 | 0.33744 | 0.52036 | 0.53762 | -1.72650 |
| death_gap_mid | 5050 | 84 | 0.10311 | 0.10425 | 0.34040 | 0.51606 | 0.53762 | -2.15640 |
| death_plus_v7_gap_mid | 5050 | 92 | 0.10278 | 0.10428 | 0.34211 | 0.51978 | 0.53762 | -1.78400 |
| v7_gap_mid | 5050 | 80 | 0.10398 | 0.10506 | 0.34222 | 0.52155 | 0.53762 | -1.60723 |

## Segment Metrics

| candidate | segment | n | brier_cal | logloss_cal | mean_pred | actual_wr | gap_pp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| death_plus_v7_gap_mid | early_7_11 | 2856 | 0.11984 | 0.38978 | 0.51084 | 0.54622 | -3.53788 |
| baseline_mid | early_7_11 | 2856 | 0.12033 | 0.38615 | 0.51568 | 0.54622 | -3.05425 |
| death_gap_mid | early_7_11 | 2856 | 0.12046 | 0.38972 | 0.51031 | 0.54622 | -3.59083 |
| v7_gap_mid | early_7_11 | 2856 | 0.12079 | 0.38911 | 0.51428 | 0.54622 | -3.19357 |
| baseline_mid | late_12_15 | 2194 | 0.08204 | 0.27402 | 0.52645 | 0.52644 | 0.00187 |
| death_gap_mid | late_12_15 | 2194 | 0.08316 | 0.27619 | 0.52354 | 0.52644 | -0.28916 |
| death_plus_v7_gap_mid | late_12_15 | 2194 | 0.08403 | 0.28006 | 0.53143 | 0.52644 | 0.49908 |
| v7_gap_mid | late_12_15 | 2194 | 0.08459 | 0.28120 | 0.53101 | 0.52644 | 0.45776 |
| death_gap_mid | late_par_50_80 | 141 | 0.16318 | 0.50781 | 0.64615 | 0.82270 | -17.65449 |
| death_plus_v7_gap_mid | late_par_50_80 | 148 | 0.16669 | 0.51434 | 0.63801 | 0.79730 | -15.92831 |
| baseline_mid | late_par_50_80 | 148 | 0.18436 | 0.55360 | 0.62885 | 0.77703 | -14.81819 |
| v7_gap_mid | late_par_50_80 | 164 | 0.19209 | 0.57027 | 0.63244 | 0.76220 | -12.97528 |
| death_plus_v7_gap_mid | par_50_80 | 530 | 0.18133 | 0.54784 | 0.65985 | 0.78302 | -12.31672 |
| death_gap_mid | par_50_80 | 508 | 0.18463 | 0.55553 | 0.66137 | 0.77756 | -11.61859 |
| baseline_mid | par_50_80 | 498 | 0.19125 | 0.56970 | 0.65843 | 0.76305 | -10.46217 |
| v7_gap_mid | par_50_80 | 498 | 0.20031 | 0.58926 | 0.65120 | 0.75301 | -10.18079 |

## Added Feature Groups

| candidate | added_count | added_features |
| --- | --- | --- |
| death_gap_mid | 12 | required_rpb, death_chase_urgency, death_feasibility, wickets_lost, runs_per_wkt_rem, balls_remaining, resources_remaining, chase_completion, tight_finish_zone, inn1_pp_wickets, mid_avg_boundary18_vs_venue, avg_boundary18_vs_venue |
| v7_gap_mid | 8 | expected_final_score, projected_vs_venue_avg, projected_score, team_strength_diff, bowling_team_win_rate, bowling_team_situation_wr, inn1_wickets_lost, batting_won_toss |
| death_plus_v7_gap_mid | 20 | required_rpb, death_chase_urgency, death_feasibility, wickets_lost, runs_per_wkt_rem, balls_remaining, resources_remaining, chase_completion, tight_finish_zone, inn1_pp_wickets, mid_avg_boundary18_vs_venue, avg_boundary18_vs_venue, expected_final_score, projected_vs_venue_avg, projected_score, team_strength_diff, bowling_team_win_rate, bowling_team_situation_wr, inn1_wickets_lost, batting_won_toss |
