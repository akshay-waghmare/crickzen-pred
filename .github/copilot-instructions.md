# GitHub Copilot Instructions for Win Probability Models

This repository contains the machine learning pipelines for predicting T20 cricket match outcomes.
**Active Models:**
- **BBL v8** (Big Bash League)
- **ILT20 v4** (International League T20)

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
  - **`bbl_v8/`**: Champion BBL model.
  - **`ilt20_v4/`**: Champion ILT20 model.
  - **`archive/`**: Deprecated models (v1-v7, etc.).
- **`docs/`**: Documentation.
  - **`BBL_V8_MODEL.md`**: BBL model details.
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
  --output-dir models/bbl_v8 \
  --calibration
```
*Note: Always use `--calibration` for production models.*

## 🧠 Model Architectures

### BBL v8 & ILT20 v4
Both champion models share the same architecture:
- **Type:** `XGBLogRegEnsemble` (50% XGBoost + 50% Logistic Regression).
- **Calibration:** Isotonic Regression (fitted on Cross-Validated Out-of-Fold predictions).
- **Features:** Top 25 features including `resource_win_prob`, `score_vs_par`, and rolling stats.
- **Key Class:** `src/bbl_pipeline/training/trainer.py:XGBLogRegEnsemble`

### Feature Stores
Each model relies on a specific feature store for inference (player stats, venue stats):
- **BBL v8:** `data/bbl_feature_store_v2`
- **ILT20 v4:** `data/ilt_feature_store_v3`

## 🛠️ Common Tasks

- **Live Prediction (CLI):** Run the Crex live predictor:
  ```bash
  python -m src.bbl_pipeline.inference.crex_live_predictor \
    --match-url "CREX_MATCH_URL" \
    --model-dir models/bbl_v8 \
    --feature-store-dir data/bbl_feature_store_v2 \
    --output-json data/live_state.json
  ```
  *(For ILT20, change model-dir to `models/ilt20_v4`)*

- **Live Visualization:** Run `streamlit run src/bbl_pipeline/app/live_streamlit_app.py`
- **Calibration:** See `docs/BBL_V8_CALIBRATION_GUIDE.md`.

## ⚠️ Important Notes for Copilot

1.  **Active Models Only:** Only use `models/bbl_v8` and `models/ilt20_v4`. Ignore everything in `models/archive/`.
2.  **Model Registry:** Keep `models/model_registry.json` updated with the latest active models and their versions.
3.  **Prefer CLI:** Use `bbl-pipeline` for standard tasks.
3.  **Calibration:** Ensure Isotonic Calibration is applied after raw prediction.
4.  **Imports:** Use absolute imports from `bbl_pipeline`.
