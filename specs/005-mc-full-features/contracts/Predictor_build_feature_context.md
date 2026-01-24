# API Contract: Predictor.build_feature_context()

**File**: `src/bbl_pipeline/inference/predictor.py`  
**Type**: Instance Method (New)  
**Status**: New Method

## Signature

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
    
    Performs 5 feature store lookups (venue stats, 2× team stats)
    and constructs a FeatureContext for use in predict_batch().
    
    Args:
        batting_team: Canonical team name (e.g., "Perth Scorchers")
        bowling_team: Canonical team name (e.g., "Sydney Sixers")
        venue: Venue name (e.g., "Perth Stadium")
        league: League code (e.g., "bbl", "sa20", "ilt20")
        innings: 1 or 2 (affects situation-specific win rates)
        
    Returns:
        FeatureContext: Cached venue/team stats for terminal evaluation
        
    Raises:
        KeyError: If team or venue not found in feature store.
                  Caller should catch and handle (e.g., fallback to defaults).
        ValueError: If innings not in {1, 2}
        
    Performance:
        ~10ms (5 feature store lookups × ~2ms each)
        
    Example:
        >>> predictor = Predictor.load("models/t20_male_v2", league="bbl")
        >>> context = predictor.build_feature_context(
        ...     batting_team="Perth Scorchers",
        ...     bowling_team="Sydney Sixers",
        ...     venue="Perth Stadium",
        ...     league="bbl",
        ...     innings=2
        ... )
        >>> print(context.venue_avg_score)
        150.2
    """
```

## Parameters

| Parameter | Type | Required | Constraints | Example |
|-----------|------|----------|-------------|---------|
| `batting_team` | str | Yes | Must exist in feature store | "Perth Scorchers" |
| `bowling_team` | str | Yes | Must exist in feature store | "Sydney Sixers" |
| `venue` | str | Yes | Must exist in feature store | "Perth Stadium" |
| `league` | str | Yes | Non-empty string | "bbl" |
| `innings` | int | Yes | 1 or 2 | 2 |

## Return Value

**Type**: `FeatureContext`

**Fields Populated**:
- `venue_avg_score`: From `feature_store.get_venue_stats(venue).avg_score`
- `venue_bat_first_wr`: From `feature_store.get_venue_stats(venue).bat_first_wr`
- `team_a_wr`: From `feature_store.get_team_stats(batting_team).win_rate`
- `team_b_wr`: From `feature_store.get_team_stats(bowling_team).win_rate`
- `batting_situation_wr`: Innings-specific (bat_first_wr if innings==1, bowl_first_wr if innings==2)
- `bowling_situation_wr`: Innings-specific (bowl_first_wr if innings==1, bat_first_wr if innings==2)
- `league`: Passed through from parameter

## Error Handling

### KeyError: Team Not Found

```python
try:
    context = predictor.build_feature_context(
        batting_team="Unknown Team",  # ❌ Not in feature store
        ...
    )
except KeyError as e:
    logger.warning(f"Team not found: {e}, falling back to defaults")
    # Fallback: use None for context (predict_batch uses defaults)
    context = None
```

### KeyError: Venue Not Found

```python
try:
    context = predictor.build_feature_context(
        venue="Unknown Venue",  # ❌ Not in feature store
        ...
    )
except KeyError as e:
    logger.warning(f"Venue not found: {e}, falling back to defaults")
    context = None
```

### ValueError: Invalid Innings

```python
try:
    context = predictor.build_feature_context(
        innings=3,  # ❌ Must be 1 or 2
        ...
    )
except ValueError as e:
    logger.error(f"Invalid innings: {e}")
    raise  # Re-raise (programming error, not user error)
```

## Usage Examples

### Example 1: Typical Usage in MC Engine

```python
# In engine.py::simulate_vectorized()
if use_ml_model and predictor:
    try:
        context = predictor.build_feature_context(
            batting_team=state.batting_team,
            bowling_team=state.bowling_team,
            venue=state.venue,
            league=state.league,
            innings=state.innings
        )
    except KeyError as e:
        logger.warning(f"Feature context build failed: {e}, using defaults")
        context = None
    
    # Pass to evaluator
    terminal_probs = evaluator.evaluate_batch_with_model(
        terminal_states,
        feature_context=context
    )
```

### Example 2: Testing with Known Values

```python
def test_build_feature_context():
    """Test feature context builds with expected values."""
    predictor = Predictor.load("models/bbl_v12", league="bbl")
    
    context = predictor.build_feature_context(
        batting_team="Perth Scorchers",
        bowling_team="Sydney Sixers",
        venue="Perth Stadium",
        league="bbl",
        innings=1
    )
    
    # Assertions based on known feature store data
    assert 140 <= context.venue_avg_score <= 160  # Perth Stadium range
    assert 0.4 <= context.venue_bat_first_wr <= 0.6
    assert 0.5 <= context.team_a_wr <= 0.7  # Perth Scorchers are strong
    assert context.league == "bbl"
```

### Example 3: Missing Team Handling

```python
def test_build_feature_context_missing_team():
    """Test that KeyError is raised for missing teams."""
    predictor = Predictor.load("models/bbl_v12", league="bbl")
    
    with pytest.raises(KeyError, match="Unknown Team"):
        predictor.build_feature_context(
            batting_team="Unknown Team",
            bowling_team="Sydney Sixers",
            venue="Perth Stadium",
            league="bbl",
            innings=1
        )
```

## Implementation Notes

### Feature Store Lookups

```python
def build_feature_context(self, batting_team, bowling_team, venue, league, innings):
    # Lookup 1: Venue stats
    venue_stats = self.feature_store.get_venue_stats(venue)
    
    # Lookup 2: Batting team overall stats
    team_a_stats = self.feature_store.get_team_stats(batting_team)
    
    # Lookup 3: Bowling team overall stats
    team_b_stats = self.feature_store.get_team_stats(bowling_team)
    
    # Derived: Situation-specific win rates
    if innings == 1:
        batting_situation_wr = team_a_stats.bat_first_wr
        bowling_situation_wr = team_b_stats.bowl_first_wr
    elif innings == 2:
        batting_situation_wr = team_a_stats.bowl_first_wr  # Chasing
        bowling_situation_wr = team_b_stats.bat_first_wr   # Defending
    else:
        raise ValueError(f"innings must be 1 or 2, got {innings}")
    
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

### Caching Considerations

**NOT IMPLEMENTED** (Context is ephemeral, built once per MC call):
- No LRU cache (overhead not worth it for once-per-call usage)
- No global cache (stale data risk when feature store updates)
- If performance becomes issue, consider caching in engine.py for multiple horizons (6ball, 12ball)

## Dependencies

- **Imports**: 
  ```python
  from ..simulation.feature_context import FeatureContext
  ```
- **Requires**: `self.feature_store` (InMemoryFeatureStore instance)

## Performance SLA

| Metric | Target | Measured |
|--------|--------|----------|
| Execution time | <15ms | ~10ms (5 lookups × 2ms) |
| Memory allocation | <1KB | ~100 bytes (FeatureContext) |
| Feature store hits | 5 | Exactly 5 (deterministic) |

## Testing Contract

```python
def test_build_feature_context_happy_path():
    """Test successful feature context build."""
    # Setup
    predictor = Predictor.load("models/bbl_v12", league="bbl")
    
    # Execute
    context = predictor.build_feature_context(
        batting_team="Perth Scorchers",
        bowling_team="Sydney Sixers",
        venue="Perth Stadium",
        league="bbl",
        innings=1
    )
    
    # Verify
    assert isinstance(context, FeatureContext)
    assert 100 <= context.venue_avg_score <= 250
    assert 0 <= context.team_a_wr <= 1
    assert context.league == "bbl"

def test_build_feature_context_missing_venue():
    """Test KeyError when venue not found."""
    predictor = Predictor.load("models/bbl_v12", league="bbl")
    
    with pytest.raises(KeyError):
        predictor.build_feature_context(
            batting_team="Perth Scorchers",
            bowling_team="Sydney Sixers",
            venue="Nonexistent Stadium",
            league="bbl",
            innings=1
        )

def test_build_feature_context_invalid_innings():
    """Test ValueError for invalid innings."""
    predictor = Predictor.load("models/bbl_v12", league="bbl")
    
    with pytest.raises(ValueError, match="innings must be 1 or 2"):
        predictor.build_feature_context(
            batting_team="Perth Scorchers",
            bowling_team="Sydney Sixers",
            venue="Perth Stadium",
            league="bbl",
            innings=3
        )
```

---

**Version**: 1.0  
**Status**: Design Complete  
**Next**: Implement in `src/bbl_pipeline/inference/predictor.py`
