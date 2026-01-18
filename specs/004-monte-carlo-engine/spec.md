# Feature Specification: Monte Carlo Simulation Engine

**Feature Branch**: `004-monte-carlo-engine`  
**Created**: 2026-01-19  
**Status**: Draft  
**Input**: Build Monte Carlo simulation engine for T20 win probability with next-ball outcome sampling, state transitions, and league temperature calibration integration

## Overview

Build a Monte Carlo simulation engine that provides forward-looking win probability distributions by simulating ball-by-ball outcomes. This complements the existing ML-based win probability model by providing uncertainty quantification and multi-ball lookahead capabilities for betting decisions.

**Key Components**:
1. **Next-ball outcome sampler** - Generates runs (0/1/2/3/4/6) and wicket probabilities based on phase/pressure
2. **Match state manager** - Tracks score, wickets, balls remaining, and target
3. **Simulation loop** - Runs N simulations forward by 1-ball or 6-balls
4. **League temperature integration** - Applies league-specific T₁/T₂ calibration to final probabilities

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Single Ball Simulation for Timing/Hedging (Priority: P1)

As a betting analyst, I want to simulate the next ball's win probability distribution so I can time my hedge decisions with confidence intervals.

**Why this priority**: Single ball simulation is the simplest use case and provides immediate value for in-play timing decisions. Forms the foundation for multi-ball simulation.

**Independent Test**: Can be tested by providing a match state (score=110, wickets=4, balls_remaining=48, target=170) and receiving a mean ± std win probability after 2000 simulations.

**Acceptance Scenarios**:

1. **Given** a match state (innings=2, score=110, wickets=4, balls_remaining=48, target=170), **When** I simulate 1 ball forward 2000 times, **Then** I receive mean win probability and standard deviation within 200ms (or 100ms with vectorization/caching enabled).
2. **Given** a high-pressure chase state (RRR=12, 3 wickets in hand), **When** I simulate 1 ball, **Then** the win probability distribution is wider (σ > 0.08) reflecting uncertainty.
3. **Given** an easy chase state (RRR=5, 8 wickets in hand), **When** I simulate 1 ball, **Then** the win probability distribution is narrower (σ < 0.05) reflecting certainty.

---

### User Story 2 - Six Ball (1 Over) Simulation for Betting Decisions (Priority: P1)

As a betting analyst, I want to simulate the next over's win probability distribution so I can make informed betting decisions with edge and confidence thresholds.

**Why this priority**: One-over lookahead is the primary use case for betting - it provides enough forward visibility to identify edge while being computationally tractable.

**Independent Test**: Can be tested by running 6-ball simulation and comparing μ₆ and σ₆ against expected ranges based on match state.

**Acceptance Scenarios**:

1. **Given** a match state, **When** I simulate 6 balls forward 2000 times, **Then** I receive mean win probability, std deviation, and 90% confidence interval.
2. **Given** death overs state (over 16-20), **When** I simulate 6 balls, **Then** the run distribution shows higher boundary probability and higher wicket probability.
3. **Given** σ₆ > 0.10 (high uncertainty), **When** applying betting rules, **Then** the system flags "do not bet" or requires higher edge threshold.

---

### User Story 3 - League Temperature Calibration Integration (Priority: P2)

As a system operator, I want simulated probabilities to be calibrated with league-specific temperature scaling so predictions are consistent with our production models.

**Why this priority**: Without league calibration, simulated probabilities will be miscalibrated vs production. This ensures consistency but is not required for core simulation functionality.

**Independent Test**: Can be tested by comparing calibrated vs uncalibrated simulation outputs for BBL (T=0.83) and SA20 (T=0.77) and verifying expected probability shifts.

**Acceptance Scenarios**:

1. **Given** SA20 innings 2 simulation (T₂=0.765), **When** I apply temperature calibration, **Then** probabilities become sharper (more confident) by expected amount.
2. **Given** BBL innings 1 simulation (T₁=0.847), **When** I apply temperature calibration, **Then** probabilities shift correctly per the calibrator.
3. **Given** an uncalibrated probability of 0.60, **When** applying T=0.8, **Then** calibrated probability is approximately 0.624 (logit(0.60)/0.8 = 0.506, sigmoid(0.506) = 0.624).

