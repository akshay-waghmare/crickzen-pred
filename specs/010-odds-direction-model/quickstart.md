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

## Step 3: Evaluate against baselines

```powershell
python scripts/validation/validate_odm_dataset.py data/odm_v1/training.parquet
```

Minimum go/no-go checks:

1. ODM dataset builds without alignment or null failures.
2. `momentum_baseline_12` is available everywhere the target is available.
3. Baseline slices exist overall, by league, by innings, and by phase.
4. Phase 4 training is the next step after this dataset checkpoint.

## Step 4: Wire into live predictor

This is not implemented in the current checkpoint. V1 live inference waits for Phase 4 and Phase 5 ODM model artifacts.

```powershell
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/t20_male_feature_store_v2 \
  --league ipl \
  --output-json data/live_state.json \
  --odm-model-dir models/odm_v1
```

Expected runtime behavior after later phases:

1. ODM returns `warming_up` until 12 historical ML probabilities exist.
2. After warm-up, live JSON includes direction, central delta, interval, and momentum comparison.
3. Core ML probability output remains unchanged.

## Step 5: Replay smoke test on recorded states

Use the available `data/match_states/ipl` and `data/match_states/psl` files to confirm inference wiring and output shape, not to claim final model quality.
