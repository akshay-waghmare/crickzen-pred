# Tasks: BBL Model Training & Inference

**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

## Phase 1: Setup
- [x] T001 Update `pyproject.toml` with new dependencies (xgboost, scikit-learn, joblib)
- [x] T002 Create package structure for `features`, `training`, `inference` in `src/bbl_pipeline/`

## Phase 2: Foundational
- [x] T003 Define `MatchState` dataclass in `src/bbl_pipeline/inference/schema.py`
- [x] T004 Implement `FeatureStore` interface and in-memory implementation in `src/bbl_pipeline/features/store.py`
- [x] T005 Implement rolling window statistics calculator (including global averages for fallbacks) in `src/bbl_pipeline/features/calculator.py`
- [x] T006 Implement venue statistics calculator in `src/bbl_pipeline/features/calculator.py`

## Phase 3: Feature Engineering & Training (US1)
**Goal**: Transform raw data, train multiple models, calibrate them, and select a champion.
- [x] T007 [US1] Implement sklearn-compatible `FeatureTransformer` in `src/bbl_pipeline/features/transformer.py`
- [x] T008 [US1] Implement time-series cross-validation splitter (Train/Calibration/Validation) in `src/bbl_pipeline/training/evaluation.py`
- [x] T009 [US1] Implement multi-model training loop (XGB, RF, LogReg) in `src/bbl_pipeline/training/trainer.py`
- [x] T010 [US1] Implement probability calibration wrapper (Isotonic/Platt) in `src/bbl_pipeline/training/calibration.py`
- [x] T011 [US1] Implement champion model selection logic based on Brier score in `src/bbl_pipeline/training/selection.py`
- [x] T012 [US1] Implement `train` CLI command in `src/bbl_pipeline/cli.py`

## Phase 4: Inference (US2)
**Goal**: Serve predictions using the champion model with low latency.
- [x] T013 [US2] Implement `Predictor` class loading champion artifacts in `src/bbl_pipeline/inference/predictor.py`
- [x] T014 [US2] Implement feature hydration and fallback logic in `src/bbl_pipeline/inference/predictor.py`
- [x] T015 [US2] Implement `predict` CLI command in `src/bbl_pipeline/cli.py`

## Phase 5: Evaluation (US3)
**Goal**: Evaluate model performance and generate reports.
- [x] T016 [US3] Implement comprehensive evaluation metrics (ECE, Brier, LogLoss) in `src/bbl_pipeline/training/evaluation.py`
- [x] T017 [US3] Implement `evaluate` CLI command in `src/bbl_pipeline/cli.py`

## Phase 6: Polish
- [x] T018 Update documentation and quickstart guides

## Dependencies
- US1 (Training) must complete before US2 (Inference) and US3 (Evaluation).
- Foundational tasks (Calculators, Schema) block US1.

## Implementation Strategy
1.  **MVP**: Implement Feature Engineering -> Train Single Model (XGB) -> Predict.
2.  **Enhancement**: Add Calibration -> Multi-Model Selection -> Advanced Metrics.
