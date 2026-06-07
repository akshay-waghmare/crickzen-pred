# Tasks: IPL Regime-Aware State Embeddings

**Input**: `specs/016-ipl-state-embeddings/plan.md`, `specs/016-ipl-state-embeddings/spec.md`, `specs/016-ipl-state-embeddings/research.md`, `specs/016-ipl-state-embeddings/data-model.md`, `specs/016-ipl-state-embeddings/contracts/offline-pilot.openapi.yaml`  
**Feature Branch**: `016-ipl-state-embeddings`  
**Date**: 2026-05-26

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other tasks in the same phase because it touches different files or is read-only.
- **[Story]**: User story from `spec.md`.
- This task list is offline-pilot only. Do not modify `models/ipl_v6`, `models/model_registry.json`, live inference flows, vector infrastructure, or rollout paths in the main implementation path.

---

## Phase 1: Setup (Offline Pilot Scaffolding)

**Purpose**: Create the reusable module, CLI, tests, and artefact-path scaffolding for an IPL-only offline pilot.

- [X] T001 Create the state-embeddings module scaffold in `src/bbl_pipeline/analysis/state_embeddings/__init__.py`, `src/bbl_pipeline/analysis/state_embeddings/types.py`, `src/bbl_pipeline/analysis/state_embeddings/corpus.py`, `src/bbl_pipeline/analysis/state_embeddings/embeddings.py`, `src/bbl_pipeline/analysis/state_embeddings/retrieval.py`, and `src/bbl_pipeline/analysis/state_embeddings/evaluation.py`
- [X] T002 Create the offline experiment CLI skeleton with `--input`, `--raw-backfill-dir`, `--output-dir`, `--mode`, `--seed`, and `--resume` in `scripts/analyze_ipl_state_embeddings_experiment.py`
- [X] T003 [P] Create the test scaffolding in `tests/unit/analysis/state_embeddings/test_corpus.py`, `tests/unit/analysis/state_embeddings/test_retrieval.py`, `tests/unit/analysis/state_embeddings/test_evaluation.py`, and `tests/integration/test_ipl_state_embeddings_experiment.py`
- [X] T004 [P] Define artefact directory constants for `experiments/ipl_state_embeddings_v1/corpus/`, `experiments/ipl_state_embeddings_v1/models/`, `experiments/ipl_state_embeddings_v1/regimes/`, `experiments/ipl_state_embeddings_v1/retrieval/`, `experiments/ipl_state_embeddings_v1/features/`, and `experiments/ipl_state_embeddings_v1/evaluation/` in `scripts/analyze_ipl_state_embeddings_experiment.py`

**Checkpoint**: The repo has a dedicated offline-pilot skeleton without touching production IPL assets.

---

## Phase 2: Foundational (Shared Experiment Infrastructure)

**Purpose**: Add the shared types, metrics, split logic, and resumability used by every later story.

**⚠️ CRITICAL**: No user story work should be considered complete until this phase is in place.

- [X] T005 Create shared typed records and manifest/report schemas in `src/bbl_pipeline/analysis/state_embeddings/types.py`
- [X] T006 [P] Implement shared row-key helpers, innings/phase segmentation, Brier/log-loss/ECE helpers, and baseline-delta utilities in `src/bbl_pipeline/analysis/state_embeddings/evaluation.py`
- [X] T007 [P] Implement time-ordered fold and season-slice split helpers for `data/ipl_features_v6/training_sampled.parquet` and `data/ipl_features_v6/training.parquet` in `src/bbl_pipeline/analysis/state_embeddings/evaluation.py`
- [X] T008 Implement resume-safe stage orchestration and artefact-manifest loading in `scripts/analyze_ipl_state_embeddings_experiment.py`

**Checkpoint**: Shared experiment mechanics are ready, and story work can proceed with the same split/gate/reporting rules.

---

## Phase 3: User Story 1 - Build IPL Embedding Corpus (Priority: P1) 🎯 MVP

**Goal**: Build a reusable, leakage-safe IPL embedding corpus and short-window corpus from existing IPL training rows.

