# IPL Horseshoe Retrain Experiment

Mode: `holdout-2026`

## Metrics

| Method | Segment | N | Brier | Delta | LogLoss | Delta | Mean Pred | Actual |
|--------|---------|---|-------|-------|---------|-------|-----------|--------|
| augmented_all_candidates | innings_1 | 2844 | 0.21026 | -0.00051 | 0.61559 | -0.00109 | 0.5505 | 0.3843 |
| augmented_horseshoe_selected | innings_1 | 2844 | 0.21076 | -0.00001 | 0.61745 | +0.00077 | 0.5541 | 0.3843 |
| baseline_v6_features | innings_1 | 2844 | 0.21078 | +0.00000 | 0.61668 | +0.00000 | 0.5514 | 0.3843 |
| augmented_all_candidates | innings_1_death | 730 | 0.21713 | +0.00207 | 0.63151 | +0.00375 | 0.6296 | 0.3753 |
| augmented_horseshoe_selected | innings_1_death | 730 | 0.21504 | -0.00001 | 0.62908 | +0.00133 | 0.6361 | 0.3753 |
| baseline_v6_features | innings_1_death | 730 | 0.21506 | +0.00000 | 0.62776 | +0.00000 | 0.6336 | 0.3753 |
| augmented_all_candidates | innings_1_middle | 1269 | 0.20320 | -0.00211 | 0.60387 | -0.00401 | 0.5689 | 0.3877 |
| augmented_horseshoe_selected | innings_1_middle | 1269 | 0.20502 | -0.00029 | 0.60822 | +0.00035 | 0.5723 | 0.3877 |
| baseline_v6_features | innings_1_middle | 1269 | 0.20531 | +0.00000 | 0.60788 | +0.00000 | 0.5710 | 0.3877 |
| augmented_all_candidates | innings_1_powerplay | 845 | 0.21495 | -0.00034 | 0.61945 | -0.00088 | 0.4543 | 0.3870 |
| augmented_horseshoe_selected | innings_1_powerplay | 845 | 0.21569 | +0.00040 | 0.62126 | +0.00093 | 0.4559 | 0.3870 |
| baseline_v6_features | innings_1_powerplay | 845 | 0.21529 | +0.00000 | 0.62033 | +0.00000 | 0.4511 | 0.3870 |
| augmented_all_candidates | innings_2 | 2607 | 0.11327 | +0.00272 | 0.36754 | +0.00559 | 0.4668 | 0.5949 |
| augmented_horseshoe_selected | innings_2 | 2607 | 0.11101 | +0.00046 | 0.36364 | +0.00169 | 0.4725 | 0.5949 |
| baseline_v6_features | innings_2 | 2607 | 0.11056 | +0.00000 | 0.36195 | +0.00000 | 0.4740 | 0.5949 |
| augmented_all_candidates | innings_2_death | 512 | 0.07439 | -0.00097 | 0.26365 | -0.00679 | 0.4670 | 0.5273 |
| augmented_horseshoe_selected | innings_2_death | 512 | 0.07454 | -0.00081 | 0.26903 | -0.00142 | 0.4657 | 0.5273 |
| baseline_v6_features | innings_2_death | 512 | 0.07536 | +0.00000 | 0.27044 | +0.00000 | 0.4669 | 0.5273 |
| augmented_all_candidates | innings_2_middle | 1258 | 0.08373 | -0.00093 | 0.29551 | -0.00414 | 0.5046 | 0.6161 |
| augmented_horseshoe_selected | innings_2_middle | 1258 | 0.08537 | +0.00071 | 0.30138 | +0.00173 | 0.5040 | 0.6161 |
| baseline_v6_features | innings_2_middle | 1258 | 0.08466 | +0.00000 | 0.29965 | +0.00000 | 0.5058 | 0.6161 |
| augmented_all_candidates | innings_2_powerplay | 837 | 0.18147 | +0.01046 | 0.53936 | +0.02780 | 0.4098 | 0.6045 |
| augmented_horseshoe_selected | innings_2_powerplay | 837 | 0.17187 | +0.00086 | 0.51510 | +0.00353 | 0.4292 | 0.6045 |
| baseline_v6_features | innings_2_powerplay | 837 | 0.17101 | +0.00000 | 0.51157 | +0.00000 | 0.4305 | 0.6045 |
| augmented_all_candidates | overall | 5451 | 0.16388 | +0.00103 | 0.49696 | +0.00211 | 0.5104 | 0.4850 |
| augmented_horseshoe_selected | overall | 5451 | 0.16306 | +0.00021 | 0.49606 | +0.00121 | 0.5151 | 0.4850 |
| baseline_v6_features | overall | 5451 | 0.16284 | +0.00000 | 0.49485 | +0.00000 | 0.5144 | 0.4850 |

## Horseshoe Screen

| Feature | Keep | Selected | Effect | Z | Scope N |
|---------|------|----------|--------|---|---------|
| `hs_i2death_dls_x_chase_difficulty` | 0.073 | True | -1.7219 | 3.10 | 6220 |
| `hs_i1death_resource_pressure` | 0.024 | False | +0.2927 | 1.72 | 7929 |
| `hs_i1death_boundary_x_wih` | 0.013 | False | +0.1124 | 1.28 | 7929 |
| `hs_i2_target_above_par_x_wickets` | 0.005 | False | +0.1671 | 0.78 | 29036 |
| `hs_i1death_expected_final_x_wih` | 0.004 | False | +0.9361 | 0.71 | 7929 |
| `hs_i2_resource_pressure` | 0.003 | False | +1.2904 | 0.63 | 29036 |
| `hs_i1death_score_vs_par_x_wih` | 0.002 | False | +0.2808 | 0.53 | 7929 |
| `hs_i2mid_dls_x_resource` | 0.002 | False | -0.1341 | 0.48 | 13640 |
| `hs_i1death_projected_vs_venue_x_wih` | 0.002 | False | +0.2532 | 0.48 | 7929 |
| `hs_i2pp_target_above_par_x_venue_chase` | 0.001 | False | -0.3518 | 0.40 | 9176 |
| `hs_i2pp_target_x_early_wicket_shock` | 0.001 | False | +0.0665 | 0.39 | 9176 |
| `hs_i2pp_required_minus_current_rr` | 0.001 | False | -0.0390 | 0.37 | 9176 |
| `hs_i2death_target_x_venue_chase` | 0.001 | False | +0.4156 | 0.37 | 6220 |
| `hs_i2pp_early_chase_wicket_shock` | 0.001 | False | -0.0349 | 0.28 | 9176 |
| `hs_i1death_bowling_situation_x_wih` | 0.001 | False | -0.0887 | 0.27 | 7929 |
| `hs_i2pp_target_above_par_x_wickets` | 0.000 | False | +0.1123 | 0.23 | 9176 |
| `hs_i2_inn1_def_x_required_rr` | 0.000 | False | +0.4015 | 0.22 | 29036 |
| `hs_i2pp_inn1_def_x_batting_wr` | 0.000 | False | +0.0526 | 0.19 | 9176 |
| `hs_i1death_wickets_in_hand` | 0.000 | False | -0.0144 | 0.15 | 7929 |