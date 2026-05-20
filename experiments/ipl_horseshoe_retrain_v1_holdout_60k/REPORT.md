# IPL Horseshoe Retrain Experiment

Mode: `holdout-2026`

## Metrics

| Method | Segment | N | Brier | Delta | LogLoss | Delta | Mean Pred | Actual |
|--------|---------|---|-------|-------|---------|-------|-----------|--------|
| augmented_all_candidates | innings_1 | 2844 | 0.21026 | -0.00051 | 0.61559 | -0.00109 | 0.5505 | 0.3843 |
| augmented_horseshoe_selected | innings_1 | 2844 | 0.21078 | +0.00000 | 0.61668 | +0.00000 | 0.5514 | 0.3843 |
| baseline_v6_features | innings_1 | 2844 | 0.21078 | +0.00000 | 0.61668 | +0.00000 | 0.5514 | 0.3843 |
| augmented_all_candidates | innings_1_death | 730 | 0.21713 | +0.00207 | 0.63151 | +0.00375 | 0.6296 | 0.3753 |
| augmented_horseshoe_selected | innings_1_death | 730 | 0.21506 | +0.00000 | 0.62776 | +0.00000 | 0.6336 | 0.3753 |
| baseline_v6_features | innings_1_death | 730 | 0.21506 | +0.00000 | 0.62776 | +0.00000 | 0.6336 | 0.3753 |
| augmented_all_candidates | innings_1_middle | 1269 | 0.20320 | -0.00211 | 0.60387 | -0.00401 | 0.5689 | 0.3877 |
| augmented_horseshoe_selected | innings_1_middle | 1269 | 0.20531 | +0.00000 | 0.60788 | +0.00000 | 0.5710 | 0.3877 |
| baseline_v6_features | innings_1_middle | 1269 | 0.20531 | +0.00000 | 0.60788 | +0.00000 | 0.5710 | 0.3877 |
| augmented_all_candidates | innings_1_powerplay | 845 | 0.21495 | -0.00034 | 0.61945 | -0.00088 | 0.4543 | 0.3870 |
| augmented_horseshoe_selected | innings_1_powerplay | 845 | 0.21529 | +0.00000 | 0.62033 | +0.00000 | 0.4511 | 0.3870 |
| baseline_v6_features | innings_1_powerplay | 845 | 0.21529 | +0.00000 | 0.62033 | +0.00000 | 0.4511 | 0.3870 |
| augmented_all_candidates | innings_2 | 2607 | 0.11327 | +0.00272 | 0.36754 | +0.00559 | 0.4668 | 0.5949 |
| augmented_horseshoe_selected | innings_2 | 2607 | 0.11056 | +0.00000 | 0.36195 | +0.00000 | 0.4740 | 0.5949 |
| baseline_v6_features | innings_2 | 2607 | 0.11056 | +0.00000 | 0.36195 | +0.00000 | 0.4740 | 0.5949 |
| augmented_all_candidates | innings_2_death | 512 | 0.07439 | -0.00097 | 0.26365 | -0.00679 | 0.4670 | 0.5273 |
| augmented_horseshoe_selected | innings_2_death | 512 | 0.07536 | +0.00000 | 0.27044 | +0.00000 | 0.4669 | 0.5273 |
| baseline_v6_features | innings_2_death | 512 | 0.07536 | +0.00000 | 0.27044 | +0.00000 | 0.4669 | 0.5273 |
| augmented_all_candidates | innings_2_middle | 1258 | 0.08373 | -0.00093 | 0.29551 | -0.00414 | 0.5046 | 0.6161 |
| augmented_horseshoe_selected | innings_2_middle | 1258 | 0.08466 | +0.00000 | 0.29965 | +0.00000 | 0.5058 | 0.6161 |
| baseline_v6_features | innings_2_middle | 1258 | 0.08466 | +0.00000 | 0.29965 | +0.00000 | 0.5058 | 0.6161 |
| augmented_all_candidates | innings_2_powerplay | 837 | 0.18147 | +0.01046 | 0.53936 | +0.02780 | 0.4098 | 0.6045 |
| augmented_horseshoe_selected | innings_2_powerplay | 837 | 0.17101 | +0.00000 | 0.51157 | +0.00000 | 0.4305 | 0.6045 |
| baseline_v6_features | innings_2_powerplay | 837 | 0.17101 | +0.00000 | 0.51157 | +0.00000 | 0.4305 | 0.6045 |
| augmented_all_candidates | overall | 5451 | 0.16388 | +0.00103 | 0.49696 | +0.00211 | 0.5104 | 0.4850 |
| augmented_horseshoe_selected | overall | 5451 | 0.16284 | +0.00000 | 0.49485 | +0.00000 | 0.5144 | 0.4850 |
| baseline_v6_features | overall | 5451 | 0.16284 | +0.00000 | 0.49485 | +0.00000 | 0.5144 | 0.4850 |

## Horseshoe Screen

_No candidates screened._