# Feature Specification: Pre-Match Match Brief

**Feature Branch**: `020-pre-match-match-brief`  
**Created**: 2026-06-07  
**Status**: Draft  
**Input**: Build a public pre-match intelligence surface for CrickenZen that explains the model view before toss, with win probability, projected first-innings score, venue context, toss sensitivity, conditions context, and 3 to 5 plain-English reasons.

## Definitions

- **Pre-match brief**: A public or subscriber-visible match preview shown before live ball-state prediction begins.
- **Brief summary card**: A compact card that highlights one pre-match factor such as win probability, projected first innings, or toss sensitivity.
- **Venue bias**: A venue-level context factor derived from historical priors, such as average first-innings score or bat-first win rate.
- **Toss sensitivity**: A measure of how much the expected match edge changes depending on toss outcome and first/second-innings conditions.
- **Conditions context**: A structured explanation of available environmental factors such as dew risk or rain risk, including explicit `not_ready` states when source data is unavailable.
- **Pressure zone**: A pre-match scoring band or scenario threshold that helps users interpret what a good, par, or under-par total looks like for that venue and match context.
- **Reason block**: One short, plain-English explanation of why the model leans a certain way before the match starts.
- **Upcoming fixture candidate**: A scheduler- or source-discovered match that has not yet started and may not yet have live ball data.

## Current State

### What Already Exists

- Public acquisition pages already exist:
  - `dashboard/templates/public.html`
  - `dashboard/templates/ipl_today.html`
  - `dashboard/templates/match_public.html`
- Public match safety boundaries already exist in `dashboard/app/public.py`.
- The dashboard can already render live and upcoming fixtures using scheduler candidates and running predictions.
- Proof and trust surfaces now exist through the proof backend and proof page phases.
- The feature store already contains venue priors such as:
  - `venue_avg_score`
  - `venue_avg_wickets`
  - `venue_bat_first_win_rate`
  in `src/bbl_pipeline/features/store.py`.
- Existing product roadmap tracking already calls out pre-match intelligence as one of the biggest current gaps.

### What Is Missing

- No dedicated pre-match page or card exists today.
- No public pre-match serializer or service exists that is distinct from live match payloads.
- Users cannot see a before-the-toss model edge, projected first innings, or venue/toss context in the dashboard.
- Dew/rain and toss sensitivity are not surfaced in a structured dashboard-ready form.
- No pre-match reason stack exists that explains the model view in plain English before the match starts.

---

## User Scenarios & Testing

### User Story 1 - Public Pre-Match Brief Overview (Priority: P1)

As a new user, I want a public pre-match brief before the match starts, so that I can understand the model lean before live ball-by-ball prediction begins.

**Why this priority**: One of the clearest gaps against CricIntel and similar products is before-the-toss packaging. This is the next biggest product unlock after trust.

**Independent Test**: Open the pre-match brief page for an upcoming IPL fixture and verify that it renders without auth, showing a pre-match win probability, projected first-innings score, venue context, and a short reason stack.

**Acceptance Scenarios**:

1. **Given** an upcoming fixture candidate exists, **When** a logged-out user opens the pre-match brief, **Then** the page renders a clear pre-match headline view without requiring live ball data.
2. **Given** the underlying model view is available, **When** the brief renders, **Then** it shows a pre-match win probability and projected first-innings score.
3. **Given** the fixture is known but some supporting context is not available yet, **When** the brief renders, **Then** missing sections are labeled honestly instead of showing fake zeros or invented certainty.
4. **Given** no eligible upcoming fixture exists, **When** the brief route or list page renders, **Then** it shows a useful empty state instead of a broken page.

---

### User Story 2 - Venue, Toss, and Conditions Context (Priority: P1)

As a serious cricket user, I want venue bias, toss sensitivity, and conditions context before the match begins, so that I can understand why the pre-match view exists and how fragile it is.

**Why this priority**: A plain percentage is not enough. The product needs the supporting context that public pre-match products do well.

