# GitHub Copilot Instructions for Win Probability Models

This repository contains the machine learning pipelines for predicting T20 cricket match outcomes.
**Active Models:**
- **BBL v10** (Big Bash League) - 618 matches, Brier 0.1800
- **ILT20 v5** (International League T20) - 99 matches, Brier 0.1886

All other models have been archived in `models/archive/`.

## 📂 Project Structure

- **`src/bbl_pipeline/`**: Core Python package (shared by all leagues).
  - **`cli.py`**: Main entry point (`bbl-pipeline`).
  - **`ingestion/`**: Parsing Cricsheet JSONs to Parquet.
  - **`processing/`**: Feature engineering logic.
  - **`training/`**: Model training and evaluation (`XGBLogRegEnsemble`).
  - **`inference/`**: Real-time prediction engine.
- **`data/`**: Data storage (gitignored).
  - **`raw_json/`**: Source JSON files (organized by league: `bbl`, `ilt20`, `npl`, etc.).
  - **`bbl_raw/`**, **`ilt_raw/`**: Ingested Parquet files.
  - **`bbl_features_v2/`**: Processed features for training.
  - **`bbl_feature_store_v2/`**: Artifacts for inference.
- **`models/`**: Trained models.
  - **`bbl_v10/`**: Champion BBL model.
  - **`ilt20_v5/`**: Champion ILT20 model.
  - **`archive/`**: Deprecated models (v1-v9, etc.).
- **`docs/`**: Documentation.
  - **`BBL_V10_MODEL.md`**: BBL model details + calibration analysis.
  - **`ILT20_V4_MODEL.md`**: ILT20 model details.
  - **`BBL_V8_CALIBRATION_GUIDE.md`**: Calibration methodology.

## 🚀 Standard CLI Workflow

Use the `bbl-pipeline` CLI for the standard end-to-end workflow.

### 1. Ingestion (JSON → Parquet)
```bash
bbl-pipeline ingest \
  --input-dir data/raw_json/bbl \
  --output-dir data/bbl_raw
```

### 2. Feature Engineering (Parquet → Features)
```bash
bbl-pipeline process \
  --input-dir data/bbl_raw/matches \
  --output-dir data/bbl_features_v2 \
  --feature-store-dir data/bbl_feature_store_v2
```

### 3. Model Training (Features → Model)
Trains the `XGBLogRegEnsemble` model with Isotonic Calibration.
```bash
bbl-pipeline train \
  --input-file data/bbl_features_v2/training.parquet \
  --output-dir models/bbl_v10 \
  --calibration
```
*Note: Always use `--calibration` for production models.*

### 4. ECE Optimization (Perfect Calibration)
After training, create phase-specific calibrators to achieve ECE ≈ 0.0000:
```bash
python scripts/train_phase_calibrators.py \
  --model-dir models/bbl_v10 \
  --features data/bbl_features_v2/training.parquet
```
This creates `models/bbl_v10/phase_calibrators.pkl` with isotonic calibrators for each innings × phase combination.

**See `docs/ECE_OPTIMIZATION_GUIDE.md` for detailed methodology.**

## 🧠 Model Architectures

### BBL v10 & ILT20 v5
Both champion models share the same architecture:
- **Type:** `XGBLogRegEnsemble` (50% XGBoost + 50% Logistic Regression).
- **Calibration:** Innings-Specific Isotonic Regression (CV-OOF fitted).
- **Features:** Top 25 features including `resource_win_prob`, `score_vs_par`, and rolling stats.
- **Key Class:** `src/bbl_pipeline/training/trainer.py:XGBLogRegEnsemble`

### Calibration Guidance (BBL v10)
Based on Brier/ECE analysis, use different probability sources by situation:

| Innings | Phase | Best for Accuracy | Best for Calibration |
|---------|-------|-------------------|---------------------|
| **1** | All | Raw Model | Raw Model |
| **2** | Powerplay | Inn-Specific Cal | Inn-Specific Cal |
| **2** | Middle | Inn-Specific Cal | Resource Win Prob |
| **2** | Death | Raw Model | Inn-Specific Cal |

**Key Insight:** BBL's raw model is well-calibrated in innings 1 (no calibration needed).

### Feature Stores
Each model relies on a specific feature store for inference (player stats, venue stats):
- **BBL v10:** `data/bbl_feature_store_v2`
  - 8 teams, 508 players, 31 venues
  - Columns: team, win_rate, matches, bat_first_wr, bowl_first_wr
  - Generated: 2025-12-31
- **ILT20 v5:** `data/ilt_feature_store_v3`
  - 6 teams, 320 players, 3 venues
  - Columns: team, win_rate, matches, bat_first_wr, bowl_first_wr
  - Generated: 2025-12-30

**Feature Store Components:**
1. **team_ratings.parquet**: Team stats (overall + situation-specific win rates)
2. **player_stats.parquet**: Player rolling averages and strike rates
3. **venue_stats.parquet**: Venue-specific performance metrics

See `docs/FEATURE_STORE.md` for detailed schema documentation.

## 🛠️ Common Tasks

- **Live Prediction (CLI):** Run the Crex live predictor:
  ```bash
  python -m src.bbl_pipeline.inference.crex_live_predictor \
    --match-url "CREX_MATCH_URL" \
    --model-dir models/bbl_v10 \
    --feature-store-dir data/bbl_feature_store_v2 \
    --output-json data/live_state.json
  ```
  *(For ILT20, change model-dir to `models/ilt20_v5`)*

- **Live Visualization:** Run `streamlit run src/bbl_pipeline/app/live_streamlit_app.py`
- **Calibration Analysis:** See `docs/BBL_V10_MODEL.md` for detailed Brier/ECE breakdown.

## ⚠️ Important Notes for Copilot

1.  **Active Models Only:** Only use `models/bbl_v10`, `models/sat_v1`, and `models/ilt20_v5`. Ignore everything in `models/archive/`.
2.  **Model Registry:** Keep `models/model_registry.json` updated whenever:
     - Regenerating feature stores (`bbl-pipeline process`)
     - Retraining models (`bbl-pipeline train`)
     - Adding/modifying feature store columns
     - See `docs/MODEL_REGISTRY_GUIDE.md` for detailed procedures
3.  **Prefer CLI:** Use `bbl-pipeline` for standard tasks.
4.  **Calibration:** Use innings-specific isotonic calibration for innings 2; raw model for innings 1.
5.  **ECE Optimization:** After training any new model, run `scripts/train_phase_calibrators.py` to create phase calibrators for perfect ECE (0.0000).
6.  **Imports:** Use absolute imports from `bbl_pipeline`.
7.  **Wicket Penalty:** The wicket penalty in ResourceFeatureCalculator now only applies to future projected runs, not runs already scored.

### Model Artifacts Checklist
After training a new model, ensure these files exist:
- `champion_model.joblib` - Main XGBLogRegEnsemble model
- `isotonic_calibrator.pkl` - Innings-specific OOF calibrators
- `phase_calibrators.pkl` - Phase-specific ECE calibrators (run `train_phase_calibrators.py`)
- `training_metadata.json` - Training config and metrics
- `feature_importance.csv` - Top 25 features
