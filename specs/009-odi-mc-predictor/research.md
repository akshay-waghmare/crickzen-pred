# Research: ODI Monte Carlo Standalone Predictor

**Feature**: `009-odi-mc-predictor`  
**Date**: 2026-02-28

## Research Questions & Findings

### RQ-1: MatchState total_balls validation (BLOCKER)

**Decision**: Extend `MatchState.__post_init__` validation from `6-120` to `6-300`.

**Rationale**: Current validation `6 <= self.total_balls <= 120` prevents ANY ODI simulation. The upper bound must become 300 (50 overs × 6 balls). The divisible-by-6 constraint remains correct.

**Alternatives considered**:
- Remove upper bound entirely → Rejected: allows nonsensical values (e.g., 10,000 balls)
- Use 600 (100 overs for Tests) → Rejected: Test match simulation is not in scope

**Impact**: 1-line change in `state.py:__post_init__`. No downstream breakage since all existing code uses total_balls ≤ 120.

---

### RQ-2: MC Sampler has no "setup" phase — 3-phase vs 4-phase mismatch

**Decision**: Add "setup" phase to MC sampler distributions (4 phases for ODI). The simulation's `get_phase()` must be updated to return 4 phases when `total_balls=300`.

**Rationale**: The `FormatConfig.odi()` defines 4 phases (powerplay, middle, setup, death) with distinct scoring patterns. The MC `config.py` only defines 3 phases. The `NextBallSampler` will `KeyError` crash if ever asked for "setup". The proportional scaling in `get_scaled_phase_boundaries()` was designed for reduced-over T20s and produces wrong ODI boundaries (PP=6 vs correct PP=10).

**Approach**: 
1. `get_phase()` gains a `format_config` or `phase_thresholds` parameter to use correct ODI boundaries
2. ODI phase distributions JSON includes 4 phases: `{"powerplay": {...}, "middle": {...}, "setup": {...}, "death": {...}}`
3. `sample_vectorized()` must iterate over whatever phases exist in the loaded distribution (not hardcoded 3)

**Alternatives considered**:
- Map "setup" → "middle" silently → Rejected: setup overs have distinctly different scoring patterns (5.7 RPO vs 4.9 RPO in middle)
- Use 3 phases for ODI too → Rejected: loses the setup/acceleration phase unique to 50-over cricket

---

### RQ-3: TerminalStateEvaluator always uses `FormatConfig.t20_reduced()` — crashes on ODI

**Decision**: `_get_calculator()` must detect ODI format and use `FormatConfig.odi()` instead of `FormatConfig.t20_reduced()`.

**Rationale**: Current code calls `FormatConfig.t20_reduced(total_overs)` which raises `ValueError` for `total_overs > 20`. When `total_balls=300`, it needs `FormatConfig.odi()` with all ODI-specific constants (par=257.7, DLS tables, wicket penalties, 4-phase system).

**Approach**: Add format detection logic:
```python
if total_balls > 120:
    config = FormatConfig.odi(gender)  # 300 balls = ODI
elif total_balls == 120:
    config = FormatConfig.t20()  # Standard T20
else:
    config = FormatConfig.t20_reduced(total_balls // 6)  # Reduced T20
```

**Alternatives considered**:
- Pass FormatConfig into TerminalStateEvaluator explicitly → Possible but requires API changes across the call chain
- Store format in MatchState → Adds complexity; total_balls is sufficient to infer format

---

### RQ-4: ODI empirical data availability for distribution extraction

**Decision**: Use the 3,085 ODI JSON files in `odis_json/` to extract empirical phase distributions.

**Rationale**: 
- `odis_json/` has 3,085 Cricsheet ODI match JSONs with full ball-by-ball data
- Standard Cricsheet format: each delivery has batter, bowler, runs (batter/extras/total), optional wicket
- This is MORE than enough data (3,000+ matches × ~300 balls = ~900,000 balls) for statistically significant phase distributions

**Approach**: Write `scripts/extract_odi_phase_distributions.py` that:
1. Reads all ODI JSONs from `odis_json/`
2. Assigns each ball to phase (PP: 1-10, Middle: 11-34, Setup: 35-40, Death: 41-50)
3. Counts run outcomes (0/1/2/3/4/5/6) per phase → probability vectors
4. Counts wicket events per phase → wicket probability per ball
5. Counts wicket events by wickets-down → wicket multiplier table
6. Outputs `phase_distributions_odi.json` in sampler-compatible format
7. Optionally splits by gender (male/female)

---

### RQ-5: MC calibrator `over_to_phase()` is T20-hardcoded

**Decision**: Add ODI-aware phase mapping to `InningsPhaseCalibrators`.

**Rationale**: The `over_to_phase(over)` helper in `mc_calibrator.py` hardcodes T20 boundaries (PP: 0-5, Mid: 6-14, Death: 15+). For ODI, it must map to PP: 0-9, Mid: 10-33, Setup: 34-39, Death: 40-49. The calibrator needs to know the format.

**Approach**: `over_to_phase()` gains an optional `total_overs` parameter. When `total_overs=50`, uses ODI phase boundaries.

**Alternatives considered**:
- Separate ODI calibrator class → Rejected: unnecessary code duplication
- Always use innings-only calibrators for ODI (no phase granularity) → Acceptable fallback initially; phase granularity can be added later

---

### RQ-6: MC-only mode without `--model-dir`

**Decision**: MC-only mode works without `--model-dir`. If model-dir is provided, load calibrators/distributions from there as optional enhancement. If omitted, use built-in `FormatConfig.odi()` defaults and embedded phase distributions.

**Rationale**: The core motivation is zero-dependency prediction. Requiring model-dir defeats the purpose. However, when model-dir IS available, calibrators significantly improve accuracy.

**Approach**: 
1. `crex_live_predictor.py` accepts `--mc-only` without requiring `--model-dir`
2. When no model-dir: use hardcoded ODI distributions (embedded in config.py or bundled data/)
3. When model-dir provided: attempt to load `phase_distributions_odi.json` and `mc_calibrator.pkl` from there
4. Graceful fallback at each step

---

### RQ-7: `sample_vectorized()` hardcodes 3 phases

**Decision**: Change the hardcoded `for phase in ("powerplay", "middle", "death")` loop to iterate over whatever phases exist in the loaded distribution.

**Rationale**: Currently line 174 of sampler.py iterates over a fixed tuple. For ODI with 4 phases, "setup" balls would be silently skipped (runs=0, no wicket), producing incorrect simulations.

**Approach**: Change to `for phase in self._run_values.keys()` or extract phases from the loaded distribution. Ensure any balls not matching a known phase get a sensible fallback (e.g., "middle").
