# GitHub Copilot Instructions for Win Probability Models

This repository contains the machine learning pipelines for predicting T20 cricket match outcomes.
**Active Models:**
- **BBL v12** (Big Bash League) - 618 matches, Brier 0.1825 (empirically calibrated penalties)
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
  - **`bbl_features_v4/`**: Processed features for training (empirical penalties).
  - **`bbl_feature_store_v2/`**: Artifacts for inference.
- **`models/`**: Trained models.
  - **`bbl_v12/`**: Champion BBL model (empirically calibrated).
  - **`ilt20_v5/`**: Champion ILT20 model.
  - **`archive/`**: Deprecated models (v1-v11, etc.).
- **`docs/`**: Documentation.
  - **`BBL_V12_MODEL.md`**: BBL model details + calibration analysis.
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

### 4. OOF Calibration Analysis (Compare All Methods)
Comprehensive OOF cross-validation analysis comparing 7 calibration strategies:
```bash
bbl-pipeline analyze-oof \
  --input-file data/bbl_features_v2/training.parquet \
  --model-dir models/bbl_v10 \
  --n-splits 5
```
**Outputs:**
- `oof_calibration_results.csv` - Detailed metrics by segment (overall, innings, phase)
- `oof_calibrators.pkl` - Trained calibrators for all 7 methods
- `OOF_CALIBRATION_REPORT.md` - Formatted markdown report

**7 Methods Compared:**
1. **Raw** - Uncalibrated base model
2. **Combined** - Single isotonic calibrator
3. **Innings-Specific** - 2 calibrators (one per innings)
4. **Innings×Phase** - 6 calibrators (powerplay/middle/death per innings)
5. **Brier-Optimized** - Per-over calibrators (40 total)
6. **ECE-Optimized** - Histogram binning + isotonic per innings×phase
7. **LogLoss-Optimized** - Platt scaling per innings×phase

**Metrics Reported:** Brier Score, ECE (10-bin), Log Loss

### 5. ECE Optimization (Perfect Calibration)
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
- **Brier-Optimized** (40 per-over calibrators) achieves best Brier but may overfit
- All calibration methods improve over raw

**Documentation:**
- Full analysis: `BBL_CALIBRATION_OOF_ANALYSIS.md`
- Analysis script: `analyze_bbl_calibrators_oof.py`
- Model documentation: `docs/BBL_V12_MODEL.md`

### Empirically Calibrated Wicket Penalties (v12)
BBL v12 uses **empirically calibrated wicket penalties** for first innings:
- **Method:** Derived from actual projected score ratios by phase/ease/wickets
- **Key Insight:** In death overs, wickets have minimal impact (~0.90-1.00 penalty)
- **Results:** 
  - Overall Brier: 0.1825 (-0.30% vs v10)
  - Inn1 death Brier: 0.2033 (-0.40% vs v10)  
  - Inn2 death Brier: 0.0859 (-3.00% vs v10)

**Penalty Philosophy:**
```
In T20 death overs:
- Actual score and run rate matter far more than wickets
- Wickets lost late have diminishing negative effect on projected score
- Even 7-8 wickets down, teams maintain ~90% of projected output
```

## ⚠️ Important Notes for Copilot

1.  **Active Models Only:** Only use `models/bbl_v12`, `models/sat_v1`, and `models/ilt20_v5`. Ignore everything in `models/archive/`.
2.  **Model Registry:** Keep `models/model_registry.json` updated whenever:
     - Regenerating feature stores (`bbl-pipeline process`)
     - Retraining models (`bbl-pipeline train`)
     - Adding/modifying feature store columns
     - See `docs/MODEL_REGISTRY_GUIDE.md` for detailed procedures
3.  **Prefer CLI:** Use `bbl-pipeline` for standard tasks.
4.  **Empirical Penalties:** BBL v12 uses empirically calibrated `FIRST_INNINGS_WICKET_PENALTY_3D` derived from actual projected score data.
5.  **OOF Analysis:** After training, run `bbl-pipeline analyze-oof` to generate calibrators and metrics.
6.  **Imports:** Use absolute imports from `bbl_pipeline`.
7.  **Wicket Penalty:** The wicket penalty in ResourceFeatureCalculator only applies to future projected runs, not runs already scored. Death phase penalties are ~0.90-1.00 (minimal impact).
8.  **Features:** BBL v12 uses `data/bbl_features_v4/` with empirically calibrated penalties.

### Model Artifacts Checklist
After training a new model, ensure these files exist:
- `champion_model.joblib` - Main XGBLogRegEnsemble model
- `oof_calibrators.pkl` - OOF calibrators from analyze-oof
- `oof_calibration_results.csv` - Detailed metrics by segment
- `OOF_CALIBRATION_REPORT.md` - Auto-generated report
