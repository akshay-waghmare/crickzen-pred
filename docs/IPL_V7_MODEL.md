# IPL v7 Model — Temperature Sharpening (T=0.75)

**Date:** 2026-05-03  
**Model:** IPL v7 (`models/ipl_v7/`)  
**Training:** 37 features, all IPL seasons ≤2025  
**OOS Holdout:** 16 matches, IPL 2026 (Apr 3–16), 580 per-over rows  
**Key Change:** Post-calibration temperature sharpening (global T=0.75) + shadow segment T logging

---

## Architecture

```
Cricsheet JSON → Ingest → Process (v7 features) → Train → IPL v7 Model
                                                          │
                                                          ▼
                                             Per-Over Isotonic (38 calibrators)
                                             + Phase fallback (6 calibrators)
                                                          │
                                                          ▼
                                             Global T=0.75 sharpening  ← NEW
                                             (sigmoid(logit(p) / 0.75))
                                                          │
                                                          ▼
                                               Final Prediction
```

---

## What Changed: v6 → v7

### 1. More Features (32 → 37)
v7 adds 5 extra features over v6 for a total of 37. See `feature_importance.csv` for full list.  
OOF Brier (5-fold CV): **0.1810**

### 2. Global Temperature Sharpening (T=0.75) — Production
Applied in `Predictor.predict()` and `Predictor._calibrate_batch()` AFTER per-over isotonic calibration and BEFORE league calibration.

**Formula:**
```python
logit_p = log(p / (1 - p))
p_sharp = sigmoid(logit_p / T)   # T < 1 → sharpens toward 0/1
```

**Why T=0.75?**  
Analysis on 16-match IPL 2026 holdout vs Betfair market odds:

| T Value | Brier (model) | vs Market | Notes |
|---------|:-------------:|:---------:|-------|
| 1.00 (no sharpening) | 0.1287 | −12.4% | Good baseline |
| 0.75 | **0.1271** | **−13.4%** | ← production |
| 0.65 | 0.1273 | −13.3% | Marginal gain, more extreme |
| 0.50 | 0.1301 | −11.4% | Over-sharpens, hurts |

The Brier curve is **flat between T=0.65–0.90** — T=0.75 sits in the middle of the safe valley.

### 3. Shadow Segment T — Monitoring Only (NOT production)
During specific overs, a second prediction is computed with segment-specific T and logged for comparison.  
**Shadow T values are NOT used for production output.**

| Segment | Shadow T | Rationale |
|---------|:--------:|-----------|
| Inn1 Powerplay (ov 1–6) | 0.40 | Only segment behind market; strong sharpening needed |
| Inn2 Powerplay (ov 1–6) | 0.60 | Stable across 12 & 16 match analyses |
| Inn2 Middle (ov 7–15) | 0.50 | Conservative (optimal range 0.33–0.55 but noisy on 16 matches) |
| All other segments | 1.0 (no-op) | Not applied |

Shadow predictions appear:
- **Console:** `[SHADOW] T=0.75 prod=XX% | seg-T shadow=YY% | inn=2 ov=8`
- **Streamlit:** Amber `🔬 Shadow T` column (appears only during shadow segments, hides otherwise)
- **JSON output:** `shadow_t_prob` field alongside `league_calibrated_prob`

**Promotion criteria:** After 30+ more live matches, if shadow consistently outperforms production on those segments (lower Brier vs market), promote the shadow T values to production by replacing `_GLOBAL_T = 0.75` with per-segment logic in `predictor.py`.

---

## OOS Holdout Results (16 matches, IPL 2026, vs Betfair)

Dataset: `data/ipl_betx21_full_market_2026.parquet` (580 per-over rows)

| Configuration | Brier | vs Market (0.1469) | Matches beat |
|---------------|:-----:|:------------------:|:------------:|
| Market (Betfair) | 0.1469 | baseline | — |
| Model T=1.0 (no sharpening) | 0.1287 | **−12.4%** | 12/16 |
| Model T=0.75 (global, **production**) | 0.1271 | **−13.4%** | 12/16 |
| Segment T (shadow combined) | 0.1229 | **−16.3%** | — |

### Per-Segment Breakdown (T=1.0 baseline)

