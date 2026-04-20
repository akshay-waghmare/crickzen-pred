# IPL v5 Model — Documentation & Lessons Learned

**Date:** 2026-04-20
**Model:** IPL v5 (`models/ipl_v5/`)
**Training:** 278,954 balls, 1,169 matches (IPL historical)
**OOS Validation:** 23 matches true holdout (12 with market comparison)
**Key Change:** Inn1 carryover features bridge the innings transition gap

---

## Architecture

```
Cricsheet JSON → Ingest → Process (v5 features) → Train → IPL v5 Model
                                                          │
                                                          ▼
                                               Innings-Specific Isotonic
                                                          │
                                                          ▼
                                                    Final Prediction
```

**Pipeline:** `model → innings-specific isotonic` (no LogitBias, no transition blend needed)

---

## What Changed: v4 → v5

### Inn1 Carryover Features (Bridge Innings Transition)

Two new features carry first-innings context into the second innings:

| Feature | Description | Importance Rank | Signal |
|---------|-------------|:--------------:|--------|
| `target_above_par` | `first_innings_score - venue_avg_score` | #5 (0.025) | Target difficulty relative to venue |
| `inn1_defendability` | resource_win_prob at inn1's last ball | #8 (0.024) | SQI model's defendability estimate |

**Why these help:** At inn2 over 1, the ML model previously lost context because:
- `projected_score` → 0 (reset for inn2, zero variance)
- `projected_vs_venue_avg` → 0 (same)
- `partnership_runs`, `runs_last_12`, `runs_last_18` → near-zero (only 1 over of data)

The carryover features give immediate signal at inn2 start:
- Is this an above-par or below-par target?
- How defendable did the SQI model rate the total?

**No data leakage:** Both features are known before inn2 starts (inn1 is complete).

**Files modified:**
- `src/bbl_pipeline/data/processor.py` — Added carryover feature computation
- `src/bbl_pipeline/training/trainer.py` — TOP_FEATURES expanded 25 → 27

---

## OOS Performance: True Holdout (Train pre-2026, Test 2026)

### vs Market (12 matches, 394 observations)

| Segment | N | Market | v4 hold | v5 hold | v5 vs Mkt |
|---------|--:|-------:|--------:|--------:|----------:|
| **OVERALL** | 394 | 0.1540 | 0.1662 | **0.1565** | **+1.7%** |
| Inn1 | 176 | 0.2214 | 0.2276 | 0.2295 | +3.7% |
| **Inn2** | 218 | 0.0996 | 0.1166 | **0.0977** | **-1.9%** ✅ |
| Inn1 PP | 54 | 0.2087 | 0.2233 | 0.2242 | +7.4% |
| Inn1 MID | 79 | 0.2267 | 0.2244 | 0.2298 | +1.4% |
| Inn1 DEA | 43 | 0.2274 | 0.2390 | 0.2355 | +3.6% |
| Inn2 PP | 72 | 0.1195 | 0.1595 | 0.1404 | +17.5% |
| **Inn2 MID** | 104 | 0.0794 | 0.1019 | **0.0784** | **-1.2%** ✅ |
| **Inn2 DEA** | 42 | 0.1154 | 0.0794 | **0.0720** | **-37.6%** ✅ |

### v4 vs v5 (23 matches, 870 observations)

| Segment | N | v4 hold | v5 hold | v5 vs v4 |
|---------|--:|--------:|--------:|---------:|
| **OVERALL** | 870 | 0.1483 | **0.1456** | **-1.9%** |
| Inn1 | 450 | 0.1890 | 0.1905 | +0.8% |
| **Inn2** | 420 | 0.1048 | **0.0975** | **-7.0%** |
| Inn2 PP | 138 | 0.1606 | **0.1469** | **-8.6%** |
| Inn2 MID | 201 | 0.0823 | **0.0774** | **-5.9%** |
| Inn2 DEA | 81 | 0.0657 | **0.0630** | **-4.2%** |

---

## Key Insights

### 1. Carryover Features Close the Inn2 Gap
- v5 now **beats market on Inn2 overall** (-1.9%) and Inn2 Mid (-1.2%)
- Inn2 PP gap narrowed from +33.5% (v4) to +17.5% (v5)
- Inn2 Death remains dominant: -37.6% vs market

### 2. Inn1 Performance Unchanged
- Inn1 metrics are similar between v4 and v5 (carryover features are 0/neutral for inn1)
- This confirms the features only help where intended

