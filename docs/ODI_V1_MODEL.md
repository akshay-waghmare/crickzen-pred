# ODI v1 Model Documentation

**Version**: v1  
**Created**: 2026-02-20  
**Branch**: 007-odi-model  
**Format**: One-Day International (50 overs)

## Overview

ODI v1 is the first ODI (50-over) win probability model, built using the same `XGBLogRegEnsemble` architecture as the T20 models. It uses a `FormatConfig`-parameterized pipeline that reuses the existing calculator, processor, and training infrastructure with ODI-specific empirical constants.

Key difference from T20: ODI v1 is a **combined gender model** with gender as a training feature and gender-aware resource constants (separate par scores, penalty tables, and DLS tables for male and female ODIs).

## Data

| Metric | Value |
|--------|-------|
| Source | Cricsheet JSON (odis_json/) |
| Total matches | 2,932 (ingested, all eras) |
| Training samples | 1,587,026 deliveries |
| Sampled training | 259,237 rows |
| Era filter | 2010+ (for empirical constants) |
| Overs filter | Exclude matches with < 50 overs |
| Male matches (2010+) | 1,632 |
| Female matches (2010+) | 506 |
| Teams | 28 |
| Feature store | data/odi_feature_store_v1 |

## Architecture

- **Model Type**: `XGBLogRegEnsemble` (50% XGBoost + 50% Logistic Regression)
- **Features**: 25 features (same set as T20 + `gender`)
- **Calibration**: Brier-optimized per-over isotonic (40 calibrators, best overall)
- **Format Config**: `FormatConfig.odi(gender)` with empirical constants

## Performance (5-fold OOF Cross-Validation)

### Overall

| Method | Brier | ECE | LogLoss |
|--------|-------|-----|---------|
| **Brier-Optimized** | **0.1609** | 0.0000 | 0.4796 |
| Innings×Phase | 0.1614 | 0.0000 | 0.4811 |
| ECE-Optimized | 0.1616 | 0.0022 | 0.4822 |
| Innings-Specific | 0.1618 | 0.0000 | 0.4824 |
| Combined | 0.1620 | 0.0000 | 0.4830 |
| Raw | 0.1621 | 0.0041 | 0.4837 |
| LogLoss-Optimized | 0.1628 | 0.0182 | 0.4883 |
| Resource WP Baseline | 0.1874 | 0.0348 | 0.5482 |

### Per-Innings

| Innings | Brier (calibrated) | ECE | Samples |
|---------|-------------------|-----|---------|
| 1st innings | 0.1975 | 0.0000 | 855,626 |
| 2nd innings | 0.1180 | 0.0000 | 731,400 |

### Key Metrics vs Targets

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| Brier Score | ≤ 0.22 | 0.1609 | ✅ Pass |
| ECE | < 0.03 | 0.0000 | ✅ Pass |
| Model vs Resource Baseline | Better | -14.1% Brier | ✅ Pass |

## Empirical Constants

### Scoring (Male vs Female ODI)

| Constant | Male | Female |
|----------|------|--------|
| Par Score | 257.7 | 227.8 |
| Median Score | 260 | 227 |
| Bat First Win Rate | 0.490 | 0.508 |
| Score Std (early) | 89.8 | 80.7 |
| Score Std (late) | 23.8 | 20.1 |

### Phase Structure (4 phases, same for both genders)

| Phase | Overs | Run Rate (M) | Run Rate (F) |
|-------|-------|-------------|-------------|
| Powerplay | 1-10 | 4.82 | 4.17 |
| Middle | 11-34 | 4.90 | 4.42 |
| Setup | 35-40 | 5.71 | 4.98 |
| Death | 41-50 | 7.32 | 6.12 |

### Chase Parameters

| Parameter | Male | Female |
|-----------|------|--------|
| RRR Midpoint | 5.5 | 5.0 |
| RRR Beta | 0.75 | 0.95 |
| SQI Beta | 0.45 | 0.50 |
| SQI Shift | 0.09 | -0.06 |

### Key Differences from T20

| Aspect | T20 | ODI |
|--------|-----|-----|
| Total overs | 20 | 50 |
| Total balls | 120 | 300 |
| Par score (male) | 160 | 257.7 |
| Phases | PP/Mid/Death | PP/Mid/Setup/Death |
| Phase thresholds | 6/15/20 | 10/34/40/50 |
| RRR midpoint | 9.5 | 5.5 (M), 5.0 (F) |
| Gender feature | No | Yes |
| Score cap max | 280 | 500 (M), 450 (F) |
| Endgame balls | 12 | 12 |

## Model Artifacts

```
models/odi_v1/
├── champion_model.joblib             # Trained XGBLogRegEnsemble
├── champion_metadata.json            # Model metadata
├── isotonic_calibrator.pkl           # OOF calibrators (innings×phase + per-over)
├── oof_calibrators.pkl               # All 7 calibration strategies
├── oof_calibration_results.csv       # Detailed metrics by segment
├── oof_probability_bins.csv          # Probability bin analysis
└── OOF_CALIBRATION_REPORT.md         # Auto-generated calibration report
```

## Feature Store

```
data/odi_feature_store_v1/
├── team_ratings.parquet              # 28 ODI teams
├── player_stats.parquet              # Player rolling averages
└── venue_stats.parquet               # Venue-specific stats
```

## CLI Usage

### Full Pipeline
```bash
bbl-pipeline retrain --league odi --version v1
```

### Individual Steps
```bash
# Ingest
bbl-pipeline ingest --input-dir odis_json --output-dir data/odi_raw

# Process (with ODI format)
bbl-pipeline process \
  --input-dir data/odi_raw/matches \
  --output-dir data/odi_features_v1 \
  --feature-store-dir data/odi_feature_store_v1 \
  --league odi

# Train
bbl-pipeline train \
  --input-file data/odi_features_v1/training.parquet \
  --output-dir models/odi_v1

# OOF Calibrators
bbl-pipeline generate-oof \
  --input-file data/odi_features_v1/training.parquet \
  --model-dir models/odi_v1

# OOF Analysis
bbl-pipeline analyze-oof \
  --input-file data/odi_features_v1/training.parquet \
  --model-dir models/odi_v1
```

### Live Prediction
```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_ODI_MATCH_URL" \
  --model-dir models/odi_v1 \
  --feature-store-dir data/odi_feature_store_v1 \
  --league odi \
  --output-json data/live_state.json
```

## FormatConfig Integration

The ODI model is powered by `FormatConfig.odi(gender)` which provides all 30+ empirical constants:

```python
from bbl_pipeline.features.format_config import FormatConfig

# Male ODI config
config_m = FormatConfig.odi(gender='male')
# Female ODI config
config_f = FormatConfig.odi(gender='female')
# Auto-resolve from league
config = FormatConfig.from_league('odi')  # defaults to male

# Key attributes
config.total_overs      # 50
config.total_balls       # 300
config.par_score         # 257.7 (male)
config.phase_thresholds  # {'powerplay':10, 'middle':34, 'setup':40, 'death':50}
```

The `ResourceFeatureCalculator` accepts `config=FormatConfig.odi()` to produce ODI-appropriate win probabilities, projected scores, and pressure indices.
