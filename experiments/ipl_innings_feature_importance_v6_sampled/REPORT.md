# IPL Innings Feature Importance

This report separates current-model sensitivity from segment-specific learnability.

## Inputs

- Features: `data\ipl_features_v6\training_sampled.parquet`
- Model: `models\ipl_v6`
- Rows: 45,562
- Features analyzed: 32
- Permutation repeats: 2
- Sample per segment: 10,000

## Saved v6 Model: Permutation Importance

Higher Brier delta means the saved model depends more on that feature inside the segment.

### innings_1

`expected_final_score` (0.0127), `score_vs_par` (0.0084), `venue_chase_success` (0.0066), `situation_advantage` (0.0062), `team_strength_diff` (0.0060), `bowling_team_situation_wr` (0.0050), `batting_team_situation_wr` (0.0037), `batting_team_win_rate` (0.0034), `resource_win_prob` (0.0032), `projected_score` (0.0023)

### innings_2

`resource_win_prob` (0.0179), `target_above_par` (0.0178), `inn1_defendability` (0.0130), `expected_final_score` (0.0083), `inn1_pp_runs` (0.0080), `score_vs_par` (0.0078), `inn1_death_rr` (0.0075), `batting_team_situation_wr` (0.0062), `team_strength_diff` (0.0048), `venue_chase_success` (0.0045)

## Segment-Specific Models

These rankings show what the same model family learns when trained only on a segment.

### innings_1

`expected_final_score` (0.2321), `resource_win_prob` (0.1222), `score_vs_par` (0.0886), `venue_chase_success` (0.0494), `bowling_team_situation_wr` (0.0454), `situation_advantage` (0.0447), `bowling_team_win_rate` (0.0435), `batting_team_win_rate` (0.0429), `team_strength_diff` (0.0424), `projected_score` (0.0396)

### innings_2

`dls_pressure_index` (0.2986), `resource_win_prob` (0.2591), `score_vs_par` (0.0356), `required_run_rate` (0.0289), `is_powerplay` (0.0284), `score_per_wicket` (0.0223), `overs_remaining` (0.0187), `target_above_par` (0.0185), `inn1_defendability` (0.0179), `batting_won_toss` (0.0177)

## Carryover Feature Read

The v6 chase-prior features should be interpreted mainly through innings 2.

| Segment | Feature | Brier Delta |
|---------|---------|-------------|
| innings_1 | `venue_chase_success` | 0.00661 |
| innings_1 | `batting_won_toss` | 0.00201 |
| innings_1 | `inn1_defendability` | 0.00000 |
| innings_1 | `target_above_par` | 0.00000 |
| innings_1 | `inn1_wickets_lost` | 0.00000 |
| innings_1 | `inn1_death_rr` | 0.00000 |
| innings_1 | `inn1_pp_runs` | 0.00000 |
| innings_2 | `target_above_par` | 0.01783 |
| innings_2 | `inn1_defendability` | 0.01299 |
| innings_2 | `inn1_pp_runs` | 0.00804 |
| innings_2 | `inn1_death_rr` | 0.00753 |
| innings_2 | `venue_chase_success` | 0.00455 |
| innings_2 | `inn1_wickets_lost` | 0.00229 |
| innings_2 | `batting_won_toss` | 0.00155 |

## Artifacts

- `saved_model_permutation_importance.csv`
- `segment_model_feature_importance.csv`
- `single_feature_signal.csv`
- `segment_metrics.json`
