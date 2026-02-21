# Quick Start: T20 Reduced-Over Match Support

**Feature**: 008-t20-reduced-overs

## Usage

### 1. Live Prediction — Reduced-Over Match (CLI override)

```bash
# 15-over match, DLS target 156
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/t20_male_feature_store_v2 \
  --league bbl \
  --total-overs 15 \
  --revised-target 156 \
  --output-json data/live_state.json
```

### 2. Live Prediction — Auto-Detect from CREX (recommended)

```bash
# System auto-detects reduced overs and DLS target from CREX page
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/t20_male_feature_store_v2 \
  --league bbl \
  --output-json data/live_state.json
```

Output when reduced overs detected:
```
[INFO] CREX detected reduced overs: 15 (was: 20)
[INFO] CREX detected revised target: 156 (DLS)
[INFO] Switching to Monte Carlo-only mode (total_overs=15 < 20)
[INFO] MC Raw: 62.3% | MC Calibrated: 59.8% (Platt)
```

### 3. Train MC Calibrator (one-time setup)

```bash
python scripts/train_mc_calibrator.py \
  --training-data data/bbl_features_v4/training.parquet \
  --model-dir models/bbl_v12 \
  --feature-store-dir data/bbl_feature_store_v2 \
  --output mc_calibrator.pkl \
  --n-simulations 1000 \
  --n-samples 10000
```

Output:
```
Running MC backtest on 10000 samples...
Fitting Platt calibrator...
Training log loss: 0.512
Validation log loss: 0.523
Saved mc_calibrator.pkl to models/bbl_v12/mc_calibrator.pkl
```

### 4. FormatConfig — Programmatic Usage

```python
from bbl_pipeline.features.format_config import FormatConfig

# Standard 20-over T20
config_20 = FormatConfig.t20()
assert config_20.total_overs == 20
assert config_20.par_score == 160.0

# Reduced 15-over match
config_15 = FormatConfig.t20_reduced(total_overs=15)
assert config_15.total_overs == 15
assert config_15.total_balls == 90
assert 130 <= config_15.par_score <= 140  # DLS-scaled

# Reduced 10-over match
config_10 = FormatConfig.t20_reduced(total_overs=10)
assert config_10.total_overs == 10
assert config_10.total_balls == 60

# 20-over reduced = identical to standard
config_20r = FormatConfig.t20_reduced(total_overs=20)
assert config_20r == config_20  # Exact same config
```

### 5. Running Tests

```bash
# All reduced-over tests
pytest tests/test_reduced_overs.py -v

# Regression — ensure 20-over behavior unchanged
pytest tests/test_simulation.py tests/test_resource_features.py -v

# Integration
pytest tests/integration/test_simulation_integration.py -v
```
