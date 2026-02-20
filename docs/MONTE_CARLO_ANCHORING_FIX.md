# Monte Carlo Anchoring Fix (Jan 22, 2026)

## Issue Summary
**Problem:** Monte Carlo simulation results showed significantly different probabilities compared to the main ML model predictions.

**Example (SA20 Qualifier 1 - PC vs SEC):**
- **ML Model (with feature store)**: PC 31.2% to win
- **Monte Carlo 6-ball mean**: PC 49.6% to win
- **Discrepancy**: 18.4 percentage points

This large difference confused users about which prediction to trust.

## Root Cause Analysis

### Two Different Feature Pipelines

**Main `predict()` method** (used by CLI and live tracking):
```python
# Full feature pipeline
- Uses InMemoryFeatureStore with actual team/player/venue stats
- Processes ball history for rolling averages
- Applies empirically calibrated wicket penalties
- Result: Accurate, well-calibrated probabilities
```

**Batch `predict_batch()` method** (used by Monte Carlo terminal evaluation):
```python
# Simplified feature pipeline (optimized for speed)
- Uses default/hardcoded values for most features
- No ball history → default rolling stats
- No feature store lookups → generic team strengths
- Result: Fast but less accurate probabilities
```

### Why This Difference Exists

The `predict_batch()` method was designed for **speed** over **accuracy** because:
1. Monte Carlo evaluates **thousands of terminal states** (2000+ per simulation)
2. Feature store lookups are expensive (~0.5-1ms per state)
3. For 2000 states: Feature store = ~1-2 seconds, Defaults = ~50-100ms

Trade-off decision: Accept less accurate absolute values to keep MC under 200ms total.

### Technical Details

**Feature Comparison:**

| Feature | Main `predict()` | Batch `predict_batch()` |
|---------|------------------|-------------------------|
| `venue_avg_score` | Actual (150.0 for Kingsmead) | Default (165.0) |
| `batting_team_win_rate` | From feature store (0.514) | Default (0.5) or passed in state |
| `runs_last_18` | From ball history (18.0) | Default (18.0) |
| `batsman_venue_avg` | From player stats (38.0) | Default (38.0) |
| `resource_win_prob` | Empirically calibrated | Simplified heuristic |

**Calibration Applied:**
- Both methods apply the same calibration chain (per-over → league)
- BUT: Different raw inputs → Different calibrated outputs
- Example: Raw 42% (main) vs 57% (batch) → After league cal: 31% vs 50%

## Solution: Anchoring Approach

Instead of trying to make `predict_batch()` match `predict()` (which would slow down MC), we **anchor** the MC distribution to the ML model baseline.

### Mathematical Formulation

```
Given:
- ml_prob: Accurate probability from main ML model with full features
- mc_mean: Monte Carlo mean from predict_batch() (less accurate)
- mc_std: Monte Carlo standard deviation (relative uncertainty)

Compute shift:
- shift = ml_prob - mc_mean

Apply shift to all MC statistics:
- anchored_mean = mc_mean + shift = ml_prob  (now matches ML model)
- anchored_p5 = mc_p5 + shift
- anchored_p95 = mc_p95 + shift
- anchored_std = mc_std  (unchanged - relative spread preserved)
```

### Intuition

Think of Monte Carlo as providing **uncertainty bounds around a baseline**:
- **ML model**: Gives us the most accurate point estimate (uses all features)
- **Monte Carlo**: Tells us how uncertain we should be (due to future randomness)
- **Anchored result**: ML model's accuracy + MC's uncertainty quantification

### Benefits

1. **Accurate Center**: Uses ML model's well-calibrated probability
2. **Meaningful Spread**: Preserves MC's relative uncertainty estimate
3. **Speed**: No change to MC performance (still <200ms)
4. **Trust**: Users see consistent probabilities across CLI and MC panel

## Implementation

### Changes to `crex_live_predictor.py`

**Before:**
```python
return {
    "simulation_1ball": {
        "mean_prob": result_1ball.mean_prob,  # Could be 50%
        "std_prob": result_1ball.std_prob,
        "p5": result_1ball.p5,
        "p95": result_1ball.p95,
    }
}
```

**After:**
```python
# Anchor MC distribution to ML model baseline
shift = model_prob - result_1ball.mean_prob

return {
    "ml_baseline": model_prob,  # 31.2% (accurate)
    "simulation_1ball": {
        "mean_prob": model_prob,  # Now 31.2% (anchored)
        "raw_mean": result_1ball.mean_prob,  # 50% (for debugging)
        "std_prob": result_1ball.std_prob,  # 5% (unchanged)
        "p5": result_1ball.p5 + shift,  # Shifted
        "p95": result_1ball.p95 + shift,  # Shifted
    }
}
```

