# Implementation Plan: Pre-Match Match Brief

**Spec**: `specs/020-pre-match-match-brief/spec.md`  
**Branch**: `020-pre-match-match-brief`  
**Date**: 2026-06-07  

---

## Summary

Build the first dedicated pre-match intelligence surface for CrickenZen. This phase adds a before-the-toss product layer to the dashboard using existing fixture discovery, venue priors, and structured pre-match heuristics so users can understand the model view before live ball-by-ball prediction begins.

The key product shift is:

```text
Live-only public cards -> Upcoming match intelligence -> Real pre-match product surface
```

This phase should stay focused on pre-match clarity and structured context. It is not a chat product, and it is not a fantasy-ranking phase.

---

## Technical Context

### Existing Public Surface

- `dashboard/app/public.py`
  - Current safe public serializer and fixture discovery patterns
  - Already distinguishes live rows from scheduler-based upcoming candidates
- `dashboard/app/routers/pages.py`
  - Current public routes for `/`, `/ipl-prediction-today`, and `/match/{slug}`
- `dashboard/templates/public.html`
- `dashboard/templates/ipl_today.html`
- `dashboard/templates/match_public.html`

### Existing Data and Priors

- `src/bbl_pipeline/features/store.py`
  - Venue prior values such as `venue_avg_score` and `venue_bat_first_win_rate`
- public scheduler candidate flow already surfaces upcoming fixtures before live state exists
- proof work already established honest ready/partial/not-ready UI patterns that can be reused here

### Important Product Constraint

This phase must clearly distinguish:

1. **Pre-match intelligence**
   - before toss
   - venue/conditions/toss context
   - projected first innings

2. **Live prediction**
   - current match state
   - scoreboard-driven win probability
   - live projections and swings

3. **Post-match proof**
   - calibration
   - Brier / ECE / accuracy

The user should never confuse a pre-match brief with a live match page or a proof page.

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Scalability & Reusability | PASS | The phase will introduce a separate pre-match serializer/service boundary instead of hardcoding one-off template logic. |
| II. Pipeline-Driven Architecture & Rapid Retraining | PASS | The brief will consume existing fixture discovery and model/venue outputs rather than creating a parallel product-only data pipeline. |
| III. Reproducibility & Versioning | PASS | Each section should have explicit source/fallback behavior, especially when dew or rain is unavailable. |
| IV. Data Integrity & Entity Consistency | PASS | Venue priors, toss sensitivity, and probability fields will be explicit and separated from live-state values. |
| V. Model Calibration & Observability | PASS | The phase adds clarity to pre-match interpretation without changing or hiding proof semantics. |

**Verdict**: PASS.

---

## Architecture

### Recommended New or Updated Modules

| File | Purpose |
|------|---------|
| `dashboard/app/prematch.py` | Safe pre-match serializer/service boundary for upcoming-fixture summaries and full brief detail |
| `dashboard/app/prematch_page.py` | Server-rendered page-context builder for the full pre-match brief |
| `dashboard/app/routers/public.py` | Optional public pre-match JSON endpoints if needed for future enhancements |
| `dashboard/app/routers/pages.py` | Add pre-match list/detail routes |
| `dashboard/templates/ipl_match_brief_today.html` | List/discovery page for upcoming pre-match briefs |
| `dashboard/templates/prematch_brief.html` | Full pre-match brief template |
| `dashboard/tests/test_prematch.py` | Serializer/service and route tests |
| `dashboard/tests/test_prematch_page.py` | Context and template rendering tests |

### Why Separate `prematch.py` from `public.py`

`dashboard/app/public.py` is optimized for live public cards and match detail. Pre-match intelligence has different needs:

- different safe fields
- no ball-state dependence
- structured factors like toss sensitivity and conditions readiness
- different reason-generation logic

Keeping pre-match logic in a dedicated module avoids polluting live serializers with preview-only assumptions.

---

## Product Shape

### Recommended V1 Routes

- `/ipl-match-brief-today`
- `/pre-match/{slug}`

Optional JSON support:

- `/api/public/pre-match`
- `/api/public/pre-match/{slug}`

This matches the existing public route pattern:

- list/discovery page
- detail page
- optional public API boundary underneath

### Recommended V1 Page Sections

1. **Hero / fixture frame**
   - teams
   - venue
   - start time
   - status badge: upcoming / toss pending / live soon

2. **Headline pre-match cards**
   - win probability
   - projected first innings
   - toss sensitivity
   - venue scoring profile

3. **How to read this match**
   - concise description of what the pre-match brief means
   - difference between pre-match and live pages

4. **Conditions context**
   - dew risk
   - rain risk
   - ready / partial / not_ready support

5. **Pressure zones**
   - below-par band
   - par band
   - above-par pressure band

6. **Why the model leans this way**
   - 3 to 5 short reasons

7. **Next-step CTA**
   - return to today page
   - follow live page once match starts
   - proof page for trust context

---

## Data Boundary

### Recommended Prematch Summary Fields

- `slug`
- `title`
- `league`
- `start_time`
- `venue`
- `status`
- `win_probability_pct`
- `projected_first_innings`
- `toss_sensitivity_label`
- `insight`
- `detail_url`

### Recommended Prematch Detail Fields

- all summary fields
- `venue_avg_score`
- `venue_bat_first_win_rate`
- `conditions`
  - dew
  - rain
- `pressure_zones`
- `reasons`
- `source_status`

