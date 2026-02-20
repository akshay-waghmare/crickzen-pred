# Data Model: Monte Carlo Full Feature Pipeline

**Feature**: 005-mc-full-features  
**Date**: 2026-01-22  
**Status**: Design Complete

## Overview

This feature introduces ONE new entity (`FeatureContext`) and modifies signatures of THREE existing methods. No database schema changes, no new storage requirements.

---

## Entity: FeatureContext

**Purpose**: Cache venue/team statistics fetched from InMemoryFeatureStore once per Monte Carlo call, amortizing lookup cost across 2000 terminal state evaluations.

**Lifecycle**: Created in `engine.py` before MC simulation, passed to `evaluator.py`, consumed by `predictor.py::predict_batch()`.

**Schema**:

```python
@dataclass
class FeatureContext:
    """
    Cached feature values for Monte Carlo terminal state evaluation.
    
    Built once per MC call to avoid repeated feature store lookups.
    Amortizes ~10ms cost across 2000 terminal states.
    """
    venue_avg_score: float              # Average score at venue (e.g., 150.0 for Perth Stadium)
    venue_bat_first_wr: float           # Bat-first win rate at venue (e.g., 0.48)
    team_a_wr: float                    # Batting team overall win rate (e.g., 0.62 for Perth Scorchers)
    team_b_wr: float                    # Bowling team overall win rate (e.g., 0.38)
    batting_situation_wr: float         # Batting team situation-specific win rate (e.g., 0.65 when batting first)
    bowling_situation_wr: float         # Bowling team situation-specific win rate (e.g., 0.42 when bowling first)
    league: str                         # League code (e.g., "bbl", "sa20", "ilt20")
    
    def __post_init__(self):
        """Validate feature values are in expected ranges."""
        if not 100 <= self.venue_avg_score <= 250:
            raise ValueError(f"venue_avg_score {self.venue_avg_score} out of range [100, 250]")
        if not 0 <= self.venue_bat_first_wr <= 1:
            raise ValueError(f"venue_bat_first_wr {self.venue_bat_first_wr} not in [0, 1]")
        # Similar validation for all probability fields...
```

**Validation Rules**:
- `venue_avg_score`: 100-250 (reasonable T20 total range)
- All win rates: 0.0-1.0 (probabilities)
- `league`: Non-empty string

**Source of Truth**: `InMemoryFeatureStore` (Parquet-backed in-memory cache)

**Immutability**: Frozen after creation (dataclass can be made frozen if needed)

---

## Modified Entities

### 1. Predictor.predict_batch()

**Before**:
```python
def predict_batch(self, states: list, league: str = None) -> np.ndarray:
    """Uses hardcoded defaults: venue_avg_score=165.0, team_wr=0.5"""
```

**After**:
```python
def predict_batch(
    self,
    states: list,
    feature_context: Optional[FeatureContext] = None,
    league: str = None
) -> np.ndarray:
    """
    Uses FeatureContext if provided, falls back to defaults with warning.
    """
```

**Changes**:
- Add `feature_context` parameter (optional, backward compatible)
- Replace hardcoded constants with `context.venue_avg_score`, `context.team_a_wr`, etc.
- Log warning if `feature_context is None`
- Track `feature_mode = "full"` vs `"simplified"`

**Impact**: Backward compatible (existing callers work unchanged)

---

### 2. TerminalStateEvaluator.evaluate_batch_with_model()

**Before**:
```python
def evaluate_batch_with_model(
    self,
    states: List[MatchState],
    apply_temp: bool = False,
) -> np.ndarray:
```

**After**:
```python
def evaluate_batch_with_model(
    self,
    states: List[MatchState],
    feature_context: Optional[FeatureContext] = None,
    apply_temp: bool = False,
) -> np.ndarray:
    """
    Pass feature_context to predictor.predict_batch().
    """
```

**Changes**:
- Add `feature_context` parameter (pass-through)
- Forward to `predictor.predict_batch(states, feature_context)`

**Impact**: Minimal (evaluator is internal, only called by engine)

---

### 3. Predictor.build_feature_context() (NEW METHOD)

