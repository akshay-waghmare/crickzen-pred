# Tasks: T20 Reduced-Over Match Support

**Feature**: 008-t20-reduced-overs  
**Branch**: `008-t20-reduced-overs`  
**Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)  
**Generated**: 2026-02-21

---

## Phase A: Simulation Core

### Task A1 — Add `total_balls` field to `MatchState`
- **File**: `src/bbl_pipeline/simulation/state.py`
- **Lines**: L23 (docstring), L56-L57 (validation), L64 (overs_completed)
- **What**:
  1. Add `total_balls: int = 120` field to `MatchState` dataclass
  2. Update `__post_init__` validation: `0 <= self.balls_remaining <= self.total_balls` (was hardcoded 120)
  3. Validate `total_balls`: must be `6 <= total_balls <= 120` and `total_balls % 6 == 0` (allows super over = 6)
  4. Fix `overs_completed` property: `(self.total_balls - self.balls_remaining) / 6` (was `120 -`)
  5. Update `copy()` method to propagate `total_balls`
  6. Update `apply_outcome()` to not need changes (already uses `balls_remaining`)
  7. Update `phase` property call: `get_phase(self.balls_remaining, self.total_balls)`
- **Acceptance**: `MatchState(innings=1, score=0, wickets_lost=0, balls_remaining=90, total_balls=90)` creates without error. Default `total_balls=120` preserves all existing behavior.
- **Spec**: FR-009, FR-010, FR-011
- **Status**: [X] Complete

### Task A2 — Fix hardcoded 120 in evaluator
- **File**: `src/bbl_pipeline/simulation/evaluator.py`
- **Lines**: L184, L273
- **What**:
  1. L184: Change `balls_bowled = 120 - state.balls_remaining` → `balls_bowled = state.total_balls - state.balls_remaining`
  2. L273 (vectorized): Change `balls_bowled = 120 - br` → use `total_balls` from the source state. Pass `total_balls` into the batch evaluation context.
- **Acceptance**: Evaluator correctly computes `overs_completed` for a 90-ball (15-over) match state.
- **Spec**: FR-003, FR-010
- **Depends on**: A1
- **Status**: [X] Complete

### Task A3 — Propagate `total_balls` through simulation engine
- **File**: `src/bbl_pipeline/simulation/engine.py`
- **Lines**: L277 (get_phase call in vectorized), L300-L310 (MatchState creation)
- **What**:
  1. In `simulate_vectorized()`, pass `total_balls` to `get_phase()` calls: `get_phase(br, total_balls=state.total_balls)`
  2. In terminal state MatchState creation, propagate `total_balls`: `MatchState(..., total_balls=state.total_balls)`
  3. In `simulate()` (non-vectorized), ensure `sim_state.copy()` already propagates `total_balls` (via A1)
- **Acceptance**: MC simulation of a 15-over match produces correct phase classifications and terminal states with `total_balls=90`.
- **Spec**: FR-003
- **Depends on**: A1
- **Status**: [X] Complete

### Task A4 — Dynamic phase boundaries for reduced overs
- **File**: `src/bbl_pipeline/simulation/config.py`
- **Lines**: L21-L22 (POWERPLAY_END_OVER, MIDDLE_END_OVER), L25-L46 (get_phase)
- **What**:
  1. Add `get_scaled_phase_boundaries(total_overs: int) -> tuple[int, int]` function returning `(powerplay_end, middle_end)`:
     - `powerplay_end = max(2, min(6, round(total_overs * 0.30)))`
     - `death_start = total_overs - max(2, round(total_overs * 0.25)) + 1`
     - `middle_end = death_start - 1`
  2. Update `get_phase()` to use scaled boundaries when `total_balls != 120`:
     - If `total_balls == 120`: use existing constants (zero regression)
     - If `total_balls != 120`: compute `total_overs = total_balls // 6`, call `get_scaled_phase_boundaries(total_overs)`
  3. Keep `POWERPLAY_END_OVER = 6` and `MIDDLE_END_OVER = 15` as constants for the default 20-over case
- **Acceptance**: `get_phase(balls_remaining=12, total_balls=72)` correctly returns `"death"` (over 10 of a 12-over match). `get_phase(balls_remaining=12, total_balls=120)` still returns `"middle"` (over 18 of 20-over match).
- **Spec**: FR-004
- **Status**: [X] Complete

