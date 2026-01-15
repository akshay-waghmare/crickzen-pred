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
- **Comprehensive OOF Calibration Analysis:** 
  - See `BBL_CALIBRATION_OOF_ANALYSIS.md` for complete 7-method comparison
  - Run `python analyze_bbl_calibrators_oof.py` to regenerate analysis
  - Interactive OOF analysis available in Streamlit app under "🔬 BBL Comprehensive OOF Calibration Analysis"

## 📊 BBL Calibration Analysis (Updated Jan 15, 2026)

### Comprehensive OOF Comparison (7 Methods)
A rigorous 5-fold cross-validation analysis compared 7 calibration approaches for BBL v10:

| Rank | Method | Calibrators | Brier | ECE | LogLoss | Best For |
|:----:|--------|:-----------:|:-----:|:---:|:-------:|----------|
| 🥇 | **ECE-Optimized** | 6 (histogram) | **0.1426** | 0.0091 | **0.4306** | Overall accuracy & sharpness |
| 🥈 | Combined | 1 (isotonic) | 0.1428 | **0.0053** | 0.4312 | Best calibration (near-perfect ECE) |
| 🥉 | Innings×Phase | 6 (isotonic) | 0.1430 | 0.0117 | 0.4374 | Balanced approach |
| 4 | LogLoss-Optimized | 6 (Platt) | 0.1432 | 0.0199 | 0.4370 | Probabilistic sharpness |
| 5 | Innings-Specific | 2 (isotonic) | 0.1435 | 0.0055 | 0.4328 | Simplicity + strong ECE |
| 6 | Brier-Optimized | 40 (per-over) | 0.1440 | 0.0132 | 0.4642 | ❌ Avoid - overfits |
| 7 | Raw | 0 | 0.1456 | 0.0558 | 0.4449 | Baseline |

**Key Findings:**
- **ECE-Optimized** (histogram binning, 6 calibrators) is best overall: +2.07% Brier, +3.21% LogLoss
- **Combined** (single isotonic) achieves near-perfect ECE (0.0053) with +90.43% improvement
- **Brier-Optimized** (40 per-over calibrators) actually hurts LogLoss (-4.35% vs raw) - overfitting
- All calibration methods improve over raw, but ECE-Optimized provides best balance

**Documentation:**
- Full analysis: `BBL_CALIBRATION_OOF_ANALYSIS.md`
- Analysis script: `analyze_bbl_calibrators_oof.py`
- Training script: `scripts/train_bbl_ece_calibrators.py`
- Active calibrators: `models/bbl_v10/ece_optimized_calibrators.pkl`

### ECE-Optimized Calibrators (Production)
The BBL v10 model now uses **ECE-Optimized calibrators** with histogram binning:
- **Method:** 15-bin histogram → isotonic regression per innings×phase
- **OOF Metrics:** Brier=0.1426, ECE=0.0091, LogLoss=0.4306
- **In-Sample (trained model):** Brier=0.1403, ECE=0.0040 (near-perfect), LogLoss=0.4230
- **File:** `models/bbl_v10/ece_optimized_calibrators.pkl`
- **Streamlit App:** Automatically loads and uses these calibrators for BBL matches

**Training Process:**
1. Generate OOF predictions using 5-fold CV (no shuffle)
2. For each innings×phase: create 15-bin histogram of predicted probabilities
3. Fit isotonic regression on bin centers vs actual win rates
4. Result: 6 calibrators (inn1_powerplay, inn1_middle, inn1_death, inn2_powerplay, inn2_middle, inn2_death)

**To retrain:**
```bash
python scripts/train_bbl_ece_calibrators.py
```

## ⚠️ Important Notes for Copilot

1.  **Active Models Only:** Only use `models/bbl_v10`, `models/sat_v1`, and `models/ilt20_v5`. Ignore everything in `models/archive/`.
2.  **Model Registry:** Keep `models/model_registry.json` updated whenever:
     - Regenerating feature stores (`bbl-pipeline process`)
     - Retraining models (`bbl-pipeline train`)
     - Adding/modifying feature store columns
     - See `docs/MODEL_REGISTRY_GUIDE.md` for detailed procedures
3.  **Prefer CLI:** Use `bbl-pipeline` for standard tasks.
4.  **Calibration - ECE-Optimized (NEW):** BBL v10 now uses ECE-optimized histogram binning calibrators (6 calibrators, best overall performance). See `BBL_CALIBRATION_OOF_ANALYSIS.md`.
5.  **ECE Optimization:** After training any new model, run `scripts/train_phase_calibrators.py` to create phase calibrators for perfect ECE (0.0000).
6.  **Imports:** Use absolute imports from `bbl_pipeline`.
7.  **Wicket Penalty:** The wicket penalty in ResourceFeatureCalculator now only applies to future projected runs, not runs already scored.
8.  **OOF Analysis:** For comprehensive calibration evaluation, use `analyze_bbl_calibrators_oof.py` which compares 7 different methods with proper cross-validation.

### Model Artifacts Checklist
After training a new model, ensure these files exist:
- `champion_model.joblib` - Main XGBLogRegEnsemble model
- `isotonic_calibrator.pkl` - Innings-specific OOF calibrators
- `phase_calibrators.pkl` - Phase-specific ECE calibrators (run `train_phase_calibrators.py`)
- `training_metadata.json` - Training config and metrics
- `feature_importance.csv` - Top 25 features