**Independent Test**: Open a pre-match brief and verify it includes venue priors, toss sensitivity, pressure-zone bands, and conditions context with ready or not-ready states.

**Acceptance Scenarios**:

1. **Given** venue priors are available, **When** the brief renders, **Then** it shows venue average score and bat-first/chasing context in user-readable terms.
2. **Given** toss sensitivity can be derived, **When** the brief renders, **Then** it shows whether toss is low, medium, or high leverage and explains why.
3. **Given** conditions data such as dew or rain is unavailable, **When** the brief renders, **Then** the page marks those sections `not_ready` rather than pretending the risk is neutral.
4. **Given** a venue par band can be estimated, **When** the brief renders, **Then** it shows pressure zones or scoring bands that help interpret first-innings outcomes.

---

### User Story 3 - Plain-English Match Reasons (Priority: P1)

As a user evaluating the product, I want 3 to 5 concise reasons for the pre-match lean, so that I can understand the story behind the number without reading internal model jargon.

**Why this priority**: Competitors package a clear “why.” We need a structured, human-readable explanation layer on top of our real data.

**Independent Test**: Inspect the pre-match brief and verify it includes 3 to 5 plain-English reason blocks sourced from structured facts rather than generic filler.

**Acceptance Scenarios**:

1. **Given** the pre-match brief is ready, **When** it renders, **Then** it includes at least 3 concise reasons explaining the model lean.
2. **Given** some evidence factors are weak or unavailable, **When** reasons are generated, **Then** they remain honest and avoid overclaiming certainty.
3. **Given** the model view is close to 50/50, **When** reasons are rendered, **Then** they describe the brief as balanced rather than forcing a strong favorite story.
4. **Given** the brief is partially ready, **When** the reason stack renders, **Then** it reflects only the available inputs and not unsupported claims.

---

### User Story 4 - Discoverable Pre-Match Entry Points (Priority: P2)

As a public visitor on the current dashboard, I want obvious links into pre-match briefs from today’s match surfaces, so that I can find the before-match product without guessing.

**Why this priority**: The brief only helps if people can discover it from the existing homepage and today pages.

**Independent Test**: Open the homepage and IPL-today page while logged out and verify there are clear links into pre-match surfaces for upcoming fixtures.

**Acceptance Scenarios**:

1. **Given** an upcoming match exists, **When** the homepage or IPL-today page renders, **Then** the user can see a link into the pre-match brief.
2. **Given** a match is already live, **When** public live pages render, **Then** they do not pretend the pre-match brief is the active live product.
3. **Given** a pre-match brief list page exists, **When** a user scans the page, **Then** upcoming briefs are visually distinct from live prediction cards.

---

## Edge Cases

- **No upcoming fixture**: Show an intentional empty state with guidance back to live or proof surfaces.
- **No pre-match probability yet**: Render the fixture and context shell, but label probability as not ready.
- **Venue known but conditions unknown**: Show venue sections as ready and conditions sections as not ready.
- **Close-to-even match**: Avoid “strong edge” language when pre-match probability is near 50%.
- **Live match crossover**: Once a match is live, the brief should clearly route users toward live pages instead of pretending it is still a pure pre-match page.
- **Missing venue mapping**: Fall back to fixture-level context and honest not-ready venue fields.
- **Multiple upcoming fixtures**: Ordering should be deterministic and useful, ideally by start time and league relevance.
- **League expansion later**: V1 may default to IPL, but serializers and page services should avoid hardcoding IPL-only semantics where generic names make sense.

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provide a dedicated public pre-match brief surface for upcoming fixtures.
- **FR-002**: The first version MUST support at least IPL upcoming fixtures through existing scheduler candidate or fixture discovery pathways.
- **FR-003**: The pre-match brief MUST display a pre-match win probability when a model view is available.
- **FR-004**: The pre-match brief MUST display a projected first-innings score or scoring band when enough context exists.
- **FR-005**: The pre-match brief MUST surface venue bias context using available venue priors such as average score and bat-first win tendency.
- **FR-006**: The pre-match brief MUST surface toss sensitivity in a user-readable form.
- **FR-007**: The pre-match brief MUST support dew and rain context sections with explicit `ready`, `partial`, or `not_ready` behavior.
- **FR-008**: The pre-match brief MUST include 3 to 5 plain-English reasons for the model lean when enough supporting context exists.
- **FR-009**: The pre-match brief MUST expose pressure zones or scoring bands that help interpret the likely first-innings range.
- **FR-010**: The implementation MUST keep pre-match payloads separate from live public payloads, with their own safe serializer or service boundary.
- **FR-011**: The implementation MUST include a list or discovery surface for upcoming pre-match briefs, or clearly integrate them into an existing public upcoming-fixture surface.
- **FR-012**: The implementation MUST add tests covering ready, partial, not-ready, and no-upcoming-fixture states.
- **FR-013**: The implementation MUST distinguish pre-match intelligence from live win probability and post-match proof in route copy and UX labels.
- **FR-014**: The implementation MUST document the source and fallback behavior for each brief section, especially venue bias, toss sensitivity, and conditions context.

