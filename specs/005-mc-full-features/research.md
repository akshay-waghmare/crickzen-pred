# Research: Monte Carlo Full Feature Pipeline

**Feature**: 005-mc-full-features  
**Date**: 2026-01-22  
**Status**: Complete

## Executive Summary

Research phase completed via comprehensive code validation. All unknowns resolved. No additional research needed.

**Key Finding**: Monte Carlo simulation core is production-ready. The ONLY issue is `predict_batch()` using hardcoded defaults instead of feature store lookups.

---

## Research Questions & Answers

### Q1: Do wickets actually fall in Monte Carlo simulation?

**Answer**: YES ✅

**Evidence**:
```python
# src/bbl_pipeline/simulation/sampler.py (lines 159-164)
WICKET_PROB = {
    'powerplay': 0.05,    # 5% per ball
    'middle': 0.04,       # 4% per ball  
    'death': 0.055,       # 5.5% per ball
}

# src/bbl_pipeline/simulation/engine.py (lines 244-247)
wickets[active_mask] += wicket_arr.astype(np.int32)
is_over |= (wickets >= 10) | (balls_remaining <= 0)
```

**Rationale**: Sampler uses empirically-derived wicket probabilities from 1.89M T20 balls. Wickets are sampled stochastically and properly increment state.

**Alternatives Considered**: 
- Fixed wickets per over → Rejected (unrealistic)
- Player-specific wicket probabilities → Out of scope (team-level abstraction sufficient)

---

### Q2: Are state-dependent features recomputed for each simulated state?

**Answer**: YES ✅

**Evidence**:
```python
# src/bbl_pipeline/inference/predictor.py (lines 820-840)
# All features derive from MatchState arguments:
current_run_rate = np.where(overs_bowled > 0, nt_scores / overs_bowled, 0.0)
runs_required = np.where(nt_innings == 2, nt_targets - nt_scores, 0.0)
required_run_rate = np.where(
    (nt_innings == 2) & (overs_remaining > 0),
    runs_required / overs_remaining,
    0.0
)
```

**Rationale**: All derived features (RRR, CRR, phase, resource%, expected_final_score) are vectorized computations from state arrays. No stale values.

**Alternatives Considered**: 
- Cache derived features → Rejected (would freeze values incorrectly)
- Pre-compute feature tensors → Rejected (states unknown until simulation)

---

### Q3: What is the root cause of the 18+ percentage point discrepancy?

**Answer**: Hardcoded defaults in `predict_batch()` ❌

**Evidence**:
```python
# src/bbl_pipeline/inference/predictor.py (lines 860-875)
# Venue stats (use defaults for speed - actual lookups are expensive)
venue_avg_score = 165.0                    # ❌ Generic default
venue_avg_wickets = 6.5                    # ❌ Generic default
venue_bat_first_win_rate = 0.45            # ❌ Generic default

# Team stats - extract from states if available, otherwise use defaults
batting_team_win_rates[i] = getattr(state, 'batting_team_win_rate', 0.5)  # ❌ Fallback
```

**Impact Analysis**:
- Perth Stadium actual avg: ~150 runs
- MC uses: 165 runs (15 runs high)
- This affects `projected_score`, `score_vs_par`, and final probability
- Result: 31.2% (ML with real features) vs 49.6% (MC with defaults)

**Rationale for Original Design**: Performance optimization - avoiding 2000 feature store lookups (each ~5ms) would add 10 seconds.

**Why This Is Wrong**: The comment is correct that *per-state* lookups are expensive, but *per-MC-call* lookups (once for 2000 states) are trivial (~10ms).

**Alternatives Considered**:
- Add venue/team stats to MatchState → Rejected (violates separation of concerns)
- Pre-populate all states with features → Rejected (memory overhead, tight coupling)
- ✅ **Selected**: FeatureContext (build once, inject to batch predictor)

---

### Q4: What is the performance budget?

**Answer**: Target ~170ms (current 100ms + 70ms overhead)

