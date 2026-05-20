# IPL Innings Feature Importance

This report separates current-model sensitivity from segment-specific learnability.

## Inputs

- Features: `data\ipl_features_v6\training.parquet`
- Model: `models\ipl_v6`
- Rows: 278,954
- Features analyzed: 32
- Permutation repeats: 3
- Sample per segment: 30,000

## Saved v6 Model: Permutation Importance

Higher Brier delta means the saved model depends more on that feature inside the segment.

### innings_1

`expected_final_score` (0.0116), `score_vs_par` (0.0090), `venue_chase_success` (0.0064), `situation_advantage` (0.0061), `team_strength_diff` (0.0057), `bowling_team_situation_wr` (0.0047), `batting_team_situation_wr` (0.0037), `resource_win_prob` (0.0035), `batting_team_win_rate` (0.0033), `bowling_team_win_rate` (0.0021)

### innings_2

`target_above_par` (0.0172), `resource_win_prob` (0.0142), `inn1_defendability` (0.0130), `score_vs_par` (0.0084), `inn1_death_rr` (0.0080), `inn1_pp_runs` (0.0079), `expected_final_score` (0.0076), `batting_team_situation_wr` (0.0065), `chase_difficulty` (0.0056), `team_strength_diff` (0.0052)

## Segment-Specific Models

These rankings show what the same model family learns when trained only on a segment.

### innings_1

`expected_final_score` (0.1841), `resource_win_prob` (0.1710), `score_vs_par` (0.0924), `venue_chase_success` (0.0548), `situation_advantage` (0.0495), `batting_team_win_rate` (0.0482), `bowling_team_situation_wr` (0.0479), `bowling_team_win_rate` (0.0462), `batting_won_toss` (0.0452), `team_strength_diff` (0.0451)

### innings_2

`resource_win_prob` (0.3081), `dls_pressure_index` (0.2125), `score_vs_par` (0.0538), `required_run_rate` (0.0446), `score_per_wicket` (0.0259), `run_rate_diff` (0.0228), `venue_chase_success` (0.0210), `target_above_par` (0.0207), `is_powerplay` (0.0204), `inn1_defendability` (0.0199)

## Carryover Feature Read

The v6 chase-prior features should be interpreted mainly through innings 2.

| Segment | Feature | Brier Delta |
|---------|---------|-------------|
| innings_1 | `venue_chase_success` | 0.00640 |
| innings_1 | `batting_won_toss` | 0.00208 |
| innings_1 | `inn1_defendability` | 0.00000 |
| innings_1 | `target_above_par` | 0.00000 |
| innings_1 | `inn1_wickets_lost` | 0.00000 |
| innings_1 | `inn1_death_rr` | 0.00000 |
| innings_1 | `inn1_pp_runs` | 0.00000 |
| innings_2 | `target_above_par` | 0.01719 |
| innings_2 | `inn1_defendability` | 0.01303 |
| innings_2 | `inn1_death_rr` | 0.00797 |
| innings_2 | `inn1_pp_runs` | 0.00787 |
| innings_2 | `venue_chase_success` | 0.00497 |
| innings_2 | `inn1_wickets_lost` | 0.00253 |
| innings_2 | `batting_won_toss` | 0.00164 |

## Artifacts

- `saved_model_permutation_importance.csv`
- `segment_model_feature_importance.csv`
- `single_feature_signal.csv`
- `segment_metrics.json`
