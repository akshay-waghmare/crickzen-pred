# Tasks: ODI Monte Carlo Standalone Predictor

**Input**: Design documents from `/specs/009-odi-mc-predictor/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify existing dependencies and confirm baseline before modifications

- [x] T001 Verify existing simulation tests pass via `pytest tests/test_simulation.py -v`
- [x] T002 [P] Verify FormatConfig.odi() returns correct constants (par=257.7, total_balls=300, 4 phases) in src/bbl_pipeline/features/format_config.py

---

## Phase 2: Foundational — MatchState & Phase System (Blocking Prerequisites)

**Purpose**: Unblock ODI simulation by fixing the hard blockers: MatchState validation, phase system, and evaluator format detection. These MUST be done before any user story work.

**⚠️ CRITICAL**: No ODI MC work can begin until `MatchState(total_balls=300)` works and `get_phase()` returns correct ODI phases.

- [x] T003 [US4] Extend MatchState total_balls validation from 6-120 to 6-300 in src/bbl_pipeline/simulation/state.py (FR-001)
- [x] T004 [P] [US2] Add ODI_PHASES tuple ("powerplay", "middle", "setup", "death") and get_odi_phase_boundaries() to src/bbl_pipeline/simulation/config.py (FR-009)
- [x] T005 [US2] Update get_phase() to detect ODI format (total_balls > 120) and return 4-phase ODI boundaries (PP:1-10, Mid:11-34, Setup:35-40, Death:41-50) in src/bbl_pipeline/simulation/config.py (FR-009)
- [x] T006 [US3] Add format detection in TerminalStateEvaluator._get_calculator(): total_balls > 120 → FormatConfig.odi() in src/bbl_pipeline/simulation/evaluator.py (FR-005)
- [x] T007 Write unit tests for MatchState(300), get_phase(ODI), and evaluator ODI detection in tests/unit/test_odi_mc.py

**Checkpoint**: `MatchState(total_balls=300)` creates without error; `get_phase(balls_remaining=240, total_balls=300)` returns "powerplay"; evaluator returns FormatConfig.odi() for 300-ball innings.

---

## Phase 3: User Story 4 & 2 — ODI Simulation Core (Priority: P1) 🎯 MVP

**Goal**: Make the MC engine simulate ODI matches end-to-end with correct 4-phase ball sampling.

**Independent Test**: Simulate 1,000 ODI innings from 0/0 (300 balls) and verify completion without crash; average total should be roughly ~200-300 with default distributions.

### Implementation

- [x] T008 [US2] Update NextBallSampler to iterate over dynamic phases from loaded distribution keys instead of hardcoded ("powerplay", "middle", "death") in src/bbl_pipeline/simulation/sampler.py line 174 (FR-002, FR-003)
- [x] T009 [US2] Add ODI distribution loading: detect ODI league names ("odi", "odm", "odm_male", "odm_female") and load phase_distributions_odi.json when available in src/bbl_pipeline/simulation/sampler.py (FR-003)
- [x] T010 [US2] Add default ODI run distributions (ODI_RUN_DIST) and wicket probabilities (ODI_WICKET_PROB) as embedded fallback constants in src/bbl_pipeline/simulation/config.py (FR-004)
- [x] T011 [US2] Add ODI wicket multiplier table (10 entries, wickets 0-9) as ODI_WICKET_MULTIPLIER constant in src/bbl_pipeline/simulation/config.py (FR-010)
- [x] T012 [US4] Write unit tests for MatchState ODI operations: apply_outcome() across 300 balls, innings completion at 0 balls and 10 wickets, overs_completed property in tests/unit/test_odi_mc.py
- [x] T013 [US2] Write unit tests for NextBallSampler with 4-phase ODI distributions and dynamic phase iteration in tests/unit/test_odi_mc.py
- [x] T014 [US2] Run 100K MC simulations of ODI innings from 0/0 and validate average total is ~250-260 with default distributions (SC-002)

**Checkpoint**: Full ODI innings simulation works end-to-end. `simulate(MatchState(total_balls=300, ...))` completes successfully and produces realistic ODI totals.

---

## Phase 4: User Story 5 — Empirical ODI Phase Distribution Extraction (Priority: P2)

**Goal**: Extract real ODI scoring patterns from 3,085 Cricsheet JSON files to replace placeholder distributions.

**Independent Test**: Run extraction script and verify output JSON has 4 phases with run probabilities summing to 1.0 and wicket rates matching published ODI statistics.

### Implementation

- [x] T015 [US5] Create extract_odi_phase_distributions.py script with CLI args (--input-dir, --output, --gender, --min-year, --verbose) in scripts/extract_odi_phase_distributions.py (FR-008)
- [x] T016 [US5] Implement Cricsheet ODI JSON parser: read ball-by-ball data, extract runs (batter+extras), detect wickets per delivery in scripts/extract_odi_phase_distributions.py
- [x] T017 [US5] Implement ODI phase assignment logic: map each ball to powerplay/middle/setup/death based on over number (1-10/11-34/35-40/41-50) in scripts/extract_odi_phase_distributions.py
- [x] T018 [US5] Compute per-phase run probability vectors (0/1/2/3/4/5/6) and wicket rates; compute wicket multiplier table by wickets-down in scripts/extract_odi_phase_distributions.py
- [x] T019 [US5] Add gender filtering (--gender male|female) and year filtering (--min-year) to extraction script in scripts/extract_odi_phase_distributions.py (FR-012)
- [x] T020 [US5] Output phase_distributions_odi.json matching schema from data-model.md (include metadata: format, gender, total_matches, total_balls, extraction_date) in scripts/extract_odi_phase_distributions.py
- [x] T021 [US5] Run extraction: `python scripts/extract_odi_phase_distributions.py --input-dir odis_json --output data/phase_distributions_odi.json --gender male --min-year 2010`
- [x] T022 [US5] Validate extracted distributions: run 100K MC simulations with empirical distributions and verify average total is 257.7 ± 10 runs (SC-002)
- [x] T023 [US5] Update embedded ODI_RUN_DIST and ODI_WICKET_PROB constants in src/bbl_pipeline/simulation/config.py with empirically-derived values from extraction

**Checkpoint**: `phase_distributions_odi.json` generated with accurate 4-phase distributions. MC simulations using empirical data reproduce realistic ODI averages.

---

## Phase 5: User Story 1 — MC-Only Live Prediction for ODI (Priority: P1)

**Goal**: Run `crex_live_predictor.py --mc-only` for any ODI match without requiring model-dir or feature store.

**Independent Test**: `python -m src.bbl_pipeline.inference.crex_live_predictor --mc-only --match-url <ODI_URL>` produces win probabilities in 5-95% range.

### Implementation

- [x] T024 [US1] Make --model-dir argument optional when --mc-only is set in src/bbl_pipeline/inference/crex_live_predictor.py (FR-006)
- [x] T025 [US1] Add ODI format detection from total_overs (>= 40 → ODI) in crex_live_predictor._run_reduced_over_prediction() and _run_prediction() in src/bbl_pipeline/inference/crex_live_predictor.py
- [x] T026 [US1] Pass FormatConfig.odi() through MC pipeline when ODI detected; load ODI phase distributions from model-dir or embedded defaults in src/bbl_pipeline/inference/crex_live_predictor.py
- [x] T027 [US1] Update MC-only JSON output to include format, phase, and simulation metadata per contracts/contracts.md output schema in src/bbl_pipeline/inference/crex_live_predictor.py
- [x] T028 [US1] Ensure --record-states works in MC-only ODI mode: all ball states recorded with calibration chain values to parquet in src/bbl_pipeline/inference/crex_live_predictor.py (FR-011)
- [x] T029 [US1] Write integration test simulating a full ODI match prediction flow (first and second innings) without model-dir in tests/integration/test_odi_predictor.py (SC-001)

**Checkpoint**: MC-only ODI predictor runs against live CREX ODI matches, produces 5-95% probabilities, no crashes (SC-005).

---

## Phase 6: User Story 3 — Enriched Resource Calculator & MC Calibration (Priority: P2)

**Goal**: Improve MC accuracy with ODI-calibrated resource evaluation and trained calibrators.

**Independent Test**: Evaluate resource_win_prob for known ODI scenarios (chasing 280 at 150/2 after 30 overs → ~65-75%) and verify calibrated Brier ≤ 0.185.

### Implementation

- [x] T030 [US3] Update over_to_phase() with total_overs parameter for ODI phase boundaries (PP:0-9, Mid:10-33, Setup:34-39, Death:40-49) in src/bbl_pipeline/calibration/mc_calibrator.py
- [x] T031 [US3] Support 4-phase InningsPhaseCalibrators (8 calibrators: 2 innings × 4 phases) in src/bbl_pipeline/calibration/mc_calibrator.py
- [x] T032 [US3] Write unit tests for over_to_phase() with ODI boundaries and InningsPhaseCalibrators with 4 phases in tests/unit/test_odi_mc.py
- [x] T033 [US3] Create train_odi_mc_calibrator.py script: run MC on historical ODI matches, fit Platt/isotonic calibrators via OOF cross-validation in scripts/train_odi_mc_calibrator.py (FR-007)
- [x] T034 [US3] Integrate MC calibrator loading in crex_live_predictor: load mc_calibrator.pkl from model-dir when available, graceful fallback when not in src/bbl_pipeline/inference/crex_live_predictor.py
- [x] T035 [US3] Write resource_win_prob validation tests for known ODI scenarios per spec acceptance criteria in tests/unit/test_odi_mc.py

**Checkpoint**: Calibrated MC Brier ≤ 0.185 on held-out ODI matches (SC-003). Resource evaluator returns sensible probabilities for typical ODI match states.

---

## Phase 7: User Story 6 — State-of-the-Art MC Enrichments (Priority: P3)

**Goal**: Advanced simulation features for improved prediction accuracy.

**Independent Test**: Compare enriched vs base MC predictions on 100+ completed ODI matches; each enrichment demonstrates ≥0.5% Brier reduction.

### Implementation

- [x] T036 [P] [US6] Implement partnership momentum factor: increase boundary probability for established partnerships (100+ runs) in src/bbl_pipeline/simulation/sampler.py
- [x] T037 [P] [US6] Implement new batsman factor: elevate dot ball probability for first 10 balls faced in src/bbl_pipeline/simulation/sampler.py
- [x] T038 [P] [US6] Implement pitch deterioration factor: wicket probability modifier based on innings progression in src/bbl_pipeline/simulation/sampler.py
- [x] T039 [US6] Write unit tests for each enrichment factor (partnership, new batsman, pitch) in tests/unit/test_odi_mc.py
- [x] T040 [US6] Backtest enriched MC vs base MC on 100+ completed ODI matches and measure Brier improvement (SC-006) in scripts/backtest_enriched_mc.py

**Checkpoint**: Each enrichment demonstrates ≥0.5% Brier reduction vs base MC (SC-006).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and validation across all stories

- [x] T041 [P] Update model_registry.json with ODI MC artifacts (phase distributions, calibrators)
- [x] T042 [P] Add ODI MC predictor documentation in docs/ODI_MC_PREDICTOR.md
- [x] T043 Run full test suite: `pytest tests/ -v` to verify no T20 regressions
- [x] T044 Run quickstart.md validation: execute all verification steps from specs/009-odi-mc-predictor/quickstart.md
- [x] T045 Performance validation: verify MC-only ODI latency < 500ms per ball with 5,000 simulations (SC-004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — verify baseline
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all user stories**
- **Phase 3 (US4+US2 Core)**: Depends on Phase 2 — ODI simulation engine
- **Phase 4 (US5 Distributions)**: Depends on Phase 3 — needs working sampler to validate
- **Phase 5 (US1 Live Predictor)**: Depends on Phase 3, optionally Phase 4 (can use default distributions)
- **Phase 6 (US3 Calibration)**: Depends on Phase 3, Phase 4 preferred (empirical distributions)
- **Phase 7 (US6 Enrichments)**: Depends on Phase 3, Phase 4, Phase 6
- **Phase 8 (Polish)**: Depends on all desired phases being complete

### User Story Dependencies

```
US4 (MatchState 300) ─┐
                       ├──► US2 (4-Phase Sampler) ──► US5 (Empirical Distributions)
