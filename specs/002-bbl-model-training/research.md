# Research: BBL Model Training & Inference

**Feature**: `002-bbl-model-training`
**Date**: 2025-12-09

## Unknowns & Decisions

### 1. Calibration Strategy
**Question**: How to implement calibration (Isotonic/Platt) with time-series cross-validation?
**Research**: Scikit-learn's `CalibratedClassifierCV` supports `cv="prefit"` or cross-validation. However, standard CV shuffles data.
**Decision**: We will implement a custom calibration loop.
1. Split data into Train / Calibration / Test (chronologically).
2. Train model on Train.
3. Calibrate on Calibration set (using `CalibratedClassifierCV(cv="prefit")` or `IsotonicRegression` directly).
4. Evaluate on Test.
**Rationale**: Ensures strict temporal separation as per Constitution Principle V.

### 2. Feature Store Implementation
**Question**: Do we need a heavy feature store (e.g., Feast) or a lightweight solution?
**Research**: The dataset (BBL) is relatively small (< 1GB). Latency requirement is < 100ms.
**Decision**: Implement a lightweight **In-Memory Feature Store**.
- Load historical stats into a Pandas DataFrame or Dictionary at startup.
- `Predictor` class queries this in-memory structure.
- **Persistence**: Save the feature state as a Parquet file (`features_snapshot.parquet`) alongside the model.
**Rationale**: Avoids infrastructure overhead while meeting latency goals.

### 3. Handling Super Overs
**Question**: Should Super Overs be included in the training data?
**Research**: Super Overs are tie-breakers and have different dynamics.
**Decision**: Exclude Super Overs from the main win probability model training.
**Rationale**: They represent a different game mode. The model predicts the winner of the *regular* match.

### 4. Model Choice
**Question**: Random Forest vs XGBoost?
**Research**: XGBoost generally performs better on tabular data but requires more tuning. Random Forest is robust out-of-the-box.
**Decision**: Start with **XGBoost** (or LightGBM) as the primary candidate due to better handling of missing values and generally higher performance, but keep the interface generic to swap in Random Forest if needed.
**Rationale**: State-of-the-art for tabular sports data.

## Technology Selection

- **Training**: `scikit-learn`, `xgboost`
- **Persistence**: `joblib`
- **Data Processing**: `pandas`, `numpy`
