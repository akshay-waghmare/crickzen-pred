# IPL Segment Candidate Feature Experiment

Sequential OOF comparison of baseline v6 features vs derived segment candidates.

## Metrics

| Segment | Variant | N | Brier | Delta | LogLoss | ECE | Mean Pred | Actual |
|---------|---------|---|-------|-------|---------|-----|-----------|--------|
| innings_1_death | augmented | 5734 | 0.20323 | -0.00051 | 0.59094 | 0.02612 | 0.4606 | 0.4641 |
| innings_1_death | baseline | 5734 | 0.20373 | +0.00000 | 0.59223 | 0.02662 | 0.4615 | 0.4641 |
| innings_2_powerplay | augmented | 4680 | 0.17821 | +0.00069 | 0.53105 | 0.01514 | 0.5416 | 0.5404 |
| innings_2_powerplay | baseline | 4680 | 0.17752 | +0.00000 | 0.52855 | 0.01046 | 0.5391 | 0.5404 |

## Top Candidate Importances

### innings_2_powerplay

- `cand_target_above_par_x_wickets`: 0.03942
- `cand_required_minus_current_rr`: 0.02447
- `cand_target_x_early_wicket_shock`: 0.02347
- `cand_inn1_def_x_batting_wr`: 0.02224
- `cand_target_above_par_x_venue_chase`: 0.02029
- `cand_early_chase_wicket_shock`: 0.01670

### innings_1_death

- `cand_expected_final_x_wickets_in_hand`: 0.02876
- `cand_bowling_situation_x_wickets_in_hand`: 0.02633
- `cand_projected_vs_venue_x_wickets_in_hand`: 0.02544
- `cand_boundary_x_wickets_in_hand`: 0.02163
- `cand_score_vs_par_x_wickets_in_hand`: 0.02043
- `cand_death_resource_pressure`: 0.01648
- `cand_wickets_in_hand`: 0.01376
