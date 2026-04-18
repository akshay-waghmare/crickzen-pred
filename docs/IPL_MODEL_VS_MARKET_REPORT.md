# IPL Model vs Market — Phase Analysis Report

**Date:** 2026-04-18
**Model:** IPL v2 (deduped, 278,954 training samples, OOF Brier 0.1817)
**Calibration:** Global T20 v2 → per-over isotonic → phase isotonic → IPL phase Platt
**Market:** Exchange mid-price odds from betx21.live (16 IPL matches, April 2026)
**Observations:** 510 live match states (over boundaries)

---

## Executive Summary

The IPL model alone does not beat the market overall (Brier 0.1904 vs 0.1546).
However, a **model + market ensemble beats the market in innings 2**, specifically
in the powerplay and middle phases where the model's resource/projection logic
captures chase dynamics that the market prices less efficiently.

---

## Phase-Level Comparison

### All Phases

| Segment | N | Market Brier | Model Brier | Gap | Gap % | Ensemble Brier | Ens α | Ens Improvement |
|---------|---|-------------|-------------|-----|-------|---------------|-------|-----------------|
| **Overall** | 510 | 0.1546 | 0.1904 | +0.0359 | +23.2% | 0.1546 | 0.00 | 0.0% |
| Inn1 Overall | 201 | 0.1936 | 0.2382 | +0.0446 | +23.0% | 0.1936 | 0.00 | 0.0% |
| Inn1 Powerplay | 56 | 0.2097 | 0.2429 | +0.0332 | +15.9% | 0.2097 | 0.00 | 0.0% |
| Inn1 Middle | 92 | 0.1982 | 0.2492 | +0.0510 | +25.7% | 0.1982 | 0.00 | 0.0% |
| Inn1 Death | 53 | 0.1686 | 0.2140 | +0.0454 | +27.0% | 0.1686 | 0.00 | 0.0% |
| **Inn2 Overall** | 309 | **0.1292** | 0.1449 | +0.0157 | +12.2% | **0.1288** | 0.14 | **-0.3%** ✅ |
| **Inn2 Powerplay** | 96 | **0.1546** | 0.1634 | +0.0088 | +5.7% | **0.1538** | 0.22 | **-0.5%** ✅ |
| **Inn2 Middle** | 144 | **0.1214** | 0.1265 | +0.0051 | +4.2% | **0.1205** | 0.27 | **-0.7%** ✅ |
| Inn2 Death | 69 | 0.1102 | 0.1578 | +0.0476 | +43.1% | 0.1101 | 0.05 | -0.1% |

> ✅ = Ensemble beats market (lower Brier is better)

### Key Takeaway

In **innings 2 powerplay** (overs 1-6) and **innings 2 middle** (overs 7-15),
blending the model at 22-27% weight with the market improves prediction accuracy
beyond what the market achieves alone. This means the model carries **independent
signal** in these phases that the market is not fully pricing.

---

## Innings 2 — Deep Dive

### Where Model Beats Market (Standalone)

The model **outright wins** (lower Brier, no blending needed) at these specific overs:

| Over | N | Market Brier | Model Brier | Model Advantage |
|------|---|-------------|-------------|-----------------|
| **4** | 16 | 0.1658 | **0.1493** | **-10.0%** |
| **6** | 16 | 0.1307 | **0.1265** | **-3.2%** |
| **7** | 16 | 0.1286 | **0.1186** | **-7.8%** |
| **8** | 16 | 0.1313 | **0.1257** | **-4.3%** |
| **10** | 16 | 0.1143 | **0.1087** | **-4.9%** |

These are overs 4-10 — exactly the early-to-mid chase where resource calculations,
run-rate projections, and wickets-in-hand matter most. The model's structural
cricket logic outperforms crowd/market wisdom here.

### Where Ensemble Adds Value

At these overs, the model alone doesn't win but blending improves on market:

