# Implementation Plan: T20 Reduced-Over Match Support via Monte Carlo

**Branch**: `008-t20-reduced-overs` | **Date**: 2026-02-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/008-t20-reduced-overs/spec.md`

## Summary

Add support for rain-affected/DLS reduced-over T20 matches by adapting the Monte Carlo simulation engine. When `total_overs < 20`, the system bypasses the trained XGBLogRegEnsemble model (calibrated on 20-over data) and uses Monte Carlo simulation exclusively, with phase boundaries, par scores, and resource calculations scaled via DLS resource curves. Input comes from CREX auto-detection (near odds portal) with CLI fallback. MC output is calibrated via Platt scaling fitted on historical 20-over MC predictions for betting-grade log loss.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: XGBoost, scikit-learn, numpy, playwright (CREX scraping), joblib  
**Storage**: Parquet (match states), joblib/pickle (calibrators)  
**Testing**: pytest  
**Target Platform**: Windows (development), Linux (production)  
**Project Type**: Single Python package (`bbl_pipeline`)  
**Performance Goals**: Monte Carlo prediction cycle < 1 second for any match length (5-20 overs)  
**Constraints**: Zero regression on 20-over predictions; betting-grade calibration (log loss ≤ 0.55)  
**Scale/Scope**: 8 files modified, 2 new files, ~300 lines net new code

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Scalability & Reusability** | ✅ PASS | Spec explicitly calls out "configurable business logic rather than ad-hoc fixes." Reduced overs handled via `FormatConfig.t20_reduced(total_overs)` factory — tournament-agnostic, not hardcoded. Constitution text directly endorses: "handle edge cases (e.g., rain-outs, DLS method) through configurable business logic." |
| **II. Pipeline-Driven Architecture** | ✅ PASS | MC calibrator training is a pipeline step (backtest → fit → serialize). No monolithic scripts. |
| **III. Reproducibility & Versioning** | ✅ PASS | MC calibrator artifact is versioned alongside model artifacts. FormatConfig factory is deterministic. |
| **IV. Data Integrity & Entity Consistency** | ✅ PASS | `total_overs` and `revised_target` validated at input (5-20 range, positive integer). No new entity mappings needed. |
| **V. Model Calibration & Observability** | ⚠️ REVIEW | ECE < 0.0021 threshold applies to production models. MC predictions for reduced-over matches won't have enough historical data for strict ECE validation initially. **Justification**: MC calibrator is trained on 141K+ full-length samples and transfers structurally. Strict ECE can be validated post-deployment as reduced-over data accumulates. Log loss ≤ 0.55 is the primary gate. |
| **Code Quality** | ✅ PASS | Type hints on all new code. Unit tests for all modified/new functions. |

**Post-Phase 1 Re-check**: All gates pass. Principle V has documented justification for deferred strict ECE validation on reduced-over subset.

## Project Structure

### Documentation (this feature)

```text
specs/008-t20-reduced-overs/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research findings
├── data-model.md        # Phase 1: Entity model
├── quickstart.md        # Phase 1: Quick start guide
├── contracts/           # Phase 1: Internal contracts
│   └── reduced_over_config.md
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (NOT created by plan)
```

### Source Code (files to modify/create)

```text
src/bbl_pipeline/
├── simulation/
│   ├── state.py              # MODIFY: Add total_balls field, fix hardcoded 120
│   ├── config.py             # MODIFY: Dynamic phase boundaries for reduced overs
│   ├── evaluator.py          # MODIFY: Fix hardcoded 120 in 2 locations
│   └── engine.py             # MODIFY: Pass total_balls through to get_phase()
├── features/
│   ├── format_config.py      # MODIFY: Add t20_reduced() factory method
│   └── calculator.py         # NO CHANGE (already config-driven)
├── inference/
│   ├── crex_live_predictor.py # MODIFY: Add CREX DLS detection, CLI args, mode switch
│   ├── match_state_schema.py  # MODIFY: Add total_overs, revised_target fields
│   └── schema.py             # NO CHANGE (already has total_overs field)
└── calibration/
    └── mc_calibrator.py       # NEW: MC Platt scaling calibrator