### Changes to Streamlit App

Added success banner explaining the approach:
```python
st.success("""
✅ **Anchored Monte Carlo**: MC simulations provide uncertainty bounds (σ, CI) 
around the ML model's calibrated baseline. This combines ML model accuracy 
with MC uncertainty quantification.
""")
```

Updated metrics to show ML baseline:
```python
st.markdown(f"**ML Baseline:** {ml_baseline*100:.1f}%")
st.metric("Mean Win Prob", f"{mean*100:.1f}%", f"±{std*100:.1f}% (1σ)")
```

## Testing & Validation

### Before Fix (SA20 Example)
```
CLI (ML Model): PC 31.2% to win
Monte Carlo 6-ball:
  Mean: 49.6%
  ±11.7% (1σ)
  90% CI: [31.2% — 65.9%]

Issue: Mean doesn't match CLI, confusing for users
```

### After Fix (SA20 Example)
```
CLI (ML Model): PC 31.2% to win  ← ML Baseline
Monte Carlo 6-ball (Anchored):
  Mean: 31.2%  ← Shifted to match ML
  ±11.7% (1σ)  ← Spread preserved
  90% CI: [12.9% — 47.5%]  ← Shifted accordingly

Result: Consistent with CLI, uncertainty still meaningful
```

## Performance Impact

**No change to MC simulation performance:**
- Anchoring shift: ~0.01ms (negligible)
- MC still completes in ~100-200ms total
- Feature store is NOT called during MC (speed preserved)

## Alternative Approaches Considered

### ❌ Option 1: Make `predict_batch()` use feature store
**Why rejected:** Would make MC 10-20x slower (~2 seconds), unacceptable for live use

### ❌ Option 2: Pre-compute and cache features for common states
**Why rejected:** State space is too large, cache would be ineffective

### ❌ Option 3: Use only MC results, ignore ML model
**Why rejected:** MC with simplified features is less accurate than ML with full features

### ✅ Option 4: Anchor MC to ML baseline (chosen)
**Why accepted:** Best of both worlds - ML accuracy + MC uncertainty, no speed penalty

## Future Improvements

### Potential Enhancements

1. **Contextual shifting**: Adjust shift based on match phase
   - Early innings: MC uncertainty more meaningful (larger relative shift)
   - Late innings: MC more constrained (smaller relative shift)

2. **Feature parity score**: Quantify how similar MC features are to actual features
   - High parity (>0.9): Trust MC mean more, smaller shift
   - Low parity (<0.7): Trust ML more, larger shift

3. **Hybrid evaluation**: Use ML model for critical terminal states (e.g., < 5 balls remaining)
   - Would increase accuracy for high-stakes moments
   - Trade-off: ~300-500ms instead of ~100ms

## Documentation Updates

Related docs:
- [CALIBRATION_CONSISTENCY_FIX.md](CALIBRATION_CONSISTENCY_FIX.md) - CLI/Streamlit consistency
- [BBL_V12_MODEL.md](BBL_V12_MODEL.md) - Calibration methodology
- [FEATURE_STORE.md](FEATURE_STORE.md) - Feature store structure

## Commits

```
7a991c8 Fix: Anchor Monte Carlo results to ML model baseline
206b8f4 docs: Add ML baseline reference in Monte Carlo panel
```

## Key Takeaways

1. **Speed vs Accuracy**: Monte Carlo optimizes for speed with simplified features
2. **Anchoring preserves both**: ML accuracy + MC uncertainty
3. **Transparency**: JSON output includes both raw_mean (MC) and ml_baseline (ML)
4. **User trust**: Consistent probabilities across CLI and Streamlit UI

## Example Output (JSON)

```json
{
  "bat_win_prob": 0.312,
  "monte_carlo": {
    "available": true,
    "ml_baseline": 0.312,
    "simulation_6ball": {
      "mean_prob": 0.312,
      "raw_mean": 0.496,
      "std_prob": 0.117,
      "p5": 0.129,
      "p95": 0.475,
      "n_sims": 2000,
      "time_ms": 157.3
    },
    "betting_decision": {
      "model_prob": 0.312,
      "simulation_mean": 0.312
    }
  }
}
```

Note: `model_prob` in betting uses `ml_baseline` (not raw MC mean) for accurate edge calculation.
