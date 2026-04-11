# Quickstart: Odds Direction Model V1

## Goal

Train and wire the first ODM that predicts the next 12-ball movement of the existing ML probability using IPL + PSL data.

## Prerequisites

1. Existing global model available at `models/t20_male_v2/champion_model.joblib`.
2. Existing processed league data available for IPL and PSL.
3. ODM base export support added to `src/bbl_pipeline/data/processor.py` and exposed through CLI.

## Step 1: Export ODM base data

```powershell
bbl-pipeline export-odm-base --league ipl --output-dir data/odm_v1
bbl-pipeline export-odm-base --league psl --output-dir data/odm_v1
```

Expected outputs:

1. `data/odm_v1/ipl_odm_base.parquet`
2. `data/odm_v1/psl_odm_base.parquet`

## Step 2: Build the training dataset and targets

```powershell
bbl-pipeline build-odm-dataset \
  --league ipl \
  --league psl \
  --base-dir data/odm_v1 \
  --features-root data \
  --global-model-dir models/t20_male_v2 \
  --output-file data/odm_v1/training.parquet \
  --report-dir data/odm_v1/reports \
  --horizon-balls 12
```

Expected outputs:

1. `data/odm_v1/training.parquet`
2. `data/odm_v1/reports/baseline_report.json`
3. `data/odm_v1/reports/by_league.csv`
4. `data/odm_v1/reports/by_league_innings_phase.csv`

## Step 3: Train the ODM direction and delta bundle

```powershell
bbl-pipeline train-odm \
  --input-file data/odm_v1/training.parquet \
  --output-dir models/odm_v1
```

Expected outputs:

1. `models/odm_v1/champion_model.joblib`
2. `models/odm_v1/direction_model.joblib`
3. `models/odm_v1/delta_model.joblib`
4. `models/odm_v1/delta_interval_lower_model.joblib`
5. `models/odm_v1/delta_interval_upper_model.joblib`
6. `models/odm_v1/feature_columns.json`
7. `models/odm_v1/metrics.json`
8. `models/odm_v1/baseline_metrics.json`
9. `models/odm_v1/training_manifest.json`
10. `models/odm_v1/direction_feature_importance.csv`
11. `models/odm_v1/delta_feature_importance.csv`

Current checked result on this branch:

1. Direction model is evaluated directly against the momentum direction baseline.
2. Delta model is evaluated directly against zero-delta and momentum-delta baselines.
3. Feature importance is saved separately for direction and delta.
4. The bundle keeps direction and magnitude concerns separate.
5. The current selected delta mode is `residual_delta` (predict residual, then add momentum baseline back).
6. Interval bounds are trained as lower and upper quantile models, then widened with phase-conditioned split-conformal adjustments saved in `training_manifest.json`.

## Step 4: Evaluate against baselines

```powershell
bbl-pipeline evaluate-odm \
  --input-file data/odm_v1/training.parquet \
  --model-dir models/odm_v1
```

Minimum go/no-go checks:

1. Direction accuracy beats the momentum baseline.
2. Delta MAE beats the momentum baseline and the zero-delta baseline.
3. Interval coverage is acceptably close to nominal 90% without exploding interval width.
4. Per-league holdout metrics are not collapsing in IPL or PSL.
5. Dataset validation still passes:

```powershell
python scripts/validation/validate_odm_dataset.py data/odm_v1/training.parquet
```

Current branch status:

1. Direction accuracy: `0.5773` vs momentum `0.5286` → pass
2. Selected delta mode: `residual_delta`
3. Delta MAE: `0.0747` vs momentum `0.1042` → pass
4. Delta MAE: `0.0747` vs zero-delta `0.0733` → still failing, delta path needs more work before live use
5. Interval coverage: `0.8935` for the nominal 90% band → acceptable first pass after conformal calibration
6. Interval average width: `0.2866`
7. Saved conformal adjustments: `overall=0.005816`, `powerplay=0.003884`, `middle=0.007379`, `death=0.003225`

## Step 5: Wire into live predictor

Basic training artifacts now exist and live ODM inference is now wired in advisory-only mode.

```powershell
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/t20_male_feature_store_v2 \
  --league ipl \
  --output-json data/live_state.json \
  --odm-model-dir models/odm_v1
```

Expected runtime behavior:

1. ODM returns `warming_up` until 12 historical ML probabilities exist.
2. After warm-up, live JSON includes an `odm` payload with direction, confidence, and a 90% interval for the next 12-ball delta.
3. The central delta point estimate is explicitly flagged as experimental and not for primary decision use.
4. Core ML probability output remains unchanged.

## Step 6: Replay smoke test on recorded states

Use the available `data/match_states/ipl` and `data/match_states/psl` files to confirm inference wiring and output shape, not to claim final model quality.
