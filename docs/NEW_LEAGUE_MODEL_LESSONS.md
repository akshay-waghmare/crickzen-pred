# New League Model — Lessons Learned & Checklist

This document captures every problem hit during PSL model development (v1→v4)
and the IPL model journey (v1→v6), distilled into a practical checklist for
building the next new league model from scratch.

---

## Problems Encountered & How to Resolve Them

### 1. Inn2 bias from fixed RRR midpoint (`rrr_midpoint_slope=0.0`)

**Problem:** Generic T20 default uses a fixed `rrr_midpoint=9.5`, meaning the
sigmoid that converts required-run-rate into win probability uses the same
midpoint at over 1 as over 19. In PSL (and IPL), teams sustain much higher RRRs
late in chases, so early-over win probs were over-pessimistic and late-over
probs were over-optimistic.

**Symptom:** Inn2 Brier noticeably worse than inn1; ECE high in death overs.
Run `scripts/analyze_<league>_resource_calculator.py` — look for
`rrr_midpoint` drift across the over-by-over breakdown.

**Fix:** Fit `rrr_midpoint` and `rrr_midpoint_slope` per league:
```python
# midpoint(over_0idx) = rrr_midpoint + rrr_midpoint_slope * over_0idx
rrr_midpoint=8.726, rrr_midpoint_slope=0.1772   # PSL
rrr_midpoint=8.56,  rrr_midpoint_slope=0.134    # IPL
```
Use `scripts/analyze_<league>_resource_calculator.py` with
`scripts/derive_<league>_improvements.py` to fit these from historical data.
**Effect:** PSL inn2 Brier −8.3%, ECE death phase −80%.

---

### 2. Inn2 PP gap — model doesn't know what inn1 looked like

**Problem:** At the start of inn2, the model only had the target score. It
didn't know *how* that target was set — 180/3 vs 180/8 are very different
chasing scenarios. Inn2 powerplay Brier was systematically high.

**Symptom:** Inn2 PP Brier much worse than inn2 middle/death; market beats
model badly in first 6 overs of inn2.

**Fix (step 1):** Add 2 carryover features (PSL v1 → v5 / IPL v5):
- `target_above_par` = `first_innings_score − venue_avg_score`
- `inn1_defendability` = `resource_win_prob` at last ball of inn1

**Fix (step 2):** Add 5 more (IPL v6 → PSL v4):
- `inn1_wickets_lost` — total resources consumed
- `inn1_pp_runs` — pitch behavior clue (early powerplay scoring)
- `inn1_death_rr` — finish momentum (death overs RR)
- `venue_chase_success` — venue-specific chase win rate
- `batting_won_toss` — toss context

**Effect (IPL v5→v6):** Inn2 PP vs market gap: +33.5% → +7.2% (78% closed).
**Effect (PSL v4):** All 7 features present, 100% non-zero in inn2. Inn1 beats
market (Brier 0.1351 vs market 0.1382).

**Important:** After the inn1 carryover features exist, the remaining inn2 PP
gap vs market is an **information gap** (live conditions, pitch, player fitness)
— not a feature engineering gap. Don't keep adding features.

---

### 3. Isotonic per-over calibrators overfit small leagues

**Problem:** Running `bbl-pipeline generate-oof` / `analyze-oof` produces 38+
per-over isotonic calibrators. For a large league (BBL, IPL: 1000+ matches)
these work well. For a small league (PSL: 331 matches, ~78k rows), the
calibrators learn the training distribution rather than generalize — they
**hurt live Brier by +12%** (0.1536 vs raw 0.1480).

**Symptom:** OOF Brier looks good, but live OOS Brier is worse than raw
uncalibrated model.

**Diagnosis:** Compare `isotonic_calibrator.pkl` (per-over) vs raw on the live
betx21/market dataset.

**Fix:** Replace the per-over isotonic dict with a single global
`TemperatureScaler`. Fit T on full training set OOF preds:
```python
# scripts/analyze_<league>_oof_temp_calibrators.py
# PSL optimal: T=0.437 (OOF fit on 78k rows, 5-fold)
ts = TemperatureScaler(); ts.temperature = 0.437
cal['per_over_calibrators'] = {k: ts for k in cal['per_over_calibrators']}
joblib.dump(cal, 'models/<league>/isotonic_calibrator.pkl')
```
**Rule of thumb:** Use per-over isotonic only when `n_matches >= ~500`. Below
that, use global temperature or innings-specific temperature.

