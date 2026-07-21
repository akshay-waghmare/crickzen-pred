# Quickstart — The Hundred Model

This is the controlled execution path. The source audit must produce the expected
manifest before model metrics are inspected.

## 1. Audit source data

```powershell
python scripts/audit_hundred_data.py --input-dir hnd_json --output-dir experiments/hundred_v1/audit
```

Confirm that the report contains 322 parseable files, 2021–2025 coverage, both genders,
301 standard v1 matches, and explicit quarantine counts. Do not continue if files disappear
without a reason code.

## 2. Run the pipeline

```powershell
bbl-pipeline retrain --league hundred_all --version v1 --n-splits 5
```

Expected isolated outputs:

```text
data/hundred_all_raw/
data/hundred_all_features_v1/
data/hundred_all_feature_store_v1/
models/hundred_all_v1/
```

The exact directory names may follow the existing CLI convention, but no output may
overwrite `models/t20_*`, `models/odi_*`, or their feature stores.

## 3. Validate the candidate

```powershell
python scripts/evaluate_hundred_promotion.py `
  --input-file data/hundred_all_features_v1/training.parquet `
  --t20-model models/t20_all_v2/champion_model.joblib `
  --holdout-season 2025 `
  --output-dir experiments/hundred_v1/evaluation
```

The report must include overall, male, female, innings, phase, Brier, log loss, ECE,
reliability, and sample/match counts.

## 4. Run focused tests

```powershell
pytest tests/unit/test_hundred_format_config.py tests/unit/test_hundred_normalization.py tests/unit/test_hundred_inference_parity.py
pytest tests/integration/test_hundred_pipeline.py
```

The candidate is research-only until the promotion checklist in `plan.md` is satisfied.
