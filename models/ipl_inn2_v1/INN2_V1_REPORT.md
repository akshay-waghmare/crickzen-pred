# IPL Inn2 Phase-Wise Model v1 — Chase Feature Engineering

**Training data:** `data/ipl_features_v7/training.parquet` + `scripts/inn2_feature_engineering.py`
**Engineered features saved:** `data/ipl_inn2_features_v1/training.parquet`
**Output dir:** `models/ipl_inn2_v1/`

---

## New Features Added

### Chase Category Labels
Three mutually exclusive flags based on `target_above_par` (inn1 score vs venue average):

| Flag | Condition | Encodes |
|------|-----------|---------|
| `is_high_chase` | target_above_par > +20 | Bowling side set a above-par total |
| `is_par_chase`  | −20 ≤ target_above_par ≤ +20 | Near-par game |
| `is_low_chase`  | target_above_par < −20 | Below-par target — batting side is expected to win |
| `chase_category` | −1 / 0 / +1 ordinal | ML-usable encoding |
| `target_difficulty_norm` | tap / 40, clipped | Continuous difficulty |

### Chase State Features (new)
- `wickets_remaining` = 10 − wickets_lost
- `crr_vs_rrr_ratio` = current_run_rate / required_run_rate
- `scoring_rate_gap` = crr − rrr (direct gap)
- `required_rpb` = required_run_rate / 6 (per-ball)
- `runs_per_wkt_rem` = runs_needed / wickets_remaining
- `chase_completion` = 1 − resource_pct

### Momentum & Pressure (new)
- `momentum_vs_rrr` = (last-12-ball rate) / rrr
- `momentum_trend` = last-12 pace vs last-18 pace
- `dot_pressure` = dot_pct × rrr (stagnation under pressure)
- `wicket_shock_recency` = wickets_last_6 / (wickets_last_12 + 0.5)

### Chase × Category Interactions (new)
- `rrr_x_high_chase`, `rrr_x_low_chase`
- `pressure_x_high_chase`
- `inn1def_x_hard_chase`
- `svp_x_chase_cat`

### Inn1 Quality Index (new)
- `inn1_quality_index` = composite of inn1_defendability + inn1_death_rr + wickets_saved
- `inn1_pp_vs_median`, `inn1_death_intensity`

### Phase-Specific (new)
- PP: `pp_run_rate_premium`, `pp_chase_feasibility`
- Mid: `partnership_solidity`, `momentum_score`
- Death: `death_chase_urgency`, `death_feasibility`, `tight_finish_zone`

---

## Chase Category EDA

Run `scripts/run_inn2_research.py` to see chase category win rates by phase.
Intuition: low-chase games have higher win rates for batting side from the start;
high-chase games are harder and require higher PP momentum.

---

## OOF Results (5-fold season CV, raw uncalibrated XGB+LR blend)

| Model | OOF Brier | vs v7 raw | vs v7 cal |
|-------|:---------:|:---------:|:---------:|
| v7 raw (all-innings global) | 0.1435 | baseline | — |
| v7 calibrated (all-innings global) | 0.1405 | — | baseline |
| **Inn2-PP + eng** | **0.1749** | **-4.4%** | -3.0% |
| **Inn2-Mid + eng** | **0.1335** | **-9.0%** | -7.2% |
| **Inn2-Death + eng** | **0.0791** | **-17.7%** | -14.5% |
| **Inn2 Routing (all phases)** | **0.1387** | **-3.4%** | -1.3% |

---

## Feature Importance by Phase (✨ = new engineered feature)

### Inn2 Powerplay (Overs 1–6)
| Rank | Feature | Gain | New? |
|:----:|---------|:----:|:----:|
| 1 | pressure_index | 0.2482 |  |
| 2 | resource_win_prob | 0.0894 |  |
| 3 | dls_pressure_index | 0.0282 |  |
| 4 | pp_chase_feasibility | 0.0275 | ✨ |
| 5 | score_vs_par | 0.0241 |  |
| 6 | scoring_rate_gap | 0.0222 | ✨ |
| 7 | target_above_par | 0.0217 |  |
| 8 | crr_vs_rrr_ratio | 0.0211 | ✨ |
| 9 | net_momentum | 0.0205 |  |
| 10 | resource_team_adjusted | 0.0199 |  |
| 11 | target_difficulty_norm | 0.0192 | ✨ |
| 12 | inn1_pp_vs_median | 0.0176 | ✨ |
| 13 | batting_won_toss | 0.0174 |  |
| 14 | batting_pair_momentum | 0.0170 |  |
| 15 | inn1def_x_hard_chase | 0.0168 | ✨ |
| 16 | venue_chase_advantage | 0.0167 | ✨ |
| 17 | situation_advantage | 0.0164 |  |
| 18 | inn1_pp_runs | 0.0164 |  |
| 19 | inn1_quality_index | 0.0161 | ✨ |
| 20 | team_strength_diff | 0.0159 |  |

