# Feature Specification: Dashboard Metrics Foundation

**Feature Branch**: `017-dashboard-metrics-foundation`  
**Created**: 2026-06-07  
**Status**: Draft  
**Input**: Build the canonical metrics and proof-data foundation that the CrickenZen proof page, proof API, and future `Ask CrickenZen` experiences will depend on.

## Definitions

- **Probability quality metrics**: Metrics that score how good model probabilities are against actual outcomes. For this phase, the required metrics are Brier score and ECE, with log loss allowed as supporting context.
- **Match-call accuracy**: A separate metric family describing whether a comparable prediction call, such as a pre-match favorite, was right or wrong once the match finished.
- **Evaluation window**: The time or data slice over which metrics are computed, such as `last_7_days`, `last_30_days`, `season_to_date`, or `all_available`.
- **Metrics snapshot**: A versioned, dashboard-readable summary artifact containing overall metrics, segment metrics, sample counts, freshness metadata, and source metadata.
- **Proof ledger row**: One user-reviewable row that links a prediction call or model snapshot to the eventual outcome and enough context to explain what happened.
- **Segment view**: A grouped metric slice such as by league, innings, phase, or other match context.
- **Canonical metric source**: The single approved data source and computation path used for dashboard-visible proof metrics, so product surfaces do not invent conflicting numbers.
- **Freshness metadata**: Timestamps and source-window metadata that tell users and operators how current a metric snapshot is.

## Current State

### What Already Exists

- Match-state recording and storage already exist under `data/match_states/<league>/` with schema support in `src/bbl_pipeline/inference/match_state_schema.py`.
- `src/bbl_pipeline/analysis/state_analyzer.py` already consolidates finished match states and computes Brier, ECE, and log loss overall plus by innings and phase.
- Training and calibration modules already compute Brier and ECE in multiple places, including `src/bbl_pipeline/training/evaluation.py`, `src/bbl_pipeline/training/oof_analyzer.py`, and `src/bbl_pipeline/cli.py`.
- Telegram signal utilities already include `build_accuracy_tracker_row()` in `src/bbl_pipeline/telegram/signals.py`, which is a useful starting point for match-call proof rows.
- The dashboard already has public and authenticated surfaces, but they currently focus on live prediction state rather than durable proof.
- A durable dashboard roadmap now exists in `docs/DASHBOARD_EXECUTION_TRACKER.md` and marks the proof page as the top product priority after metrics foundation.

### What Is Missing

- No canonical dashboard-facing metrics snapshot exists.
- No single backend contract exists for proof metrics, segment metrics, and ledger rows.
- Accuracy is not yet defined cleanly for the dashboard alongside Brier and ECE.
- No durable proof ledger exists that consistently links prediction calls to final outcomes.
- No explicit freshness or evaluation-window metadata exists for dashboard proof surfaces.
- No guardrail currently prevents future pages from mixing probability-quality metrics and match-call accuracy into one misleading number.

---

## User Scenarios & Testing

### User Story 1 - Canonical Probability Metrics Snapshots (Priority: P1)

As a dashboard operator, I want one canonical metrics snapshot for each supported league and evaluation window, so that the proof page and future dashboard surfaces always read the same Brier and ECE values from the same source.

**Why this priority**: The proof page is the highest product priority, and it cannot be trustworthy if metrics are recomputed ad hoc in several places.

**Independent Test**: Run the metrics snapshot build workflow for IPL and verify that a versioned snapshot is produced with overall Brier, ECE, sample count, freshness metadata, and segment metrics by innings and phase.

**Acceptance Scenarios**:

1. **Given** completed match-state files exist for a league, **When** the metrics build runs, **Then** it produces a canonical snapshot with overall Brier and ECE plus sample count and evaluation-window metadata.
2. **Given** enough completed data exists, **When** the snapshot is built, **Then** segment metrics are produced at least for innings and phase.
3. **Given** there are multiple possible metric implementations in the repo, **When** the dashboard snapshot is computed, **Then** it uses one documented canonical computation path rather than mixing outputs from different modules.
4. **Given** a requested evaluation window has no eligible completed data, **When** the snapshot is built, **Then** it returns a not-ready status with zero eligible sample count and does not fabricate metric values.

---

### User Story 2 - Proof Ledger and Accuracy Summary (Priority: P1)

As a user reviewing model trust, I want a ledger of comparable prediction calls and a separate accuracy summary, so that I can see both how the probabilities behave and whether the visible calls are right over time.

**Why this priority**: Users ask for proof in human terms, not just calibration charts. The dashboard needs a concrete record of predictions and outcomes.

