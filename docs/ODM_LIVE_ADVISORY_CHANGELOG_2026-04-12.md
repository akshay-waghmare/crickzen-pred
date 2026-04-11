# ODM Live Advisory Change Log (2026-04-12)

This document summarizes the ODM live-inference and Streamlit work included in this snapshot.

## 1) Scope of This Snapshot

This commit focuses on making the Odds Direction Model visible and stable during live T20 inference, especially for the IPL Streamlit workflow.

Included areas:

- live predictor compatibility fixes after the Python / scikit-learn runtime change
- live ODM feature-row completeness fixes
- Streamlit support for ODM advisory cards
- a mirror-feed path for ODM-enriched live JSON
- self-healing ODM mirror refresh from the raw live feed
- venue-stat override support in the feature store

## 2) Files Updated

Core inference/runtime:

- `src/bbl_pipeline/inference/predictor.py`
- `src/bbl_pipeline/inference/odds_direction_model.py`
- `src/bbl_pipeline/features/store.py`

Live UI / mirror-feed support:

- `src/bbl_pipeline/app/live_streamlit_app.py`
- `scripts/odm_live_json_bridge.py`

Documentation added:

- `docs/ODM_LIVE_ADVISORY_CHANGELOG_2026-04-12.md`

## 3) What Changed

### 3.1 Predictor compatibility fix

`src/bbl_pipeline/inference/predictor.py` now patches persisted `SimpleImputer` objects loaded from older sklearn artifacts by restoring `_fill_dtype` from `_fit_dtype` when necessary.

Why this was needed:

- model artifacts were saved under sklearn `1.7.2`
- the active workspace environment is sklearn `1.8.0`
- live inference was failing with:
  - `'SimpleImputer' object has no attribute '_fill_dtype'`

The predictor also now coerces league-calibrator outputs to a scalar in the single-state live path, fixing the failure:

- `only 0-dimensional arrays can be converted to Python scalars`

### 3.2 ODM feature-row completeness fix

`src/bbl_pipeline/inference/odds_direction_model.py` now sets explicit defaults for live-only fields that were present during training but missing during live assembly:

- `is_super_over`
- `runs_batter`
- `runs_extras`
- `runs_total`
- `score_adjusted_by_team`
- `projected_adjusted`
- `resource_team_adjusted`
- `run_rate_team_adj`

This removed the live ODM feature-audit gap and restored complete 90-feature coverage.

### 3.3 Streamlit ODM advisory card

`src/bbl_pipeline/app/live_streamlit_app.py` now renders a dedicated ODM advisory section showing:

- direction (`UP` / `DOWN`)
- direction confidence
- phase (`powerplay` / `middle` / `death`)
- 90% delta band for the next 12 balls
- delta mode (`residual_delta`)
- experimental point estimate
- history points used by the live ODM call

### 3.4 ODM mirror-feed support

The live app now supports a separate ODM-enriched JSON feed for ML+MC views:

- IPL mirror: `data/ipl_live_ml_odm.json`
- PSL mirror: `data/psl_live_ml_odm.json`

`scripts/odm_live_json_bridge.py` can continuously read a raw live JSON feed and write an enriched mirror that includes:

- `odm`
- `odm_feature_audit`

### 3.5 Self-healing mirror refresh

To avoid a frozen ODM mirror when the background bridge falls behind, `live_streamlit_app.py` now regenerates the mirror from the raw live feed at read time when:

- the selected source is an ODM mirror, and
- the raw JSON is newer than the mirror JSON

This keeps the Streamlit mirror source usable even if the sidecar process is not the freshest writer.

### 3.6 Streamlit backend launcher fix

The Streamlit app was previously launching predictor/bridge subprocesses with the app interpreter (`sys.executable`) instead of the repository virtual environment.

The app now prefers:

- `.venv/Scripts/python.exe` on Windows
- `.venv/bin/python` on Unix-like environments

This fixed the case where the dashboard start buttons looked stuck because the backend child processes were starting under the wrong interpreter.

### 3.7 Venue stat override support

`src/bbl_pipeline/features/store.py` now prefers the match-details venue first-innings average when present:

- `match_details_avg_1st_inns`
- fallback: `avg_1st_inns`

This change is intended to prefer the official match-details venue average over a derived team-on-venue average.

