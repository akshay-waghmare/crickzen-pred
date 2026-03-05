# ODI Monte Carlo Standalone Predictor

**Version**: v1 | **Created**: 2026-02-28 | **Branch**: `009-odi-mc-predictor`

## Overview

The ODI MC Predictor enables live win probability predictions for any ODI (50-over) cricket match using Monte Carlo simulation alone — no trained ML model or feature store required. It extends the existing T20 MC simulation engine with:

- **4-phase ODI system**: Powerplay (1-10), Middle (11-34), Setup (35-40), Death (41-50)
- **Empirical distributions**: Extracted from 1,760 male ODIs (2010+, Cricsheet)
- **Resource-based evaluation**: Uses `FormatConfig.odi()` with par=257.7, DLS tables, and wicket penalties
- **Optional enrichments**: Partnership momentum, new batsman factor, pitch deterioration

## Quick Start

### Live Prediction (MC-Only)
```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_ODI_MATCH_URL" \
  --mc-only \
  --output-json data/odi_prediction.json
```

No `--model-dir` or `--feature-store-dir` required in MC-only mode.

### With State Recording
```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_ODI_MATCH_URL" \
  --mc-only \
  --record-states \
  --output-json data/odi_prediction.json
```

## Architecture

### How It Works

1. **CREX scraper** extracts live match state (score, wickets, overs, batting/bowling teams)
2. **Format detection**: `total_overs >= 40` triggers ODI mode → `FormatConfig.odi()`
3. **MC simulation engine** runs 5,000 simulations from current match state to completion
4. **Ball-by-ball sampling** uses empirical phase-specific run distributions and wicket probabilities
5. **Terminal evaluation** uses `ResourceFeatureCalculator` with ODI par score (257.7) and DLS tables
6. **Win probability** = fraction of simulations won by batting team (optionally calibrated)

### Phase System

| Phase | Overs | Balls | Key Characteristics |
|-------|-------|-------|---------------------|
| Powerplay | 1-10 | 60 | Field restrictions, RPO ~4.68, Wicket ~2.30% |
| Middle | 11-34 | 144 | Accumulation, RPO ~4.80, Wicket ~2.15% |
| Setup | 35-40 | 36 | Acceleration, RPO ~5.61, Wicket ~3.05% |
| Death | 41-50 | 60 | Max aggression, RPO ~7.10, Wicket ~5.47% |

