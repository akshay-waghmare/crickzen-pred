# Feature Specification: Dashboard Proof Page

**Feature Branch**: `018-dashboard-proof-page`  
**Created**: 2026-06-07  
**Status**: Draft  
**Input**: Build the first public trust page for CrickenZen using the implemented proof-metrics foundation so users can inspect Brier, ECE, accuracy, segment performance, and recent proof ledger rows in one place.

## Definitions

- **Proof page**: A public or subscriber-visible dashboard page dedicated to trust, historical performance, and metric transparency rather than live match state.
- **Summary card**: A compact UI block that shows one headline metric, its plain-English meaning, and supporting context such as sample count or window.
- **Proof ledger**: A table of comparable prediction calls or proof events linked to actual outcomes.
- **Segment panel**: A UI section that groups proof metrics by innings, phase, or other supported context using the canonical metrics snapshot.
- **Freshness badge**: A visible label that tells the user whether the proof snapshot is current, stale, or not ready.
- **Methodology copy**: Plain-English text that explains what Brier, ECE, and accuracy mean, what data they come from, and what they do not mean.
- **Not-ready state**: An honest UI state shown when proof artifacts or a specific metric family are unavailable.

## Current State

### What Already Exists

- The canonical proof-data foundation is now implemented in `src/bbl_pipeline/analysis/proof_metrics.py`.
- Snapshot build automation exists in `scripts/build_dashboard_metrics_snapshot.py`.
- Dashboard-side loaders exist in `dashboard/app/proof_metrics.py`.
- Stable proof API routes already exist in `dashboard/app/routers/proof.py`:
  - `/api/proof/summary`
  - `/api/proof/segments`
  - `/api/proof/ledger`
  - `/api/proof/manifest`
- Public dashboard pages already exist in `dashboard/app/routers/pages.py` with templates such as `public.html`, `ipl_today.html`, and `match_public.html`.
- The dashboard tracker in `docs/DASHBOARD_EXECUTION_TRACKER.md` marks the proof page as the immediate product priority after the metrics foundation.

### What Is Missing

- No proof page route exists yet.
- No proof page template exists yet.
- The public dashboard does not yet expose Brier, ECE, or accuracy visually.
- Users cannot inspect proof ledger rows or segment metrics from the current UI.
- Plain-English methodology and freshness language are not yet surfaced in the product.
- Current public pages do not link into a dedicated trust surface.

---

## User Scenarios & Testing

### User Story 1 - Public Proof Overview (Priority: P1)

As a new user, I want a public proof page that explains model trust in less than a minute, so that I can quickly decide whether CrickenZen is worth following.

**Why this priority**: Trust is the biggest current product gap, and the proof page is the highest-priority dashboard surface after the metrics foundation.

**Independent Test**: Open `/proof` while logged out and verify the page renders without auth, shows summary cards for Brier, ECE, accuracy, sample count, evaluation window, and freshness, and does not display fabricated zeros when data is unavailable.

**Acceptance Scenarios**:

1. **Given** a proof snapshot exists for the default league, **When** a logged-out user opens `/proof`, **Then** the page renders public summary cards sourced from the canonical proof snapshot.
2. **Given** the proof snapshot is stale, **When** `/proof` renders, **Then** the page visibly labels the snapshot as stale instead of silently presenting it as fresh.
3. **Given** probability metrics are ready but accuracy is not ready, **When** the page renders, **Then** the Brier and ECE cards remain visible while the accuracy area shows an honest not-ready state.
4. **Given** no proof snapshot exists, **When** `/proof` renders, **Then** the page shows a useful not-ready explanation and a stable page layout rather than a blank screen or server error.

---

### User Story 2 - Segment Drilldowns and Proof Ledger (Priority: P1)

As a returning user, I want to inspect where the model performs well or poorly and review recent proof entries, so that I can judge the model beyond one headline number.

