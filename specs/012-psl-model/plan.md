# Implementation Plan: PSL Model v1

**Spec**: `specs/012-psl-model/spec.md`  
**Branch**: `012-psl-model`  
**Date**: 2026-04-22  

---

## Summary

Deliver a dedicated PSL v1 win-probability model following the IPL v6 pattern: fix the retrain CLI config so it ingests from the historical archive (`psl_json/`, 338 files), add `FormatConfig.psl()` with empirically derived scoring constants, run the end-to-end retrain pipeline, update Streamlit feeds to point at `models/psl_v1`, and register the model in `model_registry.json`.

---

## Pre-flight Checks

Before any code changes:

```powershell
# 1. Verify historical data is present
Get-ChildItem psl_json -Filter "*.json" | Measure-Object | Select-Object Count
# Expected: 338

# 2. Verify recently-played data is separate
Get-ChildItem psl_male_json -Filter "*.json" | Measure-Object | Select-Object Count
# Expected: ~15 (2026 only)

# 3. Confirm retrain CLI is wired for PSL
bbl-pipeline retrain --help
# Should list 'psl' in --league choices

# 4. Confirm no existing psl_v1 artifacts
Test-Path models/psl_v1
Test-Path data/psl_feature_store_v1
# Both should return False
```

**Known pre-flight issue (must fix first):** The retrain CLI config at `src/bbl_pipeline/cli.py` line 1503 maps PSL `json_dir` → `psl_male_json` (15 matches). This must be changed to `psl_json` (338 matches) before running the pipeline.

---

## Step 1 — Fix Retrain CLI Config (Critical Bug)

**File**: `src/bbl_pipeline/cli.py` (line ≈1503)  
**Why**: `json_dir: 'psl_male_json'` points to 15 recent files, not the 338-file historical archive. FR-009 requires using `psl_json/` for training.

**Change**:
```python
# Before
'psl': {
    'json_dir': 'psl_male_json',   # ← WRONG: only 15 recent files
    ...
}

# After
'psl': {
    'json_dir': 'psl_json',        # ← 338 historical files (2017-2026)
    ...
}
```

**Note**: The MC calibration step (Step 6 of retrain) also uses `cfg['json_dir']` — that's fine; using the 338 historical files for MC calibration is an improvement over 15 files.

**Verification**: After the fix, run `bbl-pipeline retrain --league psl --version v1` and confirm the console shows `📁 Found 338 JSON files in psl_json`.

---

## Step 2 — `FormatConfig.psl()` (Scoring Constants)

### 2a. Derive Empirical Constants

Run the existing IPL derivation script pointed at PSL training data to extract:
- `par_score` (PSL average first-innings total)
- `league_avg_score`
- `bat_first_win_rate`
- Per-phase expected run rates (powerplay / middle / death / final)
- First-innings wicket penalty 3D table
- Chase wicket penalty 2D table (optional for v1; can use T20 defaults)

```powershell
# Step 2a.1 — Run ingestion first to produce psl_features_v1/training.parquet
# (needed before constants can be derived)
bbl-pipeline ingest --input-dir psl_json --output-dir data/psl_raw

bbl-pipeline process `
  --input-dir data/psl_raw/matches `
  --output-dir data/psl_features_v1 `
  --feature-store-dir data/psl_feature_store_v1 `
  --league psl
```

> **If `process` falls back to T20 defaults (par=165.0)** — that is expected at this point because `FormatConfig.psl()` does not exist yet. The processed features will use generic constants. The FormatConfig is added next; features will be regenerated as part of `retrain` in Step 3.

```powershell
# Step 2a.2 — Derive PSL-specific constants from training rows
python scripts/derive_ipl_improvements.py `
  --data-path data/psl_features_v1/training.parquet `
  --output-py  scripts/psl_derived_tables.py
```

> **Note**: `derive_ipl_improvements.py` hard-codes the IPL data path. Check whether it accepts `--data-path` / `--output-py` args or needs a temporary edit. If the script does not accept args, copy it to `scripts/derive_psl_improvements.py`, update `DATA_PATH` to `data/psl_features_v1/training.parquet` and `OUTPUT_PY` to `scripts/psl_derived_tables.py`, then run it.