---

### User Story 4 - Betting Decision Support with Guardrails (Priority: P2)

As a betting analyst, I want clear decision support based on simulation outputs so I know when to bet, when to hedge, and when to pass.

**Why this priority**: Transforms raw simulation output into actionable betting signals. Valuable but requires core simulation engine first.

**Independent Test**: Can be tested by providing simulation outputs and verifying correct bet/pass decisions based on threshold rules.

**Acceptance Scenarios**:

1. **Given** μ₆=0.62, σ₆=0.06, market_odds=1.60 (implied 62.5%), **When** evaluating bet, **Then** system calculates edge and recommends "BET" (σ₆ ≤ phase threshold, edge ≥ phase minimum).
2. **Given** μ₆=0.55, σ₆=0.12 in innings 2 death phase, **When** evaluating bet, **Then** system recommends "PASS" (σ₆ > SIGMA_MAX[inn2][death] threshold).
3. **Given** μ₁=0.65, μ₆=0.55 (disagreement in direction), **When** evaluating bet, **Then** system recommends "PASS" (1-ball and 6-ball means disagree).
4. **Given** innings 1 middle phase, **When** evaluating bet with edge=25%, **Then** system recommends "PASS" (edge < EDGE_MIN[inn1][middle] = 30%).

---

### User Story 5 - Data-Driven Outcome Probabilities (Priority: P3)

As a data scientist, I want next-ball outcome probabilities to be learned from historical data so simulations are realistic rather than using fixed lookup tables.

**Why this priority**: Improves simulation realism significantly, but requires model training. Can start with fixed tables and upgrade later.

**Independent Test**: Can be tested by training wicket/runs models on historical data and comparing simulated outcome distributions against actual historical distributions.

**Acceptance Scenarios**:

1. **Given** historical ball-by-ball data, **When** I train a wicket probability model, **Then** predicted wicket rates match actual rates by phase (±5%).
2. **Given** trained runs distribution model, **When** sampling runs in death overs, **Then** boundary percentage matches historical death over data (±10%).
3. **Given** player-specific modifiers (high SR batter), **When** sampling outcomes, **Then** boundary probability increases appropriately.

---

### Edge Cases

- What happens when all 10 wickets fall during simulation? → Innings ends, return current win probability.
- What happens when balls remaining reaches 0? → Innings ends, compute final result.
- What happens when target is chased during simulation? → Match ends, return 1.0 win probability.
- How does system handle super overs? → Out of scope for v1; return uncertainty flag.
- What if temperature calibrator is not available for a league? → Use T=1.0 (no adjustment).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `MatchState` class that tracks innings, score, wickets_lost, balls_remaining, and target_runs.
- **FR-002**: System MUST provide a `NextBallSampler` class that returns (runs, wicket) tuple based on phase and pressure.
- **FR-003**: System MUST implement phase-based run distributions (powerplay/middle/death) with configurable probabilities.
- **FR-004**: System MUST adjust wicket probability based on pressure_index (0.0-1.0 scale).
- **FR-005**: System MUST provide a `simulate_n_balls()` function that runs N simulations forward by specified number of balls.
- **FR-006**: System MUST return mean, std deviation, and 5th/95th percentiles from simulations (percentile-based CI is more robust than assuming normality).
- **FR-007**: System MUST integrate with existing `ResourceFeatureCalculator` for state evaluation. Evaluation occurs only at the terminal state (after N balls simulated), not at intermediate steps.
- **FR-008**: System MUST support league temperature calibration via `apply_temperature(p, T)` function. Temperature is applied to the `resource_win_prob` output from the evaluator at terminal states, NOT inside the sampler (temperature calibrates confidence of win probability, not per-ball physics).
- **FR-009**: System MUST complete 2000 simulations of 6 balls each in under 500ms for real-time use (with caching/vectorization; 1000ms acceptable for naive implementation).
- **FR-010**: System MUST handle innings termination (all out or target chased) during simulation.
- **FR-011**: System MUST provide phase-aware betting thresholds via config: `EDGE_MIN_BY_PHASE[innings][phase]` and `SIGMA_MAX_BY_PHASE[innings][phase]`.
- **FR-012**: System MUST provide a unified simulation API: `simulate(state, horizon_balls=1|6|30, n_sims=2000, league="bbl")` supporting variable horizons.

