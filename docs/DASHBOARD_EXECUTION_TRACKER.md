# Dashboard Execution Tracker

Last updated: 2026-06-08
Owner: CrickenZen dashboard workstream
Status: Active (3 of 4 planned phases implemented)

## Purpose

This file is the durable cross-session tracker for dashboard product work.

Use it to keep the roadmap, current priority, success metrics, and completion state in one place even when work is split across multiple Codex sessions.

Do not use the constitution for short-horizon dashboard roadmap items unless a core project principle changes. The constitution stays stable; this file tracks execution.

## Product Read

Current dashboard strength:

- Strong live prediction engine
- Authenticated dashboard
- Public match cards and match detail pages
- Live win probability, projections, Monte Carlo blend, and streaming state
- Public proof page with Brier, ECE, accuracy ledger, and segment drilldowns
- Pre-match intelligence: upcoming fixture briefs with venue priors, toss sensitivity, pressure zones, and plain-English reasons

Current dashboard gap:

- Product packaging is weaker than leading public cricket intelligence sites
- Explanation layer is thin
- No in-product `Ask` workflow yet
- No ranked player or matchup recommendation layer yet
- Conditions data (dew, rain) is V1 not-ready — wired but awaiting data feed integration
- Pre-match win probability requires model integration (currently resolved from running predictions only)

## Execution Order

The immediate goal is to improve trust and product clarity before expanding the intelligence surface.

### Phase 0: Metrics Foundation (Spec 017)

Why this phase exists:

- The proof page must be backed by stable, queryable metrics
- We need one authoritative path for Brier, ECE, and accuracy reporting

Priority: High
Status: Implemented and verified (2026-06-07)

Spec path:

- `specs/017-dashboard-metrics-foundation/spec.md`
- `specs/017-dashboard-metrics-foundation/plan.md`

Definition of done:

- [x] Define the canonical metric sources for dashboard-visible performance
- [x] Decide the reporting grain: overall, by league, by innings, by phase, by time window
- [x] Expose Brier, ECE, and accuracy through a stable backend path for dashboard use
- [x] Document how metrics are computed, refreshed, and validated
- [x] Ensure metric labels clearly separate offline, live, and market-comparison contexts

Required metrics tracked:

- [x] Brier score
- [x] ECE (10-bin histogram, matches StateAnalyzer)
- [x] Accuracy (derived from first-ball model_final_prob favoritism vs metadata winner)
- [x] Sample count
- [x] Last updated timestamp
- [x] Evaluation window

Nice-to-have follow-ons:

- [x] Log loss
- [x] Segment drilldowns (by innings, phase, team tier)
- [x] Rolling 7-day and 30-day views
- [x] Accuracy ledger with windowed queries
- [x] Excluded-rows reporting for undated/missing-timestamp rows

Key decisions:

- Consolidated file priority: `all_matches.parquet` > `cricket-live-score.parquet` > any other non-special `.parquet`
- Accuracy derivation V1: compares first-ball `model_final_prob` favoritism against metadata `winner`
- Undated rows excluded from windowed accuracy ledger queries
- Proof page status logic: missing probability OR missing accuracy → `partial`, not `ready` (symmetric)

Validation commands used:

- `pytest tests/unit/analysis/test_proof_metrics.py -q`
- `pytest dashboard/tests/test_proof_metrics.py -v --noconftest`
- `python scripts/build_dashboard_metrics_snapshot.py --league ipl --window all_available`

Evidence files:

- `src/bbl_pipeline/analysis/proof_metrics.py` — canonical snapshot builder
- `scripts/build_dashboard_metrics_snapshot.py` — CLI snapshot builder
- `dashboard/app/proof_metrics.py` — dashboard-side loader with stale/not-ready handling
- `dashboard/app/routers/proof.py` — `/api/proof/summary|segments|ledger|manifest`
- `dashboard/app/main.py` — registered proof router
- `tests/unit/analysis/test_proof_metrics.py` — 39 tests
- `dashboard/tests/test_proof_metrics.py` — 15 pass, 6 skip (no sqlalchemy)
- `tests/conftest.py` — adds project root + dashboard/ to sys.path

### Phase 1: Proof Page (Spec 018)

Why this phase exists:

- Trust is the biggest product gap
- This is the highest-priority phase

Priority: Highest
Status: Implemented and verified (2026-06-07)

Spec path:

- `specs/018-dashboard-proof-page/spec.md`
- `specs/018-dashboard-proof-page/plan.md`
- `specs/018-dashboard-proof-page/tasks.md`

Definition of done:

- [x] Public proof page at `/proof` with league query param
- [x] Rolling Brier, ECE, and accuracy summary cards
- [x] Prediction ledger shows predicted outcome vs actual result
- [x] Methodology copy explains each metric in plain English
- [x] Users can see evaluation window and sample size
- [x] Metrics segmentable by league, innings, and phase
- [x] Freshness badge (ready/stale/not-ready)

Core scope:

