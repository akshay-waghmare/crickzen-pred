# Implementation Plan: Monte Carlo Simulation Engine

**Branch**: `004-monte-carlo-engine` | **Date**: 2026-01-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-monte-carlo-engine/spec.md`

## Summary

Build a Monte Carlo simulation engine that provides forward-looking win probability distributions by simulating ball-by-ball outcomes. The engine complements the existing XGBLogRegEnsemble model by providing uncertainty quantification (σ, percentiles) and multi-ball lookahead capabilities for betting decisions.

**Technical Approach**: 
- NumPy-vectorized simulation loop for performance (2000 sims × 6 balls < 500ms)
- Phase-based outcome tables from historical data
- Terminal state evaluation via existing `ResourceFeatureCalculator`
- League temperature calibration via `TemperatureScaler` integration

## Technical Context

**Language/Version**: Python 3.10+ (from pyproject.toml)  
**Primary Dependencies**: NumPy (vectorization), Pandas (data), joblib (serialization), existing bbl_pipeline  
**Storage**: N/A (in-memory simulation, optional pickle caching)  
**Testing**: pytest (existing test infrastructure in `/tests/`)  
**Target Platform**: Linux/Windows, CPU-only (no GPU required)  
**Project Type**: Single project - extends existing `src/bbl_pipeline/` package  
**Performance Goals**: 2000 sims × 6 balls < 500ms (optimized), < 1000ms (naive)  
**Constraints**: Must integrate with existing `ResourceFeatureCalculator` and `TemperatureScaler`  
**Scale/Scope**: Real-time betting use case, single-match simulation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Scalability & Reusability | ✅ PASS | League-agnostic via temperature calibration; phase tables are configurable |
| II. Pipeline-Driven Architecture | ✅ PASS | Simulation is a discrete module; can be added to inference pipeline |
| III. Reproducibility & Versioning | ✅ PASS | Seeded RNG for reproducibility; phase tables versioned |
| IV. Data Integrity & Entity Consistency | ✅ PASS | Uses existing entity mappings; no new entity normalization needed |
| V. Model Calibration & Observability | ✅ PASS | Temperature calibration from production; logging of simulation stats |

**No violations detected.** Constitution gate passed.

## Project Structure

### Documentation (this feature)

```text
specs/004-monte-carlo-engine/
├── plan.md              # This file
├── research.md          # Phase 0: outcome distribution research
├── data-model.md        # Phase 1: MatchState, SimulationResult schemas
├── quickstart.md        # Phase 1: usage examples
├── contracts/           # Phase 1: API contracts
│   └── simulation-api.yaml
└── tasks.md             # Phase 2: implementation tasks (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/bbl_pipeline/
├── simulation/          # NEW: Monte Carlo engine
│   ├── __init__.py
│   ├── state.py         # MatchState dataclass
│   ├── sampler.py       # NextBallSampler with phase tables
│   ├── engine.py        # simulate() main API
│   ├── evaluator.py     # Terminal state evaluation wrapper
│   ├── betting.py       # BettingThresholds, BettingDecision
│   └── config.py        # Phase tables, thresholds config
├── features/
│   └── calculator.py    # Existing - ResourceFeatureCalculator
├── training/
│   └── league_calibrator.py  # Existing - TemperatureScaler
└── inference/           # Existing - may integrate later

tests/
├── unit/
│   └── simulation/      # NEW: unit tests
│       ├── test_state.py
│       ├── test_sampler.py
│       └── test_engine.py
└── integration/
    └── test_simulation_integration.py  # NEW
```

**Structure Decision**: Single project, new `simulation/` subpackage under existing `src/bbl_pipeline/`

## Complexity Tracking

> No constitution violations - table not required.

---

## Phase 0: Research

### Research Tasks

1. **Historical run distribution by phase** - Extract actual run probabilities (0/1/2/3/4/6) from BBL/SA20 ball-by-ball data for powerplay, middle, death phases
2. **Historical wicket rates by phase** - Extract actual wicket rates by phase and pressure level
3. **Performance optimization patterns** - NumPy vectorization strategies for Monte Carlo
4. **ResourceFeatureCalculator interface** - Document required inputs/outputs for terminal evaluation

### Findings

See [research.md](research.md) for detailed research outputs.

---

## Phase 1: Design & Contracts

### Data Model

See [data-model.md](data-model.md) for entity schemas:
- `MatchState` - innings, score, wickets_lost, balls_remaining, target_runs, etc.
- `BallOutcome` - runs, is_wicket
- `SimulationResult` - mean_prob, std_prob, p5, p95, n_sims, time_taken_ms
- `BettingThresholds` - EDGE_MIN_BY_PHASE, SIGMA_MAX_BY_PHASE
- `BettingDecision` - action, edge, confidence, reasons

### API Contracts

See [contracts/simulation-api.yaml](contracts/simulation-api.yaml) for:
- `simulate(state, horizon_balls, n_sims, league) -> SimulationResult`
- `evaluate_bet(sim_result, market_odds, innings, phase) -> BettingDecision`

### Quickstart

See [quickstart.md](quickstart.md) for usage examples.

---

## Phase 2: Implementation Tasks

*Generated by `/speckit.tasks` command - not part of this planning phase.*

See [tasks.md](tasks.md) (to be created).