### Primary Source Candidates

- upcoming fixtures from existing scheduler candidate flow
- any pre-match model probability source already available in the repo/runtime
- venue priors from `src/bbl_pipeline/features/store.py`
- optional manually-derived or computed toss/pressure heuristics

### Honest V1 Fallback Rule

If any factor cannot be computed reliably, the brief should surface:

- `status = not_ready`
- short explanatory copy

Do not substitute guessed weather/dew numbers just to fill space.

---

## Heuristic and Context Design

### Win Probability

Preferred source order:

1. explicit pre-match model probability if available
2. supported preview probability source in upcoming fixture context
3. otherwise `not_ready`

### Projected First Innings

Preferred source order:

1. precomputed preview projection if available
2. venue-average-based band or heuristic projection
3. otherwise `not_ready`

### Venue Bias

V1 should use:

- `venue_avg_score`
- `venue_bat_first_win_rate`

Convert those into plain-English labels such as:

- batting-first friendly
- balanced venue
- chase-friendly venue

### Toss Sensitivity

V1 can begin with structured heuristic bands:

- low leverage
- medium leverage
- high leverage

Possible inputs:

- venue bat-first win tendency
- projected scoring environment
- how narrow or wide the pre-match edge is

### Conditions Context

V1 support is primarily a status framework:

- `ready`
- `partial`
- `not_ready`

This lets the product show dew/rain sections immediately without inventing unsupported precision.

### Pressure Zones

Recommended V1 representation:

- `below_par`
- `par_band`
- `above_par`

These can be derived from venue priors and projected scoring context using simple, documented bands rather than hidden model magic.

### Reasons

The first version should be deterministic, not LLM-generated. Example reason families:

- venue scoring profile
- toss leverage
- projected par band
- narrow vs clear model edge
- missing-context caveat if relevant

---

## Implementation Sequence

### Step 1 - Lock the Pre-Match Data Contract

Define:

1. summary fields
2. detail fields
3. conditions status structure
4. pressure-zone structure
5. reason-block structure

This contract should live in `dashboard/app/prematch.py` and `dashboard/app/prematch_page.py`, not be spread across templates.

### Step 2 - Build Safe Pre-Match Serialization

Implement:

1. upcoming-fixture list service
2. detail resolver by slug
3. venue-prior mapping helpers
4. toss-sensitivity helpers
5. pressure-zone helpers
6. reason-stack helpers

### Step 3 - Add Pre-Match Page Context Builder

Create a page service that:

1. reads pre-match detail
2. derives ready / partial / not_ready sections
3. formats factor cards
4. formats condition badges and reason blocks
5. builds template-safe context

### Step 4 - Add Routes

Update `dashboard/app/routers/pages.py` with:

1. a list/discovery route for today’s upcoming briefs
2. a detail route for one pre-match brief
3. SEO metadata for both

Optional public API routes can follow once the service shape is stable.

### Step 5 - Build Templates

Create:

1. a discovery/list page for upcoming briefs
2. a dedicated pre-match brief detail page
3. clear empty states and CTA pathways into live or proof pages

### Step 6 - Add Entry Points from Existing Public Pages

Update:

- homepage if appropriate
- `ipl_today.html`
- match/live-adjacent pages only where upcoming context is clear

The goal is discoverability without confusing live and upcoming products.

### Step 7 - Add Tests and Validation

Cover:

1. ready brief rendering
2. partial conditions rendering
3. no-upcoming-fixture rendering
4. route availability without auth
5. CTA presence from public pages

---

## Testing Strategy

### Serializer and Context Tests

Add tests for:

- venue-bias helper output
- toss-sensitivity band logic
- pressure-zone band generation
- reason-block generation
- no-probability / no-venue fallback behavior

### Route and Template Tests

Add tests that:

- render the list page
- render the detail page
- show not-ready dew/rain sections honestly
- preserve clear distinction between upcoming and live messaging

### Suggested Validation Commands

```bash
pytest dashboard/tests/test_prematch.py -v
pytest dashboard/tests/test_prematch_page.py -v
```

Optional broader regression:

```bash
cd dashboard
.venv\Scripts\python.exe -m pytest tests/ -q
```

---

## Risks and Mitigations

### Risk 1 - The Product Promises Conditions Insight Without Real Data

Mitigation:

- build explicit `not_ready` section handling
- document source behavior per factor

### Risk 2 - Pre-Match and Live Pages Blur Together

Mitigation:

- use route naming, page headings, and status labels that clearly say upcoming / before toss
- keep live cards and brief cards visually distinct

### Risk 3 - Reason Stack Becomes Generic Copy

Mitigation:

- generate reasons from structured heuristics
- require each reason to tie back to a specific factor

### Risk 4 - Too Much Scope Gets Pulled Into Weather or Market Ingestion

Mitigation:

- keep V1 focused on current fixture discovery plus venue/model heuristics
- treat richer external-context feeds as later enhancements

---

## Out of Scope for This Phase

- Ask CrickenZen
- fantasy or player rankings
- full market-vs-model comparison layer
- new external weather ingestion infrastructure
- redesigning live dashboards

---

## Handoff to Next Phase

When this phase is complete, the next dashboard phase should be able to assume:

- there is a dedicated before-the-toss product surface
- pre-match semantics are clear and reusable
- public users can distinguish live prediction, pre-match intelligence, and proof

That sets up later recommendation and agent phases on top of a much stronger product spine.