The script produces:
- `PSL_par_score` — verify it differs from T20 default (165.0) by ≥ 3 runs (SC-004)
- `PSL_league_avg_score`
- `PSL_bat_first_win_rate`
- `PSL_expected_run_rates` dict
- `PSL_first_innings_wicket_penalty_3d` dict
- (Optional) `PSL_chase_wicket_penalty_2d` dict

### 2b. Add `FormatConfig.psl()` Classmethod

**File**: `src/bbl_pipeline/features/format_config.py`

Locate the `ipl()` classmethod (around line 331) and add `psl()` immediately after it, following the same `replace(base, ...)` pattern:

```python
@classmethod
def psl(cls) -> "FormatConfig":
    """Return a PSL-tuned T20 configuration.

    Scoring constants are derived empirically from PSL historical match
    data (338 matches, 2017-2026) via ``scripts/derive_psl_improvements.py``.
    """
    base = cls.t20()
    return replace(
        base,
        # PSL scoring environment — fill from scripts/psl_derived_tables.py output
        par_score=<DERIVED_VALUE>,           # e.g. 160.3 — must differ from 165.0 by ≥ 3
        league_avg_score=<DERIVED_VALUE>,
        bat_first_win_rate=<DERIVED_VALUE>,
        # PSL chase sigmoid (fit on PSL per-over observations)
        rrr_beta=<DERIVED_VALUE>,            # start with T20 default 0.7 if insufficient data
        rrr_midpoint=<DERIVED_VALUE>,
        rrr_midpoint_slope=0.0,              # update if per-over fit available; 0 = fixed midpoint
        expected_run_rates={
            "powerplay": <DERIVED_VALUE>,
            "middle":    <DERIVED_VALUE>,
            "death":     <DERIVED_VALUE>,
            "final":     <DERIVED_VALUE>,
        },
        first_innings_score_midpoint=<DERIVED_VALUE>,
        first_innings_score_beta=0.04,       # start with IPL value; refine later
        # PSL first-innings wicket penalties (from derive script)
        first_innings_wicket_penalty_3d={
            # Paste PSL_FIRST_INNINGS_WICKET_PENALTY_3D from psl_derived_tables.py
        },
    )
```

**Placeholder values**: If PSL data is insufficient to fit per-over sigmoid parameters reliably (< 200 observations per over), keep `rrr_midpoint_slope=0.0` and use the T20 fixed midpoint. Document the decision in a comment.

### 2c. Update `from_league` Dispatcher

**File**: `src/bbl_pipeline/features/format_config.py` (around line 884)

```python
@classmethod
def from_league(cls, league: str) -> FormatConfig:
    ...
    if league == "ipl":
        return cls.ipl()
    if league == "psl":          # ← ADD THIS
        return cls.psl()
    # All other leagues are T20
    return cls.t20()
```

**Verification**:
```python
from bbl_pipeline.features.format_config import FormatConfig
cfg = FormatConfig.from_league('psl')
assert cfg.par_score != 165.0, "PSL par_score must differ from T20 default"
print(f"PSL par_score: {cfg.par_score}")  # Should be empirically derived value
```

---

## Step 3 — Run Retrain Pipeline

With the CLI fix (Step 1) and FormatConfig (Step 2) in place:

```powershell
bbl-pipeline retrain --league psl --version v1
```

This runs all 7 steps automatically:

| Step | Action | Output |
|------|--------|--------|
| 1 | Ingest `psl_json/` → Parquet | `data/psl_raw/matches/` |
| 2 | Process features (using `FormatConfig.psl()`) | `data/psl_features_v1/training.parquet` |
| 3 | Train `XGBLogRegEnsemble` | `models/psl_v1/champion_model.joblib` |
| 4 | Generate OOF calibrators | `models/psl_v1/isotonic_calibrator.pkl` |
| 5 | Analyze OOF (7 methods) | `models/psl_v1/OOF_CALIBRATION_REPORT.md` |
| 6 | Calibrate MC simulation | `models/psl_v1/mc_calibrator.pkl` |
| 7 | Update model registry | `models/model_registry.json` (partial — see Step 5) |

