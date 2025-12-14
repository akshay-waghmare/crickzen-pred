# GitHub Copilot Instructions for BBL Win Probability Model

This repository contains the BBL Win Probability Model (currently v8), a machine learning pipeline for predicting T20 cricket match outcomes.

## 📂 Project Structure

- **`src/bbl_pipeline/`**: Core Python package.
  - **`cli.py`**: Main entry point (`bbl-pipeline`).
  - **`ingestion/`**: Parsing Cricsheet JSONs to Parquet.
  - **`processing/`**: Feature engineering logic.
  - **`training/`**: Model training and evaluation (`XGBLogRegEnsemble`).
  - **`inference/`**: Real-time prediction engine.
- **`data/`**: Data storage (gitignored).
  - **`bbl_raw/`**: Ingested Parquet files.
  - **`bbl_features_v2/`**: Processed features for training.
  - **`bbl_feature_store_v2/`**: Artifacts for inference (player stats, venue stats).
- **`models/`**: Trained models.
  - **`bbl_v8/`**: Current champion model (Ensemble + Calibration).
- **`docs/`**: Documentation.
  - **`BBL_V8_MODEL.md`**: Model architecture and features.
  - **`BBL_V8_CALIBRATION_GUIDE.md`**: Calibration methodology.
- **`scripts/`**: Analysis and utility scripts.

## 🚀 Standard CLI Workflow

Use the `bbl-pipeline` CLI for the standard end-to-end workflow.

### 1. Ingestion (JSON → Parquet)
Converts raw Cricsheet JSON files into efficient Parquet format.
```bash
bbl-pipeline ingest \
  --input-dir data/raw_json \
  --output-dir data/bbl_raw
```

### 2. Feature Engineering (Parquet → Features)
Generates training features and feature store artifacts.
**Standard Output:** `data/bbl_features_v2/training.parquet`
```bash
bbl-pipeline process \
  --input-dir data/bbl_raw/matches \
  --output-dir data/bbl_features_v2 \
  --feature-store-dir data/bbl_feature_store_v2
```

### 3. Model Training (Features → Model)
Trains the `XGBLogRegEnsemble` model with Isotonic Calibration.
**Current Version:** v8
```bash
bbl-pipeline train \
  --input-file data/bbl_features_v2/training.parquet \
  --output-dir models/bbl_v8 \
  --calibration
```
*Note: Always use `--calibration` for the production model to ensure ECE ≈ 0.*

### 4. Validation
Validates the schema of processed data.
```bash
bbl-pipeline validate --data-dir data/bbl_raw
```

## 🧠 Model Architecture (v8)

The current champion model is **BBL v8**.
- **Type:** `XGBLogRegEnsemble` (50% XGBoost + 50% Logistic Regression).
- **Calibration:** Isotonic Regression (fitted on Cross-Validated Out-of-Fold predictions).
- **Features:** Top 25 features including `resource_win_prob`, `score_vs_par`, and rolling stats.
- **Key Class:** `src/bbl_pipeline/training/trainer.py:XGBLogRegEnsemble`

## 🛠️ Common Tasks

- **Live Prediction (CLI):** Run the Crex live predictor:
  ```bash
  python -m src.bbl_pipeline.inference.crex_live_predictor \
    --match-url "CREX_MATCH_URL" \
    --model-dir models/bbl_v8 \
    --feature-store-dir data/bbl_feature_store_v2 \
    --output-json data/live_state.json
  ```
- **Live Visualization:** Run `streamlit run src/bbl_pipeline/app/live_streamlit_app.py` to view the dashboard.
- **Feature Fixes:** Check `docs/FEATURE_FIXES_DEC_2025.md` for recent logic changes.
- **Calibration:** See `docs/BBL_V8_CALIBRATION_GUIDE.md` for the detailed calibration process.

## ⚠️ Important Notes for Copilot

1.  **Prefer CLI:** When asked to run pipeline steps, prefer the `bbl-pipeline` CLI over ad-hoc scripts in `scripts/`.
2.  **v8 Standard:** Always refer to `models/bbl_v8` and `data/bbl_features_v2` as the current standard.
3.  **Calibration:** Remember that v8 requires Isotonic Calibration to be applied *after* the raw model prediction.
4.  **Imports:** Use absolute imports from `bbl_pipeline` (e.g., `from bbl_pipeline.inference.predictor import Predictor`).
