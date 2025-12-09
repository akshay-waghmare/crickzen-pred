# Feature Specification: BBL Model Training & Inference

**Feature Branch**: `002-bbl-model-training`
**Created**: 2025-12-09
**Status**: Draft
**Input**: User description: "Implement the BBL model training and inference pipeline. The system must ingest the processed Parquet data and perform feature engineering (calculating historical player averages, strike rates, and venue stats as per selected_features.csv). It must train a probabilistic classifier (e.g., Random Forest or XGBoost) with time-series cross-validation. It must include a calibration step (Isotonic/Platt) to ensure accurate probabilities. Finally, it must provide an inference module that accepts match state (venue, teams, players, over) and enriches it with historical stats to generate predictions."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Feature Engineering & Training (Priority: P1)

As a Data Scientist, I want to transform raw match data into predictive features and train a calibrated model so that I can generate accurate win probabilities.

**Why this priority**: This is the core logic of the prediction system.

**Independent Test**: Run the training pipeline on historical data. Verify that features (rolling averages) are calculated correctly (no data leakage) and that the model achieves a baseline accuracy/log-loss on the test set.

**Acceptance Scenarios**:

1. **Given** the processed Parquet dataset, **When** the feature engineering pipeline runs, **Then** it produces a training dataset with historical stats (e.g., `batsman_avg_last_10`) calculated *prior* to each match.
2. **Given** the training dataset, **When** the model is trained, **Then** it uses time-series cross-validation (training on past, validating on future) to prevent leakage.
3. **Given** the trained model, **When** calibration is applied, **Then** the output probabilities are well-calibrated (verified by a calibration curve/Brier score).
4. **Given** the training completes, **Then** the model artifacts (model, encoders, scalers) are saved to disk.

---

### User Story 2 - Inference Module (Priority: P1)

As an Application, I want to request a prediction for a specific match state so that I can display the win probability to the user.

**Why this priority**: Enables the consumption of the model.

**Independent Test**: Load the saved model artifacts. Pass a mock "upcoming match" state (e.g., "Maxwell batting at MCG, over 10.1"). Verify that the system returns a valid probability (0-1).

**Acceptance Scenarios**:

1. **Given** a match state (Venue: MCG, Batter: Maxwell, Bowler: Starc, Over: 15), **When** `predict()` is called, **Then** the system looks up the latest historical stats for these entities from the feature store/state.
2. **Given** a new/unknown player, **When** `predict()` is called, **Then** the system uses robust fallback values (e.g., global averages) instead of crashing.
3. **Given** the model output, **Then** the system returns both the raw probability and the calibrated probability.

---

### User Story 3 - Model Evaluation & Versioning (Priority: P2)

As a Data Scientist, I want to evaluate the model's performance and version the artifacts so that I can track improvements over time.

**Why this priority**: Essential for iterative improvement and reproducibility.

**Independent Test**: Run the evaluation command. Check that it generates a report (Accuracy, Log Loss, Brier Score) and tags the saved model with a version number.

**Acceptance Scenarios**:

1. **Given** a trained model, **When** evaluated on the hold-out test set (most recent season), **Then** performance metrics are logged.
2. **Given** a successful training run, **Then** artifacts are saved in a versioned directory (e.g., `models/v1.0.0/`).

## Clarifications

### Session 2025-12-09
- Q: Should the spec mandate the Multi-Algorithm Champion Selection pipeline? → A: Yes, update REQ-5 to explicitly require training multiple models and selecting the best based on Brier score.

## Requirements *(mandatory)*

### Feature Engineering
- **REQ-1**: The system MUST calculate **rolling averages** for players (batting average, strike rate) and teams (win rate) over a configurable window (e.g., last 10 matches, all-time).
- **REQ-2**: The system MUST calculate **venue statistics** (average runs per over, toss advantage).
- **REQ-3**: The system MUST ensure **no data leakage**: features for Match N must only use data from Match 1 to N-1. Rolling statistics must be computed using a strictly prior-dated window, excluding the current match's data.
- **REQ-4**: The system MUST encode categorical variables (Teams, Venues) using consistent mappings (Label/Target encoding) derived from the training set.

### Model Training
- **REQ-5**: The system MUST implement a **Multi-Algorithm Training Pipeline** that trains multiple candidate models (Logistic Regression, XGBoost, Random Forest) using identical cross-validation folds.
- **REQ-6**: The system MUST use **Time-Series Split** for validation (not random K-Fold) to respect temporal order.
- **REQ-7**: The system MUST apply **Probability Calibration** (Isotonic or Platt Scaling). It MUST check for minimum data requirements (e.g., >100 samples per bin) and fallback to Platt Scaling or uncalibrated output if insufficient.
- **REQ-8**: The system MUST persist all training artifacts (Model, Encoders, Imputers, Feature Selectors) to disk.
- **REQ-15**: The system MUST automatically select a **Champion Model** based on the lowest Brier Score (primary) and Calibration Error (secondary) on the hold-out set. The champion's metadata MUST be stored in a registry file.

### Inference
- **REQ-9**: The system MUST provide a `Predictor` class that loads artifacts and accepts a "Match State" object.
- **REQ-10**: The `Predictor` MUST handle **missing entities** (new players/venues) gracefully using fallback strategies (e.g., using global league averages for that role).
- **REQ-11**: The system MUST allow "hydrating" a match state: taking raw names/IDs and looking up their pre-calculated historical stats.
- **REQ-14**: The system SHOULD implement a **Feature Store / Snapshot** approach for fast inference lookups. It MUST cache the latest historical stats for all entities to minimize computation time during prediction.

### CLI & Workflow
- **REQ-12**: The system MUST provide CLI commands for `train`, `evaluate`, and `predict`.
- **REQ-13**: The `train` command MUST accept configuration for hyperparameters and feature windows.

## Success Criteria

- **Accuracy**: Model achieves Log Loss < 0.65 (baseline) on the test set.
- **Calibration**: Brier Score < 0.25 (or baseline equivalent); Expected Calibration Error (ECE) < 0.1.
- **Robustness**: Inference does not crash for any valid input combination, even with unknown players (fallback active).
- **Performance**: Inference latency < 100ms per prediction at 50 requests/second load.

## Assumptions

- We assume the "processed Parquet data" from Phase 1 contains all necessary raw events.
- We assume "Match State" for inference includes the current score, wickets, and active players.
- We assume historical stats are sufficient proxies for "form".

