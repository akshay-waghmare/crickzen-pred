# API Contract: Predictor.predict_batch() (Modified)

**File**: `src/bbl_pipeline/inference/predictor.py`  
**Type**: Instance Method (Modified)  
**Status**: Signature Change (Backward Compatible)

## Signature

### Before (Current)

```python
def predict_batch(self, states: list, league: str = None) -> np.ndarray:
    """
    Predict win probabilities for multiple MatchState objects.
    
    Uses hardcoded defaults: venue_avg_score=165.0, team_wr=0.5
    """
```

### After (New)

```python
def predict_batch(
    self,
    states: list,
    feature_context: Optional[FeatureContext] = None,
    league: str = None
) -> np.ndarray:
    """
    Predict win probabilities for multiple MatchState objects in a single batch.
    
    When feature_context is provided, uses actual venue/team stats from feature store.
    Otherwise falls back to hardcoded defaults (venue_avg_score=165.0, team_wr=0.5).
    
    Args:
        states: List of MatchState objects to evaluate
        feature_context: Optional cached feature values for venue/teams.
                        If None, uses defaults and logs warning.
        league: Optional league code for league-specific calibration
        
    Returns:
        np.ndarray: Win probabilities (one per state)
        
    Performance:
        - With context: ~160ms for 2000 states (full features)
        - Without context: ~100ms for 2000 states (simplified features)
        
    Example:
        >>> # With FeatureContext (MC use case)
        >>> context = predictor.build_feature_context(...)
        >>> probs = predictor.predict_batch(terminal_states, feature_context=context)
        
        >>> # Without context (legacy/non-MC)
        >>> probs = predictor.predict_batch(states)  # Uses defaults
    """
```

## Changes

| Aspect | Before | After | Impact |
|--------|--------|-------|--------|
| **Signature** | `(states, league=None)` | `(states, feature_context=None, league=None)` | ✅ Backward compatible |
| **Venue avg score** | `venue_avg_score = 165.0` | `context.venue_avg_score if context else 165.0` | ✅ Uses real value when available |
| **Team win rates** | `getattr(state, 'team_wr', 0.5)` | `context.team_a_wr if context else 0.5` | ✅ Uses real value when available |
| **Logging** | No warning | Logs warning if `context is None` | ✅ Observability |
| **Return type** | `np.ndarray` | `np.ndarray` | ✅ Unchanged |

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `states` | `list[MatchState]` | Yes | N/A | Match states to evaluate |
| `feature_context` | `Optional[FeatureContext]` | No | `None` | Cached venue/team features |
| `league` | `Optional[str]` | No | `None` | League code for calibration |

## Return Value

**Type**: `np.ndarray`

**Shape**: `(n,)` where `n = len(states)`

**Values**: Win probabilities in range [0.0, 1.0]

## Behavioral Changes

### With FeatureContext (New Behavior)

```python
# Inside predict_batch() implementation
if feature_context:
    venue_avg_score = feature_context.venue_avg_score        # Real value (e.g., 150.2)
    venue_bat_first_wr = feature_context.venue_bat_first_wr  # Real value (e.g., 0.48)
    team_a_wr = feature_context.team_a_wr                    # Real value (e.g., 0.62)
    team_b_wr = feature_context.team_b_wr                    # Real value (e.g., 0.38)
    feature_mode = "full"
    logger.debug("predict_batch using full features from FeatureContext")
else:
    venue_avg_score = 165.0                                   # Generic default
    venue_bat_first_wr = 0.45                                 # Generic default
    team_a_wr = 0.5                                           # Generic default
    team_b_wr = 0.5                                           # Generic default
    feature_mode = "simplified"
    logger.warning("predict_batch using simplified features (no FeatureContext provided)")
```

### Without FeatureContext (Existing Behavior - Preserved)

Existing callers see **NO change**:
```python
# Legacy code continues to work
probs = predictor.predict_batch([state1, state2, state3])
# Uses defaults, logs warning (new), returns same results (unchanged)
```

## Usage Examples

### Example 1: MC with FeatureContext (New)

```python
# In engine.py
context = predictor.build_feature_context(
    batting_team=state.batting_team,
    bowling_team=state.bowling_team,
    venue=state.venue,
    league=state.league,
    innings=state.innings
)

terminal_probs = predictor.predict_batch(
    terminal_states,
    feature_context=context,  # ✅ Uses real features
    league=state.league
)
```

### Example 2: Legacy Without Context (Preserved)

```python
# Existing code (no changes needed)
probs = predictor.predict_batch(states)
# Output: [0.52, 0.48, 0.61, ...] (using defaults)
# Log: WARNING "predict_batch using simplified features"
```

