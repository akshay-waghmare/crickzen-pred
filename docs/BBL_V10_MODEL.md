# BBL v10 Model Documentation

**Date:** December 31, 2025  
**Model Version:** bbl_v10  
**Training Data:** `data/bbl_features_v2/training.parquet`  
**Feature Store:** `data/bbl_feature_store_v2`

## Overview

BBL v10 is an XGBLogRegEnsemble model for predicting T20 cricket match outcomes. This version includes a critical fix to the wicket penalty calculation and comprehensive calibration analysis.

## Model Architecture

### Ensemble: XGBLogRegEnsemble
- **XGBoost Weight:** 50%
- **Logistic Regression Weight:** 50%
- **Calibration:** Innings-Specific Isotonic Regression (CV-OOF fitted)

### Training Statistics
| Metric | Value |
|--------|-------|
| **Training Samples** | 141,435 |
| **Matches** | 618 |
| **Features** | 25 |
| **Brier Score (raw)** | 0.1818 |
| **Brier Score (calibrated)** | 0.1800 |

## Key Changes from v9

### 1. Wicket Penalty Fix
**Problem:** Previous versions applied wicket penalty to `expected_final_score`, which included runs already scored. This caused underestimation of win probability for high 1st innings scores (e.g., 202/7 showing 45% instead of ~55%).

**Solution:** The penalty now only applies to **future projected runs**, not runs already scored:

```python
# OLD (incorrect):
adjusted_expected_score = expected_final_score * wicket_capability

# NEW (correct):
additional_runs_projected = max(0, expected_final_score - current_score)
adjusted_additional_runs = additional_runs_projected * wicket_capability
adjusted_expected_score = current_score + adjusted_additional_runs
```

### 2. Clean Rebuild
- Deleted all previous BBL artifacts (v9, features, feature store)
- Ingested fresh from `bbl_male_json/` (618 matches)
- Regenerated features and feature store

## Calibration Analysis

### Overall Performance (141,435 samples)

| Metric | Raw Model | Calibrated | Resource Prob |
|--------|-----------|------------|---------------|
| **Brier Score** | **0.1456** ✅ | 0.1482 | 0.1930 |
| **ECE** | 0.0558 | 0.0607 | **0.0472** ✅ |

### Innings-Specific Performance

#### Innings 1 (73,875 samples - Setting Target)
| Metric | Raw Model | Calibrated | Resource Prob |
|--------|-----------|------------|---------------|
| **Brier** | **0.1775** ✅ | 0.1830 | 0.2260 |
| **ECE** | **0.0642** ✅ | 0.0827 | 0.0934 |

#### Innings 2 (67,560 samples - Chasing)
| Metric | Raw Model | Calibrated | Resource Prob |
|--------|-----------|------------|---------------|
| **Brier** | 0.1107 | **0.1102** ✅ | 0.1569 |
| **ECE** | 0.0466 | **0.0367** ✅ | 0.0407 |

### Phase-by-Phase Breakdown

#### Innings 1 Phases
| Phase | Samples | Best Brier | Best ECE |
|-------|---------|------------|----------|
| Powerplay (1-6) | 18,658 | Raw (0.2013) | Raw (0.0925) |
| Middle (7-15) | 33,364 | Raw (0.1739) | Raw (0.0537) |
| Death (16-20) | 18,200 | Raw (0.1622) | Raw (0.0549) |

#### Innings 2 Phases
| Phase | Samples | Best Brier | Best ECE |
|-------|---------|------------|----------|
| Powerplay (1-6) | 18,700 | Cal (0.1565) | Cal (0.0497) |
| Middle (7-15) | 32,475 | Cal (0.1060) | **Res (0.0281)** |
| Death (16-20) | 14,780 | Raw (0.0674) | Cal (0.0600) |

## When to Trust Which Probability

### Simple Rules

**Innings 1 (All Phases):**
> Use **Raw Model Probability** - it's already well-calibrated out of the box

**Innings 2:**
| Phase | Best for Accuracy | Best for Calibration |
|-------|-------------------|---------------------|
| Powerplay | Inn-Specific Calibrated | Inn-Specific Calibrated |
| Middle | Inn-Specific Calibrated | **Resource Win Prob** |
| Death | Raw | Inn-Specific Calibrated |

### Key Insight
BBL's raw model is much better calibrated than ILT20's raw model, especially in innings 1. This is likely due to the larger training dataset (618 matches vs 99).

## Feature Store

### Contents
| File | Records | Description |
|------|---------|-------------|
| `team_ratings.parquet` | 8 teams | Team win rates (overall + situation-specific) |
| `player_stats.parquet` | 508 players | Rolling batting/bowling averages |
| `venue_stats.parquet` | 31 venues | Venue-specific scores and win rates |

### Team Columns
- `team`, `win_rate`, `matches`, `bat_first_wr`, `bowl_first_wr`

### Generated
- Date: 2025-12-31
- Source: 618 BBL matches from Cricsheet

## Per-Over Calibrators

BBL v10 has two separate per-over calibrator files, optimized for different metrics:

### Calibrator Files
| File | Optimized For | Use Case |
|------|---------------|----------|
| `per_over_calibrators.pkl` | ECE (Expected Calibration Error) | Best calibration/reliability |
| `per_over_calibrators_brier.pkl` | Brier Score (Log Loss) | Best accuracy |

### Key Findings
- **Innings 1:** Both ECE and Brier optimizers select `source: raw` - they produce **identical outputs**
- **Innings 2:** ECE uses `source: cal`, Brier uses `source: raw` - produces **4-5% difference**
- **Log Loss Analysis:** Brier-optimized calibrator wins 39/40 overs for Log Loss metric

### Streamlit App Usage
- **Blue Box (Best Accuracy):** Uses `per_over_calibrators_brier.pkl`
- **Orange Box (Best ECE):** Uses `per_over_calibrators.pkl`

For innings 1, both boxes will show the same probability. The difference appears in innings 2.

## Files

| File | Description |
|------|-------------|
| `models/bbl_v10/champion_model.joblib` | Trained XGBLogRegEnsemble |
| `models/bbl_v10/isotonic_calibrator.pkl` | Innings-specific isotonic calibrators |
| `models/bbl_v10/per_over_calibrators.pkl` | ECE-optimized per-over calibrators |
| `models/bbl_v10/per_over_calibrators_brier.pkl` | Brier-optimized per-over calibrators |
| `data/bbl_feature_store_v2/` | Feature store (team, player, venue stats) |
| `data/bbl_features_v2/training.parquet` | Training features |

## Usage

### Training
```bash
bbl-pipeline train \
  --input-file data/bbl_features_v2/training.parquet \
  --output-dir models/bbl_v10
```

### Generate Calibrator
```bash
bbl-pipeline generate-oof \
  --input-file data/bbl_features_v2/training.parquet \
  --model-dir models/bbl_v10
```

### Live Prediction
```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "https://crex.com/scoreboard/.../live" \
  --model-dir models/bbl_v10 \
  --feature-store-dir data/bbl_feature_store_v2 \
  --output-json data/live_state.json
```

## Comparison with ILT20 v5

| Metric | BBL v10 | ILT20 v5 |
|--------|---------|----------|
| Training Matches | 618 | 99 |
| Training Samples | 141,435 | 23,209 |
| Brier (raw) | 0.1818 | 0.2084 |
| Brier (calibrated) | 0.1800 | 0.1886 |
| Inn1 Best | Raw | - |
| Inn2 Best | Calibrated | Calibrated |

BBL's larger dataset leads to a better-calibrated raw model, especially in innings 1.
