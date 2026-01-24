# Feature Specification: Monte Carlo Full Feature Pipeline

**Feature Branch**: `005-mc-full-features`  
**Created**: 2026-01-22  
**Status**: Draft  
**Input**: User description: "Improve --use-ml-model option in Monte Carlo to use full feature pipeline instead of simplified predict_batch defaults"

## Definitions

- **Baseline ML probability**: The output of the main predictor's `predict()` method on the current MatchState at time T
- **MC mean probability**: The mean of terminal state probabilities evaluated by the ML model over N simulations
- **Identical match state**: The exact MatchState object used by `predict()` at time T, including all fields: over/ball, runs, wickets, target, innings, batting_team, bowling_team, and any derived fields (RRR, CRR, phase, balls_remaining) that affect ML predictions
- **Feature-store keys**: The identifiers used to lookup venue statistics, team ratings, and player stats from the InMemoryFeatureStore (venue_key, team_a_key, team_b_key, league)
- **Calibration chain**: The sequence of calibrators applied to raw model output: base model → per-over isotonic → league temperature/platt scaling

## Current State Analysis

### What Already Works ✅

Validation performed on 2026-01-22 confirms:

- **Monte Carlo simulation core is CORRECT** - No changes needed to `engine.py`, `sampler.py`, or state transition logic
- **Wickets fall correctly** - Phase-specific probabilities (5-5.5% per ball), proper increment, all-out detection
- **State-dependent features recompute correctly** - RRR, CRR, phase, resource%, expected_final_score all derive from updated state
- **No frozen/stale features** - All features in `predict_batch()` derive from MatchState arguments
- **All-out scenarios handled** - Deterministic 0.0/1.0 probabilities, no wasted ML calls
- **MatchState propagation correct** - Team names, venue, league properly copied to terminal states

### The Single Root Cause ❌

**Problem**: `predict_batch()` uses hardcoded defaults for venue/team features instead of feature store lookups.

**Evidence** (from `predictor.py` lines 860-875):
```python
# Venue stats (use defaults for speed - actual lookups are expensive)
venue_avg_score = 165.0                    # ❌ Should be from feature store
venue_bat_first_win_rate = 0.45            # ❌ Should be from feature store

# Team stats - extract from states if available, otherwise use defaults
batting_team_win_rates[i] = getattr(state, 'batting_team_win_rate', 0.5)  # ❌ Fallback to 0.5
```

**Impact**: Monte Carlo generates realistic future states but evaluates them with wrong venue/team context:
- Perth Stadium actual avg: ~150 runs → MC uses 165 (generic default)
- Team win rates: Actual 0.62/0.38 → MC uses 0.5/0.5 (generic defaults)
- Result: 18+ percentage point discrepancy (31.2% ML baseline vs 49.6% MC mean)

**This is the ONLY bug** - MC simulation logic is already production-grade.

### The Surgical Fix

This feature implements a **surgical fix to terminal evaluation only**:

1. **Add FeatureContext** - Cache venue/team stats ONCE per MC call (not per state)
2. **Modify `predict_batch()`** - Use FeatureContext values instead of hardcoded defaults
3. **Keep everything else unchanged** - No MC logic changes, no performance regression

**Not a rewrite** - This is a targeted fix to inject real feature-store values into an already-correct MC pipeline.

See [SIMULATION_STATE_VALIDATION.md](SIMULATION_STATE_VALIDATION.md) for detailed validation report.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent Probability Predictions (Priority: P1)

As a live match predictor user, I want the Monte Carlo simulation results to be consistent with the main ML model predictions, so that I don't see confusing discrepancies between the displayed win probability and the simulation mean.

**Why this priority**: Core value proposition - users currently see 18+ percentage point differences between ML model (31.2%) and MC simulation (49.6%), causing confusion about which prediction to trust.

**Independent Test**: Run live predictor with `--use-ml-model --league sa20`, compare `bat_win_prob` with `monte_carlo.simulation_6ball.mean_prob`. Values should differ by less than 5 percentage points.

**Identical State Verification Test**: Serialize MatchState at time T (JSON), feed identical state into: (1) main predictor `predict()`, (2) MC terminal evaluator with N=1 simulation (no randomness) using FeatureContext. Verify outputs are identical within epsilon (≤0.001, not just ±5%), confirming same feature pipeline. This test MUST pass to validate FR-001/FR-002 compliance.

**Regression Test**: Run MC with `--use-ml-model` on historical match at over 10.3 (known state). Record: (a) ML baseline prob, (b) MC mean prob with simplified features (current), (c) MC mean prob with FeatureContext (fixed). Verify (c) is within ±5% of (a) while (b) shows 15-20% drift.

**Acceptance Scenarios**:

