# Tasks: ODI Win Probability Model

**Input**: Design documents from `/specs/007-odi-model/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in specification. Test tasks included only for T20 regression safety (critical gate).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the FormatConfig abstraction and T20 regression safety net before any ODI-specific work.

- [X] T001 Create FormatConfig frozen dataclass with all 20+ fields, validation, and `t20()` factory method in src/bbl_pipeline/features/format_config.py
- [X] T002 Extract all 31 T20-hardcoded constants from src/bbl_pipeline/features/calculator.py into FormatConfig.t20() factory method, ensuring exact value preservation
- [X] T003 Create T20 regression snapshot: run current calculator on 10 diverse match states (early PP, mid overs, death, 1st/2nd innings, various wickets) and save expected outputs to tests/unit/test_t20_regression_snapshots.json
- [X] T004 Create T20 regression test in tests/unit/test_t20_regression.py that loads snapshots and verifies calculator output is identical after refactoring

**Checkpoint**: FormatConfig exists with T20 preset. Regression safety net in place. No ODI code yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Refactor calculator and processor to accept FormatConfig. All existing T20 behavior preserved via defaults.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. T20 regression test MUST pass after every task.

- [X] T005 Add `config: FormatConfig = None` parameter to `ResourceFeatureCalculator.__init__()` in src/bbl_pipeline/features/calculator.py, defaulting to `FormatConfig.t20()` when None
- [X] T006 Replace all 31 hardcoded constants in src/bbl_pipeline/features/calculator.py with `self.config.<field>` references (TOTAL_OVERS, TOTAL_BALLS, PAR_SCORE_T20, phase boundaries, DLS_RESOURCE_TABLE, FIRST_INNINGS_WICKET_PENALTY_3D, WICKET_PENALTY_2D, RRR_MIDPOINT, SQI_BETA, etc.)
- [X] T007 Run T20 regression test from T004 — verify all 10 match states produce identical output after refactoring
- [X] T008 Add `format_config: FormatConfig = None` parameter to `process_bbl_data()` in src/bbl_pipeline/data/processor.py, defaulting to `FormatConfig.t20()` when None
- [X] T009 Replace 11 hardcoded T20 values in src/bbl_pipeline/data/processor.py with format_config references (120→total_balls, bins→phase_bins_balls, 160.0→par_score, phase booleans, /1200→total_balls*10)
- [X] T010 Add `format_type` field to league config dict in src/bbl_pipeline/cli.py (default `'t20'` for all existing leagues)
- [X] T011 Run T20 regression test again — verify existing T20 pipeline produces identical features and predictions after all refactoring

**Checkpoint**: Calculator and processor are fully parameterized. T20 regression passes. Ready for ODI work.

---

## Phase 3: User Story 1 — Empirical ODI Resource Analysis (Priority: P1) 🎯 MVP

**Goal**: Run empirical analysis on 3,085 ODI matches to derive gender-aware resource constants (par scores, DLS table, wicket penalties, run rates, chase parameters).

**Independent Test**: Run `python scripts/analyze_odi_empirical.py --input-dir odis_json --output scripts/odi_empirical_constants.json --cutoff-year 2010` and verify it produces a JSON file with separate male/female constants that differ meaningfully from T20 values.

### Implementation for User Story 1

- [X] T012 [US1] Create scripts/analyze_odi_empirical.py scaffold with CLI args (--input-dir, --output, --cutoff-year, --female-dir), JSON loading, 2010+ filtering, overs=50 filtering, and male/female separation
- [X] T013 [US1] Implement average scoring analysis: compute per-gender avg 1st innings score, avg 2nd innings score, bat-first win rate, and overall scoring distributions in scripts/analyze_odi_empirical.py
- [X] T014 [US1] Implement per-over run rate analysis: compute run rate by over number (1-50) per gender, identify phase transition points, output expected_run_rates per phase in scripts/analyze_odi_empirical.py
- [X] T015 [US1] Implement DLS resource table derivation: compute actual runs scored per (overs_remaining × wickets_lost) bucket, normalize to percentage of total innings potential, output 11×51 grid per gender in scripts/analyze_odi_empirical.py
- [X] T016 [US1] Implement first innings wicket penalty computation: compute projected-score ratios by phase × ease × wickets for 4-phase ODI structure, output FIRST_INNINGS_WICKET_PENALTY_3D per gender in scripts/analyze_odi_empirical.py
- [X] T017 [US1] Implement chase wicket penalty computation: compute chase_ease × wickets → win-rate-impact table, output WICKET_PENALTY_2D per gender in scripts/analyze_odi_empirical.py
- [X] T018 [US1] Implement RRR/chase parameter derivation: compute RRR midpoint (where chase win % ≈ 50%), RRR beta, chase ease thresholds per gender in scripts/analyze_odi_empirical.py
- [X] T019 [US1] Implement SQI/confidence parameters: compute SQI beta, SQI shift, confidence_full_overs, score_std_early, score_std_late per gender from score distributions in scripts/analyze_odi_empirical.py
- [X] T020 [US1] Add console report output: print formatted summary of all derived constants with sample counts and comparison to T20 values in scripts/analyze_odi_empirical.py
- [X] T021 [US1] Run the analysis script on odis_json/ data and review output — verify par scores (~250 male, ~195 female), bat-first win rates, and phase boundaries make sense for ODI cricket

**Checkpoint**: Empirical constants JSON exists with gender-specific ODI values. Ready to populate FormatConfig.odi().

---

## Phase 4: User Story 2 — ODI Resource Feature Calculator (Priority: P1)

**Goal**: Create FormatConfig.odi() presets populated with empirical constants, and verify the parameterized calculator produces sensible ODI predictions.

**Independent Test**: Feed sample ODI match states (e.g., 150/3 after 30 overs batting first; 200/4 after 40 overs chasing 280) into the calculator with ODI config and verify win probabilities, projected scores, and phases are sensible.

### Implementation for User Story 2

- [X] T022 [US2] Add `odi(gender='male')` factory method to FormatConfig in src/bbl_pipeline/features/format_config.py, populated with male empirical constants from scripts/odi_empirical_constants.json output
- [X] T023 [US2] Add `odi(gender='female')` factory method to FormatConfig in src/bbl_pipeline/features/format_config.py, populated with female empirical constants
- [X] T024 [P] [US2] Add `from_league(league)` factory method to FormatConfig in src/bbl_pipeline/features/format_config.py that resolves format from league config dict
- [X] T025 [P] [US2] Create tests/unit/test_format_config.py with validation tests: T20 invariants hold, ODI invariants hold (total_balls=300, phases sum to 50, par scores in range), gender variants differ
- [X] T026 [US2] Create tests/unit/test_odi_calculator.py with ODI-specific match state tests: 150/3 after 30 overs batting first → win_prob ~0.45-0.55; 200/4 after 40 overs chasing 280 → win_prob ~0.35-0.45; over 42 → phase="death"
- [X] T027 [US2] Verify calculator with ODI config handles edge cases: all-out before 50 overs (resources=0), first over (minimal confidence), last over (endgame logic with 300-ball scale), 0 wickets lost

**Checkpoint**: FormatConfig.odi() produces sensible constants. Calculator with ODI config passes all match-state tests.

---

## Phase 5: User Story 3 — Pipeline Compatibility for ODI League (Priority: P2)

**Goal**: Run `bbl-pipeline retrain --league odi --version v1` end-to-end, producing a trained model with calibrators.

**Independent Test**: Execute the full retrain command and verify `models/odi_v1/champion_model.joblib`, `oof_calibrators.pkl`, and `OOF_CALIBRATION_REPORT.md` all exist with Brier ≤ 0.22.

### Implementation for User Story 3

- [X] T028 [US3] Add `overs` field capture to `extract_match_metadata()` in src/bbl_pipeline/ingestion/processor.py — read from `info.overs` in Cricsheet JSON
- [X] T029 [US3] Add `'ODI'` to super-over detection match type whitelist in src/bbl_pipeline/ingestion/processor.py
- [X] T030 [US3] Add `odi` league config entry to LEAGUE_CONFIGS dict in src/bbl_pipeline/cli.py with json_dir='odis_json', raw_dir='data/odi_raw', features_dir='data/odi_features', feature_store_dir='data/odi_feature_store', model_prefix='odi', format_type='odi'
- [X] T031 [US3] Wire format_type resolution in the `retrain` command in src/bbl_pipeline/cli.py: detect format_type from league config, create appropriate FormatConfig, pass to process_bbl_data()
- [X] T032 [US3] Add date filtering (2010+) and overs filtering (exclude < 50) to ODI processing path in src/bbl_pipeline/data/processor.py or src/bbl_pipeline/cli.py
- [X] T033 [US3] Add `gender` column extraction from ingested data and include as binary training feature (0=male, 1=female) in src/bbl_pipeline/data/processor.py
- [X] T034 [US3] Add `is_setup` phase boolean column (overs 35-40) to feature engineering in src/bbl_pipeline/data/processor.py when format_type is ODI
- [X] T035 [US3] Add `gender` to TOP_FEATURES list in src/bbl_pipeline/training/trainer.py (conditionally, only when present in training data)
- [X] T036 [US3] Add `--format-type` CLI flag to the process command in src/bbl_pipeline/cli.py with choices=['t20', 'odi'], default='t20'
- [X] T037 [US3] Run `bbl-pipeline ingest --input-dir odis_json --output-dir data/odi_raw` and verify ODI parquet files are created with match_type=ODI and gender field
- [X] T038 [US3] Run `bbl-pipeline process` with ODI config and verify training.parquet has 50-over features, gender column, is_setup column, and ODI par-score-based features
- [X] T039 [US3] Run `bbl-pipeline retrain --league odi --version v1` end-to-end and verify champion_model.joblib, oof_calibrators.pkl, OOF_CALIBRATION_REPORT.md are produced
- [X] T040 [US3] Update models/model_registry.json with ODI model entry (version, Brier score, feature store, date, match count)

**Checkpoint**: Full ODI pipeline works end-to-end. Model trained and registered. Brier ≤ 0.22, ECE < 0.03.

---

## Phase 6: User Story 4 — Live ODI Match Prediction (Priority: P3)

**Goal**: Live predictor serves real-time ODI predictions using ODI model and 50-over resource calculations.

**Independent Test**: Point the Crex live predictor at an ODI match URL with `--league odi` and verify predictions update with correct phases (e.g., over 35 = "middle" not "death").

### Implementation for User Story 4

- [X] T041 [US4] Update src/bbl_pipeline/inference/crex_live_predictor.py to accept `--league` parameter and resolve FormatConfig for ODI matches (replace hardcoded 120/20 with config values)
- [X] T042 [US4] Update src/bbl_pipeline/inference/realtime_mapper.py to use total_overs/total_balls from FormatConfig instead of hardcoded 20/120
- [X] T043 [US4] Verify src/bbl_pipeline/inference/schema.py total_overs default works correctly when overridden by ODI config (already partially parameterized)
- [X] T044 [US4] Test live predictor with ODI model against a sample ODI match state — verify phases, projected scores, and win probabilities are ODI-appropriate

**Checkpoint**: Live ODI predictions work with correct 50-over calculations.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and validation across all stories.

- [X] T045 [P] Create docs/ODI_V1_MODEL.md documenting ODI model architecture, empirical constants, calibration results, and comparison to T20 models
- [X] T046 [P] Update .github/copilot-instructions.md with ODI model entry (league, Brier score, feature store details, sample counts)
- [X] T047 Run T20 regression test one final time — verify BBL v12, ILT20 v5, SA20 v2 predictions are completely unchanged
- [X] T048 Run quickstart.md validation — execute all steps from specs/007-odi-model/quickstart.md and verify they complete successfully
- [X] T049 Code cleanup: remove any debug prints, ensure type hints on all new functions, verify absolute imports throughout

**Checkpoint**: Documentation complete. T20 regression confirmed. ODI model ready for production.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001-T004) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — empirical analysis uses existing data, no code dependencies
- **US2 (Phase 4)**: Depends on US1 output (empirical constants JSON)
- **US3 (Phase 5)**: Depends on US2 (FormatConfig.odi() must exist for pipeline)
- **US4 (Phase 6)**: Depends on US3 (trained model must exist)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational) → US1 (Empirical Analysis)
                                              ↓
                                           US2 (ODI Calculator)
                                              ↓
                                           US3 (Pipeline Integration)
                                              ↓
                                           US4 (Live Prediction)
                                              ↓
                                           Phase 7 (Polish)
```

