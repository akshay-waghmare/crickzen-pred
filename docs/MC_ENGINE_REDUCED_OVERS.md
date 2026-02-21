# Monte Carlo Engine: Reduced-Over Support & Calibration

**Version**: 2.0  
**Date**: February 21, 2026  
**Feature**: 008-t20-reduced-overs  
**Status**: Production Ready ✅

## Overview

The MC simulation engine now supports **rain-affected / DLS reduced-over T20 matches** (5–20 overs per side). When `total_overs < 20`, the system automatically uses MC simulation exclusively (bypassing the XGBLogRegEnsemble model), with phase boundaries, par scores, and resource calculations scaled via DLS resource curves. A Platt-scaling calibrator corrects systematic MC biases for betting-grade probability output.

This guide covers:
1. How to use the MC engine for standard and reduced-over matches
2. How the MC Platt calibrator works
3. How to retrain the calibrator
4. Architecture and key files

---

## Quick Start

### Standard 20-Over Match

```python
from bbl_pipeline.simulation import MatchState, simulate

state = MatchState(
    innings=2,
    score=80,
    wickets_lost=2,
    balls_remaining=60,
    target_runs=170,
    batting_team="Sydney Sixers",
    bowling_team="Sydney Thunder",
    league="bbl",
    # total_balls defaults to 120 (20 overs)
)

result = simulate(state, horizon=6, n_simulations=1000)
print(f"Win prob: {result.mean_prob:.1%}")  # e.g., 45.2%
```

### Reduced-Over Match (e.g., 15-over DLS)

```python
state = MatchState(
    innings=2,
    score=80,
    wickets_lost=2,
    balls_remaining=30,       # 5 overs left in a 15-over match
    target_runs=135,          # DLS revised target
    batting_team="Brisbane Heat",
    bowling_team="Sydney Thunder",
    league="bbl",
    total_balls=90,           # 15 overs × 6 = 90 balls
)

result = simulate(state, horizon=6, n_simulations=1000)
print(f"Win prob: {result.mean_prob:.1%}")  # Calibrated automatically
```

### FormatConfig for Reduced Overs

```python
from bbl_pipeline.features.format_config import FormatConfig

# Standard 20-over
config_20 = FormatConfig.t20()          # par=160, phases: pp=6, mid=14, death=18

# Reduced 15-over
config_15 = FormatConfig.t20_reduced(15) # par≈133, phases: pp=5, mid=11, death=12

# Identity: t20_reduced(20) == t20()
assert FormatConfig.t20_reduced(20) == FormatConfig.t20()

# Super over
config_1 = FormatConfig.t20_reduced(1)   # par≈13, total_balls=6
```

---

## MC Platt Calibrator

### What It Does

The raw MC simulation output has systematic biases — it tends to be over-confident in death overs and slightly under-confident early. The Platt calibrator applies a logistic regression on `logit(mc_raw_prob)` to correct these biases.

**Before calibration (BBL backtest):**
- Reduced-over: Brier=0.3208, ECE=0.3466 (severe over-confidence)
- Standard 20-over: Brier=0.1307, ECE=0.1280

**After calibration:**
- Reduced-over: Brier=0.1417 (-56%), ECE=0.0338 (-90%)
- Standard 20-over: Brier=0.1234 (-6%), ECE=0.0931 (-27%)

### How It Works

1. **Training**: MC predictions are run against historical match data at each over boundary
2. **Fitting**: A `LogisticRegression` is fit on `logit(mc_prob)` → `actual_outcome`
3. **Inference**: The fitted model transforms raw MC probabilities into calibrated ones
4. **Storage**: Saved as `mc_calibrator.pkl` in the model directory

### Automatic Application

The calibrator is **automatically applied** during `simulate()` and `simulate_vectorized()` when:
- `mc_calibrator.pkl` exists in the model directory
- The simulation is NOT using an ML model for terminal evaluation (i.e., using the resource heuristic)

No code changes needed — just place `mc_calibrator.pkl` in your model directory.

---

## Training the MC Calibrator

### Via CLI (Recommended)

```bash
# Train from Cricsheet JSON match files
bbl-pipeline calibrate-mc \
  --json-dir bbl_male_json \
  --model-dir models/t20_male_v2 \
  --league bbl \
  --max-matches 200 \
  --n-sims 200 \
  --seed 42
```

**Output:**
```
MC calibrator training started    json_dir=bbl_male_json selected_matches=80 n_sims=200
MC prediction collection complete matches=80 predictions=1455
MC calibrator saved               path=models/t20_male_v2/mc_calibrator.pkl

MC Calibrator Training Summary
==================================================
  Matches analyzed:   80
  Prediction points:  1455
  Train/Val split:    1164/291
  
  Validation Metrics:
  Metric           Raw    Calibrated      Delta
  ------------------------------------------
  Brier         0.1310      0.1282    -0.0028
  ECE           0.0644      0.0345    -0.0299
```