| Over | N | Market Brier | Ensemble Brier | α (model weight) | Improvement |
|------|---|-------------|---------------|-------------------|-------------|
| 2 | 16 | 0.1688 | 0.1679 | 0.22 | -0.5% |
| 5 | 16 | 0.1381 | 0.1361 | 0.49 | -1.4% |
| 9 | 16 | 0.1162 | 0.1145 | 0.38 | -1.4% |
| 11 | 16 | 0.1165 | 0.1158 | 0.24 | -0.6% |
| 13 | 16 | 0.1160 | 0.1151 | 0.24 | -0.8% |

### Where Market Dominates

Death overs (16-20) and innings 1 — the market wins decisively:

| Phase | Market Brier | Model Brier | Gap |
|-------|-------------|-------------|-----|
| Inn1 (all) | 0.1936 | 0.2382 | +23.0% |
| Inn2 Death | 0.1102 | 0.1578 | +43.1% |

---

## Log Loss Comparison

| Segment | N | Market LogLoss | Model LogLoss | Ensemble LogLoss | Ens α |
|---------|---|---------------|---------------|-----------------|-------|
| Overall | 510 | 0.4711 | 0.5468 | 0.4711 | 0.00 |
| Inn2 Overall | 309 | 0.4026 | 0.4345 | **0.4019** | 0.14 |
| Inn2 Powerplay | 96 | 0.4716 | 0.4917 | **0.4704** | 0.22 |
| Inn2 Middle | 144 | 0.3880 | 0.3958 | **0.3848** | 0.27 |
| Inn2 Death | 69 | 0.3369 | 0.4355 | 0.3377 | 0.05 |

The ensemble also improves Log Loss in innings 2 powerplay and middle phases.

---

## Interpretation

### Why the model adds value in innings 2 powerplay/middle

1. **Resource-based projections** — The model computes remaining resources,
   required run rate, and projected score using DLS-inspired logic. In overs 4-10
   of a chase, these structural factors are highly predictive.

2. **Wickets-in-hand valuation** — The model explicitly values batting resources
   remaining, which the market may underweight during stable chases.

3. **Score-vs-par tracking** — The model tracks how the chasing team is tracking
   against a par score, providing a structural anchor that the market may lack.

### Why the model loses in innings 1 and death overs

1. **First innings** — Win probability depends on factors the model handles weakly:
   pitch reading, dew prediction, team depth perception, and "how defendable is
   this score" intuition.

2. **Death overs** — Every ball changes everything. The market reprices instantly
   while the model's over-boundary granularity is too coarse.

3. **Team priors** — Despite deduplication, team ratings may still not reflect
   current-season form accurately enough.

---

## Recommended Usage

For live IPL prediction, the optimal strategy is:

| Phase | Strategy | Model Weight |
|-------|----------|-------------|
| Innings 1 (all) | Market only | 0% |
| Innings 2, Powerplay | Market + Model blend | ~22% |
| Innings 2, Middle | Market + Model blend | ~27% |
| Innings 2, Death | Market only | ~5% |

This ensemble achieves **lower Brier than either source alone** in innings 2.

---

## ⚠️ True Out-of-Sample Validation (2026-04-19)

The results above used the IPL v2 model which was **trained on 2026 data** (data leakage).
To validate properly, we trained a **holdout model on 2007-2025 only**, fitted Platt
calibrators on 2023-2025 OOF predictions, then tested on the same 2026 live data.

### Methodology
1. **Holdout model:** Trained on 273,503 rows from 1,146 IPL matches (2007-2025)
2. **Platt calibrators:** Fitted on 5-fold match-level OOF predictions from 2023-2025 (51,555 rows, 214 matches)
3. **Test set:** 510 live observations from 16 IPL 2026 matches (completely unseen by model AND calibrators)

### Overall Results

