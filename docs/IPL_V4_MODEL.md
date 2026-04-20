# IPL v4 Model — Documentation & Lessons Learned

**Date:** 2026-04-20
**Model:** IPL v4 (`models/ipl_v4/`)
**Training:** 278,954 balls, 1,169 matches (IPL historical)
**OOS Validation:** 12 matches, 432 observations vs Betfair exchange (April 2026)
**Key Change:** Per-over adaptive RRR midpoint in resource calculator

---

## Architecture

```
Cricsheet JSON → Ingest → Process (v4 features) → Train → IPL v4 Model
                                                          │
                                                          ▼
                                               Per-Over Isotonic Calibration
                                                          │
                                                          ▼
                                                    Final Prediction
```

**Pipeline:** `model → per-over isotonic` (2-step only, NO LogitBias, NO transition blend)

---

## What Changed: v3 → v4

### Resource Calculator Improvement

The **single biggest change** is the per-over adaptive RRR midpoint for innings 2:

| Parameter | v3 (old) | v4 (new) | Why |
|-----------|----------|----------|-----|
| `rrr_midpoint` | 9.5 (fixed) | `8.56 + 0.134 × over` | Death overs sustain higher RRR in IPL |
| `rrr_beta` | 0.57 | 0.598 | Refit for IPL data |
| `chase_wicket_weight` | 1.0 | 0.0 | Wicket penalties HURT inn2 by +6.7% |

**Files modified:**
- `src/bbl_pipeline/features/format_config.py` — Added `rrr_midpoint_slope`, `chase_wicket_weight`
- `src/bbl_pipeline/features/calculator.py` — Per-over midpoint calculation

**Impact on resource_win_prob (in-sample):**

| Metric | v3 | v4 | Change |
|--------|----|----|--------|
| Inn2 Brier | 0.1744 | 0.1601 | **−8.2%** |
| Inn2 ECE | 0.1075 | 0.0135 | **−86.5%** |
| Inn1 Brier | unchanged | unchanged | 0.0% |

### Why v4 Doesn't Need LogitBias or Transition Blend

v3 required a complex 4-step pipeline (`iso → LogitBias → blend(6)`) because the
resource calculator had systematic biases that needed post-hoc correction. v4's improved
resource calculator absorbs those biases at the feature level.

**LogitBias on v4 — fitted biases are all near-zero:**

| Segment | v3 Bias | v4 Bias | Interpretation |
|---------|---------|---------|----------------|
| inn1_powerplay | +0.065 | +0.020 | No correction needed |
| inn1_middle | −0.323 | +0.030 | Bias gone |
| inn1_death | −0.689 | −0.040 | Bias gone |
| inn2_powerplay | +0.102 | −0.030 | Bias gone |
| inn2_mid/death | 0.000 | −0.010 / +0.090 | Already near-zero in v3 too |

**Transition blend on v4 — HURTS performance:**

| Metric | Without Blend | With Blend | Impact |
|--------|---------------|------------|--------|
| Inn2 PP Brier | 0.1651 | 0.1666 | **+0.9% worse** |
| Inn2 PP ECE | 0.0326 | 0.0547 | **+67.8% worse** |

**Lesson:** When the resource calculator is accurate, blending inn1's final probability
as a "prior" for inn2 adds noise. The per-over midpoint already gives accurate
early-chase probabilities without needing a transition prior.

---

## Full Metrics (In-Sample, 278,954 balls)

### Raw Model (no calibration)

| Segment | N | Brier | LogLoss | ECE |
|---------|---:|------:|--------:|----:|
| **OVERALL** | 278,954 | 0.1657 | 0.4926 | 0.0324 |
| Inn1 | 144,340 | 0.2001 | 0.5821 | 0.0344 |
| Inn2 | 134,614 | 0.1288 | 0.3965 | 0.0335 |
| Inn1 PP | 43,750 | 0.2186 | 0.6267 | 0.0572 |
| Inn1 Mid | 57,572 | 0.1956 | 0.5717 | 0.0492 |
| Inn1 Death | 43,018 | 0.1873 | 0.5508 | 0.0350 |
| Inn2 PP | 43,736 | 0.1661 | 0.4998 | 0.0471 |
| Inn2 Mid | 56,563 | 0.1275 | 0.3953 | 0.0413 |
| Inn2 Death | 34,315 | 0.0835 | 0.2671 | 0.0365 |

### Per-Over Isotonic Calibration (production pipeline)

