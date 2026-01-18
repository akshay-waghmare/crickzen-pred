# Data Model: Monte Carlo Simulation Engine

**Date**: 2026-01-19  
**Feature**: 004-monte-carlo-engine

## Entities

### 1. MatchState

Current match situation for simulation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `innings` | int | Yes | 1 (batting first) or 2 (chasing) |
| `score` | int | Yes | Current runs scored (0+) |
| `wickets_lost` | int | Yes | Wickets lost (0-10) |
| `balls_remaining` | int | Yes | Balls remaining in innings (0-120) |
| `target_runs` | int | Inn2 only | Target to chase (Inn2) or None (Inn1) |
| `league` | str | Yes | League code for temperature calibration (e.g., "bbl", "sa20") |
| `batting_team` | str | Yes | Canonical team name |
| `bowling_team` | str | Yes | Canonical team name |
| `venue` | str | No | Venue name (optional, for venue adjustments) |

**Validation Rules**:
- `innings` ∈ {1, 2}
- `score` ≥ 0
- `wickets_lost` ∈ [0, 10]
- `balls_remaining` ∈ [0, 120]
- If `innings == 2`, `target_runs` must be provided
- If `wickets_lost == 10`, innings is over

**Derived Properties**:
- `overs_completed` = (120 - balls_remaining) / 6
- `phase` = 'powerplay' if overs < 6 else 'middle' if overs < 15 else 'death'
- `is_over` = (wickets_lost == 10) or (balls_remaining == 0) or (innings == 2 and score >= target_runs)

---

### 2. BallOutcome

Result of a single simulated ball.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `runs` | int | Yes | Runs scored (0, 1, 2, 3, 4, 5, 6) |
| `is_wicket` | bool | Yes | Whether a wicket fell |

**Validation Rules**:
- `runs` ∈ {0, 1, 2, 3, 4, 5, 6}
- If `is_wicket == True`, a wicket is added to `wickets_lost`

**Note**: In v1, extras (wides, no-balls) are simplified. A "5" represents extras + runs. Future versions may model extras separately.

---

### 3. SimulationResult

Aggregated output from N Monte Carlo simulations.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mean_prob` | float | Yes | Mean win probability across simulations |
| `std_prob` | float | Yes | Standard deviation of win probabilities |
| `p5` | float | Yes | 5th percentile win probability |
| `p95` | float | Yes | 95th percentile win probability |
| `n_sims` | int | Yes | Number of simulations run |
| `horizon_balls` | int | Yes | Number of balls simulated forward |
| `time_taken_ms` | float | Yes | Execution time in milliseconds |
| `league` | str | Yes | League used for temperature calibration |
| `temperature` | float | No | Temperature applied (if any) |

**Validation Rules**:
- `mean_prob` ∈ [0.0, 1.0]
- `std_prob` ≥ 0
- `p5` ≤ `mean_prob` ≤ `p95`
- `n_sims` > 0

---

### 4. BettingThresholds

Phase-aware configuration for betting decisions.

| Field | Type | Description |
|-------|------|-------------|
| `EDGE_MIN_BY_PHASE` | Dict[str, Dict[str, float]] | Minimum edge required by innings×phase |
| `SIGMA_MAX_BY_PHASE` | Dict[str, Dict[str, float]] | Maximum σ₆ allowed by innings×phase |

**Default Values**:

```python
EDGE_MIN_BY_PHASE = {
    'inn1': {'powerplay': 0.30, 'middle': 0.30, 'death': 0.25},
    'inn2': {'powerplay': 0.20, 'middle': 0.18, 'death': 0.15},
}

SIGMA_MAX_BY_PHASE = {
    'inn1': {'powerplay': 0.10, 'middle': 0.10, 'death': 0.10},
    'inn2': {'powerplay': 0.10, 'middle': 0.10, 'death': 0.10},
}
```

**Rationale**:
- Inn2 death has lower edge threshold (15%) because outcomes are more predictable
- Inn1 middle requires higher edge (30%) due to uncertainty about final score

---

### 5. BettingDecision

Recommendation output from betting evaluation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | str | Yes | "BET", "PASS", or "HEDGE" |
| `edge` | float | Yes | Calculated edge (model_prob - implied_prob) |
| `confidence` | float | Yes | Confidence level (1 - σ₆ normalized) |
| `reasons` | List[str] | Yes | Explanation of decision |
| `mu_1` | float | No | 1-ball simulation mean (if computed) |
| `mu_6` | float | Yes | 6-ball simulation mean |
| `sigma_6` | float | Yes | 6-ball simulation std |
| `market_odds` | float | Yes | Market decimal odds |
| `implied_prob` | float | Yes | 1 / market_odds |

**Decision Logic**:

```
IF sigma_6 > SIGMA_MAX_BY_PHASE[innings][phase]:
    action = "PASS"
    reasons.append("High uncertainty (σ₆ > threshold)")
ELIF mu_1 and sign(mu_1 - 0.5) != sign(mu_6 - 0.5):
    action = "PASS"
    reasons.append("1-ball and 6-ball disagree on direction")
ELIF edge < EDGE_MIN_BY_PHASE[innings][phase]:
    action = "PASS"
    reasons.append(f"Edge {edge:.1%} below threshold")
ELSE:
    action = "BET"
    reasons.append(f"Edge {edge:.1%} with σ₆={sigma_6:.3f}")
```

---

### 6. NextBallSampler

Configuration and state for outcome sampling.

| Field | Type | Description |
|-------|------|-------------|
| `run_dist` | Dict[str, Dict[int, float]] | Run probabilities by phase |
| `wicket_prob` | Dict[str, float] | Base wicket probability by phase |
| `wicket_multiplier` | Dict[int, float] | Multiplier by wickets already down |
| `rng` | np.random.Generator | Random number generator (seeded for reproducibility) |

**Methods**:
- `sample(state: MatchState) -> BallOutcome` - Sample single outcome
- `sample_vectorized(states: np.ndarray, n: int) -> Tuple[np.ndarray, np.ndarray]` - Sample n outcomes for vectorized simulation

---

## State Transitions

### Ball Event Flow

```
MatchState + BallOutcome → MatchState'

1. score' = score + outcome.runs
2. wickets_lost' = wickets_lost + (1 if outcome.is_wicket else 0)
3. balls_remaining' = balls_remaining - 1
4. Check termination:
   - If wickets_lost' == 10 → innings over
   - If balls_remaining' == 0 → innings over
   - If innings == 2 and score' >= target_runs → match won
```

### Innings Termination Conditions

| Condition | Result |
|-----------|--------|
| `wickets_lost == 10` | All out, return `resource_win_prob` at terminal state |
| `balls_remaining == 0` | Overs complete, return `resource_win_prob` at terminal state |
| `innings == 2 and score >= target` | Target chased, return `1.0` (batting team wins) |

---

## Relationships

```
MatchState ──1:N──▶ BallOutcome (via simulation)
     │
     ▼
SimulationResult ◀── aggregate(N × terminal MatchState)
     │
     ▼
BettingDecision ◀── evaluate(SimulationResult, market_odds, thresholds)
```

---

## Serialization Notes

- `MatchState`: JSON-serializable dataclass
- `SimulationResult`: JSON-serializable dataclass  
- `BettingThresholds`: YAML/JSON config file
- `NextBallSampler`: Pickle for phase tables + RNG state
