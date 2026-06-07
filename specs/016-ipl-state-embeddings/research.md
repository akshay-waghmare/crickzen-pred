# Research: IPL Regime-Aware State Embeddings

## Decision 1: Primary corpus should come from IPL v6 feature rows

**Decision**: Use `data/ipl_features_v6/training.parquet` and `training_sampled.parquet` as the primary retrieval and embedding corpus.

**Rationale**: The existing IPL feature dataset already contains `match_id`, `innings`, `over`, `ball`, `batting_team`, `bowling_team`, `is_winner`, and `resource_win_prob`, so it is immediately usable for a traceable, leakage-safe offline corpus. This also keeps the pilot aligned with the current IPL baseline and avoids a costly re-ingestion path.

**Alternatives considered**:
- Use live logged IPL states first — rejected because `data/match_states/ipl/` is too small for V1.
- Rebuild everything directly from raw JSON/parquet — rejected because the feature rows already represent the production-aligned baseline and should stay primary.

## Decision 2: Raw IPL parquet is backfill-only

**Decision**: Use `data/ipl_raw/matches/*.parquet` only to backfill missing `date`, `venue`, or prior-ball continuity needed for ordering and state-window construction.

**Rationale**: The raw IPL parquet has the needed ball-level context (`match_id`, `date`, `innings`, `over`, `ball`, `batting_team`, `winner`, `venue`) but should not replace the feature-row corpus. Keeping raw data as a secondary enrichment source preserves the spec requirement that historical analogue retrieval starts from existing feature/training rows first.

**Alternatives considered**:
- Ignore raw backfill entirely — rejected because time ordering and complete window reconstruction may need it.
- Make raw parquet the canonical corpus — rejected because it would duplicate existing feature engineering and increase pilot complexity.

## Decision 3: Start with a tabular embedding pipeline

**Decision**: Fit embeddings with train-only `StandardScaler` + `PCA` on selected numeric state and short-window features.

**Rationale**: This matches the repo’s current dependency footprint and keeps the pilot reproducible, cheap, and easy to ablate against the raw-feature baseline. PCA is enough to test whether compact state structure helps retrieval and downstream ML before exploring more complex manifold methods.

**Alternatives considered**:
- Use the raw feature space only — rejected because the feature asks for a compact embedding and regime discovery layer.
- Add UMAP immediately — rejected because the repo can already test feasibility with PCA and because new dependencies are explicitly out of scope for V1.

## Decision 4: Use KMeans for regime discovery

**Decision**: Use `KMeans` on PCA embeddings as the first regime-discovery method, with train-only fitting and validation on later folds/slices.

**Rationale**: KMeans is available now, simple to persist, and easy to summarize with coverage, centroid distance, and cluster outcome separation. That is enough to test whether repeatable IPL regimes exist before moving to density-based clustering.

**Alternatives considered**:
- Manual heuristic buckets only — rejected because the feature asks for evidence-based regime discovery rather than narrative grouping.
- HDBSCAN or other density clustering — rejected for V1 because they add complexity and new dependencies too early.

## Decision 5: Use exact nearest-neighbour retrieval

**Decision**: Use exact `NearestNeighbors` over train embeddings for historical analogue retrieval.

**Rationale**: Exact NN is fast enough at the current IPL scale, keeps leakage handling simple, and avoids infrastructure like FAISS or Qdrant. It also makes debugging easier because every neighbour can be inspected directly.

**Alternatives considered**:
- FAISS / ANN indexing — rejected because the pilot scale does not require it.
- Raw SQL- or rules-based lookup — rejected because it would not test whether embeddings preserve useful state similarity.

## Decision 6: Evaluate by extending the existing IPL experiment pattern

**Decision**: Reuse the evaluation shape from `scripts/analyze_ipl_mc_features_experiment.py`: time-ordered CV, fold-local fitting, baseline deltas, innings/phase segments, and explicit gate reporting.

**Rationale**: The repo already has a leak-aware IPL baseline comparison script that measures Brier, ECE, and log loss by overall and segment. Reusing that pattern keeps the new pilot calibration-first and avoids inventing a second reporting standard.

**Alternatives considered**:
- Run only a qualitative retrieval demo — rejected because the spec requires decision-ready baseline comparison.
- Evaluate only aggregate metrics — rejected because the spec explicitly requires segment-level calibration/regression visibility.

## Decision 7: Go/no-go must be strict

**Decision**: The pilot is `GO` only if a regime-aware variant beats the current IPL baseline on **both** Brier and log loss and does not materially worsen ECE or key innings/phase behaviour.

**Rationale**: This feature is interesting only if it produces measurable predictive value, not just interpretability. The repo constitution and spec both prioritize calibration and evidence-based promotion, so interpretability-only wins are documented but do not justify rollout.

**Alternatives considered**:
- Promote on Brier alone — rejected because the user explicitly requires both Brier and log loss.
- Promote on interpretability gains without baseline wins — rejected because V1 is a feasibility pilot, not a storytelling feature.
