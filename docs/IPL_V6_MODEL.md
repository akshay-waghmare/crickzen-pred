# IPL v6 Model — Pre-Chase Prior Features

**Date:** 2026-04-20
**Model:** IPL v6 (`models/ipl_v6/`)
**Training:** 278,954 balls, 1,169 matches (IPL historical)
**OOS Validation:** 23 matches true holdout (12 with market comparison)
**Key Change:** Pre-chase prior features (inn1 context + toss + venue chase bias)

---

## Architecture

```
Cricsheet JSON → Ingest → Process (v6 features) → Train → IPL v6 Model
                                                          │
                                                          ▼
                                               Innings-Specific Isotonic
                                                          │
                                                          ▼
                                                    Final Prediction
```

**Pipeline:** `model → innings-specific isotonic` (32 features)

---

## What Changed: v5 → v6

### New Features (5 additions, 27 → 32)

| Feature | Rank | Importance | Description |
|---------|:----:|:----------:|-------------|
| `venue_chase_success` | #5 | 0.027 | Venue-specific chase win rate (historical) |
| `inn1_death_rr` | #14 | 0.021 | Run rate in overs 16-20 of inn1 (finish momentum) |
| `inn1_pp_runs` | #15 | 0.021 | Total runs in inn1 powerplay (pitch behavior proxy) |
| `batting_won_toss` | #16 | 0.021 | Binary: did current batting team win the toss? |
| `inn1_wickets_lost` | #23 | 0.018 | Wickets fallen in inn1 (180/3 ≠ 180/8) |

### Design Philosophy

The inn2 PP gap vs market was diagnosed as a **cold-start prior deficit**, not a transition bug.
At the start of a chase, the model has weak state information while the market already prices in:
- Venue chasing conditions (dew, pitch wear)
- Toss advantage (chose to chase for a reason)
- Quality of the total set (180/3 with death acceleration ≠ 180/8 with collapse)

These features inject **pre-chase prior information** so the model doesn't start cold.

---

## OOS Results (True Holdout: train pre-2026, test 2026)

*Note: Metrics recomputed with aligned metadata (processor now includes match_id/season in training.parquet).*

### v5 → v6 Improvement (ALL 23 matches, P(batting_team))

| Segment | N | v5 Brier | v6 Brier | Change |
|---------|:-:|:--------:|:--------:|:------:|
| **OVERALL** | 870 | 0.1199 | 0.1129 | **-5.8%** ✅ |
| Inn1 | 450 | 0.1690 | 0.1627 | -3.7% ✅ |
| &nbsp; Inn1 PP | 138 | 0.1848 | 0.1811 | -2.0% |
| &nbsp; Inn1 MID | 203 | 0.1599 | 0.1537 | -3.8% ✅ |
| &nbsp; Inn1 DEA | 109 | 0.1661 | 0.1560 | -6.1% ✅ |
| **Inn2** | 420 | 0.0672 | 0.0595 | **-11.5%** ✅ |
| &nbsp; Inn2 PP | 138 | 0.1023 | 0.0969 | -5.2% ✅ |
| &nbsp; Inn2 MID | 201 | 0.0517 | 0.0419 | **-19.1%** ✅ |
| &nbsp; Inn2 DEA | 81 | 0.0459 | 0.0395 | -14.0% ✅ |

### vs Market (12 matches with Betfair odds, P(inn1_team))

| Segment | N | Market | v6 | vs Market |
|---------|:-:|:------:|:--:|:---------:|
| **OVERALL** | 394 | 0.1540 | 0.1282 | **-16.7%** ✅ |
| Inn1 | 176 | 0.2214 | 0.2093 | -5.4% ✅ |
| &nbsp; Inn1 PP | 54 | 0.2087 | 0.2199 | +5.4% |
| &nbsp; Inn1 MID | 79 | 0.2267 | 0.2065 | -8.9% ✅ |
| &nbsp; Inn1 DEA | 43 | 0.2274 | 0.2013 | -11.5% ✅ |
| **Inn2** | 218 | 0.0996 | 0.0627 | **-37.0%** ✅ |
| &nbsp; Inn2 PP | 72 | 0.1195 | 0.0961 | **-19.5%** ✅ |
| &nbsp; Inn2 MID | 104 | 0.0794 | 0.0458 | **-42.3%** ✅ |
| &nbsp; Inn2 DEA | 42 | 0.1154 | 0.0470 | **-59.2%** ✅ |

### Inn2 PP Gap Progression

| Version | Inn2 PP vs Market | Key Change |
|---------|:-----------------:|------------|
| v4 (baseline) | +33.5% | No carryover features |
| v5 | +17.5% | + target_above_par, inn1_defendability |
| **v6** | **-19.5%** | + venue_chase, toss, inn1 momentum/wickets/PP |

v6 now **beats market in every segment except Inn1 PP** (+5.4%).
Inn2 PP flipped from +33.5% worse to **-19.5% better** than market.

---

## Feature Importance (Full 32 Features)

| Rank | Feature | Importance |
|:----:|---------|:----------:|
| 1 | resource_win_prob | 0.254 |
| 2 | dls_pressure_index | 0.128 |
| 3 | score_vs_par | 0.094 |
| 4 | run_rate_diff | 0.037 |
| 5 | **venue_chase_success** | **0.027** |
| 6 | expected_final_score | 0.026 |
| 7 | rrr_times_wickets | 0.025 |
| 8 | target_above_par | 0.024 |
| 9 | situation_advantage | 0.023 |
| 10 | batting_team_win_rate | 0.023 |

---

## Experiments That Failed

### ❌ Inn1 Pitch Proxy Features (Team-Adjusted)
- dot%, boundary%, runs_per_wkt scaled by batting team strength
- Holdout: +0.6% worse overall, +4.8% worse inn2 mid
- Scoreboard-derived aggregate features hit diminishing returns

---

## Lessons Learned

1. **Pre-chase prior features > scoreboard aggregates.** Venue chase success, toss context,
   and inn1 structure (wickets, death RR, PP runs) all provide real signal. Generic pitch
   proxies (dot%, boundary%) do not.

2. **The inn2 PP gap is an information gap, not a model gap.** The remaining +7.2% likely
   reflects market knowledge we can't extract from scoreboard (dew, pitch behavior under
   lights, trader priors, intent signals).

3. **180/3 ≠ 180/8.** Carrying `inn1_wickets_lost` lets the model distinguish between
   strong totals with resources preserved vs inflated/collapse totals.

4. **Toss matters.** `batting_won_toss` ranked #16 — the model learns that choosing to
   chase carries information about conditions.

5. **Venue chase history is very strong.** `venue_chase_success` at #5 is the single
   most impactful new feature. Some venues heavily favor chasing.

---

## Model Artifacts

```
models/ipl_v6/
├── champion_model.joblib      # XGBLogRegEnsemble (32 features)
├── isotonic_calibrator.pkl    # Innings-specific + per-over calibrators
├── feature_importance.csv     # 32 features ranked by importance
└── data_version.json          # Data hash for reproducibility
```

**Training data:** `data/ipl_features_v6/training.parquet`
**Feature store:** `data/ipl_feature_store_v3/`

---

## Next Steps

1. **Collect more OOS data** — 12 matches with market is thin. Full IPL 2026 (~60 matches)
   will give much more reliable per-segment conclusions.

2. **Inn2 PP specialist model** — A dedicated model for overs 1-3 of chase using
   primarily prior features with small live update. Could close remaining gap.

3. **Inn1 closing probability** — Use the full model's calibrated prediction at inn1 end
   (not just resource_win_prob) as the prior. Requires stacking/OOF approach.