**Expected console output** at start: `📁 Found 338 JSON files in psl_json`

**Expected training sample count**: ~75,000–95,000 rows (338 matches × ~250 ball-states avg)

---

## Step 4 — Validate Model Artifacts

```powershell
# 4.1 — All required files exist
Test-Path models/psl_v1/champion_model.joblib   # Must be True (FR-003)
Test-Path models/psl_v1/oof_calibrators.pkl     # Must be True (FR-003)
Test-Path models/psl_v1/OOF_CALIBRATION_REPORT.md  # Must be True (FR-010)
Test-Path data/psl_feature_store_v1/team_ratings.parquet   # Must be True (FR-004)
Test-Path data/psl_feature_store_v1/player_stats.parquet   # Must be True (FR-004)
Test-Path data/psl_feature_store_v1/venue_stats.parquet    # Must be True (FR-004)

# 4.2 — OOF Brier score check
python -c "
import pandas as pd
df = pd.read_csv('models/psl_v1/oof_calibration_results.csv')
brier = df[(df.method=='brier_optimized') & (df.segment=='overall')]['brier'].iloc[0]
print(f'OOF Brier (brier_optimized): {brier:.4f}')
assert brier < 0.200, f'Brier {brier:.4f} exceeds SC-002 target of 0.200'
"

# 4.3 — Feature store team coverage
python -c "
import pandas as pd
df = pd.read_parquet('data/psl_feature_store_v1/team_ratings.parquet')
print('Teams in feature store:')
print(df['team'].tolist())
# Expected: 6 teams (Hyderabad Kingsmen absent — 2026 franchise, no training data)
# All 6 historical teams must be present (SC-005)
"

# 4.4 — Hyderabad Kingsmen fallback (no KeyError)
python -c "
from bbl_pipeline.features.store import FeatureStore
store = FeatureStore.load('data/psl_feature_store_v1')
# This should NOT raise an error
rating = store.get_team_rating('Hyderabad Kingsmen', fallback_to_average=True)
print(f'HYK fallback rating: {rating}')
"
```

**For 4.4**: If `FeatureStore.get_team_rating` does not yet accept `fallback_to_average=True`, check the existing implementation. The spec (FR-005) requires league-average fallback — if it is not already implemented for PSL, add a guard in `store.py` for the PSL context that returns the mean of all known team ratings when the team key is missing.

---

## Step 5 — Model Registry Update

The `retrain` Step 7 auto-updates the registry, but the auto-generated entry may be missing the `league_calibrator` field and some statistics. After training, verify and manually complete the `active_models.PSL` entry in `models/model_registry.json`:

```json
"PSL": {
  "path": "models/psl_v1",
  "version": "v1",
  "description": "XGBLogRegEnsemble (25 features) + Per-Over Brier-Optimized Calibration (Brier: <VALUE>, ECE: 0.0000)",
  "training": {
    "samples": <FROM_TRAINING>,
    "matches": 338,
    "date": "2026-04-22",
    "brier_score": <OOF_BRIER>
  },
  "calibrator": {
    "path": "models/psl_v1/isotonic_calibrator.pkl",
    "type": "per_over_brier_optimized",
    "n_calibrators": "<COUNT_FROM_SCRIPT>"
  },
  "notes": "No league calibrator at v1 launch. Will be added once live PSL match states are recorded. Hyderabad Kingsmen (2026 expansion) absent from feature store — falls back to league-average ratings.",
  "feature_store": {
    "path": "data/psl_feature_store_v1",
    "version": "v1",
    "generated_date": "2026-04-22",
    "training_data_samples": <FROM_TRAINING>,
    "statistics": {
      "teams": 6,
      "players": "<COUNT>",
      "venues": "<COUNT>"
    }
  }
}
```

**Important**: `registry_league_names` in `cli.py` does not currently include `'ipl': 'IPL'` or `'psl': 'PSL'` mappings (the IPL and PSL keys are missing from the dict at line ≈1720). Verify that step 7 of `retrain` correctly writes a `PSL` key. If `registry_league_names.get('psl', 'psl'.upper())` falls through to `.upper()`, it will produce `'PSL'` — which is correct — but the auto-generated metrics should still be verified by inspection.