| Segment | N | Brier | LogLoss | ECE |
|---------|---:|------:|--------:|----:|
| **OVERALL** | 278,954 | 0.1660 | 0.4915 | 0.0348 |
| Inn1 | 144,340 | 0.2017 | 0.5862 | 0.0482 |
| Inn2 | 134,614 | 0.1278 | 0.3899 | 0.0230 |
| Inn1 PP | 43,750 | 0.2217 | 0.6335 | 0.0626 |
| Inn1 Mid | 57,572 | 0.1967 | 0.5745 | 0.0500 |
| Inn1 Death | 43,018 | 0.1881 | 0.5538 | 0.0360 |
| Inn2 PP | 43,736 | 0.1651 | 0.4942 | 0.0326 |
| Inn2 Mid | 56,563 | 0.1269 | 0.3894 | 0.0265 |
| Inn2 Death | 34,315 | 0.0815 | 0.2577 | 0.0247 |

---

## OOS Performance vs Betfair Market (12 matches, 432 obs)

### Overall Comparison

| Model Config | Brier | vs Market |
|-------------|------:|----------:|
| **Betfair Market** | **0.1446** | baseline |
| v4 iso only | 0.1470 | +1.7% |
| v4 +bias | 0.1468 | +1.6% |
| v4 +bias+blend | 0.1470 | +1.7% |
| v3 iso only | 0.1484 | +2.7% |
| v3 +bias | 0.1484 | +2.7% |
| v3 FULL (iso+bias+blend) | 0.1482 | +2.6% |

**Key finding:** v4 is +1.0% better than v3 on OOS (0.1470 vs 0.1484).
LogitBias and blend provide negligible improvement on v4 (+0.1% at best).

### By Innings × Phase (v4 FULL vs Market)

| Segment | N | Market | v3 | v4 | v4 vs Mkt |
|---------|---:|------:|------:|------:|----------:|
| Inn1 PP | 72 | 0.2252 | 0.2101 (−6.7%) | 0.2046 | **−9.1%** ✅ |
| Inn1 Mid | 93 | 0.2218 | 0.2017 (−9.1%) | 0.2039 | **−8.1%** ✅ |
| Inn1 Death | 66 | 0.1675 | 0.1607 (−4.1%) | 0.1652 | **−1.4%** ✅ |
| Inn2 PP | 66 | 0.0890 | 0.1319 (+48.2%) | 0.1270 | +42.7% ❌ |
| Inn2 Mid | 86 | 0.0592 | 0.0909 (+53.6%) | 0.0874 | +47.7% ❌ |
| Inn2 Death | 49 | 0.0731 | 0.0619 (−15.3%) | 0.0615 | **−15.9%** ✅ |

**Pattern:** Model beats market in Inn1 (all phases) and Inn2 Death.
Market beats model in Inn2 PP and Inn2 Mid — this is a **sharpness gap**, not bias.

---

## Remaining Weakness: Inn2 PP/Mid (+42-48% vs Market)

### Diagnosis: Under-Confidence (Sharpness), Not Bias

The model predicts ~0.65 when the market says ~0.80. The model's predictions are
**directionally correct but not extreme enough**.

- **Bias:** Model mean ≈ actual mean ✅ (LogitBias near-zero confirms no systematic shift)
- **Sharpness:** Model spread ≈ 0.80× market spread ❌ (predictions cluster around 0.5-0.7)

### Why LogitBias Can't Fix This

LogitBias shifts the **mean** of predictions (adds a constant in logit space).
The problem is the **variance** — predictions need to be more extreme in both directions.
Temperature scaling (T<1) could help but hurts death overs where model is already good.

### Root Cause: Information Gap

The market has access to live context the model doesn't:
- Pitch behavior (turning, swinging, flat)
- Dew factor (massive impact on chasing in IPL)
- Player intent/body language/momentum
- Bowling changes, field placements
- Weather conditions

The model only sees scoreboard data (runs, wickets, overs, run rates).
This is a fundamental information asymmetry that **cannot be fixed with more features
from the same data source** — confirmed by Track A experiment (partnership + win rate
features provided zero OOS improvement).

---

## ⚠️ Critical Lessons — DO NOT REPEAT

### 1. ALWAYS Sort Raw Parquet Before Alignment

```python
# ❌ WRONG — raw parquet has random row order
raw = pd.read_parquet('data/ipl_raw/matches')
feat[col] = raw[col].values[:n]  # Assigns WRONG match_id/winner!

# ✅ CORRECT — sort first
raw = pd.read_parquet('data/ipl_raw/matches')
raw = raw.sort_values(['match_id', 'innings', 'over', 'ball']).reset_index(drop=True)
```