1. **Given** a live match with ML model showing 40% win probability, **When** Monte Carlo simulation runs with ML model enabled, **Then** the MC mean probability should be within ±5% of the ML model baseline (using identical match state as defined above)
2. **Given** feature store loaded with actual team/venue stats, **When** MC evaluates terminal states, **Then** the feature values used should match those from the full feature pipeline
3. **Given** a match in any phase (powerplay, middle, death), **When** using ML terminal evaluation, **Then** venue/team features must come from the same feature-store keys used by main `predict()`, not hardcoded defaults

---

### User Story 2 - Acceptable Performance (Priority: P1)

As a live match viewer, I want Monte Carlo simulations to complete within an acceptable timeframe, so that the UI remains responsive during live updates.

**Why this priority**: Performance is a hard constraint - users cannot wait 5+ seconds for MC results during live matches with 2-second refresh intervals.

**Independent Test**: Time MC simulation with full features enabled. Should complete within acceptable latency budget.

**Acceptance Scenarios**:

1. **Given** MC running with 2000 simulations, **When** using full feature pipeline, **Then** total MC time should complete within 1 second
2. **Given** live predictor with 2-second refresh interval, **When** MC simulation runs, **Then** it should not block the main prediction loop beyond 1.5 seconds total
3. **Given** high-frequency updates during exciting match moments, **When** multiple MC simulations queue up, **Then** the system should gracefully handle the load without crashing

---

### User Story 3 - Accurate Uncertainty Quantification (Priority: P2)

As a betting decision maker, I want the Monte Carlo uncertainty bounds (σ, CI) to reflect realistic outcome variance, so that I can make informed decisions about bet timing and confidence.

**Why this priority**: Betting edge calculations depend on accurate uncertainty estimation. If MC uses wrong features, the variance may not represent true match uncertainty.

**Independent Test**: Compare MC spread (σ) with historical outcome variance for similar match situations.

**Acceptance Scenarios**:

1. **Given** MC simulation with full features, **When** calculating standard deviation, **Then** the σ should reflect realistic T20 outcome variance for the match phase
2. **Given** a match in death overs (high variance), **When** MC simulates 12 balls, **Then** the 90% CI width should be appropriately wide (±15-25%)
3. **Given** a match with one team heavily favored, **When** MC runs, **Then** the confidence intervals should not clip unrealistically at 0% or 100%

---

### Edge Cases

- What happens when feature store is not available? (Fallback to simplified features with warning)
- How does system handle very short simulations (1-2 balls remaining)?
- What if terminal state evaluation times out?
- How are all-out scenarios (10 wickets) handled in terminal evaluation?
- What happens when feature store has stale/missing keys? (Venue naming mismatches, team abbreviations, neutral venues → log warning + fallback mode + emit `feature_mode="simplified"`)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When `--use-ml-model` is enabled, venue features used in terminal evaluation MUST be sourced from FeatureContext built from InMemoryFeatureStore (no hardcoded defaults like venue_avg_score=165)
- **FR-002**: When `--use-ml-model` is enabled, team features used in terminal evaluation MUST be sourced from FeatureContext built from InMemoryFeatureStore (no hardcoded defaults like team_win_rate=0.5)
- **FR-003**: MC terminal evaluation MUST call the exact same `predict_proba_calibrated()` function used by the live predictor, applying the full calibration chain: base model → per-over isotonic calibrator → league temperature/platt scaling
- **FR-004**: System MUST complete MC simulation (2000 simulations × 6-12 balls) within 1 second when using full features
- **FR-005**: System MUST log a warning if full feature pipeline is unavailable and falls back to simplified features
- **FR-006**: System MUST preserve the current simplified feature behavior when `--use-ml-model` is NOT specified
- **FR-007**: MC simulation results MUST include a field indicating whether full or simplified features were used
- **FR-008**: Terminal state probabilities MUST match main predictor within ±5% for identical match states (as defined above)
- **FR-009**: FeatureContext MUST be built once per MC call (containing league, venue_key, team_a_key, team_b_key, innings-specific stats) and reused for all terminal states in that call; on key mismatch or missing data, fallback to simplified mode with warning
- **FR-010**: MC terminal evaluation MUST use a batched inference API for evaluating multiple terminal states (no per-state `predict()` loop calls); features must be vectorized/cached to achieve performance targets
- **FR-011**: Each simulation horizon result (e.g., simulation_6ball, simulation_12ball) MUST include its own `feature_mode` indicator, allowing UI to show if different horizons used different feature pipelines (e.g., 6-ball used full, 12-ball fell back to simplified)

### Key Entities