US2 (Phase System)  ───┘         │                          │
                                 ├──► US1 (Live Predictor) ◄┘
US3 (Evaluator ODI) ────────────►│
                                 └──► US3 (MC Calibration) ──► US6 (Enrichments)
```

### Within Each User Story

- Foundational components (state, config) before sampler/evaluator
- Sampler/evaluator before live predictor integration
- Core implementation before writing integration tests
- Unit tests alongside or immediately after implementation

### Parallel Opportunities

**Phase 2** (after Phase 1):
- T003 (MatchState) and T004 (ODI_PHASES) can run in parallel (different files)

**Phase 3** (after Phase 2):
- T008 (sampler) and T010+T011 (config constants) can run in parallel (different files)
- T012 and T013 (tests) can run in parallel

**Phase 4**:
- T015–T020 are sequential within the extraction script (single file)

**Phase 5** (after Phase 3):
- T024–T028 are sequential (all in crex_live_predictor.py)

**Phase 7**:
- T036, T037, T038 can all run in parallel (independent enrichment features in sampler.py)

---

## Parallel Example: Phase 2 (Foundational)

```bash
# These can run in parallel (different files):
T003: "Extend MatchState total_balls to 300 in simulation/state.py"
T004: "Add ODI_PHASES and get_odi_phase_boundaries() in simulation/config.py"

