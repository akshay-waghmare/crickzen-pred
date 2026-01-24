# API Contract: FeatureContext

**File**: `src/bbl_pipeline/simulation/feature_context.py`  
**Type**: Dataclass (Value Object)  
**Status**: New Entity

## Interface

```python
from dataclasses import dataclass

@dataclass
class FeatureContext:
    """
    Cached feature values for Monte Carlo terminal state evaluation.
    
    Built once per MC call to avoid repeated feature store lookups.
    Amortizes ~10ms cost across 2000 terminal states.
    
    All fields are immutable after creation (value object pattern).
    """
    
    venue_avg_score: float
    """Average score at venue (e.g., 150.0 for Perth Stadium). Range: [100, 250]."""
    
    venue_bat_first_wr: float
    """Bat-first win rate at venue (e.g., 0.48). Range: [0.0, 1.0]."""
    
    team_a_wr: float
    """Batting team overall win rate (e.g., 0.62 for Perth Scorchers). Range: [0.0, 1.0]."""
    
    team_b_wr: float
    """Bowling team overall win rate (e.g., 0.38). Range: [0.0, 1.0]."""
    
    batting_situation_wr: float
    """Batting team situation-specific win rate (e.g., 0.65 when batting first). Range: [0.0, 1.0]."""
    
    bowling_situation_wr: float
    """Bowling team situation-specific win rate (e.g., 0.42 when bowling first). Range: [0.0, 1.0]."""
    
    league: str
    """League code (e.g., "bbl", "sa20", "ilt20"). Non-empty string."""
    
    def __post_init__(self) -> None:
        """
        Validate feature values are in expected ranges.
        
        Raises:
            ValueError: If any field is out of valid range
        """
```

## Validation Rules

| Field | Constraint | Error Message |
|-------|-----------|---------------|
| `venue_avg_score` | 100 ≤ value ≤ 250 | "venue_avg_score {value} out of range [100, 250]" |
| `venue_bat_first_wr` | 0.0 ≤ value ≤ 1.0 | "venue_bat_first_wr {value} not in [0, 1]" |
| `team_a_wr` | 0.0 ≤ value ≤ 1.0 | "team_a_wr {value} not in [0, 1]" |
| `team_b_wr` | 0.0 ≤ value ≤ 1.0 | "team_b_wr {value} not in [0, 1]" |
| `batting_situation_wr` | 0.0 ≤ value ≤ 1.0 | "batting_situation_wr {value} not in [0, 1]" |
| `bowling_situation_wr` | 0.0 ≤ value ≤ 1.0 | "bowling_situation_wr {value} not in [0, 1]" |
| `league` | len(value) > 0 | "league must be non-empty string" |

## Usage Examples

### Example 1: Build from Feature Store

```python
from bbl_pipeline.simulation.feature_context import FeatureContext

# Predictor has access to InMemoryFeatureStore
context = predictor.build_feature_context(
    batting_team="Perth Scorchers",
    bowling_team="Sydney Sixers",
    venue="Perth Stadium",
    league="bbl",
    innings=2
)

# Result:
# FeatureContext(
#     venue_avg_score=150.2,
#     venue_bat_first_wr=0.48,
#     team_a_wr=0.62,
#     team_b_wr=0.38,
#     batting_situation_wr=0.59,  # bowl_first_wr for innings 2
#     bowling_situation_wr=0.45,  # bat_first_wr for innings 2
#     league="bbl"
# )
```

### Example 2: Manual Construction (Testing)

```python
context = FeatureContext(
    venue_avg_score=165.0,
    venue_bat_first_wr=0.45,
    team_a_wr=0.5,
    team_b_wr=0.5,
    batting_situation_wr=0.5,
    bowling_situation_wr=0.5,
    league="test"
)
```

### Example 3: Validation Error

```python
# Raises ValueError: venue_avg_score 300.0 out of range [100, 250]
context = FeatureContext(
    venue_avg_score=300.0,  # ❌ Too high
    venue_bat_first_wr=0.45,
    team_a_wr=0.5,
    team_b_wr=0.5,
    batting_situation_wr=0.5,
    bowling_situation_wr=0.5,
    league="bbl"
)
```

## Implementation Notes

- **Immutability**: Consider making dataclass frozen for safety: `@dataclass(frozen=True)`
- **Serialization**: Not needed (ephemeral, created per MC call)
- **Equality**: Default dataclass equality (all fields must match)
- **Hashing**: Not needed unless used as dict key (unlikely)

## Dependencies

- **Imports**: `from dataclasses import dataclass`
- **No external dependencies** (pure Python stdlib)

## Testing Contract

```python
def test_feature_context_validation():
    """Test that FeatureContext validates field ranges."""
    
    # Valid context
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
    
    # Invalid venue_avg_score (too low)
    with pytest.raises(ValueError, match="out of range"):
        FeatureContext(venue_avg_score=50.0, ...)
    
    # Invalid win rate (negative)
    with pytest.raises(ValueError, match="not in \\[0, 1\\]"):
        FeatureContext(..., team_a_wr=-0.1, ...)
```

---

**Version**: 1.0  
**Status**: Design Complete  
**Next**: Implement in `src/bbl_pipeline/simulation/feature_context.py`
