# Feature Specification: Public Dashboard Growth Surfaces

**Feature Branch**: `013-public-dashboard-growth`  
**Created**: 2026-04-27  
**Status**: Draft  
**Input**: Turn the existing private CrickenZen dashboard into a public acquisition engine by adding SEO/indexable match pages, unauthenticated lite prediction APIs, simple model insight copy, Telegram distribution hooks, and clear upgrade paths into the paid dashboard.

## Definitions

- **Public match page**: An unauthenticated HTML page for a single match or match-search intent, built for users searching live cricket prediction terms such as "IPL prediction today", "DC vs RCB win probability", or "who will win MI vs CSK".
- **Public lite API**: Unauthenticated endpoints that expose only acquisition-safe prediction data: match title, score, status, rounded win probability, projected score/chase pressure, and one short model insight.
- **Premium dashboard**: The existing authenticated dashboard at `/dashboard`, including detailed model blend, Monte Carlo, ODM, full timeline, commentary, manual match starts, and multi-match tracking.
- **Model insight copy**: User-facing text generated from current state and recent probability history, e.g. "RCB win probability up 8% in the last 2 overs" instead of raw model fields.
- **Programmatic SEO page**: A deterministic route or template that can render many match-specific pages from match metadata and live state without manually creating static files.
- **Distribution event**: A generated prediction update intended for Telegram and later social channels, triggered by live match milestones or probability swings.
- **Entitlement boundary**: The separation between free public value and paid dashboard detail.

## Current State

### What Already Exists ✅

- **FastAPI dashboard app** in `dashboard/app/` with page routes, auth routes, live prediction routes, admin routes, and health checks.
- **Authenticated dashboard** at `/dashboard` showing live/upcoming matches, score state, win probability timeline, model blend, projections, ODM signal, and commentary.
- **PredictionManager** can list active predictions and read latest JSON state from live predictor subprocess output.
- **Auto scheduler** can discover CREX candidates and expose scheduler status to authenticated users.
- **League configs** support IPL, PSL, BBL, SA20, ILT20, WPL, T20 World Cup, SSM, and BPL.
- **Telegram package** exists under `src/bbl_pipeline/telegram/`, including message formatting and bot client tests.
- **Subscriber/admin foundation** exists: users have `plan`, `is_active`, admin subscriber creation, suspension, and reactivation.

### What Is Missing ❌

- **No public acquisition home page**: `/` redirects directly to `/dashboard`.
- **No public match pages**: routes such as `/ipl-prediction-today` or `/match/{slug}` do not exist.
- **No unauthenticated lite API**: all meaningful live prediction state requires login.
- **No SEO metadata for match pages**: no canonical titles/descriptions targeted at search demand.
- **No public-safe state serializer**: current state enrichment includes premium-only details such as model blend, MC, ODM, full history, and commentary.
- **No plan enforcement**: `plan` is displayed but not used to gate public/pro/premium capabilities.
- **No model insight copy layer**: UI surfaces raw metrics more than simple, shareable prediction claims.
- **No automated Telegram distribution for live dashboard updates**.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Public Cricket Prediction Entry Points (Priority: P1)

As a cricket fan searching during a live match, I want to open a public CrickenZen prediction page without logging in, so that I can quickly see who is favoured and whether the match momentum is changing.

**Why this priority**: This fixes the main growth gap: the model is valuable but hidden behind authentication. Public entry pages create surfaces where search and social users can collide with the product.

**Independent Test**: Open `/ipl-prediction-today` and `/match/{slug}` in a logged-out browser. Verify the pages render without a token, show current public match rows or a useful empty state, and include a CTA to `/login` or `/dashboard`.

**Acceptance Scenarios**:

