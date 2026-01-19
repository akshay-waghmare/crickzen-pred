# Tasks: Monte Carlo Simulation Engine

**Input**: Design documents from `/specs/004-monte-carlo-engine/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Unit tests included for core components (pytest).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create simulation package structure and configuration

- [X] T001 Create simulation package structure: `src/bbl_pipeline/simulation/__init__.py`
- [X] T002 [P] Create phase tables config in `src/bbl_pipeline/simulation/config.py` with RUN_DIST, WICKET_PROB, WICKET_MULTIPLIER from research.md
- [X] T003 [P] Create MatchState dataclass in `src/bbl_pipeline/simulation/state.py` per data-model.md schema

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Implement NextBallSampler class in `src/bbl_pipeline/simulation/sampler.py` with phase-based run/wicket distributions
- [X] T005 [P] Implement `get_phase(balls_remaining)` helper in `src/bbl_pipeline/simulation/config.py` (powerplay/middle/death)
- [X] T006 [P] Implement cumulative distribution arrays for `np.searchsorted()` sampling in `src/bbl_pipeline/simulation/sampler.py`
- [X] T007 Implement terminal state evaluator wrapper in `src/bbl_pipeline/simulation/evaluator.py` that calls `ResourceFeatureCalculator.calculate_all_features()`
- [X] T008 [P] Implement `apply_temperature(prob, temperature)` function in `src/bbl_pipeline/simulation/evaluator.py`
- [X] T009 [P] Create unit test for MatchState validation in `tests/test_simulation.py` (combined test file)
- [X] T010 [P] Create unit test for NextBallSampler distributions in `tests/test_simulation.py` (combined test file)

**Checkpoint**: Foundation ready - sampler and evaluator tested, user story implementation can begin

---

## Phase 3: User Story 1 - Single Ball Simulation (Priority: P1) 🎯 MVP

**Goal**: Simulate next ball's win probability distribution for timing/hedging decisions

**Independent Test**: `simulate(state, horizon_balls=1, n_sims=2000)` returns mean ± std within 200ms

### Implementation for User Story 1

- [X] T011 [US1] Implement SimulationResult dataclass in `src/bbl_pipeline/simulation/state.py` with mean_prob, std_prob, p5, p95, time_taken_ms
- [X] T012 [US1] Implement `simulate_single_ball()` core loop in `src/bbl_pipeline/simulation/engine.py` (non-vectorized first)
- [X] T013 [US1] Implement state transition logic (score, wickets, balls_remaining update) in `src/bbl_pipeline/simulation/engine.py`
- [X] T014 [US1] Handle innings termination conditions (all out, balls=0, target chased) in `src/bbl_pipeline/simulation/engine.py`
- [X] T015 [US1] Add timing measurement and return SimulationResult in `src/bbl_pipeline/simulation/engine.py`
- [X] T016 [P] [US1] Create unit test for 1-ball simulation in `tests/test_simulation.py`
- [X] T017 [US1] Verify 1-ball simulation completes in <300ms (naive) in `scripts/benchmark_simulation.py` (~50ms actual)

**Checkpoint**: User Story 1 complete - single ball simulation works with timing < 300ms

---

## Phase 4: User Story 2 - Six Ball Simulation (Priority: P1)

**Goal**: Simulate next over's win probability distribution for betting decisions

**Independent Test**: `simulate(state, horizon_balls=6, n_sims=2000)` returns mean, std, p5, p95 within 500ms

### Implementation for User Story 2

- [X] T018 [US2] Extend `simulate()` to support `horizon_balls` parameter in `src/bbl_pipeline/simulation/engine.py`
- [X] T019 [US2] Implement vectorized simulation across N simulations in `src/bbl_pipeline/simulation/engine.py` using NumPy
- [X] T020 [US2] Vectorize state updates (score/wickets/balls arrays) in `src/bbl_pipeline/simulation/engine.py`
- [ ] T021 [US2] Batch terminal state evaluation (call evaluator once with 2000 states) in `src/bbl_pipeline/simulation/engine.py`
- [X] T022 [US2] Calculate percentiles (p5, p95) in SimulationResult in `src/bbl_pipeline/simulation/engine.py`
- [X] T023 [P] [US2] Create unit test for 6-ball simulation in `tests/test_simulation.py`
- [X] T024 [US2] Verify 6-ball simulation completes in <500ms (optimized) in `scripts/benchmark_simulation.py` (~60ms actual)
- [X] T025 [US2] Add integration test with real match state in `tests/integration/test_simulation_integration.py`

### ML Model Batch Evaluation (Accuracy Mode)

**Goal**: Use league-calibrated ML model instead of resource_win_prob for more accurate Monte Carlo probabilities

- [X] T055 [US2] Add `predict_batch()` method to Predictor for batch evaluation of multiple states in `src/bbl_pipeline/inference/predictor.py`
- [X] T056 [US2] Update `TerminalStateEvaluator` to accept optional Predictor in `src/bbl_pipeline/simulation/evaluator.py`
- [X] T057 [US2] Add `evaluate_batch_with_model()` method to TerminalStateEvaluator for batch ML evaluation
- [X] T058 [US2] Update `simulate()` and `simulate_vectorized()` to accept optional `predictor` parameter in `src/bbl_pipeline/simulation/engine.py`
- [X] T059 [US2] Update `crex_live_predictor.py` to pass predictor to simulate() for ML model evaluation
- [X] T060 [P] [US2] Create unit test for batch ML model evaluation in `tests/test_simulation.py`
- [X] T061 [US2] Verify ML model batch simulation completes in <1000ms in `scripts/benchmark_simulation.py`
  - **COMPLETED**: Optimized with vectorized feature generation - ~49ms for 2000 sims (20x faster than target)
  - **Implementation**: Vectorized numpy operations for all dynamic features, batch model prediction, batch calibration

**Checkpoint**: User Story 2 enhanced - ML model batch evaluation fully optimized
- Default (fast): ~100ms using resource_win_prob heuristic
- ML model mode: ~49ms (faster than resource_win_prob!) using vectorized feature generation

---

## Phase 5: User Story 3 - League Temperature Calibration (Priority: P2)

**Goal**: Apply league-specific temperature scaling to simulation outputs

**Independent Test**: `simulate(..., league="sa20")` applies T₂=0.765 and shifts probabilities correctly

### Implementation for User Story 3

- [X] T026 [US3] Create temperature loading from `models/t20_male_v1/league_calibrators/<league>/` in `src/bbl_pipeline/simulation/evaluator.py`
- [X] T027 [US3] Integrate temperature application at terminal evaluation (after `resource_win_prob`) in `src/bbl_pipeline/simulation/evaluator.py`
- [X] T028 [US3] Add `temperature` field to SimulationResult in `src/bbl_pipeline/simulation/state.py`
- [X] T029 [US3] Handle missing calibrator gracefully (default T=1.0) in `src/bbl_pipeline/simulation/evaluator.py`
- [X] T030 [P] [US3] Create unit test for temperature math (0.60 @ T=0.8 → 0.624) in `tests/test_simulation.py`
- [X] T031 [US3] Test BBL and SA20 temperature loading in `tests/integration/test_simulation_integration.py`

**Checkpoint**: User Story 3 complete - temperature calibration works for all leagues

---

## Phase 6: User Story 4 - Betting Decision Support (Priority: P2)

**Goal**: Provide clear BET/PASS/HEDGE recommendations with guardrails

**Independent Test**: `evaluate_bet(sim_result, market_odds, innings, phase)` returns correct action

### Implementation for User Story 4

- [X] T032 [US4] Create BettingThresholds dataclass in `src/bbl_pipeline/simulation/betting.py` with EDGE_MIN_BY_PHASE, SIGMA_MAX_BY_PHASE
- [X] T033 [US4] Create BettingDecision dataclass in `src/bbl_pipeline/simulation/betting.py` with action, edge, reasons
- [X] T034 [US4] Implement `evaluate_bet()` function in `src/bbl_pipeline/simulation/betting.py` with decision logic
- [ ] T035 [US4] Implement 1-ball/6-ball agreement check in `src/bbl_pipeline/simulation/betting.py`
- [X] T036 [US4] Add configurable threshold overrides to `evaluate_bet()` in `src/bbl_pipeline/simulation/betting.py`
- [X] T037 [P] [US4] Create unit test for betting decision logic in `tests/test_simulation.py`
- [X] T038 [US4] Test phase-aware thresholds (inn2_death=15%, inn1_middle=30%) in `tests/test_simulation.py`
- [ ] T039 [US4] Test 1-ball/6-ball disagreement detection in `tests/test_simulation.py`
- [X] T052 [US4] Add `model_prob` parameter to `evaluate_bet()` in `src/bbl_pipeline/simulation/betting.py` to use league-calibrated probability for edge calculation (instead of simulation mean)
- [X] T053 [US4] Update `crex_live_predictor.py` to pass league-calibrated model probability to `evaluate_bet()`
- [X] T054 [P] [US4] Create unit test for `evaluate_bet()` with explicit `model_prob` override in `tests/test_simulation.py`

**Checkpoint**: User Story 4 complete - betting decisions work with phase-aware thresholds and use league-calibrated model probability for edge calculation

---

## Phase 7: User Story 5 - Data-Driven Probabilities (Priority: P3)

**Goal**: Learn run/wicket distributions from historical data

**Independent Test**: Trained distributions match historical rates within ±10%

### Implementation for User Story 5

- [ ] T040 [US5] Create script to extract run distributions from ball-by-ball parquet files in `scripts/analysis/extract_phase_distributions.py`
- [ ] T041 [US5] Generate league-specific phase tables (BBL, SA20, etc.) in `scripts/analysis/extract_phase_distributions.py`
- [ ] T042 [US5] Implement league-specific distribution loading in `src/bbl_pipeline/simulation/sampler.py`
- [ ] T043 [US5] Add wicket multiplier by wickets down (lower-order effect) in `src/bbl_pipeline/simulation/sampler.py`
- [ ] T044 [P] [US5] Create validation script comparing simulated vs actual distributions in `scripts/validation/validate_phase_distributions.py`
- [ ] T045 [US5] Test that simulated death over boundary rate matches historical ±10% in validation script

**Checkpoint**: User Story 5 complete - data-driven distributions validated

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T046 [P] Export public API in `src/bbl_pipeline/simulation/__init__.py` (simulate, evaluate_bet, MatchState, etc.)
- [X] T047 [P] Add type hints and docstrings to all public functions
- [X] T048 [P] Update `src/bbl_pipeline/__init__.py` to expose simulation module
- [X] T049 [P] Add performance benchmark script in `scripts/benchmark_simulation.py`
- [ ] T050 Run quickstart.md validation - verify all examples work
- [X] T051 [P] Add structured logging for simulation stats (n_sims, time_taken_ms)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 - BLOCKS all user stories
- **Phase 3-7 (User Stories)**: All depend on Phase 2 completion
- **Phase 8 (Polish)**: Depends on all user stories being complete

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (1-ball) | Foundational | None (first) |
| US2 (6-ball) | US1 (extends simulate) | None |
| US3 (Temperature) | US1 or US2 | US4 |
| US4 (Betting) | US2 (needs σ₆) | US3 |
| US5 (Data-Driven) | Foundational | US1, US2, US3, US4 |

### Parallel Opportunities Within Phases

**Phase 1**:
```
T002 (config.py) ║ T003 (state.py) - different files
```

**Phase 2**:
```
T005 (get_phase) ║ T006 (CDF arrays) ║ T008 (temperature) - different files
T009 (test_state) ║ T010 (test_sampler) - different test files
```

**Phase 6 (US4)**:
```
T037 (test_betting) can start after T034 (evaluate_bet)
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup (~30 min)
2. Complete Phase 2: Foundational (~2 hours)
3. Complete Phase 3: US1 - Single Ball (~1.5 hours)
4. Complete Phase 4: US2 - Six Ball (~2 hours)
5. **STOP and VALIDATE**: 6-ball simulation works in < 500ms
6. Can deploy/use for basic betting analysis

### Incremental Delivery

| Milestone | Stories | Capability |
|-----------|---------|------------|
| MVP | US1 + US2 | Simulation with uncertainty |
| v1.1 | + US3 | Temperature-calibrated outputs |
| v1.2 | + US4 | Betting decision support |
| v2.0 | + US5 | Data-driven distributions |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Performance targets: 1-ball < 200ms, 6-ball < 500ms
- Temperature math: `sigmoid(logit(p) / T)` where T < 1 = sharper
- Avoid: running vectorized tests before naive implementation works
