# Add New T20 League to BBL Pipeline

Complete workflow for adding a standalone T20 league model to the BBL prediction pipeline. Follow this skill whenever a user asks to "add a new league" or "create a model for X league".

## Prerequisites

- Cricsheet JSON match files in a directory (e.g., `data/X_json/`)
- League must be T20 format (20 overs, 10 wickets)
- The `bbl-pipeline` package must be importable

## Step 1: Register League in CLI

Edit `src/bbl_pipeline/cli.py` - add 4 entries:

**a) Add to retrain `click.Choice`** (search for `'psl', 'odi'`):
```python
# Before:   ... 'psl', 'odi', ...
# After:    ... 'psl', 'X', 'odi', ...
```

**b) Add league config** (search for `'psl': {`):
```python
'X': {
    'json_dir': 'data/X_json',
    'raw_dir': 'data/X_raw',
    'features_dir': 'data/X_features',
    'feature_store_dir': 'data/X_feature_store',
    'model_prefix': 'X',
    'format_type': 't20',
},
```

**c) Add registry mapping** (search for `'wpl': 'WPL'`):
```python
'X': 'X_UPPER',
```

**d) Add to update-matches** (search for `'psl', 'odi'` in the second occurrence):
- Add 'X' to `click.Choice`
- Add `'X': ['Event Name Pattern']` to `league_patterns`
- Add `'X': 'data/X_json'` to `target_dirs`

## Step 2: Run Base Model Training

```bash
$env:PYTHONIOENCODING='utf-8'
python -m bbl_pipeline.cli retrain --league X --version v1
```

This 7-step pipeline runs: ingest -> process -> train -> generate-oof -> analyze-oof -> calibrate-mc -> update-registry.

**Expected outputs:**
- `data/X_raw/matches/` - ingested parquet
- `data/X_features_v1/training.parquet` - feature-engineered data
- `data/X_feature_store_v1/` - team/player/venue stats
- `models/X_v1/champion_model.joblib` - trained base model
- `models/X_v1/isotonic_calibrator.pkl` - calibrators

**If MC calibration warns about missing distributions**, run Step 2b.

## Step 2b: Extract Phase Distributions

```bash
python scripts/extract_league_phase_distributions.py --league X
```

Creates `data/phase_distributions_X.json` from the raw parquet data. This enables league-specific ball-by-ball sampling in the MC simulation engine instead of falling back to global T20 distributions.

## Step 3: Build Phase-Split Model

```bash
python scripts/build_league_phase_features.py --league X --version v1
```

Creates `models/X_v1_phase/` with:
- `champion_model_pp.joblib` - Powerplay (overs 1-6)
- `champion_model_mid.joblib` - Middle (overs 7-15)  
- `champion_model_death.joblib` - Death (overs 16-20)
- `phase_oof_calibrators.pkl` - Per-over calibrators
- `routing_config.json` - Inference routing configuration
- `phase_features.json` - Feature lists per phase
- `oof_results.csv` / `oos_comparison.csv` - Evaluation metrics

## Step 4: Verify

```bash
# Check model artifacts exist
Get-ChildItem models/X_v1/
Get-ChildItem models/X_v1_phase/

# Check registry entry
python -c "import json; r=json.load(open('models/model_registry.json')); print('X' in r['active_models'] or 'X_UPPER' in r['active_models'])"
```

## Key Files Referenced

| File | Purpose |
|------|---------|
| `src/bbl_pipeline/cli.py` | CLI registration (retrain, update-matches commands) |
| `scripts/build_league_phase_features.py` | Reusable phase-split model builder |
| `scripts/extract_league_phase_distributions.py` | Reusable phase distribution extractor |
| `src/bbl_pipeline/training/blend_model.py` | XGBLRBlend model class |
| `src/bbl_pipeline/training/calibration.py` | PlattCalibrator |
| `src/bbl_pipeline/features/inn2_engineering.py` | Innings-2 feature engineering |
| `models/model_registry.json` | Central model registry |

## Model Architecture

- **Base model**: XGBoost + LogisticRegression blend (41 features, XGBLogRegEnsemble)
- **Phase-split**: 3 separate XGBLRBlend models for innings-2 phases
- **Calibration**: Per-over isotonic (PP/DEATH) and Platt (MID) calibrators
- **Phase definitions**: PP=1-6, MID=7-15, DEATH=16-20
- **OOS split**: train on pre-2025, test on 2025+

## Common Issues

1. **Registry update fails**: `archived_models['IPL']` is a list, not dict. Fix: `scripts/build_league_phase_features.py` already handles this. For CLI, ensure edits have `isinstance(model_info, dict)` guard.

2. **Missing phase distributions warning**: Run `scripts/extract_league_phase_distributions.py --league X` to create the file.

3. **Features not in training data**: Normal for new leagues - the build script auto-detects available features and uses what's present. Fewer features mean broader but still valid predictions.

4. **Unicode errors on Windows**: Always set `$env:PYTHONIOENCODING='utf-8'` before running pipeline commands.