1. **Given** there are live or discovered IPL matches, **When** a logged-out user opens `/ipl-prediction-today`, **Then** they see match cards with title, status, score if available, rounded win probability if available, and one short model insight.
2. **Given** a public match slug resolves to an active or discovered match, **When** a logged-out user opens `/match/{slug}`, **Then** the page renders a match-specific prediction view with live score, win probability, projection/chase pressure, last 5 public swings, and an "Unlock full model dashboard" CTA.
3. **Given** no live match is active, **When** `/ipl-prediction-today` is opened, **Then** the page renders upcoming/discovered matches and an SEO-friendly empty state, not a login wall or server error.
4. **Given** a match slug cannot be resolved, **When** `/match/{slug}` is opened, **Then** the response returns a useful 404-style public page with links back to `/ipl-prediction-today` and `/`.

---

### User Story 2 — Public Lite Prediction API (Priority: P1)

As a frontend or distribution surface, I want a public API that returns only lite prediction data, so that public pages and Telegram/social snippets can reuse the same safe acquisition payload.

**Why this priority**: A public serializer and API prevent accidental leakage of premium model internals while enabling multiple growth surfaces.

**Independent Test**: Call `/api/public/matches`, `/api/public/ipl-today`, and `/api/public/matches/{slug}` without an Authorization header. Verify they return 200 for resolvable data, contain rounded probability and one insight, and omit MC, ODM, detailed blend weights, full history, and commentary.

**Acceptance Scenarios**:

1. **Given** active predictions exist, **When** `/api/public/matches` is called without auth, **Then** it returns a list of public match summaries.
2. **Given** IPL auto-discovery has candidate matches, **When** `/api/public/ipl-today` is called, **Then** it includes discovered IPL candidates even before a live prediction subprocess has started.
3. **Given** a match has detailed internal state, **When** it is serialized for the public API, **Then** it exposes only free fields and omits premium fields: `monte_carlo`, `odm`, raw `blend`, full `history`, full `chart_history`, `commentary`, `features`, and `pred_state`.
4. **Given** probability history exists, **When** the public API returns a match detail, **Then** it includes at most 5 public swing points, each rounded and safe for display.

---

### User Story 3 — Model Edge as Simple Copy (Priority: P1)

As a casual user, I want the prediction engine to explain the current situation in plain language, so that I understand the edge without reading model internals.

**Why this priority**: The product differentiation is the model, but raw fields like `ml_prob`, `mc_prob`, or `resource_win_prob` do not create an immediate hook.

**Independent Test**: Feed representative states into the insight builder and verify it emits deterministic one-sentence insights for probability swings, pressure, chase/par status, and missing-data fallback.

**Acceptance Scenarios**:

1. **Given** a team's win probability has moved by at least 5 percentage points recently, **When** the public serializer builds an insight, **Then** the insight describes the swing and affected side.
2. **Given** the chasing side has a target and required run rate is high, **When** insight copy is generated, **Then** it describes chase pressure rather than showing only numeric RRR.
3. **Given** innings 1 has projected score and par/venue average data, **When** insight copy is generated, **Then** it describes whether the batting side is ahead of or behind par.
4. **Given** no model state is available yet, **When** insight copy is generated, **Then** it returns a safe placeholder such as "Model probability will appear once live ball data is available."

---

### User Story 4 — Telegram-First Distribution Hooks (Priority: P2)

As an operator, I want the system to generate Telegram-ready prediction updates during live matches, so that CrickenZen appears where cricket attention already exists.

**Why this priority**: Cricket attention is event-driven. Telegram updates are a high-density distribution channel and can reuse the public lite payload.

**Independent Test**: Run a dry-run Telegram publisher against a sample public match payload and verify it emits messages for match start, 5-over milestones, probability swings, final-over pressure, and match completion without posting duplicate updates.

**Acceptance Scenarios**:

1. **Given** a match starts, **When** public state first becomes available, **Then** a Telegram-ready "match live" message can be generated.
2. **Given** a match crosses a 5-over milestone, **When** a new public state is processed, **Then** one milestone message is generated and subsequent duplicate states do not repost the same milestone.
3. **Given** win probability moves by at least the configured threshold, **When** a new public state is processed, **Then** a turning-point message is generated.
4. **Given** a match ends, **When** final state is processed, **Then** a post-match summary message can be generated with final probability recap if available.

---

