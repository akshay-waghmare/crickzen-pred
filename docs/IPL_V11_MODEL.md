# IPL v11 Model — Inn2 Phase Routing

## Overview

IPL v11 replaces the v7 global inn2 predictions with **three dedicated inn2 phase models** (PP / Mid / Death). Inn1 remains on the v7 global model.

```
Inn1 (overs 1-20): models/ipl_v7  (unchanged)
Inn2 PP    (1-6):  models/ipl_inn2_v1  champion_model_pp.joblib
Inn2 Mid  (7-15):  models/ipl_inn2_v1  champion_model_mid.joblib
Inn2 Death(16-20): models/ipl_inn2_v1  champion_model_death.joblib
```

**Routing config**: `models/ipl_v11/routing_config.json`

---

## Performance: v7 vs v11 (Season OOF, 5-fold, 2007–2026)

| Phase | v7 OOF cal | v11 OOF cal | Improvement |
|-------|-----------|------------|-------------|
| Inn2 PP | 0.18026 | **0.17043** | ▼ 5.5% |
| Inn2 Mid | 0.14389 | **0.13067** | ▼ 9.2% |
| Inn2 Death | 0.09260 | **0.07708** | ▼ 16.8% |
| Inn2 Total | 0.14054 | **0.13545** | ▼ 3.6% |

### Holdout (2025+2026, ~10k rows, true OOS)

| Phase | v7 OOF | v11 no-T | vs v7 |
|-------|--------|----------|-------|
| Inn2 PP | 0.18026 | **0.14489** | ▼ 19.6% |
| Inn2 Mid | 0.14389 | **0.10318** | ▼ 28.3% |
| Inn2 Death | 0.09260 | **0.06805** | ▼ 26.5% |
| Inn2 Total | 0.14054 | **0.11233** | ▼ 20.0% |

---

## Feature Engineering: `engineer_inn2_features()`

Script: `scripts/inn2_feature_engineering.py`

The engineered features extend the base v7 feature set with inn2-specific context:

### Momentum & Pressure
| Feature | Description | Phase Importance |
|---------|-------------|-----------------|
| `rr_vs_rrr` | Current RR vs Required RR (gap) | PP + Mid top feature |
| `wickets_in_hand` | 10 - wickets_fallen | All phases |
| `rolling_3over_rr` | RR in last 3 overs | Mid + Death |
| `balls_remaining` | Balls left | Death critical |
| `win_prob_swing` | Change in win prob last 2 overs | Mid + Death |

### Chase Context (Inn1 Carryover)
| Feature | Description | Source |
|---------|-------------|--------|
| `target_above_par` | inn1_score - venue_avg (≈ pressure proxy) | Best OOF feature |
| `inn1_defendability` | Final inn1 resource_win_prob | Inn2 entry signal |
| `inn1_pp_runs` | Powerplay runs in inn1 | Chase momentum context |
| `inn1_death_rr` | Death over RR in inn1 | Death target shape |
| `inn1_wickets_lost` | Total inn1 wickets | Target score stiffness |
| `batting_won_toss` | 1 if batting team won the toss | Strategic advantage |
| `venue_chase_success` | Historical chase win rate at this venue | Venue bias |

### Team Ratings
| Feature | Description |
|---------|-------------|
| `batting_team_win_rate` | Team overall win rate |
| `batting_team_bat_first_wr` | Win rate batting first |
| `batting_team_bowl_first_wr` | Win rate bowling first |
| `batting_team_venue_wr` | **Team win rate at specific venue** (added v11 final) |

---

## Phase Models

### Training Data
- Source: `data/ipl_inn2_features_v1/training.parquet` (126 cols, 134,614 rows)
- **IMPORTANT**: Do NOT regenerate via `scripts/run_inn2_research.py` — it would drop `batting_team_venue_wr`

### Architecture: `XGBLRBlend`
- 50% XGBoost (400 trees, depth=5, LR=0.02) + 50% LogisticRegression (C=0.01)
- Defined in `scripts/calibrate_inn2_phases_oof.py` and `src/bbl_pipeline/training/blend_model.py`

### Phase Feature Counts
| Phase | Features | Key additions vs v7 |
|-------|----------|---------------------|
| PP (1-6) | 55 | `rr_vs_rrr`, `target_above_par`, `venue_chase_success`, `batting_team_venue_wr` |
| Mid (7-15) | 71 | All PP features + `rolling_3over_rr`, `win_prob_swing`, `batting_won_toss` |
| Death (16-20) | 59 | `balls_remaining`, `wickets_in_hand`, `inn1_death_rr`, `rr_vs_rrr` |

Feature lists: `models/ipl_inn2_v1/phase_features.json`

---

## Calibration

### Calibration Stack
```
Raw XGBLRBlend output → Per-over isotonic calibrator → Final probability
```