**Breakdown**:
| Component | Current | Target | Delta |
|-----------|---------|--------|-------|
| Build FeatureContext | N/A | ~10ms | +10ms |
| Build terminal states | ~20ms | ~20ms | 0ms |
| Feature generation | ~50ms | ~100ms | +50ms |
| Model inference | ~30ms | ~30ms | 0ms |
| Calibration | N/A | ~10ms | +10ms |
| **TOTAL** | **~100ms** | **~170ms** | **+70ms** |

**Rationale**: 
- FeatureContext: 5 feature store lookups × 2ms = 10ms
- Slightly slower feature generation with real context (conditional logic, more variance)
- Calibration already exists (just not timed separately)

**Validation**: Target is well within 1s hard cap (SC-002) and <2× slowdown requirement (SC-003: 170/100 = 1.7×).

**Alternatives Considered**:
- Cache feature store globally → Rejected (already done, InMemoryFeatureStore is cached)
- Use subset of features → Considered (may implement later if needed)
- GPU acceleration → Out of scope (overkill for 170ms)

---

### Q5: How is InMemoryFeatureStore structured?

**Answer**: Parquet-backed in-memory cache with canonical team/venue names

**Structure**:
```python
InMemoryFeatureStore:
    venue_stats: Dict[str, VenueStats]
        - avg_score: float
        - bat_first_wr: float
        - avg_wickets: float
    team_stats: Dict[str, TeamStats]
        - win_rate: float
        - bat_first_wr: float
        - bowl_first_wr: float
    player_stats: Dict[str, PlayerStats]
        - rolling_avg, rolling_sr, etc.
```

**Loading**: 
- Loaded once when Predictor initializes
- Parquet files in `data/<league>_feature_store_v2/`
- ~100ms initial load, then instant lookups (in-memory dict)

**Key Methods**:
```python
store.get_venue_stats(venue: str) -> VenueStats
store.get_team_stats(team: str, innings: int) -> TeamStats
```

**Rationale**: Already optimized for speed. Adding 5 lookups per MC call is negligible.

**Alternatives Considered**:
- SQL database → Rejected (overkill, slower)
- JSON files → Rejected (slower parsing)
- ✅ **Current design is optimal** for this use case

---

## Technology Decisions

### Decision 1: Use FeatureContext Dataclass

**Chosen**: `@dataclass` with typed fields

**Rationale**:
- Type-safe (helps catch bugs at dev time)
- Self-documenting (explicit field names)
- Minimal overhead (compiled to fast attribute access)
- Compatible with existing codebase style

**Alternatives Rejected**:
- `Dict[str, Any]` → Not type-safe, error-prone
- `NamedTuple` → Immutable (fine), but less flexible for future extensions
- Custom class with `__init__` → More boilerplate than dataclass

**Implementation**:
```python
@dataclass
class FeatureContext:
    """Cached venue/team features for MC terminal evaluation."""
    venue_avg_score: float
    venue_bat_first_wr: float
    team_a_wr: float
    team_b_wr: float
    batting_situation_wr: float
    bowling_situation_wr: float
    league: str
```

---

### Decision 2: Build FeatureContext Once Per MC Call

**Chosen**: Call `build_feature_context()` in `engine.py` before simulation loop

**Rationale**:
- Amortizes cost across 2000 terminal states
- Context doesn't change during simulation (venue/teams constant)
- Clean separation: engine owns simulation, predictor owns features

**Alternatives Rejected**:
- Build per-state → 10,000ms (unacceptable)
- Build globally once → Stale data when match state changes
- Pass feature store directly → Tight coupling, violates encapsulation

**Implementation**:
```python
# In engine.py::simulate_vectorized()
if use_ml_model and predictor:
    context = predictor.build_feature_context(
        batting_team=state.batting_team,
        bowling_team=state.bowling_team,
        venue=state.venue,
        league=state.league,
        innings=state.innings
    )
    probs = evaluator.evaluate_batch_with_model(terminal_states, context)
```

---

### Decision 3: Make FeatureContext Optional in predict_batch()