### User Story 5 — Upgrade Path and Entitlement Boundary (Priority: P2)

As a free public user, I want to understand what is available in the full dashboard, so that I can upgrade only after seeing useful prediction value.

**Why this priority**: Monetization should happen after proof of value. Public pages must show enough to acquire users while reserving detailed model data for paid plans.

**Independent Test**: Open public pages and authenticated dashboard as free/monthly/yearly/admin users. Verify public pages are visible to everyone, free users see upgrade CTAs for premium panels, and premium-only fields remain unavailable from public endpoints.

**Acceptance Scenarios**:

1. **Given** a logged-out user views a public page, **When** they click "Unlock full model dashboard", **Then** they are taken to login/register with return context preserved.
2. **Given** a free authenticated user opens `/dashboard`, **When** premium features are displayed, **Then** MC/ODM/full timeline areas can show upgrade states instead of raw premium data.
3. **Given** a paid user opens `/dashboard`, **When** premium features load, **Then** existing full model detail remains available.
4. **Given** a public API request is made, **When** the requester is unauthenticated, **Then** premium fields are never returned regardless of user plan.

---

## Edge Cases

- **No active predictions**: Public pages must still render discovered/upcoming matches and SEO copy.
- **Auto scheduler disabled**: Public API must return a stable empty response with `enabled=false` metadata rather than failing.
- **CREX discovery returns wrong-league candidates**: Public IPL pages must filter candidates to IPL-specific source/URL/league metadata and avoid showing unrelated live cricket as IPL prediction content.
- **Duplicate active predictions**: Public summaries should dedupe by normalized match URL/slug.
- **Unknown teams from URL slugs**: Slug parser should create readable titles even when state has not yet resolved team names.
- **State file temporarily incomplete**: Public serializer must tolerate missing JSON or partial state and return a safe "starting soon" payload.
- **Probability unavailable**: Public pages must avoid fake precision and show "Awaiting model" instead of `0%`.
- **Mobile search traffic**: Public templates must be responsive and show the current answer above the fold.
- **SEO noindex for low-value pages**: Empty or unresolvable match pages should not create thin-indexed content.
- **Legal/product risk**: Copy must present predictions as model probabilities/analytics, not guaranteed betting advice.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST change `/` from a redirect to `/dashboard` into a public acquisition page rendered from a new public template.
- **FR-002**: The system MUST provide `/ipl-prediction-today` as a public HTML route that renders current IPL live/discovered/upcoming public prediction cards without authentication.
- **FR-003**: The system MUST provide `/match/{slug}` as a public HTML route for match-specific prediction pages.
- **FR-004**: The system MUST provide `/prediction/{league}/{teams}` as a public alias route that resolves to the same match-detail template when possible.
- **FR-005**: The system MUST add unauthenticated public API endpoints: `/api/public/matches`, `/api/public/matches/{slug}`, and `/api/public/ipl-today`.
- **FR-006**: The public API MUST use a dedicated public serializer that exposes only allowed free fields and omits premium model internals.
- **FR-007**: Public match summaries MUST include: `slug`, `title`, `league`, `status`, `score`, `overs`, `win_probability_pct`, `projected_score` or chase pressure, `insight`, `updated_at`, and `detail_url` when available.
- **FR-008**: Public match detail MUST include at most the last 5 public probability swing points and MUST NOT include raw full history.
- **FR-009**: The public serializer MUST round win probability to whole percentages.
- **FR-010**: The system MUST generate deterministic model insight copy from live state and recent public history.
- **FR-011**: Public pages MUST include SEO title, meta description, canonical URL, and Open Graph basics for match/share surfaces.
- **FR-012**: Public pages MUST include clear CTAs to unlock the full authenticated dashboard.
- **FR-013**: Public pages MUST be usable with JavaScript disabled for initial content, with optional client-side polling/enhancement allowed after first render.
- **FR-014**: Public API responses MUST be cache-safe for short intervals and include no user-specific data.
- **FR-015**: The existing authenticated dashboard MUST continue to work with no regression in current live match start/list/state behavior.
- **FR-016**: The system MUST add tests proving public endpoints are accessible without auth and premium endpoints still require auth where applicable.
- **FR-017**: The system MUST provide a Telegram dry-run publisher/service that consumes public match payloads and produces Telegram-ready messages without requiring live bot credentials in tests.
- **FR-018**: Telegram distribution MUST dedupe milestone/swing posts per match to avoid repeated messages for unchanged states.
- **FR-019**: Public IPL surfaces MUST filter out non-IPL candidates if CREX discovery returns general live-score matches.
- **FR-020**: The implementation MUST keep premium dashboard fields available only behind authenticated routes and/or plan gates.