**Independent Test**: Build proof-ledger rows from available prediction-call records and final outcomes, then verify the accuracy summary reports wins, losses, hit rate, sample count, and exclusion counts without mixing those values into Brier or ECE.

**Acceptance Scenarios**:

1. **Given** a comparable pre-match or explicitly tracked prediction call exists and the final winner is known, **When** the ledger builder runs, **Then** it creates a proof row linking prediction side, probability/confidence, final result, and review context.
2. **Given** some rows are missing winner, predicted side, or timestamp, **When** the accuracy summary is computed, **Then** those rows are excluded and counted with explicit exclusion reasons.
3. **Given** probability metrics and call accuracy are both available, **When** summary data is returned for the dashboard, **Then** the two metric families remain clearly separated.
4. **Given** no comparable call rows exist yet for a window or league, **When** the accuracy summary is built, **Then** it reports not-ready or insufficient-data status rather than misleading `0%` accuracy.

---

### User Story 3 - Stable Backend Contract for Dashboard Proof Surfaces (Priority: P1)

As a dashboard engineer, I want a stable backend contract for summary metrics, segment metrics, and ledger rows, so that the proof page and later `Ask CrickenZen` workflows can ship without rewriting metric logic.

**Why this priority**: The next phase is the proof page. If the contract is unstable, every UI layer will become brittle.

**Independent Test**: Query the metrics summary, metrics segments, and ledger endpoints or loaders and verify that they return versioned, dashboard-safe payloads with timestamps, windows, and readiness state.

**Acceptance Scenarios**:

1. **Given** snapshot data exists, **When** the summary contract is requested, **Then** it returns overall probability metrics, overall accuracy metrics, evaluation window, last updated timestamp, and source metadata.
2. **Given** segment data exists, **When** the segment contract is requested, **Then** it returns league, innings, and phase slices in a stable typed structure.
3. **Given** no snapshot has been generated yet, **When** the contract is requested, **Then** it returns a structured not-ready response instead of a server error or placeholder metric values.
4. **Given** proof-ledger rows exist, **When** the ledger contract is requested, **Then** it returns dashboard-safe rows sorted in a deterministic and documented order.

---

### User Story 4 - Honest Metric Definitions and Freshness Metadata (Priority: P2)

As a product user, I want plain-English metric definitions and freshness metadata, so that I understand what the proof numbers mean and how current they are.

**Why this priority**: The proof page will fail if users see numbers without context or assume stale metrics are current.

**Independent Test**: Inspect the generated metric metadata and verify it includes metric definitions, evaluation windows, last-updated timestamps, and source descriptions that the next proof page can display directly.

**Acceptance Scenarios**:

1. **Given** a metrics snapshot exists, **When** metadata is generated, **Then** it includes plain-English labels for Brier, ECE, and accuracy.
2. **Given** a snapshot was built from a rolling window, **When** metadata is returned, **Then** the window definition is explicit and machine-readable.
3. **Given** a snapshot is stale by the defined threshold, **When** the contract is requested, **Then** the response marks it stale rather than silently presenting it as current.
4. **Given** accuracy and probability metrics are both exposed, **When** metadata is rendered, **Then** it explains that accuracy measures discrete calls while Brier and ECE measure probability quality.

---

## Edge Cases

