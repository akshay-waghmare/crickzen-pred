# Research: Odds Direction Model V1

## Decision 1: Target the 12-ball movement of ML probability, not resource-win-probability or market odds

**Decision**: Use `ml_delta_12 = ml_prob[i+12] - ml_prob[i]` as the primary target, where `ml_prob` is generated from `models/t20_male_v2/champion_model.joblib`.

**Rationale**: This aligns the ODM with the probability output the repo already uses operationally. It also reflects richer context than `resource_win_prob`, which is only one input into the global model.

**Alternatives considered**:

1. `resource_win_prob` delta only: rejected because it is easier to compute but less aligned to the actual ML output the user wants to time.
2. Historical market odds delta: rejected because historical odds are not available.

## Decision 2: Keep momentum as the mandatory baseline and residual as a sidecar analysis target

**Decision**: Benchmark against `momentum_baseline_12 = ml_prob[i] - ml_prob[i-12]` and compute `residual_delta_12 = ml_delta_12 - momentum_baseline_12`, but do not make residual the primary deployed target in V1.

**Rationale**: Momentum is the simplest plausible explanation for near-term probability drift. If ODM cannot beat it, ODM is not useful. Residual is still worth computing because it highlights whether the model adds signal beyond trend continuation.

**Alternatives considered**:

1. Ship residual-target model first: rejected because it adds complexity before proving the direct target is learnable.
2. Ignore baseline comparison: rejected because it would not address the self-referential risk documented in the spec.

## Decision 3: Export a new ODM base parquet instead of training directly from existing `training.parquet`

**Decision**: Add an ODM-specific base export from `src/bbl_pipeline/data/processor.py` that preserves `match_id`, `innings`, `over`, and `ball` together with current features.

**Rationale**: The existing `data/ipl_features_v1/training.parquet` and `data/psl_features_v1/training.parquet` have the feature columns ODM needs, but local inspection shows they do not contain `match_id`, `over`, or `ball`. Without those keys, a 12-ball-ahead target cannot be built safely.

**Alternatives considered**:

1. Infer sequence from current parquet ordering: rejected because that risks cross-match leakage and invalid targets.
2. Train only from `data/match_states/*`: rejected because only one IPL and one PSL recorded parquet are currently available locally.

## Decision 4: Use XGBoost regressors for V1

**Decision**: Use XGBoost-based regression for central delta and interval bounds.

**Rationale**: XGBoost is already a first-class dependency in the repo and fits the current training stack. It is fast enough for live inference and does not require introducing LightGBM or a separate probabilistic framework just to get V1 shipped.

**Alternatives considered**:

1. LightGBM quantile regression: rejected for V1 because it adds a new dependency and the repo already standardizes on XGBoost.
2. Neural or sequence models: rejected because they are unnecessary before a tabular baseline has proven useful.
3. Logistic-only direction model: rejected because the user explicitly wants magnitude and interval outputs, not just sign.

## Decision 5: Make ODM an optional advisory layer in live inference

**Decision**: Integrate ODM into `crex_live_predictor.py` as an optional block that can report `warming_up` until enough history exists.

**Rationale**: The current predictor already maintains prediction history and writes JSON outputs. ODM can slot into that path without re-architecting live inference or touching the main probability model.

**Alternatives considered**:

1. New service or app endpoint first: rejected because it is more infrastructure than the repo needs for V1.
2. Mandatory ODM dependency in predictor: rejected because ODM should not break live predictions if the artifact is absent or underperforming.

## Decision 6: Recorded match states are replay validation only in V1

**Decision**: Use the two available recorded match-state parquet files only for smoke/replay validation, not for model training.

**Rationale**: The sample is far too small for model fitting, but still useful to confirm the live predictor integration path works end to end.

**Alternatives considered**:

1. Mix recorded state data into training: rejected because sample size is negligible and likely to create false confidence.
