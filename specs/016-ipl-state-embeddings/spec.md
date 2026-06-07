# Feature Specification: IPL Regime-Aware State Embeddings

**Feature Branch**: `016-ipl-state-embeddings`  
**Created**: 2026-05-26  
**Status**: Draft  
**Input**: Build an IPL-first, regime-aware match state embedding pilot that stays ML-first, uses existing repo assets, and tests offline retrieval/calibration value before any wider rollout.

## Definitions

- **State embedding**: A compact numeric representation of one IPL match state or short state window that preserves match context for offline similarity search and regime discovery.
- **State window**: A small sequence of recent IPL states used to represent momentum or transition context instead of a single ball in isolation.
- **Regime**: A repeatable family of match states with shared context and risk profile, such as collapse risk, pressure state, tactical instability, acceleration potential, or volatility regime.
- **Historical analogue**: A prior IPL state or window that is judged similar enough to the current query state to support comparison, explanation, or feature generation.
- **Retrieval corpus**: The offline IPL reference set used for regime discovery and analogue lookup. In V1 this comes primarily from historical IPL feature/training rows, with raw IPL JSON backfill only if needed.
- **Regime-aware feature**: A derived signal from embeddings or retrieval, such as regime ID, regime confidence, neighbour outcome summary, or regime-conditioned calibration bucket.

## Current State

### What Already Exists

- Multiple IPL feature stores and training datasets already exist in the repo under `data/ipl_features_*` and `data/ipl_feature_store_*`, including `data/ipl_features_v6`.
- IPL model directories already exist under `models/ipl_*`, including `models/ipl_v6`, giving a practical baseline for comparison.
- The Monte Carlo engine already exists under `src/bbl_pipeline/simulation/`.
- Live state logging and state analysis already exist through `src/bbl_pipeline/inference/match_state_logger.py` and `src/bbl_pipeline/analysis/state_analyzer.py`.
- MC calibration tooling already exists through `src/bbl_pipeline/calibration/mc_trainer.py`.
- A leak-aware pattern for testing feature/calibration impact already exists in `scripts/analyze_mc_cal_as_feature.py`.
- The repo already has the local dependency footprint needed for a first-pass offline pilot using simple PCA, KMeans, and nearest-neighbour style workflows before considering newer manifold, density-clustering, or vector-database tooling.

### What Is Missing

- No IPL-specific embedding corpus exists for state-level or window-level retrieval experiments.
- No offline regime discovery workflow exists for IPL match states.
- No historical analogue retrieval evaluation exists for IPL embeddings.
- No regime-aware experiment currently measures whether embedding-derived features improve IPL probabilities, MC interpretation, or calibration quality.
- Live logged IPL state history is still limited, so live-only retrieval is not yet feasible as the primary corpus.

---

## User Scenarios & Testing

### User Story 1 - Build IPL Embedding Corpus (Priority: P1)

As a model developer, I want to build an IPL-only embedding dataset from existing historical feature rows and match data, so that regime discovery and retrieval experiments start from a reusable, leakage-safe corpus instead of ad hoc samples.

**Why this priority**: The corpus is the foundation for every later regime, retrieval, and calibration test. Without a reliable IPL corpus, all downstream conclusions are weak.

**Independent Test**: Run the corpus build workflow and verify it creates a reusable IPL embedding dataset with stable row keys, source metadata, and enough coverage to support offline experiments.

**Acceptance Scenarios**:

1. **Given** historical IPL feature rows are available, **When** the corpus builder runs, **Then** it creates an IPL-only state dataset keyed to match, innings, over, ball, and outcome context.
2. **Given** live logged IPL states are insufficient, **When** the corpus is assembled, **Then** historical IPL training rows are used as the primary corpus and raw IPL JSON is used only as a backfill source where needed.
3. **Given** a state window view is required, **When** the workflow generates window records, **Then** each window remains traceable back to the original IPL match states used to create it.

---

### User Story 2 - Discover and Evaluate Regimes Offline (Priority: P1)

As a model developer, I want to discover repeatable IPL regimes offline and score their stability, separation, and usefulness, so that regime labels are evidence-based rather than narrative guesswork.

**Why this priority**: The feature only matters if regimes are measurable and repeatable across historical IPL data.

**Independent Test**: Run the regime discovery workflow and verify it outputs named regime summaries, regime coverage counts, and offline evaluation tables showing whether regimes are stable and meaningful.

**Acceptance Scenarios**:

1. **Given** an IPL embedding corpus exists, **When** regime discovery runs, **Then** it produces regime assignments or regime scores for eligible IPL states.
2. **Given** regimes are proposed, **When** offline evaluation runs, **Then** the report shows regime coverage, outcome separation, and stability across validation splits or time slices.
3. **Given** a regime label such as collapse risk or acceleration potential is surfaced, **When** the report is reviewed, **Then** it includes the observable state patterns that justify that label.

---

### User Story 3 - Retrieve Historical Analogues (Priority: P1)

As a model developer, I want to retrieve similar historical IPL states from the embedding space, so that I can inspect what usually happened next in comparable situations.