- [x] Summary cards for Brier, ECE, accuracy, sample count
- [x] Prediction history table with proof ledger
- [x] Segment views for innings and phase where available
- [x] Calibration summary section
- [x] Honest caveats about probability-based forecasting
- [x] CTAs from `public.html` and `match_public.html` linking to `/proof`

Key decisions:

- Page status: symmetric partial logic — missing probability OR missing accuracy → `partial`
- Methodology copy lives in page context builder, not in template
- Templates use Jinja2 directly (not FastAPI TestClient) for rendering tests to bypass missing sqlalchemy

Evidence files:

- `dashboard/app/proof_page.py` — page context builder with `_derive_page_status()`
- `dashboard/templates/proof.html` — full proof page (hero, freshness, summary cards, methodology, segments, ledger, CTAs)
- `dashboard/app/routers/pages.py` — `/proof` route
- `dashboard/templates/public.html` — proof CTA added
- `dashboard/templates/match_public.html` — proof CTA added
- `tests/test_proof_page.py` — 27 tests (ready/stale/not-ready/partial states, combinatorics, template rendering, CTA presence)

### Phase 2: Ask CrickenZen

Why this phase exists:

- The dashboard needs a question-driven product layer
- The answer engine should read our real model state, not hallucinate or guess

Priority: High
Status: Deferred (2026-06-07)

Deferred note:

- Explicitly skipped so the next build focus can move to pre-match product packaging first.

Definition of done:

- [ ] Dashboard includes an `Ask CrickenZen` entry point
- [ ] Backend `/api/ask` or equivalent endpoint exists
- [ ] Intent-based answering works on structured data first
- [ ] Answers include supporting data, not only prose

Phase 2 starter intents:

- [ ] Who is ahead and why?
- [ ] What changed in the last 2 overs?
- [ ] Is the market above or below our model?
- [ ] What is dew doing to the chase?
- [ ] Show similar historical states

Guardrails:

- [ ] Structured backend facts first, optional LLM summarization second
- [ ] Clear separation between live state, historical analysis, and inferred explanation

### Phase 3: Pre-Match Match Brief (Spec 020)

Why this phase exists:

- Competitors package pre-match intelligence better than we do
- We need a before-the-toss product, not only a live-match product

Priority: High
Status: Implemented and verified (2026-06-08), with P0/P1/P2 bug fixes applied

Spec path:

- `specs/020-pre-match-match-brief/spec.md`
- `specs/020-pre-match-match-brief/plan.md`
- `specs/020-pre-match-match-brief/tasks.md`

Implementation summary:

- Standalone pre-match serializer (`dashboard/app/prematch.py`) with dataclasses, venue-prior lookup (17 IPL venues), toss-sensitivity heuristics, pressure-zone generation, conditions-status framework, and deterministic reason engine (3–5 reasons)
- Page context builder (`dashboard/app/prematch_page.py`) with factor cards, condition cards, and methodology copy
- Routes: `GET /ipl-match-brief-today` (discovery list) and `GET /pre-match/{slug}` (detail)
- Templates: `ipl_match_brief_today.html` (list) and `prematch_brief.html` (detail) — Tailwind dark theme
- CTAs on `public.html` ("Before the toss" section) and `ipl_today.html` (top-right link)
- Kept standalone — no `app.public` or `pydantic_settings` dependency

Definition of done:

- [x] Pre-match page or card exists before live prediction begins
- [x] Match brief includes win probability and projected score
- [x] Match brief includes venue and condition context
- [x] Match brief includes 3 to 5 reasons in plain English

Target elements:

- [x] Win probability (from running prediction if available)
- [x] Projected first innings (~par from venue prior)
- [x] Venue bias (batting-first friendly / chase-friendly / balanced)
- [x] Dew or rain risk (V1 `not_ready` — framework in place)
- [x] Toss sensitivity (high / medium / low leverage)
- [x] Pressure zones (above par / par band / below par)
- [x] Key reasons (3–5, deterministic from venue + probability + toss)

Bug fix log (2026-06-08):

| Severity | Issue | Fix |
|----------|-------|-----|
| **P0** | `get_detail()` always returned `None` venue (stub), `None` probability | Venue resolver scans candidate label/URL for known IPL venue substrings with generic-word exclusion. Service caches candidate dicts by slug. Probability looked up from running predictions on same URL. |
| **P1** | `_match_title("MI vs CSK on Jun 07, 2026 at 14:30 PM T20")` → `"MI vs CSK vs T20"` (format treated as team) | Regex rewritten for `YYYY at HH:MM AM/PM FORMAT` pattern. Same fix in `public.py:title_from_label()`. |
| **P1** | CTA link used naive `/pre-match/` → `/match/` replace, producing 404 (pre-match slug ≠ live slug) | Added `live_match_slug` field to `PrematchBriefDetail` computed as `_slugify(f"{title} {league} win probability")`. Template uses `ctx.detail.live_match_slug`. |
| **P2** | No tests for real `PrematchService.get_detail()` service path | Added 15 new tests: 4 service integration, 5 title parsing, 4 venue resolution, 2 live slug, 1 CTA-link rendering. |

Validation commands used:

- `$env:PYTHONPATH = "dashboard"; pytest dashboard/tests/test_prematch.py -v --noconftest` — 38/38
- `$env:PYTHONPATH = "dashboard"; pytest dashboard/tests/test_prematch_page.py -v --noconftest` — 11/11
- Manual runtime check: `PrematchService.get_detail()` with fake IPL candidate — venue resolves, slug correct, live CTA slug matches public pattern

Evidence files:

- `dashboard/app/prematch.py` — pre-match serializer/service with venue aliases, 17 IPL venue priors, and `_pre_match_live_slug()`
- `dashboard/app/prematch_page.py` — page context builder with factor cards, condition cards
- `dashboard/app/routers/pages.py` — `/ipl-match-brief-today` and `/pre-match/{slug}` routes (lines 161–192)
- `dashboard/templates/ipl_match_brief_today.html` — upcoming briefs discovery page
- `dashboard/templates/prematch_brief.html` — detail page (hero, factor cards, conditions, pressure zones, reasons, methodology, live CTA)
- `dashboard/templates/public.html` — "Before the toss" CTA section linking to `/ipl-match-brief-today`
- `dashboard/templates/ipl_today.html` — pre-match brief link in hero header
- `dashboard/tests/test_prematch.py` — 38 tests (venue, bias, toss, pressure, conditions, reasons, slug, title parsing, venue resolution, live slug, service integration)
- `dashboard/tests/test_prematch_page.py` — 11 tests (context cards, condition badges, template rendering for list/detail/empty/not-ready, CTA presence including live-match-slug)

### Phase 4: Ranked Recommendations

Why this phase exists:

- This is the most obvious surface-area gap against fantasy-oriented products
- It should come after trust, proof, and explanation are in place

Priority: Medium
Status: Planned

Definition of done:

- [ ] Ranked player or matchup recommendations exist
- [ ] Ranking logic is documented and reproducible
- [ ] Recommendations clearly explain why a player or matchup ranks highly

Starter scope:

- [ ] Top ranked players 1 to 22
- [ ] Captain and vice-captain candidates
- [ ] Matchup edges
- [ ] Suitability by conditions and phase

## Current Priority

As of 2026-06-08, the active execution order is:

1. ~~Phase 0: Metrics Foundation~~ — DONE
2. ~~Phase 1: Proof Page~~ — DONE
3. ~~Phase 3: Pre-Match Match Brief~~ — DONE (with bug fixes)
4. Phase 4: Ranked Recommendations — next
5. Phase 2: Ask CrickenZen — deferred

## Architecture Notes

### Dashboard test commands (must use these exactly)

| Layer | Command |
|-------|---------|
| Dashboard app tests | `$env:PYTHONPATH = "dashboard"; pytest dashboard/tests/test_*.py -v --noconftest` |
| Pipeline tests | `pytest tests/unit/analysis/test_*.py -q` |
| Proof page tests | `pytest tests/test_proof_page.py -v` (uses `tests/conftest.py` which adds root + dashboard to sys.path) |

### Import conventions

- Dashboard routes import from `app.*` (not `dashboard.app.*`)
- New service modules must NOT import from `app.public` (pulls in `pydantic_settings`). Inline small utilities instead.
- Templates extend `dashboard/templates/base.html`
- Template rendering tests use `jinja2.Environment(loader=FileSystemLoader(template_dir))`, not FastAPI TestClient (avoids sqlalchemy dependency)

### Visual language

- Dark theme: `bg-slate-950`, `border-slate-800`, `bg-slate-900`
- Status colors: emerald = ready, amber = stale/upcoming, slate = not-ready
- Typography: `rounded-2xl`, `font-black`, `tracking-tight`

## Session Continuity Rules

Update this file whenever dashboard roadmap work starts or ends.

At minimum, future sessions should update:

- `Last updated`
- phase status
- newly completed checklist items
- blocked items
- any changed priority order

When a phase starts implementation through Spec Kit, add:

- the spec folder path
- the implementation owner
- the validation commands used
- the evidence files or URLs

## Future Spec Kit Sequence

When we begin implementation, use Spec Kit for each phase and keep this tracker as the top-level roadmap.

Completed:

- Spec 017: Dashboard metrics foundation — implemented and verified
- Spec 018: Dashboard proof page — implemented and reviewed
- Spec 020: Pre-match match brief — implemented and verified (with P0/P1/P2 fixes)

Planned:

- Spec 019: Ask CrickenZen — deferred
- Spec 021: Ranked recommendations — next active phase

If priorities change, update this section and the `Current Priority` section together.

## Notes

- Proof must report Brier, ECE, and accuracy honestly
- Accuracy alone is not enough; probability quality must stay front and center
- Dashboard messaging should always distinguish between live win probability, pre-match intelligence, and post-match proof
- Pre-match serializer kept standalone to avoid `pydantic_settings` dependency chain
- Conditions (dew, rain) are V1 `not_ready` — data framework exists for future integration
- Snapshot build script must be run to generate `data/dashboard_metrics/latest/` before `/proof` shows data
- 6 test skips in `test_proof_metrics.py` when `sqlalchemy` is not installed — expected, not a regression