- **TerminalState**: A simulated end-of-horizon match state requiring win probability evaluation (score, wickets, balls, target, team context)
- **FeatureContext**: Cached feature values (venue stats, team ratings) passed to terminal evaluation to avoid repeated lookups
- **TerminalBatch**: Container for batch inference - {states: List[TerminalState], X: np.ndarray (feature matrix), feature_context: FeatureContext, valid_mask: np.ndarray (for early-ended matches)}
- **SimulationResult**: Contains mean_prob, std_prob, p5, p95, timing info, and feature_mode indicator

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: MC simulation mean probability within ±5% of main ML model prediction for identical match state (as defined above)
- **SC-002**: Full-feature MC simulation completes in under 1 second for 2000 simulations × 6 balls
- **SC-003**: Full-feature MC should be ≤2× slower than simplified feature MC (current ~100-200ms → ideally <500ms), with hard cap of 1 second (per SC-002)
- **SC-004**: Feature store lookup overhead per simulation batch under 50ms (amortized across all terminal states)
- **SC-005**: Zero regression in prediction accuracy for non-MC use cases
- **SC-006**: `feature_mode` indicator ("full" or "simplified") MUST be logged to console and included in JSON output for every MC simulation

## Assumptions

- Feature store is loaded and available when `--use-ml-model` is specified
- Team abbreviations in simulation states can be resolved to full team names for feature store lookup
- Venue name in simulation state matches feature store venue keys
- Per-state feature store lookups are the main performance bottleneck (not model inference)
- Caching feature context at simulation start is acceptable (values don't change during simulation)

## Out of Scope

- **Changes to Monte Carlo simulation core** - `engine.py`, `sampler.py`, `state.py` are already correct per validation
- **Real-time ball history tracking** - MC terminal evaluation uses defaults for rolling stats (runs_last_12, boundary_pct_last_18)
- **Per-batsman/bowler stats** - Terminal evaluation uses team-level aggregates, not individual player IDs
- **Adaptive simulation count** - N=2000 is fixed, no convergence-based adjustment
- **GPU acceleration** - Batch model inference uses CPU XGBoost (sufficient for <1s target)
- **Retraining models** - Uses existing `t20_male_v2` model, no retraining required

## Technical Notes

### Current Implementation Status

**Monte Carlo Simulation Core** (ALREADY CORRECT ✅):
- `engine.py`: Proper wicket/state updates, vectorized sampling, terminal detection
- `sampler.py`: Phase-specific wicket probabilities, realistic run distributions
- `state.py`: Clean state transitions, proper MatchState propagation
- **No changes needed to simulation logic**

**Terminal Evaluation** (NEEDS FIX ❌):
- `predict_batch()`: Uses hardcoded defaults (`venue_avg_score=165.0`, `team_wr=0.5`) instead of feature store
- **This is the ONLY bug** causing the 18+ percentage point MC/ML discrepancy

### Two Feature Pipelines

1. **Main `predict()`**: Full features from feature store, ball history, player stats → ~5-10ms per state
2. **Batch `predict_batch()`**: Simplified defaults → ~0.05ms per state

For 2000 terminal states, calling `predict()` in a loop would take 10-20 seconds (unacceptable) vs simplified = ~100ms (current).

### The Surgical Fix

**CRITICAL**: The solution CANNOT call `predict()` per terminal state. It requires a **batched/vectorized feature pipeline** that:

1. **Build FeatureContext once** per MC call (~10ms):
   ```python
   context = FeatureContext(
       venue_avg_score=store.get_venue_avg(venue),      # Real value
       venue_bat_first_wr=store.get_venue_bf_wr(venue), # Real value
       team_a_wr=store.get_team_wr(batting_team),       # Real value
       team_b_wr=store.get_team_wr(bowling_team),       # Real value
       league=league
   )
   ```

2. **Pass context to `predict_batch()`** - Replace hardcoded constants:
   ```python
   venue_avg_score = context.venue_avg_score  # Not 165.0
   team_a_wr = context.team_a_wr              # Not 0.5
   ```

3. **Keep batch processing** - Vectorized feature generation, single model inference call for all 2000 states

4. **Apply calibration chain** - Per-over isotonic → league temperature (same as main predictor)

### Performance Budget

**Current** (with hardcoded defaults):
- Build terminal states: ~20ms
- Feature generation (simplified): ~50ms
- Model inference (batch): ~30ms
- **Total: ~100ms**

**Target** (with FeatureContext):
- Build FeatureContext: ~10ms (one-time feature store lookups)
- Build terminal states: ~20ms
- Feature generation (with context): ~100ms (slightly slower but using real values)
- Model inference (batch): ~30ms
- Calibration: ~10ms
- **Total: ~170ms** (within 500ms target, well under 1s hard cap)

**Key Insight**: Amortizing 5 feature store lookups across 2000 states adds only ~70ms vs using wrong defaults.

### Validation

See [SIMULATION_STATE_VALIDATION.md](SIMULATION_STATE_VALIDATION.md) for comprehensive analysis confirming:
- MC core is correct (wickets fall, features update, no stale state)
- `predict_batch()` hardcoded defaults are the sole root cause
- Proposed FeatureContext solution is surgical and maintains performance
