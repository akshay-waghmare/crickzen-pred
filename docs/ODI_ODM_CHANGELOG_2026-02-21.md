# ODI/ODM Change Log (2026-02-21)

This document summarizes all ODI/ODM work included in this commit.

## 1) Core Format Support

- Added `FormatConfig` abstraction for format-aware constants in `src/bbl_pipeline/features/format_config.py`.
- Added ODI presets (male/female), league resolution, and validation invariants.
- Refactored calculator usage to read format-specific constants instead of hardcoded T20 assumptions.

## 2) Pipeline + CLI Updates

- Updated `src/bbl_pipeline/cli.py` to support ODI/ODM flow end-to-end.
- Added/updated league config handling for ODI and ODM leagues.
- Fixed OOF commands (`generate-oof`, `analyze-oof`) to use format-aware total overs.
- Added ODI-safe over derivation for calibration segments.
- Updated retrain flow to pass ODI total overs to OOF generation/analysis.

## 3) OOF Calibration Fixes (Critical)

- Updated `src/bbl_pipeline/training/oof_analyzer.py` to remove hardcoded 20-over assumptions.
- Added dynamic per-over segmentation (`1..total_overs`).
- Added ODI phase support (`powerplay`, `middle`, `setup`, `death`) where appropriate.
- Ensured calibration reports and segment loops are format-aware.

## 4) Inference + Live Predictor Fixes

- Updated `src/bbl_pipeline/inference/predictor.py` phase selection to use ordered phase definitions from `FormatConfig` (supports ODI setup/death boundaries correctly).
- Updated live predictor/realtime mapping/schema paths for ODI compatibility:
  - `src/bbl_pipeline/inference/crex_live_predictor.py`
  - `src/bbl_pipeline/inference/realtime_mapper.py`
  - `src/bbl_pipeline/inference/schema.py`

## 5) Team/Venue Mapping

- Updated `src/bbl_pipeline/features/store.py` with ODI/ODM aliases already used in live runs.
- Added explicit venue normalization to avoid wrong fuzzy venue matches:
  - `International Cricket Stadium` → `Western Australia Cricket Association Ground, Perth`
  - `WACA Ground, Perth` → `Western Australia Cricket Association Ground, Perth`

## 6) Data/Processing and Simulation Touchpoints

- Updated ODI-aware handling in:
  - `src/bbl_pipeline/data/processor.py`
  - `src/bbl_pipeline/features/calculator.py`
  - `src/bbl_pipeline/simulation/config.py`

## 7) Models Retrained with Correct ODI Calibration

Retrained with corrected 50-over calibration behavior:

- `models/odi_v1/`
- `models/odm_male_v1/`
- `models/odm_female_v1/`

Observed calibration structure after retrain:

- ODI models now have per-over calibrators covering overs up to 50.
- ODI models now include setup-phase aware calibrator keys (innings x phase coverage).

Registry updated:

- `models/model_registry.json`

## 8) Tests and Specs Added/Updated

- Added ODI/format tests:
  - `tests/unit/test_odi_config.py`
  - `tests/unit/test_t20_regression.py`
  - `tests/unit/test_t20_regression_snapshots.json`
- Added ODI analysis utility:
  - `scripts/analyze_odi_empirical.py`
- Added ODI planning/spec materials:
  - `specs/007-odi-model/`

## 9) Validation Notes

- Live ODM inference executed successfully for multiple ODM matches using `models/odm_male_v1`.
- Team resolution confirmed for domestic abbreviations (e.g., `VIC`, `WACA`, `NSW`, `TAS`).
- Venue alias issue for CREX generic name resolved via explicit alias mapping.

---

If further cleanup is needed (for example, splitting docs/spec commits from model artifact commits), this commit can be followed by targeted history cleanup in a separate branch.