### Via Retrain Pipeline

The MC calibrator is automatically trained as step 6/7 in the `retrain` pipeline for T20 models:

```bash
bbl-pipeline retrain --league bbl --version v13
```

The pipeline runs: ingest → process → train → generate-oof → analyze-oof → **calibrate-mc** → update-registry

If `calibrate-mc` fails, the pipeline continues (non-fatal warning).

### Programmatic API

```python
from bbl_pipeline.calibration.mc_trainer import train_mc_calibrator

result = train_mc_calibrator(
    json_dir="bbl_male_json",
    model_dir="models/t20_male_v2",
    league="bbl",
    max_matches=200,
    n_sims=200,
    seed=42,
)

print(result.summary())
print(f"Brier improvement: {result.brier_improvement:.4f}")
print(f"ECE improvement: {result.ece_improvement:.4f}")
```

---

## Architecture

### Key Files

| File | Purpose |
|------|---------|
| `src/bbl_pipeline/simulation/state.py` | `MatchState` dataclass with `total_balls` field |
| `src/bbl_pipeline/simulation/config.py` | `get_phase()` with dynamic phase boundaries, `get_scaled_phase_boundaries()` |
| `src/bbl_pipeline/simulation/engine.py` | `simulate()` / `simulate_vectorized()` with MC calibrator integration |
| `src/bbl_pipeline/simulation/evaluator.py` | `TerminalStateEvaluator` with format-aware `ResourceFeatureCalculator` caching |
| `src/bbl_pipeline/features/format_config.py` | `FormatConfig.t20_reduced()` factory method |
| `src/bbl_pipeline/calibration/mc_calibrator.py` | `MCCalibrator` — Platt scaling fit/predict/save/load |
| `src/bbl_pipeline/calibration/mc_trainer.py` | `train_mc_calibrator()` — backtest + fit pipeline |
| `src/bbl_pipeline/cli.py` | `calibrate-mc` CLI command |

### Data Flow

```
MatchState(total_balls=90)
  │
  ├─── get_phase(balls_remaining, total_balls=90)
  │       └── get_scaled_phase_boundaries(15) → (pp=5, mid=11)
  │
  ├─── NextBallSampler.sample(phase="death")
  │       └── Phase-specific run/wicket distributions
  │
  ├─── TerminalStateEvaluator.evaluate(terminal_state)
  │       └── _get_calculator(total_balls=90)
  │           └── FormatConfig.t20_reduced(15)
  │               └── ResourceFeatureCalculator(config)
  │                   └── resource_win_prob (raw heuristic)
  │
  └─── MCCalibrator.calibrate_batch(raw_probs)
          └── Platt scaling: sigmoid(a * logit(p) + b)
              └── Calibrated win probability (betting-grade)
```

### Phase Boundary Scaling

| Total Overs | Powerplay | Middle | Death Starts | Formula |
|:-----------:|:---------:|:------:|:------------:|---------|
| 20 | 1-6 | 7-15 | 16 | Standard T20 constants |
| 18 | 1-5 | 6-14 | 15 | `pp=round(18×0.30)=5` |
| 15 | 1-5 | 6-11 | 12 | `pp=round(15×0.30)=5` |
| 12 | 1-4 | 5-9 | 10 | `pp=round(12×0.30)=4` |
| 10 | 1-3 | 4-7 | 8 | `pp=round(10×0.30)=3` |
| 7 | 1-2 | 3-5 | 6 | `pp=max(2,round(7×0.30))=2` |
| 5 | 1-2 | 3 | 4 | `pp=max(2,round(5×0.30))=2` |

### Evaluator FormatConfig Caching

The `TerminalStateEvaluator` caches `ResourceFeatureCalculator` instances by `total_balls`:

```python
# First call with total_balls=90: creates FormatConfig.t20_reduced(15) + calculator
# Subsequent calls with total_balls=90: returns cached calculator
# Calls with total_balls=120: uses standard FormatConfig.t20() calculator
```

This ensures no performance overhead from creating FormatConfig instances per simulation.

---

## Live Prediction with Reduced Overs

### CLI Usage

```bash
# With explicit reduced overs (CLI override)
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/t20_male_feature_store_v2 \
  --league bbl \
  --total-overs 15 \
  --revised-target 156 \
  --output-json data/live_state.json

# Auto-detect from CREX page (recommended for live matches)
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/t20_male_feature_store_v2 \
  --league bbl \
  --output-json data/live_state.json
```

### Prediction Mode Routing

| Condition | Prediction Engine | Calibration |
|-----------|-------------------|-------------|
| `total_overs == 20` (default) | XGBLogRegEnsemble + MC | Standard per-over calibration chain |
| `total_overs < 20` | MC-only | Platt MC calibrator |
| Mode switch mid-match | Immediate switch, logged | Switch calibration method |

