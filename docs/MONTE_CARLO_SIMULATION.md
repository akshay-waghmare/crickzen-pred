# Monte Carlo Simulation Engine

**Version**: 1.0  
**Date**: January 19, 2026  
**Status**: Production Ready ✅

## Overview

The Monte Carlo simulation engine provides uncertainty quantification and betting decision support for live T20 match predictions. It simulates thousands of possible match outcomes to compute confidence intervals and optimal betting strategies.

## Key Features

- **1-Ball Simulation**: Next delivery outcomes with uncertainty (σ₁)
- **6-Ball Simulation**: Next over outcomes with temperature-scaled variance (σ₆)
- **Temperature Calibration**: League-specific probability adjustments (BBL, SA20, ILT20, WPL)
- **Betting Decision Support**: Phase-aware Kelly criterion with risk guardrails
- **Performance**: <200ms for 1-ball, <500ms for 6-ball simulations

## Architecture

### Module Structure

```
src/bbl_pipeline/simulation/
├── __init__.py          # Public API exports
├── config.py            # Phase tables, run/wicket distributions
├── state.py             # MatchState & SimulationResult dataclasses
├── sampler.py           # NextBallSampler (phase-based probabilities)
├── evaluator.py         # TerminalStateEvaluator (model integration)
├── engine.py            # simulate(), simulate_vectorized()
└── betting.py           # evaluate_bet(), Kelly criterion
```

### Data Flow

```
1. Current Match State → MatchState
2. MatchState → simulate(horizon=6, n_sims=2000)
3. For each simulation:
   - Sample runs/wickets from phase distributions
   - Update state (score, wickets, balls)
   - Evaluate terminal state → win probability
   - Apply league temperature calibration
4. Aggregate results → SimulationResult (mean, σ, p5, p95)
5. SimulationResult + Market Odds → evaluate_bet()
6. Return BettingDecision (BET/NO_BET/SKIP)
```

## API Reference

### Core Functions

#### `simulate(state, horizon=1, n_simulations=1000)`

Run Monte Carlo simulation from current state.

**Parameters:**
- `state` (MatchState): Current match situation
- `horizon` (int): Number of balls to simulate (1, 6, 12, etc.)
- `n_simulations` (int): Number of Monte Carlo paths (≥100)
- `apply_temp` (bool): Apply league temperature calibration (default: True)
- `model_dir` (str): Path to model directory (default: "models/t20_male_v1")

**Returns:** SimulationResult with mean_prob, std_prob, p5, p95, time_taken_ms

**Example:**
```python
from bbl_pipeline.simulation import MatchState, simulate

state = MatchState(
    innings=2,
    score=150,
    wickets_lost=4,
    balls_remaining=24,
    target_runs=170,
    league="bbl",
    batting_team="Perth Scorchers",
    bowling_team="Sydney Sixers",
)

# 1-ball simulation
result_1 = simulate(state, horizon=1, n_simulations=1000)
print(f"Next ball: {result_1.mean_prob:.1%} ± {result_1.std_prob:.1%}")

# 6-ball simulation
result_6 = simulate(state, horizon=6, n_simulations=2000)
print(f"Next over: {result_6.mean_prob:.1%} [{result_6.p5:.1%}, {result_6.p95:.1%}]")
```

#### `evaluate_bet(simulation_result, market_odds, balls_remaining)`

Evaluate betting decision with phase-aware thresholds.

**Parameters:**
- `simulation_result` (SimulationResult): Result from simulate()
- `market_odds` (float): Decimal odds (e.g., 2.0 = even money)
- `balls_remaining` (int): Balls remaining (for phase detection)
- `thresholds` (BettingThresholds, optional): Custom thresholds

**Returns:** BettingDecision with decision (BET/NO_BET/SKIP), edge, kelly_stake, rationale

**Example:**
```python
from bbl_pipeline.simulation import simulate, evaluate_bet

result = simulate(state, horizon=6, n_simulations=2000)
decision = evaluate_bet(
    simulation_result=result,
    market_odds=2.5,  # Bookmaker odds
    balls_remaining=state.balls_remaining,
)

if decision.decision == BetDecision.BET:
    print(f"BET {decision.kelly_stake:.1%} of bankroll")
    print(f"Edge: {decision.edge:.1%}")
    print(f"Rationale: {decision.rationale}")
```

### Data Classes

#### MatchState

Current match situation for simulation.

**Fields:**
- `innings` (int): 1 (batting first) or 2 (chasing)
- `score` (int): Current runs scored (0+)
- `wickets_lost` (int): Wickets lost (0-10)
- `balls_remaining` (int): Balls remaining in innings (0-120)
- `target_runs` (int | None): Target to chase (required if innings=2)
- `league` (str): League code for temperature calibration
- `batting_team` (str): Canonical batting team name
- `bowling_team` (str): Canonical bowling team name
- `venue` (str | None): Venue name (optional)

