# Quickstart: Monte Carlo Full Feature Pipeline

**Feature**: 005-mc-full-features  
**For**: Developers implementing or testing the FeatureContext fix  
**Time**: 15-30 minutes to read, 2-4 hours to implement

## TL;DR

**Problem**: MC uses hardcoded `venue_avg_score=165.0, team_wr=0.5` instead of feature store  
**Solution**: Build FeatureContext once per MC call, inject to `predict_batch()`  
**Impact**: +70ms for 18+ percentage point accuracy gain

---

## Quick Implementation Checklist

- [ ] Create `src/bbl_pipeline/simulation/feature_context.py` (dataclass)
- [ ] Add `build_feature_context()` method to `Predictor`
- [ ] Modify `predict_batch()` to accept optional `feature_context` parameter
- [ ] Update `engine.py` to build context before simulation
- [ ] Update `evaluator.py` to pass context to `predict_batch()`
- [ ] Add unit test for FeatureContext validation
- [ ] Add integration test for identical state equality
- [ ] Add regression test for historical match accuracy
- [ ] Update logging to track `feature_mode` ("full" vs "simplified")

---

## Step-by-Step Implementation

### Step 1: Create FeatureContext Dataclass (5 min)

**File**: `src/bbl_pipeline/simulation/feature_context.py` (NEW)

```python
"""Feature context for Monte Carlo terminal evaluation."""

from dataclasses import dataclass

@dataclass
class FeatureContext:
    """
    Cached venue/team features for MC terminal state evaluation.
    
    Built once per MC call to amortize feature store lookup cost
    across 2000 terminal states (~10ms total vs 10,000ms per-state).
    """
    venue_avg_score: float
    venue_bat_first_wr: float
    team_a_wr: float
    team_b_wr: float
    batting_situation_wr: float
    bowling_situation_wr: float
    league: str
    
    def __post_init__(self) -> None:
        """Validate feature values are in expected ranges."""
        if not 100 <= self.venue_avg_score <= 250:
            raise ValueError(
                f"venue_avg_score {self.venue_avg_score} out of range [100, 250]"
            )
        if not 0 <= self.venue_bat_first_wr <= 1:
            raise ValueError(
                f"venue_bat_first_wr {self.venue_bat_first_wr} not in [0, 1]"
            )
        if not 0 <= self.team_a_wr <= 1:
            raise ValueError(f"team_a_wr {self.team_a_wr} not in [0, 1]")
        if not 0 <= self.team_b_wr <= 1:
            raise ValueError(f"team_b_wr {self.team_b_wr} not in [0, 1]")
        if not 0 <= self.batting_situation_wr <= 1:
            raise ValueError(
                f"batting_situation_wr {self.batting_situation_wr} not in [0, 1]"
            )
        if not 0 <= self.bowling_situation_wr <= 1:
            raise ValueError(
                f"bowling_situation_wr {self.bowling_situation_wr} not in [0, 1]"
            )
        if not self.league:
            raise ValueError("league must be non-empty string")
```

### Step 2: Add build_feature_context() to Predictor (15 min)

**File**: `src/bbl_pipeline/inference/predictor.py` (MODIFY)

Add this method after `predict()`:

```python
def build_feature_context(
    self,
    batting_team: str,
    bowling_team: str,
    venue: str,
    league: str,
    innings: int
) -> FeatureContext:
    """
    Build FeatureContext from InMemoryFeatureStore.
    
    Args:
        batting_team: Canonical team name (e.g., "Perth Scorchers")
        bowling_team: Canonical team name (e.g., "Sydney Sixers")
        venue: Venue name (e.g., "Perth Stadium")
        league: League code (e.g., "bbl")
        innings: 1 or 2 (affects situation-specific win rates)
        
    Returns:
        FeatureContext with venue/team stats
        
    Raises:
        KeyError: If team/venue not found in feature store
        ValueError: If innings not in {1, 2}
    """
    from ..simulation.feature_context import FeatureContext
    
    if innings not in (1, 2):
        raise ValueError(f"innings must be 1 or 2, got {innings}")
    
    # Lookup venue stats
    venue_stats = self.feature_store.get_venue_stats(venue)
    
    # Lookup team stats
    team_a_stats = self.feature_store.get_team_stats(batting_team)
    team_b_stats = self.feature_store.get_team_stats(bowling_team)
    
    # Determine situation-specific win rates
    if innings == 1:
        # Batting first, bowling first
        batting_situation_wr = team_a_stats.bat_first_wr
        bowling_situation_wr = team_b_stats.bowl_first_wr
    else:
        # Chasing, defending
        batting_situation_wr = team_a_stats.bowl_first_wr
        bowling_situation_wr = team_b_stats.bat_first_wr
    
    return FeatureContext(
        venue_avg_score=venue_stats.avg_score,
        venue_bat_first_wr=venue_stats.bat_first_wr,
        team_a_wr=team_a_stats.win_rate,
        team_b_wr=team_b_stats.win_rate,
        batting_situation_wr=batting_situation_wr,
        bowling_situation_wr=bowling_situation_wr,
        league=league
    )
```

### Step 3: Modify predict_batch() Signature (30 min)

**File**: `src/bbl_pipeline/inference/predictor.py` (MODIFY)

**Change signature** (line ~702):
```python
def predict_batch(
    self,
    states: list,
    feature_context: Optional["FeatureContext"] = None,  # NEW
    league: str = None
) -> np.ndarray:
```

**Add import** at top of file:
```python
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..simulation.feature_context import FeatureContext
```

**Replace hardcoded defaults** (lines ~860-875):

**BEFORE**:
```python
# Venue stats (use defaults for speed - actual lookups are expensive)
venue_avg_score = 165.0
venue_avg_wickets = 6.5
venue_bat_first_win_rate = 0.45
```

**AFTER**:
```python
# Venue stats - use FeatureContext if available, else defaults
if feature_context:
    venue_avg_score = feature_context.venue_avg_score
    venue_bat_first_wr = feature_context.venue_bat_first_wr
    feature_mode = "full"
    logger.debug("predict_batch using full features from FeatureContext")
else:
    venue_avg_score = 165.0
    venue_bat_first_wr = 0.45
    feature_mode = "simplified"
    logger.warning(
        "predict_batch using simplified features (no FeatureContext provided)"
    )

venue_avg_wickets = 6.5  # Not in context yet
```

**Replace team win rates** (lines ~920-930):

**BEFORE**:
```python
for i, idx in enumerate(non_terminal_indices):
    state = states[idx]
    batting_team_win_rates[i] = getattr(state, 'batting_team_win_rate', 0.5)
    bowling_team_win_rates[i] = getattr(state, 'bowling_team_win_rate', 0.5)
    batting_team_situation_wrs[i] = getattr(state, 'batting_team_situation_wr', batting_team_win_rates[i])
    bowling_team_situation_wrs[i] = getattr(state, 'bowling_team_situation_wr', bowling_team_win_rates[i])
```

**AFTER**:
```python
if feature_context:
    # All states in batch have same teams (same MC call)
    batting_team_win_rates[:] = feature_context.team_a_wr
    bowling_team_win_rates[:] = feature_context.team_b_wr
    batting_team_situation_wrs[:] = feature_context.batting_situation_wr
    bowling_team_situation_wrs[:] = feature_context.bowling_situation_wr
else:
    # Fallback to state attributes or defaults
    for i, idx in enumerate(non_terminal_indices):
        state = states[idx]
        batting_team_win_rates[i] = getattr(state, 'batting_team_win_rate', 0.5)
        bowling_team_win_rates[i] = getattr(state, 'bowling_team_win_rate', 0.5)
        batting_team_situation_wrs[i] = getattr(state, 'batting_team_situation_wr', batting_team_win_rates[i])
        bowling_team_situation_wrs[i] = getattr(state, 'bowling_team_situation_wr', bowling_team_win_rates[i])
```

