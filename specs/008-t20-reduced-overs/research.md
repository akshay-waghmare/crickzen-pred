# Research: T20 Reduced-Over Match Support

**Feature**: 008-t20-reduced-overs  
**Date**: 2026-02-21

## R1: Where are the hardcoded 120/20 references?

**Decision**: 6 hardcoded locations must change; 2 are already parameterized.

**Findings**:

| File | Line | Code | Status |
|------|------|------|--------|
| `simulation/state.py` | L56 | `0 <= self.balls_remaining <= 120` | Must change |
| `simulation/state.py` | L64 | `(120 - self.balls_remaining) / 6` | Must change |
| `simulation/evaluator.py` | L184 | `balls_bowled = 120 - state.balls_remaining` | Must change |
| `simulation/evaluator.py` | L273 | `balls_bowled = 120 - br` (vectorized) | Must change |
| `simulation/config.py` | L25 | `get_phase(total_balls=120)` default | Already parameterized ✅ |
| `features/calculator.py` | All methods | Uses `self.TOTAL_OVERS` / `self.TOTAL_BALLS` | Already config-driven ✅ |

**Rationale**: The simulation layer has the most hardcoding. The feature calculator is clean because it reads from FormatConfig. The core fix is adding `total_balls` to `MatchState` in the simulation layer.

## R2: Can FormatConfig support reduced overs?

**Decision**: Yes — create a new factory method `FormatConfig.t20_reduced(total_overs)`.

**Findings**:
- `FormatConfig` is `@dataclass(frozen=True)` — immutable after creation, but new instances are fine
- `__post_init__` validates: `total_balls == total_overs * 6`, `total_wickets == 10`, last phase threshold must equal `total_overs`
- T20 factory has `phase_thresholds={"powerplay": 6, "middle": 14, "death": 18, "final": 20}` — last must equal total_overs
- DLS resource table keys go from 0.0 to 20.0 — reduced overs (5-19) are within range, interpolation works
- Constructor validates `total_balls == total_overs * balls_per_over` — a 15-over config with `total_balls=90` would pass

**Alternatives considered**:
- Mutating existing config: Rejected — frozen dataclass
- Scaling at call sites: Rejected — fragile, violates DRY

## R3: How should phase boundaries scale for reduced overs?

**Decision**: Proportional scaling with minimums.

**Scaling formula**:
- Powerplay: `max(2, min(6, round(total_overs * 0.30)))` → e.g., 15-over = 5, 10-over = 3, 7-over = 2
- Death starts at: `total_overs - max(2, round(total_overs * 0.25)) + 1` → e.g., 15-over: death at 12, 10-over: death at 8
- Middle: everything between
- Final: always equals total_overs (validation requirement)

**Phase boundary table**:

| Overs | Powerplay (1-N) | Middle | Death starts | Final |
|:-----:|:---------------:|:------:|:------------:|:-----:|
| 20 | 6 | 7-15 | 16 | 20 |
| 18 | 5 | 6-14 | 15 | 18 |
| 15 | 5 | 6-11 | 12 | 15 |
| 12 | 4 | 5-9 | 10 | 12 |
| 10 | 3 | 4-7 | 8 | 10 |
| 7 | 2 | 3-5 | 6 | 7 |
| 5 | 2 | 3 | 4 | 5 |

**Rationale**: ICC powerplay is 6 overs in a 20-over game (30%), so 30% scaling is consistent. Death is the last 25% (5/20). Minimums prevent degenerate cases where a phase has 0 overs.

## R4: How does par score scale for reduced overs?

**Decision**: Use existing DLS resource table in FormatConfig, not linear scaling.

**Findings**:
- `FormatConfig.t20()` includes a full DLS resource table mapping `wickets_lost → {overs_remaining: resource_pct}`
- `ResourceFeatureCalculator.calculate_resource_percentage()` interpolates this table
- For 0 wickets, 15 overs remaining: DLS resource ≈ 83% → par ≈ 135 (not 120 from linear 75%)
- The calculator already uses `self.PAR_SCORE_T20` from config
- A reduced FormatConfig with `par_score = 160 * dls_resource_pct(total_overs, wickets=0)` would be correct

**Alternatives considered**:
- Linear scaling (par * overs/20): Rejected — underestimates, doesn't match DLS
- New resource curve: Rejected — existing DLS table is standard and sufficient

## R5: Where does CREX show DLS/reduced-over data?

**Decision**: Parse from the match page near the odds portal area. Specific selectors need runtime validation.

**Findings**:
- CREX shows "Target: X (DLS)" or "Revised Target: X" text when DLS is applied
- The scraper already intercepts `sV3` API responses — may contain total overs in match metadata
- Current scraper has NO DLS-related parsing (no regex for "revised", "dls", "reduced")
- The `sV3` response field `R` contains odds data; adjacent fields may have match configuration
- Fallback: DOM text search for patterns like `r'(?:revised\s+)?target\s*:\s*(\d+)\s*\(?dls\)?'`

**Rationale**: CREX is the data source we already scrape. Adding a regex/DOM lookup for DLS info is minimal work. CLI override provides a safety net.

## R6: How should MC calibration work?

**Decision**: Platt scaling fitted on MC predictions from historical 20-over matches.

**Approach**:
1. Run Monte Carlo on 141K+ historical T20 ball states (from existing training.parquet)
2. Collect MC raw predictions vs actual match outcomes (binary: batting team won or not)
3. Fit Platt scaling (logistic regression on logit of MC prediction) per phase or per innings
4. Store calibrator as `mc_calibrator.pkl` alongside model artifacts
5. Apply at inference time: `calibrated_prob = platt_calibrator.predict_proba(mc_raw_prob)`

**Why Platt over isotonic**: MC predictions are smoother than ensemble model predictions (they come from averaging thousands of simulation paths). Platt's 2-parameter model is sufficient — isotonic's flexibility isn't needed and could overfit with the narrower MC output distribution.

**Why not temperature**: Temperature is a single parameter (T) that only scales confidence. MC may have a systematic bias (e.g., always optimistic by 2pp) which needs the intercept term that Platt provides.

**Rationale**: MC's biases are structural — over/under-confidence at different game stages comes from the run distribution assumptions, not match length. A calibrator fitted on 20-over MC data transfers to 15-over MC data.

## R7: What test changes are needed?

**Decision**: Update existing tests + add reduced-over-specific tests.

**Findings**:
- `tests/test_simulation.py` (1009 lines): Has `TestMatchState` that validates balls_remaining range 0-120 — needs updating
- `tests/integration/test_simulation_integration.py`: Real match scenarios — add reduced-over scenarios
- `tests/test_resource_features.py`: ResourceFeatureCalculator tests — add reduced config tests
- No existing reduced-over tests exist

**New tests needed**:
1. `MatchState` accepts `total_balls=90` and validates `0 <= balls_remaining <= 90`
2. Phase classification for 15-over, 10-over, 5-over matches
3. Par score scaling matches DLS expectations
4. Monte Carlo simulation completes for reduced-over states
5. 20-over behavior is identical (regression)
