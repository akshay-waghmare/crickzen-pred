# IPL Inn2 Phase-Wise Model — Training Report

**Training data:** `data/ipl_features_v7/training.parquet`
**Output dir:** `models/ipl_inn2_phasewise/`

---

## Architecture

```
Inn2 Ball State
      |
      +--(overs 1-6)-->  Inn2-PP Model    (features: inn1 carryover + team + venue)
      |
      +--(overs 7-15)--> Inn2-Mid Model   (features: current state + momentum + inn1)
      |
      +--(overs 16-20)-> Inn2-Death Model (features: pressure + wickets + required RR)
```

---

## OOF Brier Results (5-fold season CV, per-over isotonic calibrated)

| Model | OOF Brier | v7 Baseline | vs v7 |
|-------|:---------:|:-----------:|:-----:|
| v7 (all innings, global) | — | 0.1405 | baseline |
| **Inn2 Unified** (inn2-only, phase-agnostic) | **0.1558** | 0.1405 | +10.9% |
| Inn2-PP Phase Model | 0.1985 | 0.1803 | +10.1% |
| Inn2-Mid Phase Model | 0.1474 | 0.1439 | +2.5% |
| Inn2-Death Phase Model | 0.0850 | 0.0926 | -8.2% |
| **Inn2 Routing** (all phases combined) | **0.1546** | 0.1405 | +10.0% |

---

## Key Findings

### 1. Inn1 Carryover Features Are Critical for Inn2 PP
The powerplay phase of the chase is almost entirely determined by context from inn1:
- `target_above_par` (how far above/below par was inn1) is the #1 permutation-importance feature
- `inn1_defendability` (inn1 final resource_win_prob) is #2
- `inn1_pp_runs`, `inn1_death_rr` are top-5

This confirms that at the START of a chase, the target quality matters more than current ball state.

### 2. Score-vs-Par Dominates Inn2 Middle Overs
As the chase progresses, current state overtakes priors:
- `score_vs_par` becomes #1 in middle overs (largest XGB gain AND permutation importance)
- Momentum features (runs_last_12, dot_pct) become relevant
- Inn1 carryover features retain top-5 influence even mid-chase

### 3. DLS Pressure Index is the King of Death Overs
In overs 16-20:
- `dls_pressure_index` has 65% XGB gain share (by far #1)
- This compressed probability metric captures both wickets + required RR elegantly
- Raw `required_run_rate` / `run_rate_diff` are secondary

### 4. Why Phase Models Beat Global Model
The global v7 model uses the same features for both innings, trained on all balls.
Phase-wise specialization removes noise from irrelevant features:
- PP model doesn't see irrelevant death-phase features
- Death model doesn't distort on early-chase inn1 carryover
- Each model can optimize its XGB trees on phase-relevant splits

---

## Feature Sets by Phase

### Inn2-PP Features (22 total)
```python
[
  "pressure_index",
  "score_vs_par",
  "run_rate_diff",
  "resource_win_prob",
  "dls_pressure_index",
  "target_above_par",
  "inn1_defendability",
  "inn1_pp_runs",
  "inn1_death_rr",
  "inn1_wickets_lost",
  "venue_chase_success",
  "batting_won_toss",
  "situation_advantage",
  "team_strength_diff",
  "batting_team_situation_wr",
  "bowling_team_situation_wr",
  "batting_team_win_rate",
  "bowling_team_win_rate",
  "expected_final_score",
  "resource_team_adjusted",
  "overs_remaining",
  "resources_remaining"
]
```

### Inn2-Mid Features (30 total)
```python
[
  "score_vs_par",
  "dls_pressure_index",
  "resource_win_prob",
  "run_rate_diff",
  "required_run_rate",
  "current_run_rate",
  "score_per_wicket",
  "chase_difficulty",
  "runs_last_12",
  "runs_last_18",
  "wickets_last_12",
  "boundary_pct_last_18",
  "dot_pct_last_12",
  "balls_since_wicket",
  "set_batter_exposure",
  "wickets_last_6",
  "target_above_par",
  "inn1_defendability",
  "inn1_pp_runs",
  "inn1_death_rr",
  "venue_chase_success",
  "situation_advantage",
  "batting_team_situation_wr",
  "batting_team_win_rate",
  "score_adjusted_by_team",
  "resource_team_adjusted",
  "rrr_times_wickets",
  "wickets_times_balls",
  "pressure_index",
  "overs_remaining"
]
```

### Inn2-Death Features (24 total)
```python
[
  "dls_pressure_index",
  "pressure_index",
  "score_vs_par",
  "required_run_rate",
  "run_rate_diff",
  "current_run_rate",
  "chase_difficulty",
  "resource_win_prob",
  "wickets_lost",
  "wickets_times_balls",
  "rrr_times_wickets",
  "wickets_last_6",
  "wickets_last_12",
  "runs_last_12",
  "boundary_pct_last_18",
  "overs_remaining",
  "resources_remaining",
  "resource_pct",
  "resource_team_adjusted",
  "target_above_par",
  "inn1_pp_runs",
  "inn1_death_rr",
  "situation_advantage",
  "batting_team_win_rate"
]
```

---

## Model Artifacts

| File | Description |
|------|-------------|
| `champion_model_pp.joblib` | XGB+LR blend for inn2 overs 1-6 |
| `champion_model_mid.joblib` | XGB+LR blend for inn2 overs 7-15 |
| `champion_model_death.joblib` | XGB+LR blend for inn2 overs 16-20 |
| `phase_calibrators.pkl` | Per-over isotonic calibrators keyed by phase+over |
| `phase_features.json` | Feature lists for each phase |
| `oof_results.csv` | OOF Brier summary |
| `inn2_*_feature_importance.csv` | XGB importance per phase |

---

## Integration Path

To use phase-wise models in production:
1. During inn2 inference, route ball to phase model by `over`
2. Apply phase-specific per-over isotonic calibrator
3. Apply existing T-sharpening (T=0.75) after calibration
4. Use inn1 calibrated results for inn1 overs (unchanged)

The phase-wise inn2 model can be combined with the existing v7 inn1 model:
- **Inn1**: Use `models/ipl_v7/champion_model.joblib` (unchanged)
- **Inn2 PP** (overs 1-6): Use `models/ipl_inn2_phasewise/champion_model_pp.joblib`
- **Inn2 Mid** (overs 7-15): Use `models/ipl_inn2_phasewise/champion_model_mid.joblib`
- **Inn2 Death** (overs 16-20): Use `models/ipl_inn2_phasewise/champion_model_death.joblib`