### Step 4: Update Evaluator (10 min)

**File**: `src/bbl_pipeline/simulation/evaluator.py` (MODIFY)

**Change signature** (line ~304):
```python
def evaluate_batch_with_model(
    self,
    states: List[MatchState],
    feature_context: Optional["FeatureContext"] = None,  # NEW
    apply_temp: bool = False,
) -> np.ndarray:
```

**Add import**:
```python
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .feature_context import FeatureContext
```

**Pass context to predictor** (line ~357):
```python
return self.predictor.predict_batch(
    states,
    feature_context=feature_context,  # NEW
    league=league
)
```

### Step 5: Update Engine (15 min)

**File**: `src/bbl_pipeline/simulation/engine.py` (MODIFY)

**In `simulate_vectorized()`** (around line ~280):

**BEFORE**:
```python
if use_ml_model:
    terminal_probs = evaluator.evaluate_batch_with_model(terminal_states, apply_temp=False)
```

**AFTER**:
```python
if use_ml_model:
    # Build FeatureContext once for all terminal states
    try:
        context = predictor.build_feature_context(
            batting_team=state.batting_team,
            bowling_team=state.bowling_team,
            venue=state.venue,
            league=state.league,
            innings=state.innings
        )
    except KeyError as e:
        logger.warning(
            "Feature context build failed, using defaults",
            error=str(e),
            venue=state.venue,
            teams=f"{state.batting_team} vs {state.bowling_team}"
        )
        context = None
    
    terminal_probs = evaluator.evaluate_batch_with_model(
        terminal_states,
        feature_context=context,  # NEW
        apply_temp=False
    )
```

---

## Testing Checklist

### Unit Tests (30 min)

**File**: `tests/unit/test_feature_context.py` (NEW)

```python
import pytest
from bbl_pipeline.simulation.feature_context import FeatureContext

def test_feature_context_valid():
    """Test valid FeatureContext creation."""
    context = FeatureContext(
        venue_avg_score=150.0,
        venue_bat_first_wr=0.48,
        team_a_wr=0.62,
        team_b_wr=0.38,
        batting_situation_wr=0.65,
        bowling_situation_wr=0.42,
        league="bbl"
    )
    assert context.venue_avg_score == 150.0
    assert context.league == "bbl"

def test_feature_context_invalid_venue_score():
    """Test validation for out-of-range venue score."""
    with pytest.raises(ValueError, match="out of range"):
        FeatureContext(
            venue_avg_score=300.0,  # Too high
            venue_bat_first_wr=0.48,
            team_a_wr=0.62,
            team_b_wr=0.38,
            batting_situation_wr=0.65,
            bowling_situation_wr=0.42,
            league="bbl"
        )

def test_build_feature_context():
    """Test Predictor.build_feature_context()."""
    from bbl_pipeline.inference.predictor import Predictor
    
    predictor = Predictor.load("models/bbl_v12", league="bbl")
    
    context = predictor.build_feature_context(
        batting_team="Perth Scorchers",
        bowling_team="Sydney Sixers",
        venue="Perth Stadium",
        league="bbl",
        innings=1
    )
    
    assert isinstance(context, FeatureContext)
    assert 140 <= context.venue_avg_score <= 160  # Perth range
    assert context.league == "bbl"
```

### Integration Tests (45 min)

**File**: `tests/integration/test_mc_feature_context.py` (NEW)