**Independent Test**: Run the corpus-build stage on `data/ipl_features_v6/training_sampled.parquet` and verify `experiments/ipl_state_embeddings_v1/corpus/embedding_corpus.parquet`, `window_corpus.parquet`, and `corpus_manifest.json` are created with stable row keys and exclusion counts.

### Tests for User Story 1

- [X] T009 [P] [US1] Add unit tests for row-key construction, exclusion reasons, and window completeness in `tests/unit/analysis/state_embeddings/test_corpus.py`
- [X] T010 [US1] Add corpus-build integration assertions for `experiments/ipl_state_embeddings_v1/corpus/embedding_corpus.parquet` and `experiments/ipl_state_embeddings_v1/corpus/corpus_manifest.json` in `tests/integration/test_ipl_state_embeddings_experiment.py`

### Implementation for User Story 1

- [X] T011 [US1] Implement IPL v6 input loading and required-column validation for `data/ipl_features_v6/training_sampled.parquet` and `data/ipl_features_v6/training.parquet` in `src/bbl_pipeline/analysis/state_embeddings/corpus.py`
- [X] T012 [US1] Implement leakage-safe ordering, stable `match_id:innings:over:ball` row keys, and eligibility/exclusion handling in `src/bbl_pipeline/analysis/state_embeddings/corpus.py`
- [X] T013 [US1] Implement missing-context backfill from `data/ipl_raw/matches/*.parquet` with fallback lookup into `ipl_male_json/*.json` in `src/bbl_pipeline/analysis/state_embeddings/corpus.py`
- [X] T014 [US1] Implement up-to-6-ball state-window aggregation and traceable `source_row_keys` in `src/bbl_pipeline/analysis/state_embeddings/corpus.py`
- [X] T015 [US1] Write `experiments/ipl_state_embeddings_v1/corpus/embedding_corpus.parquet`, `experiments/ipl_state_embeddings_v1/corpus/window_corpus.parquet`, and `corpus_manifest.json` from `src/bbl_pipeline/analysis/state_embeddings/corpus.py`
- [X] T016 [US1] Wire the corpus-build stage and pilot-mode defaults into `scripts/analyze_ipl_state_embeddings_experiment.py`

**Checkpoint**: The offline IPL corpus exists and is reusable for regimes, retrieval, and downstream evaluation.

---

## Phase 4: User Story 2 - Discover and Evaluate Regimes Offline (Priority: P1)

**Goal**: Fit simple embeddings and cluster-based regimes offline, then evaluate whether those regimes are stable and meaningful.

**Independent Test**: Run the regime-discovery stage on the sampled corpus and verify `experiments/ipl_state_embeddings_v1/regimes/regime_assignments.parquet` and `regime_summary.csv` report coverage, separation, and stability.

### Tests for User Story 2

- [X] T017 [P] [US2] Add unit tests for PCA fit/transform invariants, cluster assignment coverage, and regime-summary gates in `tests/unit/analysis/state_embeddings/test_evaluation.py`

### Implementation for User Story 2

- [X] T018 [US2] Implement train-only numeric feature selection, `StandardScaler` fitting, PCA fitting, and explained-variance exports in `src/bbl_pipeline/analysis/state_embeddings/embeddings.py`
- [X] T019 [US2] Implement train-only `KMeans` regime fitting, validation-row assignment, and persisted `experiments/ipl_state_embeddings_v1/models/scaler.joblib`, `pca.joblib`, and `kmeans.joblib` in `src/bbl_pipeline/analysis/state_embeddings/embeddings.py`
- [X] T020 [US2] Implement regime summaries for coverage, cluster size, centroid separation, stability, and outcome separation in `src/bbl_pipeline/analysis/state_embeddings/evaluation.py`
- [X] T021 [US2] Derive evidence-based regime labels and write `experiments/ipl_state_embeddings_v1/regimes/regime_assignments.parquet` and `experiments/ipl_state_embeddings_v1/regimes/regime_summary.csv` in `src/bbl_pipeline/analysis/state_embeddings/evaluation.py`
- [X] T022 [US2] Wire the regime-discovery stage into `scripts/analyze_ipl_state_embeddings_experiment.py` using sampled pilot defaults before full `data/ipl_features_v6/training.parquet`