# Then sequentially:
T005: "Update get_phase() for ODI detection in simulation/config.py" (depends on T004)
T006: "Add ODI format detection in evaluator.py" (depends on T003)
T007: "Write unit tests for all foundational changes" (depends on T003-T006)
```

## Parallel Example: Phase 7 (Enrichments)

```bash
# All three enrichments can run in parallel (independent features):
T036: "Partnership momentum factor"
T037: "New batsman factor"
T038: "Pitch deterioration factor"

# Then sequentially:
T039: "Unit tests for all enrichments" (depends on T036-T038)
T040: "Backtest enriched vs base MC" (depends on T036-T039)
```

---

## Implementation Strategy

### MVP First (Phases 1-3 + Phase 5)

1. Complete Phase 1: Setup verification
2. Complete Phase 2: Foundational (MatchState + phases + evaluator) — **CRITICAL**
3. Complete Phase 3: ODI simulation core (sampler + defaults)
4. Complete Phase 5: MC-only live predictor integration
5. **STOP and VALIDATE**: Run `--mc-only` against a live ODI match
6. Deploy/use immediately with default distributions

### Incremental Delivery

1. **MVP** (Phases 1-3, 5): Working MC-only ODI predictor with default distributions → 8 hours
2. **+ Empirical Distributions** (Phase 4): Replace defaults with real data → +2.5 hours
3. **+ Calibration** (Phase 6): Platt/isotonic calibrators for Brier improvement → +2.5 hours
4. **+ Enrichments** (Phase 7): Partnership, new batsman, pitch factors → +4 hours
5. **Polish** (Phase 8): Docs, registry, validation → +1.5 hours

Each phase adds value without breaking previous phases.

---

## Notes

- T20 simulation must not regress — T007 and T043 verify existing behavior
- FormatConfig.odi() already exists and has all ODI constants — no changes needed in format_config.py
- Default distributions (T010) are placeholder estimates; Phase 4 replaces them with empirical data
- Phases 5 and 4 can be swapped: predictor works with defaults first, empirical data improves accuracy later
- Total: 45 tasks across 8 phases (~14.5 hours estimated effort)
