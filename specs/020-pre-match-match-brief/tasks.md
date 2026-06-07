# Tasks: Pre-Match Match Brief (020-pre-match-match-brief)

**Input**: `specs/020-pre-match-match-brief/plan.md`, `specs/020-pre-match-match-brief/spec.md`  
**Feature Branch**: `020-pre-match-match-brief`  
**Date**: 2026-06-07

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files or is pure verification
- **[Story]**: User story from `spec.md`
- Exact file paths are included wherever implementation is required

---

## Phase 1: Baseline & Source Verification

**Purpose**: Confirm the current public fixture-discovery path and venue priors can support a pre-match product without changing live semantics first.

- [ ] T001 Verify how upcoming fixtures currently flow through `dashboard/app/public.py`, especially `_candidate_summary()`, `list_matches()`, and `list_ipl_today()` (FR-002, FR-010)
- [ ] T002 [P] Inspect current public page routing in `dashboard/app/routers/pages.py` and identify where the pre-match list and detail routes should live (FR-001, FR-011)
- [ ] T003 [P] Inspect venue-prior sources in `src/bbl_pipeline/features/store.py` and record the exact fields available for V1 venue bias and pressure-zone logic (FR-005, FR-009)
- [ ] T004 [P] Decide and document the initial factor support matrix: probability, projected first innings, venue bias, toss sensitivity, dew, rain, pressure zones, reasons (FR-007, FR-014)

**Checkpoint**: V1 source boundaries and fallback behavior are clear.

---

## Phase 2: Pre-Match Serializer & Service Boundary (Blocks UI)

**Purpose**: Create a safe pre-match data contract that stays separate from live payloads.

- [ ] T005 [US1] Create `dashboard/app/prematch.py` with public dataclasses or typed objects for `PrematchBriefSummary`, `PrematchBriefDetail`, `ConditionsStatus`, `PressureZoneBand`, and `PrematchReason` (FR-010)
- [ ] T006 [US1] Add safe slug and fixture-title helpers in `dashboard/app/prematch.py` for upcoming pre-match briefs, reusing current patterns where practical (FR-001, FR-011)
- [ ] T007 [US2] Add venue-prior lookup helpers in `dashboard/app/prematch.py` using fields from `src/bbl_pipeline/features/store.py` (FR-005)
- [ ] T008 [US2] Add toss-sensitivity helpers in `dashboard/app/prematch.py` that return documented low/medium/high leverage labels with supporting copy (FR-006)
- [ ] T009 [US2] Add pressure-zone generation helpers in `dashboard/app/prematch.py` for below-par, par, and above-par scoring bands (FR-009)
- [ ] T010 [US2] Add conditions-status helpers in `dashboard/app/prematch.py` for dew and rain sections with `ready`, `partial`, or `not_ready` behavior (FR-007)
- [ ] T011 [US3] Add deterministic reason-generation helpers in `dashboard/app/prematch.py` that produce 3 to 5 concise reasons from structured factors (FR-008)
- [ ] T012 [US1] Add `PrematchService` to `dashboard/app/prematch.py` that lists eligible upcoming fixtures and resolves one full brief by slug without leaking raw internal state (FR-001, FR-010, FR-011)

**Checkpoint**: A standalone pre-match service boundary exists.

---

## Phase 3: Serializer and Factor Tests (Blocks Route Exposure)

**Purpose**: Lock the pre-match contract and factor logic before exposing pages or API routes.

- [ ] T013 [P] [US2] Create `dashboard/tests/test_prematch.py` coverage for venue-prior lookups, toss-sensitivity labels, pressure-zone generation, and conditions-status fallbacks (FR-005, FR-006, FR-007, FR-009)
- [ ] T014 [P] [US3] Add reason-generation tests in `dashboard/tests/test_prematch.py` proving briefs produce 3 to 5 concise structured reasons without generic filler (FR-008)
- [ ] T015 [US1] Add no-upcoming-fixture tests in `dashboard/tests/test_prematch.py` proving the service returns a stable empty state rather than crashing (edge case)
- [ ] T016 [US1] Add missing-probability and missing-venue tests in `dashboard/tests/test_prematch.py` proving sections degrade honestly to `not_ready` where necessary (FR-003, FR-005, FR-007)

