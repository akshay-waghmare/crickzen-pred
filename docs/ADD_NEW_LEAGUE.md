# Add New T20 League

Complete guide for adding a standalone T20 league model to the BBL prediction pipeline. Follows **Constitution Principle I** (tournament-agnostic via configuration, not code rewrites).

## Quick Start (3 commands)

```bash
# 1. Train base model (one-time CLI registration needed first)
$env:PYTHONIOENCODING='utf-8'
python -m bbl_pipeline.cli retrain --league <slug> --version v1

# 2. Extract league-specific phase distributions (for MC simulation)
python scripts/extract_league_phase_distributions.py --league <slug>

# 3. Build phase-split innings-2 model (PP/MID/DEATH)
python scripts/build_league_phase_features.py --league <slug> --version v1
```

## CLI Registration (one-time)

Edit `src/bbl_pipeline/cli.py` and add 4 entries for the new league:

### a) retrain command `click.Choice` (line ~1419)

```python
# Search for: 'psl', 'odi',
# Add the new league slug before 'odi':
@click.option('--league', type=click.Choice([
    'bbl', 'sa20', 'ilt20', 'bpl', 'ssm', 'wpl', 'ipl', 'psl', 'ntb',
    'odi', ...
```

### b) League config dict (line ~1446)

```python
'<slug>': {
    'json_dir': 'data/<slug>_json',
    'raw_dir': 'data/<slug>_raw',
    'features_dir': 'data/<slug>_features',
    'feature_store_dir': 'data/<slug>_feature_store',
    'model_prefix': '<slug>',
    'format_type': 't20',
},
```

### c) Registry name mapping (line ~1713)

```python
'<slug>': '<UPPER_NAME>',
```

### d) update-matches command (line ~1301)

Three places: `click.Choice` list, `league_patterns` dict, and `target_dirs` dict. Follow existing patterns.

## Prerequisites

- Cricsheet JSON files at `data/<slug>_json/`
- League is T20 format (20 overs, 10 wickets)
- `bbl_pipeline` package importable (`pip install -e .` from repo root)

## Pipeline Steps (what retrain does)

| Step | Command | Output |
|------|---------|--------|
| 1. Ingest | JSON -> Parquet | `data/<slug>_raw/matches/` |
| 2. Process | Parquet -> Features | `data/<slug>_features_v1/training.parquet` |
| 3. Train | Features -> Model | `models/<slug>_v1/champion_model.joblib` |
| 4. Generate-OOF | OOF predictions + calibrators | `models/<slug>_v1/isotonic_calibrator.pkl` |
| 5. Analyze-OOF | Calibration report | `models/<slug>_v1/OOF_CALIBRATION_REPORT.md` |
| 6. Calibrate-MC | Platt scaling for MC engine | `models/<slug>_v1/mc_calibrators_innings.pkl` |
| 7. Update Registry | Register in model_registry.json | `model_registry.json` updated |

## Model Architecture

```
models/<slug>_v1/                    # Base model (trained by retrain)
  |- champion_model.joblib           # XGBLogRegEnsemble (41 features)
  |- isotonic_calibrator.pkl         # Innings-phase calibrators
  |- mc_calibrators_innings.pkl      # MC simulation calibrators

models/<slug>_v1_phase/              # Phase-split model (from build script)
  |- champion_model_pp.joblib        # Powerplay (overs 1-6)
  |- champion_model_mid.joblib       # Middle (overs 7-15)
  |- champion_model_death.joblib     # Death (overs 16-20)
  |- phase_oof_calibrators.pkl       # Per-over calibrators per phase
  |- routing_config.json             # Inference routing configuration
  |- phase_features.json             # Feature lists per phase
  |- oof_results.csv                 # OOF evaluation metrics
  |- oos_comparison.csv              # OOS (2025+) evaluation
```

**Phase calibration**: PP=isotonic, MID=platt, DEATH=isotonic.  
**OOS split**: train on pre-2025, test on 2025+.

## Reusable Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/build_league_phase_features.py` | Parameterized phase-split model builder | `--league X --version v1` |
| `scripts/extract_league_phase_distributions.py` | Phase distribution extractor | `--league X` |

These replace the need for per-league build scripts (e.g., `build_ipl_v17_pp_features.py`, `build_ntb_v1_phase_features.py`). New leagues only need the 4 CLI registrations + 3 commands above.

## Verification Checklist

```bash
# Base model artifacts
Get-ChildItem models/<slug>_v1/

# Phase model artifacts
Get-ChildItem models/<slug>_v1_phase/

# Registry entry
python -c "import json; r=json.load(open('models/model_registry.json')); print('<UPPER>' in r['active_models'])"

# Phase distributions
Test-Path data/phase_distributions_<slug>.json
```

## Example: NTB T20 Blast (most recently added)

| Metric | Value |
|--------|-------|
| Source data | 1,489 matches (2014-2026) |
| Training rows | 332,156 ball-by-ball |
| Base model Brier | 0.1754 |
| PP OOF Brier | 0.16930 |
| MID OOF Brier | 0.12152 |
| DEATH OOF Brier | 0.06990 |
| OOS test rows | 17,369 (2025-2026) |

## Common Issues

| Issue | Fix |
|-------|-----|
| Registry update fails with `'list' object has no attribute 'get'` | `archived_models['IPL']` is a list; `build_league_phase_features.py` handles this. For CLI retrain, ensure `isinstance(model_info, dict)` guard. |
| MC calibration warns "League-specific distributions not found" | Run `extract_league_phase_distributions.py --league <slug>` |
| Unicode errors on Windows | Always `$env:PYTHONIOENCODING='utf-8'` first |
| Features missing from training data | The build script auto-detects available features; fewer features = broader but valid predictions |
