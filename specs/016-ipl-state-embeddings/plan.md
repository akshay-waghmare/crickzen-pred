# Implementation Plan: IPL Regime-Aware State Embeddings

**Branch**: `016-ipl-state-embeddings` | **Date**: 2026-05-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/016-ipl-state-embeddings/spec.md`

## Summary

Build an IPL-only, offline-first pilot that turns existing IPL v6 training rows into a reusable state-embedding corpus, discovers repeatable regimes with simple scikit-learn tooling, retrieves historical analogues without leakage, and tests whether regime-aware numeric features improve the current IPL baseline.

**Technical Approach**:
- Use `data/ipl_features_v6/training*.parquet` as the primary corpus, with `data/ipl_raw/matches/*.parquet` only for missing date/context backfill.
- Fit train-only `StandardScaler` + `PCA`, then use `KMeans` for regime discovery and exact `NearestNeighbors` for analogue retrieval.
- Reuse the existing leak-aware experiment pattern from `scripts/analyze_ipl_mc_features_experiment.py` for time-ordered CV, baseline deltas, and promotion gates.
- Keep V1 implementation KISS: no UMAP, HDBSCAN, FAISS, Qdrant, live service, or dashboard integration.

## Technical Context

**Language/Version**: Python >=3.10 (from `pyproject.toml`), Markdown/YAML for plan artefacts  
**Primary Dependencies**: pandas, numpy, pyarrow, scikit-learn (`StandardScaler`, `PCA`, `KMeans`, `NearestNeighbors`), joblib, structlog, existing `bbl_pipeline` modules  
**Storage**: Parquet/CSV/JSON/Markdown artefacts under `experiments/ipl_state_embeddings_v1/`; spec artefacts under `specs/016-ipl-state-embeddings/`; no new database or service  
**Testing**: `pytest` for helper modules plus sampled-script smoke runs on `data/ipl_features_v6/training_sampled.parquet`  
**Target Platform**: Local/offline Windows or Linux CPU workflow  
**Project Type**: Single Python project extending `src/bbl_pipeline/` plus one orchestration script in `scripts/`  
**Performance Goals**: Sampled pilot completes in a practical local session; full run is resumable/restart-safe; retrieval batches finish in seconds, not minutes  
**Constraints**: IPL-only for V1; offline-first; ML-first; calibration-first; train-only fitting for scaler/PCA/KMeans/NN; no self/future leakage; training rows before raw backfill; no new heavyweight dependencies; go/no-go requires beating baseline on both Brier and log loss without material calibration/segment regression  
**Scale/Scope**: `data/ipl_features_v6/training.parquet` currently has 278,954 rows / 65 columns; raw backfill lives in `data/ipl_raw/matches/`; live logged IPL states exist in `data/match_states/ipl/` but are too small to be the primary V1 corpus

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Scalability & Reusability | ✅ PASS | V1 is IPL-only by spec, but the implementation stays reusable by isolating league-specific defaults in corpus config and file paths rather than hardcoding logic into shared algorithms. |
| II. Pipeline-Driven Architecture & Rapid Retraining | ✅ PASS | The pilot is an offline pipeline: corpus build → embedding fit → regime/retrieval eval → baseline comparison. It can rerun from `training_sampled.parquet` or `training.parquet` with one command. |
| III. Reproducibility & Versioning | ✅ PASS | Random seed, split policy, PCA/KMeans params, and artefact manifests will be saved with experiment outputs. |
| IV. Data Integrity & Entity Consistency | ✅ PASS | Primary source is existing IPL feature rows with stable `match_id/innings/over/ball`; raw parquet backfill is limited to missing date/context and uses existing team/venue strings already present in the repo pipeline. |
| V. Model Calibration & Observability | ✅ PASS | Evaluation explicitly reports baseline vs candidate Brier, log loss, and ECE overall and by innings/phase. No-go is mandatory if Brier and log loss do not both beat baseline or calibration/segment behaviour worsens materially. |

**Post-design verdict**: PASS. No constitution violation is required for V1.

## Project Structure

### Documentation (this feature)

```text
specs/016-ipl-state-embeddings/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── offline-pilot.openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
scripts/
└── analyze_ipl_state_embeddings_experiment.py   # NEW orchestration CLI

src/bbl_pipeline/analysis/
└── state_embeddings/
    ├── __init__.py
    ├── types.py                                 # dataclasses / typed records
    ├── corpus.py                                # corpus build + window assembly + quality report
    ├── embeddings.py                            # scaler/PCA fit-transform + persistence
    ├── retrieval.py                             # NN fit/query + leakage guards + analogue summaries
    └── evaluation.py                            # regime metrics, baseline comparison, report helpers

tests/
├── unit/
│   └── analysis/
│       └── state_embeddings/
│           ├── test_corpus.py
│           ├── test_retrieval.py
│           └── test_evaluation.py
└── integration/
    └── test_ipl_state_embeddings_experiment.py
```

### Experiment Artefacts

```text
experiments/ipl_state_embeddings_v1/
├── corpus/
│   ├── embedding_corpus.parquet
│   ├── window_corpus.parquet
│   └── corpus_manifest.json
├── models/
│   ├── scaler.joblib
│   ├── pca.joblib
│   ├── kmeans.joblib
│   └── neighbors.joblib
├── regimes/
│   ├── regime_assignments.parquet
│   └── regime_summary.csv
├── retrieval/
│   ├── analogue_results.parquet
│   └── retrieval_summary.json
├── features/
│   └── regime_features.parquet
└── evaluation/
    ├── metrics.csv
    ├── segment_metrics.csv
    ├── reliability_bins.csv
    └── PILOT_REPORT.md
```

**Structure Decision**: Keep the first implementation as one offline experiment script plus a small reusable `state_embeddings` helper package under `src/bbl_pipeline/analysis/`.

## Phase 0: Research

### Research Tasks

1. Confirm the primary IPL baseline dataset, model artefacts, and evaluation pattern.
2. Confirm what match-state keys already exist in `data/ipl_features_v6/training.parquet`.
3. Confirm whether raw IPL parquet can backfill date/window context when needed.
4. Confirm reusable repo patterns for calibration/segment reporting and state logging.
5. Resolve the simplest feasible embedding/retrieval stack that matches repo reality.

### Research Findings

See [research.md](research.md). Key outcomes:
- Use `data/ipl_features_v6/training*.parquet` first, because it already contains `match_id`, `innings`, `over`, `ball`, teams, outcome, and `resource_win_prob`.
- Use raw IPL parquet only to backfill missing `date`, `venue`, or prior-ball continuity for window construction.
- Reuse the existing time-ordered CV and baseline-delta pattern from `scripts/analyze_ipl_mc_features_experiment.py`.
- Start with exact scikit-learn methods (`PCA`, `KMeans`, `NearestNeighbors`) and defer newer manifold/vector-db tooling.

## Phase 1: Design & Contracts

### Data Model

See [data-model.md](data-model.md) for the design of:
- `EmbeddingRecord`
- `StateWindowRecord`
- `RetrievalCorpus`
- `RegimeAssignment`
- `HistoricalAnalogue`
- `RegimeFeatureRow`
- `PilotEvaluationReport`

### API / Job Contracts

See [contracts/offline-pilot.openapi.yaml](contracts/offline-pilot.openapi.yaml) for the planned interfaces for:
- corpus build
- regime discovery
- analogue retrieval
- baseline evaluation

### Quickstart

See [quickstart.md](quickstart.md) for the intended pilot and full-run commands.

## Implementation Sequence

### Step 1 - Build a leakage-safe IPL corpus

Create a corpus builder that:

1. Loads `data/ipl_features_v6/training_sampled.parquet` for pilot and `training.parquet` for full runs.
2. Sorts rows by `match_id`, `innings`, `over`, `ball`, and backfilled `date` when available.
3. Builds a stable row key such as:

   ```text
   {match_id}:{innings}:{over}:{ball}
   ```

4. Keeps IPL feature rows as the primary corpus.
5. Uses raw IPL parquet only when a needed context field is missing or when prior-ball window history cannot be reconstructed from feature rows alone.
6. Excludes and counts:
   - super overs / reduced-over / structurally incomplete matches
   - terminal states with no balls remaining
   - rows missing enough context to trace or window safely

**KISS choice**: start with per-state corpus plus one short rolling window view; do not build sequence models in V1.

### Step 2 - Add a simple state-window representation

Represent each anchor state using:
- anchor row features
- prior up-to-6-ball rolling summaries from the same match and innings
- window metadata (`window_size`, `window_complete`, `source_row_keys`)

Window features should be simple aggregations, e.g.:
- runs in window
- wickets in window
- boundary rate in window
- change in current/required rate
- resource/probability delta across the window

This keeps the first pass compatible with tabular ML and avoids RNN/transformer complexity.

### Step 3 - Fit embeddings with train-only PCA

Use a train-only fit pipeline:

1. Choose the numeric state/window feature subset from the existing IPL feature frame.
2. Standardize with `StandardScaler`.
3. Reduce to a compact embedding with `PCA`.
4. Save scaler, PCA model, explained-variance summary, and transformed vectors.

**Planned V1 default**:
- exact scikit-learn pipeline
- tune PCA dimensionality from a small grid (for example 8/12/16 components)
- keep a raw-feature fallback baseline for ablation

### Step 4 - Discover regimes with simple clustering

Run `KMeans` on train embeddings only and assign regimes to validation rows.

Evaluation should include:
- regime coverage counts
- regime size distribution
- silhouette / centroid-separation summary
- stability across time-ordered folds or season slices
- outcome separation by overall/innings/phase win rate

Semantic labels such as `collapse_risk`, `pressure_state`, `acceleration_potential`, or `volatility_regime` should be generated from observed cluster summaries, not hand-authored first.

### Step 5 - Retrieve historical analogues

Fit exact `NearestNeighbors` on the train corpus and query held-out rows.

Leakage guards:
- exclude the same row key
- exclude same-match future rows
- exclude obvious duplicated event keys
- prefer earlier historical rows only when query date/ordering is available

Return for each query:
- ranked neighbour row keys
- distance / similarity
- source context (`match_id`, innings, over, ball, teams)
- downstream outcome summary
- regime summary of neighbours

### Step 6 - Build regime-aware numeric features

The first candidate features should stay simple and inference-feasible:

| Feature group | Initial fields |
|---|---|
| Retrieval summary | `neighbor_win_rate_k`, `neighbor_outcome_std_k`, `neighbor_mean_resource_prob_k`, `neighbor_distance_mean_k` |
| Regime summary | `regime_id`, `regime_confidence`, `regime_cluster_win_rate`, `regime_cluster_size` |
| Hybrid | combination of retrieval + regime summary |

Planned evaluation variants:

| Variant | Description |
|---|---|
| `baseline_ipl_v6_features` | Current IPL v6 feature set only |
| `regime_retrieval_features` | Baseline + retrieval summary features |
| `regime_cluster_features` | Baseline + regime summary features |
| `regime_hybrid_features` | Baseline + both sets |

Keep V1 numeric-first. Do not add text explanations, LLM layers, or live retrieval services.

### Step 7 - Evaluate against the current IPL baseline

Create `scripts/analyze_ipl_state_embeddings_experiment.py` by reusing the structure of `scripts/analyze_ipl_mc_features_experiment.py`:

1. Same split protocol for baseline and candidates.
2. Fold-local fitting for scaler, PCA, KMeans, and NN index.
3. Metrics at minimum:
   - Brier
   - log loss
   - ECE
   - sample count
4. Segments at minimum:
   - overall
   - innings 1 / innings 2
   - innings × phase (`powerplay`, `middle`, `death`)
5. Outputs:
   - baseline values
   - candidate values
   - delta vs baseline
   - retrieval quality summary
   - regime quality summary
   - final go/no-go verdict

**Preferred evaluation protocol**:
- pilot: `training_sampled.parquet`
- full OOF: `training.parquet`
- optional latest-season holdout if raw/date backfill is stable enough

### Step 8 - Enforce the go/no-go gate

Promotion is **NO-GO** unless at least one regime-aware ML variant passes all of these:

1. **Overall Brier beats `baseline_ipl_v6_features`.**
2. **Overall log loss beats `baseline_ipl_v6_features`.**
3. **Overall ECE does not materially worsen** (default V1 interpretation: no worse; if a small tolerance is introduced, it must be documented in the report).
4. **No key innings/phase segment materially regresses** on Brier or ECE.
5. Retrieval coverage remains high enough to support the feature (target: >=95% valid analogue set coverage on held-out queries).
6. Corpus coverage remains high enough to avoid cherry-picking (target: >=95% eligible rows represented or explicitly excluded with reason).

**Recommended initial material-regression thresholds**:
- segment Brier regression > `+0.003` = fail
- segment ECE regression > `+0.005` = fail

If no variant passes, the pilot still succeeds only by writing a decision-ready **NO-GO** report recommending no production change and no wider rollout.

### Step 9 - Keep production untouched in V1

This pilot must **not**:
- modify `models/ipl_v6`
- update model registry entries
- add live dashboard inference dependencies
- introduce vector DB infrastructure
- claim portability to BBL/PSL/other leagues

Only a later follow-up may consider production promotion if the offline gate passes.

## Validation Strategy

### Script-level validation

```powershell
python scripts/analyze_ipl_state_embeddings_experiment.py `
  --input data/ipl_features_v6/training_sampled.parquet `
  --output-dir experiments/ipl_state_embeddings_v1 `
  --mode pilot `
  --seed 42 `
  --resume
```

### Expected validation checks

1. `corpus_manifest.json` shows corpus coverage and exclusion reasons.
2. `regime_summary.csv` shows stable cluster coverage and interpretable summaries.
3. `retrieval_summary.json` shows held-out query coverage and leakage-filter counts.
4. `evaluation/metrics.csv` includes baseline/candidate Brier, log loss, ECE, and deltas.
5. `evaluation/PILOT_REPORT.md` ends with explicit `GO` or `NO-GO`.

### Test focus

- unit tests for row-key construction, window assembly, and exclusion logic
- unit tests for leakage filters in analogue retrieval
- unit tests for regime summary / gate evaluation helpers
- integration test for sampled end-to-end orchestration

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Embeddings add no value beyond scoreboard twins | Compare against baseline and inspect neighbour diversity / regime summaries explicitly. |
| Leakage through same-match neighbours | Enforce row-key, same-match, and future-row exclusion before scoring. |
| Windows need context not present in feature rows | Backfill only the missing context from raw IPL parquet; keep training rows primary. |
| Cluster labels are unstable | Mark unstable regimes unreliable rather than forcing semantics. |
| Aggregate gains hide segment damage | Gate on innings/phase segment behaviour, not just overall metrics. |
| Scope creep into live serving or new infra | Keep V1 offline and scikit-learn-only. |

## Complexity Tracking

> No constitution violations - table not required.