**Why this priority**: Summary metrics alone are not enough. Users need context by innings, phase, and recent calls to trust the product honestly.

**Independent Test**: Open `/proof`, verify segment panels render innings and phase metrics from the proof API, and confirm the recent proof ledger shows deterministic rows with prediction side, confidence/probability, timestamp, and outcome.

**Acceptance Scenarios**:

1. **Given** segment metrics exist, **When** the proof page renders, **Then** innings and phase panels show grouped proof metrics with sample counts and labels.
2. **Given** proof-ledger rows exist, **When** the proof page renders, **Then** it shows a recent ledger table with deterministic ordering and user-readable columns.
3. **Given** the ledger is empty for a league or window, **When** the proof page renders, **Then** it shows an empty-state explanation instead of an empty broken table.
4. **Given** some segments have very small samples, **When** the proof page renders, **Then** the UI surfaces the sample size clearly and does not overstate the result.

---

### User Story 3 - Plain-English Methodology and Caveats (Priority: P1)

As a skeptical user, I want plain-English explanations of Brier, ECE, accuracy, and proof limitations, so that I understand what the numbers mean and what they do not promise.

**Why this priority**: Metrics without interpretation can create false confidence or confusion. This page must teach trust, not just display numbers.

**Independent Test**: Open `/proof` and verify the page includes concise metric definitions, an explanation of the evaluation window, and explicit caveats that separate probability quality from discrete call accuracy.

**Acceptance Scenarios**:

1. **Given** summary metrics are available, **When** the proof page renders, **Then** Brier, ECE, and accuracy each include concise plain-English explanations.
2. **Given** the snapshot includes an evaluation window and freshness metadata, **When** the page renders, **Then** that context is visible near the headline proof numbers.
3. **Given** the proof page describes accuracy, **When** the user reads the page, **Then** it clearly states that accuracy is not the same thing as probability calibration.
4. **Given** the proof data is based on completed matches and proof-ledger rows, **When** methodology copy is shown, **Then** it states the scope honestly and avoids guaranteed-performance language.

---

### User Story 4 - Trust Entry Points from Existing Public Surfaces (Priority: P2)

As a public visitor browsing the current site, I want clear links into the proof page, so that trust is easy to discover from the homepage and match pages.

**Why this priority**: The proof page will not fix product trust if users have to guess that it exists.

**Independent Test**: Open `/`, `/ipl-prediction-today`, and a public match page while logged out and verify that each surface includes a visible CTA to `/proof`.

**Acceptance Scenarios**:

1. **Given** the homepage renders, **When** the visitor scans the hero or navigation, **Then** a clear proof CTA is visible.
2. **Given** a public match page renders, **When** the visitor views model detail, **Then** there is a clear link to the proof page for trust follow-up.
3. **Given** the proof page exists, **When** public surfaces link to it, **Then** the link copy frames it as model proof or performance, not vague marketing language.

---

## Edge Cases

