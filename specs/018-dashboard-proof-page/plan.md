# Implementation Plan: Dashboard Proof Page

**Spec**: `specs/018-dashboard-proof-page/spec.md`  
**Branch**: `018-dashboard-proof-page`  
**Date**: 2026-06-07  

---

## Summary

Build the first dedicated trust page for the CrickenZen dashboard. This phase turns the completed proof-metrics foundation into a public product surface that explains model quality clearly, shows recent proof evidence, and links trust back into the rest of the dashboard.

The key product shift is:

```text
Implemented proof backend -> Public trust page -> Clear model credibility in the dashboard
```

This phase should stay focused on clarity and proof. It is not the `Ask CrickenZen` phase, and it is not a pre-match research product yet.

---

## Technical Context

### Existing Proof Backend

- `src/bbl_pipeline/analysis/proof_metrics.py`
  - Canonical summary, segment, accuracy, ledger, and manifest builders
- `scripts/build_dashboard_metrics_snapshot.py`
  - Snapshot build entry point
- `dashboard/app/proof_metrics.py`
  - Dashboard-side artifact loaders with stale and not-ready handling
- `dashboard/app/routers/proof.py`
  - Existing proof API routes for summary, segments, ledger, and manifest

### Existing Public Dashboard Surface

- `dashboard/app/routers/pages.py`
  - Current public pages at `/`, `/ipl-prediction-today`, `/match/{slug}`
- `dashboard/templates/base.html`
  - Existing public layout and nav shell
- `dashboard/templates/public.html`
  - Public homepage hero and live-card pitch
- `dashboard/templates/match_public.html`
  - Match-level public detail and dashboard upgrade CTA

### Important Product Constraint

This phase must preserve the separation introduced in Spec 017:

1. **Probability quality**
   - Brier
   - ECE
   - optional supporting log loss if already present in summary

2. **Comparable call accuracy**
   - wins/losses
   - hit rate
   - ledger rows

The UI can place these side by side, but it must not blur them into a single trust score.

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Scalability & Reusability | PASS | The page will consume existing proof loaders and should remain league-aware even if IPL is the default V1 presentation. |
| II. Pipeline-Driven Architecture & Rapid Retraining | PASS | The UI reads generated artifacts rather than inventing an alternate runtime path. |
| III. Reproducibility & Versioning | PASS | The page will display build freshness, evaluation window, and snapshot-derived context rather than hiding it. |
| IV. Data Integrity & Entity Consistency | PASS | Proof semantics remain anchored to Spec 017 contracts and cannot drift inside the template. |
| V. Model Calibration & Observability | PASS | This phase exposes calibration and accuracy to users directly, which strengthens observability rather than diluting it. |

**Verdict**: PASS.

---

## Architecture

### Recommended New or Updated Modules

| File | Purpose |
|------|---------|
| `dashboard/app/proof_page.py` | Build a clean server-rendered proof-page context from summary, segment, ledger, and manifest loaders |
| `dashboard/app/routers/pages.py` | Add `/proof` route and pass proof-page context into the template |
| `dashboard/templates/proof.html` | Dedicated proof page template for summary cards, segment panels, ledger, and methodology |
| `dashboard/templates/public.html` | Add a visible proof CTA from the public homepage |
| `dashboard/templates/match_public.html` | Add a visible proof CTA from match pages |
| `dashboard/tests/test_proof_page.py` | Route and template rendering tests for proof-page states |

### Why Add a Page Service Layer

Avoid pushing loader and formatting logic directly into `pages.py` or Jinja. A small `dashboard/app/proof_page.py` service keeps:

- status normalization in Python
- display labels in one place
- partial-ready logic consistent
- future `Ask CrickenZen` and proof-page reuse cleaner

This also makes stale, empty, and not-ready behavior easier to test than if it were buried in template conditionals.

---

## Product Shape

### Recommended V1 Route

- `/proof`

Optional future extension:

- `?league=ipl`

V1 should default to `ipl`, but the route should not assume IPL in every helper or label.

### Recommended V1 Page Sections

1. **Hero / trust framing**
   - short explanation of what the page proves
   - freshness badge
   - evaluation window badge

2. **Headline proof cards**
   - Brier
   - ECE
   - Accuracy
   - Sample count
   - optional supporting wins/losses line

3. **How to read this**
   - short plain-English explanations
   - explicit note that accuracy and calibration are different

4. **Segment performance**
   - innings rows
   - phase rows
   - sample counts visible

5. **Recent proof ledger**
   - deterministic recent rows
   - prediction side
   - probability/confidence
   - final winner
   - result status
   - timestamp

6. **Caveats and scope**
   - what data is included
   - why stale or partial data can happen
   - no guaranteed outcome language

7. **Trust-to-product CTA**
   - links back to live match pages and the full dashboard

---

## Data Flow

### Preferred Server-Rendered Flow

```text
/proof request
  -> proof_page.build_context(league)
  -> dashboard/app/proof_metrics.py loaders
  -> summary / segments / ledger / manifest artifacts
  -> normalized ProofPageContext
  -> Jinja render dashboard/templates/proof.html
```

This keeps the trust-critical first render available without JavaScript and aligns with the existing dashboard page architecture.