**Impact:** Without sorting, the EDA showed model was 118% WORSE than market (fake).
With sorting, model is only 1.7% worse (real).

### 2. betx21 Over Indexing

- betx21 `over_int` = `int(float_from_score_string)` → maps to 1-indexed overs
- Cricsheet `over` is 0-indexed: `cricsheet_over + 1 = betx21_over`
- When matching betx21 to Cricsheet: `betx21_over == cricsheet_over + 1`

### 3. Wicket Penalties HURT Inn2 (in IPL)

The multiplicative wicket_mult and rate_factor in the resource calculator
overcorrect for innings 2. Setting `chase_wicket_weight=0.0` improved Brier by 6.7%.

**Why:** IPL teams maintain ~90% scoring output even 7-8 wickets down in death overs.
The penalties were calibrated for formats where losing wickets has bigger impact.

### 4. LogitBias is a Symptom Fix, Not a Root Cause Fix

v3 needed LogitBias (biases up to −0.689) because the resource calculator was
systematically wrong. Fixing the resource calculator (v4) made all biases drop to ≤0.09.

**Rule:** If you need large LogitBias corrections, the upstream feature is broken.
Fix the feature, don't patch with post-hoc bias.

### 5. Transition Blend is Harmful When Resource Is Accurate

Blending inn1's final probability into early inn2 makes sense only if the model
can't properly estimate early-chase probabilities. The per-over adaptive midpoint
gives accurate early-chase estimates, making the blend redundant and harmful.

### 6. Temperature Scaling Has Phase Tradeoffs

T<1 makes predictions more extreme → helps inn2 PP/mid but hurts inn2 death
(where model is already sharper than market). Net effect is usually negative.

### 7. More Features ≠ Better OOS Performance

Track A experiment added partnership_runs (r=0.17, #3 strongest signal) and
target-encoded win rates. Result: **zero OOS improvement**.

XGBoost can already learn these interactions from existing tree splits on
related features. The information gap is live context, not features.

---

## Model Artifacts

```
models/ipl_v4/
├── champion_model.joblib          # XGBLogRegEnsemble (25 features)
├── isotonic_calibrator.pkl        # Per-over OOF calibrators
├── oof_calibration_results.csv    # Detailed OOF metrics
├── OOF_CALIBRATION_REPORT.md      # Auto-generated report
├── training_metadata.json         # Training config + sample counts
└── (NO league_calibrators/)       # NOT needed — biases are near-zero
```

**Feature Store:** `data/ipl_feature_store_v3/` (shared with v3)

---

## Production Status

**v4 is NOT yet in production.** Current production is v3 (iso only, no bias/blend).

Decision criteria for promoting v4:
- [x] OOS beats v3 (0.1470 vs 0.1484, +1.0% improvement) ✅
- [x] Simpler pipeline (2-step vs 4-step) ✅
- [ ] Need more OOS data (12 matches is thin)
- [ ] Update launcher.py, live_streamlit_app.py, dashboard config

---

## Comparison: v3 vs v4 Pipeline Complexity

| Aspect | v3 | v4 |
|--------|----|----|
| Pipeline steps | 4 (iso → bias → blend) | 2 (iso only) |
| Calibrator files | 3 (isotonic + logit_bias + league_cal) | 1 (isotonic) |
| Parameters to tune | ~8 (6 biases + blend alpha + blend window) | 0 |
| OOS Brier | 0.1484 (iso) / 0.1482 (full) | 0.1470 |
| Maintenance risk | High (biases can drift) | Low (just isotonic) |
| Resource calc params | fixed midpoint=9.5 | adaptive midpoint + no wicket penalty |

**Recommendation:** Promote v4 to production once 20+ OOS matches validate the improvement.

---

## Appendix: FormatConfig Changes (Backward Compatible)

New fields added to `FormatConfig` dataclass:

```python
rrr_midpoint_slope: float = 0.0    # Per-over midpoint adjustment (0.0 = no change)
chase_wicket_weight: float = 1.0   # 0.0 = disable wicket penalty, 1.0 = full penalty
```

**IPL config:** `rrr_midpoint_slope=0.134, chase_wicket_weight=0.0`
**All other leagues:** `rrr_midpoint_slope=0.0, chase_wicket_weight=1.0` (unchanged behavior)

These defaults ensure zero impact on BBL, ILT20, SA20, WPL, ODI, or any other league.
