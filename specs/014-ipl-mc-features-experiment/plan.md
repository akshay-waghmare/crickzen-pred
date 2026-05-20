# Implementation Plan: IPL MC Features Experiment

**Spec**: `specs/014-ipl-mc-features-experiment/spec.md`  
**Branch**: `014-ipl-mc-features-experiment`  
**Date**: 2026-04-27  

---

## Summary

Run an offline, leak-free IPL experiment to test whether calibrated Monte Carlo outputs improve the existing ML model. The experiment will generate MC-derived features for IPL v6 training rows, evaluate several feature variants against the current feature baseline, and produce a go/no-go report focused on Brier score, ECE, and log loss. No production model or registry entry is changed unless a later promotion task is explicitly approved.

---

## Core Hypothesis

The current ML model already uses `resource_win_prob`, which is a strong but deterministic resource-based estimate. Calibrated MC output may add value because it captures forward-looking uncertainty and near-term path risk. The useful signal may be:

- `mc_win_prob`: calibrated MC estimate
- `mc_resource_gap`: where MC disagrees directionally with resource probability
- `mc_resource_abs_gap`: how uncertain or unusual the state looks
- `mc_simulation_std`: path uncertainty from simulation

The experiment should answer:

1. Does MC improve Brier?
2. Does MC improve ECE?
3. Does MC improve log loss?
4. Are improvements stable by innings and phase?
5. Is the improvement large enough to justify extra live latency?

---

## Pre-flight Checks

```powershell
# Verify baseline data
Test-Path data/ipl_features_v6/training.parquet
Test-Path data/ipl_features_v6/training_sampled.parquet

# Verify baseline model artifacts
Test-Path models/ipl_v6/champion_model.joblib
Test-Path models/ipl_v6/oof_calibration_results.csv
Test-Path models/ipl_v6/OOF_CALIBRATION_REPORT.md

# Inspect columns needed to reconstruct MC states
python - <<'PY'
import pandas as pd
df = pd.read_parquet("data/ipl_features_v6/training_sampled.parquet")
print(df.shape)
print(sorted(df.columns.tolist()))
PY
```

Expected state fields, either directly or mappable:

- innings
- over
- ball
- current score or score
- wickets lost
- target runs for innings 2
- batting team
- bowling team
- winner label (`is_winner`)
- `resource_win_prob`

If any required fields are missing, add a reconstruction step from `data/ipl_raw/matches/` or IPL JSON before running MC simulation.

---

## Step 1 - Create Experiment Directory

All generated artefacts live under:

```text
experiments/ipl_mc_features_v1/
```

Expected outputs:

```text
experiments/ipl_mc_features_v1/
  mc_feature_cache.parquet
  cache_quality.json
  metrics.csv
  segment_metrics.csv
  feature_importance.csv
  reliability_bins.csv
  REPORT.md
```

This directory is intentionally separate from `models/ipl_v6`.

---

## Step 2 - Implement MC Feature Cache Generator

Create:

```text
scripts/analyze_ipl_mc_features_experiment.py
```

Recommended CLI:

```powershell
python scripts/analyze_ipl_mc_features_experiment.py `
  --input data/ipl_features_v6/training_sampled.parquet `
  --output-dir experiments/ipl_mc_features_v1 `
  --mode pilot `
  --n-sims 300 `
  --seed 42
```

Full run:

```powershell
python scripts/analyze_ipl_mc_features_experiment.py `
  --input data/ipl_features_v6/training.parquet `
  --output-dir experiments/ipl_mc_features_v1 `
  --mode full `
  --n-sims 1000 `
  --resume `
  --seed 42
```

### Cache generation rules

For each eligible row:

1. Build a `bbl_pipeline.simulation.state.MatchState`.
2. Run MC with a fixed horizon, initially 6 balls, because the dashboard/live blend already exposes six-ball MC.
3. Store raw MC output:
   - `mc_raw_win_prob = result.mean_prob`
   - `mc_simulation_std = result.std_prob`
4. Store row key metadata:
   - row index
   - match id if available
   - innings
   - over/ball
   - seed
   - n-sims
   - horizon
5. Do not use actual outcome during raw MC generation.

### Important evaluator rule

Use an independent MC evaluator that does not depend on the candidate ML model. Do not run MC with the same ML model that will later consume MC features. That creates circular inference.

For this experiment, default MC terminal evaluation should be resource-based or use a stable pre-existing non-candidate evaluator. Document the chosen mode in `cache_quality.json`.

---

## Step 3 - Fold-Local MC Calibration

The raw cache can be generated once, but calibrated `mc_win_prob` must be produced inside each evaluation fold:

1. Split data using the same time-series/CV protocol for all methods.
2. For each fold:
   - fit MC calibrator using train fold `mc_raw_win_prob` and train labels only
   - transform validation fold `mc_raw_win_prob` to `mc_win_prob`
   - compute gap features on the validation fold using calibrated `mc_win_prob`
3. Repeat for every fold.

Recommended calibrators:

- Start with Platt/logistic calibration by innings.
- Add phase or innings-phase calibrators only if each segment has enough samples.
- Record calibrator type in the output metrics.

Never use an MC calibrator trained on the full dataset for fold validation metrics.

---

## Step 4 - Model Variants

Evaluate these variants under the same split protocol:

| Method | Feature Treatment |
| --- | --- |
| `baseline_ipl_v6_features` | Current `XGBLogRegEnsemble.TOP_FEATURES` only |
| `mc_standalone_calibrated` | `mc_win_prob` only, no ML features |
| `ml_add_mc_win_prob` | Baseline features plus `mc_win_prob` |
| `ml_add_mc_gap_features` | Baseline features plus `mc_win_prob`, `mc_resource_gap`, `mc_resource_abs_gap`, `mc_simulation_std` |
| `ml_replace_resource_with_mc` | Replace `resource_win_prob` with `mc_win_prob` |

Because `XGBLogRegEnsemble` selects from a fixed `TOP_FEATURES` list, the experiment must explicitly extend the candidate feature list. Do this inside the experiment script first. Do not change production `TOP_FEATURES` until the experiment passes gates.

Suggested implementation:

```python
class IPLMCFeatureEnsemble(XGBLogRegEnsemble):
    TOP_FEATURES = [
        "mc_win_prob",
        "mc_resource_gap",
        "mc_resource_abs_gap",
        "mc_simulation_std",
        *XGBLogRegEnsemble.TOP_FEATURES,
    ]
