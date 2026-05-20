# Tasks: Public Dashboard Growth Surfaces (013-public-dashboard-growth)

**Input**: `specs/013-public-dashboard-growth/plan.md`, `specs/013-public-dashboard-growth/spec.md`  
**Feature Branch**: `013-public-dashboard-growth`  
**Date**: 2026-04-27

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files or is pure verification
- **[Story]**: User story from `spec.md`
- Exact file paths are included wherever implementation is required

---

## Phase 1: Setup & Baseline Verification

**Purpose**: Confirm current dashboard behavior before adding public routes.

- [ ] T001 Verify current `/` redirects to `/dashboard` by checking `dashboard/app/routers/pages.py`; record this as the behavior to replace (FR-001)
- [ ] T002 [P] Verify existing dashboard server starts locally and `/health` returns `{"status":"ok"}` using commands from `plan.md`
- [ ] T003 [P] Run current focused dashboard tests: `cd dashboard; .venv\Scripts\python.exe -m pytest tests/test_live.py tests/test_auth.py -q`
- [ ] T004 [P] Inspect current public/no-auth endpoints (`/api/matches/leagues`, `/api/matches/detect-league`) to ensure new public endpoints do not conflict with existing route prefixes

**Checkpoint**: Current dashboard baseline known and stable.

---

## Phase 2: Public Serializer Foundation (Blocks MVP)

**Purpose**: Create the safe data boundary before exposing any unauthenticated API or page.

⚠️ **CRITICAL**: Do not expose `/api/public/*` until the serializer redaction tests exist.

- [ ] T005 [US2] Create `dashboard/app/public.py` with public dataclasses or Pydantic models for `PublicMatchSummary`, `PublicMatchDetail`, and `PublicSwingPoint` (FR-007, FR-008)
- [ ] T006 [US2] Add slug helpers to `dashboard/app/public.py`: normalize active match title/state/CREX URL into stable lowercase slugs (FR-003, FR-004)
- [ ] T007 [US2] Add probability helpers to `dashboard/app/public.py`: extract best available internal probability, round to integer percent, and return `None` instead of `0` when probability is unavailable (FR-009)
- [ ] T008 [US3] Add `build_public_insight(state, swings)` to `dashboard/app/public.py` with priority order: probability swing, chase pressure, par/projection status, basic probability, fallback copy (FR-010)
- [ ] T009 [US2] Add public swing extraction to `dashboard/app/public.py`: derive at most 5 rounded public swing points from enriched history without returning raw history (FR-008)
- [ ] T010 [US2] Add public summary/detail serializer functions to `dashboard/app/public.py` that explicitly whitelist allowed fields and never pass through raw state (FR-006, FR-007)
- [ ] T011 [US2] Add `PublicMatchService` to `dashboard/app/public.py` that reads active predictions from `PredictionManager`, optionally reads scheduler candidates, dedupes by normalized URL/slug, and returns public summaries/details (FR-005, FR-019)

**Checkpoint**: Public payload can be produced in-process, but no route exposes it yet.

---

## Phase 3: Serializer and Insight Tests (Blocks Public API)

**Purpose**: Lock the premium data boundary with tests before adding unauthenticated routes.

- [ ] T012 [P] [US3] Create `dashboard/tests/test_public_insights.py` covering insight output for probability swing, second-innings chase pressure, first-innings above/below par, basic probability, and missing state fallback (FR-010)
- [ ] T013 [P] [US2] Create `dashboard/tests/test_public.py` serializer tests proving public payloads round probabilities to whole percentages and include expected free fields (FR-007, FR-009)
- [ ] T014 [US2] Add premium redaction test in `dashboard/tests/test_public.py` asserting serialized payload JSON does not contain forbidden keys: `monte_carlo`, `odm`, `blend`, `features`, `pred_state`, `history`, `chart_history`, `commentary`, `ml_prob`, `mc_prob`, `ml_weight`, `mc_weight` (SC-003)
- [ ] T015 [US2] Add no-state/missing-state serializer test proving active predictions with absent JSON state return safe "awaiting model" data rather than crashing (edge case)
- [ ] T016 [US2] Add IPL candidate filtering test proving non-IPL CREX live-score candidates are excluded from `/api/public/ipl-today` service results (FR-019, SC-009)

**Checkpoint**: Redaction and insight behavior covered before public exposure.

---

## Phase 4: Public Lite API (MVP P1)

**Goal**: Add unauthenticated JSON endpoints for public pages and distribution surfaces.

**Independent Test**: Call `/api/public/matches`, `/api/public/ipl-today`, and `/api/public/matches/{slug}` without Authorization. They return public-safe JSON and never leak premium fields.

