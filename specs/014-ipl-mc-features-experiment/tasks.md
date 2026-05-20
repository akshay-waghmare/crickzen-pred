# Tasks: IPL MC Features Experiment (014-ipl-mc-features-experiment)

**Input**: `specs/014-ipl-mc-features-experiment/plan.md`, `specs/014-ipl-mc-features-experiment/spec.md`  
**Feature Branch**: `014-ipl-mc-features-experiment`  
**Date**: 2026-04-27

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other tasks in the same phase because it touches different files or is read-only.
- **[Story]**: User story from `spec.md`.
- This task list is for an experiment. Do not modify production IPL defaults until promotion gates pass.

---

## Phase 1: Setup and Pre-flight

**Purpose**: Confirm the current IPL v6 artefacts and understand whether feature rows contain enough state to reconstruct MC simulations.

- [ ] T001 Verify `data/ipl_features_v6/training.parquet` and `data/ipl_features_v6/training_sampled.parquet` exist.
- [ ] T002 [P] Verify `models/ipl_v6/champion_model.joblib`, `models/ipl_v6/oof_calibration_results.csv`, and `models/ipl_v6/OOF_CALIBRATION_REPORT.md` exist.
- [ ] T003 [P] Inspect columns in `data/ipl_features_v6/training_sampled.parquet` and document required state columns for MC reconstruction in `experiments/ipl_mc_features_v1/cache_quality.json` once the experiment script exists.
- [ ] T004 [P] Create the experiment output directory `experiments/ipl_mc_features_v1/` with no changes to `models/ipl_v6`.

**Checkpoint**: Data/model preconditions are known, and any missing state columns are identified before coding the experiment.

---

## Phase 2: Experiment Script Skeleton (Foundation)

**Purpose**: Add a single script that owns cache generation, model comparison, metrics, and report writing.

- [ ] T005 [US1] Create `scripts/analyze_ipl_mc_features_experiment.py` with CLI options: `--input`, `--output-dir`, `--mode`, `--n-sims`, `--seed`, `--resume`, `--horizon-balls`, and `--max-rows`.
- [ ] T006 [US1] Add shared metric helpers in the script for Brier, 10-bin ECE, safe log loss, and baseline delta calculation.
- [ ] T007 [US1] Add report writers in the script for `metrics.csv`, `segment_metrics.csv`, `feature_importance.csv`, `reliability_bins.csv`, `cache_quality.json`, and `REPORT.md`.
- [ ] T008 [US1] Add unit-testable pure helpers in the script for phase bucketing, probability clipping, and feature variant construction.

**Checkpoint**: The script can run in dry mode and write empty/placeholder artefacts without touching production files.

---

## Phase 3: Historical MC Feature Cache (US2 - P1)

**Goal**: Generate reproducible MC-derived features for IPL historical rows.

**Independent Test**: Run the script on a small row limit and confirm `mc_feature_cache.parquet` joins one-to-one with selected input rows.

- [ ] T009 [US2] Implement row-to-`MatchState` reconstruction in `scripts/analyze_ipl_mc_features_experiment.py` using IPL feature row columns; fail with a clear missing-column report if required columns are absent.
- [ ] T010 [US2] Implement raw MC simulation for each eligible row using an independent/resource-based evaluator, fixed seed, configurable `--n-sims`, and configurable `--horizon-balls`.
- [ ] T011 [US2] Write cache columns `mc_raw_win_prob`, `mc_simulation_std`, row key metadata, and simulation metadata to `experiments/ipl_mc_features_v1/mc_feature_cache.parquet`.
- [ ] T012 [US2] Implement `--resume` so existing cache rows are reused and incomplete rows continue without duplicates.
- [ ] T013 [US2] Implement skipped-row accounting in `cache_quality.json`, including counts by skip reason and missing column names.
- [ ] T014 [P] [US2] Add a small test file `tests/unit/test_ipl_mc_features_experiment.py` covering row-key generation, phase bucketing, gap feature calculation, and cache join validation using synthetic rows.

**Checkpoint**: Pilot cache generation is reproducible and auditable.

---

## Phase 4: Fold-Local MC Calibration (US1 - P1)

**Goal**: Convert raw MC probabilities into leak-free calibrated `mc_win_prob` values inside each evaluation fold.

**Independent Test**: A synthetic test proves validation labels are not used when fitting the MC calibrator for that validation fold.

- [ ] T015 [US1] Implement time-series/CV split creation in `scripts/analyze_ipl_mc_features_experiment.py`, reusing existing split patterns where practical.
- [ ] T016 [US1] Implement fold-local MC Platt calibration by innings: fit on train fold `mc_raw_win_prob` and labels, transform validation fold only.
- [ ] T017 [US1] Add calibrated feature construction for each validation fold: `mc_win_prob`, `mc_resource_gap`, `mc_resource_abs_gap`, and `mc_simulation_std`.
- [ ] T018 [US1] Add tests in `tests/unit/test_ipl_mc_features_experiment.py` proving fold-local calibration does not read validation labels and preserves row order.

**Checkpoint**: Calibrated MC features are available for validation folds without leakage.

---

## Phase 5: Model Variant Evaluation (US1 - P1)

**Goal**: Compare baseline IPL v6 features against MC-augmented variants using identical split and metric protocols.

