# Tasks: Odds Direction Model V1

**Input**: Design documents from `/specs/010-odds-direction-model/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md, contracts/odm-inference.openapi.yaml

**Tests**: Formal TDD is not required for this feature, but V1 includes repository-specific validation and smoke-check tasks for export integrity, holdout performance, and live inference wiring.

**Organization**: Tasks are grouped by user story and ordered for the smallest viable V1: sequence-preserving ODM export, leakage-safe target generation, baseline comparison, model training, artifact saving, and basic inference integration.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no blocking dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`, `[US4]`)
- Every task includes the exact repository path to change or validate

## Phase 1: Setup (Shared ODM Scaffolding)

**Purpose**: Establish the ODM-specific module and validation surface inside the existing package without changing the current champion ML flow.

- [ ] T001 Add ODM command placeholders and shared option parsing in `src/bbl_pipeline/cli.py`
- [ ] T002 [P] Create the ODM dataset and training module stubs in `src/bbl_pipeline/training/odm_dataset.py` and `src/bbl_pipeline/training/odm_trainer.py`
- [ ] T003 [P] Create the ODM evaluation and inference module stubs in `src/bbl_pipeline/training/odm_evaluation.py` and `src/bbl_pipeline/inference/odds_direction_model.py`
- [ ] T004 [P] Create ODM validation script entry points in `scripts/validation/validate_odm_base.py`, `scripts/validation/validate_odm_dataset.py`, and `scripts/validation/validate_odm_replay.py`

**Checkpoint**: ODM file layout exists in the package, CLI, and validation scripts so implementation can proceed without touching unrelated model paths.

---

## Phase 2: Foundational (Blocking ODM Data Integrity)

**Purpose**: Build the sequence-preserving export and shared validation rules that every downstream ODM task depends on.

**⚠️ CRITICAL**: No ODM dataset, training, or inference work should start until this phase is complete.

- [ ] T005 Extend sequence-preserving ODM base export in `src/bbl_pipeline/data/processor.py` to write legal-ball rows with `league`, `match_id`, `date`, `season`, `innings`, `over`, and `ball`
- [ ] T006 Update `src/bbl_pipeline/cli.py` to expose `export-odm-base` with league-specific inputs and dedicated ODM output paths under `data/odm_v1/`
- [ ] T007 [P] Implement uniqueness, sort-order, and missing-key validation in `scripts/validation/validate_odm_base.py` for `data/odm_v1/*_odm_base.parquet`
- [ ] T008 [P] Add ODM artifact path and acceptance notes to `specs/010-odds-direction-model/quickstart.md`

**Checkpoint**: IPL and PSL ODM base exports can be produced reproducibly, and validation can prove that `(league, match_id, innings, over, ball)` is unique and ordered.

---

## Phase 3: User Story 1 - EDA Discovery via Training-Ready ODM Dataset (Priority: P0)

**Goal**: Convert ODM base exports into a leakage-safe training table and baseline report that confirms the 12-ball target is valid before model promotion.

**Independent Test**: Running the ODM dataset build on IPL + PSL produces `data/odm_v1/training.parquet` with no cross-match or cross-innings target leakage, plus a baseline report that slices zero-delta and momentum performance by league, innings, and phase.

**Acceptance Checks**:

- `ml_delta_12` is computed only within each `(league, match_id, innings)` group
- Nulls in lag/lead features are explained only by start-of-innings and end-of-innings trimming
- `momentum_baseline_12` is available everywhere the target is available
- The 12-ball horizon and baseline slices are documented in the notebook or report artifacts for this feature

### Implementation for User Story 1

- [ ] T009 [US1] Implement grouped ODM dataset loading and concatenation for IPL + PSL in `src/bbl_pipeline/training/odm_dataset.py`
- [ ] T010 [US1] Implement global-model probability generation from `models/t20_male_v2/champion_model.joblib` in `src/bbl_pipeline/training/odm_dataset.py`
- [ ] T011 [US1] Implement `ml_delta_12`, `momentum_baseline_12`, `residual_delta_12`, and innings-safe trimming in `src/bbl_pipeline/training/odm_dataset.py`
- [ ] T012 [P] [US1] Implement V1 ODM feature derivations including `ml_prob_delta_6`, `ml_prob_delta_12`, `ml_rwp_gap`, and `ml_rwp_gap_delta_6` in `src/bbl_pipeline/training/odm_dataset.py`
- [ ] T013 [P] [US1] Implement baseline reporting by overall, league, innings, and phase in `src/bbl_pipeline/training/odm_evaluation.py`
- [ ] T014 [US1] Add a CLI entry in `src/bbl_pipeline/cli.py` to build `data/odm_v1/training.parquet` and emit baseline summaries from `src/bbl_pipeline/training/odm_dataset.py`
- [ ] T015 [US1] Implement leakage, null-rate, and boundary-trim validation in `scripts/validation/validate_odm_dataset.py`
- [ ] T016 [US1] Refresh the analysis workflow in `specs/010-odds-direction-model/eda_odds_direction.ipynb` to inspect the exported ODM training dataset and rank baseline slices