---

### 4. `final_over_lookup` makes things worse with sparse data

**Problem:** Adding a `final_over_lookup` table (empirically derived from
actual end-of-over states) improves resource_win_prob accuracy for large
leagues. But for PSL (331 matches), the cells are too sparse — some final-over
states have <5 observations — causing the lookup to overfit noise.

**Symptom:** After adding `final_over_lookup` to `FormatConfig.psl()` and
retraining, live Brier went from 0.1452 → 0.1480 (+1.9%).

**Fix:** Don't add `final_over_lookup` for leagues with fewer than ~500 matches.
The sigmoid fallback (`rrr_midpoint` + `rrr_beta`) is smoother and generalizes
better. Add a comment in `FormatConfig`:
```python
# NOTE: final_over_lookup NOT added — <N> matches too sparse
```

---

### 5. Logit-space post-hoc bias correction fails with sparse live data

**Problem:** Tried fitting a logit-space bias correction (additive shift /
scale / per-segment) on the live betx21 dataset to squeeze out remaining
market gap. With only 15 live matches (458 obs), LOMO cross-validation folds
have 3–5 observations for some segments → volatile bias estimates.

**Symptom:** All blend alphas converge to 0.00 (use pure market). Best
"honest" result barely moves vs raw.

**Fix:** Don't attempt post-hoc logit correction with fewer than ~50 live
matches and ~2,000+ observations. Temperature scaling (a single parameter) is
far more stable at small sample sizes.

**Rule of thumb:** 
- `n_live_matches < 20`: trust the model as-is, no post-hoc correction
- `n_live_matches 20-50`: global temperature only
- `n_live_matches 50+`: innings-specific temperature
- `n_live_matches 200+`: per-phase calibrators safe

---

### 6. Transition blend becomes redundant (and harmful) after adaptive sigmoid + inn1 carryover

**Problem:** The innings transition blend (`transition_blend_overs=6`) was added
to smooth the abrupt jump in win probability at the start of inn2. It works
by blending the inn1 final win prob with the inn2 early probs over the first
6 overs.

After adding the per-over adaptive sigmoid AND the inn1 carryover features,
the blend becomes **redundant** and **hurts inn2 PP Brier by +0.9%** because
it dampens genuine model signal in the powerplay.

**Fix:** Set `transition_blend_overs=0` in `FormatConfig` once the league has:
- Per-over adaptive `rrr_midpoint_slope > 0`, AND
- Inn1 carryover features (`inn1_defendability`, `target_above_par`, etc.)

**IPL:** Disabled at v4 (blend −0.9% hurt).  
**PSL:** Disabled at v4 — inn1 Brier improved from 0.1372 → 0.1351 (beats market).

---

### 7. Chase wicket penalty effect is league-specific

**Problem:** IPL disabled `chase_wicket_weight` (set to 0.0) because checking
wickets in the inn2 resource calculator was **hurting IPL inn2 Brier by +6.7%**.
The assumption was this would also help PSL.

**Result:** PSL v5 (wicket penalty disabled) was significantly WORSE:
- Inn2 Brier: 0.1294 → 0.1492 (+15%)
- Inn1 Brier: 0.1351 → 0.1495 (+11%)

**Explanation:** IPL's high-paced scoring environment means wickets are less
informative than run rate. PSL is a more balanced/defensive league (slower
pitches in Lahore/Rawalpindi) where wicket preservation genuinely matters.

**Fix:** Never blindly copy this between leagues. Always test in isolation with
a retrain + live comparison. The default `chase_wicket_weight=1.0` should stay
unless proven harmful for the specific league.

---

### 8. Market quality varies dramatically across leagues

**Problem:** "Model beats market" is only meaningful relative to the market's
quality. Different leagues have very different betfair / betx21 market sharpness:

