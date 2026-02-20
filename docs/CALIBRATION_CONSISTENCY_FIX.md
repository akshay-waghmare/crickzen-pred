# Calibration Consistency Fix (Jan 21, 2026)

## Issue Summary
**Problem:** Streamlit app and CLI predictor showed different win probabilities for the same match state.
- CLI: SEC 41.2% (after SA20 league calibration)
- Streamlit: SEC ~59.2% (after applying sat_v2 calibrators)

**Root Cause:** Streamlit was applying `sat_v2` (SA20-specific model) calibrators to `t20_male_v2` (global model) raw output. These calibrators are incompatible because they were trained on different model outputs.

## Solution
Implemented a calibration handoff protocol where CLI exports its final league-calibrated value, and Streamlit uses it directly instead of re-calibrating.

### Changes Made

#### 1. Windows Encoding Fixes
**Problem:** Unicode emojis (✅, 📊, ⚠️, etc.) caused `UnicodeEncodeError` on Windows cp1252 console.

**Fixed Files:**
- `src/bbl_pipeline/inference/crex_live_predictor.py`: 15+ emoji replacements
  - ✅ → `[OK]`
  - 📊 → `[INFO]`
  - ⚠️ → `[WARN]`
  - 🏏 → `[START]`
  - 🔄 → `[REFRESH]`
  - 🛑 → `[STOP]`
  - 🎯 → `[TARGET]`
  
- `src/bbl_pipeline/inference/predictor.py`:
  - 📊 → `[CAL]`
  - 🌍 → `[LEAGUE]`
  - 🔍 → `DEBUG:`
  
- `src/bbl_pipeline/features/store.py`:
  - Fixed SEASON stats logging emoji

#### 2. Model Directory Defaults
**Problem:** Hardcoded `models/t20_male_v1` fallback paths in simulation code, but v1 is archived.

**Fixed:**
- `src/bbl_pipeline/simulation/evaluator.py`: Changed default `model_dir` from v1 → v2
- `src/bbl_pipeline/simulation/engine.py`: Updated all simulation function defaults

#### 3. Enhanced Calibration Tracking
**Added visibility into which model and calibration method the predictor uses:**

**predictor.py:**
- Added `model_dir` attribute to `Predictor.__init__`
- Enhanced calibration logging to show method and calibrator count:
  ```
  [CAL] Raw: 47.0% | Smoothed: 47.2% | Inn-Specific: 47.7% | Phase (inn1_death): 42.7%
  [LEAGUE] League (SA20): 42.7% -> 41.2%
  ```

**evaluator.py:**
- Added calibration type logging in terminal state evaluation:
  ```python
  calibration='per_over_brier_optimized (38 calibrators)'
  league_calibration='sa20 (temperature)'
  ```

**engine.py:**
- Added `predictor_model_dir` and `ml_model_source` to simulation debug output

#### 4. CLI → Streamlit Calibration Handoff
**Problem:** Streamlit didn't know if CLI had already applied league calibration.

**Solution (crex_live_predictor.py):**
Added two fields to JSON output:
```python
"league": "sa20",  # League code if specified via --league
"league_calibrated_prob": 0.4120482663530882,  # Final calibrated value
```

**Streamlit already had the logic** (live_streamlit_app.py:877-879):
```python
cli_applied_league_calibration = league is not None and league_calibrated_prob is not None

if is_sa20_match and SA20_CALIBRATORS is not None and not cli_applied_league_calibration:
    # Only recalibrate if CLI did NOT already do it
```

## Calibration Chain (SA20 Example)

### Before Fix
**CLI:**
```
Raw (t20_male_v2): 47.0%
→ Phase (t20_male_v2 phase calibrator): 42.7%
→ League (SA20 temperature scaler): 41.2% ✓ FINAL
```

**Streamlit:**
```
Raw (from CLI JSON): 47.0%
→ Phase (sat_v2 phase calibrator): 59.2% ✗ WRONG
```
Different calibrators applied to same raw input → inconsistent results.

### After Fix
**CLI:**
```
Raw: 47.0% → Phase: 42.7% → League (SA20): 41.2%
Exports: league="sa20", league_calibrated_prob=0.412
```

**Streamlit:**
```
Sees: league="sa20" and league_calibrated_prob=0.412
→ Skips recalibration
→ Uses CLI's final value: 41.2% ✓ CONSISTENT
```

## Testing
Run the SA20 predictor to verify consistency:
```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_SA20_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/t20_male_feature_store_v2 \
  --league sa20 \
  --output-json data/live_state.json
```

Then launch Streamlit:
```bash
streamlit run src/bbl_pipeline/app/live_streamlit_app.py
```

Both should show the same final probability.

## Architecture Notes

### Why Different Calibrators Are Incompatible
Each calibrator is an **isotonic regression** trained on a specific model's outputs:
- `t20_male_v2` calibrators: Trained on global model predictions (all T20 leagues)
- `sat_v2` calibrators: Trained on SA20-specific model predictions

These models have different feature spaces and output distributions. Applying sat_v2 calibrators to t20_male_v2 outputs is like applying a BBL team's salary cap to NBA contracts.

### Global Model + League Calibration (Recommended)
The correct approach is:
1. Train one **global unified model** on all T20 data
2. Freeze the model
3. Learn **league-specific calibration** (Temperature/Platt scaling) on each league
4. Apply calibration as final adjustment layer

This is what we now do with `t20_male_v2 + --league sa20`.

## Commit
```
git commit 1600c23
"Fix: League calibration consistency between CLI and Streamlit for SA20"
```

## Related Documentation
- [Model Registry Guide](MODEL_REGISTRY_GUIDE.md) - Model versioning and feature stores
- [BBL v12 Model](BBL_V12_MODEL.md) - Calibration methodology
- [Feature Store](FEATURE_STORE.md) - Feature store structure
