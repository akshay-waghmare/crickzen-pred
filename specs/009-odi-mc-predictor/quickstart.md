# Quickstart: ODI Monte Carlo Standalone Predictor

**Feature**: `009-odi-mc-predictor`  
**Branch**: `009-odi-mc-predictor`

## Prerequisites

- Python 3.10+
- Repository cloned with dependencies installed: `pip install -e .`
- ODI JSON match files in `odis_json/` (3,085 files already present)
- For live predictions: CREX match URL for an ODI match

## Implementation Order

### Step 1: Fix MatchState Validation (5 min)

Edit `src/bbl_pipeline/simulation/state.py`:
```python
# Change upper bound from 120 to 300
if not (6 <= self.total_balls <= 300 and self.total_balls % 6 == 0):
```

### Step 2: Add ODI Phase Support to SimConfig (30 min)

Edit `src/bbl_pipeline/simulation/config.py`:
- Add `ODI_PHASES = ("powerplay", "middle", "setup", "death")`
- Add `get_odi_phase_boundaries()` returning `(60, 204, 240, 300)` (ball counts)
- Update `get_phase()` to detect ODI (total_balls=300) and use 4-phase system
- Add ODI-specific `RUN_DIST` and `WICKET_PROB` constants

### Step 3: Extract ODI Phase Distributions (1 hr)

Create `scripts/extract_odi_phase_distributions.py`:
```bash
python scripts/extract_odi_phase_distributions.py \
  --input-dir odis_json \
  --output data/phase_distributions_odi.json \
  --gender male --min-year 2010
```

### Step 4: Update Sampler for Dynamic Phases (30 min)

Edit `src/bbl_pipeline/simulation/sampler.py`:
- Replace hardcoded `("powerplay", "middle", "death")` with dynamic phase list
- Load phases from distribution file keys
- Support `phase_distributions_odi.json`

### Step 5: Fix Evaluator for ODI (15 min)

Edit `src/bbl_pipeline/simulation/evaluator.py`:
- Add format detection in `_get_calculator()`: `total_balls > 120` → `FormatConfig.odi()`
- Use existing `FormatConfig.odi()` constants (par=257.7, DLS tables, etc.)

### Step 6: Update MC Calibrator (30 min)

Edit `src/bbl_pipeline/calibration/mc_calibrator.py`:
- Make `over_to_phase()` format-aware with ODI boundaries
- Support 4-phase `InningsPhaseCalibrators`

### Step 7: Enable MC-Only for ODI in Live Predictor (1 hr)

Edit `src/bbl_pipeline/inference/crex_live_predictor.py`:
- Make `--model-dir` optional when `--mc-only` is set
- Detect ODI format from `total_overs >= 40`
- Pass `FormatConfig.odi()` through MC pipeline
- Output format-aware JSON results

## Verification

### Unit Tests
```bash
pytest tests/unit/test_odi_mc.py -v
```

### Integration Test
```bash
pytest tests/integration/test_odi_predictor.py -v
```

### Manual Smoke Test
```bash
# MC-only prediction for a live ODI
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "https://crex.live/scoreboard/OGQ/1/..." \
  --mc-only \
  --output-json data/odi_prediction.json
```

## Key Files Modified

| File | Change |
|------|--------|
| `simulation/state.py` | Extend `total_balls` to 300 |
| `simulation/config.py` | Add 4-phase ODI system |
| `simulation/sampler.py` | Dynamic phase iteration |
| `simulation/evaluator.py` | ODI format detection |
| `calibration/mc_calibrator.py` | ODI-aware `over_to_phase()` |
| `inference/crex_live_predictor.py` | MC-only without model-dir |

## Key Files Created

| File | Purpose |
|------|---------|
| `scripts/extract_odi_phase_distributions.py` | Extract distributions from ODI JSONs |
| `tests/unit/test_odi_mc.py` | Unit tests for ODI MC |
| `tests/integration/test_odi_predictor.py` | End-to-end integration test |