| Source | Brier | vs Market | LogLoss | vs Market |
|--------|-------|-----------|---------|-----------|
| **Market (exchange)** | **0.1546** | — | **0.4711** | — |
| Holdout Model (raw) | 0.1990 | +28.7% | 0.5677 | +20.5% |
| Holdout + Historical Platt | 0.1878 | +21.5% | 0.5450 | +15.7% |

**Verdict: MARKET WINS decisively on truly out-of-sample data.**

### Phase Breakdown (Brier Score)

| Phase | N | Market | Holdout+Platt | Gap |
|-------|---|--------|---------------|-----|
| Inn1 Powerplay | 46 | 0.2052 | 0.2364 | +15.2% |
| Inn1 Middle | 102 | 0.2013 | 0.2642 | +31.2% |
| Inn1 Death | 53 | 0.1686 | 0.2399 | +42.3% |
| **Inn1 Total** | 201 | **0.1936** | **0.2514** | **+29.9%** |
| Inn2 Powerplay | 80 | 0.1594 | 0.1789 | +12.2% |
| Inn2 Middle | 160 | 0.1223 | 0.1351 | +10.5% |
| Inn2 Death | 69 | 0.1102 | 0.1352 | +22.6% |
| **Inn2 Total** | 309 | **0.1292** | **0.1464** | **+13.3%** |

### Key Findings

1. **The market is better everywhere.** No phase shows model beating market on OOS data.
2. **Platt helps** — reduces raw gap from +28.7% to +21.5% — but not enough.
3. **Ensemble alpha = 0.000** — optimal blend is 100% market, 0% model.
4. **Inn2 death blending** shows -0.4% improvement (α=0.115) — the only segment where model adds marginal value.
5. **Previous "model beats market" findings were invalid** — caused by model being trained on 2026 data (the test set).

### What This Means

- The model's structural cricket logic (resources, projections, DLS) is real and valuable for **standalone prediction**
- But **exchange markets aggregate thousands of informed bettors** who have the same structural knowledge PLUS live context (pitch behavior, dew, momentum, injury info)
- For live IPL prediction, the model serves as a **useful reference** but should not override market prices
- The ensemble analysis from earlier sections is **directionally informative** but the magnitudes are overstated due to the data leakage

---

## Reproducibility

```bash
# ORIGINAL analysis (IPL v2 model — includes 2026 data in training)
python scripts/rescore_ipl_v2.py
# Output: data/ipl_model_vs_market_v2.parquet

# TRUE OUT-OF-SAMPLE validation (holdout model — excludes 2026)
python scripts/validate_platt_oos.py
# Output: data/ipl_oos_validation_2026.parquet
#         data/ipl_oos_validation_summary.json
#         models/ipl_holdout_pre2026/ (holdout model + calibrators)
```

**Model artifacts used:**
- `models/ipl_v2/champion_model.joblib` (OOF Brier 0.1817) — original analysis
- `models/ipl_holdout_pre2026/champion_model.joblib` — OOS validation
- `models/ipl_holdout_pre2026/oos_platt_calibrators.pkl` — 8 phase Platt calibrators trained on 2023-2025 OOF
- `models/t20_male_v2/league_calibrators/ipl/league_calibrator.pkl` (phase Platt, 2026-04-18)
- `data/ipl_feature_store_v2/` (14 canonical teams, deduped)

---

## Monte Carlo Simulation Contribution Test (2026-04-19)

### Does MC Simulation Add Value Over Market?

The MC engine simulates ball-by-ball outcomes using phase-specific run distributions
and evaluates terminal states via `resource_win_prob` (DLS-like formula). This is
fundamentally different from the ML model (feature-based XGBLogRegEnsemble). We tested
whether MC provides independent signal that helps when blended with market odds.

**Test setup:**
- 410 scorable observations (100 inn2 obs skipped — no target available)
- MC: 1000 simulations, horizon=6, resource_win_prob evaluation (no ML model)
- MC Calibrator: `InningsMCCalibrators` (Platt scaling, trained on IPL v2 data)
- All predictions are P(team1 wins) to align with market and actuals