scripts/
└── train_mc_calibrator.py     # NEW: Backtest MC on historical data, fit Platt

tests/
├── test_simulation.py         # MODIFY: Add reduced-over MatchState tests
├── test_reduced_overs.py      # NEW: Comprehensive reduced-over test suite
└── integration/
    └── test_simulation_integration.py  # MODIFY: Add reduced-over scenarios
```

**Structure Decision**: Single project structure. All changes are within the existing `bbl_pipeline` package. Two new files (`mc_calibrator.py`, `train_mc_calibrator.py`) plus one new test file. 8 existing files modified.

## Change Impact Analysis

### Layer 1: Simulation Core (no external dependencies)

| File | Change | Lines | Risk |
|------|--------|-------|------|
| `simulation/state.py` | Add `total_balls: int = 120` field; fix validation and `overs_completed` | ~15 | Medium — all simulation code creates MatchState |
| `simulation/config.py` | Add `get_phase_scaled()` or make boundaries dynamic | ~30 | Low — `get_phase` already accepts `total_balls` |
| `simulation/evaluator.py` | Replace `120 - state.balls_remaining` with `state.total_balls - state.balls_remaining` (2 locations) | ~4 | Low — direct substitution |
| `simulation/engine.py` | Pass `total_balls` to `get_phase()` calls; propagate in `simulate_vectorized()` | ~10 | Medium — vectorized path needs attention |

### Layer 2: Feature Configuration (depends on Layer 1)

| File | Change | Lines | Risk |
|------|--------|-------|------|
| `features/format_config.py` | Add `t20_reduced(total_overs)` factory; scale phase thresholds + par score via DLS | ~50 | Low — new factory, no existing code changes |

### Layer 3: Inference & Integration (depends on Layers 1-2)

| File | Change | Lines | Risk |
|------|--------|-------|------|
| `inference/crex_live_predictor.py` | Add DLS auto-detection regex/DOM parsing; CLI args `--total-overs`, `--revised-target`; mode switch logic | ~80 | High — largest file (1791 lines), CREX parsing is fragile |
| `inference/match_state_schema.py` | Add `total_overs` and `revised_target` to PyArrow schema | ~5 | Low |

### Layer 4: Calibration (independent, can be done in parallel)

| File | Change | Lines | Risk |
|------|--------|-------|------|
| `calibration/mc_calibrator.py` | New: Platt scaling wrapper for MC predictions | ~60 | Low — standard sklearn pattern |
| `scripts/train_mc_calibrator.py` | New: Backtest MC on training.parquet, fit calibrator | ~100 | Medium — needs MC engine + training data |

### Regression Risk

The primary regression risk is in MatchState validation. Adding `total_balls` field with default `120` ensures all existing code paths continue to work. The critical test: **when no `total_overs` is specified, the system must behave identically to today.**

## Implementation Order

```
Phase A: Simulation Core (Layer 1)
  ├─ A1: MatchState + total_balls field
  ├─ A2: evaluator.py hardcoded 120 fixes
  ├─ A3: engine.py total_balls propagation
  └─ A4: config.py dynamic phase boundaries

Phase B: FormatConfig (Layer 2) — depends on A
  └─ B1: t20_reduced() factory method

Phase C: Inference Integration (Layer 3) — depends on A+B
  ├─ C1: CLI args + mode switch logic
  ├─ C2: CREX DLS auto-detection
  └─ C3: Match state schema update

Phase D: MC Calibration (Layer 4) — parallel with B+C
  ├─ D1: mc_calibrator.py
  └─ D2: train_mc_calibrator.py script

Phase E: Testing — after all layers
  ├─ E1: Update existing tests (regression)
  └─ E2: New reduced-over test suite
```

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Deferred ECE < 0.0021 for reduced-over MC | Insufficient historical reduced-over data for strict ECE validation | Cannot fabricate real reduced-over outcomes; log loss ≤ 0.55 from 20-over backtest is the interim gate |