| League | Market Brier | Context |
|--------|-------------|---------|
| IPL (betx21) | 0.1667 | Weak book — easy to beat |
| PSL (betx21) | 0.1015 | Very sharp local Pakistani exchange |
| IPL (betfair) | ~0.13 | Moderate |

The PSL model hitting Brier 0.13 inn2 looks bad vs a 0.08 market, but the
model's absolute accuracy (OOF 0.1448) is comparable to IPL v6 (OOF 0.1411)
with 3.5× fewer training matches.

**Fix:** Always report both absolute Brier AND market-relative gap. The
absolute OOF Brier is the best proxy for model quality independent of market.
Don't over-optimize to beat a specific market — especially a sharp local one.

---

## New League Model Checklist

### Phase 1: Setup & Data
- [ ] Collect ≥150 matches minimum; ≥300 preferred for reliable calibration
- [ ] Run `bbl-pipeline ingest` and `bbl-pipeline process`
- [ ] Check `data/<league>_features_v1/training.parquet` — verify `innings==2` rows have non-zero `inn1_*` carryover columns
- [ ] Verify feature store has `venue_avg_score` (needed for `target_above_par`)

### Phase 2: FormatConfig
- [ ] Derive `par_score`, `league_avg_score`, `bat_first_win_rate` from data
- [ ] Fit `rrr_midpoint` and `rrr_midpoint_slope` per-over (don't use default 9.5/0.0)
- [ ] Fit `rrr_beta` from per-over data
- [ ] If ≥500 matches: add `final_over_lookup`; else: leave as None
- [ ] Set `transition_blend_overs=6` initially; test disabling after adaptive sigmoid + carryover added
- [ ] Leave `chase_wicket_weight=1.0` by default; test disabling only if inn2 Brier is suspiciously high
- [ ] Derive empirical `first_innings_wicket_penalty_3d` and `chase_wicket_penalty_2d`

### Phase 3: Training
- [ ] Run `bbl-pipeline retrain --league <X> --version v1`
- [ ] Check OOF report: inn2 Brier should be ≤ overall Brier
- [ ] Check inn2 PP Brier — if much worse than middle/death, inn1 carryover features may not be populating

### Phase 4: Calibration
- [ ] Run `bbl-pipeline analyze-oof` to generate per-over isotonic calibrators
- [ ] If `n_matches < ~500`: replace per-over isotonic with `TemperatureScaler`
  - Fit T via `scripts/analyze_<league>_oof_temp_calibrators.py`
  - Typical range: T=0.35–0.55 for T20 leagues
- [ ] Validate calibrator on any available live data

### Phase 5: Live Validation
- [ ] Collect ≥10 live match observations before drawing conclusions
- [ ] Compare model Brier vs market Brier — note market quality tier
- [ ] If live Brier > OOF Brier by >20%: suspect calibrator overfit → switch to temperature
- [ ] Don't fit post-hoc logit corrections with <50 live matches

### Phase 6: Iteration
- [ ] Test `transition_blend_overs=0` if adaptive sigmoid + inn1 carryover present
- [ ] Test `chase_wicket_weight=0.0` — but only test, don't assume it helps
- [ ] Do NOT add `final_over_lookup` if n_matches < 500 even if it looks good on OOF
- [ ] Each change: retrain → temperature-patch calibrator → compare on same live dataset

---

## PSL Model Version History

| Version | Key Change | Live Brier Overall | Inn1 | Inn2 | Notes |
|---------|-----------|-------------------|------|------|-------|
| v1 | Baseline (fixed midpoint) | 0.1584 | — | — | Inn2 biased |
| v2 | Adaptive sigmoid + T=0.437 | **0.1367** | 0.1372 | 0.1364 | Inn1 beats market ✅ |
| v3 | + final_over_lookup | 0.1480 | — | — | REVERTED (worse) |
| v4 | + transition_blend=0 | **0.1351 inn1** | **0.1351** | 0.1294 | Champion ✅ |
| v5 | + chase_wicket_weight=0 | worse | 0.1495 | 0.1492 | REVERTED (hurts PSL) |

**Champion: PSL v4** — `transition_blend_overs=0`, `chase_wicket_weight=1.0`, T=0.437
