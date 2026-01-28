# T20 International Male v1 Model Setup

**Date Created:** January 28-29, 2026  
**Model:** `models/t20_international_male_v1`  
**Feature Store:** `data/t20_international_male_feature_store_v1`  
**Raw Data:** `data/t20_international_male_raw` (3,113 matches from 2004-2026)

## Overview

The T20 International Male v1 model is a unified global model trained on T20 international cricket matches. It serves as the reference model for international T20 cricket win probability predictions.

## Model Architecture

- **Type:** `XGBLogRegEnsemble` (50% XGBoost + 50% Logistic Regression)
- **Training Samples:** 686,832 balls across 3,113 matches
- **Brier Score (OOF 5-fold CV):** 0.1605
- **Features:** 25 top features including resource win probability, score vs par, and rolling stats

## Setup Steps Completed

### 1. Data Processing
```bash
bbl-pipeline process \
  --input-dir data/t20_international_male_raw/matches \
  --output-dir data/t20_international_male_features_v1 \
  --feature-store-dir data/t20_international_male_feature_store_v1
```

**Output:**
- Training data: `data/t20_international_male_features_v1/training.parquet` (686,832 rows)
- Sampled data: `data/t20_international_male_features_v1/training_sampled.parquet` (111,622 rows)
- Feature store artifacts:
  - `team_ratings.parquet` (107 teams)
  - `player_stats.parquet`
  - `venue_stats.parquet`

### 2. Phase Distribution Extraction
```bash
python scripts/analysis/extract_phase_distributions.py \
  --json-dir t20_international_male \
  --league t20i \
  --output data/t20_international_male_feature_store_v1/phase_distributions_t20i.json
```

**Output:** Phase-based run distributions for powerplay, middle, and death phases extracted from 3,113 JSON match files (3+ hours processing).

**File:** `models/t20_international_male_v1/phase_distributions_t20i.json` (moved to model directory)

## Model Artifacts

Located in `models/t20_international_male_v1/`:
- `champion_model.joblib` - Trained XGBLogRegEnsemble
- `champion_metadata.json` - Model metadata
- `isotonic_calibrator.pkl` - OOF calibrator
- `oof_calibrators.pkl` - All calibration methods
- `oof_calibration_results.csv` - OOF metrics
- `oof_probability_bins.csv` - Probability bin analysis
- `OOF_CALIBRATION_REPORT.md` - Detailed calibration report
- `phase_distributions_t20i.json` - League-specific phase distributions ✨ NEW

## Live Prediction

### Running Live Predictions
```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/t20_international_male_v1 \
  --feature-store-dir data/t20_international_male_feature_store_v1 \
  --output-json data/live_state_t20i.json
```

### Example (India vs New Zealand, Jan 29, 2026)
```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "https://crex.com/scoreboard/V6I/1V1/4th-T20/R/O/ind-vs-nz-4th-t20-new-zealand-tour-of-india-2026/live" \
  --model-dir models/t20_international_male_v1 \
  --feature-store-dir data/t20_international_male_feature_store_v1 \
  --output-json data/live_state_t20i.json
```

**Features:**
- ✅ Real-time win probability updates using T20i phase distributions
- ✅ Multi-ball horizon projections (1, 6, 12, 30 balls)
- ✅ Current state visualization (score, wickets, overs)
- ✅ JSON output for downstream consumption

## Feature Store Summary

| Component | Count | Status |
|-----------|-------|--------|
| Teams | 107 | ✅ |
| Players | ~5,000+ | ✅ |
| Venues | 3,000+ | ✅ |
| Phase Distributions | 3 (powerplay, middle, death) | ✅ |

## OOF Calibration Performance

| Method | Brier | ECE | LogLoss |
|--------|-------|-----|---------|
| Raw | 0.1599 | 0.0041 | 0.4777 |
| Combined | 0.1598 | 0.0000 | 0.4770 |
| **Innings-Specific** | **0.1596** | **0.0000** | **0.4760** |
| Innings×Phase | 0.1592 | 0.0000 | 0.4748 |

Best calibration: **Innings×Phase** (6 calibrators, perfect ECE)

## Data Sources

- **JSON Data:** `t20_international_male/` directory (3,113 match files)
  - Seasons: 2004/05 - 2025/26
  - Format: Cricsheet JSON with ball-by-ball data
- **Ingested Parquet:** `data/t20_international_male_raw/matches/` (partitioned by season)

## Model Registry

Should be added to `models/model_registry.json`:

```json
{
  "t20_international_male_v1": {
    "model_type": "XGBLogRegEnsemble",
    "training_date": "2026-01-28",
    "n_samples": 686832,
    "brier_score": 0.1605,
    "base_model_params": {
      "xgb_weight": 0.5,
      "n_features": 25,
      "logreg_c": 0.01
    },
    "feature_store": "data/t20_international_male_feature_store_v1",
    "phase_distributions": "models/t20_international_male_v1/phase_distributions_t20i.json",
    "leagues": ["t20i"],
    "status": "active"
  }
}
```

## Next Steps

1. ✅ Data processing complete
2. ✅ Phase distributions extracted
3. ✅ Live predictions working
4. ⏳ Update model registry with T20i entry
5. ⏳ Deploy live prediction service
6. ⏳ Setup Streamlit dashboard integration

## Notes

- Match completeness warnings are expected due to partial ball history from live scorecards
- VDCA Cricket Stadium (Indore) default venue stats used when unavailable in feature store
- Sparse ball history (24.1% complete) triggers fallback to seasonal team statistics
- Season stats used for teams with insufficient rolling data