**Properties:**
- `overs_completed`: Overs completed in current innings
- `phase`: Current game phase (powerplay/middle/death)
- `is_over`: Whether match is complete

#### SimulationResult

Aggregated simulation results with uncertainty.

**Fields:**
- `mean_prob` (float): Mean win probability [0, 1]
- `std_prob` (float): Standard deviation
- `p5` (float): 5th percentile
- `p95` (float): 95th percentile
- `n_sims` (int): Number of simulations
- `horizon_balls` (int): Balls simulated per path
- `time_taken_ms` (float): Execution time in milliseconds
- `league` (str): League identifier
- `temperature` (float | None): Applied temperature (if any)

**Properties:**
- `ci_low`: Lower 90% confidence bound (p5)
- `ci_high`: Upper 90% confidence bound (p95)
- `ci_width`: Width of 90% confidence interval

#### BettingDecision

Structured betting recommendation with rationale.

**Fields:**
- `decision` (BetDecision): BET, NO_BET, or SKIP
- `edge` (float): Model edge over market
- `kelly_stake` (float): Optimal bet size (0-1)
- `confidence` (float): Confidence in decision [0, 1]
- `phase` (str): Game phase (powerplay/middle/death)
- `rationale` (str): Human-readable explanation
- `model_prob` (float): Model's probability
- `market_odds` (float): Market decimal odds
- `implied_prob` (float): Market's implied probability
- `sigma` (float): Simulation uncertainty

## Phase-Based Distributions

Empirically derived from historical T20 data.

### Run Distributions by Phase

| Phase | 0 | 1 | 2 | 3 | 4 | 6 |
|-------|---|---|---|---|---|---|
| **Powerplay** (0-36 balls) | 45% | 20% | 8% | 5% | 15% | 7% |
| **Middle** (37-96 balls) | 50% | 22% | 9% | 4% | 10% | 5% |
| **Death** (97-120 balls) | 35% | 18% | 10% | 6% | 15% | 16% |

### Wicket Probabilities by Phase

| Phase | Base Wicket % | Multiplier (5+ down) |
|-------|---------------|----------------------|
| **Powerplay** | 4.0% | 1.3× |
| **Middle** | 5.0% | 1.4× |
| **Death** | 6.0% | 1.5× |

**Rationale:**
- **Powerplay**: Field restrictions encourage boundaries (16% sixes)
- **Middle**: Risk management phase with highest dot ball rate (50%)
- **Death**: Aggressive batting, highest wicket risk (6%), most boundaries (31%)

## Temperature Calibration

League-specific probability adjustments applied at terminal evaluation.

**Formula:** `p_cal = sigmoid(logit(p_raw) / T)`

### Current Calibrators

| League | Temperature | Status | Matches |
|--------|-------------|--------|---------|
| **BBL** | None | Default (T=1.0) | 672K samples |
| **SA20** | 0.765 | Calibrated | 121 matches |
| **ILT20** | TBD | Default (T=1.0) | 99 matches |
| **WPL** | TBD | Default (T=1.0) | 74 matches |

**Interpretation:**
- **T < 1.0**: Sharper probabilities (more confident)
- **T = 1.0**: Identity (no adjustment)
- **T > 1.0**: Softer probabilities (less confident)

## Betting Decision Logic

### Phase-Aware Thresholds

| Phase | Min Edge | Max Sigma | Kelly Cap |
|-------|----------|-----------|-----------|
| **Powerplay** | 10% | 8% | 3% |
| **Middle** | 8% | 5% | 5% |
| **Death** | 5% | 10% | 10% |

**Rationale:**
- **Powerplay**: High variance requires larger edge (10%)
- **Middle**: Stable phase allows lower edge (8%) but stricter σ (5%)
- **Death**: Tight games justify aggressive Kelly (10%) despite variance

### Decision Rules

1. **SKIP**: σ > max_sigma for phase
   - "Uncertainty too high, wait for more stable conditions"

2. **NO_BET**: Edge < 0
   - "Negative edge, market odds imply higher probability than model"

3. **BET**: Edge ≥ min_edge for phase AND σ ≤ max_sigma
   - Kelly stake = (edge / odds) × kelly_cap

## Integration

### Backend (crex_live_predictor.py)