**Why this priority**: Analogue retrieval is the most direct proof that the embeddings preserve useful cricket context.

**Independent Test**: Submit held-out IPL query states and verify the system returns valid historical analogues with source metadata, similarity ranking, and downstream outcome summaries.

**Acceptance Scenarios**:

1. **Given** a held-out IPL query state, **When** analogue retrieval runs, **Then** it returns the top similar historical IPL states without returning the exact same source row.
2. **Given** retrieved analogues are returned, **When** the result is inspected, **Then** each analogue includes enough source context to understand match situation and what happened next.
3. **Given** query states come from a later evaluation period, **When** retrieval is evaluated, **Then** the analogue set excludes future leakage from the same match or later-labelled duplicates.

---

### User Story 4 - Test Regime-Aware Probability Impact vs Current IPL Baseline (Priority: P1)

As a model owner, I want to test whether regime-aware features beat the current IPL production-aligned baseline on Brier score and log loss, while preserving acceptable calibration, so that I can decide if the idea deserves wider rollout.

**Why this priority**: The pilot succeeds only if it delivers a concrete offline answer on whether embeddings or regime-aware features outperform the current IPL feature-model setup, not just whether they are interesting.

**Independent Test**: Run a baseline-versus-regime-aware IPL experiment and verify it reports baseline and candidate scores, plus delta versus baseline for Brier, log loss, and ECE, along with a go/no-go recommendation.

**Acceptance Scenarios**:

1. **Given** the current IPL production-aligned baseline exists, **When** regime-aware experiment variants are evaluated, **Then** each variant is compared against that same baseline on the same holdout protocol.
2. **Given** regime-aware features are added, **When** the experiment report is generated, **Then** it explicitly answers whether the candidate beats the previous Brier score and log loss and includes delta versus baseline for Brier, log loss, and ECE.
3. **Given** regime-aware features are added, **When** calibration metrics are produced, **Then** the report shows whether they improve, worsen, or only re-segment model confidence in key innings and phase segments.
4. **Given** no regime-aware variant clears the promotion bar, **When** the pilot report is finalized, **Then** it explicitly recommends no production change and no broader rollout.

---

## Edge Cases

- **Sparse live IPL logs**: If logged IPL state history is too small for meaningful retrieval, the pilot must fall back to historical IPL feature/training rows and, if required, raw IPL JSON backfill.
- **Non-standard matches**: Reduced-over, abandoned, or structurally incomplete IPL matches must be excluded or tagged so they do not distort regime discovery.
- **Leakage through near-duplicate states**: Query rows must not retrieve themselves, later duplicates from the same labelled event, or future rows that leak the answer.
- **Missing reconstruction fields**: If a feature row cannot be mapped back to enough match context for retrieval or window creation, the row must be excluded and counted in data quality output.
- **Terminal and near-terminal states**: Finished chases, already-decided innings, or zero-ball remaining states must not dominate regime formation or analogue results.
- **Unstable regimes**: If a proposed regime appears only in tiny samples or changes meaning across splits, it must be marked unreliable rather than promoted as a valid semantic state.
- **Scoreboard-only neighbours**: If retrieval collapses to trivial score/wicket twins without useful context, the report must flag that the embedding is not adding enough information.

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST build an IPL-only offline corpus for match states and short state windows using existing repository data sources.
- **FR-002**: The corpus MUST preserve stable source keys and metadata sufficient to trace each record back to its originating match context.
- **FR-003**: The initial corpus MUST use historical IPL feature/training rows as the default retrieval source and MAY use raw IPL JSON only to backfill missing context or window history.
- **FR-004**: The pilot MUST remain ML-first and MUST NOT position LLMs, chat agents, or narrative generation as the core decision layer.
- **FR-005**: The pilot MUST support offline regime discovery using existing local repository dependencies and simple PCA, KMeans, and nearest-neighbour style patterns before any new infrastructure is considered.
- **FR-006**: The pilot MUST output measurable regime or semantic signals covering at least collapse risk, pressure state, tactical instability, acceleration potential, volatility regime, and similar historical states.
- **FR-007**: The system MUST provide offline evaluation outputs for regime quality, including coverage, stability, and outcome separation.
- **FR-008**: The system MUST provide historical analogue retrieval for held-out IPL states, including ranked neighbours, source context, and downstream outcome summaries.
- **FR-009**: Retrieval evaluation MUST exclude self-matches and obvious future leakage from the same event, match, or duplicated source state.
- **FR-010**: The pilot MUST generate regime-aware features or summaries that can be joined back to existing IPL probability and MC evaluation workflows.
- **FR-011**: The pilot MUST compare every regime-aware experiment variant against the current IPL production-aligned baseline or current IPL feature-model setup using the same evaluation split and holdout protocol.
- **FR-012**: Every offline experiment report MUST include baseline and candidate values, plus delta versus baseline, for at least Brier score, log loss, and ECE.
- **FR-013**: The pilot MUST provide segmented comparison versus baseline by key innings and match phase slices where data volume allows, so calibration or probability regressions are not hidden by aggregate results.
- **FR-014**: The pilot MUST produce a decision-ready report that explicitly states whether regime-aware embeddings beat the current IPL baseline on Brier score and log loss, only improve interpretability, or do not justify continuation.
- **FR-015**: If a regime-aware variant does not beat the current IPL baseline on both Brier score and log loss, the report MUST recommend no production change.
- **FR-016**: The pilot MUST run as an offline experiment first and MUST NOT require live serving, live dashboard integration, or operator workflow changes for V1.
- **FR-017**: The pilot MUST avoid introducing heavyweight new infrastructure solely for V1, including vector databases or large orchestration layers.
- **FR-018**: Any recommendation for wider rollout MUST be gated on evidence from the IPL-only pilot rather than assumed portability to other leagues.

