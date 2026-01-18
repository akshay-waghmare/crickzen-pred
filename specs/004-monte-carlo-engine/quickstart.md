# Quickstart: Monte Carlo Simulation Engine

**Date**: 2026-01-19  
**Feature**: 004-monte-carlo-engine

## Installation

The Monte Carlo engine is part of the `bbl_pipeline` package:

```bash
pip install -e .
```

## Basic Usage

### 1. Single Ball Simulation (Timing/Hedging)

```python
from bbl_pipeline.simulation import MatchState, simulate

# Create match state: Inn2, score 110/4, 48 balls remaining, chasing 170
state = MatchState(
    innings=2,
    score=110,
    wickets_lost=4,
    balls_remaining=48,
    target_runs=170,
    league="bbl",
    batting_team="Melbourne Stars",
    bowling_team="Sydney Sixers"
)

# Simulate 1 ball forward, 2000 times
result = simulate(state, horizon_balls=1, n_sims=2000, league="bbl")

print(f"1-ball lookahead: {result.mean_prob:.3f} ± {result.std_prob:.3f}")
print(f"90% CI: [{result.p5:.3f}, {result.p95:.3f}]")
print(f"Time: {result.time_taken_ms:.1f}ms")
```

**Expected Output**:
```
1-ball lookahead: 0.623 ± 0.042
90% CI: [0.558, 0.689]
Time: 85.3ms
```

### 2. Six Ball Simulation (Betting Decisions)

```python
from bbl_pipeline.simulation import simulate, evaluate_bet

# Same state as above
result_6 = simulate(state, horizon_balls=6, n_sims=2000, league="bbl")

print(f"6-ball lookahead: {result_6.mean_prob:.3f} ± {result_6.std_prob:.3f}")
print(f"90% CI: [{result_6.p5:.3f}, {result_6.p95:.3f}]")

# Evaluate betting decision
decision = evaluate_bet(
    sim_result=result_6,
    market_odds=1.60,  # Market has team at 62.5% implied
    innings=2,
    phase="middle"
)

print(f"\nAction: {decision.action}")
print(f"Edge: {decision.edge:.1%}")
print(f"Reasons: {decision.reasons}")
```

**Expected Output**:
```
6-ball lookahead: 0.618 ± 0.068
90% CI: [0.512, 0.724]

Action: PASS
Edge: -0.7%
Reasons: ['Edge -0.7% below threshold (18% required for inn2 middle)']
```

### 3. With 1-Ball/6-Ball Agreement Check

```python
from bbl_pipeline.simulation import simulate, evaluate_bet

# Run both simulations
result_1 = simulate(state, horizon_balls=1, n_sims=2000, league="bbl")
result_6 = simulate(state, horizon_balls=6, n_sims=2000, league="bbl")

# Evaluate with agreement check
decision = evaluate_bet(
    sim_result=result_6,
    market_odds=1.50,  # Market has team at 66.7% implied
    innings=2,
    phase="middle",
    sim_result_1ball=result_1
)

print(f"μ₁ = {result_1.mean_prob:.3f}, μ₆ = {result_6.mean_prob:.3f}")
print(f"Action: {decision.action}")
print(f"Reasons: {decision.reasons}")
```

### 4. Death Overs Example (High Stakes)

```python
# Death over scenario: Inn2, 150/5, 12 balls remaining, chasing 175
state_death = MatchState(
    innings=2,
    score=150,
    wickets_lost=5,
    balls_remaining=12,
    target_runs=175,
    league="sa20",  # SA20 has sharper calibration
    batting_team="Sunrisers Eastern Cape",
    bowling_team="MI Cape Town"
)

result = simulate(state_death, horizon_balls=6, n_sims=2000, league="sa20")

print(f"Death over: {result.mean_prob:.3f} ± {result.std_prob:.3f}")
print(f"Temperature applied: {result.temperature:.3f}")

# Lower threshold in death overs (15% edge required)
decision = evaluate_bet(
    sim_result=result,
    market_odds=1.80,  # 55.6% implied
    innings=2,
    phase="death"
)
print(f"Action: {decision.action}")
```

### 5. First Innings Example

```python
# First innings: 95/2 after 10 overs
state_inn1 = MatchState(
    innings=1,
    score=95,
    wickets_lost=2,
    balls_remaining=60,
    target_runs=None,  # No target in first innings
    league="bbl",
    batting_team="Perth Scorchers",
    bowling_team="Brisbane Heat"
)

result = simulate(state_inn1, horizon_balls=6, n_sims=2000, league="bbl")

print(f"Inn1 middle: {result.mean_prob:.3f} ± {result.std_prob:.3f}")
# Note: Higher edge threshold (30%) for first innings middle
```

## Configuration

### Custom Betting Thresholds

```python
from bbl_pipeline.simulation import BettingThresholds, evaluate_bet

# More conservative thresholds
thresholds = BettingThresholds(
    EDGE_MIN_BY_PHASE={
        'inn1': {'powerplay': 0.35, 'middle': 0.35, 'death': 0.30},
        'inn2': {'powerplay': 0.25, 'middle': 0.20, 'death': 0.18},
    },
    SIGMA_MAX_BY_PHASE={
        'inn1': {'powerplay': 0.08, 'middle': 0.08, 'death': 0.08},
        'inn2': {'powerplay': 0.08, 'middle': 0.08, 'death': 0.10},
    }
)

decision = evaluate_bet(result, market_odds=1.60, innings=2, phase="death", thresholds=thresholds)
```

### Reproducibility (Seeded RNG)

```python
# Same seed → same results
result_a = simulate(state, horizon_balls=6, n_sims=2000, league="bbl", seed=42)
result_b = simulate(state, horizon_balls=6, n_sims=2000, league="bbl", seed=42)

assert result_a.mean_prob == result_b.mean_prob  # True
```

## League Temperature Values

| League | T₁ (Inn1) | T₂ (Inn2) | Effect |
|--------|-----------|-----------|--------|
| BBL | 0.847 | 0.830 | Sharper predictions |
| SA20 | 0.899 | 0.765 | Inn2 much sharper |
| SSM | 0.877 | 0.888 | Slight sharpening |

Temperature < 1.0 → predictions move toward 0/1 (more confident).

## Performance Expectations

| Scenario | Target | Naive | Optimized |
|----------|--------|-------|-----------|
| 1 ball, 2000 sims | 200ms | 300ms | 80ms |
| 6 balls, 2000 sims | 500ms | 800ms | 200ms |
| 30 balls, 2000 sims | 2000ms | 3500ms | 1000ms |

Optimizations: NumPy vectorization, pre-computed CDF tables, cached ResourceFeatureCalculator.

## Next Steps

- See [data-model.md](data-model.md) for entity schemas
- See [contracts/simulation-api.yaml](contracts/simulation-api.yaml) for full API spec
- See [research.md](research.md) for phase table derivation