### 3. Remaining Weakness: Inn2 PP (overs 1-6)
- Still +17.5% vs market (down from +33.5%)
- Root cause: early chase overs have very little ball-by-ball data
- Market has live context (dew, pitch, momentum) we can't capture from scoreboard

### 4. XGBoost Feature Importance (v5)

| Rank | Feature | Importance |
|:----:|---------|:----------:|
| 1 | resource_win_prob | 0.309 |
| 2 | dls_pressure_index | 0.147 |
| 3 | score_vs_par | 0.094 |
| 4 | run_rate_diff | 0.037 |
| 5 | **target_above_par** | **0.025** |
| 6 | team_strength_diff | 0.025 |
| 7 | expected_final_score | 0.024 |
| 8 | **inn1_defendability** | **0.024** |
| ... | (17 more features) | ... |

Both new features rank in the top 8 — they carry genuine signal.

---

## Investigation Log: What Was Tried and What Didn't Work

### ❌ Inn1 Pitch Proxy Features (Team-Adjusted)
- Added inn1_dots, inn1_boundaries, inn1_runs_per_wkt scaled by batting team win rate
- Idea: strong team with high dot% = genuinely tough pitch; weak team = just poor batting
- Holdout result: +0.6% worse overall, +4.8% worse inn2 mid
- Scoreboard-derived features have hit diminishing returns for IPL

### ❌ MC Predictor for Inn2 PP
- Monte Carlo simulation is +13% worse than ML across all inn2 PP overs
- Even 10% MC + 90% ML blend hurts (+0.6%)
- MC only ties at over 1, loses progressively worse

### ❌ Defendability Bridge (SQI → RRR Blend)
- Blending inn1's SQI-based probability with inn2's RRR ALWAYS hurts
- RRR is already more accurate than SQI at the boundary (Brier 0.2045 vs 0.2088)
- The +7.2pp resource_win_prob jump is RRR CORRECTING SQI's error

### ❌ Partnership Features + Target-Encoded Win Rates (v3 enhancement)
- Adding partnership_runs, partnership_balls, batsman_win_rate
- OOS result: marginally WORSE (-0.0006 Brier)
- The model already captures these signals through existing features

### ✅ Inn1 Carryover Features (THIS MODEL)
- target_above_par + inn1_defendability
- -7.0% improvement on inn2, -8.6% on inn2 PP
- Simple, no leakage, immediately available at prediction time

---

## Lessons Learned (DO NOT REPEAT)

1. **Don't blend at the resource level.** RRR is better than SQI for inn2. The jump is a correction, not a bug.

2. **Don't use MC for inn2 PP.** MC simulation has less information than the ML model.

3. **Don't add more player features.** XGBoost consistently assigns zero gain to player-level features (batting averages, strike rates). The model learns from scoreboard state, not individual players.

4. **DO carry forward inn1 context.** The ML model needs to know WHAT target was set (target_above_par) and HOW defendable it is (inn1_defendability). These are the #5 and #8 most important features.

5. **Don't train on all data for OOS validation.** True holdout (train pre-2026, test 2026) gives much more conservative (and realistic) results than train-on-all.

6. **12 matches is thin.** Many per-over comparisons have only 12 observations. Need 50+ matches for reliable per-over conclusions.

7. **Don't add more scoreboard-derived pitch features.** Even team-strength-adjusted pitch proxies (dot%, boundary%, RPW) add noise. XGBoost already extracts available scoreboard signal. The remaining inn2 PP gap vs market is an *information* gap (dew, pitch behavior, intent signals) not a *feature engineering* gap.

---

## Model Artifacts

```
models/ipl_v5/
├── champion_model.joblib      # XGBLogRegEnsemble (27 features)
├── isotonic_calibrator.pkl    # Innings-specific + per-over calibrators
├── feature_importance.csv     # 27 features ranked by importance
└── data_version.json          # Data hash for reproducibility
```

**Training data:** `data/ipl_features_v5/training.parquet`
**Feature store:** `data/ipl_feature_store_v3/`

---

## Next Steps

1. **Collect more OOS data** — 23 matches is still thin. Need full IPL 2026 (~60 matches).
2. **Apply LogitBias + transition blend** — May further improve inn2 PP (v3 full chain was -2.7% vs market).
3. **Market-model ensemble** — Blend model + market odds with phase-specific weights.
4. **Live context features** — Dew, pitch deterioration, momentum (requires non-scoreboard data).