---

## Phase B: FormatConfig

### Task B1 — Add `FormatConfig.t20_reduced()` factory method
- **File**: `src/bbl_pipeline/features/format_config.py`
- **Lines**: After existing `t20()` factory (~L282)
- **What**:
  1. Add class method `t20_reduced(cls, total_overs: int) -> FormatConfig`:
     - Validate `1 <= total_overs <= 20`
     - If `total_overs == 20`: return `cls.t20()` (identical)
     - Compute `total_balls = total_overs * 6`
     - Compute scaled phase thresholds using same formula as A4:
       - `pp_end = max(2, min(6, round(total_overs * 0.30)))`
       - `death_start = total_overs - max(2, round(total_overs * 0.25)) + 1`
       - `phase_thresholds = {"powerplay": pp_end, "middle": death_start - 1, "death": total_overs - 1, "final": total_overs}`
     - Compute `par_score` via DLS: `par = 160.0 * dls_resource_pct(total_overs, wickets=0)` using the existing DLS resource table
     - Copy all other fields from T20 base (DLS table, run rates, wicket penalties, etc.)
  2. Update `from_league()` to NOT use this — `from_league()` always returns full T20/ODI. Reduced config is created explicitly by the caller.
- **Acceptance**: `FormatConfig.t20_reduced(15).par_score` is between 130-140. `FormatConfig.t20_reduced(20) == FormatConfig.t20()`. `FormatConfig.t20_reduced(1)` creates valid super-over config.
- **Spec**: FR-004, FR-005
- **Depends on**: A4 (same phase scaling formula)
- **Status**: [X] Complete

---

## Phase C: Inference Integration

### Task C1 — CLI arguments and prediction mode switch
- **File**: `src/bbl_pipeline/inference/crex_live_predictor.py`
- **Lines**: L1730-L1791 (argparse), L114 (format_config init), L260-L267 (MC simulation), L1187+ (prediction flow)
- **What**:
  1. Add CLI arguments to argparse:
     - `--total-overs` (int, default=None, help="Total overs per innings (1-20). Auto-detected from CREX if not specified.")
     - `--revised-target` (int, default=None, help="DLS revised target for 2nd innings. Auto-detected from CREX if not specified.")
  2. In `__init__` or early setup: if `--total-overs` provided, create `FormatConfig.t20_reduced(total_overs)` instead of `FormatConfig.from_league(league)`
  3. Add prediction mode routing:
     ```
     if effective_total_overs < 20:
         # MC-only mode
         result = self._run_monte_carlo_simulation(...)
         win_prob = mc_calibrator.calibrate(result['mc_win_prob'])
     else:
         # Standard model + calibration chain (existing code)
         win_prob = self._predict_standard(...)
     ```
  4. Add mode switch detection: if `total_overs` changes from 20 to <20 during a live session, log: `"Switching to MC-only mode: total_overs={new}, ball={current_ball}"`
  5. For `revised_target`: when provided, override `self.match_state.target` for innings 2
  6. Ensure `_run_monte_carlo_simulation()` creates `MatchState(total_balls=total_overs*6)` 
- **Acceptance**: `bbl-pipeline` predictor accepts `--total-overs 15 --revised-target 156` without error. When `total_overs=15`, only MC predictions are produced (model not invoked). When `total_overs=20` or not provided, behavior is identical to current production.
- **Spec**: FR-001, FR-002, FR-008, FR-011, FR-013, FR-014, FR-015
- **Depends on**: A1, B1
- **Status**: [X] Complete

### Task C2 — CREX DLS auto-detection
- **File**: `src/bbl_pipeline/inference/crex_live_predictor.py`
- **Lines**: L920-L993 (state parsing section)
- **What**:
  1. Add regex patterns to detect reduced overs and DLS target from CREX page:
     - Revised target: `r'(?:revised\s+)?target\s*[:\-]\s*(\d+)\s*\(?(?:d/?l/?s?|dls)\)?'` (case-insensitive)
     - Reduced overs: `r'(\d+)\s+ov(?:er)?s?\s+(?:match|per\s+side|a\s+side)'` (case-insensitive)
  2. Add DOM fallback: check near odds portal area for DLS info divs
  3. Check sV3 API response for match metadata containing total overs
  4. Input priority logic: CLI override > CREX detected > default 20
  5. On each scrape cycle: check if detected `total_overs` differs from current; if so, trigger mode switch (C1 logic)
  6. Log when detection finds reduced overs: `"CREX detected reduced overs: {n} (was: {prev})"`