**Chosen**: `feature_context: Optional[FeatureContext] = None`

**Rationale**:
- Backward compatible (existing code works unchanged)
- Graceful fallback (logs warning if context missing)
- Explicit opt-in for MC use case

**Alternatives Rejected**:
- Required parameter → Breaking change for non-MC callers
- Use sentinel value → Less clear than Optional
- Auto-build if missing → Hidden side effects, tight coupling

**Implementation**:
```python
def predict_batch(
    self,
    states: list,
    feature_context: Optional[FeatureContext] = None,
    league: str = None
) -> np.ndarray:
    if feature_context:
        venue_avg_score = feature_context.venue_avg_score
        feature_mode = "full"
    else:
        venue_avg_score = 165.0
        feature_mode = "simplified"
        logger.warning("predict_batch using simplified features (no context)")
```

---

### Decision 4: Pass FeatureContext Through Evaluator

**Chosen**: `evaluator.evaluate_batch_with_model(states, context)` → `predictor.predict_batch(states, context)`

**Rationale**:
- Evaluator already owns predictor call
- Clean layering: engine → evaluator → predictor
- Avoids engine having direct predictor dependency

**Alternatives Rejected**:
- Engine calls predictor directly → Tight coupling, duplicates logic
- Evaluator builds context → Violates single responsibility (predictor owns features)
- Global context injection → Hidden state, hard to test

**Implementation**:
```python
# evaluator.py::evaluate_batch_with_model()
def evaluate_batch_with_model(
    self,
    states: List[MatchState],
    feature_context: Optional[FeatureContext] = None,
    apply_temp: bool = False,
) -> np.ndarray:
    return self.predictor.predict_batch(states, feature_context=feature_context)
```

---

### Decision 5: No Changes to MC Simulation Core

**Chosen**: Zero modifications to `engine.py` simulation loop, `sampler.py`, or `state.py`

**Rationale**:
- Validation proved these components are production-ready
- Risk mitigation: don't fix what isn't broken
- Surgical fix principle: modify only the faulty component

**Validation Evidence**:
- Wickets fall correctly ✅
- State transitions correct ✅
- No frozen features ✅
- All-out detection works ✅

**Alternatives Rejected**:
- Refactor MC for "cleanliness" → Unnecessary risk
- Add state validation → Already validated externally
- Optimize sampler → Not a performance bottleneck

---

## Implementation Constraints

### Performance Constraints

- **Hard Cap**: 1 second for 2000 simulations × 6 balls (SC-002)
- **Target**: ~170ms (within 500ms ideal, 1.7× slowdown vs current 100ms)
- **Budget Breakdown**: See Q4 above

### Backward Compatibility

- `predict_batch()` must work without FeatureContext (existing callers)
- Fallback to defaults must log warning (observability)
- No breaking changes to `MatchState`, `SimulationResult`, or public APIs

### Testing Requirements

1. **Unit Test**: `test_feature_context.py`
   - FeatureContext builds correctly from feature store
   - Handles missing venue/team keys gracefully
   - Returns expected structure

2. **Integration Test**: `test_mc_feature_context.py`
   - Identical state equality: `predict()` vs `predict_batch([state], context)` < 0.001
   - MC mean probability within ±5% of ML baseline
   - Performance: <1s for 2000 simulations

3. **Regression Test**:
   - Historical match state (e.g., BBL Perth vs Sydney over 10.3)
   - Compare: (a) ML baseline, (b) MC with defaults (current), (c) MC with context (fixed)
   - Verify (c) within ±5% of (a), (b) shows 15-20% drift

---

## Open Questions (Resolved)

**None** - All research questions answered via validation.

---

## Next Steps (Phase 1)

1. Generate `data-model.md` - Document FeatureContext schema
2. Generate `contracts/` - API contracts for modified methods
3. Generate `quickstart.md` - Developer guide for using FeatureContext
4. Update agent context with new entities

---

**Research Complete**: 2026-01-22  
**Next Phase**: Design (data-model.md, contracts, quickstart)
