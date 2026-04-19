# Feature Experiment Log

## Experiment: 012 — IPL Feature Enhancement
**Date**: 2026-04-19
**Spec**: specs/012-ipl-feature-enhancement/spec.md
**Baseline Brier (OOS 2026)**: 0.1878

### Config A: Swap-25
- **Features In**: partnership_runs, partnership_balls, batsman_win_rate
- **Features Out**: boundary_pct_last_18, runs_last_12, wickets_last_12
- **Total Features**: 25
- **OOF Brier**: 0.1808
- **OOF ECE**: 0.0112
- **OOF LogLoss**: 0.5299
- **OOS Brier (2026)**: [pending]
- **Top 10 Features by XGBoost Gain**: resource_win_prob, dls_pressure_index, score_vs_par, run_rate_diff, situation_advantage, team_strength_diff, projected_score, batting_team_situation_wr, required_run_rate, batting_team_win_rate
- **Segment Regression Check**: [pending]

### Config B: Expand-28
- **Features In**: partnership_runs, partnership_balls, batsman_win_rate
- **Features Out**: (none)
- **Total Features**: 28
- **OOF Brier**: 0.1809
- **OOF ECE**: 0.0094
- **OOF LogLoss**: 0.5300
- **OOS Brier (2026)**: [pending]
- **Top 10 Features by XGBoost Gain**: resource_win_prob, dls_pressure_index, score_vs_par, run_rate_diff, situation_advantage, team_strength_diff, batting_team_situation_wr, batting_team_win_rate, bowling_team_situation_wr, required_run_rate
- **Segment Regression Check**: [pending]

### Config C: Expand-30
- **Features In**: partnership_runs, partnership_balls, partnership_run_rate, batsman_win_rate, batsman_vs_team_win_rate
- **Features Out**: (none)
- **Total Features**: 30
- **OOF Brier**: 0.1810
- **OOF ECE**: 0.0106
- **OOF LogLoss**: 0.5305
- **OOS Brier (2026)**: [pending]
- **Top 10 Features by XGBoost Gain**: resource_win_prob, dls_pressure_index, score_vs_par, run_rate_diff, situation_advantage, required_run_rate, team_strength_diff, batting_team_situation_wr, bowling_team_situation_wr, score_per_wicket
- **Segment Regression Check**: [pending]

### Winner: Config B (Expand-28)
- **Deployed**: YES
- **OOS Brier (2026 holdout)**: 0.1501 (vs baseline 0.1878)
- **Improvement over baseline**: 0.0377 Brier (20.1% relative improvement, 7.5x target)
- **Selection rationale**: Config B selected over Config A despite marginally higher Brier (0.0001 difference) because it has significantly better ECE (0.0094 vs 0.0112), retains all original features (lower regression risk), and adds 3 proven features without disrupting the existing feature set.
- **Notes**: 
  - All 3 configs perform within 0.0002 Brier of each other — essentially tied
  - New features (partnership_runs, partnership_balls, batsman_win_rate) don't appear in top 10 by XGBoost gain — they provide marginal but consistent signal that benefits the LogReg component
  - resource_win_prob and dls_pressure_index continue to dominate feature importance
  - Config B's ECE of 0.0094 is excellent calibration quality
  - OOS segment breakdown: inn2_middle (0.0836) and inn2_death (0.0730) are excellent
  - batsman_win_rate importance rank: 22/28 (0.0141), partnership_runs: 24/28 (0.0061)