```python
import pytest
from bbl_pipeline.simulation.state import MatchState
from bbl_pipeline.inference.predictor import Predictor

def test_identical_state_equality():
    """Test FR-008: predict() and predict_batch() produce identical results."""
    predictor = Predictor.load("models/bbl_v12", league="bbl")
    
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
    
    # Batch predictor with context (should match)
    context = predictor.build_feature_context(
        batting_team=state.batting_team,
        bowling_team=state.bowling_team,
        venue=state.venue,
        league=state.league,
        innings=state.innings
    )
    prob_batch = predictor.predict_batch([state], feature_context=context)[0]
    
    # Should be identical (not just ±5%)
    assert abs(prob_main - prob_batch) < 0.001, \
        f"predict()={prob_main:.4f}, predict_batch()={prob_batch:.4f}"

def test_mc_accuracy_with_context():
    """Test SC-001: MC mean within ±5% of ML baseline."""
    from bbl_pipeline.simulation.engine import simulate_vectorized
    
    predictor = Predictor.load("models/bbl_v12", league="bbl")
    
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
    
    # ML baseline
    ml_prob = predictor.predict(state)
    
    # MC with full features
    result = simulate_vectorized(
        state,
        horizon=6,
        n_simulations=2000,
        predictor=predictor
    )
    
    # Should be within ±5%
    assert abs(result.mean_prob - ml_prob) < 0.05, \
        f"ML={ml_prob:.4f}, MC={result.mean_prob:.4f}"
```

---

## Validation

### Before Merge Checklist

- [ ] All unit tests pass
- [ ] Integration test shows <0.001 difference (identical state)
- [ ] MC mean within ±5% of ML baseline (SC-001)
- [ ] Performance <1s for 2000 simulations (SC-002)
- [ ] Slowdown <2× vs simplified (SC-003)
- [ ] `feature_mode` logged correctly ("full" vs "simplified")
- [ ] Backward compatibility verified (existing code works)
- [ ] No regressions in non-MC prediction accuracy

### Manual Testing

```bash
# Test with real match
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "https://www.espncricinfo.com/series/..." \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/t20_male_feature_store_v2 \
  --league bbl \
  --use-ml-model \
  --output-json data/test_output.json

# Check output
cat data/test_output.json | jq '.monte_carlo.simulation_6ball'

# Verify:
# - feature_mode: "full"
# - mean_prob within ±5% of bat_win_prob
# - time_taken_ms < 1000
```

---

## Troubleshooting

### Issue: KeyError when building context

**Symptom**: `KeyError: 'Unknown Team'`

**Solution**: Check team name matches feature store canonical names:
```python
# Check available teams
print(predictor.feature_store.team_stats.keys())

# Use exact name from feature store
context = predictor.build_feature_context(
    batting_team="Perth Scorchers",  # Not "Scorchers" or "Perth"
    ...
)
```

### Issue: MC still shows 18% discrepancy

**Symptom**: MC mean != ML baseline even with FeatureContext

**Debugging**:
```python
# Check if context is actually being used
import logging
logging.basicConfig(level=logging.DEBUG)

# Should see: "predict_batch using full features from FeatureContext"
# NOT: "predict_batch using simplified features"
```

### Issue: Performance >1s

**Symptom**: MC takes 1.5s with FeatureContext

**Solution**: Profile to find bottleneck:
```python
import time

start = time.time()
context = predictor.build_feature_context(...)
print(f"Context build: {(time.time() - start) * 1000:.1f}ms")

start = time.time()
probs = predictor.predict_batch(states, feature_context=context)
print(f"Predict batch: {(time.time() - start) * 1000:.1f}ms")
```

Expected:
- Context build: <15ms
- Predict batch: <180ms

---

## Next Steps

After implementing:
1. Run full test suite: `pytest tests/`
2. Run manual validation on historical match
3. Update model registry with tested change
4. Merge to main
5. Deploy to production

**Estimated Total Time**: 2-4 hours for implementation + testing

---

**Quick Reference**:
- [Spec](spec.md)
- [Validation Report](SIMULATION_STATE_VALIDATION.md)
- [Implementation Guide](IMPLEMENTATION_GUIDE.md)
- [Contracts](contracts/)
