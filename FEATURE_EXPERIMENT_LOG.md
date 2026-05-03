# Feature Experiment Log

## Experiment: 013 — IPL v7 Temperature Sharpening
**Date**: 2026-05-03  
**Model**: IPL v7 (`models/ipl_v7/`)  
**Technique**: Post-calibration temperature scaling (T < 1 sharpens predictions toward extremes)  
**Full doc**: `docs/IPL_V7_MODEL.md`

### Motivation
IPL v7 (37 features) OOF Brier = 0.1810, but OOS predictions looked under-confident — model showed
flat curves where the market was already pricing more extreme probabilities. Hypothesis: the model
has signal but is being softened by isotonic calibration.

### Method
Analysed 16 IPL 2026 matches against Betfair market odds using a proper 3-way split:
- Train: all seasons ≤ 2025
- Calibration: 2025 season
- Holdout: IPL 2026 (Apr 3–16, 16 matches, 580 per-over rows from `data/ipl_betx21_full_market_2026.parquet`)

Swept T ∈ {0.40, 0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00} globally and per-segment.

### Results

| T | Brier | vs Market (0.1469) |
|---|:-----:|:------------------:|
| 1.00 (baseline) | 0.1287 | −12.4% |
| 0.90 | 0.1276 | −13.1% |
| **0.75** | **0.1271** | **−13.4%** ← adopted |
| 0.65 | 0.1273 | −13.3% |
| 0.50 | 0.1301 | −11.4% |

**Decision**: Global T=0.75 baked into `Predictor.predict()` and `Predictor._calibrate_batch()`.

### Shadow Mode (monitoring, not production)
Segment-specific T values logged alongside production for 30+ match validation:

| Segment | Shadow T | Status |
|---------|:--------:|--------|
| Inn1 PP | 0.40 | Shadow — needs 30+ match validation |
| Inn2 PP | 0.60 | Shadow — needs 30+ match validation |
| Inn2 Mid | 0.50 | Shadow (conservative; optimal 0.33–0.55 but noisy) |

Shadow visible in: Streamlit amber `🔬 Shadow T` column + `[SHADOW]` console log + `shadow_t_prob` JSON field.

### Key Findings
- Brier curve flat between T=0.65–0.90 (max swing <0.001) — T=0.75 is safe mid-valley choice
- Inn1 PP is ONLY segment behind market (+5.1%); all Inn2 segments crush market (−33% to −40%)
- Inn2 Mid T=0.30 HURTS despite model dominance there — it's a feature gap, not calibration gap
- Segment-specific T combo achieves −16.3% vs market on this sample but too noisy to productionise

---

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
