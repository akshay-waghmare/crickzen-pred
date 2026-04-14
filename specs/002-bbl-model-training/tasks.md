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
  - Global metrics written to `metrics.json`
  - **Segment breakdown** written to `segment_metrics.csv`: rows keyed by (innings, phase, wickets_bucket, rrr_bucket); columns: Brier, LogLoss, ECE, N samples
    - `innings`: 1 or 2
    - `phase`: powerplay / middle / death
    - `wickets_bucket`: 0-2 / 3-5 / 6-10
    - `rrr_bucket`: <7 / 7-12 / >12 (second innings only)
  - Global Brier can mask phase-specific weakness; segment breakdown is the primary diagnostic tool
- [x] T017 [US3] Implement `evaluate` CLI command in `src/bbl_pipeline/cli.py`

## Phase 6: Polish
- [x] T018 Update documentation and quickstart guides

## Phase 7: Guardrails (Retroactive improvements)

- [x] T022 **Data versioning** — Write `data_version.json` during `train` CLI command
  - Compute SHA-256 of the input parquet file(s)
  - Write to model output dir: `{"dataset_hash": "<sha256>", "source_files": [...], "date_range": "...", "row_count": N}`
  - `champion.json` includes `data_version_hash` field linking to the exact data used

- [x] T019 **Drift monitoring** — Add rolling Brier/LogLoss window (last 50 matches) to `src/bbl_pipeline/training/evaluation.py`
  - Compute rolling metric alongside overall holdout metric in `evaluate` CLI command
  - Write `rolling_drift.csv` (columns: `match_date`, `rolling_brier_50`, `rolling_logloss_50`) to model output dir
  - Alert (log WARNING) if rolling Brier degrades > 0.02 vs training-set Brier — signals season/pitch/scoring drift requiring retrain

- [x] T020 **Feature importance + SHAP hooks** — Add to `src/bbl_pipeline/training/trainer.py` and `src/bbl_pipeline/inference/predictor.py`
  - At training time: dump `feature_importance.csv` (XGBoost `feature_importances_`, LogReg coefficients) to model output dir
  - In `Predictor`: add `explain(match_state) -> dict` method that returns per-feature contributions using XGBoost's `predict(output_margin=True)` + manual SHAP if shap is installed
  - In debug mode (`--debug` flag on `predict` CLI): attach full feature snapshot to prediction JSON output

- [x] T021 **Inference latency test** — Add to `tests/inference/test_predictor.py`
  - Time 100 sequential `Predictor.predict()` calls on a realistic MatchState
  - Assert p50 latency < 50ms and p99 latency < 100ms
  - Run as part of CI to catch regressions when new features are added

## Dependencies
- US1 (Training) must complete before US2 (Inference) and US3 (Evaluation).
- Foundational tasks (Calculators, Schema) block US1.

## Implementation Strategy
1.  **MVP**: Implement Feature Engineering -> Train Single Model (XGB) -> Predict.
2.  **Enhancement**: Add Calibration -> Multi-Model Selection -> Advanced Metrics.