### Calibrators: `models/ipl_inn2_v1/phase_oof_calibrators.pkl`
| Phase | Calibrators | Raw OOF | Calibrated OOF | Gain |
|-------|-------------|---------|----------------|------|
| PP | 6 (overs 1-6) | 0.17336 | **0.17043** | −1.7% |
| Mid | 9 (overs 7-15) | 0.13348 | **0.13067** | −2.1% |
| Death | 4 (overs 16-19) | 0.07914 | **0.07708** | −2.6% |

Calibrators fitted via 5-fold season-based OOF on `ipl_inn2_features_v1/training.parquet`.

### T-Scaling: NOT Needed

T-scaling (temperature scaling) was evaluated as an additional calibration layer.

**T_oos** (fitted on ≤2024 OOF predictions, applied to 2025+2026 holdout):
- PP: T = 1.017 · Mid: T = 1.027 · Death: T = 1.003

All values ≈ 1.0 → the per-over isotonic calibrators already handle calibration correctly. No additional T-scaling is needed in production.

> **Key insight**: Previous sessions showed large T values because champion model predictions were
> evaluated in-sample (overfit). Proper OOF evaluation shows T ≈ 1.0 across all phases.

---

## Inference: `batting_team_venue_wr`

This feature requires a new artefact in the feature store.

**File**: `data/ipl_feature_store_v3/team_venue_ratings.parquet`
- Schema: `team, venue, win_rate, n` (263 rows, n ≥ 3 matches)
- Fallback: 0.5 (no-info prior) when (team, venue) combo not found
- Loaded by `InMemoryFeatureStore.get_team_venue_wr(team, venue)`

**Sample values**:
- CSK @ Chepauk = 0.717 ✅
- MI @ Wankhede = 0.621 ✅

---

## Files

| File | Description |
|------|-------------|
| `models/ipl_v11/routing_config.json` | Inn2 phase routing config with brier metrics |
| `models/ipl_inn2_v1/champion_model_pp.joblib` | PP phase model (55 feats) |
| `models/ipl_inn2_v1/champion_model_mid.joblib` | Mid phase model (71 feats) |
| `models/ipl_inn2_v1/champion_model_death.joblib` | Death phase model (59 feats) |
| `models/ipl_inn2_v1/phase_features.json` | Feature lists per phase |
| `models/ipl_inn2_v1/phase_oof_calibrators.pkl` | Per-over isotonic calibrators |
| `models/ipl_inn2_v1/oof_calibrated_results.csv` | OOF Brier results per phase |
| `data/ipl_inn2_features_v1/training.parquet` | Training data (126 cols, 134,614 rows) |
| `data/ipl_feature_store_v3/team_venue_ratings.parquet` | Venue WR artefact for inference |
| `scripts/inn2_feature_engineering.py` | Feature engineering pipeline |
| `scripts/calibrate_inn2_phases_oof.py` | OOF calibrator generation |
| `scripts/run_inn2_research.py` | ⚠️ DANGER: overwrites training data — do not run |

---

## How to Retrain

1. **Feature engineering** (only if regenerating from scratch):
   ```bash
   python scripts/run_inn2_research.py  # ⚠️ Only run intentionally — overwrites training data
   ```

2. **Regenerate OOF calibrators** (after champion model changes):
   ```bash
   python scripts/calibrate_inn2_phases_oof.py
   ```

3. **Rebuild venue WR artefact** (after adding new IPL matches):
   ```bash
   python -c "
   import sys; sys.path.insert(0,'src')
   from bbl_pipeline.features.store import InMemoryFeatureStore
   # Rebuild team_venue_ratings.parquet from data/ipl_raw/matches
   "
   ```

---

## Development History

| Session | Work Done |
|---------|-----------|
| EDA & research | Feature importance analysis, inn2 EDA, phase-wise model research |
| v11 architecture | Inn2 phase routing design, `engineer_inn2_features()` |
| Phase model training | PP/Mid/Death models, OOF calibration, v7 comparison |
| v10 features | Added 9 inn2 momentum features, 50-feature dataset |
| Phase routing production | `Inn2PhaseRouter`, `crex_live_predictor` integration |
| Phase routing calibration | Season OOF calibrators, per-over isotonic |
| Brier comparison | v7 vs v11 no-T vs v11+T full comparison chart |
| Temperature scaling | T_oos ≈ 1.0 — T-scaling not needed for v11 |
| venue_wr feature | `batting_team_venue_wr` added to training data + inference store |
| **This session** | T-scaling final verdict, routing_config update, documentation |

---

## Lessons Learned

1. **Phase models beat global inn2**: routing to 3 dedicated models gives 5-17% OOF improvement
2. **Inn1 carryover features matter**: `target_above_par`, `inn1_defendability` are top-5 features in PP
3. **Venue × team interaction** (`batting_team_venue_wr`): adds −0.75% in PP despite low XGB gain rank
4. **T-scaling diagnosis**: always use OOF (not champion model in-sample) predictions to evaluate T — in-sample overfitting artificially inflates T correction need
5. **XGB gain rank misleads for static features**: `batting_team_venue_wr` ranks last by gain but contributes real OOF signal because it provides match-level context, not ball-level variation