**Checkpoint**: The pilot can produce train-only embeddings, regime assignments, and interpretable regime summaries.

---

## Phase 5: User Story 3 - Retrieve Historical Analogues (Priority: P1)

**Goal**: Retrieve historical IPL analogues from the embedding space without self-match or future leakage.

**Independent Test**: Run held-out queries through the retrieval stage and verify `experiments/ipl_state_embeddings_v1/retrieval/analogue_results.parquet` and `retrieval_summary.json` contain ranked neighbours, context fields, and coverage statistics.

### Tests for User Story 3

- [X] T023 [P] [US3] Add unit tests for self-match exclusion, same-match future-row filtering, and neighbour ranking in `tests/unit/analysis/state_embeddings/test_retrieval.py`

### Implementation for User Story 3

- [X] T024 [US3] Implement exact `NearestNeighbors` fit/query on train embeddings and persisted `experiments/ipl_state_embeddings_v1/models/neighbors.joblib` in `src/bbl_pipeline/analysis/state_embeddings/retrieval.py`
- [X] T025 [US3] Implement leakage guards for duplicate event keys, same-row matches, and future-labelled same-match rows in `src/bbl_pipeline/analysis/state_embeddings/retrieval.py`
- [X] T026 [US3] Implement analogue result enrichment with source context, neighbour outcome summaries, and regime summaries in `src/bbl_pipeline/analysis/state_embeddings/retrieval.py`
- [X] T027 [US3] Write `experiments/ipl_state_embeddings_v1/retrieval/analogue_results.parquet` and `experiments/ipl_state_embeddings_v1/retrieval/retrieval_summary.json` in `src/bbl_pipeline/analysis/state_embeddings/retrieval.py`
- [X] T028 [US3] Wire held-out analogue retrieval into `scripts/analyze_ipl_state_embeddings_experiment.py` so pilot queries use only earlier train-fold rows from `experiments/ipl_state_embeddings_v1/corpus/embedding_corpus.parquet`

**Checkpoint**: The pilot can retrieve valid historical analogues with leakage filtering and measurable coverage.

---

## Phase 6: User Story 4 - Test Regime-Aware Probability Impact vs Current IPL Baseline (Priority: P1)

**Goal**: Generate regime-aware numeric features and decide offline whether they beat the current IPL baseline on both Brier and log loss without unacceptable calibration regressions.

**Independent Test**: Run the full sampled pilot and verify `experiments/ipl_state_embeddings_v1/evaluation/metrics.csv`, `segment_metrics.csv`, `reliability_bins.csv`, and `PILOT_REPORT.md` compare baseline and candidate variants with baseline deltas and an explicit GO/NO-GO verdict.

### Tests for User Story 4

- [X] T029 [US4] Extend sampled end-to-end assertions for `experiments/ipl_state_embeddings_v1/evaluation/metrics.csv`, `experiments/ipl_state_embeddings_v1/evaluation/segment_metrics.csv`, `experiments/ipl_state_embeddings_v1/evaluation/reliability_bins.csv`, and `experiments/ipl_state_embeddings_v1/evaluation/PILOT_REPORT.md` in `tests/integration/test_ipl_state_embeddings_experiment.py`

### Implementation for User Story 4

