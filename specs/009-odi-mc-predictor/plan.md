# Implementation Plan: ODI Monte Carlo Standalone Predictor

**Branch**: `009-odi-mc-predictor` | **Date**: 2026-02-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/009-odi-mc-predictor/spec.md`

## Summary

Extend the existing Monte Carlo simulation engine to support ODI (50-over) cricket, enabling standalone `--mc-only` live predictions for any ODI/List A match without requiring a trained ML model or feature store. This requires:

1. **Unblocking ODI simulation** — Fix `MatchState` validation (120→300 balls), `TerminalStateEvaluator` (T20-only→format-aware), and phase system (3→4 phases)
2. **Empirical ODI distributions** — Extract phase-specific run/wicket probabilities from 3,085 Cricsheet ODI JSON files
3. **Zero-dependency predictor** — Make `--model-dir` optional in `--mc-only` mode; use built-in ODI defaults when no model artifacts available
4. **MC enrichments** (P3) — Partnership momentum, new batsman factor, pitch deterioration

Technical approach: modify 6 existing files and create 3 new files/scripts, leveraging the existing `FormatConfig.odi()` which already has all ODI constants (par=257.7, DLS tables, 4-phase system, wicket penalties).

## Technical Context

**Language/Version**: Python 3.13.7 (`requires-python = ">=3.10"`)  
**Primary Dependencies**: pandas>=2.0, numpy, scikit-learn>=1.3, xgboost>=2.0, joblib>=1.3, structlog>=23.0, playwright (for CREX scraping)  
**Storage**: Parquet files (features, match states), JSON (phase distributions, match data), joblib/pkl (models, calibrators)  
**Testing**: pytest (unit in `tests/unit/`, integration in `tests/integration/`, existing `test_simulation.py`)  
**Target Platform**: Windows/Linux desktop, CLI-driven  
**Project Type**: Single Python package (`src/bbl_pipeline/`)  
**Performance Goals**: <500ms per ball for 5,000 MC simulations; average ODI simulated total within ±10 runs of empirical mean (257.7)  
**Constraints**: MC-only Brier ≤ 0.185 (within 15% of ML model's 0.1609); ECE < 0.0021 is a stretch target (constitution requirement, justified relaxation for MC-only below)  
**Scale/Scope**: 3,085 ODI matches for distribution extraction (~900K balls), live prediction for any ODI match worldwide

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I — Scalability & Reusability: **PASS**
- Feature extends existing tournament-agnostic architecture (FormatConfig pattern)
- ODI support via configuration, not code rewrites — `FormatConfig.odi()` already exists
- Phase boundaries are parameterized, not hardcoded per-format
- Edge cases (reduced overs, DLS revised targets, super overs) addressed in spec

### Principle II — Pipeline-Driven Architecture: **PASS**
- Distribution extraction is a pipeline step (`scripts/extract_odi_phase_distributions.py`)
- Calibrator training follows existing OOF pipeline (`bbl-pipeline analyze-oof`)
- Live prediction integrates with existing `crex_live_predictor.py` CLI
- Retrain workflow: extract distributions → train calibrators → predict

### Principle III — Reproducibility & Versioning: **PASS**
- Phase distributions saved as versioned JSON files in model directory
- Calibrators saved as versioned `.pkl` artifacts
- Distribution extraction script is deterministic (same input → same output)
- Model registry updated with ODI MC artifacts

### Principle IV — Data Integrity & Entity Consistency: **PASS**
- Unknown teams handled gracefully (assumed 0.5 win rate in MC-only mode)
- Phase assignment uses validated ball counts, not string parsing
- Distribution JSON schema validated on load (sum-to-1.0 check, required keys)

### Principle V — Model Calibration & Observability: **CONDITIONAL PASS**
- **ECE < 0.0021 constraint**: This is a stretch target for MC-only mode. MC-only predictions are inherently less precise than ML+calibration models. The spec targets Brier ≤ 0.185 (within 15% of ML model). ECE optimization via per-phase isotonic calibrators is included in the design but may not achieve 0.0021 for a first-principles simulation approach.
- **Justification**: MC-only mode serves matches where NO ML prediction is possible (unknown teams). Any calibrated prediction is better than no prediction. The ECE threshold applies to production ML models; MC-only is an explicit fallback with understood accuracy tradeoffs.
- Live monitoring: `--record-states` captures all MC predictions with calibration chain for post-hoc analysis

## Project Structure

### Documentation (this feature)

```text
specs/009-odi-mc-predictor/
├── plan.md              # This file
├── spec.md              # Feature specification (6 user stories, 12 FRs)
├── research.md          # Phase 0 research (7 RQs resolved)
├── data-model.md        # Phase 1 entity definitions (5 entities)
├── quickstart.md        # Phase 1 implementation guide
├── contracts/
│   └── contracts.md     # Phase 1 API contracts (7 contracts)
├── checklists/
│   └── requirements.md  # Requirements validation checklist
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/bbl_pipeline/
├── simulation/
│   ├── state.py              # MODIFY: Extend total_balls validation to 300
│   ├── config.py             # MODIFY: Add ODI 4-phase system, ODI constants
│   ├── sampler.py            # MODIFY: Dynamic phase iteration, 4-phase support
│   ├── evaluator.py          # MODIFY: ODI format detection in _get_calculator()
│   ├── engine.py             # No changes needed (format-agnostic)
│   └── feature_context.py    # No changes needed
├── calibration/
│   └── mc_calibrator.py      # MODIFY: ODI-aware over_to_phase()
├── inference/
│   └── crex_live_predictor.py  # MODIFY: MC-only without model-dir for ODI
└── features/
    └── format_config.py      # No changes needed (FormatConfig.odi() exists)