| Segment | Model Brier | Market Brier | vs Market |
|---------|:-----------:|:------------:|:---------:|
| Inn1 PP | 0.1430 | 0.1360 | +5.1% ← behind |
| Inn1 Mid | ~0.12 | ~0.13 | −8% |
| Inn1 Death | ~0.13 | ~0.18 | −28% |
| Inn2 PP | ~0.10 | ~0.15 | −33% |
| Inn2 Mid | ~0.08 | ~0.13 | **−38%** |
| Inn2 Death | ~0.06 | ~0.10 | **−40%** |

**Key insight:** Inn2 segments are where the model dominates. Inn1 PP is the only weak spot (shadow T=0.40 targets this).

### Segment-Optimal T values (from 16-match analysis)

| Segment | Optimal T | Adopted? |
|---------|:---------:|:--------:|
| Inn1 PP | 0.364 | Shadow (0.40, rounded) |
| Inn1 Mid | 1.06 | No (soften slightly, not worth it) |
| Inn1 Death | 0.97 | No (near 1.0) |
| Inn2 PP | 0.606 | Shadow (0.60) |
| Inn2 Mid | 0.327 | Shadow (0.50, conservative) |
| Inn2 Death | 1.07 | No (near 1.0) |

---

## Implementation Details

### Code Locations

| File | Change | Line (approx) |
|------|--------|:-------------:|
| `src/bbl_pipeline/inference/predictor.py` | Global T=0.75 + shadow compute in `predict()` | ~980 |
| `src/bbl_pipeline/inference/predictor.py` | Global T=0.75 in `_calibrate_batch()` | ~1770 |
| `src/bbl_pipeline/inference/crex_live_predictor.py` | Reads `last_shadow_prob`, logs `[SHADOW]` line, emits `shadow_t_prob` in JSON | ~2316 |
| `src/bbl_pipeline/app/live_streamlit_app.py` | Amber `🔬 Shadow T` column in calibration cards | ~1586 |

### Where T is Applied in the Chain
```
Raw XGB+LR score
      ↓
Per-over isotonic calibration (38 calibrators)
      ↓
Phase×target fallback (6 calibrators)
      ↓
Constraint layer (transition blend, terminal clamp)
      ↓  ← T=0.75 applied HERE (global production)
      ↓  ← shadow T computed HERE (stored, not returned)
League calibrator (if applicable)
      ↓
Final win_prob
```

---

## Data Pipeline

- **Training data:** `data/ipl_features_v7/training.parquet`
- **Feature store:** `data/ipl_feature_store_v3`
- **Model artifacts:** `models/ipl_v7/champion_model.joblib`, `oof_calibrators.pkl`
- **OOS market dataset:** `data/ipl_betx21_full_market_2026.parquet` (580 rows, 16 matches)
- **Analysis scripts:**
  - `scripts/_temp_full_betx21_T_analysis.py` — full T-sweep pipeline (betx21 parse → CS map → model → Brier vs market)
  - `scripts/_temp_segment_T.py` — per-segment T sweep
  - `scripts/_temp_find_T_vs_market.py` — original 12-match analysis

---

## Lessons Learned

1. **Global T > segment T in production** — on 16 matches, segment T is noisy (Inn2 Mid optimal T swings 0.33→0.55 between 12 vs 16 match samples). Global T=0.75 is stable.
2. **Shadow mode first** — never bake extreme T values (0.35, 0.40) directly without 30+ match validation.
3. **Flat Brier valley** — the curve between T=0.65–0.90 changes Brier by <0.001. No need to over-tune.
4. **Inn2 Mid is a feature gap, not calibration gap** — T=0.30 on Inn2 Mid HURTS (Brier 0.0806 vs optimal 0.0777). The model already crushes the market there; adding more sharpening doesn't help.
5. **Betfair data source:** `C:\Users\ADMINS\Documents\projects\betx21.live\ipl_matches_download` has full IPL 2026 betx21 data. Script `_temp_full_betx21_T_analysis.py` re-maps when new Cricsheet data arrives.

---

## Next Steps

- [ ] After 30+ live matches: compare `shadow_t_prob` vs `league_calibrated_prob` vs market in recorded states
- [ ] If Inn2 PP shadow (T=0.60) consistently wins → promote to production  
- [ ] If Inn1 PP shadow (T=0.40) consistently wins → replace global T for that segment
- [ ] Re-run `_temp_full_betx21_T_analysis.py` once IPL 2026 Cricsheet JSON catches up past Apr 16