**Verification**:
```python
import json
with open('models/model_registry.json') as f:
    reg = json.load(f)
entry = reg['active_models']['PSL']
assert entry['path'] == 'models/psl_v1'
assert entry['version'] == 'v1'
assert entry['training']['samples'] > 0
assert entry['feature_store']['path'] == 'data/psl_feature_store_v1'
print("Registry OK:", entry['description'])
```

---

## Step 6 — Streamlit Integration

**File**: `src/bbl_pipeline/app/live_streamlit_app.py` (lines ≈482–498)

**Current state**: Both PSL feed configs have `"model_dir": "models/t20_male_v2"` (placeholder).

**Required change**:
```python
# Before
"PSL ML+MC": {
    ...
    "model_dir": "models/t20_male_v2",   # placeholder
    ...
},
"PSL MC-only": {
    ...
    "model_dir": "models/t20_male_v2",   # placeholder
    ...
},

# After
"PSL ML+MC": {
    ...
    "model_dir": "models/psl_v1",        # dedicated PSL model
    ...
},
"PSL MC-only": {
    ...
    "model_dir": "models/psl_v1",        # dedicated PSL model
    ...
},
```

Both entries already have `"feature_store_dir": "data/psl_feature_store_v1"` and `"league": "psl"` — no other changes needed.

**Verification**: After the model exists on disk, launch Streamlit and select the "PSL ML+MC" feed. Confirm the footer/debug panel shows `model_dir = models/psl_v1` (not `t20_male_v2`). For the Hyderabad Kingsmen test, load a recorded PSL 2026 state file — team should display correctly with no "unknown team" warning.

---

## Step 7 — Testing

### 7.1 Unit / Smoke Tests

```powershell
# FormatConfig regression
python -c "
from bbl_pipeline.features.format_config import FormatConfig
psl = FormatConfig.psl()
t20 = FormatConfig.t20()
ipl = FormatConfig.ipl()
assert psl.par_score != t20.par_score, 'PSL par_score must differ from T20'
assert psl.par_score != ipl.par_score, 'PSL par_score must differ from IPL'
assert FormatConfig.from_league('psl').par_score == psl.par_score
assert FormatConfig.from_league('t20').par_score == t20.par_score  # no regression
assert FormatConfig.from_league('ipl').par_score == ipl.par_score  # no regression
print(f'PSL par_score={psl.par_score}  T20 par_score={t20.par_score}')
print('FormatConfig tests passed')
"

# Full inference smoke test against a PSL match
python -m src.bbl_pipeline.inference.crex_live_predictor `
  --match-url "PASTE_A_PSL_2026_CREX_URL_HERE" `
  --model-dir models/psl_v1 `
  --feature-store-dir data/psl_feature_store_v1 `
  --league psl

# Expected output:
#   Team resolution: 6 known teams display correctly
#   HYK maps to "Hyderabad Kingsmen" with no error
#   Par score shown matches FormatConfig.psl().par_score (not 165.0)
#   Win probability is between 5% and 95%
```

### 7.2 Existing Test Suite

```powershell
python -m pytest tests/ -x -q
```

Check that no existing tests break. Particular attention to:
- Any tests importing `FormatConfig` directly
- Tests for `from_league` dispatch
- Feature store tests that might assert on known team lists

### 7.3 Baseline Comparison (SC-003)

```powershell
# Compare PSL v1 vs global T20 model on PSL data
python -c "
import pandas as pd, numpy as np
from sklearn.metrics import brier_score_loss
import joblib

df = pd.read_parquet('data/psl_features_v1/training.parquet')
y  = df['is_winner']
X  = df.drop(columns=['is_winner']).select_dtypes('number').fillna(0)

# PSL v1 predictions
psl_model = joblib.load('models/psl_v1/champion_model.joblib')
psl_pred  = psl_model.predict_proba(X)[:, 1]
psl_brier = brier_score_loss(y, psl_pred)

# Global T20 model predictions (features need realigning)
t20_model = joblib.load('models/t20_male_v2/champion_model.joblib')
shared_features = [c for c in t20_model.selected_features_ if c in X.columns]
t20_pred  = t20_model.predict_proba(X[shared_features])[:, 1]
t20_brier = brier_score_loss(y, t20_pred)

print(f'PSL v1 Brier:             {psl_brier:.4f}')
print(f'Global T20 Brier (on PSL):{t20_brier:.4f}')
print(f'Improvement:              {(t20_brier - psl_brier) / t20_brier:.1%}')
assert psl_brier < t20_brier, 'PSL-specific model must beat global T20 on PSL data (SC-003)'
"
```