**Checkpoint**: User Story 1 is complete when ODM training data can be rebuilt from base exports and the baseline report proves the target-generation logic is trustworthy.

---

## Phase 4: User Story 2 - Direction Classification from Central Delta Model (Priority: P1) 🎯 MVP

**Goal**: Train the smallest viable ODM that predicts the central 12-ball delta, derives UP/DOWN from its sign, and only promotes if it clears baseline thresholds.

**Independent Test**: Training on `data/odm_v1/training.parquet` produces a central ODM model and metrics where holdout MAE beats the zero-delta baseline, relative MAE improves on momentum by at least the agreed practical threshold, and direction accuracy is not worse than momentum for either IPL or PSL.

**Acceptance Checks**:

- Splits are grouped by `match_id` and ordered by date where available
- Promotion logic blocks a weak model from being treated as live-ready
- `metrics.json`, `baseline_metrics.json`, and `training_manifest.json` are written under `models/odm_v1/`
- Artifact saving does not modify existing ML or MC artifact directories

### Implementation for User Story 2

- [ ] T017 [US2] Implement grouped train-validation splitting and baseline go/no-go evaluation in `src/bbl_pipeline/training/odm_trainer.py`
- [ ] T018 [US2] Implement the central XGBoost ODM regressor and derive `direction` from predicted delta sign in `src/bbl_pipeline/training/odm_trainer.py`
- [ ] T019 [P] [US2] Implement holdout metrics, league slices, and momentum comparison summaries in `src/bbl_pipeline/training/odm_evaluation.py`
- [ ] T020 [US2] Implement artifact saving for `champion_model.joblib`, `feature_columns.json`, `metrics.json`, `baseline_metrics.json`, and `training_manifest.json` in `src/bbl_pipeline/training/odm_trainer.py`
- [ ] T021 [US2] Extend `src/bbl_pipeline/cli.py` with `train-odm` and `evaluate-odm` commands that call `src/bbl_pipeline/training/odm_trainer.py` and `src/bbl_pipeline/training/odm_evaluation.py`
- [ ] T022 [US2] Add a repository-specific holdout verification workflow in `scripts/validation/validate_odm_dataset.py` for MAE, sign accuracy, and per-league acceptance checks
- [ ] T023 [US2] Document the V1 ODM training command sequence and promotion thresholds in `docs/ODM_V1.md`

**Checkpoint**: User Story 2 is complete when a single central ODM model can be trained and saved reproducibly, with metrics that justify keeping ODM in scope for live inference.

---

## Phase 5: User Story 3 - Delta with Confidence Intervals and Basic Inference Integration (Priority: P1)

**Goal**: Add interval bounds and optional live predictor integration without changing the existing ML probability output path.

**Independent Test**: With an ODM artifact present, the live predictor emits an additive ODM block with `status`, `direction`, `delta_mean`, `delta_ci_lower`, `delta_ci_upper`, `momentum_baseline`, `edge_vs_momentum`, `confidence`, and `horizon_balls`; with insufficient history or no artifact it returns `warming_up` or `unavailable` without breaking the rest of the prediction payload.

**Acceptance Checks**:

- Lower, center, and upper predictions are persisted in a single ODM bundle with explicit `horizon_balls = 12`
- Holdout interval coverage lands in the expected acceptance band before live enablement
- ODM inference stays additive and does not overwrite `model_final_prob`
- Warm-up logic reuses existing prediction history rather than inventing a separate state store

### Implementation for User Story 3

- [ ] T024 [US3] Implement lower, center, and upper ODM regressors plus bound-order correction in `src/bbl_pipeline/training/odm_trainer.py`
- [ ] T025 [P] [US3] Implement interval coverage, sharpness, and confidence-band reporting in `src/bbl_pipeline/training/odm_evaluation.py`
- [ ] T026 [US3] Implement `OddsDirectionModel.load()` and `OddsDirectionModel.predict()` with `ready`, `warming_up`, and `unavailable` states in `src/bbl_pipeline/inference/odds_direction_model.py`
- [ ] T027 [US3] Integrate optional ODM loading, recent-ML-prob history reuse, and additive JSON output into `src/bbl_pipeline/inference/crex_live_predictor.py`
- [ ] T028 [US3] Align the in-process ODM response fields with `specs/010-odds-direction-model/contracts/odm-inference.openapi.yaml` in `src/bbl_pipeline/inference/odds_direction_model.py`
- [ ] T029 [US3] Implement replay smoke validation for IPL and PSL recorded states in `scripts/validation/validate_odm_replay.py`
- [ ] T030 [US3] Update live ODM usage and warm-up expectations in `specs/010-odds-direction-model/quickstart.md`

**Checkpoint**: User Story 3 is complete when ODM artifacts can drive additive live predictions safely and replay validation confirms the output shape and warm-up behavior.

---

## Phase 6: User Story 4 - Combined Betting Signal (Priority: P2)

**Goal**: Layer ODM direction onto the existing edge display only after the V1 advisory model has passed its baseline and interval gates.

**Independent Test**: When ODM status is `ready`, console and JSON consumers can distinguish a favorable edge that is strengthening from one that is weakening; when ODM is not ready, the current ML and MC outputs remain unchanged.