## 4) Validation Summary

Validated during the live IPL CSK vs DC run:

- raw predictor feed updated successfully in `data/ipl_live_ml.json`
- ODM mirror feed updated successfully in `data/ipl_live_ml_odm.json`
- ODM advisory reached `status = ready`
- ODM feature audit reported `missing_count = 0`
- Streamlit IPL mirror source no longer depended entirely on a continuously healthy sidecar

Observed remaining follow-up:

- the live venue-average path still needs a final end-to-end cleanup to ensure the match-details venue average is always the one shown/used in active live runs

## 5) ODM Artifact Summary

Artifact directory:

- `models/odm_v1/`

Training-manifest highlights:

- `feature_count`: `90`
- `selected_delta_mode`: `residual_delta`
- direction model: `xgboost_classifier_on_direction`
- point-estimate delta model: `xgboost_regressor_on_residual_delta_12_plus_momentum_baseline`
- interval model: `hist_gradient_boosting_quantiles_on_residual_delta_12_with_phase_conditioned_split_conformal_adjustment`

Holdout metrics from `models/odm_v1/metrics.json`:

- direction accuracy: `0.5773`
- direction ROC AUC: `0.6126`
- delta MAE: `0.0747`
- interval 90% coverage: `0.8935`
- interval average width: `0.2866`

## 6) Top Features Used by ODM

These rankings come from the saved artifact CSVs in `models/odm_v1/`.

Important note:

- these are feature-importance rankings, not globally signed effects
- they tell us which inputs mattered most to each model
- they do **not** reliably mean that increasing a feature always pushes the prediction in one direction across all match states

### 6.1 Top features for `UP` / `DOWN` direction prediction

Source:

- `models/odm_v1/direction_feature_importance.csv`

Top 10 features:

1. `required_run_rate` (`0.0765`)
2. `is_middle_overs` (`0.0722`)
3. `phase_middle` (`0.0523`)
4. `chase_difficulty` (`0.0348`)
5. `pressure_index` (`0.0335`)
6. `rrr_times_wickets` (`0.0241`)
7. `resource_win_prob` (`0.0236`)
8. `overs_remaining` (`0.0184`)
9. `run_rate_diff` (`0.0173`)
10. `ball_number` (`0.0167`)

Also notable in the direction model:

- `league_psl`
- `league_ipl`
- `ml_prob`
- `resource_pct`
- `target_minus_venue_avg_score`

### 6.2 Top features for point-estimate delta prediction

Source:

- `models/odm_v1/delta_feature_importance.csv`

Top 10 features:

1. `wickets_last_12` (`0.2637`)
2. `ml_prob_delta_12` (`0.1932`)
3. `runs_last_12` (`0.0814`)
4. `ml_prob_delta_6` (`0.0310`)
5. `runs_last_18` (`0.0134`)
6. `resource_pct` (`0.0105`)
7. `boundary_pct_last_18` (`0.0101`)
8. `phase_middle` (`0.0083`)
9. `dls_pressure_index` (`0.0082`)
10. `overs_remaining` (`0.0082`)

Also notable in the point-estimate model:

- `ml_prob`
- `rrr_times_wickets`
- `wickets_lost`
- `run_rate_diff`
- `crr_minus_target_rr`
- `league_ipl`
- `chase_difficulty`
- `resource_win_prob`

## 7) Practical Interpretation Notes

How to read the live ODM card:

- `Direction` is the primary short-term directional signal
- `Confidence` is the classifier confidence for that direction
- `90% Delta Band` is the next-12-ball change range in **percentage points of win probability**
- `Point Estimate` is still experimental and should not be treated as the primary signal
- `History points` is the number of distinct-ball live snapshots available to ODM during the call

Repository guidance implemented in the app:

- use direction and interval as the main advisory signals
- treat the central point estimate as supporting information only

## 8) Suggested Follow-Up

Remaining non-blocking work after this snapshot:

1. Finish the end-to-end venue-average cleanup so the active live predictor consistently uses the official match-details venue average.
2. If desired, add a dedicated analysis note explaining ODM cards in user-facing language inside the live dashboard or docs.
3. If stronger interpretability is needed, add SHAP/per-feature directional analysis instead of relying only on raw importance ranking.