- [X] T030 [US4] Implement regime-aware feature joins for `neighbor_win_rate_k`, `neighbor_outcome_std_k`, `neighbor_mean_resource_prob_k`, `neighbor_distance_mean_k`, `regime_id`, `regime_confidence`, `regime_cluster_win_rate`, and `regime_cluster_size` in `src/bbl_pipeline/analysis/state_embeddings/evaluation.py`
- [X] T031 [US4] Write `experiments/ipl_state_embeddings_v1/features/regime_features.parquet` and build `baseline_ipl_v6_features`, `regime_retrieval_features`, `regime_cluster_features`, and `regime_hybrid_features` frames in `scripts/analyze_ipl_state_embeddings_experiment.py`
- [X] T032 [US4] Implement time-ordered baseline-vs-candidate training and evaluation in `scripts/analyze_ipl_state_embeddings_experiment.py` by reusing `scripts/analyze_ipl_mc_features_experiment.py` split, metric, and reporting patterns
- [X] T033 [US4] Implement overall baseline deltas for Brier, log loss, and ECE in `experiments/ipl_state_embeddings_v1/evaluation/metrics.csv` from `src/bbl_pipeline/analysis/state_embeddings/evaluation.py`
- [X] T034 [US4] Implement segmented innings and innings-by-phase evaluation plus reliability bins in `experiments/ipl_state_embeddings_v1/evaluation/segment_metrics.csv` and `experiments/ipl_state_embeddings_v1/evaluation/reliability_bins.csv` from `src/bbl_pipeline/analysis/state_embeddings/evaluation.py`
- [X] T035 [US4] Implement the go/no-go gate in `src/bbl_pipeline/analysis/state_embeddings/evaluation.py` requiring a regime-aware variant to beat `baseline_ipl_v6_features` on both Brier and log loss while not materially worsening ECE or key segments
- [X] T036 [US4] Generate `experiments/ipl_state_embeddings_v1/evaluation/PILOT_REPORT.md` in `scripts/analyze_ipl_state_embeddings_experiment.py` with corpus coverage, retrieval coverage, regime quality, baseline deltas, segmented regressions, and explicit GO/NO-GO plus no-production-change guidance when gates fail

**Checkpoint**: The sampled pilot produces a decision-ready offline report grounded in baseline deltas and segmented calibration checks.

---

## Phase 7: Polish & Cross-Cutting Validation

**Purpose**: Validate the full offline path, refresh operator guidance, and stop at a decision-ready pilot.

- [X] T037 Run `python -m pytest tests/unit/analysis/state_embeddings/test_corpus.py tests/unit/analysis/state_embeddings/test_retrieval.py tests/unit/analysis/state_embeddings/test_evaluation.py tests/integration/test_ipl_state_embeddings_experiment.py -q`
- [X] T038 Run `python scripts/analyze_ipl_state_embeddings_experiment.py --input data/ipl_features_v6/training_sampled.parquet --raw-backfill-dir data/ipl_raw/matches --output-dir experiments/ipl_state_embeddings_v1 --mode pilot --seed 42 --resume` and review `experiments/ipl_state_embeddings_v1/evaluation/PILOT_REPORT.md`
- [X] T039 Run `python scripts/analyze_ipl_state_embeddings_experiment.py --input data/ipl_features_v6/training.parquet --raw-backfill-dir data/ipl_raw/matches --output-dir experiments/ipl_state_embeddings_v1 --mode full --seed 42 --resume` and confirm `experiments/ipl_state_embeddings_v1/evaluation/metrics.csv` and `experiments/ipl_state_embeddings_v1/evaluation/segment_metrics.csv` still support the final verdict
- [X] T040 Update the offline-pilot command and artefact expectations in `specs/016-ipl-state-embeddings/quickstart.md`, keeping V1 explicitly limited to offline evaluation only

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 → Phase 2**: Setup first, then shared experiment infrastructure.
- **Phase 3 (US1)**: Starts after Phase 2 and produces the corpus required by every later story.
- **Phase 4 (US2)** and **Phase 5 (US3)**: Both depend on US1 and can proceed in parallel once the corpus exists.
- **Phase 6 (US4)**: Depends on US2 and US3 because feature generation and evaluation need both regime outputs and analogue outputs.
- **Phase 7**: Depends on all required story work being complete.

### User Story Dependencies

- **US1**: No dependency on other user stories; this is the first practical MVP checkpoint.
- **US2**: Depends on US1 corpus outputs.
- **US3**: Depends on US1 corpus outputs.
- **US4**: Depends on both US2 regime outputs and US3 retrieval outputs.

### Within Each User Story

- Tests must be written before or alongside implementation and should fail before the story is considered complete.
- Corpus/window creation must finish before embedding, clustering, or retrieval.
- Train-only fitting must finish before held-out retrieval or baseline comparison.
- Baseline metrics and segmented deltas must exist before the go/no-go report is generated.

---

## Parallel Opportunities