### Key Entities

- **MatchState**: Current match situation - innings (1/2), score, wickets_lost, balls_remaining, target_runs (if innings 2), league, batting_team, bowling_team
- **BallOutcome**: Result of a simulated ball - runs (0/1/2/3/4/6), is_wicket (bool), extras (optional)
- **BettingThresholds**: Phase-aware config - EDGE_MIN_BY_PHASE (e.g., inn2_death=15%, inn1_middle=30%), SIGMA_MAX_BY_PHASE (e.g., default=0.10)
- **SimulationResult**: Aggregated simulation output - mean_prob, std_prob, confidence_interval, n_simulations, time_taken_ms
- **NextBallSampler**: Outcome generator - phase-based run/wicket probabilities, pressure modifiers, optional player modifiers
- **BettingDecision**: Recommendation output - action (BET/PASS/HEDGE), edge, confidence, reasons

## Assumptions

1. Existing `ResourceFeatureCalculator.calculate_all_features()` provides accurate state evaluation including `resource_win_prob` and `pressure_index`.
2. League temperature calibrators (T₁, T₂) are available in `models/t20_male_v1/league_calibrators/<league>/`.
3. Initial version uses fixed phase-based probability tables; data-driven models can be added later.
4. Super overs are out of scope for v1.
5. Extras (wides, no-balls) can be ignored in v1 or treated as +1 run with no wicket. **Note**: Ignoring extras makes simulation slightly conservative in chases (actual scoring rate ~5% higher due to extras).
6. All 10 wickets falling ends the innings regardless of balls remaining.
7. Default betting thresholds: Inn2 death=15% edge, Inn1 middle=30% edge, σ_max=0.10 (configurable).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: System completes 2000 simulations of 6 balls each in under 500ms on standard hardware.
- **SC-002**: Simulated run distributions match historical phase distributions within 10% (powerplay boundaries, death over scoring rates).
- **SC-003**: Simulated wicket rates match historical rates within 15% by phase.
- **SC-004**: Temperature-calibrated simulation outputs match production model outputs within 2% for static states.
- **SC-005**: Betting decisions based on phase-aware σ₆ thresholds reduce false signals by 30% compared to point estimates alone.
- **SC-006**: 1-ball and 6-ball agreement filter reduces bad bets by 20% compared to 6-ball only.
- **SC-007**: Phase-aware edge thresholds (Inn2 death=15%, Inn1 middle=30%) improve ROI by 15% vs flat thresholds.

## Simulation Horizon API *(mandatory)*

The simulation engine MUST expose a single unified API supporting variable horizons:

```
simulate(
    state: MatchState,
    horizon_balls: int = 6,      # 1, 6, or 30 balls forward
    n_sims: int = 2000,          # Number of Monte Carlo paths
    league: str = "bbl"          # For temperature calibration
) -> SimulationResult
```

**Horizon Options**:
- `horizon_balls=1`: Single ball lookahead for timing/hedging decisions
- `horizon_balls=6`: One over lookahead for primary betting decisions  
- `horizon_balls=30`: Five over lookahead for strategic analysis (v2)

**Returns**: `SimulationResult` with mean_prob, std_prob, p5, p95, n_sims, time_taken_ms

## Out of Scope

- Super over simulation
- Player-specific batting/bowling models (v1 uses phase averages)
- Live integration with betting platforms
- Historical backtesting framework
- Visualization/UI components