- **No completed matches**: Metrics snapshot must return not-ready status without fake metric values.
- **Incomplete metadata**: If `winner` or key match identifiers are missing, affected rows must be excluded and counted.
- **Mixed contexts**: Pre-match call accuracy must not be merged into live ball-state Brier or ECE.
- **Duplicate proof rows**: Repeated source records for the same match/prediction phase must dedupe deterministically.
- **League mismatch**: Snapshot builders must not mix rows across leagues when generating league-level proof.
- **Small samples**: Very small windows must be explicitly marked as low-confidence or insufficient-data instead of overconfident proof.
- **Stale artifacts**: Old snapshots must carry freshness metadata so the UI can label them honestly.
- **Different ECE implementations**: The phase must choose and document one canonical ECE computation method for dashboard proof.
- **Partial proof sources**: If probability-quality metrics exist but no comparable accuracy ledger exists yet, the dashboard must expose one as ready and the other as not-ready, not fail both.

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST define one canonical metric computation path for dashboard-visible probability-quality metrics.
- **FR-002**: The system MUST generate a versioned metrics snapshot for at least one supported league and evaluation window.
- **FR-003**: Each metrics snapshot MUST include overall Brier score, overall ECE, sample count, evaluation window, and last-updated timestamp.
- **FR-004**: Each metrics snapshot MUST include segment metrics at least by innings and phase where data volume allows.
- **FR-005**: The system MUST keep probability-quality metrics and match-call accuracy metrics as separate metric families in data contracts and documentation.
- **FR-006**: Probability-quality metrics MUST be sourced from completed match-state data and actual outcomes, not from partial live states.
- **FR-007**: Match-call accuracy MUST be sourced only from explicit comparable calls with a known predicted side and final result.
- **FR-008**: The system MUST produce proof-ledger rows containing enough context to show predicted side, probability or confidence, timestamp, final result, and explanatory notes where available.
- **FR-009**: The system MUST count excluded rows and expose exclusion reasons for both probability metrics and accuracy metrics.
- **FR-010**: The system MUST provide a stable backend contract or loader for summary metrics, segment metrics, and proof-ledger rows.
- **FR-011**: The backend contract MUST support not-ready and stale states without using fabricated metric defaults.
- **FR-012**: The snapshot metadata MUST include plain-English metric labels and source/freshness metadata suitable for direct dashboard display.
- **FR-013**: The system MUST support at least configurable rolling windows and all-available windows for proof reporting.
- **FR-014**: The phase MUST define where dashboard proof artifacts live on disk and how they are refreshed.
- **FR-015**: The implementation MUST document validation steps that reproduce the snapshot and verify metric correctness against canonical source calculations.

### Non-Functional Requirements

- **NFR-001**: Snapshot generation must be reproducible from the same input state files, windows, and metric settings.
- **NFR-002**: The dashboard-facing contract must remain stable across sessions and future UI phases.
- **NFR-003**: Missing-data cases must degrade honestly and deterministically.
- **NFR-004**: The first implementation should reuse existing repo metric code where practical instead of introducing a separate incompatible metric stack.

### Key Entities

- **MetricsSnapshot**: Top-level proof artifact for one league and one evaluation window, containing overall metrics, readiness state, timestamps, and references to segment/ledger data.
- **ProbabilityMetricsSummary**: Overall Brier/ECE summary plus sample count and explanatory metadata.
- **AccuracyMetricsSummary**: Overall hit rate summary for comparable prediction calls plus wins, losses, exclusions, and sample count.
- **SegmentMetricRow**: One grouped metric row for a league, innings, phase, or other supported slice.
- **ProofLedgerRow**: One row linking a prediction call or tracked proof event to the eventual outcome and review context.
- **MetricsBuildManifest**: Build metadata containing version, inputs, windows, timestamps, exclusion counts, and freshness status.

---

## Success Criteria

- **SC-001**: A canonical metrics snapshot can be generated for IPL with overall Brier, ECE, sample count, evaluation window, and freshness metadata.
- **SC-002**: The same snapshot includes innings and phase segment metrics when eligible completed data exists.
- **SC-003**: Accuracy summary output reports wins, losses, hit rate, sample count, and exclusions without being conflated with probability metrics.
- **SC-004**: Summary, segment, and ledger contracts return structured not-ready states instead of fake zeros when data is missing.
- **SC-005**: The canonical dashboard metric path is documented well enough that future proof-page work does not need to rediscover metric semantics.
- **SC-006**: Snapshot validation reproduces at least one league’s Brier and ECE values from the same completed-state inputs using the documented canonical method.
- **SC-007**: The phase leaves the repo ready for the next proof-page spec to consume stable summary, segment, and ledger data without changing metric definitions.

---

## Assumptions

- The proof page phase will consume this foundation rather than recomputing dashboard metrics directly in templates.
- Completed match-state data under `data/match_states/<league>/` is the correct primary source for probability-quality proof.
- Existing telegram signal and storage patterns are sufficient starting points for proof-ledger accuracy rows, even if additional persistence is added later.
- Accuracy is useful product evidence, but Brier and ECE remain the primary trust metrics for the dashboard.
- This phase is foundation-only and does not need to ship the full proof-page UI.

## Dependencies

- `src/bbl_pipeline/analysis/state_analyzer.py`
- `src/bbl_pipeline/training/evaluation.py`
- `src/bbl_pipeline/telegram/signals.py`
- `src/bbl_pipeline/inference/match_state_logger.py`
- `data/match_states/<league>/`
- `docs/DASHBOARD_EXECUTION_TRACKER.md`

## Out of Scope

- Building the proof-page HTML or public page in this phase
- Adding LLM or chat behavior
- Reframing live public pages
- Changing model-training logic solely to make proof easier
- Introducing a new database if file-based snapshots are enough for V1