scripts/
└── extract_odi_phase_distributions.py  # NEW: Extract distributions from ODI JSONs

tests/
├── unit/
│   └── test_odi_mc.py        # NEW: Unit tests for ODI MC components
└── integration/
    └── test_odi_predictor.py  # NEW: End-to-end ODI MC prediction test
```

**Structure Decision**: Single project extending existing `src/bbl_pipeline/` package. No new packages or modules needed — all changes are modifications to existing simulation/calibration/inference modules plus one new extraction script and test files.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| ECE < 0.0021 not guaranteed for MC-only | MC-only is a first-principles fallback for matches with unknown teams; inherently less precise than calibrated ML models | Requiring ECE < 0.0021 would block deployment of any MC-only predictions, leaving these matches with NO coverage at all. MC-only Brier ≤ 0.185 (within 15% of ML) is the practical target. |

## Implementation Phases

### Phase A: Core Simulation Unblocking (P1 — Stories 1, 2, 4)

**Goal**: Enable ODI simulation end-to-end without crashes

| Step | File | Change | Effort |
|:----:|------|--------|:------:|
| A.1 | `simulation/state.py` | Change `total_balls` upper bound from 120 to 300 | 5 min |
| A.2 | `simulation/config.py` | Add `ODI_PHASES`, `get_odi_phase_boundaries()`, update `get_phase()` for 4-phase ODI | 30 min |
| A.3 | `simulation/evaluator.py` | Add format detection: `total_balls > 120` → `FormatConfig.odi()` | 15 min |
| A.4 | `simulation/sampler.py` | Dynamic phase iteration from loaded distribution keys, not hardcoded tuple | 30 min |
| A.5 | `tests/unit/test_odi_mc.py` | Unit tests: MatchState(300), get_phase(ODI), sampler with 4 phases, evaluator with odi config | 45 min |

**Verification**: `MatchState(total_balls=300)` creates without error; `get_phase()` returns correct ODI phases; MC simulation of 300-ball innings completes without crash.

### Phase B: Empirical ODI Phase Distributions (P1/P2 — Story 5)

**Goal**: Extract real ODI scoring patterns from 3,085 Cricsheet JSONs

| Step | File | Change | Effort |
|:----:|------|--------|:------:|
| B.1 | `scripts/extract_odi_phase_distributions.py` | New script: parse ODI JSONs, assign balls to 4 phases, compute run/wicket distributions | 1.5 hr |
| B.2 | Run extraction | `python scripts/extract_odi_phase_distributions.py --input-dir odis_json --output data/phase_distributions_odi.json --gender male` | 10 min |
| B.3 | Embed defaults in `simulation/config.py` | Add `ODI_RUN_DIST` and `ODI_WICKET_PROB` constants from extracted data as fallback | 20 min |
| B.4 | Validate distributions | Verify average simulated ODI total ≈ 257.7 (±10 runs) over 100K simulations | 20 min |

**Verification**: Generated `phase_distributions_odi.json` has 4 phases, run probabilities sum to 1.0, wicket rates match published ODI statistics (~3-5% per ball overall).

### Phase C: MC-Only ODI Live Prediction (P1 — Stories 1, 3)

**Goal**: Run `crex_live_predictor.py --mc-only` for ODI matches without model-dir

| Step | File | Change | Effort |
|:----:|------|--------|:------:|
| C.1 | `inference/crex_live_predictor.py` | Make `--model-dir` optional when `--mc-only`; detect ODI format from `total_overs >= 40` | 45 min |
| C.2 | `inference/crex_live_predictor.py` | Pass `FormatConfig.odi()` through MC pipeline; use ODI distributions | 30 min |
| C.3 | `calibration/mc_calibrator.py` | Add `total_overs` param to `over_to_phase()`; support ODI phase boundaries | 30 min |
| C.4 | `inference/crex_live_predictor.py` | Ensure `--record-states` works in MC-only ODI mode (FR-011) | 30 min |
| C.5 | `tests/integration/test_odi_predictor.py` | Integration test: simulate full ODI match prediction pipeline | 45 min |

**Verification**: `python -m src.bbl_pipeline.inference.crex_live_predictor --mc-only --match-url <ODI_URL>` produces win probabilities in 5-95% range without crashes.

### Phase D: MC Calibration for ODI (P2 — Story 3, FR-007)

**Goal**: Train Platt/isotonic calibrators to improve raw MC probabilities

| Step | File | Change | Effort |
|:----:|------|--------|:------:|
| D.1 | `scripts/train_odi_mc_calibrator.py` | New script: run MC on historical ODI matches, fit Platt/isotonic calibrators on OOF data | 1.5 hr |
| D.2 | Run calibrator training | OOF cross-validation on ODI training data | 30 min |
| D.3 | Integrate calibrators | Load `mc_calibrator.pkl` in predictor when available | 30 min |

**Verification**: Calibrated MC Brier score ≤ 0.185 on held-out ODI matches.

### Phase E: MC Enrichments (P3 — Story 6)

**Goal**: State-of-the-art simulation features for improved accuracy

| Step | Feature | Description | Effort |
|:----:|---------|-------------|:------:|
| E.1 | Partnership momentum | Increase boundary probability for established partnerships (100+ runs) | 1 hr |
| E.2 | New batsman factor | Elevated dot ball probability for first 10 balls faced | 1 hr |
| E.3 | Pitch deterioration | Wicket probability modifier based on innings progression | 45 min |
| E.4 | Backtesting | Compare enriched vs base MC on 100+ completed ODI matches | 1 hr |

**Verification**: Each enrichment demonstrates ≥0.5% Brier reduction in backtesting (SC-006).

## Dependencies & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Extracted ODI distributions may not perfectly reproduce average totals | MC accuracy suffers | Validate against 257.7 target; adjust distributions if needed |
| CREX ODI page structure may differ from T20 | Scraper fails | Test against 3+ different ODI match URLs before release |
| MC-only predictions may be too noisy for short horizons (first few overs) | Poor early-match predictions | Use longer horizon (12+ balls) in early overs; document known limitation |
| ECE < 0.0021 may be unachievable for MC-only | Constitution compliance | Documented as justified deviation; MC-only is explicit fallback mode |

## Estimated Total Effort

| Phase | Priority | Effort |
|:-----:|:--------:|:------:|
| A: Core Simulation Unblocking | P1 | ~2.5 hr |
| B: Empirical Distributions | P1/P2 | ~2.5 hr |
| C: MC-Only Live Prediction | P1 | ~3 hr |
| D: MC Calibration | P2 | ~2.5 hr |
| E: MC Enrichments | P3 | ~4 hr |
| **Total** | | **~14.5 hr** |

P1 deliverables (Phases A+B+C) provide a working ODI MC predictor in ~8 hours.
