# IPL Horseshoe Retrain Experiment

Mode: `holdout-2026`

## Metrics

| Method | Segment | N | Brier | Delta | LogLoss | Delta | Mean Pred | Actual |
|--------|---------|---|-------|-------|---------|-------|-----------|--------|
| augmented_all_candidates | innings_1 | 2844 | 0.19108 | +0.00158 | 0.56789 | +0.00361 | 0.5223 | 0.3843 |
| augmented_horseshoe_selected | innings_1 | 2844 | 0.19027 | +0.00077 | 0.56606 | +0.00178 | 0.5202 | 0.3843 |
| baseline_v6_features | innings_1 | 2844 | 0.18950 | +0.00000 | 0.56428 | +0.00000 | 0.5186 | 0.3843 |
| augmented_all_candidates | innings_1_death | 730 | 0.18872 | +0.00180 | 0.56164 | +0.00377 | 0.5807 | 0.3753 |
| augmented_horseshoe_selected | innings_1_death | 730 | 0.18722 | +0.00029 | 0.55733 | -0.00055 | 0.5746 | 0.3753 |
| baseline_v6_features | innings_1_death | 730 | 0.18693 | +0.00000 | 0.55788 | +0.00000 | 0.5856 | 0.3753 |
| augmented_all_candidates | innings_1_middle | 1269 | 0.18629 | +0.00225 | 0.55807 | +0.00521 | 0.5387 | 0.3877 |
| augmented_horseshoe_selected | innings_1_middle | 1269 | 0.18580 | +0.00176 | 0.55750 | +0.00463 | 0.5384 | 0.3877 |
| baseline_v6_features | innings_1_middle | 1269 | 0.18404 | +0.00000 | 0.55286 | +0.00000 | 0.5319 | 0.3877 |
| augmented_all_candidates | innings_1_powerplay | 845 | 0.20032 | +0.00039 | 0.58803 | +0.00107 | 0.4474 | 0.3870 |
| augmented_horseshoe_selected | innings_1_powerplay | 845 | 0.19964 | -0.00029 | 0.58646 | -0.00050 | 0.4459 | 0.3870 |
| baseline_v6_features | innings_1_powerplay | 845 | 0.19993 | +0.00000 | 0.58696 | +0.00000 | 0.4407 | 0.3870 |
| augmented_all_candidates | innings_2 | 2607 | 0.09459 | -0.00016 | 0.31621 | -0.00221 | 0.5228 | 0.5949 |
| augmented_horseshoe_selected | innings_2 | 2607 | 0.09487 | +0.00012 | 0.31776 | -0.00066 | 0.5215 | 0.5949 |
| baseline_v6_features | innings_2 | 2607 | 0.09475 | +0.00000 | 0.31842 | +0.00000 | 0.5218 | 0.5949 |
| augmented_all_candidates | innings_2_death | 512 | 0.06170 | -0.00108 | 0.21790 | -0.00649 | 0.5026 | 0.5273 |
| augmented_horseshoe_selected | innings_2_death | 512 | 0.06335 | +0.00058 | 0.22327 | -0.00112 | 0.4988 | 0.5273 |
| baseline_v6_features | innings_2_death | 512 | 0.06278 | +0.00000 | 0.22439 | +0.00000 | 0.4913 | 0.5273 |
| augmented_all_candidates | innings_2_middle | 1258 | 0.07470 | -0.00073 | 0.26779 | -0.00295 | 0.5470 | 0.6161 |
| augmented_horseshoe_selected | innings_2_middle | 1258 | 0.07550 | +0.00007 | 0.26995 | -0.00079 | 0.5460 | 0.6161 |
| baseline_v6_features | innings_2_middle | 1258 | 0.07543 | +0.00000 | 0.27074 | +0.00000 | 0.5452 | 0.6161 |
| augmented_all_candidates | innings_2_powerplay | 837 | 0.14460 | +0.00127 | 0.44912 | +0.00152 | 0.4988 | 0.6045 |
| augmented_horseshoe_selected | innings_2_powerplay | 837 | 0.14326 | -0.00007 | 0.44741 | -0.00019 | 0.4987 | 0.6045 |
| baseline_v6_features | innings_2_powerplay | 837 | 0.14333 | +0.00000 | 0.44760 | +0.00000 | 0.5052 | 0.6045 |
| augmented_all_candidates | overall | 5451 | 0.14493 | +0.00075 | 0.44752 | +0.00083 | 0.5226 | 0.4850 |
| augmented_horseshoe_selected | overall | 5451 | 0.14464 | +0.00046 | 0.44731 | +0.00061 | 0.5208 | 0.4850 |
| baseline_v6_features | overall | 5451 | 0.14418 | +0.00000 | 0.44670 | +0.00000 | 0.5201 | 0.4850 |

## Horseshoe Screen

| Feature | Keep | Selected | Effect | Z | Scope N |
|---------|------|----------|--------|---|---------|
| `hs_i1death_score_vs_par_x_wih` | 0.176 | True | -0.4016 | 2.17 | 36497 |
| `hs_i2pp_inn1_def_x_batting_wr` | 0.124 | True | +0.2102 | 1.77 | 41516 |
| `hs_i1death_resource_pressure` | 0.111 | True | -0.2267 | 1.66 | 36497 |
| `hs_i1death_expected_final_x_wih` | 0.111 | True | -0.9671 | 1.66 | 36497 |
| `hs_i2pp_target_x_early_wicket_shock` | 0.099 | True | -0.1042 | 1.56 | 41516 |
| `hs_i1death_projected_vs_venue_x_wih` | 0.089 | True | -0.2849 | 1.47 | 36497 |
| `hs_i2pp_required_minus_current_rr` | 0.064 | True | -0.0478 | 1.23 | 41516 |
| `hs_i2death_dls_x_chase_difficulty` | 0.054 | True | -0.5878 | 1.13 | 28365 |
| `hs_i2_inn1_def_x_required_rr` | 0.043 | False | +0.6369 | 1.00 | 132007 |
| `hs_i2pp_target_above_par_x_wickets` | 0.039 | False | -0.2115 | 0.95 | 41516 |
| `hs_i1death_bowling_situation_x_wih` | 0.035 | False | -0.1085 | 0.89 | 36497 |
| `hs_i2mid_dls_x_resource` | 0.031 | False | -0.0901 | 0.85 | 62126 |
| `hs_i2pp_early_chase_wicket_shock` | 0.030 | False | -0.0366 | 0.83 | 41516 |
| `hs_i1death_boundary_x_wih` | 0.020 | False | +0.0239 | 0.67 | 36497 |
| `hs_i2_resource_pressure` | 0.019 | False | -0.7079 | 0.65 | 132007 |
| `hs_i2death_target_x_venue_chase` | 0.012 | False | +0.2021 | 0.53 | 28365 |
| `hs_i1death_wickets_in_hand` | 0.002 | False | +0.0124 | 0.23 | 36497 |
| `hs_i2_target_above_par_x_wickets` | 0.002 | False | -0.0279 | 0.21 | 132007 |
| `hs_i2pp_target_above_par_x_venue_chase` | 0.000 | False | +0.0171 | 0.08 | 41516 |