- **Setup**: T003 and T004 can run in parallel after T001-T002 scaffolding starts.
- **Foundational**: T006 and T007 can run in parallel because they both extend `src/bbl_pipeline/analysis/state_embeddings/evaluation.py` but cover independent helper groups only if work is carefully batched; otherwise do them sequentially in one change.
- **US1**: T009 can run while T011-T012 are being implemented; after the loader exists, T013 and T014 can proceed as separate slices in `src/bbl_pipeline/analysis/state_embeddings/corpus.py`.
- **US2**: After T018 is in place, T019 and T020 can be split between embedding persistence and regime-summary logic.
- **US3**: After T024 lands, T025 and T026 can proceed in parallel across leakage filtering and result enrichment.
- **US4**: After T031-T032 produce predictions, T033 and T034 can proceed in parallel for overall and segmented reporting.

---

## Parallel Example: User Story 1

```text
Task: "T013 Implement missing-context backfill from data/ipl_raw/matches/*.parquet with fallback lookup into ipl_male_json/*.json in src/bbl_pipeline/analysis/state_embeddings/corpus.py"
Task: "T014 Implement up-to-6-ball state-window aggregation and traceable source_row_keys in src/bbl_pipeline/analysis/state_embeddings/corpus.py"
```

## Parallel Example: User Story 2

```text
Task: "T019 Implement train-only KMeans regime fitting and persisted models in src/bbl_pipeline/analysis/state_embeddings/embeddings.py"
Task: "T020 Implement regime summaries for coverage, cluster size, centroid separation, stability, and outcome separation in src/bbl_pipeline/analysis/state_embeddings/evaluation.py"
```

## Parallel Example: User Story 3

```text
Task: "T025 Implement leakage guards for duplicate event keys, same-row matches, and future-labelled same-match rows in src/bbl_pipeline/analysis/state_embeddings/retrieval.py"
Task: "T026 Implement analogue result enrichment with source context, neighbour outcome summaries, and regime summaries in src/bbl_pipeline/analysis/state_embeddings/retrieval.py"
```

## Parallel Example: User Story 4

```text
Task: "T033 Implement overall baseline deltas for Brier, log loss, and ECE in experiments/ipl_state_embeddings_v1/evaluation/metrics.csv from src/bbl_pipeline/analysis/state_embeddings/evaluation.py"
Task: "T034 Implement segmented innings and innings-by-phase evaluation plus reliability bins in experiments/ipl_state_embeddings_v1/evaluation/segment_metrics.csv and experiments/ipl_state_embeddings_v1/evaluation/reliability_bins.csv from src/bbl_pipeline/analysis/state_embeddings/evaluation.py"
```

---

## Implementation Strategy

### MVP First

1. Complete **Phase 1: Setup**.
2. Complete **Phase 2: Foundational**.
3. Complete **Phase 3: US1** and validate the offline corpus on `data/ipl_features_v6/training_sampled.parquet`.
4. Treat that corpus checkpoint as the first MVP milestone before adding clustering, retrieval, and evaluation.

### Decision-Ready Pilot Delivery

1. Add **US2** regime discovery on the sampled corpus.
2. Add **US3** analogue retrieval on the sampled corpus.
3. Add **US4** regime-aware feature generation and baseline comparison on the sampled corpus.
4. Validate the sampled pilot end-to-end before running the full `data/ipl_features_v6/training.parquet` flow.
5. Stop at the offline go/no-go report; do not add production rollout work unless a later follow-up is explicitly requested.

### Suggested Scope

- **First implementation focus**: sampled offline IPL pilot only.
- **Full decision scope**: sampled pilot first, then full offline comparison.
- **Out of main path**: production promotion, vector DB, ANN infra, dashboard/live rollout, or SLM/LLM layers.

---

## Notes

- Every story is repository-aligned around existing IPL v6 parquet inputs, raw IPL match backfill sources, scikit-learn primitives, and the current evaluation/reporting pattern in `scripts/analyze_ipl_mc_features_experiment.py`.
- Baseline comparison must explicitly include overall deltas for Brier, log loss, and ECE, plus segmented innings and innings-phase evaluation.
- The report is **NO-GO** unless a regime-aware variant beats the baseline on **both** Brier and log loss and avoids material calibration/segment regression.
