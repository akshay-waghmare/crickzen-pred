# Data Model: IPL Regime-Aware State Embeddings

## 1. EmbeddingRecord

One eligible IPL state row used as the anchor unit for embedding, retrieval, and downstream feature generation.

| Field | Type | Notes |
|---|---|---|
| `row_key` | string | Stable key: `match_id:innings:over:ball` |
| `match_id` | string | Existing IPL match identifier |
| `date` | date/datetime nullable | Backfilled from raw parquet if needed for time ordering |
| `innings` | int | 1 or 2 |
| `over` | int | Ball anchor over |
| `ball` | int | Ball anchor ball number |
| `batting_team` | string | Source metadata |
| `bowling_team` | string | Source metadata |
| `winner` | string nullable | Historical outcome metadata |
| `is_winner` | int | Label for batting-side outcome |
| `resource_win_prob` | float | Existing baseline signal |
| `base_features` | vector/columns | Selected numeric feature subset from IPL v6 row |
| `embedding_vector` | float[] | PCA-transformed embedding |
| `source_priority` | enum | `feature_row` or `feature_row_with_raw_backfill` |
| `eligibility_status` | enum | `eligible` / `excluded` |
| `exclusion_reason` | string nullable | Counted in corpus manifest |

**Validation rules**
- `row_key` must be unique.
- `innings` must be 1 or 2.
- terminal / structurally incomplete states are excluded, not partially retained.

## 2. StateWindowRecord

Short rolling context attached to an anchor state.

| Field | Type | Notes |
|---|---|---|
| `window_id` | string | Derived from anchor `row_key` plus window size |
| `anchor_row_key` | string | FK to `EmbeddingRecord.row_key` |
| `window_size_balls` | int | Initial V1 target: up to 6 prior legal balls |
| `source_row_keys` | string[] | Ordered keys used in the window |
| `window_complete` | bool | False when some prior context is unavailable |
| `runs_in_window` | int | Aggregate signal |
| `wickets_in_window` | int | Aggregate signal |
| `boundary_rate_in_window` | float | Aggregate signal |
| `resource_delta_window` | float | Anchor-vs-window change |
| `run_rate_delta_window` | float | Anchor-vs-window change |

**Validation rules**
- all `source_row_keys` must belong to the same `match_id` and `innings`
- no future rows may appear in the window

## 3. RetrievalCorpus

Versioned artefact describing the fitted corpus and its provenance.

| Field | Type | Notes |
|---|---|---|
| `corpus_version` | string | e.g. `ipl_state_embeddings_v1` |
| `input_path` | string | Source parquet path |
| `raw_backfill_dir` | string nullable | Used only if needed |
| `eligible_rows` | int | Count used in corpus |
| `excluded_rows` | int | Count excluded |
| `exclusion_breakdown` | map | Reason → count |
| `feature_columns` | string[] | Numeric columns used pre-PCA |
| `window_fields` | string[] | Rolling fields used |
| `pca_components` | int | Stored fit config |
| `random_seed` | int | Reproducibility |
| `fit_split_policy` | string | Time-ordered CV / holdout policy |

## 4. RegimeAssignment

Cluster/regime output for one embedding row.

| Field | Type | Notes |
|---|---|---|
| `row_key` | string | FK to `EmbeddingRecord` |
| `regime_id` | int | KMeans cluster id |
| `regime_label` | string nullable | Derived summary label, e.g. `pressure_state` |
| `regime_confidence` | float | Inverse-distance or normalized confidence |
| `centroid_distance` | float | Raw cluster-distance signal |
| `regime_cluster_win_rate` | float | Historical cluster batting-side win rate |
| `regime_cluster_size` | int | Cluster support |
| `stability_flag` | enum | `stable`, `borderline`, `unstable` |

**Validation rules**
- every assigned row must trace back to a fitted train-time regime model
- unstable regimes remain reportable but are not treated as trustworthy semantic labels

## 5. HistoricalAnalogue

One ranked neighbour returned for a held-out query row.

| Field | Type | Notes |
|---|---|---|
| `query_row_key` | string | Held-out state |
| `neighbor_row_key` | string | Historical analogue |
| `rank` | int | 1..K |
| `distance` | float | Embedding-space distance |
| `neighbor_match_id` | string | Source context |
| `neighbor_innings` | int | Source context |
| `neighbor_over` | int | Source context |
| `neighbor_ball` | int | Source context |
| `neighbor_is_winner` | int | Historical outcome |
| `neighbor_resource_win_prob` | float | Baseline comparison context |
| `leakage_filter_applied` | bool | Should always be true in held-out eval |

**Validation rules**
- `neighbor_row_key != query_row_key`
- no same-match future analogue for a held-out query
- duplicate event analogues are removed before final ranking

## 6. RegimeFeatureRow

Numeric features joined back to the baseline ML frame for one eligible row.

| Field | Type | Notes |
|---|---|---|
| `row_key` | string | Join key |
| `neighbor_win_rate_k` | float | Mean batting win rate over top-K analogues |
| `neighbor_outcome_std_k` | float | Outcome volatility over top-K analogues |
| `neighbor_mean_resource_prob_k` | float | Analogue baseline context |
| `neighbor_distance_mean_k` | float | Similarity confidence |
| `regime_id` | int | Numeric regime id |
| `regime_confidence` | float | Confidence score |
| `regime_cluster_win_rate` | float | Cluster-level outcome summary |
| `regime_cluster_size` | int | Cluster support |

## 7. PilotEvaluationReport

Decision-ready output for the whole pilot.

| Field | Type | Notes |
|---|---|---|
| `variant` | string | Baseline or regime-aware candidate |
| `split` | string | Pilot / OOF / holdout |
| `segment` | string | overall, innings, innings-phase |
| `brier` | float | Lower is better |
| `log_loss` | float | Lower is better |
| `ece` | float | Lower is better |
| `baseline_brier_delta` | float | Negative = improvement |
| `baseline_log_loss_delta` | float | Negative = improvement |
| `baseline_ece_delta` | float | Negative = improvement |
| `retrieval_coverage` | float | Fraction of valid analogue sets |
| `corpus_coverage` | float | Fraction of eligible corpus rows retained |
| `gate_status` | enum | `pass` / `fail` |
| `gate_failures` | string[] | Explicit reasons |
| `recommendation` | enum | `go`, `no_go`, `interpretability_only` |

## Relationships

- `EmbeddingRecord 1 -> 0..1 StateWindowRecord`
- `EmbeddingRecord 1 -> 1 RegimeAssignment`
- `EmbeddingRecord 1 -> 0..K HistoricalAnalogue` as query
- `EmbeddingRecord 1 -> 0..1 RegimeFeatureRow`
- `RetrievalCorpus 1 -> many EmbeddingRecord`
- `PilotEvaluationReport` summarizes metrics derived from `RegimeFeatureRow` joins and held-out predictions

## State Transitions

### Corpus lifecycle

`raw_feature_row` → `eligible/excluded` → `embedded` → `assigned_regime` → `retrieval_ready` → `evaluated`

### Recommendation lifecycle

`draft_metrics` → `gates_checked` → `go` or `no_go`

No row may skip directly from `eligible` to `evaluated` without train-only embedding/retrieval fitting.