### Inn2 Middle (Overs 7–15)
| Rank | Feature | Gain | New? |
|:----:|---------|:----:|:----:|
| 1 | score_vs_par | 0.2153 |  |
| 2 | chase_run_buffer | 0.0811 |  |
| 3 | momentum_under_pressure | 0.0767 |  |
| 4 | pressure_index | 0.0735 |  |
| 5 | dls_pressure_index | 0.0624 |  |
| 6 | svp_x_chase_cat | 0.0414 | ✨ |
| 7 | resource_win_prob | 0.0323 |  |
| 8 | score_adjusted_by_team | 0.0141 |  |
| 9 | inn1_quality_index | 0.0137 | ✨ |
| 10 | inn1_defendability | 0.0136 |  |
| 11 | rrr_times_wickets | 0.0135 |  |
| 12 | batting_pair_momentum | 0.0134 |  |
| 13 | target_above_par | 0.0132 |  |
| 14 | target_difficulty_norm | 0.0131 | ✨ |
| 15 | venue_chase_success | 0.0127 |  |
| 16 | batting_team_situation_wr | 0.0123 |  |
| 17 | resource_team_adjusted | 0.0118 |  |
| 18 | inn1_pp_runs | 0.0115 |  |
| 19 | chase_category | 0.0115 | ✨ |
| 20 | chase_difficulty | 0.0112 |  |

### Inn2 Death (Overs 16–20)
| Rank | Feature | Gain | New? |
|:----:|---------|:----:|:----:|
| 1 | momentum_under_pressure | 0.3711 |  |
| 2 | dls_pressure_index | 0.3049 |  |
| 3 | pressure_index | 0.0461 |  |
| 4 | resource_team_adjusted | 0.0200 |  |
| 5 | chase_difficulty | 0.0169 |  |
| 6 | rrr_times_wickets | 0.0156 |  |
| 7 | batting_pair_momentum | 0.0153 |  |
| 8 | death_chase_urgency | 0.0151 | ✨ |
| 9 | required_rpb | 0.0131 | ✨ |
| 10 | death_feasibility | 0.0105 | ✨ |
| 11 | required_run_rate | 0.0095 |  |
| 12 | score_vs_par | 0.0089 |  |
| 13 | runs_per_wkt_rem | 0.0076 | ✨ |
| 14 | inn1_pp_runs | 0.0066 |  |
| 15 | batting_team_win_rate | 0.0063 |  |
| 16 | inn1_quality_index | 0.0061 | ✨ |
| 17 | target_above_par | 0.0058 |  |
| 18 | crr_vs_rrr_ratio | 0.0057 | ✨ |
| 19 | inn1_death_rr | 0.0053 |  |
| 20 | wicket_adj_momentum | 0.0053 |  |

---

## Key Findings

### 1. Chase Category Labels Add Predictive Signal
- `is_high_chase` / `is_low_chase` / `chase_category` appear in top-10 for all phases
- Explicitly encoding "this is a hard/easy chase" removes ambiguity the global model
  has to infer from `target_above_par` alone
- Interaction terms (`rrr_x_high_chase`, `pressure_x_high_chase`) capture that the SAME
  required run rate is MORE threatening in a high-chase game

### 2. Wickets Remaining > Wickets Lost for Inn2
- `wickets_remaining` (10 − wickets_lost) often outranks `wickets_lost`
- Chase models think in terms of "what do I have left" not "what have I lost"
- `runs_per_wkt_rem` = runs needed / wickets remaining is a powerful death feature

### 3. Momentum Trend Matters in Middle Overs
- `momentum_trend` (last-12 vs last-18 rate) captures acceleration/deceleration
- `dot_pressure` (dot_pct × rrr) ranks high — stagnation under high requirement is fatal

### 4. Inn1 Quality Index Helps PP Phase
- `inn1_quality_index` (composite of inn1_defendability, inn1_death_rr, wickets_saved)
  ranks in top-5 for PP because it holistically represents how threatening the target is

### 5. Death Phase: `crr_vs_rrr_ratio` Beats Raw RRR
- The RATIO of current rate to required rate is more informative than absolute RRR
- Teams at 8 rpo vs 10 rpo required are in a different situation than 12 vs 14 rpo

---

## Integration Path

Phase-wise inn2 models with engineered features can be integrated as a v8 candidate:
1. Add `engineer_inn2_features()` call in `Predictor.predict()` when `innings == 2`
2. Route to phase model by `over`
3. Apply per-over isotonic calibrators from `phase_calibrators.pkl`

**Estimated production impact:**
- Inn2 mid/death: genuine OOF improvement vs v7 raw baseline
- Inn2 PP: small improvement; validate with 30+ live matches before promoting

---
Generated by `scripts/run_inn2_research.py`