- **No proof artifacts**: Render a stable not-ready page with explanation and next-step CTA instead of a broken page.
- **Stale snapshot**: Show stale labeling and preserve the timestamp.
- **Accuracy unavailable**: Keep probability metrics visible and label accuracy as not ready.
- **Empty ledger**: Replace the ledger table with explanatory empty-state copy.
- **Low sample segments**: Surface sample counts clearly and avoid overstated labels.
- **Malformed segment payloads**: Fail gracefully to empty panels rather than crashing the full page.
- **Long team names or labels**: Layout must remain readable on mobile and desktop.
- **Multiple leagues later**: The route and page context must not hardcode IPL-only naming in generic proof components even if IPL is the default league.

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST expose a proof page route at `/proof` that renders without authentication.
- **FR-002**: The proof page MUST use the canonical proof snapshot and proof API/loader paths from Spec 017 rather than recomputing metrics inside templates.
- **FR-003**: The proof page MUST display headline summary cards for Brier, ECE, accuracy, sample count, evaluation window, and last-updated or freshness status.
- **FR-004**: The proof page MUST surface stale and not-ready states honestly and visibly.
- **FR-005**: The proof page MUST render segment views for innings and phase when segment data is available.
- **FR-006**: The proof page MUST render recent proof-ledger rows with user-readable prediction and outcome context.
- **FR-007**: The proof page MUST include concise methodology copy explaining Brier, ECE, accuracy, and the evaluation window in plain English.
- **FR-008**: The proof page MUST clearly distinguish probability-quality metrics from discrete call accuracy.
- **FR-009**: The proof page MUST preserve a useful mobile layout and a readable desktop layout using the existing dashboard visual language.
- **FR-010**: Existing public surfaces MUST gain at least one clear CTA into the proof page.
- **FR-011**: The page MUST degrade gracefully when only some proof sections are ready.
- **FR-012**: The implementation MUST include dashboard tests for the page route, proof rendering states, and proof CTA presence on linked public pages.
- **FR-013**: The implementation MUST document the validation path for refreshing proof artifacts and checking the rendered page locally.

### Non-Functional Requirements

- **NFR-001**: The proof page should load from existing snapshot artifacts and loader contracts without adding a new database dependency.
- **NFR-002**: The first version should prefer server-rendered content for trust-critical summary information rather than relying fully on client-side JavaScript.
- **NFR-003**: The page must remain honest under partial or stale data conditions.
- **NFR-004**: The implementation should preserve the current dashboard template and navigation patterns unless a specific proof need requires adjustment.

### Key Entities

- **ProofPageContext**: The server-rendered context object containing summary metrics, segment rows, ledger rows, freshness state, and explanatory copy for the proof template.
- **SummaryMetricCard**: One headline metric card showing a metric value, label, definition, and supporting context.
- **ProofLedgerDisplayRow**: One display-ready ledger row rendered in the proof table.
- **SegmentDisplayGroup**: A group of segment rows organized for the template, such as innings or phase.
- **ProofStatusBanner**: A status object representing ready, stale, partial, or not-ready proof states for page messaging.

---

## Success Criteria

- **SC-001**: A logged-out user can open `/proof` and see a trust-oriented page sourced from the canonical proof artifacts.
- **SC-002**: The page communicates Brier, ECE, accuracy, sample size, and freshness in less than 60 seconds of reading.
- **SC-003**: The proof page never fabricates zeros for missing metrics and instead shows explicit ready, stale, or not-ready states.
- **SC-004**: Segment panels and proof ledger rows render correctly from the existing proof API/loader contracts.
- **SC-005**: Homepage and public match surfaces include clear proof CTAs.
- **SC-006**: Local dashboard tests cover route rendering, stale/not-ready handling, and proof CTA presence.
- **SC-007**: The phase leaves the repo ready for the next dashboard phase without needing to redesign proof semantics again.

---

## Assumptions

- IPL can remain the default proof league in V1, but the page should avoid unnecessary IPL-only hardcoding in reusable proof helpers.
- The current proof summary already contains the accuracy section the page needs; a separate accuracy endpoint is not required for V1.
- A table-based or card-based ledger is sufficient for V1; interactive charting is optional and not required.
- The proof page should prioritize trust and clarity over dense analytics or premium-only detail.

## Dependencies

- `specs/017-dashboard-metrics-foundation/spec.md`
- `dashboard/app/proof_metrics.py`
- `dashboard/app/routers/proof.py`
- `dashboard/app/routers/pages.py`
- `dashboard/templates/base.html`
- `dashboard/templates/public.html`
- `dashboard/templates/match_public.html`
- `docs/DASHBOARD_EXECUTION_TRACKER.md`

## Out of Scope

- Ask CrickenZen chat or natural-language answering
- Pre-match match brief UI
- Ranked player or matchup recommendation surfaces
- Recomputing dashboard metrics in the browser
- Building a new charting stack solely for this phase
