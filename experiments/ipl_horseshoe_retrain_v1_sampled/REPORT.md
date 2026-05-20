# IPL Horseshoe Retrain Experiment

Mode: `cv`

## Metrics

| Method | Segment | N | Brier | Delta | LogLoss | Delta | Mean Pred | Actual |
|--------|---------|---|-------|-------|---------|-------|-----------|--------|
| augmented_all_candidates | innings_1 | 17579 | 0.21761 | +0.00035 | 0.62300 | +0.00069 | 0.4482 | 0.4698 |
| augmented_horseshoe_selected | innings_1 | 17579 | 0.21723 | -0.00003 | 0.62221 | -0.00010 | 0.4484 | 0.4698 |
| baseline_v6_features | innings_1 | 17579 | 0.21726 | +0.00000 | 0.62231 | +0.00000 | 0.4497 | 0.4698 |
| augmented_all_candidates | innings_1_death | 5416 | 0.20378 | +0.00131 | 0.59212 | +0.00310 | 0.4577 | 0.4736 |
| augmented_horseshoe_selected | innings_1_death | 5416 | 0.20354 | +0.00107 | 0.59165 | +0.00263 | 0.4581 | 0.4736 |
| baseline_v6_features | innings_1_death | 5416 | 0.20247 | +0.00000 | 0.58902 | +0.00000 | 0.4663 | 0.4736 |
| augmented_all_candidates | innings_1_middle | 7813 | 0.21438 | -0.00013 | 0.61606 | -0.00055 | 0.4481 | 0.4682 |
| augmented_horseshoe_selected | innings_1_middle | 7813 | 0.21396 | -0.00055 | 0.61514 | -0.00147 | 0.4482 | 0.4682 |
| baseline_v6_features | innings_1_middle | 7813 | 0.21451 | +0.00000 | 0.61661 | +0.00000 | 0.4451 | 0.4682 |
| augmented_all_candidates | innings_1_powerplay | 4350 | 0.24063 | +0.00001 | 0.67392 | -0.00008 | 0.4364 | 0.4678 |
| augmented_horseshoe_selected | innings_1_powerplay | 4350 | 0.24016 | -0.00046 | 0.67295 | -0.00105 | 0.4365 | 0.4678 |
| baseline_v6_features | innings_1_powerplay | 4350 | 0.24062 | +0.00000 | 0.67400 | +0.00000 | 0.4371 | 0.4678 |
| augmented_all_candidates | innings_2 | 16593 | 0.13347 | -0.00117 | 0.41238 | -0.00299 | 0.5174 | 0.5130 |
| augmented_horseshoe_selected | innings_2 | 16593 | 0.13400 | -0.00064 | 0.41387 | -0.00150 | 0.5180 | 0.5130 |
| baseline_v6_features | innings_2 | 16593 | 0.13464 | +0.00000 | 0.41537 | +0.00000 | 0.5178 | 0.5130 |
| augmented_all_candidates | innings_2_death | 4508 | 0.07853 | -0.00220 | 0.26922 | -0.00680 | 0.4631 | 0.4718 |
| augmented_horseshoe_selected | innings_2_death | 4508 | 0.07967 | -0.00105 | 0.27284 | -0.00318 | 0.4624 | 0.4718 |
| baseline_v6_features | innings_2_death | 4508 | 0.08073 | +0.00000 | 0.27602 | +0.00000 | 0.4569 | 0.4718 |
| augmented_all_candidates | innings_2_middle | 7726 | 0.14044 | -0.00026 | 0.43043 | -0.00050 | 0.5280 | 0.5263 |
| augmented_horseshoe_selected | innings_2_middle | 7726 | 0.14103 | +0.00033 | 0.43195 | +0.00102 | 0.5297 | 0.5263 |
| baseline_v6_features | innings_2_middle | 7726 | 0.14070 | +0.00000 | 0.43093 | +0.00000 | 0.5289 | 0.5263 |
| augmented_all_candidates | innings_2_powerplay | 4359 | 0.17793 | -0.00171 | 0.52842 | -0.00347 | 0.5548 | 0.5320 |
| augmented_horseshoe_selected | innings_2_powerplay | 4359 | 0.17771 | -0.00193 | 0.52766 | -0.00423 | 0.5547 | 0.5320 |
| baseline_v6_features | innings_2_powerplay | 4359 | 0.17964 | +0.00000 | 0.53189 | +0.00000 | 0.5611 | 0.5320 |
| augmented_all_candidates | overall | 34172 | 0.17675 | -0.00039 | 0.52073 | -0.00110 | 0.4818 | 0.4908 |
| augmented_horseshoe_selected | overall | 34172 | 0.17682 | -0.00032 | 0.52104 | -0.00078 | 0.4822 | 0.4908 |
| baseline_v6_features | overall | 34172 | 0.17714 | +0.00000 | 0.52182 | +0.00000 | 0.4827 | 0.4908 |

## Horseshoe Screen

| Feature | Mean Keep | Selected Rate | Mean Effect | Mean Z |
|---------|-----------|---------------|-------------|--------|
| `hs_i2_target_above_par_x_wickets` | 0.787 | 1.00 | -0.3220 | 5.21 |
| `hs_i2pp_inn1_def_x_batting_wr` | 0.722 | 1.00 | +0.3636 | 4.76 |
| `hs_i1death_bowling_situation_x_wih` | 0.597 | 1.00 | -0.2069 | 3.34 |
| `hs_i2pp_target_above_par_x_wickets` | 0.554 | 1.00 | -0.3773 | 2.98 |
| `hs_i1death_expected_final_x_wih` | 0.522 | 1.00 | -0.7778 | 2.89 |
| `hs_i1death_projected_vs_venue_x_wih` | 0.479 | 1.00 | -0.2473 | 2.49 |
| `hs_i1death_resource_pressure` | 0.471 | 1.00 | -0.2586 | 2.48 |
| `hs_i2pp_target_x_early_wicket_shock` | 0.394 | 1.00 | -0.1808 | 2.18 |
| `hs_i2_resource_pressure` | 0.297 | 1.00 | -0.2524 | 1.53 |
| `hs_i2pp_early_chase_wicket_shock` | 0.233 | 1.00 | -0.1393 | 1.41 |
| `hs_i2pp_target_above_par_x_venue_chase` | 0.195 | 1.00 | -0.0415 | 1.36 |
| `hs_i1death_score_vs_par_x_wih` | 0.525 | 0.67 | -0.3438 | 2.95 |
| `hs_i2mid_dls_x_resource` | 0.250 | 0.67 | -0.0500 | 1.32 |
| `hs_i2death_target_x_venue_chase` | 0.221 | 0.67 | -0.1108 | 1.37 |
| `hs_i1death_wickets_in_hand` | 0.082 | 0.67 | +0.0157 | 0.56 |
| `hs_i2_inn1_def_x_required_rr` | 0.268 | 0.33 | -0.1780 | 1.81 |
| `hs_i2death_dls_x_chase_difficulty` | 0.120 | 0.33 | -0.1098 | 0.64 |
| `hs_i2pp_required_minus_current_rr` | 0.102 | 0.33 | -0.0482 | 0.55 |
| `hs_i1death_boundary_x_wih` | 0.025 | 0.00 | -0.0052 | 0.37 |