### CREX Auto-Detection

The live predictor automatically detects reduced overs from the CREX match page:
- **Revised target**: regex `r'(?:revised\s+)?target\s*[:\-]\s*(\d+)\s*\(?(?:d/?l/?s?|dls)\)?'`
- **Reduced overs**: regex `r'(\d+)\s+ov(?:er)?s?\s+(?:match|per\s+side|a\s+side)'`

Priority: CLI override → CREX auto-detect → default 20 overs

---

## Testing

```bash
# All reduced-over tests (14 tests)
pytest tests/test_reduced_overs.py -v

# Simulation tests (79 tests)
pytest tests/test_simulation.py -v

# Integration tests
pytest tests/integration/test_simulation_integration.py -v

# Full suite
pytest tests/ -v
```

### Test Coverage

| Category | Tests | File |
|----------|:-----:|------|
| Phase boundaries | 6 | `test_reduced_overs.py` |
| FormatConfig | 7 | `test_reduced_overs.py` |
| MatchState | 2 | `test_reduced_overs.py` |
| MC simulation | 2 | `test_reduced_overs.py` |
| Evaluator | 1 | `test_reduced_overs.py` |
| Regression (20-over) | 2 | `test_reduced_overs.py` |
| MCCalibrator | 5 | `test_reduced_overs.py` |

---

## Model Artifacts

After training with MC calibration, the model directory should contain:

```
models/t20_male_v2/
├── champion_model.joblib        # Main XGBLogRegEnsemble model
├── oof_calibrators.pkl          # OOF calibrators (phase/per-over)
├── mc_calibrator.pkl            # MC Platt scaling calibrator (NEW)
├── oof_calibration_results.csv  # Detailed metrics
├── OOF_CALIBRATION_REPORT.md    # Auto-generated report
└── league_calibrators/          # League-specific calibrators
```

---

## Calibration Results (BBL, 80 matches)

| Metric | Raw MC | Calibrated | Delta |
|--------|:------:|:----------:|:-----:|
| Brier (validation) | 0.1310 | 0.1282 | -0.0028 |
| ECE (validation) | 0.0644 | 0.0345 | -0.0299 |

### Reduced-Over Specific (30 DLS matches)

| Metric | Raw MC | Calibrated | Delta | Improvement |
|--------|:------:|:----------:|:-----:|:-----------:|
| Brier | 0.3208 | 0.1417 | -0.1791 | -56% |
| ECE | 0.3466 | 0.0338 | -0.3128 | -90% |

### Root Cause of Original Over-Confidence

The `TerminalStateEvaluator` always created `ResourceFeatureCalculator()` with default `FormatConfig.t20()` (20 overs, 120 balls). For reduced-over matches (e.g., 17 overs = 102 balls), the calculator thought there were 18 extra balls remaining, making required run rates appear drastically lower → extreme over-confidence.

**Fix**: Evaluator now creates format-aware calculators via `_get_calculator(total_balls)`. Standard matches unaffected (use default 120-ball config).

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/analyze_mc_calibration.py` | Analyze MC calibration metrics across matches (DLS/standard/both) |
| `scripts/simulate_reduced_over_match.py` | Demo: replay a real DLS match (BBL 1114863) with MC predictions |
| `scripts/train_mc_calibrator.py` | Train MC calibrator from training.parquet (alternative to CLI) |
| `scripts/train_mc_calibrator_from_json.py` | Train MC calibrator from Cricsheet JSON files (alternative to CLI) |

---

## Change Log

### v2.0 (February 21, 2026) — Reduced-Over Support

- ✅ `MatchState.total_balls` field (default 120, supports 6–120)
- ✅ Dynamic phase boundaries via `get_scaled_phase_boundaries(total_overs)`
- ✅ `FormatConfig.t20_reduced(total_overs)` factory with DLS-scaled par scores
- ✅ `TerminalStateEvaluator` format-aware calculator caching
- ✅ `MCCalibrator` Platt scaling (fit/predict/save/load)
- ✅ `train_mc_calibrator()` backtest + fit pipeline
- ✅ `calibrate-mc` CLI command
- ✅ Integrated into 7-step `retrain` pipeline
- ✅ CREX auto-detection of DLS target and reduced overs
- ✅ Match state schema extended with `total_overs`, `revised_target`
- ✅ 25+ tests covering phase boundaries, FormatConfig, MC simulation, calibration
- ✅ Zero regression on standard 20-over predictions

### v1.0 (January 19, 2026) — Initial Engine

- ✅ Initial implementation with 1-ball and 6-ball simulation
- ✅ Phase-based run/wicket distributions
- ✅ Temperature calibration support
- ✅ Betting decision support with Kelly criterion