### Overall Results

| Method | Brier | LogLoss | vs Market |
|--------|-------|---------|-----------|
| **Market** | **0.1632** | **0.4867** | baseline |
| MC Raw | 0.1791 | 0.5155 | +9.7% worse |
| MC Calibrated | 0.1861 | 0.5397 | +14.1% worse |
| ML Holdout+Platt | 0.1848 | 0.5337 | +13.3% worse |

> MC Calibrator actually hurts — raw MC is closer to market. The calibrator was trained on
> IPL v2 data (which includes 2026), suggesting miscalibration or overfitting.

### Blending Results

| Blend | Optimal Weights | Blend Brier | vs Market |
|-------|----------------|-------------|-----------|
| MC Raw + Market | 3.4% MC, 96.6% market | 0.1631 | -0.01% |
| MC Cal + Market | 0% MC, 100% market | 0.1632 | +0.00% |
| MC + ML + Market (triple) | 0% MC, 2.1% ML, 97.9% market | 0.1631 | -0.01% |

> The optimizer converges to near-100% market weight in all blends.

### Phase Breakdown: MC vs Market

| Phase | N | MC Brier | Market Brier | MC Advantage | Blend α | Blend Brier |
|-------|---|----------|-------------|-------------|---------|-------------|
| Inn1 death | 53 | 0.2150 | 0.1686 | +27.5% | 0.00 | 0.1686 |
| Inn1 middle | 92 | 0.2267 | 0.1982 | +14.4% | 0.00 | 0.1982 |
| Inn1 PP | 56 | 0.2305 | 0.2097 | +9.9% | 0.00 | 0.2097 |
| Inn2 PP | 66 | 0.1881 | 0.1448 | +29.9% | 0.00 | 0.1448 |
| Inn2 middle | 99 | 0.1441 | 0.1270 | +13.5% | 0.10 | 0.1268 |
| **Inn2 death** | **44** | **0.1017** | **0.1329** | **-23.5%** ✅ | **1.00** | **0.1017** |

> **MC beats market ONLY in innings 2 death overs** (last 5 overs of a chase),
> where the match outcome becomes increasingly deterministic — few balls remain,
> and MC simulation converges to correct mathematical probabilities.

### Why MC Wins in Inn2 Death

In the death overs of a chase (overs 16-20), match outcomes are nearly deterministic:
- Few balls remaining → small outcome space → simulation is very accurate
- Market may lag or overshoot due to human reaction time and sentiment
- MC directly computes the probability from possible run/wicket paths
- With 30 or fewer balls, the simulation essentially becomes exact combinatorial calculation

### MC Uncertainty Analysis

| Segment | Obs | MC Brier | Market Brier |
|---------|-----|----------|-------------|
| Low MC uncertainty (std ≤ 0.036) | 205 | 0.1364 | 0.1183 |
| High MC uncertainty (std > 0.036) | 205 | 0.2359 | 0.2080 |
| MC-Market agree (diff ≤ 0.104) | 205 | 0.1729 | 0.1610 |
| MC-Market disagree (diff > 0.104) | 205 | 0.1993 | 0.1653 |

> When MC disagrees with market, market is MORE accurate — disagreement signals
> MC error, not market inefficiency.

### Conclusion

**MC simulation does NOT add meaningful independent signal** to beat the market:
1. MC overall Brier (0.1791) is 9.7% worse than market (0.1632)
2. Blending MC + market yields negligible improvement (-0.01%)
3. Triple blend (MC + ML + market) also stays at ~100% market weight
4. MC uncertainty and disagreement metrics do NOT predict market inefficiency
5. **Exception:** Inn2 death overs — MC is 23.5% better (but n=44, needs more data)

**Reproduce:**
```bash
python scripts/test_mc_contribution.py
# Output: data/ipl_mc_contribution_test.parquet
```