```

For the replacement variant, copy the frame and assign:

```python
df_variant["resource_win_prob"] = df_variant["mc_win_prob"]
```

---

## Step 5 - Evaluation Protocol

Minimum evaluation:

1. **Pilot** on `training_sampled.parquet`
2. **Full OOF/time-series CV** on `training.parquet`
3. **Time holdout** if a reliable date column exists or can be joined:
   - train: seasons before the most recent completed season
   - holdout: most recent completed season

Metrics:

- Brier score
- ECE, 10-bin
- Log loss
- Count `n`

Segments:

- overall
- innings 1
- innings 2
- phase:
  - powerplay
  - middle
  - death
- optional over buckets:
  - 0-5
  - 6-10
  - 11-15
  - 16-20

Output shape for `metrics.csv`:

```csv
method,split,segment,n,brier,ece,log_loss,baseline_brier_delta,baseline_ece_delta,baseline_log_loss_delta
```

Negative deltas mean improvement.

---

## Step 6 - Promotion Gates

Do not promote unless the best MC-augmented ML variant passes all gates:

1. Overall Brier improves by at least 0.001 absolute versus baseline.
2. Overall log loss is not worse than baseline and ideally improves by at least 0.002 absolute.
3. Overall ECE is not worse than baseline.
4. No innings segment worsens Brier by more than 0.003 absolute.
5. No major phase segment worsens Brier by more than 0.003 absolute.
6. Feature importance shows at least one MC feature is used with non-trivial importance.
7. The improvement is visible in both OOF/CV and time holdout, if holdout is available.

If only `mc_standalone_calibrated` wins but MC-augmented ML does not, do not promote as an ML feature change. That result suggests the MC output is useful as a separate blend input, not as a training feature.

---

## Step 7 - Optional Candidate Model

Only after promotion gates pass, train a candidate:

```text
models/ipl_v7_mc_features_candidate/
```

The candidate must include:

- `champion_model.joblib`
- selected feature metadata including MC fields
- MC feature-generation metadata
- calibration artefacts
- `EXPERIMENT_REPORT.md` copied from the experiment output

Do not update:

- `models/ipl_v6`
- `models/model_registry.json` active IPL entry
- dashboard default model path

Those are separate production rollout tasks.

---

## Step 8 - Live Inference Risk Check

Before production, measure:

1. Baseline IPL v6 prediction latency.
2. MC feature generation latency.
3. Candidate ML prediction latency after MC features are appended.
4. Total update latency under dashboard poll interval.

If latency is too high:

- reduce n-sims
- cache MC by state key where possible
- run MC asynchronously and fall back to baseline ML while MC is pending
- keep MC features out of production ML and use them only as a dashboard diagnostic

---

## Validation Commands

Focused checks after implementation:

```powershell
python scripts/analyze_ipl_mc_features_experiment.py `
  --input data/ipl_features_v6/training_sampled.parquet `
  --output-dir experiments/ipl_mc_features_v1 `
  --mode pilot `
  --n-sims 100 `
  --seed 42

Test-Path experiments/ipl_mc_features_v1/metrics.csv
Test-Path experiments/ipl_mc_features_v1/REPORT.md
```

Report inspection:

```powershell
Import-Csv experiments/ipl_mc_features_v1/metrics.csv |
  Where-Object { $_.segment -eq "overall" } |
  Format-Table method,split,n,brier,ece,log_loss,baseline_brier_delta,baseline_ece_delta,baseline_log_loss_delta -AutoSize
```

---

## Rollback Plan

Because this is an experiment, rollback is simple:

- Delete `experiments/ipl_mc_features_v1/`
- Do not touch `models/ipl_v6`
- Do not touch `models/model_registry.json`
- Do not update dashboard configs

If a candidate model was created, leave it inactive or delete only `models/ipl_v7_mc_features_candidate/`.

---

## Open Questions

1. Should MC horizon be fixed at 6 balls, or should the experiment include 12-ball and 30-ball variants?
2. Should calibrated MC probability use Platt only, or compare Platt vs isotonic by innings/phase?
3. Should the final production design use MC features inside ML, or keep MC and ML separate and blend them after calibration?
4. What is the maximum acceptable live added latency for IPL dashboard updates?