- [ ] T017 [US2] Create `dashboard/app/routers/public.py` with `APIRouter(prefix="/api/public", tags=["Public"])`
- [ ] T018 [US2] Add `GET /api/public/matches` in `dashboard/app/routers/public.py` using `PublicMatchService.list_matches()` (FR-005)
- [ ] T019 [US2] Add `GET /api/public/ipl-today` in `dashboard/app/routers/public.py` using `PublicMatchService.list_ipl_today()` and IPL-only filtering (FR-005, FR-019)
- [ ] T020 [US2] Add `GET /api/public/matches/{slug}` in `dashboard/app/routers/public.py` using `PublicMatchService.get_match(slug)` and return 404 with `suggested_url` for unresolved slugs (FR-005)
- [ ] T021 [US2] Register public router in `dashboard/app/main.py` before the page router (FR-005)
- [ ] T022 [US2] Add endpoint tests in `dashboard/tests/test_public.py` proving all three public API routes work without auth and do not require `Authorization` headers (SC-002)
- [ ] T023 [US2] Add endpoint redaction test for `/api/public/matches` and `/api/public/matches/{slug}` using realistic sample state with premium fields present internally (SC-003)

**Checkpoint**: Public API MVP works and is safe.

---

## Phase 5: Public Page Routes (MVP P1)

**Goal**: Add public, indexable page routes for acquisition traffic.

**Independent Test**: Open `/`, `/ipl-prediction-today`, and `/match/{slug}` in a logged-out browser or `Invoke-WebRequest`; responses render HTML without redirecting to login/dashboard.

- [ ] T024 [US1] Update `dashboard/app/routers/pages.py`: replace `/` redirect with `public.html` render using `PublicMatchService` (FR-001)
- [ ] T025 [US1] Add `/ipl-prediction-today` route to `dashboard/app/routers/pages.py`, rendering `ipl_today.html` with IPL public summaries (FR-002)
- [ ] T026 [US1] Add `/match/{slug}` route to `dashboard/app/routers/pages.py`, rendering `match_public.html` for resolved slugs and a useful public 404/fallback for unresolved slugs (FR-003)
- [ ] T027 [US1] Add `/prediction/{league}/{teams}` alias route to `dashboard/app/routers/pages.py` using the same service/detail template (FR-004)
- [ ] T028 [US1] Pass SEO metadata from routes into templates: title, meta description, canonical path, Open Graph title/description, and noindex flag for unresolved/empty detail pages (FR-011, SC-010)
- [ ] T029 [US1] Add page route tests in `dashboard/tests/test_public.py` proving `/`, `/ipl-prediction-today`, and `/match/{slug}` render without auth and are not redirects to `/dashboard` or `/login` (SC-001)

**Checkpoint**: Public routes exist and return server-rendered HTML.

---

## Phase 6: Public Templates (MVP P1)

**Goal**: Make the public pages useful as first-viewport acquisition surfaces.

- [ ] T030 [US1] Create `dashboard/templates/public.html` extending `base.html`; show CrickenZen public value, live/today match cards, and CTAs to `/ipl-prediction-today` and `/login` (FR-001, FR-012)
- [ ] T031 [US1] Create `dashboard/templates/ipl_today.html` extending `base.html`; show IPL match cards with title, status, score, rounded probability/awaiting-model state, insight, and detail links (FR-002, FR-013)
- [ ] T032 [US1] Create `dashboard/templates/match_public.html` extending `base.html`; show match title, score, win probability, projection/chase label, last 5 swings, one insight, locked premium preview, and dashboard CTA (FR-003, FR-012)
- [ ] T033 [US5] Add public premium-preview UI sections in `match_public.html`: Monte Carlo, ODM, full timeline, commentary, alerts, all shown as locked/upgrade preview rather than real premium values (FR-020)
- [ ] T034 [US1] Ensure public templates render a useful empty state when no active predictions/candidates exist, with links back to `/ipl-prediction-today` and `/login` (edge case)
- [ ] T035 [US1] Verify mobile first viewport manually or via simple screenshot/browser check: match title, score/status, probability/awaiting-model, insight, and CTA visible at mobile width (SC-005)

**Checkpoint**: Public acquisition pages are usable and visually aligned with the existing dashboard.

---

## Phase 7: Optional Public Client Enhancement

**Goal**: Keep public pages fresh without making JavaScript required.

- [ ] T036 [P] [US1] Add optional client-side polling helper for public pages using `/api/public/matches` and `/api/public/matches/{slug}`; keep server-rendered initial content intact (FR-013)
- [ ] T037 [P] [US1] Add a small test or manual checklist confirming public pages remain useful when JavaScript is disabled (FR-013)

**Checkpoint**: Public pages can update live, but are not JS-dependent.

---

## Phase 8: Telegram Dry-Run Distribution (P2)