**Checkpoint**: The pre-match contract is covered before any page depends on it.

---

## Phase 4: Pre-Match Page Context Builder (MVP P1)

**Goal**: Build a server-rendered pre-match page context separate from raw serializers.

**Independent Test**: Build page context for an upcoming fixture and verify it contains headline cards, conditions sections, pressure zones, and reasons.

- [ ] T017 [US1] Create `dashboard/app/prematch_page.py` with a `build_prematch_page_context(slug: str | None = None, league: str = "ipl")` entry point (FR-001, FR-003)
- [ ] T018 [US1] In `dashboard/app/prematch_page.py`, normalize ready, partial, and not-ready sections for each factor block (FR-007, FR-012)
- [ ] T019 [US2] Add display shaping in `dashboard/app/prematch_page.py` for venue cards, toss cards, conditions cards, and pressure-zone bands (FR-005, FR-006, FR-007, FR-009)
- [ ] T020 [US3] Add brief methodology / framing copy in `dashboard/app/prematch_page.py` that explains how pre-match intelligence differs from live prediction (FR-013, FR-014)

**Checkpoint**: Templates can render from a stable page context rather than raw service objects.

---

## Phase 5: Public Routes (MVP P1)

**Goal**: Add public discovery and detail routes for pre-match briefs.

**Independent Test**: Logged-out users can open the list page and one detail page without auth.

- [ ] T021 [US1] Update `dashboard/app/routers/pages.py` to add `GET /ipl-match-brief-today` using the pre-match list context (FR-001, FR-011)
- [ ] T022 [US1] Update `dashboard/app/routers/pages.py` to add `GET /pre-match/{slug}` using `build_prematch_page_context` (FR-001)
- [ ] T023 [US1] Add SEO metadata for both pre-match routes with clear “pre-match” or “before toss” framing (FR-013)
- [ ] T024 [US1] Add stable empty-state behavior for no-upcoming-fixture cases instead of redirecting to live pages or login (FR-001, FR-012)

**Checkpoint**: Pre-match routes exist as public product surfaces.

---

## Phase 6: Pre-Match Templates (MVP P1)

**Goal**: Ship a real before-the-toss UI, not just a raw data dump.

**Independent Test**: The list page clearly shows upcoming briefs, and the detail page clearly communicates win probability, projected score, venue bias, toss sensitivity, conditions, pressure zones, and reasons.

- [ ] T025 [US1] Create `dashboard/templates/ipl_match_brief_today.html` extending `dashboard/templates/base.html` for the upcoming-brief list page (FR-001, FR-011)
- [ ] T026 [US1] Create `dashboard/templates/prematch_brief.html` extending `dashboard/templates/base.html` for the full pre-match brief detail page (FR-001, FR-003)
- [ ] T027 [US1] Add headline factor cards in `dashboard/templates/prematch_brief.html` for win probability, projected first innings, toss sensitivity, and venue profile (FR-003, FR-004, FR-005, FR-006)
- [ ] T028 [US2] Add conditions sections for dew and rain in `dashboard/templates/prematch_brief.html` with explicit ready/not-ready labeling (FR-007)
- [ ] T029 [US2] Add pressure-zone UI in `dashboard/templates/prematch_brief.html` for below-par, par, and above-par scoring bands (FR-009)
- [ ] T030 [US3] Add a 3 to 5 reason stack in `dashboard/templates/prematch_brief.html` with concise supporting text (FR-008)
- [ ] T031 [US1] Add framing copy that clearly distinguishes this page from live match pages and proof pages (FR-013)
- [ ] T032 [US1] Add empty and partial-state render blocks in both templates for no-fixture and missing-factor scenarios (FR-007, FR-012)

**Checkpoint**: The pre-match product surface is understandable and visually distinct.

---

## Phase 7: Entry Points from Existing Public Surfaces (P2)

