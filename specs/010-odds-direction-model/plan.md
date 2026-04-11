# Implementation Plan: Odds Direction Model V1

**Branch**: `010-odds-direction-model` | **Date**: 2026-04-11 | **Spec**: `/specs/010-odds-direction-model/spec.md`
**Input**: Feature specification from `/specs/010-odds-direction-model/spec.md`

## Summary

Build the smallest viable Odds Direction Model (ODM) that predicts the next-12-ball movement of the existing global T20 ML probability, not market odds. V1 should reuse the current Python package, CLI, and live predictor, train on IPL + PSL ball-by-ball features, compare against a simple momentum baseline, and ship as an advisory layer alongside the current ML + MC outputs.

The main repository-specific constraint is that the current `data/*_features_v1/training.parquet` files contain the feature columns needed for modeling but do not preserve `match_id` and ball sequence keys required to build a valid 12-ball future target. The clean V1 path is therefore to add an ODM-specific sequence-preserving dataset export from the existing processing pipeline rather than trying to infer sequence from the current training export.

## Technical Context

**Language/Version**: Python 3.10+ project; current configured workspace environment is Python 3.13.7  
**Primary Dependencies**: pandas, pyarrow, scikit-learn, xgboost, joblib, click, structlog  
**Storage**: Parquet datasets in `data/`, model artifacts in `models/`, JSON metadata/metrics sidecars  
**Testing**: pytest-style test suite under `tests/` plus CLI/inference smoke tests  
**Target Platform**: Local/offline Python CLI and live predictor runtime on Windows/Linux  
**Project Type**: Single Python package with CLI and in-process inference  
**Performance Goals**: ODM inference adds <10 ms per live prediction after warm-up; training completes on ~348k IPL+PSL balls on a workstation without distributed tooling  
**Constraints**: No historical market odds; only 2 recorded match-state files available locally; ODM must never feed back into ML training; no tournament-specific hardcoding; do not disturb current champion ML artifact path  
**Scale/Scope**: Initial V1 on IPL (273,503 rows) + PSL (74,695 rows), 12-ball horizon, one advisory model family, one live integration point

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Gate Status: PASS**

1. **Scalability & Reusability**: Pass. ODM design is league-agnostic and uses `league` as data, not code branching. V1 starts with IPL + PSL only because those feature datasets already exist.
2. **Pipeline-Driven Architecture & Rapid Retraining**: Pass. Plan adds modular CLI steps for ODM dataset preparation, training, and evaluation instead of notebook-only logic.
3. **Reproducibility & Versioning**: Pass. ODM artifacts will include source dataset references, global ML model dependency, feature list, baseline metrics, and training configuration.
4. **Data Integrity & Entity Consistency**: Pass. Sequence-preserving ODM base export will validate uniqueness of `(league, match_id, innings, over, ball)` and prevent cross-match/cross-innings horizon shifts.
5. **Model Calibration & Observability**: Pass with scope note. The constitution's strict ECE threshold remains applicable to the underlying win-probability model. ODM is an advisory delta model, so V1 will validate interval coverage, sign accuracy, baseline lift, and live logging without replacing or recalibrating `model_final_prob`.

**Post-Design Re-check**: Still PASS. The selected design keeps ODM isolated from the main win-probability training loop and introduces no hardcoded league behavior or unversioned artifacts.

## Project Structure

### Documentation (this feature)

```text
specs/010-odds-direction-model/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── odm-inference.openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
src/bbl_pipeline/
├── cli.py                                  # Add ODM commands
├── data/
│   └── processor.py                        # Add ODM base export hook
├── training/
│   ├── odm_dataset.py                      # Build target-ready ODM dataset
│   ├── odm_trainer.py                      # Train quantile/point ODM models
│   └── odm_evaluation.py                   # Baselines, holdout metrics, coverage
└── inference/
    └── odds_direction_model.py             # Load artifacts and score live states

tests/
├── training/
│   ├── test_odm_dataset.py
│   └── test_odm_trainer.py
└── inference/
    └── test_odds_direction_model.py

data/
└── odm_v1/
    ├── ipl_odm_base.parquet
    ├── psl_odm_base.parquet
    ├── training.parquet
    └── evaluation/

models/
└── odm_v1/
    ├── champion_model.joblib
    ├── feature_columns.json
    ├── metrics.json
    ├── baseline_metrics.json
    └── training_manifest.json
```

**Structure Decision**: Keep ODM inside the existing `bbl_pipeline` package and extend the current CLI/inference flow. Avoid creating a separate project or service. Persist ODM-specific data/artifacts in new `data/odm_v1` and `models/odm_v1` directories so the current win-probability model paths remain unchanged.