---

## Edge-Case Handling Checklist

| Edge Case | Handling | Status |
|-----------|----------|--------|
| **Hyderabad Kingsmen (new 2026 team)** | `TEAM_ABBREVIATIONS_PSL` already maps `HYK`/`HK` → "Hyderabad Kingsmen"; feature store will not contain this team (training predates 2026) — must fall back to league-average ratings, not raise `KeyError` | Verify in Step 4.4 |
| **Rawalpindiz naming quirk** | `TEAM_ABBREVIATIONS_PSL` maps `RWP`/`RPZ` → "Rawalpindiz" — no rename needed; ensure this string appears consistently in training and feature store | Verify team name in feature store after retrain |
| **Wrong source directory** | Fixed in Step 1: retrain uses `psl_json/` (338) not `psl_male_json/` (15) | Step 1 |
| **`from_league('psl')` fallback** | Dispatcher updated in Step 2c to call `FormatConfig.psl()` | Step 2c |
| **No league calibrator at v1** | Registry `notes` field documents this; Streamlit and inference code work correctly with OOF calibrators only — `league_calibrators/psl/` directory absent is normal | Step 5 |
| **FormatConfig fallback at venue with no stats** | Predictor already falls back to `FormatConfig.par_score` when venue_avg_score is absent from feature store | No code change needed |

---

## Artifact Checklist (post-pipeline)

```
models/psl_v1/
├── champion_model.joblib          ← FR-003
├── isotonic_calibrator.pkl        ← FR-003 (per-over brier_optimized)
├── oof_calibrators.pkl            ← from analyze-oof
├── oof_calibration_results.csv    ← from analyze-oof
├── OOF_CALIBRATION_REPORT.md      ← FR-010
├── champion_metadata.json         ← from train
├── feature_importance.csv         ← from train
└── mc_calibrator.pkl              ← from calibrate-mc (non-critical)

data/psl_feature_store_v1/
├── team_ratings.parquet           ← FR-004 (6 historical PSL teams)
├── player_stats.parquet           ← FR-004
└── venue_stats.parquet            ← FR-004

models/model_registry.json
└── active_models.PSL              ← FR-008
```

---

## File Change Summary

| File | Change |
|------|--------|
| `src/bbl_pipeline/cli.py` | Fix `psl` retrain config: `json_dir` → `'psl_json'` |
| `src/bbl_pipeline/features/format_config.py` | Add `FormatConfig.psl()` classmethod; update `from_league` dispatcher |
| `src/bbl_pipeline/app/live_streamlit_app.py` | Change `"model_dir"` in PSL ML+MC and PSL MC-only configs from `"models/t20_male_v2"` to `"models/psl_v1"` |
| `models/model_registry.json` | Add `active_models.PSL` entry (auto-created by retrain Step 7, then manually completed) |

> **No other files need modification.** `TEAM_ABBREVIATIONS_PSL`, `_resolve_team_abbrev`, and Streamlit feed display names are already correct.

---

## Execution Order

```
1. Fix cli.py json_dir (Step 1)           ← Code change, 1 line
2. Run ingestion + derive constants (2a)  ← Data work, read-only until FormatConfig written
3. Add FormatConfig.psl() (2b, 2c)        ← Code change, ~50 lines
4. bbl-pipeline retrain --league psl --version v1  ← ~30 min
5. Validate artifacts (Step 4)            ← Verification only
6. Complete registry entry (Step 5)       ← JSON edit
7. Update Streamlit model_dir (Step 6)    ← Code change, 2 lines
8. Run tests (Step 7)                     ← Verification only
```
