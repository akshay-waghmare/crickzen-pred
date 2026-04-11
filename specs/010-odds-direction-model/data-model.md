# Data Model: Odds Direction Model V1

## Entity: OdmBaseRow

Represents one legal ball with the existing feature set plus sequence identifiers required for future-target construction.

| Field | Type | Notes |
|-------|------|-------|
| `league` | string | `ipl`, `psl`, and later other leagues |
| `match_id` | string | Source match identifier from raw parquet |
| `date` | datetime/string | Used for time-aware validation ordering |
| `season` | string | For slicing and lineage |
| `innings` | int | 1 or 2 |
| `over` | int | Over number from processed dataset |
| `ball` | int | Ball number within over |
| `resource_win_prob` | float | Existing feature |
| `is_winner` | int | Existing match outcome label |
| `...existing feature columns...` | numeric/bool | Reuse the current processed training features |

**Validation rules**

1. `(league, match_id, innings, over, ball)` must be unique.
2. Rows must be sorted by `(league, match_id, innings, over, ball)` before lag/lead operations.
3. No row may be used if sequence identifiers are missing.

## Entity: OdmTrainingSample

Represents one trainable sample after lag/lead target generation.

| Field | Type | Notes |
|-------|------|-------|
| `league` | string | Carried from base row |
| `match_id` | string | Used for grouped validation splits |
| `innings` | int | Prevent cross-innings target leakage |
| `phase` | string | Derived from over for sliced evaluation |
| `ml_prob` | float | Current global-model probability |
| `ml_prob_delta_6` | float | Recent 6-ball probability momentum |
| `ml_prob_delta_12` | float | Recent 12-ball probability momentum |
| `ml_rwp_gap` | float | `ml_prob - resource_win_prob` |
| `ml_rwp_gap_delta_6` | float | 6-ball change in the gap |
| `ml_delta_12` | float | Primary target |
| `momentum_baseline_12` | float | Baseline comparator |
| `residual_delta_12` | float | Sidecar experimental target |
| `direction_label` | int | `1` if `ml_delta_12 > 0`, else `0` |
| `feature_*` | numeric/bool | Final selected V1 feature set |

**Validation rules**

1. First 12 balls of an innings cannot have momentum features.
2. Last 12 balls of an innings cannot have future target labels.
3. Lead/lag operations must stay within the same `(league, match_id, innings)` group.

## Entity: OdmModelBundle

Serialized artifact stored in `models/odm_v1/champion_model.joblib`.

| Field | Type | Notes |
|-------|------|-------|
| `feature_columns` | list[string] | Exact column order for inference |
| `lower_model` | model object | Predicts lower quantile |
| `center_model` | model object | Predicts central delta |
| `upper_model` | model object | Predicts upper quantile |
| `horizon_balls` | int | Fixed at 12 for V1 |
| `global_model_dependency` | string | Expected path/version for `t20_male_v2` |
| `training_manifest` | dict | Source datasets, row counts, dates, params |

**Validation rules**

1. `feature_columns` must match the training dataset used to fit the artifact.
2. `horizon_balls` must be stored explicitly to avoid silent mismatch at inference.
3. `lower <= center <= upper` should hold after prediction, with clipping or correction if needed.

## Entity: OdmPrediction

Runtime inference output appended to live prediction JSON.

| Field | Type | Notes |
|-------|------|-------|
| `status` | string | `ready`, `warming_up`, `unavailable` |
| `direction` | string | `UP` or `DOWN` |
| `delta_mean` | float | Central predicted 12-ball change |
| `delta_ci_lower` | float | Lower interval bound |
| `delta_ci_upper` | float | Upper interval bound |
| `momentum_baseline` | float | Current simple-trend baseline |
| `edge_vs_momentum` | float | `delta_mean - momentum_baseline` |
| `horizon_balls` | int | 12 |
| `confidence` | string | Derived from interval width |

**Validation rules**

1. `warming_up` must be returned when fewer than 12 historical `ml_prob` values exist.
2. ODM output must not overwrite the existing `model_final_prob` fields.
3. Output labels must describe model-probability movement, not market movement.

## Relationships

1. `OdmBaseRow` is the raw ODM export from the processing pipeline.
2. `OdmTrainingSample` is derived from ordered groups of `OdmBaseRow`.
3. `OdmModelBundle` is trained from `OdmTrainingSample`.
4. `OdmPrediction` is produced by applying `OdmModelBundle` to live features plus recent ML-probability history.
