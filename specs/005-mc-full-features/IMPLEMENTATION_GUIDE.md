# Feature 005: Monte Carlo Full Feature Pipeline - Implementation Guide

**Status**: Ready for Implementation  
**Branch**: `005-mc-full-features`  
**Validated**: 2026-01-22

## Quick Reference

- **Spec**: [spec.md](spec.md)
- **Validation Report**: [SIMULATION_STATE_VALIDATION.md](SIMULATION_STATE_VALIDATION.md)
- **Checklist**: [checklists/requirements.md](checklists/requirements.md)

## The Problem (One Sentence)

Monte Carlo generates realistic future states but evaluates them using wrong venue/team features (hardcoded defaults instead of feature store), causing 18+ percentage point drift.

## The Solution (One Sentence)

Inject real feature-store values into `predict_batch()` once per MC call via FeatureContext, instead of using hardcoded defaults.

## What's NOT Being Changed ✅

**Monte Carlo simulation core is CORRECT** - validated 2026-01-22:
- `engine.py` - Wicket updates, state transitions, terminal detection
- `sampler.py` - Phase-specific wicket probabilities, run distributions
- `state.py` - MatchState dataclass, apply_outcome logic

**No changes needed to:**
- Simulation loop
- Wicket sampling
- State propagation
- All-out detection

## What IS Being Changed 🔧

**Single file: `src/bbl_pipeline/inference/predictor.py`**

Replace this:
```python
# Line 860-863
venue_avg_score = 165.0                    # ❌ Hardcoded
venue_bat_first_win_rate = 0.45            # ❌ Hardcoded
batting_team_win_rates[i] = getattr(state, 'batting_team_win_rate', 0.5)  # ❌ Fallback
```

With this:
```python
if feature_context:
    venue_avg_score = feature_context.venue_avg_score        # ✅ Real value
    venue_bat_first_wr = feature_context.venue_bat_first_wr  # ✅ Real value
    team_a_wr = feature_context.team_a_wr                    # ✅ Real value
else:
    venue_avg_score = 165.0  # Fallback + warning
```

**Supporting changes:**
1. Add `FeatureContext` dataclass (new file: `src/bbl_pipeline/simulation/feature_context.py`)
2. Add `build_feature_context()` method to `Predictor`
3. Update `engine.py` to build context once per MC call
4. Update `evaluator.py` to pass context to `predict_batch()`

## Implementation Steps

### Step 1: Add FeatureContext Dataclass
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

### Step 2: Add Builder Method to Predictor
```python
def build_feature_context(
    self,
    batting_team: str,
    bowling_team: str,
    venue: str,
    league: str,
    innings: int
) -> FeatureContext:
    """Build feature context from feature store (one-time lookup)."""
    # Use existing InMemoryFeatureStore methods
    venue_stats = self.feature_store.get_venue_stats(venue)
    team_a_stats = self.feature_store.get_team_stats(batting_team, innings)
    team_b_stats = self.feature_store.get_team_stats(bowling_team, innings)
    
    return FeatureContext(...)
```

### Step 3: Update predict_batch() Signature
```python
def predict_batch(
    self,
    states: list,
    feature_context: Optional[FeatureContext] = None,  # NEW
    league: str = None
) -> np.ndarray:
```

### Step 4: Update engine.py to Build Context
```python
# In simulate_vectorized()
if use_ml_model:
    context = predictor.build_feature_context(
        batting_team=state.batting_team,
        bowling_team=state.bowling_team,
        venue=state.venue,
        league=state.league,
        innings=state.innings
    )
    terminal_probs = evaluator.evaluate_batch_with_model(
        terminal_states,
        feature_context=context,  # NEW
        apply_temp=False
    )
```

### Step 5: Add Validation Test
```python
def test_identical_state_equality():
    """FR-008: Terminal state probs must match main predictor within ±5%."""
    state = MatchState(...)
    
    # Main predictor
    prob_main = predictor.predict(state)
    
    # MC terminal eval with context
    context = predictor.build_feature_context(...)
    prob_batch = predictor.predict_batch([state], feature_context=context)[0]
    
    # Should be identical (not just ±5%)
    assert abs(prob_main - prob_batch) < 0.001
```

## Performance Budget

| Component | Time | Notes |
|-----------|------|-------|
| Build FeatureContext | ~10ms | One-time per MC call |
| Build terminal states | ~20ms | Same as current |
| Feature generation | ~100ms | Slightly slower (real context) |
| Model inference | ~30ms | Same as current |
| Calibration | ~10ms | Same as current |
| **TOTAL** | **~170ms** | Within 500ms target ✅ |

**Current**: ~100ms (with wrong features)  
**Target**: ~170ms (with correct features)  
**Hard cap**: 1000ms

## Success Criteria

- ✅ MC mean probability within ±5% of ML baseline (SC-001)
- ✅ Total time <1 second for 2000 simulations (SC-002)
- ✅ Less than 2× slowdown vs simplified (SC-003: 170ms vs 100ms = 1.7×)
- ✅ `feature_mode` logged and in JSON output (SC-006)

## Files to Modify

1. **NEW**: `src/bbl_pipeline/simulation/feature_context.py` - FeatureContext dataclass
2. **MODIFY**: `src/bbl_pipeline/inference/predictor.py` - Add `build_feature_context()`, update `predict_batch()`
3. **MODIFY**: `src/bbl_pipeline/simulation/engine.py` - Build context, pass to evaluator
4. **MODIFY**: `src/bbl_pipeline/simulation/evaluator.py` - Pass context to `predict_batch()`
5. **NEW**: `tests/test_feature_context.py` - Validation tests

## Testing Strategy

1. **Unit test**: FeatureContext builds correctly from feature store
2. **Integration test**: Identical state equality (main vs batch with context)
3. **Regression test**: Historical match state shows ±5% accuracy
4. **Performance test**: 2000 simulations complete in <1s

## Rollout Plan

1. Merge to `005-mc-full-features` branch
2. Run regression tests on BBL/SA20/ILT20 historical data
3. Verify ±5% accuracy on 10+ known match states
4. Merge to main after validation
5. Update model registry with tested change

## Risk Assessment

- **Low risk**: Surgical change to one function, backward compatible
- **Fallback**: If context is None, uses current defaults (no regression)
- **Validation**: Multiple tests ensure correctness before merge
- **Performance**: 70ms slowdown acceptable for 18+ percentage point accuracy gain

---

**Ready for `/speckit.plan`** to generate detailed implementation tasks.
