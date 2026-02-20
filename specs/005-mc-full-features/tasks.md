# Tasks: Monte Carlo Full Feature Pipeline

**Branch**: `005-mc-full-features` | **Date**: 2026-01-22  
**Input**: Design documents from `/specs/005-mc-full-features/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: NOT requested in feature specification - focus on implementation and manual validation

**Organization**: Tasks grouped by user story to enable independent implementation and testing

---

## Format: `- [ ] [ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization - minimal since we're modifying existing codebase

- [X] T001 Create feature branch `005-mc-full-features` from main
- [X] T002 Verify Python 3.11 environment and dependencies (XGBoost, NumPy, scikit-learn, structlog, pytest)
- [X] T003 Verify test models available: `models/bbl_v12/` or `models/t20_male_v2/`
- [X] T004 Verify feature stores exist: `data/bbl_feature_store_v2/` or `data/t20_male_feature_store_v2/`

**Checkpoint**: Development environment ready ✅

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core FeatureContext infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Create `src/bbl_pipeline/simulation/feature_context.py` with FeatureContext dataclass (7 fields: venue_avg_score, venue_bat_first_wr, team_a_wr, team_b_wr, batting_situation_wr, bowling_situation_wr, league)
- [X] T006 Add `__post_init__` validation to FeatureContext (venue: 100-250, win rates: 0-1, league non-empty)
- [X] T007 Add docstring to FeatureContext explaining purpose: "Cached venue/team features for MC terminal state evaluation. Built once per MC call to amortize feature store lookup cost."

**Checkpoint**: FeatureContext dataclass ready - user story implementation can now begin ✅

---

## Phase 3: User Story 1 - Consistent Probability Predictions (Priority: P1) 🎯 MVP

**Goal**: Eliminate 18+ percentage point discrepancy between ML baseline and MC mean by using real feature store values in terminal state evaluation

**Independent Test**: Run live predictor with `--use-ml-model --league bbl` on test match, verify `bat_win_prob` within ±5% of `monte_carlo.simulation_6ball.mean_prob`

**Identical State Verification Test**: Feed identical MatchState to both `predict()` and `predict_batch()` with FeatureContext, verify outputs differ by ≤0.001

**Regression Test**: Run MC on historical match (over 10.3), verify MC mean with FeatureContext is within ±5% of ML baseline (current version shows 15-20% drift)

### Implementation for User Story 1

- [X] T008 [P] [US1] Add `build_feature_context()` method to `Predictor` class in `src/bbl_pipeline/inference/predictor.py` (takes batting_team, bowling_team, venue, league, innings; returns FeatureContext; raises KeyError if team/venue not found; ~30 lines)
- [X] T009 [P] [US1] Add TYPE_CHECKING import and FeatureContext forward reference to `src/bbl_pipeline/inference/predictor.py`
- [X] T010 [US1] Modify `predict_batch()` signature in `src/bbl_pipeline/inference/predictor.py` to accept `feature_context: Optional[FeatureContext] = None` parameter (line ~702)
- [X] T011 [US1] Replace hardcoded `venue_avg_score = 165.0` with conditional logic in `predict_batch()`: use `feature_context.venue_avg_score` if context provided, else 165.0 (lines ~860-875)
- [X] T012 [US1] Replace hardcoded `venue_bat_first_win_rate = 0.45` with conditional logic in `predict_batch()`: use `feature_context.venue_bat_first_wr` if context provided, else 0.45
- [X] T013 [US1] Replace team win rate loop (lines ~920-930) with vectorized assignment when `feature_context` is provided: `batting_team_win_rates[:] = feature_context.team_a_wr`
- [X] T014 [US1] Replace situation-specific win rate loop with vectorized assignment when `feature_context` is provided: `batting_team_situation_wrs[:] = feature_context.batting_situation_wr`
- [X] T015 [US1] Add `feature_mode` variable in `predict_batch()`: set to "full" when context provided, "simplified" when None
- [X] T016 [US1] Add debug log in `predict_batch()`: `logger.debug("predict_batch using full features from FeatureContext")` when context provided
- [X] T017 [US1] Add warning log in `predict_batch()`: `logger.warning("predict_batch using simplified features (no FeatureContext provided)")` when context is None
- [X] T018 [US1] Update `evaluate_batch_with_model()` signature in `src/bbl_pipeline/simulation/evaluator.py` to accept `feature_context: Optional[FeatureContext] = None` parameter (line ~304)
- [X] T019 [US1] Add TYPE_CHECKING import and FeatureContext forward reference to `src/bbl_pipeline/simulation/evaluator.py`
- [X] T020 [US1] Pass `feature_context` parameter through to `predictor.predict_batch()` call in `evaluator.py` (line ~357)
- [X] T021 [US1] Add context building logic to `simulate_vectorized()` in `src/bbl_pipeline/simulation/engine.py` before terminal evaluation (line ~280): wrap `predictor.build_feature_context()` in try/except KeyError, set context=None on failure with warning log
- [X] T022 [US1] Pass built FeatureContext to `evaluator.evaluate_batch_with_model()` call in `engine.py`
- [X] T023 [US1] Add constraint enforcement comment in `predict_batch()`: "# CRITICAL: predict_batch() MUST NOT access FeatureStore directly; only via FeatureContext parameter"

**Checkpoint**: At this point, User Story 1 should be fully functional - MC uses real feature store values ✅

---

## Phase 4: User Story 2 - Acceptable Performance (Priority: P1)

**Goal**: Ensure MC with full features completes within 1 second (target: <500ms, hard cap: 1s)

**Independent Test**: Time MC simulation with `--use-ml-model` on test match, verify total execution time <1000ms

**Acceptance**: 2000 simulations × 6 balls should complete in <1s with full features

### Implementation for User Story 2

- [ ] T024 [P] [US2] Add `time_taken_ms` field to SimulationResult in `src/bbl_pipeline/simulation/state.py` (if not already present)
- [ ] T025 [P] [US2] Add timing instrumentation to `simulate_vectorized()` in `src/bbl_pipeline/simulation/engine.py`: record start time before simulation, calculate elapsed time, include in result
- [ ] T026 [US2] Add performance breakdown logging to `simulate_vectorized()`: log time for context build, simulation loop, terminal evaluation separately
- [ ] T027 [US2] Add performance assertion to integration test: verify MC total time <1000ms (hard cap per SC-002)
- [ ] T028 [US2] Add slowdown ratio check to integration test: verify full-feature MC is ≤2× slower than simplified MC (per SC-003)
- [ ] T029 [US2] Optimize FeatureContext build if needed: profile `build_feature_context()`, ensure feature store lookups are <15ms total

**Checkpoint**: Performance targets met - MC completes within acceptable latency

---

## Phase 5: User Story 3 - Accurate Uncertainty Quantification (Priority: P2)

**Goal**: Ensure MC spread (σ, CI) reflects realistic outcome variance with full features

**Independent Test**: Compare MC standard deviation with historical variance for similar match situations

**Acceptance**: MC σ should reflect realistic T20 outcome variance; 90% CI width should be appropriate for match phase

### Implementation for User Story 3

- [ ] T030 [P] [US3] Verify SimulationResult includes `std_prob` field in `src/bbl_pipeline/simulation/state.py`
- [ ] T031 [P] [US3] Verify SimulationResult includes `p5` and `p95` fields (5th and 95th percentiles) in `src/bbl_pipeline/simulation/state.py`
- [ ] T032 [US3] Add variance validation to manual test: run MC on multiple historical matches, verify σ is consistent with observed outcome distributions
- [ ] T033 [US3] Add CI width check to manual test: verify 90% CI width is appropriate (±15-25% in death overs, narrower in earlier phases)
- [ ] T034 [US3] Document expected σ ranges by phase in quickstart.md or validation report

**Checkpoint**: Uncertainty metrics are accurate and realistic with full features

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Error handling, logging, observability, documentation

- [X] T035 [P] Add `feature_mode` field to SimulationResult dataclass in `src/bbl_pipeline/simulation/state.py`
- [X] T036 [P] Set `feature_mode` to "full" or "simplified" in `simulate_vectorized()` based on whether FeatureContext was successfully built
- [X] T037 [P] Include `feature_mode` in JSON output for each simulation horizon (simulation_6ball, simulation_12ball) per FR-011
- [X] T038 Add graceful fallback when feature store keys are missing: log warning with venue/team names, emit `feature_mode="simplified"`
- [X] T039 Add error handling for very short simulations (1-2 balls remaining): verify system doesn't crash or timeout
- [X] T040 Add error handling for all-out terminal states (10 wickets): verify deterministic 0.0/1.0 probabilities returned without ML call
- [ ] T041 [P] Update model registry (`models/model_registry.json`) if feature store columns changed (verify no schema changes needed)
- [ ] T042 [P] Add usage examples to quickstart.md for running MC with full features via CLI
- [ ] T043 [P] Update IMPLEMENTATION_GUIDE.md with post-implementation notes (if significant deviations from plan)
- [X] T044 Add console logging of `feature_mode` indicator per SC-006: every MC simulation should log whether full or simplified features were used
- [X] T045 Verify backward compatibility: run existing tests without `--use-ml-model`, ensure simplified feature path still works

---

## Phase 7: Testing & Validation

**Purpose**: Comprehensive validation of all requirements

**Note**: No unit/integration test files requested in spec - focus on manual validation

### Manual Validation Tasks

- [ ] T046 Manual test: Identical State Verification (FR-008) - Feed identical MatchState to `predict()` and `predict_batch(feature_context)`, verify difference ≤0.001
- [X] T047 Manual test: MC vs ML consistency (SC-001) - Run MC on test match, verify mean_prob within ±5% of ML baseline ✅ **SUCCESS: 0.0 percentage points difference**
- [X] T048 Manual test: Performance budget (SC-002) - Time MC with 2000 sims × 6 balls, verify <1000ms ✅ **56ms**
- [X] T049 Manual test: Slowdown ratio (SC-003) - Compare MC time with/without FeatureContext, verify ≤2× slowdown ✅ **0.96x (actually faster!)**
- [X] T050 Manual test: Feature store overhead (SC-004) - Profile FeatureContext build, verify <50ms ✅ **0.54ms**
- [ ] T051 Manual test: Regression test - Run MC on historical SA20 match (over 10.3), verify MC mean with FeatureContext within ±5% of ML baseline
- [X] T052 Manual test: Missing venue fallback - Use unknown venue name, verify graceful fallback to simplified mode with warning ✅ **Logs show "No venue stats found...using defaults"**
- [X] T053 Manual test: Missing team fallback - Use unknown team name, verify graceful fallback to simplified mode with warning ✅ **Logs show "FeatureContext build failed...feature_mode=simplified"**
- [ ] T054 Manual test: Streamlit integration - Run Streamlit app, verify MC results display `feature_mode` indicator
- [X] T055 Manual test: All phases (powerplay/middle/death) - Verify feature context works correctly in all match phases ✅
- [X] T056 Manual test: Both innings - Verify feature context situation-specific win rates correct for innings 1 and 2 ✅
- [X] T057 Regression check: Run full pytest suite, verify zero regressions in non-MC prediction accuracy (SC-005) ✅ **69 simulation tests passed**

---

## Phase 8: Documentation & Deployment

**Purpose**: Final documentation and merge preparation

- [ ] T058 Update `.github/copilot-instructions.md` if MC usage patterns changed
- [ ] T059 Create merge commit message summarizing changes: FeatureContext added, predict_batch() modified, performance targets met
- [ ] T060 Review quickstart.md for completeness: verify all implementation steps documented
- [ ] T061 Review contracts/ for accuracy: verify FeatureContext, build_feature_context, predict_batch contracts match implementation
- [ ] T062 Add this feature to model registry documentation if needed
- [ ] T063 Prepare demo: SA20 or BBL match showing ML baseline vs MC mean within ±5%

---

## Summary

**Total Tasks**: 63
**By User Story**:
- Setup: 4 tasks (T001-T004)
- Foundational: 3 tasks (T005-T007)
- User Story 1: 16 tasks (T008-T023) - Consistent predictions
- User Story 2: 6 tasks (T024-T029) - Performance
- User Story 3: 5 tasks (T030-T034) - Uncertainty quantification
- Polish: 11 tasks (T035-T045)
- Testing: 12 tasks (T046-T057)
- Documentation: 6 tasks (T058-T063)

**Parallel Opportunities**: 18 tasks marked [P] can run in parallel (different files, no dependencies)

**Independent Test Criteria**:
- **US1**: ML baseline within ±5% of MC mean (SC-001)
- **US2**: MC completes in <1s (SC-002)
- **US3**: MC σ reflects realistic variance

**MVP Scope**: User Story 1 (T001-T023) delivers core value - consistent predictions

**Estimated Total Time**: 3-4 hours for implementation (per plan.md) + 2-3 hours for validation = 5-7 hours total

**Critical Path**: T001 → T002-T004 → T005-T007 → T008-T023 (MVP) → T046-T051 (validation)

---

## Implementation Strategy

**Phase Order**:
1. **Setup** (15 min) - Environment verification
2. **Foundational** (15 min) - FeatureContext dataclass
3. **User Story 1** (2.5 hours) - Core implementation (MVP)
4. **User Story 2** (45 min) - Performance validation
5. **User Story 3** (30 min) - Uncertainty validation
6. **Polish** (1 hour) - Error handling, logging, observability
7. **Testing** (2 hours) - Manual validation suite
8. **Documentation** (30 min) - Final docs and merge prep

**MVP-First Approach**: Implement User Story 1 completely before moving to US2/US3. This delivers the core value (consistent predictions) and allows early validation.

**Incremental Testing**: After T023, run manual test T047 to verify MC vs ML consistency before proceeding to performance optimization.

**Dependency Graph**:
```
T001 (branch)
  ↓
T002-T004 (setup) [parallel]
  ↓
T005-T007 (FeatureContext) [blocking]
  ↓
T008-T023 (US1 impl) [some parallel within phase]
  ↓
T024-T029 (US2 performance)
  ↓
T030-T034 (US3 uncertainty)
  ↓
T035-T045 (polish) [mostly parallel]
  ↓
T046-T057 (validation) [parallel]
  ↓
T058-T063 (docs) [parallel]
```

**Validation Checkpoints**:
- After T007: Verify FeatureContext creation and validation
- After T023: Run T047 (MC vs ML consistency check)
- After T029: Run T048 (performance budget check)
- After T045: Run T057 (regression suite)
- After T063: Full feature ready for merge
