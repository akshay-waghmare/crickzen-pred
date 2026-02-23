# MC Platt Calibration Fix

**Date**: February 2026  
**Commit**: `1d40974`  
**Status**: Fixed & Verified ✅

## Summary

Fixed a critical bug where Monte Carlo Platt calibration (`InningsMCCalibrators`) was being applied to individual binary terminal states (0s and 1s) instead of the aggregated mean probability. This caused calibrated MC output to be identical to raw MC output.

## The Bug

### Root Cause

In both `simulate()` and `simulate_vectorized()` in `engine.py`, the calibration was applied via `calibrate_batch()` to the full array of terminal probabilities:

```python
# BEFORE (broken)
terminal_probs = mc_cal.calibrate_batch(terminal_probs, state.innings)
# terminal_probs contains binary 0s and 1s from terminal state evaluation
```

### Why It Failed

Platt scaling applies `sigmoid(a * logit(p) + b)` to each probability. When the input is binary:
- `logit(0) = -∞` → `sigmoid(a * -∞ + b) ≈ 0`
- `logit(1) = +∞` → `sigmoid(a * +∞ + b) ≈ 1`

The calibrator effectively returned the same 0/1 values, making `MC_CAL == MC_RAW`.

### How It Was Discovered

Backtest analysis showed `MC_CAL_LL` and `MC_RAW_LL` columns were identical across all segments. Manual inspection with `inspect_mc_calibrator.py` confirmed the calibrators themselves were valid (e.g., `p=0.50 → Inn1: 0.6599, Inn2: 0.4496`), pointing to incorrect application rather than broken calibrators.

## The Fix

### Approach

Changed both `simulate()` and `simulate_vectorized()` to:
1. **Capture** `raw_mean = np.mean(terminal_probs)` before calibration
2. **Build** `SimulationResult` from raw terminal probs (preserving `std`, `p5`, `p95` from the raw distribution)
3. **Apply** calibration to the aggregated mean: `mc_cal.calibrate(result.mean_prob, state.innings)`

```python
# AFTER (correct)
raw_mean = float(np.mean(terminal_probs))  # Save pre-calibration

result = SimulationResult.from_probs(probs=terminal_probs, ..., raw_mean=raw_mean)

# Apply calibration to the final mean (continuous value, not binary)
mc_cal = _load_mc_calibrator(model_dir)
if mc_cal is not None:
    result.mean_prob = mc_cal.calibrate(result.mean_prob, state.innings)
    result.mean_prob = float(np.clip(result.mean_prob, 0.0, 1.0))
```

### Why This Is Correct

- Platt scaling expects a **continuous probability** as input (0.0-1.0)
- The aggregated mean from N simulations IS a continuous probability
- `std`, `p5`, `p95` should reflect the raw simulation distribution, not the calibrated one
- The `raw_mean` field allows tracking the calibration shift for analysis

### Files Changed

| File | Change |
|------|--------|
| `src/bbl_pipeline/simulation/engine.py` | Restructured calibration in `simulate()` and `simulate_vectorized()` |
| `src/bbl_pipeline/simulation/state.py` | Added `raw_mean: Optional[float]` to `SimulationResult` |
| `analyze_divergence_report.py` | New 3-way comparison script (ML vs MC_CAL vs MC_RAW) |
| `inspect_mc_calibrator.py` | Diagnostic tool for calibrator inspection |
| `verify_mc_calibration.py` | Calibrator verification script |

## Verification

### Unit Tests

All 63 simulation tests pass unchanged — the fix doesn't alter the API contract.

### Calibrator Values (T20I)

```
InningsMCCalibrators:
  Innings 1: Platt(a=1.2543, b=0.6711) — 3,052 samples, Brier=0.2053
  Innings 2: Platt(a=1.1696, b=-0.2073) — 2,756 samples, Brier=0.1185

Prob      | Inn1 Output     | Inn2 Output     | Diff
-----------------------------------------------------------
0.10      | 0.1609          | 0.0823          | +0.0609
0.30      | 0.3875          | 0.2702          | +0.0875
0.50      | 0.6599          | 0.4496          | +0.1599
0.70      | 0.8662          | 0.6441          | +0.1662
0.90      | 0.9669          | 0.8619          | +0.0669
```

**Interpretation**: Inn1 calibrator shifts probabilities upward (first innings batting team historically undervalued by resource_win_prob). Inn2 calibrator shifts slightly downward (chase slightly overvalued).

### Backtest Results (200 T20I Matches)

```
SEGMENT         | ML LL    | MC CAL LL  | MC RAW LL  | ML ECE   | MC CAL ECE | MC RAW ECE
--------------------------------------------------------------------------------------------------------------
OVERALL         | 0.4338   | 0.4650     | 0.4868     | 0.0359   | 0.0268     | 0.0479
Innings 1       | 0.4895   | 0.5004     | 0.5342     | 0.0560   | 0.0290     | 0.0681
Innings 2       | 0.3803   | 0.4296     | 0.4394     | 0.0304   | 0.0278     | 0.0440
```

**Key findings**:
- MC_CAL now shows real improvement over MC_RAW (-4.5% LogLoss, -44% ECE)
- Calibrated MC has better ECE (honesty) than ML in Innings 1 (0.0290 vs 0.0560)
- ML remains superior on LogLoss (sharpness) overall

### Live Inference Path

The fix flows automatically through the live inference path:
- `crex_live_predictor.py` → `simulate_one_over()` → `simulate_vectorized()`
- When `predictor` is provided (ML model), calibration is skipped (correct behavior)
- When `predictor` is None (resource_win_prob), calibration is now correctly applied

## Impact on Downstream Systems

| Component | Impact |
|-----------|--------|
| Live predictor | Calibrated MC probabilities now differ from raw (as intended) |
| Match state logger | `raw_mean` field available for calibration tracking |
| Divergence analysis | 3-way comparison now meaningful |
| Betting decisions | More accurate MC probabilities for edge calculation |
| Streamlit app | No changes needed (uses SimulationResult.mean_prob) |

## Related Documentation

- [MONTE_CARLO_SIMULATION.md](MONTE_CARLO_SIMULATION.md) — Engine architecture and temperature calibration
- [MONTE_CARLO_ANCHORING_FIX.md](MONTE_CARLO_ANCHORING_FIX.md) — Previous MC fix (anchoring bias)
- [LEAGUE_CALIBRATION_GUIDE.md](LEAGUE_CALIBRATION_GUIDE.md) — League-specific calibration methods