Note: Unlike typical projects, these user stories are **sequential** — each builds on the output of the previous one. US2 needs empirical constants from US1. US3 needs FormatConfig.odi() from US2. US4 needs a trained model from US3.

### Within Each User Story

- Models/configs before services
- Services before integration
- Core implementation before edge cases
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T001 and T003 can run in parallel (FormatConfig creation + snapshot generation)
- **Phase 2**: T008-T009 (processor refactoring) can run in parallel with T005-T006 (calculator refactoring) if different developers
- **US1**: T013-T019 analysis sub-tasks are mostly independent (different analysis functions)
- **US2**: T024, T025 can run in parallel (factory method + tests — different files)
- **US3**: T028-T029 (ingestion) can run in parallel with T030 (CLI config) — different files
- **Phase 7**: T045, T046 (docs) can run in parallel

---

## Parallel Example: User Story 1 (Empirical Analysis)

```
# These analysis functions can be implemented in parallel:
T013: Average scoring analysis (get_scoring_stats())
T014: Per-over run rate analysis (get_run_rates())  
T015: DLS resource table derivation (get_dls_table())
T016: First innings wicket penalties (get_batting_penalties())
T017: Chase wicket penalties (get_chase_penalties())
T018: RRR/chase parameters (get_chase_params())
T019: SQI/confidence parameters (get_confidence_params())

# Then combine into output:
T020: Console report + JSON output (uses all above)
T021: Run and review (depends on all above)
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup (FormatConfig + regression safety)
2. Complete Phase 2: Foundational (calculator + processor refactoring)
3. Complete Phase 3: US1 (empirical analysis → constants JSON)
4. Complete Phase 4: US2 (FormatConfig.odi() + calculator validation)
5. **STOP and VALIDATE**: ODI calculator produces sensible predictions

### Full Pipeline Delivery

6. Complete Phase 5: US3 (pipeline integration → trained model)
7. **STOP and VALIDATE**: Model trained, Brier ≤ 0.22, ECE < 0.03

### Live Production

8. Complete Phase 6: US4 (live prediction support)
9. Complete Phase 7: Polish (docs, final regression check)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- T20 regression test (T004/T007/T011/T047) is the critical safety gate — run it after every refactoring task
- Empirical constants from T021 feed directly into T022/T023 — review output before proceeding
- The `gender` feature is the key differentiator from T20 models — ensures male/female ODIs get appropriate resource calculations
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