- **Acceptance**: When a CREX page shows "Revised Target: 156 (DLS)" text, the system extracts `revised_target=156`. When no DLS text found, defaults to standard behavior.
- **Spec**: FR-001, FR-002, FR-015
- **Depends on**: C1
- **Notes**: CREX page structure may vary — regex patterns need validation against real DLS match pages. Build with defensive parsing (try/except, log failures, fall back to CLI/default).
- **Status**: [X] Complete

### Task C3 — Match state schema update
- **File**: `src/bbl_pipeline/inference/match_state_schema.py`
- **Lines**: BALL_STATE_SCHEMA definition
- **What**:
  1. Add `("total_overs", pa.int16())` to `BALL_STATE_SCHEMA` (default 20)
  2. Add `("revised_target", pa.int16())` to `BALL_STATE_SCHEMA` (nullable, default null)
  3. Update `MatchStateLogger` to write these fields from current match state
- **Acceptance**: Recorded Parquet files from a reduced-over match contain `total_overs=15` and `revised_target=156` columns. Existing 20-over recordings show `total_overs=20` and `revised_target=null`.
- **Spec**: FR-012
- **Depends on**: C1
- **Status**: [X] Complete

---

## Phase D: MC Calibration (parallel with B+C)

### Task D1 — MC Platt calibrator module
- **File**: `src/bbl_pipeline/calibration/mc_calibrator.py` (NEW)
- **What**:
  1. Create `MCCalibrator` class:
     - `__init__(self)`: Initialize with `LogisticRegression` from sklearn
     - `fit(self, mc_probs: np.ndarray, actual_outcomes: np.ndarray)`: Fit Platt scaling on `logit(mc_probs)` vs `actual_outcomes`
     - `calibrate(self, mc_raw_prob: float) -> float`: Apply Platt scaling to single MC prediction
     - `calibrate_batch(self, mc_raw_probs: np.ndarray) -> np.ndarray`: Vectorized version
     - `save(self, path: str)`: Serialize via joblib
     - `load(cls, path: str) -> MCCalibrator`: Class method to deserialize
  2. Include metadata: `training_samples`, `training_log_loss`, `training_brier`, `fitted_date`
  3. Handle edge cases: clip `mc_raw_prob` to `[0.001, 0.999]` before logit to avoid inf
  4. Create `src/bbl_pipeline/calibration/__init__.py` if directory is new
- **Acceptance**: `MCCalibrator` fits on 1000 sample pairs in <1 second. `calibrate(0.65)` returns a float between 0 and 1. `save()` + `load()` roundtrips correctly.
- **Spec**: FR-016, FR-017
- **Status**: [X] Complete

### Task D2 — MC backtest training script
- **File**: `scripts/train_mc_calibrator.py` (NEW)
- **What**:
  1. Load training data from `--training-data` (Parquet with ball-level features + outcomes)
  2. Sample `--n-samples` ball states (default 10000) stratified by innings and phase
  3. For each sample: run MC simulation (`--n-simulations`, default 1000) → get `mc_raw_prob`
  4. Pair with actual match outcome (batting team won / lost)
  5. Split 80/20 train/validation
  6. Fit `MCCalibrator` on training set
  7. Evaluate on validation: log loss, Brier, ECE
  8. Gate check: log loss ≤ 0.55 and ECE < 0.0021 on validation
  9. Save calibrator to `--output` (default: `{model-dir}/mc_calibrator.pkl`)
  10. Print summary report with metrics
- **Acceptance**: Script completes successfully on BBL training data. Validation log loss ≤ 0.55. Calibrator file created.
- **Spec**: FR-017, SC-007, SC-009
- **Depends on**: D1
- **Notes**: This may take 30-60 minutes for 10K samples × 1000 simulations. Consider vectorized MC path for speed.
- **Status**: [X] Complete

---

## Phase E: Testing