### What the Page Service Should Normalize

- ready vs partial vs not-ready status
- stale flag and human-readable freshness label
- grouped segment rows by `segment_type`
- trimmed recent ledger rows for V1 display
- fallbacks when accuracy or ledger are missing
- concise metric explanations and caveat copy

---

## Route and Rendering Decisions

### Route Behavior

- public access, no auth required
- default league `ipl`
- HTTP `200` for ready, partial, and stale proof states
- HTTP `200` for not-ready proof page as long as the route itself is valid

This page is a product surface, not an API contract. A not-ready trust state should still render a complete page.

### API Reuse

The page may call the loaders directly instead of making internal HTTP requests to `/api/proof/*`.

Reason:

- fewer moving parts
- simpler testing
- avoids same-process HTTP overhead
- preserves one data contract while keeping page rendering simple

The API remains useful for future client-side enhancements and other consumers.

---

## UI Behavior

### Headline Cards

Each card should show:

- metric label
- metric value or not-ready label
- one-line definition
- supporting context when relevant

Examples:

- `Brier`: lower is better
- `ECE`: lower is better
- `Accuracy`: discrete call hit rate
- `Sample`: number of evaluated rows or calls

### Segment Panels

Prefer a compact card or table layout with:

- segment label
- Brier
- ECE
- sample count

Do not bury sample size. Small samples are part of the proof story.

### Ledger Table

Recommended columns:

- match
- predicted side
- predicted confidence or probability
- final winner
- result
- timestamp

Keep V1 compact and scrollable on mobile rather than forcing a dense desktop-first table.

### Status Messaging

Support four states:

- `ready`
- `stale`
- `partial`
- `not_ready`

The page service should derive `partial` when, for example, probability metrics are ready but accuracy or ledger is missing.

---

## Implementation Sequence

### Step 1 - Lock the Proof Page Contract

Confirm the display contract for:

1. summary metrics
2. status banner
3. segment groups
4. ledger rows
5. methodology copy

This contract should live in `dashboard/app/proof_page.py`, not scattered across route and template code.

### Step 2 - Add the Page Context Builder

Implement a small page service that:

1. loads summary, segments, ledger, and manifest
2. derives top-level page status
3. groups segments by type
4. limits or orders ledger rows for V1
5. exposes plain-English definitions and caveats

### Step 3 - Add the `/proof` Route

Update `dashboard/app/routers/pages.py` to:

1. call the proof page service
2. render `proof.html`
3. pass SEO metadata
4. keep the route public

### Step 4 - Build the Proof Template

Create a dedicated `dashboard/templates/proof.html` that:

1. matches the existing dashboard visual language
2. renders ready, partial, stale, and not-ready states
3. surfaces summary cards first
4. then methodology, segments, and ledger
5. ends with clear next-step CTAs

### Step 5 - Add Trust Entry Points

Update public pages to link to `/proof`:

- homepage hero or supporting card
- public match page trust area
- optionally nav if the pattern fits cleanly

### Step 6 - Add Tests and Validation

Cover:

1. ready route rendering
2. stale summary rendering
3. not-ready rendering
4. partial rendering
5. CTA presence from public pages
6. basic proof copy presence

---

## Testing Strategy

### Unit-Like Dashboard Tests

Add page-context and rendering tests for:

- ready proof summary
- stale freshness label
- probability-ready / accuracy-not-ready partial state
- empty ledger rendering
- grouped segments by innings and phase

### Route Tests

Add tests that:

- call `/proof` without auth
- verify HTTP `200`
- verify rendered HTML contains proof summary headings and metric labels
- verify homepage and match pages link to `/proof`

### Suggested Validation Commands

```bash
pytest dashboard/tests/test_proof_page.py -v
pytest dashboard/tests/test_proof_metrics.py -v --noconftest
python scripts/build_dashboard_metrics_snapshot.py --league ipl --window all_available
```

Optional broader dashboard regression:

```bash
cd dashboard
.venv\Scripts\python.exe -m pytest tests/ -q
```

---

## Risks and Mitigations

### Risk 1 - The Page Becomes a Metrics Dump

Mitigation:

- keep the summary and methodology sections first
- use plain-English copy before detailed tables

### Risk 2 - Accuracy Overpowers Calibration

Mitigation:

- keep Brier and ECE visually first
- add explicit copy that accuracy is a different metric family

### Risk 3 - Stale or Partial Data Looks Like Failure

Mitigation:

- add intentional status banners
- keep the layout stable across ready and not-ready states

### Risk 4 - UI Reimplements Proof Semantics

Mitigation:

- centralize all display shaping in `dashboard/app/proof_page.py`
- consume the existing proof loaders instead of ad hoc file parsing

---

## Out of Scope for This Phase

- Ask CrickenZen endpoint or UI
- pre-match intelligence page
- player rankings or fantasy recommendations
- complex interactive charting
- multi-league filtering UX beyond a simple default-ready structure

---

## Handoff to Next Phase

When this phase is complete, the next dashboard phase should be able to assume:

- there is a public trust page at `/proof`
- proof metrics are visible and understandable
- public surfaces link into proof
- methodology and caveats are already in the product

That sets up the next phase to focus on interactive intelligence, not basic credibility.