**Goal**: Make the new pre-match surface discoverable from current public traffic surfaces.

**Independent Test**: A visitor can move from homepage or today page into the upcoming pre-match brief without guessing.

- [ ] T033 [US4] Update `dashboard/templates/public.html` to add a pre-match CTA block when upcoming briefs exist or to advertise the feature generally (FR-011)
- [ ] T034 [US4] Update `dashboard/templates/ipl_today.html` to clearly distinguish live cards from upcoming brief links (FR-011, FR-013)
- [ ] T035 [US4] Review whether `dashboard/templates/match_public.html` should link back to a pre-match brief only when the fixture is still upcoming; do not confuse live pages with brief pages (FR-013)

**Checkpoint**: Discovery from public surfaces is in place without mixing live and upcoming intent.

---

## Phase 8: Page and Route Tests (Blocks Sign-Off)

**Purpose**: Protect the UX and route behavior before moving to later phases.

- [ ] T036 [P] [US1] Create `dashboard/tests/test_prematch_page.py` covering ready-state detail-page rendering without auth (FR-012)
- [ ] T037 [P] [US1] Add no-upcoming-fixture rendering test in `dashboard/tests/test_prematch_page.py` for list and detail fallbacks (FR-012)
- [ ] T038 [P] [US2] Add partial-conditions rendering test proving dew/rain sections surface `not_ready` honestly (FR-007)
- [ ] T039 [P] [US3] Add reason-stack rendering tests proving the brief shows 3 to 5 reasons with the expected section headings (FR-008)
- [ ] T040 [P] [US4] Add CTA/link tests confirming homepage and IPL-today pages expose pre-match discovery paths (FR-011)

**Checkpoint**: Pre-match UX behavior is locked by focused tests.

---

## Final Phase: Regression & Launch Checks

- [ ] T041 Run serializer/service tests: `pytest dashboard/tests/test_prematch.py -v`
- [ ] T042 Run page/context tests: `pytest dashboard/tests/test_prematch_page.py -v`
- [ ] T043 Run relevant dashboard public-page regression if needed: `cd dashboard; .venv\Scripts\python.exe -m pytest tests/ -q`
- [ ] T044 Start the dashboard locally and manually smoke test `/ipl-match-brief-today`, `/pre-match/{slug}`, `/ipl-prediction-today`, and `/` while logged out
- [ ] T045 Verify mobile-width and desktop-width rendering for the pre-match detail page, ensuring headline cards and reasons remain readable

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 -> Baseline/source verification only
Phase 2 -> Blocks all page and route work
Phase 3 -> Blocks route exposure
Phase 4 -> Depends on Phase 2 service boundary
Phase 5 -> Depends on Phase 4 page context
Phase 6 -> Depends on Phase 5 routes and Phase 4 context
Phase 7 -> Depends on Phase 6 surface shape
Phase 8 -> Depends on Phases 4-7
Final   -> Depends on implemented phases
```

### MVP Scope

MVP includes:

- Phase 1
- Phase 2
- Phase 3
- Phase 4
- Phase 5
- Phase 6
- Phase 8
- Final tasks T041-T045

MVP excludes:

- optional deeper entry-point polish in T035 if it risks blurring live/upcoming messaging

### Parallel Opportunities

- T002-T004 can run in parallel after T001.
- T013-T016 can run in parallel once `dashboard/app/prematch.py` exists.
- T036-T040 can be written in parallel after route and template shape stabilize.

---

## Task Count

- **Total tasks**: 45
- **MVP tasks**: 41
- **Tasks by story**:
  - US1 pre-match overview and routing: 21
  - US2 venue/toss/conditions: 11
  - US3 reason stack: 5
  - US4 discovery and CTAs: 5
  - regression and launch checks: 5

---

## Suggested First Commit

The first implementation commit should contain only:

- `dashboard/app/prematch.py`
- `dashboard/tests/test_prematch.py`

Do not start with page polish. Lock the pre-match data contract, factor logic, and fallback behavior first, then add routes and templates once the product semantics are stable.