### Task E1 — Update existing simulation tests
- **File**: `tests/test_simulation.py`
- **Lines**: ~L100-L110 (TestMatchState validation tests)
- **What**:
  1. Update `TestMatchState` to verify `total_balls=120` default behavior (regression test)
  2. Add test: `MatchState(balls_remaining=90, total_balls=90)` is valid
  3. Add test: `MatchState(balls_remaining=91, total_balls=90)` raises `ValueError`
  4. Add test: `overs_completed` property returns correct value for non-120 total_balls
  5. Verify all existing tests pass without modification (no assertion changes needed if defaults are correct)
- **Acceptance**: `pytest tests/test_simulation.py` passes with 0 failures. All pre-existing tests produce identical results.
- **Spec**: SC-006
- **Status**: [X] Complete

### Task E2 — New reduced-over test suite
- **File**: `tests/test_reduced_overs.py` (NEW)
- **What**:
  1. **Phase boundary tests**:
     - `test_phase_15_overs`: over 12 of 15-over match is death, not middle
     - `test_phase_10_overs`: over 8 of 10-over match is death
     - `test_phase_5_overs`: over 4 of 5-over match is death
     - `test_phase_20_overs_unchanged`: over 16 of 20-over match is death (regression)
  2. **FormatConfig tests**:
     - `test_reduced_config_par_score`: 15-over par ≈ 133 (±5%)
     - `test_reduced_config_identity`: `t20_reduced(20) == t20()`
     - `test_reduced_config_super_over`: `t20_reduced(1)` creates valid config
     - `test_reduced_config_total_balls`: `t20_reduced(12).total_balls == 72`
  3. **MatchState tests**:
     - `test_state_reduced_validation`: `balls_remaining=60, total_balls=60` is valid
     - `test_state_reduced_overs_completed`: correct overs_completed for 90-ball match
  4. **MC simulation tests**:
     - `test_mc_reduced_over_completes`: MC simulation on 15-over state returns valid probability
     - `test_mc_reduced_vs_full`: MC on 15-over match at same score/overs-remaining gives different probability than 20-over
  5. **Evaluator tests**:
     - `test_evaluator_reduced_balls_bowled`: Evaluator computes correct `balls_bowled` for 90-ball state
  6. **Regression tests**:
     - `test_20_over_regression`: Full pipeline with default `total_balls=120` produces identical output to pre-change baseline
- **Acceptance**: All tests pass. Coverage: phase boundaries (4 tests), FormatConfig (4), MatchState (2), MC simulation (2), evaluator (1), regression (1) = 14 tests minimum.
- **Spec**: SC-001, SC-003, SC-005, SC-006
- **Depends on**: A1-A4, B1
- **Status**: [X] Complete

### Task E3 — Integration tests for reduced-over scenarios
- **File**: `tests/integration/test_simulation_integration.py`
- **Lines**: After existing test scenarios
- **What**:
  1. Add `test_reduced_over_chase_scenario`: 15-over match, team 2 chasing 135, at 80/2 after 10 overs. Run MC. Win prob should be between 0.3 and 0.7 (reasonable range).
  2. Add `test_reduced_over_first_innings`: 12-over match, team 1 at 95/3 after 9 overs. MC projects a realistic expected score (not 163-level).
  3. Add `test_mode_switch_simulation`: Create a match state that starts at 20 overs, then changes to 16 overs. Verify MC simulation adjusts horizon.
- **Acceptance**: All integration tests pass. Performance: each MC simulation completes in <1 second (SC-002).
- **Spec**: SC-002, SC-004
- **Depends on**: A1-A4, B1
- **Status**: [X] Complete

---

## Summary

| Phase | Tasks | Est. Lines | Dependencies |
|-------|:-----:|:----------:|:------------:|
| A: Simulation Core | 4 | ~60 | None |
| B: FormatConfig | 1 | ~50 | A4 |
| C: Inference | 3 | ~90 | A1, B1 |
| D: MC Calibration | 2 | ~160 | None (parallel) |
| E: Testing | 3 | ~200 | A, B |
| **Total** | **13** | **~560** | |

### Execution Order (critical path)

```
A1 → A2 ─┐
A1 → A3 ─┤
     A4 ──┼─→ B1 ──→ C1 → C2
          │          C1 → C3
          │
D1 → D2 ─┘  (parallel)
          │
          └─→ E1 → E2 → E3
```

**Parallelizable**: Phase D (MC calibration) can be done entirely in parallel with Phases B and C.