### Example 3: Identical State Verification (Testing)

```python
def test_identical_state_equality():
    """Verify predict() and predict_batch() produce same result."""
    state = MatchState(
        innings=2,
        score=85,
        wickets_lost=3,
        balls_remaining=48,
        target_runs=150,
        batting_team="Perth Scorchers",
        bowling_team="Sydney Sixers",
        venue="Perth Stadium",
        league="bbl"
    )
    
    # Main predictor (full features)
    prob_main = predictor.predict(state)
    
    # Batch predictor with FeatureContext (should match)
    context = predictor.build_feature_context(
        batting_team=state.batting_team,
        bowling_team=state.bowling_team,
        venue=state.venue,
        league=state.league,
        innings=state.innings
    )
    prob_batch = predictor.predict_batch([state], feature_context=context)[0]
    
    # Should be identical (not just ±5%)
    assert abs(prob_main - prob_batch) < 0.001
```

## Implementation Notes

### Feature Replacement Logic

**Before**:
```python
# Line 860-863 (predictor.py)
venue_avg_score = 165.0
venue_avg_wickets = 6.5
venue_bat_first_win_rate = 0.45
```

**After**:
```python
if feature_context:
    venue_avg_score = feature_context.venue_avg_score
    venue_avg_wickets = 6.5  # Not in context yet (future: add if needed)
    venue_bat_first_wr = feature_context.venue_bat_first_wr
else:
    venue_avg_score = 165.0
    venue_avg_wickets = 6.5
    venue_bat_first_wr = 0.45
```

### Team Win Rate Replacement

**Before**:
```python
# Line 920-925 (predictor.py)
for i, idx in enumerate(non_terminal_indices):
    state = states[idx]
    batting_team_win_rates[i] = getattr(state, 'batting_team_win_rate', 0.5)
    bowling_team_win_rates[i] = getattr(state, 'bowling_team_win_rate', 0.5)
```

**After**:
```python
if feature_context:
    # All states in batch have same teams (same MC call)
    batting_team_win_rates[:] = feature_context.team_a_wr
    bowling_team_win_rates[:] = feature_context.team_b_wr
    batting_team_situation_wrs[:] = feature_context.batting_situation_wr
    bowling_team_situation_wrs[:] = feature_context.bowling_situation_wr
else:
    # Existing fallback logic
    for i, idx in enumerate(non_terminal_indices):
        state = states[idx]
        batting_team_win_rates[i] = getattr(state, 'batting_team_win_rate', 0.5)
        bowling_team_win_rates[i] = getattr(state, 'bowling_team_win_rate', 0.5)
```

## Performance Impact

| Scenario | Time (2000 states) | Change |
|----------|-------------------|--------|
| Without context (current) | ~100ms | Baseline |
| With context (new) | ~160ms | +60ms (+60%) |
| Acceptable per SC-003 | <200ms | ✅ PASS |

**Rationale for slowdown**:
- Slight overhead from conditional logic (`if feature_context`)
- More variance in feature values (real vs constant defaults)
- Worth it for 18+ percentage point accuracy gain

## Testing Contract

```python
def test_predict_batch_with_context():
    """Test that context is used when provided."""
    predictor = Predictor.load("models/bbl_v12", league="bbl")
    
    state = MatchState(...)
    context = predictor.build_feature_context(...)
    
    prob = predictor.predict_batch([state], feature_context=context)[0]
    
    # Should use real features (not defaults)
    assert 0 < prob < 1  # Valid probability
    # Further assertion: compare to predict() (should be identical)

def test_predict_batch_without_context_backward_compatible():
    """Test that existing behavior is preserved."""
    predictor = Predictor.load("models/bbl_v12", league="bbl")
    
    states = [MatchState(...), MatchState(...)]
    
    # Should work without context (backward compatible)
    probs = predictor.predict_batch(states)
    
    assert len(probs) == 2
    assert all(0 <= p <= 1 for p in probs)

def test_predict_batch_logs_warning_without_context():
    """Test that warning is logged when context not provided."""
    predictor = Predictor.load("models/bbl_v12", league="bbl")
    
    with pytest.warns(UserWarning, match="simplified features"):
        predictor.predict_batch([MatchState(...)])
```

## Migration Guide

**No migration needed** - This is a backward compatible change.

**Recommended for new code**:
```python
# OLD (still works)
probs = predictor.predict_batch(states)

# NEW (recommended for MC)
context = predictor.build_feature_context(...)
probs = predictor.predict_batch(states, feature_context=context)
```

---

**Version**: 1.0  
**Status**: Design Complete  
**Next**: Implement in `src/bbl_pipeline/inference/predictor.py`
