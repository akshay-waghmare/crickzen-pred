# Quickstart: ODI Win Probability Model

**Feature**: 007-odi-model

## Prerequisites

- Python 3.11+
- `bbl-pipeline` CLI installed (`pip install -e .`)
- ODI data in `odis_json/` (3,085 JSON files, Cricsheet format)

## Step 0: Empirical Analysis (one-time)

Generate ODI-specific constants from the data:

```bash
python scripts/analyze_odi_empirical.py \
  --input-dir odis_json \
  --output scripts/odi_empirical_constants.json \
  --cutoff-year 2010
```

**Output**: `scripts/odi_empirical_constants.json` with gender-aware par scores, DLS tables, wicket penalties, RRR midpoints, and expected run rates.

Review the constants before proceeding — these drive the entire model.

## Step 1: Ingest

```bash
bbl-pipeline ingest \
  --input-dir odis_json \
  --output-dir data/odi_raw
```

## Step 2: Process (Feature Engineering)

```bash
bbl-pipeline process \
  --input-dir data/odi_raw/matches \
  --output-dir data/odi_features \
  --feature-store-dir data/odi_feature_store \
  --format-type odi
```

The `--format-type odi` flag selects ODI-specific FormatConfig constants (50 overs, 4 phases, ODI par scores, gender-aware penalties).

## Step 3: Full Retrain (Recommended)

```bash
bbl-pipeline retrain --league odi --version v1
```

Or individual steps:

### Train

```bash
bbl-pipeline train \
  --input-file data/odi_features/training.parquet \
  --output-dir models/odi_v1
```

### Generate OOF Calibrators

```bash
bbl-pipeline generate-oof \
  --input-file data/odi_features/training.parquet \
  --model-dir models/odi_v1
```

### Analyze OOF Calibration

```bash
bbl-pipeline analyze-oof \
  --input-file data/odi_features/training.parquet \
  --model-dir models/odi_v1 \
  --n-splits 5
```

## Step 4: Live Prediction

### Using global model (if ODI integrated)
```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/odi_feature_store \
  --league odi \
  --output-json data/live_state.json
```

### Using standalone ODI model
```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/odi_v1 \
  --feature-store-dir data/odi_feature_store \
  --output-json data/live_state.json
```

## Validation Checklist

After training, verify:
- [ ] `models/odi_v1/champion_model.joblib` exists
- [ ] `models/odi_v1/oof_calibrators.pkl` exists  
- [ ] `models/odi_v1/OOF_CALIBRATION_REPORT.md` shows Brier < 0.22
- [ ] `data/odi_feature_store/team_ratings.parquet` has ODI teams
- [ ] T20 models unchanged — run `bbl-pipeline analyze-oof` on BBL v12 to confirm no regression
- [ ] `models/model_registry.json` updated with ODI entry

## Key Differences from T20

| Aspect | T20 | ODI |
|--------|-----|-----|
| Total overs | 20 | 50 |
| Phases | PP/Mid/Death/Final | PP/Mid/Setup/Death |
| Par score (male) | ~160 | ~250 |
| Par score (female) | ~140 | ~195 |
| RRR midpoint | 9.5 | ~6.0 |
| Gender feature | No | Yes |
| Data cutoff | All years | 2010+ |