The 4-phase ODI system (vs T20's 3 phases) captures the distinct "setup" phase where teams accelerate before the death overs — a hallmark of modern ODI cricket.

### Run Distributions (Empirical)

Extracted from 935,224 balls across 1,760 male ODIs (2010+):

| Runs | Powerplay | Middle | Setup | Death |
|------|-----------|--------|-------|-------|
| 0 (dot) | 63.5% | 50.8% | 45.8% | 36.4% |
| 1 | 20.2% | 36.4% | 38.5% | 42.3% |
| 2 | 4.2% | 4.8% | 5.7% | 8.1% |
| 3 | 1.0% | 0.5% | 0.5% | 0.6% |
| 4 | 10.0% | 6.2% | 7.5% | 8.9% |
| 5 | 0.2% | 0.1% | 0.1% | 0.1% |
| 6 | 1.0% | 1.2% | 1.9% | 3.7% |

### Wicket Multiplier Table

Adjusts base wicket probability by wickets already fallen (0-9):

| Wickets Down | Multiplier | Effect |
|:------------:|:----------:|--------|
| 0 | 0.84 | Lower risk with full batting lineup |
| 1 | 0.79 | Slightly lower risk |
| 2 | 0.75 | Lowest risk — established partnership typical |
| 3 | 0.82 | Below average risk |
| 4 | 0.95 | Near baseline |
| 5 | 1.12 | Slightly above baseline |
| 6 | 1.39 | Elevated risk — tail approaching |
| 7 | 1.77 | High risk — late order |
| 8 | 2.00 | Clamped — tail ender |
| 9 | 2.00 | Clamped — last wicket pair |

## Empirical Distribution Extraction

### Source
- **Input**: 3,085 Cricsheet ODI JSON files (`odis_json/`)
- **Filtered**: 1,760 male ODIs from 2010 onwards
- **Total balls**: 935,224 | **Total wickets**: 25,740

### Re-extraction
```bash
python scripts/extract_odi_phase_distributions.py \
  --input-dir odis_json \
  --output data/phase_distributions_odi.json \
  --gender male \
  --min-year 2010 \
  --verbose
```

Options:
- `--gender male|female` — Filter by gender
- `--min-year YYYY` — Only include matches from this year onwards
- `--verbose` — Print per-phase statistics during extraction

### Output Format
```json
{
  "format": "odi",
  "gender": "male",
  "total_matches": 1760,
  "total_balls": 935224,
  "run_dist": { "powerplay": {...}, "middle": {...}, "setup": {...}, "death": {...} },
  "wicket_prob": { "powerplay": 0.023, "middle": 0.0215, "setup": 0.0305, "death": 0.0547 },
  "wicket_multiplier": { "0": 0.84, ... "9": 2.61 },
  "expected_run_rates": { "powerplay": 4.68, "middle": 4.80, "setup": 5.61, "death": 7.10 }
}
```

## MC Calibration (Optional)

Train Platt/isotonic calibrators on historical ODI data to improve Brier score:

```bash
python scripts/train_odi_mc_calibrator.py \
  --input-dir odis_json \
  --output-dir models/odi_mc_v1 \
  --gender male \
  --min-year 2010 \
  --oof
```

This produces:
- `mc_calibrators_innings_phase.pkl` — 8 calibrators (2 innings × 4 ODI phases)
- `mc_calibrators_innings.pkl` — 2 calibrators (1 per innings, fallback)

The live predictor loads calibrators automatically when present in the model directory.

### Calibrator Loading Priority
1. `mc_calibrators_innings_phase.pkl` (InningsPhaseCalibrators — 8 phase-specific)
2. `mc_calibrators_innings.pkl` (InningsMCCalibrators — 2 innings-specific)
3. `mc_calibrator.pkl` (legacy single MCCalibrator)

## MC Enrichments

Three optional enrichment factors improve simulation realism. Enable with `enrichments=True` on `NextBallSampler`:

### 1. Partnership Momentum
After 20+ balls without a wicket, established partnerships have a 3-6% chance of upgrading dots/singles/twos to boundaries (4s). Scales with partnership length.

### 2. New Batsman Factor
Within 10 balls of a wicket falling, the new batsman has a 0-15% chance of converting singles/twos to dot balls. Linearly decaying effect. Boundaries (4/6) are unaffected.

### 3. Pitch Deterioration
After 40% of the innings is bowled, wicket probability gradually increases (0-4% additional probability) to simulate pitch wear and bowler fatigue patterns.

## Backtesting

Compare enriched vs base MC predictions on completed ODI matches:

```bash
python scripts/backtest_enriched_mc.py \
  --input-dir odis_json \
  --gender male \
  --min-year 2020 \
  --n-sims 5000 \
  --verbose
```

Reports Brier score comparison between base and enriched MC simulations.

## Files Modified

| File | Change |
|------|--------|
| `src/bbl_pipeline/simulation/state.py` | `total_balls` validation extended to 6-300 |
| `src/bbl_pipeline/simulation/config.py` | ODI phase system, run distributions, wicket probabilities |
| `src/bbl_pipeline/simulation/sampler.py` | Dynamic phase loading, ODI distributions, enrichments |
| `src/bbl_pipeline/simulation/evaluator.py` | ODI format detection → `FormatConfig.odi()` |
| `src/bbl_pipeline/calibration/mc_calibrator.py` | ODI-aware `over_to_phase()`, 4-phase calibrators |
| `src/bbl_pipeline/inference/crex_live_predictor.py` | MC-only ODI mode, format detection, calibrator loading |

## Files Created

| File | Purpose |
|------|---------|
| `scripts/extract_odi_phase_distributions.py` | Extract empirical distributions from Cricsheet ODI JSONs |
| `scripts/train_odi_mc_calibrator.py` | Train MC calibrators on historical ODI data |
| `scripts/backtest_enriched_mc.py` | Compare base vs enriched MC Brier scores |
| `data/phase_distributions_odi.json` | Empirical ODI phase distributions (1,760 matches) |
| `tests/unit/test_odi_mc.py` | 98 ODI unit tests |
| `tests/integration/test_odi_predictor.py` | 16 ODI integration tests |

## Test Suite

```bash
# ODI unit tests (98 tests)
pytest tests/unit/test_odi_mc.py -v

# ODI integration tests (16 tests)
pytest tests/integration/test_odi_predictor.py -v

# All ODI tests (114 tests)
pytest tests/unit/test_odi_mc.py tests/integration/test_odi_predictor.py -v

# Full suite including T20 regression check
pytest tests/ -v
```

### Test Coverage

| Test Class | Tests | Focus |
|------------|:-----:|-------|
| TestMatchStateODI | 7 | MatchState creation and validation for 300 balls |
| TestMatchStateODIOperations | 8 | apply_outcome, innings completion, overs_completed |
| TestODIPhaseSystem | 11 | 4-phase boundaries, get_phase() for ODI |
| TestEvaluatorODIDetection | 8 | FormatConfig.odi() selection by evaluator |
| TestMatchStatePhaseIntegration | 4 | MatchState ↔ phase system integration |
| TestODIConfigConstants | 9 | Embedded ODI distributions and defaults |
| TestNextBallSamplerODI | 12 | Sampler with ODI distributions, dynamic phases |
| TestODIMCSimulationIntegration | 4 | End-to-end ODI simulation runs |
| TestOverToPhaseODI | 8 | over_to_phase() with ODI boundaries |
| TestInningsPhaseCalibratorsODI | 7 | 4-phase calibrator support |
| TestResourceWinProbODI | 9 | Resource evaluator for known ODI scenarios |
| TestPartnershipMomentum | 3 | Partnership boundary enrichment |
| TestNewBatsmanFactor | 3 | New batsman dot ball enrichment |
| TestPitchDeterioration | 3 | Pitch wear wicket enrichment |
| TestEnrichedMCSimulation | 3 | Enriched vs base simulation comparison |
| TestODIMCSimulationEndToEnd | 4 | Full simulation pipeline (integration) |
| TestODIFormatConfigIntegration | 3 | FormatConfig.odi() integration |
| TestODIMCProbabilityRealism | 5 | Realistic probability outputs |
| TestODISamplerLeagueDetection | 4 | League name → ODI distribution loading |

## Performance

- **Target**: < 500ms per ball with 5,000 simulations (SC-004)
- **Typical**: ~100-300ms per ball depending on innings stage
- **Bottleneck**: MC simulation loop (NumPy vectorized where possible)

## Limitations

- **MC-only accuracy**: Expected ~15% worse Brier than trained ML model (0.185 vs 0.161)
- **No team/player strength**: MC-only assumes teams are equally skilled (0.5 base win rate)
- **No venue effects**: Venue-specific scoring patterns not incorporated without feature store
- **Calibration optional**: Uncalibrated MC predictions may have systematic bias; train calibrators for production use
- **Reduced overs**: DLS-revised ODI targets use existing `FormatConfig.odi()` DLS tables but phase scaling for heavily reduced ODIs (< 20 overs) may be suboptimal

## Model Registry Entry

The ODI MC predictor is registered in `models/model_registry.json` under the `odi_mc` key. See the registry for full artifact paths and metadata.