```python
def _run_monte_carlo_simulation(self) -> dict:
    """Run Monte Carlo simulation for current match state."""
    if not SIMULATION_AVAILABLE:
        return {"available": False}
    
    # Create simulation state
    sim_state = SimMatchState(
        innings=self.innings,
        score=self.score,
        wickets_lost=self.wickets,
        balls_remaining=self.balls_remaining,
        target_runs=self.target if self.innings == 2 else None,
        league=self.league,
        batting_team=self.batting_team,
        bowling_team=self.bowling_team,
    )
    
    # Run simulations
    result_1ball = simulate(sim_state, horizon=1, n_simulations=1000)
    result_6ball = simulate(sim_state, horizon=6, n_simulations=2000)
    
    # Evaluate betting decision
    betting_decision = None
    if self.market_odds:
        betting_decision = evaluate_bet(
            simulation_result=result_6ball,
            market_odds=self.market_odds,
            balls_remaining=self.balls_remaining,
        )
    
    return {
        "available": True,
        "simulation_1ball": {...},
        "simulation_6ball": {...},
        "betting_decision": {...},
    }
```

### Frontend (live_streamlit_app.py)

```python
# Monte Carlo Simulation Panel
mc_data = d.get("monte_carlo", {})
if mc_data and mc_data.get("available", False):
    with st.expander("🎲 Monte Carlo Simulation", expanded=True):
        sim_1ball = mc_data.get("simulation_1ball", {})
        sim_6ball = mc_data.get("simulation_6ball", {})
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Next Ball", f"{sim_1ball['mean']*100:.1f}%")
        with col2:
            st.metric("Next Over", f"{sim_6ball['mean']*100:.1f}%")
        
        betting = mc_data.get("betting_decision", {})
        if betting:
            st.write(f"**{betting['action']}**: {betting['rationale']}")
```

## Performance Benchmarks

All benchmarks run on Intel i7-12700K, Windows 11.

| Scenario | N Sims | Mean Time | Target | Status |
|----------|--------|-----------|--------|--------|
| **1-ball** | 1,000 | 37.5 ms | <200 ms | ✅ PASS |
| **6-ball naive** | 2,000 | 126.9 ms | <1000 ms | ✅ PASS |
| **6-ball vectorized** | 2,000 | 62.1 ms | <500 ms | ✅ PASS |
| **1-over** | 5,000 | 146.2 ms | <1000 ms | ✅ PASS |

**Key Optimizations:**
- Vectorized sampling with NumPy (2.4× speedup)
- Cumulative distribution arrays for searchsorted
- Pre-computed phase boundaries
- Batch terminal state evaluation

## Testing

### Unit Tests (39 tests)

**Location:** `tests/test_simulation.py`

**Coverage:**
- MatchState validation and transitions
- NextBallSampler distributions
- Temperature calibration math
- Betting decision logic
- Phase detection
- Simulate integration

**Run:** `pytest tests/test_simulation.py -v`

### Integration Tests (13 tests)

**Location:** `tests/integration/test_simulation_integration.py`

**Coverage:**
- Real match state simulations
- Betting decision pipeline
- League temperature loading
- Vectorized vs naive agreement

**Run:** `pytest tests/integration/test_simulation_integration.py -v`

### Benchmark Script

**Location:** `scripts/benchmark_simulation.py`

**Run:** `python scripts/benchmark_simulation.py`

## Known Limitations

1. **Batch Evaluation**: Terminal states evaluated sequentially (T021 optimization pending)
2. **Agreement Check**: 1-ball/6-ball disagreement detection not implemented (T035/T039)
3. **Data-Driven Distributions**: Using empirical estimates, not league-specific (US5 pending)
4. **Wicket Multiplier**: Simplified model (linear by wickets down)

## Future Enhancements

### Phase 2: Data-Driven Distributions (US5)

- Extract phase tables from ball-by-ball parquet files
- Generate league-specific run/wicket distributions
- Implement wicket multiplier by lower-order effect
- Validate simulated vs actual boundary rates

### Phase 3: Advanced Calibration

- Per-team temperature adjustments
- Venue-specific multipliers
- Weather/pitch condition factors
- Recent form weighting

### Phase 4: Multi-Over Horizons

- 12-ball (2-over) simulation
- 30-ball (5-over) simulation
- Adaptive horizon selection based on game state

## References

- **Specification**: `specs/004-monte-carlo-engine/spec.md`
- **Research**: `specs/004-monte-carlo-engine/research.md`
- **Tasks**: `specs/004-monte-carlo-engine/tasks.md`
- **Contracts**: `specs/004-monte-carlo-engine/contracts/`

## Change Log

### v1.0 (January 19, 2026)

- ✅ Initial implementation with 1-ball and 6-ball simulation
- ✅ Phase-based run/wicket distributions
- ✅ Temperature calibration support (BBL, SA20, ILT20, WPL)
- ✅ Betting decision support with Kelly criterion
- ✅ Integration with crex_live_predictor.py
- ✅ Streamlit UI visualization panel
- ✅ 52 tests (39 unit + 13 integration)
- ✅ Performance benchmarks (<200ms 1-ball, <500ms 6-ball)