### Non-Functional Requirements

- **NFR-001**: The V1 brief should reuse existing scheduler, fixture, and venue-prior sources where practical instead of requiring a brand-new data platform.
- **NFR-002**: The page should remain useful and honest even when only partial supporting context is ready.
- **NFR-003**: The first version should prefer server-rendered content for the main brief rather than requiring a client-only application shell.
- **NFR-004**: The UI should preserve the current CrickenZen public design language while clearly distinguishing upcoming briefs from live cards.

### Key Entities

- **PrematchBriefSummary**: A list-card representation of one upcoming fixture with headline pre-match signals.
- **PrematchBriefDetail**: The full brief payload for one upcoming fixture, including venue context, toss sensitivity, conditions status, pressure zones, and reasons.
- **PrematchFactorCard**: One user-facing factor block such as win probability, projected first innings, or toss leverage.
- **ConditionsStatus**: A structured object for dew or rain with `ready`, `partial`, or `not_ready` state and explanatory copy.
- **PressureZoneBand**: A labeled scoring band such as below par, par range, or above-par pressure threshold.
- **PrematchReason**: One concise structured reason explaining the pre-match lean.

---

## Success Criteria

- **SC-001**: A logged-out user can open a dedicated pre-match brief for an upcoming IPL fixture and understand the pre-match model story in under 60 seconds.
- **SC-002**: The brief shows win probability, projected first-innings context, venue bias, toss sensitivity, and at least 3 reasons when those inputs are available.
- **SC-003**: Missing conditions inputs such as dew or rain do not produce fake neutral values; they render honest not-ready states.
- **SC-004**: Upcoming brief discovery is visible from current public surfaces.
- **SC-005**: The phase leaves the repo ready for ranked recommendations and future Ask/agent layers without redefining pre-match semantics.

---

## Assumptions

- IPL is the right default scope for V1, but the implementation should stay reusable enough for later league expansion.
- Venue priors from `src/bbl_pipeline/features/store.py` are a legitimate starting point for V1 venue bias and pressure-zone logic.
- Conditions context may be partially ready in V1; honest `not_ready` states are preferable to guessed weather or dew claims.
- The pre-match reason stack should come from structured heuristics and existing model/venue context first, not a generic LLM layer.

## Dependencies

- `dashboard/app/public.py`
- `dashboard/app/routers/pages.py`
- `dashboard/templates/public.html`
- `dashboard/templates/ipl_today.html`
- `dashboard/templates/match_public.html`
- `src/bbl_pipeline/features/store.py`
- `docs/DASHBOARD_EXECUTION_TRACKER.md`

## Out of Scope

- Ask CrickenZen chat or free-form question answering
- Ranked player or fantasy recommendations
- Building a weather ingestion platform beyond the V1-ready fallback structure
- Rewriting the live dashboard experience
- Post-match proof or calibration changes