**Independent Test**: Pilot mode produces `metrics.csv` with rows for all required methods and valid Brier/ECE/log loss values.

- [ ] T019 [US1] Implement `baseline_ipl_v6_features` training/evaluation using the current `XGBLogRegEnsemble` feature behavior.
- [ ] T020 [US1] Implement `mc_standalone_calibrated` as a probability-only baseline using calibrated `mc_win_prob`.
- [ ] T021 [US1] Implement `ml_add_mc_win_prob` by extending candidate feature selection to include `mc_win_prob`.
- [ ] T022 [US1] Implement `ml_add_mc_gap_features` by extending candidate feature selection to include `mc_win_prob`, `mc_resource_gap`, `mc_resource_abs_gap`, and `mc_simulation_std`.
- [ ] T023 [US1] Implement `ml_replace_resource_with_mc` by replacing `resource_win_prob` with `mc_win_prob` in a copy of each fold's feature frame.
- [ ] T024 [US1] Export overall metrics and deltas versus baseline to `experiments/ipl_mc_features_v1/metrics.csv`.
- [ ] T025 [US1] Export segmented metrics by innings and phase to `experiments/ipl_mc_features_v1/segment_metrics.csv`.
- [ ] T026 [US1] Export feature importance for ML variants to `experiments/ipl_mc_features_v1/feature_importance.csv`.

**Checkpoint**: The experiment can decide whether any MC feature variant beats the baseline on pilot data.

---

## Phase 6: Reporting and Promotion Gates (US3 - P2)

**Goal**: Produce a clear go/no-go report, not just raw metrics.

**Independent Test**: `REPORT.md` names the winning method, states whether promotion gates passed, and lists the exact reasons when they fail.

- [ ] T027 [US3] Implement promotion gate evaluation in `scripts/analyze_ipl_mc_features_experiment.py`: Brier improvement >= 0.001, log loss not worse, ECE not worse, and no innings/phase Brier regression > 0.003.
- [ ] T028 [US3] Generate `experiments/ipl_mc_features_v1/REPORT.md` with summary tables, metric deltas, segment regressions, feature importance notes, cache quality, and recommendation.
- [ ] T029 [US3] Add reliability bin output to `experiments/ipl_mc_features_v1/reliability_bins.csv` for baseline and best MC variant.
- [ ] T030 [US3] Add a report section explicitly documenting inference latency risk and whether the result should be "no promotion", "candidate only", or "ready for live dry run".

**Checkpoint**: The experiment output is decision-ready.

---

## Phase 7: Full Run and Validation

**Purpose**: Move from pilot to full IPL v6 training data only after the implementation behaves correctly on sampled data.

- [ ] T031 Run pilot mode on `data/ipl_features_v6/training_sampled.parquet` with `--n-sims 100` and verify all artefacts are generated.
- [ ] T032 Run focused tests: `python -m pytest tests/unit/test_ipl_mc_features_experiment.py -q`.
- [ ] T033 Run full mode on `data/ipl_features_v6/training.parquet` with resume enabled and a documented `--n-sims` value.
- [ ] T034 Inspect `experiments/ipl_mc_features_v1/REPORT.md` and record the final go/no-go decision in the report.

**Checkpoint**: Full experiment result exists and is ready for review.

---

## Phase 8: Optional Candidate Model (Only If Gates Pass)

**Purpose**: Create an inactive IPL v7 candidate only after the report recommends promotion.

Do not start this phase if the report says no promotion.

- [ ] T035 [US3] Train an inactive candidate model under `models/ipl_v7_mc_features_candidate/` using the winning MC feature variant and all eligible IPL training rows.
- [ ] T036 [US3] Save candidate selected-feature metadata proving MC fields are included.
- [ ] T037 [US3] Copy `experiments/ipl_mc_features_v1/REPORT.md` into the candidate model directory as `EXPERIMENT_REPORT.md`.
- [ ] T038 [US3] Add a recorded-state latency check comparing IPL v6 prediction latency versus candidate prediction with MC feature generation.
- [ ] T039 [US3] Keep `models/model_registry.json` unchanged unless a later production rollout task is explicitly requested.

**Checkpoint**: Candidate exists but is inactive and safe to discard.

---

## Dependencies and Execution Order

```text
Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5 -> Phase 6 -> Phase 7
                                                           |
                                                           v
                                              Phase 8 only if gates pass
```

Key dependencies:

- T009 depends on T003 because row reconstruction needs column knowledge.
- T015-T018 depend on T011 because fold-local calibration needs raw MC probabilities.
- T019-T026 depend on T017 because ML variants need calibrated MC features.
- T027-T030 depend on T024-T026 because gates need metrics and feature importance.
- T035-T039 must not run unless T034 says promotion gates passed.

---

## Parallel Opportunities

- T001, T002, T003, and T004 are mostly independent.
- T014 can be written while T009-T013 are being implemented.
- T024, T025, and T026 can be implemented in parallel after model variant predictions are available.
- T029 and T030 can be implemented in parallel after `REPORT.md` structure exists.

---

## MVP Scope

MVP is Phases 1-7:

- script
- pilot cache
- leak-free calibration
- required model variants
- metrics/report
- full run decision

Phase 8 is explicitly optional and should only happen if the experiment demonstrates a real metric improvement.

**Total tasks**: 39  
**Required MVP tasks**: 34  
**Optional candidate tasks**: 5