### Key Entities

- **PublicMatchSummary**: Public-safe summary for listing pages and cards. Fields: `slug`, `title`, `league`, `status`, `score`, `overs`, `win_probability_pct`, `projection_label`, `insight`, `updated_at`, `detail_url`.
- **PublicMatchDetail**: Public-safe detail payload for match pages. Extends `PublicMatchSummary` with `team_a`, `team_b`, `venue`, `target`, `last_swings`, and CTA metadata.
- **PublicSwingPoint**: One public probability movement point with rounded over, score, win probability percentage, and short label. Limited to last 5.
- **InsightBuilder**: Pure helper that converts prediction state/history into one acquisition-friendly sentence.
- **PublicMatchRepository/Service**: Read-only service that combines active predictions and scheduler candidates, dedupes them, resolves slugs, and applies the public serializer.
- **TelegramDistributionEvent**: A message candidate derived from public payload and event rules: start, milestone, swing, final pressure, completion.
- **EntitlementPolicy**: Rules mapping user plan to dashboard capabilities; public API always uses the free policy.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Logged-out users can open `/`, `/ipl-prediction-today`, and `/match/{slug}` without being redirected to `/login`.
- **SC-002**: `/api/public/matches`, `/api/public/ipl-today`, and `/api/public/matches/{slug}` return valid JSON without an Authorization header.
- **SC-003**: Public API payloads contain no premium keys: `monte_carlo`, `odm`, `blend`, `features`, `pred_state`, `history`, `chart_history`, `commentary`, `ml_prob`, `mc_prob`, `ml_weight`, or `mc_weight`.
- **SC-004**: Public win probability values are rounded to integer percentages; no decimal precision is exposed publicly.
- **SC-005**: Public match pages render a useful first viewport on mobile width with match title, score/status, probability/awaiting-model state, insight, and CTA visible.
- **SC-006**: Existing dashboard tests continue to pass after the public router is added.
- **SC-007**: New tests cover no-active-match, active-match, discovered-candidate, missing-state, unknown-slug, and premium-field-redaction cases.
- **SC-008**: Telegram dry-run tests generate one message per milestone/swing event and do not duplicate messages for identical state.
- **SC-009**: Public IPL page filters out non-IPL candidate URLs during the known CREX discovery mixed-feed case.
- **SC-010**: Public pages include indexable SEO metadata for valid match/today pages and noindex metadata for unresolved/empty detail pages.

---

## Assumptions

- The current FastAPI/Jinja/Alpine dashboard is the active web stack for this repo. Any Angular/Spring references from growth notes are treated as conceptual, not implementation targets.
- Live match state remains sourced from `PredictionManager` and auto scheduler candidates; no new scorer ingestion system is required for the MVP.
- Public pages can launch before Stripe/billing is implemented, as long as CTAs route users toward login/register and the entitlement boundary is explicit.
- Public win probability is rounded and intentionally less detailed than the dashboard to preserve premium value.
- Telegram MVP can start as dry-run/service logic with tests before enabling live bot posting in production.

## Dependencies

- Existing dashboard app must continue running via `dashboard/app/main.py`.
- Existing `PredictionManager` state reading and `AutoPredictionScheduler.status()` are the source of public match/candidate data.
- Existing templates/base styling and Tailwind output can be reused.
- Telegram posting depends on existing `src/bbl_pipeline/telegram/` config/client modules, but dry-run tests must not require bot credentials.