**Signature**:
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
        
    Performance:
        ~10ms (5 feature store lookups × 2ms each)
    """
```

**Implementation**:
```python
def build_feature_context(self, batting_team, bowling_team, venue, league, innings):
    venue_stats = self.feature_store.get_venue_stats(venue)
    team_a_stats = self.feature_store.get_team_stats(batting_team)
    team_b_stats = self.feature_store.get_team_stats(bowling_team)
    
    batting_situation_wr = team_a_stats.bat_first_wr if innings == 1 else team_a_stats.bowl_first_wr
    bowling_situation_wr = team_b_stats.bowl_first_wr if innings == 1 else team_b_stats.bat_first_wr
    
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

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. User runs: bbl-pipeline crex --use-ml-model --league sa20   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. crex_live_predictor.py creates MatchState                    │
│    state = MatchState(batting_team="PC", bowling_team="SEC",    │
│                       venue="Newlands", league="sa20")          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. engine.py::simulate_vectorized() called                     │
│    if use_ml_model:                                             │
│        context = predictor.build_feature_context(...)  ◄─ NEW  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. predictor.build_feature_context()                            │
│    venue_stats = feature_store.get_venue_stats("Newlands")     │
│    team_a = feature_store.get_team_stats("PC")                 │
│    team_b = feature_store.get_team_stats("SEC")                │
│    return FeatureContext(venue_avg_score=148.5, ...)           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. engine.py runs MC simulation (2000 simulations × 6 balls)   │
│    Creates 2000 terminal states (each with updated wickets)    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. evaluator.evaluate_batch_with_model(states, context)        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. predictor.predict_batch(states, feature_context=context)    │
│    venue_avg_score = context.venue_avg_score  (148.5, not 165) │
│    team_a_wr = context.team_a_wr              (0.58, not 0.5)  │
│    [Generate 2000-row feature matrix with real context]        │
│    [Run XGBoost batch inference: 2000 → 2000 probabilities]    │
│    [Apply calibration chain: per-over + league]                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. engine.py computes statistics from 2000 probabilities       │
│    mean_prob, std_prob, p5, p95                                │
│    return SimulationResult(feature_mode="full")                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Validation & Constraints

### Field Constraints

| Field | Type | Range | Example | Fallback |
|-------|------|-------|---------|----------|
| `venue_avg_score` | float | 100-250 | 150.5 | 165.0 |
| `venue_bat_first_wr` | float | 0.0-1.0 | 0.48 | 0.45 |
| `team_a_wr` | float | 0.0-1.0 | 0.62 | 0.5 |
| `team_b_wr` | float | 0.0-1.0 | 0.38 | 0.5 |
| `batting_situation_wr` | float | 0.0-1.0 | 0.65 | 0.5 |
| `bowling_situation_wr` | float | 0.0-1.0 | 0.42 | 0.5 |
| `league` | str | non-empty | "sa20" | N/A |

### Missing Data Handling

**Scenario 1**: Venue not found in feature store
```python
try:
    venue_stats = self.feature_store.get_venue_stats(venue)
except KeyError:
    logger.warning(f"Venue {venue} not in feature store, using defaults")
    venue_stats = VenueStats(avg_score=165.0, bat_first_wr=0.45)
```

**Scenario 2**: Team not found
```python
try:
    team_stats = self.feature_store.get_team_stats(team)
except KeyError:
    logger.warning(f"Team {team} not in feature store, using defaults")
    team_stats = TeamStats(win_rate=0.5, bat_first_wr=0.5, bowl_first_wr=0.5)
```

**Scenario 3**: FeatureContext not provided to predict_batch()
```python
if feature_context is None:
    logger.warning("predict_batch() called without FeatureContext, using defaults")
    venue_avg_score = 165.0
    team_a_wr = 0.5
```

---

## State Transitions

FeatureContext has no state transitions (immutable value object).

**Lifecycle**:
1. **Created**: `predictor.build_feature_context()` in `engine.py`
2. **Passed**: Through `evaluator.evaluate_batch_with_model()`
3. **Consumed**: In `predictor.predict_batch()` to replace hardcoded defaults
4. **Discarded**: After MC call completes

**No persistence** - Built fresh for each MC simulation.

---

## Relationships

```
┌──────────────────────┐
│ InMemoryFeatureStore │ (existing, no changes)
│ ────────────────────  │
│ venue_stats: Dict    │
│ team_stats: Dict     │
│ player_stats: Dict   │
└──────────┬───────────┘
           │ lookups (5× per MC call)
           │
           ▼
┌──────────────────────┐
│ FeatureContext       │ (NEW)
│ ────────────────────  │
│ venue_avg_score      │
│ venue_bat_first_wr   │
│ team_a_wr            │
│ team_b_wr            │
│ batting_situation_wr │
│ bowling_situation_wr │
│ league               │
└──────────┬───────────┘
           │ passed to
           │
           ▼
┌──────────────────────┐
│ Predictor            │ (modified)
│ ────────────────────  │
│ predict_batch()      │ ◄─ NEW: feature_context param
│ build_feature_context() │ ◄─ NEW: method
└──────────────────────┘
```

---

## Performance Characteristics

| Operation | Time | Frequency | Total Impact |
|-----------|------|-----------|--------------|
| Build FeatureContext | ~10ms | Once per MC call | +10ms |
| Pass context (reference) | ~0.001ms | 1× (evaluator → predictor) | Negligible |
| Use context in predict_batch | ~0.04ms | Per state (2000×) | +80ms |

**Total**: ~90ms overhead vs 100ms current = 190ms (within 500ms target)

**Note**: Original estimate was 170ms. Adding 20ms margin for safety.

---

## Migration Strategy

**No migration needed** - This is a new optional feature, not a data model change.

**Rollout**:
1. Deploy code with FeatureContext (backward compatible)
2. Existing callers continue using defaults (no regression)
3. MC simulation opts in by passing context
4. Gradual adoption (non-MC use cases can opt in later if beneficial)

---

**Design Complete**: 2026-01-22  
**Next**: Generate contracts/ and quickstart.md