## Phase 0: Research Decisions

Research outcomes are captured in `research.md`. The key decisions that drive this plan are:

1. Build V1 around `ml_delta_12 = ml_prob[i+12] - ml_prob[i]` generated from `models/t20_male_v2/champion_model.joblib`.
2. Use momentum as the hard baseline: `ml_prob[i] - ml_prob[i-12]`.
3. Keep residual target as a sidecar evaluation target for V1, not the primary shipped objective.
4. Export a new sequence-preserving ODM base dataset instead of repurposing the current `training.parquet` directly.
5. Use XGBoost-based regression first because it is already in the repo dependency set and fits the existing training style.

## Phase 1: Design & Contracts

Design outputs are captured in `data-model.md`, `quickstart.md`, and `contracts/odm-inference.openapi.yaml`.

### Design Choices

1. **Dataset strategy**: Add a second export from `process_bbl_data` for ODM use that keeps sequence identifiers and the existing feature columns.
2. **Training target**: Train the main model on `ml_delta_12`; compute direction from the predicted central delta sign.
3. **Baselines**: Always report zero-delta baseline and momentum baseline before accepting the learned model.
4. **Inference state**: Reuse predictor history already maintained in `crex_live_predictor.py` to cache the last 12 ML probabilities for warm-up and baseline comparison.
5. **Integration**: Make ODM optional via explicit model directory/config. If the ODM model is absent or there is insufficient history, predictor output should include a `warming_up` or `unavailable` status instead of failing.

## Implementation Phases

### Phase 1: Export Sequence-Preserving ODM Base Data

**Goal**: Produce a stable ODM input dataset with both current ML features and sequence keys.

**Work**

1. Extend `src/bbl_pipeline/data/processor.py` to optionally write `odm_base.parquet` alongside the current `training.parquet`.
2. Keep existing model features plus: `league`, `match_id`, `date`, `season`, `innings`, `over`, `ball`.
3. Preserve current de-duplication and sort order by `match_id`, `innings`, `over`, `ball`.
4. Ensure the export is one row per legal ball and excludes malformed/incomplete sequence rows.
5. Generate ODM base files for IPL and PSL only in V1.

**Acceptance Checks**

1. `odm_base.parquet` exists for both leagues.
2. `(match_id, innings, over, ball)` is unique within each league.
3. Row counts are within expected bounds of current league feature datasets after legal-ball filtering.
4. Existing `training.parquet` generation for core ML remains unchanged.

### Phase 2: Build Targets, Baselines, and ODM Training Dataset

**Goal**: Convert ODM base rows into a valid learning table for a 12-ball horizon.

**Work**

1. Create `src/bbl_pipeline/training/odm_dataset.py` to load multiple ODM base files and concatenate with a `league` column.
2. Generate `ml_prob` for every row using `models/t20_male_v2/champion_model.joblib`.
3. Compute `ml_delta_12`, `momentum_baseline_12`, and `residual_delta_12` inside each `(league, match_id, innings)` group only.
4. Add a minimal ODM feature set for V1:
   - existing top ML features already in the dataset
   - `ml_prob`
   - `ml_prob_delta_6`, `ml_prob_delta_12`
   - `ml_rwp_gap = ml_prob - resource_win_prob`
   - `ml_rwp_gap_delta_6`
   - `runs_last_12`, `runs_last_18`, `wickets_last_12`, `pressure_index`, `score_vs_par`, `run_rate_diff`, `acceleration_potential`
5. Drop the first 12 balls of each innings for lag-based features and the last 12 balls for future targets.
6. Save the combined ODM training dataset to `data/odm_v1/training.parquet` with target and baseline columns included.

**Acceptance Checks**

1. No target rows are built across innings or match boundaries.
2. `ml_delta_12` and `momentum_baseline_12` null rates are explained only by start/end-of-innings trimming.
3. A baseline report is emitted showing zero-delta and momentum performance by overall, league, innings, and phase.
4. Recorded match-state data is not used as a primary training source in V1.

### Phase 3: Train Smallest Viable ODM Model

**Goal**: Ship one model family that can predict central direction and interval bounds without new dependencies.

**Work**

1. Add `src/bbl_pipeline/training/odm_trainer.py` using XGBoost regressors.
2. Train three models for the same feature set:
   - lower quantile (p10)
   - central prediction (p50 or point regressor)
   - upper quantile (p90)
3. Derive direction from the sign of the central delta prediction.
4. Keep residual-target experiments offline in evaluation only unless they clearly beat direct-delta prediction.
5. Save a single `champion_model.joblib` bundle plus metrics/feature metadata sidecars under `models/odm_v1/`.

