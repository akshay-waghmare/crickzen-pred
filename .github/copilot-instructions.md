# GitHub Copilot Instructions for Win Probability Models

This repository contains the machine learning pipelines for predicting T20 cricket match outcomes.

**Active Models:**
- **T20 Male v2** (Global Unified Model) - Trained on all T20 leagues, uses league-specific calibrators
- **BBL v12** (Big Bash League) - 141,435 samples, Brier 0.1760 (per-over brier-optimized calibration)
- **SA20 v2** (South Africa T20 League) - 121 matches, 26,121 samples, Brier 0.1597
- **ILT20 v5** (International League T20) - 99 matches, Brier 0.1886
- **WPL v2** (Women's Premier League) - 74 matches, 17,062 samples, Brier 0.1510

All other models have been archived in `models/archive/`.

**Global Model Architecture (Recommended):**
- Use `models/t20_male_v2` with `--league` parameter for league-specific calibration
- Calibration chain: Raw → Phase → PerOver → League (final adjustment)

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

### Quick Start: Full Retrain (Recommended)
The `retrain` command runs the complete pipeline in one step:
```bash
bbl-pipeline retrain --league sa20 --version v2
```
This runs: ingest → process → train → generate-oof → analyze-oof → update-registry

### Update Matches from Recently Played
Copy new matches from the recently_played folder to league-specific folders:
```bash
bbl-pipeline update-matches --league sa20 --dry-run  # Preview
bbl-pipeline update-matches --league sa20            # Copy files
bbl-pipeline update-matches --league all             # All leagues
```

### Individual Pipeline Steps

#### 1. Ingestion (JSON → Parquet)
```bash
bbl-pipeline ingest \
  --input-dir data/raw_json/bbl \
  --output-dir data/bbl_raw
```

#### 2. Feature Engineering (Parquet → Features)
```bash
bbl-pipeline process \
  --input-dir data/bbl_raw/matches \
  --output-dir data/bbl_features_v2 \
  --feature-store-dir data/bbl_feature_store_v2
```

#### 3. Model Training (Features → Model)
Trains the `XGBLogRegEnsemble` model. Do NOT use `--calibration` (calibration comes from generate-oof).
```bash
bbl-pipeline train \
  --input-file data/bbl_features_v2/training.parquet \
  --output-dir models/bbl_v10
```

#### 4. Generate OOF Calibrators (For Inference)
Creates `isotonic_calibrator.pkl` used by the predictor and Streamlit app:
```bash
bbl-pipeline generate-oof \
  --input-file data/bbl_features_v2/training.parquet \
  --model-dir models/bbl_v10
```

#### 5. OOF Calibration Analysis (Compare All Methods)
Comprehensive OOF cross-validation analysis comparing 7+ calibration strategies:
```bash
bbl-pipeline analyze-oof \
  --input-file data/bbl_features_v2/training.parquet \
  --model-dir models/bbl_v10 \
  --n-splits 5
```
**Outputs:**
- `oof_calibration_results.csv` - Detailed metrics by segment (overall, innings, phase)
- `oof_probability_bins.csv` - Probability bin analysis
- `oof_calibrators.pkl` - Trained calibrators for all 7 methods
- `OOF_CALIBRATION_REPORT.md` - Formatted markdown report with resource baseline comparison

**8 Methods Compared:**
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

### BBL v12 & ILT20 v5
Both champion models share the same architecture:
- **Type:** `XGBLogRegEnsemble` (50% XGBoost + 50% Logistic Regression).
- **Calibration:** BBL v12 uses per-over brier-optimized isotonic (38 calibrators); ILT20 v5 uses innings-specific.
- **Features:** Top 25 features including `resource_win_prob`, `score_vs_par`, and rolling stats.
- **Key Class:** `src/bbl_pipeline/training/trainer.py:XGBLogRegEnsemble`

### Calibration Strategy (BBL v12)
**Production Calibrators:**
- **Per-Over Brier-Optimized** (38 calibrators): inn1_over2-20, inn2_over2-20 → Brier 0.1760, ECE 0.0000
- **Phase-Specific** (6 calibrators): Fallback for over 1 → Brier 0.1787, ECE 0.0000
- **Missing overs:** inn1_over1, inn2_over1 (no variation at match start)

**OOF Performance (5-fold CV, 141,435 samples):**
| Method | Brier | ECE | LogLoss | Description |
|--------|-------|-----|---------|-------------|
| **Brier-Optimized** | **0.1760** | 0.0000 | 0.5190 | Per-over isotonic (best overall) |
| Innings×Phase | 0.1787 | 0.0000 | 0.5269 | 6 phase-level calibrators |
| ECE-Optimized | 0.1796 | 0.0038 | 0.5300 | Histogram + isotonic |
| Innings-Specific | 0.1809 | 0.0000 | 0.5327 | 2 innings-level calibrators |
| Raw | 0.1825 | 0.0162 | 0.5381 | Uncalibrated model |

**Key Insight:** Per-over granularity captures within-phase variation (-2.7% Brier vs phase, -3.6% vs raw).

### Feature Stores
Each model relies on a specific feature store for inference (player stats, venue stats):
- **BBL v12:** `data/bbl_feature_store_v2`
  - 8 teams, 508 players, 31 venues
  - Columns: team, win_rate, matches, bat_first_wr, bowl_first_wr
  - Generated: 2026-01-17
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
  # Using global model with league calibration (RECOMMENDED)
  python -m src.bbl_pipeline.inference.crex_live_predictor \
    --match-url "CREX_MATCH_URL" \
    --model-dir models/t20_male_v2 \
    --feature-store-dir data/t20_male_feature_store_v2 \
    --league ssm \
    --output-json data/live_state.json
  
  # Available leagues: ssm, bbl, sa20, ilt20, wpl, etc.
  # Output shows calibration chain:
  #   Raw: 6.7% | Phase (inn2_middle): 6.4% | PerOver (inn2_over11): 7.0%
  #   League (SSM): 7.0% -> 4.1%
  
  # Using league-specific model (legacy)
  python -m src.bbl_pipeline.inference.crex_live_predictor \
    --match-url "CREX_MATCH_URL" \
    --model-dir models/bbl_v12 \
    --feature-store-dir data/bbl_feature_store_v2 \
    --output-json data/live_state.json
  ```

- **Match State Recording (CLI):** Record complete match states during live predictions:
  ```bash
  # Record match states alongside live predictions
  python -m src.bbl_pipeline.inference.crex_live_predictor \
    --match-url "CREX_MATCH_URL" \
    --model-dir models/bbl_v12 \
    --feature-store-dir data/bbl_feature_store_v2 \
    --record-states
  
  # Custom output directory
  python -m src.bbl_pipeline.inference.crex_live_predictor \
    --match-url "CREX_URL" \
    --model-dir models/sa20_v2 \
    --feature-store-dir data/sa20_feature_store_v2 \
    --record-states \
    --states-dir data/match_states/sa20_2025
  
  # Records 80+ columns per ball:
  #   - Raw match state (runs, wickets, overs, batsmen)
  #   - All 50+ computed features
  #   - Complete calibration chain (raw → league)
  #   - CREX market odds + deviation metrics
  #   - Team tiers, match phase, model/feature store versions
  
  # Output: data/match_states/<league>/<match_id>.parquet
  ```

- **Analyze Recorded Matches:** Generate calibration reports and consolidate data:
  ```bash
  # Consolidate all match files
  bbl-pipeline analyze-states --league bbl --consolidate
  
  # Generate calibration report (Brier, ECE, LogLoss)
  bbl-pipeline analyze-states --league sa20 --calibration-report
  
  # Full workflow: consolidate + calibration
  bbl-pipeline analyze-states \
    --league ilt20 \
    --consolidate \
    --calibration-report
  
  # Output files:
  #   - all_matches.parquet (consolidated ball states)
  #   - CALIBRATION_REPORT.md (metrics by innings/phase/tier)
  #   - signal_events.parquet (deviation signals with reversion labels)
  #   - volatility_profiles.parquet (model vs market volatility)
  ```

- **Key Classes for Match State Logging:**
  - `MatchStateLogger` (`src/bbl_pipeline/inference/match_state_logger.py`): Records ball states to Parquet with buffering, error isolation
  - `StateAnalyzer` (`src/bbl_pipeline/analysis/state_analyzer.py`): Consolidates matches, computes calibration metrics, extracts signals
  - **Schemas:** `src/bbl_pipeline/inference/match_state_schema.py` (PyArrow schemas for BALL_STATE, MATCH_METADATA, SIGNAL_EVENT, VOLATILITY_PROFILE)

- **Live Visualization:** Run `streamlit run src/bbl_pipeline/app/live_streamlit_app.py`
- **Calibration Analysis:** See `docs/BBL_V12_MODEL.md` for detailed Brier/ECE breakdown.
- **Comprehensive OOF Calibration Analysis:** 
  - See `BBL_CALIBRATION_OOF_ANALYSIS.md` for complete 7-method comparison
  - Run `python analyze_bbl_calibrators_oof.py` to regenerate analysis
  - Interactive OOF analysis available in Streamlit app under "🔬 BBL Comprehensive OOF Calibration Analysis"
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

### League-Specific Calibration (Recommended Approach)
For adapting the global unified T20 model to specific leagues:

```bash
bbl-pipeline calibrate-league \
  --global-model models/t20_male_v2 \
  --input-file data/<league>_features/training.parquet \
  --league <league> \
  --method temperature  # or platt
```

**Architecture:**
1. **Global model** trained on all T20s (frozen)
2. **League adaptation** via Temperature/Platt scaling (NOT isotonic - too steppy)
3. **Innings-wise calibrators** for stability (2 calibrators per league)

**Temperature vs Platt:**
- **Temperature**: Single parameter T - divides logits by T before sigmoid
  - T > 1: Softer predictions (toward 0.5)
  - T < 1: Sharper predictions (toward 0/1)
- **Platt**: Two parameters (a, b) - sigmoid(a * logit(p) + b)
  - More flexible than temperature
  - Can shift and scale predictions

**When to Use:**
- 200-500+ league matches: Fit temperature/platt on league data
- Limited data: Use global model with dampener or last season's calibrator

### Model Artifacts Checklist
After training a new model, ensure these files exist:
- `champion_model.joblib` - Main XGBLogRegEnsemble model
- `oof_calibrators.pkl` - OOF calibrators from analyze-oof
- `oof_calibration_results.csv` - Detailed metrics by segment
- `OOF_CALIBRATION_REPORT.md` - Auto-generated report
- `league_calibrators/<league>/` - League-specific calibrators (optional)