**Goal**: Convert public payloads into Telegram-ready event messages without enabling live posting yet.

- [ ] T038 [US4] Create `dashboard/app/telegram_distribution.py` with event types `match_live`, `milestone`, `swing`, `final_pressure`, and `match_finished` (FR-017)
- [ ] T039 [US4] Implement in-memory dedupe key generation: `match_slug:event_type:event_key` to avoid repeated milestone/swing messages (FR-018)
- [ ] T040 [US4] Implement Telegram-ready message formatting from `PublicMatchDetail`, reusing existing `src/bbl_pipeline/telegram` formatter/client only if it does not require credentials in tests (FR-017)
- [ ] T041 [US4] Add `dashboard/tests/test_telegram_distribution.py` covering match start, 5-over milestone, probability swing threshold, final pressure, completion, and duplicate suppression (SC-008)

**Checkpoint**: Telegram distribution logic is testable in dry-run mode.

---

## Phase 9: Entitlement Boundary Prep (P2)

**Goal**: Prepare the dashboard for monetization without blocking public launch.

- [ ] T042 [US5] Create `dashboard/app/entitlements.py` with capability policy for `free`, `monthly`, `yearly`, and `admin` plans; keep public API always on free/redacted policy (FR-020)
- [ ] T043 [US5] Add tests for entitlement policy: free cannot access MC/ODM/alerts, monthly/yearly/admin can, public policy always redacts premium data (FR-020)
- [ ] T044 [US5] Add dashboard UI upgrade placeholders for free users only if current authenticated dashboard can read `user.plan` without breaking existing paid/admin behavior (FR-020)

**Checkpoint**: Monetization boundary is explicit; Stripe/payment can be a separate feature.

---

## Final Phase: Regression & Launch Checks

- [ ] T045 Run public-focused tests: `cd dashboard; .venv\Scripts\python.exe -m pytest tests/test_public.py tests/test_public_insights.py -q`
- [ ] T046 Run Telegram tests if Phase 8 was implemented: `cd dashboard; .venv\Scripts\python.exe -m pytest tests/test_telegram_distribution.py -q`
- [ ] T047 Run full dashboard suite: `cd dashboard; .venv\Scripts\python.exe -m pytest tests/ -q` (SC-006)
- [ ] T048 Start local server and smoke test: `/`, `/ipl-prediction-today`, `/api/public/matches`, `/api/public/ipl-today`, `/dashboard`, `/auth/login`
- [ ] T049 Run redaction command from `plan.md` against `/api/public/matches` and at least one `/api/public/matches/{slug}` response (SC-003)
- [ ] T050 Review SEO metadata in rendered HTML for valid public pages and noindex behavior for unresolved match detail pages (SC-010)

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1  → Baseline only
Phase 2  → Blocks every public route/API
Phase 3  → Blocks Phase 4 public API exposure
Phase 4  → Public API MVP
Phase 5  → Depends on Phase 2 service; can start after Phase 4 service shape is stable
Phase 6  → Depends on Phase 5 route contexts
Phase 7  → Depends on Phase 4 API + Phase 6 templates
Phase 8  → Depends on Phase 2 public payload shape
Phase 9  → Can run after MVP if monetization gating is prioritized
Final    → Depends on implemented phases
```

### MVP Scope

MVP includes:

- Phase 1
- Phase 2
- Phase 3
- Phase 4
- Phase 5
- Phase 6
- Final tasks T045, T047, T048, T049, T050

MVP excludes:

- Phase 7 public polling
- Phase 8 Telegram dry-run distribution
- Phase 9 entitlement prep

### Parallel Opportunities

- T002-T004 can run in parallel after T001.
- T012 and T013 can run in parallel after T005-T010.
- T024-T028 can be implemented alongside T030-T032 once template context shape is agreed, but route tests should come after both exist.
- Phase 8 Telegram work can run in parallel with template polish after Phase 2 stabilizes.
- Phase 9 entitlement prep can run in parallel with Telegram after public redaction is complete.

---

## Task Count

- **Total tasks**: 50
- **MVP tasks**: 39
- **P2 tasks**: 11
- **Tasks by story**:
  - US1 public pages: 18
  - US2 public API/serializer: 19
  - US3 insight copy: 2 direct tasks plus serializer coverage
  - US4 Telegram: 4
  - US5 entitlement/upgrade: 5
  - Baseline/final verification: 9

---

## Suggested First Commit

The first implementation commit should contain only:

- `dashboard/app/public.py`
- `dashboard/tests/test_public_insights.py`
- serializer/redaction tests in `dashboard/tests/test_public.py`

Do not add public routes in the same commit as the first serializer. The redaction boundary should be reviewable by itself before any unauthenticated endpoint exists.