**Validation Strategy**

1. Split by `match_id`, not random rows.
2. Prefer time-aware splits inside each league where dates are available.
3. Report combined metrics and league slices for IPL and PSL.

**Acceptance Checks**

1. Central delta MAE beats the zero baseline.
2. Central delta MAE improves on the momentum baseline by a practical margin, target `>= 2%` relative improvement overall.
3. Direction accuracy is `> 52%` overall and not worse than momentum in either IPL or PSL.
4. Interval coverage for the nominal 80% band falls within `75%-85%` on holdout.
5. If the learned model does not beat momentum, V1 should not be promoted into live predictor output.

### Phase 4: CLI and Artifact Workflow

**Goal**: Make ODM train/evaluate flows repeatable through the existing CLI.

**Work**

1. Extend `src/bbl_pipeline/cli.py` with minimal ODM commands:
   - `export-odm-base`
   - `train-odm`
   - `evaluate-odm`
2. `export-odm-base` should build base datasets for one or more leagues.
3. `train-odm` should accept input parquet(s), global model dir, output model dir, and horizon.
4. `evaluate-odm` should output overall and sliced metrics plus baseline comparison.
5. Keep registry integration out of V1 unless ODM becomes a first-class model selector elsewhere.

**Acceptance Checks**

1. End-to-end ODM training can be run without notebooks.
2. CLI outputs the exact source data and model dependency versions used.
3. Artifacts are written into dedicated ODM directories without altering main ML artifacts.

### Phase 5: Live Inference Integration

**Goal**: Expose ODM as an optional advisory block in live prediction output.

**Work**

1. Add `src/bbl_pipeline/inference/odds_direction_model.py` with a `load()` and `predict()` interface matching repository conventions.
2. Add optional ODM loading to `src/bbl_pipeline/inference/crex_live_predictor.py`.
3. Reuse predictor history to maintain the last 12 `ml_prob` values needed for momentum and warm-up.
4. Output a new JSON block such as:
   - `status`
   - `direction`
   - `delta_mean`
   - `delta_ci_lower`
   - `delta_ci_upper`
   - `momentum_baseline`
   - `edge_vs_momentum`
   - `horizon_balls`
5. If fewer than 12 historical probabilities exist, return `status = warming_up` and skip the score.

**Acceptance Checks**

1. Live predictor still works unchanged when no ODM model dir is provided.
2. ODM output never replaces `model_final_prob`; it is additive only.
3. Added latency stays within the target budget.
4. JSON output is stable and backward-compatible for existing consumers.

### Phase 6: Validation, Rollout Guardrails, and Documentation

**Goal**: Keep V1 honest and prevent a weak advisory model from being mistaken for edge.

**Work**

1. Add `src/bbl_pipeline/training/odm_evaluation.py` for sliced reporting by league, innings, and phase.
2. Run smoke validation on the two recorded state files in `data/match_states/ipl` and `data/match_states/psl` only as qualitative replay checks.
3. Document that ODM predicts movement of the ML model, not market odds.
4. Document that ODM must not feed back into main ML training labels or features.
5. Write a short ODM README or model note under `docs/` once implementation starts.

**Acceptance Checks**

1. Baseline comparison is included in every evaluation report.
2. Replay validation does not crash on recorded state files.
3. All user-facing output labels say `model probability direction`, not `market odds direction`.

## Risks

1. **Sequence key gap in current training parquet**: Current exported training files are not sufficient to generate a correct 12-ball target alone. V1 addresses this by exporting an ODM base dataset from the processor.
2. **Self-referential learning**: ODM predicts future ML movement using features related to the ML model. Baseline comparison against momentum and residual analysis are mandatory safeguards.
3. **No historical market odds**: ODM cannot claim trading-edge validity in V1. It only predicts movement of the repo's ML probability.
4. **Too little recorded live state data**: Only one IPL and one PSL recorded parquet file exist locally, so replay validation is smoke-level only.
5. **Weak signal risk**: If learned performance is flat versus momentum, the correct V1 outcome is no live deployment, not forced integration.

## Acceptance Summary

V1 is acceptable only if all of the following hold:

1. ODM training data is built with correct match/innings sequencing.
2. The trained model beats both zero-delta and momentum baselines on holdout error or sign accuracy.
3. Inference is optional, warm-up aware, and does not affect the existing ML probability path.
4. Artifacts and metrics are versioned in dedicated ODM directories.
5. The implementation remains league-agnostic and pipeline-driven.

## Complexity Tracking

No constitution violations requiring justification.
