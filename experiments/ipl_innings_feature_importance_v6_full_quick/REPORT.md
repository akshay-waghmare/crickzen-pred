# IPL Innings Feature Importance

This report separates current-model sensitivity from segment-specific learnability.

## Inputs

- Features: `data\ipl_features_v6\training.parquet`
- Model: `models\ipl_v6`
- Rows: 278,954
- Features analyzed: 32
- Permutation repeats: 1
- Sample per segment: 8,000

## Saved v6 Model: Permutation Importance

Higher Brier delta means the saved model depends more on that feature inside the segment.

### innings_1

`expected_final_score` (0.0136), `score_vs_par` (0.0095), `situation_advantage` (0.0072), `venue_chase_success` (0.0062), `team_strength_diff` (0.0052), `bowling_team_situation_wr` (0.0048), `batting_team_situation_wr` (0.0038), `resource_win_prob` (0.0036), `batting_team_win_rate` (0.0032), `projected_score` (0.0024)

### innings_2

`target_above_par` (0.0172), `inn1_defendability` (0.0129), `resource_win_prob` (0.0128), `inn1_death_rr` (0.0088), `inn1_pp_runs` (0.0083), `score_vs_par` (0.0076), `expected_final_score` (0.0074), `batting_team_situation_wr` (0.0064), `team_strength_diff` (0.0053), `venue_chase_success` (0.0051)

## Segment-Specific Models

These rankings show what the same model family learns when trained only on a segment.

_Skipped._

## Carryover Feature Read

The v6 chase-prior features should be interpreted mainly through innings 2.

| Segment | Feature | Brier Delta |
|---------|---------|-------------|
| innings_1 | `venue_chase_success` | 0.00623 |
| innings_1 | `batting_won_toss` | 0.00196 |
| innings_1 | `inn1_defendability` | 0.00000 |
| innings_1 | `target_above_par` | 0.00000 |
| innings_1 | `inn1_wickets_lost` | 0.00000 |
| innings_1 | `inn1_death_rr` | 0.00000 |
| innings_1 | `inn1_pp_runs` | 0.00000 |
| innings_2 | `target_above_par` | 0.01717 |
| innings_2 | `inn1_defendability` | 0.01292 |
| innings_2 | `inn1_death_rr` | 0.00876 |
| innings_2 | `inn1_pp_runs` | 0.00829 |
| innings_2 | `venue_chase_success` | 0.00513 |
| innings_2 | `inn1_wickets_lost` | 0.00265 |
| innings_2 | `batting_won_toss` | 0.00145 |

## Artifacts

- `saved_model_permutation_importance.csv`
- `segment_model_feature_importance.csv`
- `single_feature_signal.csv`
- `segment_metrics.json`
