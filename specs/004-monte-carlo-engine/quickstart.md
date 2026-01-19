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
result = simulate(state, horizon=1, n_simulations=2000)

print(f"1-ball lookahead: {result.mean_prob:.3f} ± {result.std_prob:.3f}")
print(f"90% CI: [{result.p5:.3f}, {result.p95:.3f}]")
print(f"Time: {result.time_taken_ms:.1f}ms")
```

**Expected Output**:
```
1-ball lookahead: 0.881 ± 0.021
90% CI: [0.862, 0.922]
Time: 117.2ms
```

### 2. Six Ball Simulation (Betting Decisions)

```python
from bbl_pipeline.simulation import simulate, evaluate_bet

# Same state as above
result_6 = simulate(state, horizon=6, n_simulations=2000)

print(f"6-ball lookahead: {result_6.mean_prob:.3f} ± {result_6.std_prob:.3f}")
print(f"90% CI: [{result_6.p5:.3f}, {result_6.p95:.3f}]")

# Evaluate betting decision
decision = evaluate_bet(
    simulation_result=result_6,
    market_odds=1.60,  # Market has team at 62.5% implied
    balls_remaining=48,
)

print(f"\nAction: {decision.decision.value}")
print(f"Edge: {decision.edge:.1%}")
print(f"Rationale: {decision.rationale}")
```

**Expected Output**:
```
6-ball lookahead: 0.868 ± 0.068
90% CI: [0.756, 0.964]

Action: SKIP
Edge: 24.3%
Rationale: Uncertainty too high: σ=0.0684 > max 0.05 for middle. Wait for more stable conditions.
```

### 3. With 1-Ball/6-Ball Agreement Check

```python
from bbl_pipeline.simulation import simulate, check_simulation_agreement, evaluate_bet_with_agreement

# Run both simulations
result_1 = simulate(state, horizon=1, n_simulations=1000)
result_6 = simulate(state, horizon=6, n_simulations=2000)

# Check if simulations agree
agreement = check_simulation_agreement(result_1, result_6)
print(f"Agreement: {agreement.agree}")
print(f"Mean diff: {agreement.diff:.2%}")
print(f"Volatility ratio: {agreement.ratio:.2f}x")
print(f"Recommendation: {agreement.recommendation}")

# Evaluate with agreement check (auto-downgrades on disagreement)
decision, agreement = evaluate_bet_with_agreement(
    result_1ball=result_1,
    result_6ball=result_6,
    market_odds=1.50,  # Market has team at 66.7% implied
    balls_remaining=48,
    model_prob=0.85,  # Optional: use league-calibrated model prob for edge
)

print(f"μ₁ = {result_1.mean_prob:.3f}, μ₆ = {result_6.mean_prob:.3f}")
print(f"Action: {decision.decision.value}")
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

result = simulate(state_death, horizon=6, n_simulations=2000)

print(f"Death over: {result.mean_prob:.3f} ± {result.std_prob:.3f}")
print(f"Temperature applied: {result.temperature}")

# Lower threshold in death overs (15% edge required)
decision = evaluate_bet(
    simulation_result=result,
    market_odds=1.80,  # 55.6% implied
    balls_remaining=12,
)
print(f"Action: {decision.decision.value}")
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

result = simulate(state_inn1, horizon=6, n_simulations=2000)

print(f"Inn1 middle: {result.mean_prob:.3f} ± {result.std_prob:.3f}")
# Note: Higher edge threshold (30%) for first innings middle
```

### 6. Using ML Model for Monte Carlo (More Accurate)

```python
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.simulation import simulate

# Load predictor with league calibration
predictor = Predictor.load(
    "models/t20_male_v2",
    "data/t20_male_feature_store_v2",
    league="bbl"
)

# Simulate with ML model terminal state evaluation
result = simulate(
    state, 
    horizon=6, 
    n_simulations=2000,
    predictor=predictor  # Uses ML model instead of resource_win_prob
)

print(f"ML model result: {result.mean_prob:.3f} ± {result.std_prob:.3f}")
print(f"Time: {result.time_taken_ms:.1f}ms")  # ~50ms for 2000 sims
```

## Configuration

### Custom Betting Thresholds

```python
from bbl_pipeline.simulation import BettingThresholds, evaluate_bet

# More conservative thresholds
thresholds = BettingThresholds(
    edge_min_powerplay=0.05,
    edge_min_middle=0.04,
    edge_min_death=0.07,
    sigma_max_powerplay=0.08,
    sigma_max_middle=0.06,
    sigma_max_death=0.10,
)

decision = evaluate_bet(
    simulation_result=result,
    market_odds=1.60,
    balls_remaining=48,
    thresholds=thresholds
)
```

### Reproducibility (Seeded RNG)

```python
from bbl_pipeline.simulation import simulate, NextBallSampler

# Create seeded sampler
sampler = NextBallSampler(seed=42)

# Same seed → same results  
result_a = simulate(state, horizon=6, n_simulations=2000, sampler=sampler)

sampler_b = NextBallSampler(seed=42)
result_b = simulate(state, horizon=6, n_simulations=2000, sampler=sampler_b)

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
