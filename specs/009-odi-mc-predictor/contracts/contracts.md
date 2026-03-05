# Contracts: ODI Monte Carlo Standalone Predictor

**Feature**: `009-odi-mc-predictor`  
**Date**: 2026-02-28

## CLI Contracts

### 1. MC-Only Live Prediction (Extension of existing CLI)

```
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url <CREX_URL> \
  --mc-only \
  [--model-dir <MODEL_DIR>] \
  [--output-json <JSON_PATH>] \
  [--record-states] \
  [--poll-interval <SECONDS>]
```

**Changes from current**:
- `--model-dir` becomes **optional** in `--mc-only` mode (was required)
- When `--model-dir` omitted: uses built-in ODI defaults, no calibration
- When `--model-dir` provided: loads calibrators and phase distributions from there

**Output contract** (JSON to stdout and `--output-json`):

```json
{
  "mode": "mc-only",
  "format": "odi",
  "batting_team": "Eastern Storm",
  "bowling_team": "Griqualand West",
  "score": "150/3",
  "overs": 30.0,
  "phase": "middle",
  "target": 299,
  "win_probability": {
    "batting_team": 0.682,
    "bowling_team": 0.318,
    "raw_mc_prob": 0.695,
    "calibrated": true,
    "calibration_method": "platt_innings"
  },
  "simulation": {
    "n_simulations": 5000,
    "horizon_balls": 6,
    "std": 0.042,
    "ci_low": 0.615,
    "ci_high": 0.749,
    "elapsed_ms": 340
  }
}
```

---

### 2. Phase Distribution Extraction Script

```
python scripts/extract_odi_phase_distributions.py \
  --input-dir <ODI_JSON_DIR> \
  --output <OUTPUT_JSON> \
  [--gender male|female] \
  [--min-year <YEAR>] \
  [--verbose]
```

**Input**: Directory of Cricsheet ODI JSON files  
**Output**: `phase_distributions_odi.json` (schema per data-model.md)

**Example**:
```
python scripts/extract_odi_phase_distributions.py \
  --input-dir odis_json \
  --output models/odi_v1/phase_distributions_odi.json \
  --gender male \
  --min-year 2010
```

**Stdout contract** (summary):
```
Processed 1,632 matches (876,432 balls)
Phase distributions:
  powerplay (overs 1-10):  4.82 RPO, 3.5% wicket rate, 16.7% boundary rate
  middle    (overs 11-34): 4.90 RPO, 3.8% wicket rate, 12.4% boundary rate
  setup     (overs 35-40): 5.71 RPO, 4.5% wicket rate, 17.1% boundary rate
  death     (overs 41-50): 7.32 RPO, 7.0% wicket rate, 23.2% boundary rate
Saved to: models/odi_v1/phase_distributions_odi.json
```

---

### 3. MC Calibrator Training Script

```
python scripts/train_odi_mc_calibrator.py \
  --input-file <FEATURES_PARQUET> \
  --output-dir <MODEL_DIR> \
  [--n-splits <CV_FOLDS>] \
  [--method platt|isotonic]
```

**Input**: ODI training features parquet (with `batting_team_won` outcome column)  
**Output**: `mc_calibrator.pkl` or `mc_calibrators_innings.pkl` in model directory

---

## Internal API Contracts

### 4. MatchState Constructor (Extended)

```python
# Before (T20 only):
MatchState(total_balls=120, ...)  # OK
MatchState(total_balls=300, ...)  # ValueError!

# After (T20 + ODI):
MatchState(total_balls=120, ...)  # OK (T20)
MatchState(total_balls=300, ...)  # OK (ODI)
MatchState(total_balls=600, ...)  # ValueError (Test not supported)
```

**Validation**: `6 <= total_balls <= 300`, divisible by 6.

---

### 5. get_phase() (Extended)

```python
# Current: Only returns "powerplay", "middle", "death"
get_phase(balls_remaining=240, total_balls=300)  # Wrong: "middle" (should be "powerplay")

# After: Returns format-aware phase including "setup"
get_phase(balls_remaining=240, total_balls=300)  # Correct: "powerplay" (over 10 of 50)
get_phase(balls_remaining=90, total_balls=300)   # "setup" (over 35)
get_phase(balls_remaining=30, total_balls=300)   # "death" (over 45)
```

**Phase mapping for ODI (total_balls=300)**:

| balls_remaining | overs_completed | phase |
|:-:|:-:|:-:|
| 300–241 | 0–9 | powerplay |
| 240–97 | 10–33 | middle |
| 96–61 | 34–39 | setup |
| 60–1 | 40–49 | death |

---

### 6. NextBallSampler (Extended)

```python
# Current: Only 3-phase distributions
sampler = NextBallSampler(league="bbl")
runs, wicket = sampler.sample(state)  # Uses powerplay/middle/death

# After: 4-phase distributions for ODI
sampler = NextBallSampler(league="odi", model_dir="models/odi_v1")
runs, wicket = sampler.sample(state)  # Uses powerplay/middle/setup/death

# Phase iteration in vectorized mode:
# Before: for phase in ("powerplay", "middle", "death"):
# After:  for phase in self._phases:  # Dynamic from loaded distributions
```

---

### 7. TerminalStateEvaluator._get_calculator() (Extended)

```python
# Current: Always uses FormatConfig.t20_reduced()
# After:
def _get_calculator(self, total_balls: int) -> ResourceFeatureCalculator:
    if total_balls > 120:
        config = FormatConfig.odi()  # ODI format
    elif total_balls == 120:
        config = FormatConfig.t20()  # Standard T20
    else:
        config = FormatConfig.t20_reduced(total_balls // 6)
    return ResourceFeatureCalculator(config=config)
```