**Acceptance Checks**:

- Combined signal wording refers to model-probability direction, not market odds direction
- No existing output consumer breaks when the ODM block is absent
- Combined recommendations remain advisory and do not feed back into training or calibration

### Implementation for User Story 4

- [ ] T031 [US4] Implement an ODM-aware advisory decision helper in `src/bbl_pipeline/inference/display.py`
- [ ] T032 [US4] Surface combined ODM plus edge messaging in `src/bbl_pipeline/inference/crex_live_predictor.py`
- [ ] T033 [US4] Extend replay validation for combined-signal fallback behavior in `scripts/validation/validate_odm_replay.py`

**Checkpoint**: User Story 4 is complete when combined betting-language output is additive, guarded behind ODM readiness, and clearly downstream of the existing probability model.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, rollout notes, and pragmatic cleanup after the V1 ODM path is working.

- [ ] T034 [P] Add ODM artifact lineage, source datasets, and go-no-go notes to `docs/ODM_V1.md`
- [ ] T035 [P] Add a one-command validation checklist for export, training, evaluation, and replay in `specs/010-odds-direction-model/quickstart.md`
- [ ] T036 Run the full ODM quickstart flow and record expected output files and acceptance results in `specs/010-odds-direction-model/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1; blocks all downstream ODM work because sequence-preserving export is the basis for valid targets.
- **User Story 1 (Phase 3)**: Depends on Phase 2; must complete before model training because it produces `data/odm_v1/training.parquet` and baseline summaries.
- **User Story 2 (Phase 4)**: Depends on User Story 1; requires the training dataset and baseline acceptance logic.
- **User Story 3 (Phase 5)**: Depends on User Story 2; requires saved ODM artifacts before live inference can be wired safely.
- **User Story 4 (Phase 6)**: Depends on User Story 3; combined advisory output is explicitly later than core ODM inference.
- **Polish (Phase 7)**: Depends on the user stories you choose to ship.

### User Story Dependencies

- **US1**: No dependency on other user stories, but depends on foundational export support.
- **US2**: Depends on US1 because the central model trains from the ODM training dataset and its baseline report.
- **US3**: Depends on US2 because interval and live inference require saved model artifacts and promotion gates.
- **US4**: Depends on US3 because it only wraps the additive ODM output after basic inference is stable.

### Dependency Graph

`Phase 1 -> Phase 2 -> US1 -> US2 -> US3 -> US4 -> Phase 7`

---

## Parallel Opportunities

- **Setup**: `T002`, `T003`, and `T004` can proceed in parallel after `T001` defines the CLI surface.
- **Foundational**: `T007` and `T008` can run in parallel once `T005` and `T006` define the export contract.
- **US1**: `T012` and `T013` can run in parallel after `T011` establishes grouped target generation.
- **US2**: `T019` and `T020` can run in parallel after `T018` establishes the central model output.
- **US3**: `T025` and `T028` can run in parallel after `T024` defines the quantile artifact structure.
- **Polish**: `T034` and `T035` can run in parallel once the shipped scope is clear.

### Parallel Example: User Story 1

```text
T012 [US1] Implement V1 ODM feature derivations in src/bbl_pipeline/training/odm_dataset.py
T013 [US1] Implement baseline reporting in src/bbl_pipeline/training/odm_evaluation.py
```

### Parallel Example: User Story 2

```text
T019 [US2] Implement holdout metrics in src/bbl_pipeline/training/odm_evaluation.py
T020 [US2] Implement artifact saving in src/bbl_pipeline/training/odm_trainer.py
```

### Parallel Example: User Story 3

```text
T025 [US3] Implement interval coverage reporting in src/bbl_pipeline/training/odm_evaluation.py
T028 [US3] Align ODM response fields with specs/010-odds-direction-model/contracts/odm-inference.openapi.yaml
```

---

## Implementation Strategy

### Smallest Viable V1

1. Complete Phase 1 and Phase 2.
2. Complete User Story 1 to get a leakage-safe ODM training dataset and baseline report.
3. Complete User Story 2 to train and save the central ODM artifact with go-no-go checks.
4. Complete the core of User Story 3 to add quantile bounds and optional live inference integration.
5. Stop and validate before attempting User Story 4.

### Suggested MVP Scope

The smallest shippable ODM V1 is **Phase 1 + Phase 2 + US1 + US2 + US3**. `US4` should remain a follow-on once the additive ODM block is trustworthy in replay and live smoke checks.

### Incremental Delivery

1. Ship export and dataset validation first.
2. Add baseline reports and central-model training next.
3. Add quantile bounds and artifact saving.
4. Add optional live integration only after model promotion checks pass.
5. Add combined betting-language output last, if still justified.

---

## Notes

- All tasks are dependency-ordered for a pragmatic V1 rather than a full research program.
- Residual-target experiments are intentionally deferred to evaluation sidecars unless the direct-delta model fails to beat momentum.
- The task list keeps ODM additive to the existing ML and MC outputs and avoids touching `models/t20_male_v2` artifact paths.
- Validation tasks are mandatory for export integrity, holdout promotion, and live replay safety.