### Non-Functional Requirements

- **NFR-001**: The pilot must be reproducible from the same IPL inputs, split policy, and random seed settings.
- **NFR-002**: Pilot-mode iteration should complete within a practical local experimentation window on a sampled IPL corpus.
- **NFR-003**: Full-corpus runs must support resumable or restart-safe artefact generation where long-running offline steps are involved.
- **NFR-004**: All evaluation artefacts must clearly separate data quality issues, retrieval quality, regime quality, and probability-impact results.

---

## Key Entities

- **EmbeddingRecord**: One IPL state or state window with source identifiers, context fields, embedding values, and outcome metadata.
- **RetrievalCorpus**: The reusable IPL reference collection used for regime discovery and analogue lookup.
- **RegimeAssignment**: The regime label or regime score attached to an embedding record, along with confidence or reliability metadata.
- **HistoricalAnalogueSet**: The ranked set of similar historical IPL states returned for a query state, including similarity order and downstream outcomes.
- **RegimeAwareVariant**: A baseline-comparison experiment variant that adds or conditions on embedding-derived regime signals.
- **PilotEvaluationReport**: The final experiment summary describing corpus quality, regime quality, retrieval quality, calibration impact, and go/no-go recommendation.

---

## Success Criteria

- **SC-001**: The pilot creates a reusable IPL embedding corpus covering at least 95% of eligible sampled IPL experiment rows, with excluded rows counted and explained.
- **SC-002**: Regime discovery produces evaluation output for coverage, stability, and outcome separation across at least one holdout or time-split protocol.
- **SC-003**: Historical analogue retrieval returns valid ranked analogues for at least 95% of held-out evaluation queries.
- **SC-004**: Every evaluation report includes baseline and candidate values plus delta versus baseline for Brier score, log loss, and ECE.
- **SC-005**: A regime-aware variant is considered promising only if it beats the current IPL baseline on both Brier score and log loss on the chosen IPL evaluation protocol.
- **SC-006**: A regime-aware variant cannot be considered promising if it materially worsens calibration in key innings or match phase segments, even when aggregate metrics improve.
- **SC-007**: The final report provides a clear go/no-go decision for promotion or wider rollout based on baseline-versus-regime-aware comparisons rather than leaving the result ambiguous.
- **SC-008**: If no variant beats the baseline on both Brier score and log loss while preserving acceptable calibration, the pilot still succeeds only by recommending no production change and documenting why rollout should be deferred.

---

## Assumptions

- V1 is limited to IPL and does not need to generalize to other leagues before feasibility is proven.
- Historical IPL feature rows are the primary source of truth for the first corpus build.
- Raw IPL JSON backfill is acceptable only where feature rows alone do not provide enough context for reconstruction or window creation.
- The first feasible version should stay within current repo patterns and existing local dependencies, favoring simple offline methods over new specialised infrastructure.
- The pilot is intended to test retrieval and regime usefulness offline before any live serving decision.

## Dependencies

- Existing IPL feature datasets under `data/ipl_features_*` and `data/ipl_feature_store_*`, especially the current IPL training baseline around `data/ipl_features_v6`.
- Existing IPL model baselines under `models/ipl_*`, especially `models/ipl_v6` or the current active IPL comparison target.
- MC engine modules under `src/bbl_pipeline/simulation/`.
- Match state logging under `src/bbl_pipeline/inference/match_state_logger.py`.
- Historical state analysis under `src/bbl_pipeline/analysis/state_analyzer.py`.
- MC calibration tooling under `src/bbl_pipeline/calibration/mc_trainer.py`.
- Existing feature-impact experiment pattern in `scripts/analyze_mc_cal_as_feature.py`.

## Out of Scope

- Replacing calibrated ML probabilities with LLMs, chatbots, or narrative-first systems.
- Building a live production embedding service in V1.
- Adding giant agent infrastructure for orchestration or commentary generation.
- Introducing UMAP, HDBSCAN, FAISS, Qdrant, or other new vector-database or approximate-nearest-neighbour infrastructure before the offline pilot proves value.
- Multi-league rollout before IPL feasibility is demonstrated.
- Production promotion of any regime-aware model change without a successful offline IPL pilot.
