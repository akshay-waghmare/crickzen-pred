# Tasks: Dashboard Proof Page (018-dashboard-proof-page)

**Input**: `specs/018-dashboard-proof-page/plan.md`, `specs/018-dashboard-proof-page/spec.md`  
**Feature Branch**: `018-dashboard-proof-page`  
**Date**: 2026-06-07

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files or is pure verification
- **[Story]**: User story from `spec.md`
- Exact file paths are included wherever implementation is required

---

## Phase 1: Baseline & Proof Contract Verification

**Purpose**: Confirm the implemented proof backend is ready to drive the page without changing proof semantics.

- [ ] T001 Verify current proof endpoints return the expected top-level shapes from `dashboard/app/routers/proof.py` and `dashboard/app/proof_metrics.py` (FR-002)
- [ ] T002 [P] Run proof backend tests before page work: `pytest tests/unit/analysis/test_proof_metrics.py -q`
- [ ] T003 [P] Run dashboard proof contract tests: `pytest dashboard/tests/test_proof_metrics.py -v --noconftest`
- [ ] T004 [P] Run `python scripts/build_dashboard_metrics_snapshot.py --league ipl --window all_available` and confirm latest artifacts exist under `data/dashboard_metrics/latest/` (FR-013)
- [ ] T005 Inspect current public page routes in `dashboard/app/routers/pages.py` and templates in `dashboard/templates/` to confirm where proof CTAs should be added (FR-010)

**Checkpoint**: The existing proof foundation is validated and the UI phase can build on stable artifacts.

---

## Phase 2: Proof Page Context Service (Blocks Template Work)

**Purpose**: Centralize proof-page display shaping before the route and template are added.

- [ ] T006 [US1] Create `dashboard/app/proof_page.py` with a `build_proof_page_context(league: str = "ipl")` entry point (FR-001, FR-002)
- [ ] T007 [US1] In `dashboard/app/proof_page.py`, load summary, segments, ledger, and manifest through `dashboard/app/proof_metrics.py` rather than internal HTTP calls (FR-002)
- [ ] T008 [US1] Add top-level page-status derivation in `dashboard/app/proof_page.py` for `ready`, `stale`, `partial`, and `not_ready` states (FR-004, FR-011)
- [ ] T009 [US2] Add segment grouping helpers in `dashboard/app/proof_page.py` that split rows into innings and phase display groups with stable ordering and sample counts (FR-005)
- [ ] T010 [US2] Add ledger formatting helpers in `dashboard/app/proof_page.py` that trim or order recent rows for V1 display without changing proof semantics (FR-006)
- [ ] T011 [US3] Add plain-English metric definitions, methodology copy, and caveat strings in `dashboard/app/proof_page.py` so templates stay thin (FR-007, FR-008)
- [ ] T012 [US1] Expose proof freshness label, evaluation window label, and supportive summary metadata in the page context (FR-003, FR-004)

**Checkpoint**: One reusable page-context object exists for all proof rendering states.

---

## Phase 3: Proof Page Route (MVP P1)

**Goal**: Add a public route that renders the proof page without authentication.

**Independent Test**: Visit `/proof` while logged out and confirm the page returns HTML with proof summary content.

- [ ] T013 [US1] Update `dashboard/app/routers/pages.py` to import `build_proof_page_context` from `dashboard/app/proof_page.py` (FR-001)
- [ ] T014 [US1] Add `GET /proof` to `dashboard/app/routers/pages.py` and render `dashboard/templates/proof.html` using the proof-page context (FR-001, FR-003)
- [ ] T015 [US1] Add proof-specific SEO metadata in the `/proof` route: title, description, canonical path, and noindex behavior only if the route is intentionally hidden later (FR-001)
- [ ] T016 [US1] Keep `/proof` public and stable under ready, partial, stale, and not-ready states; do not redirect to `/login` or `/dashboard` (FR-001, FR-004)

**Checkpoint**: `/proof` exists as a public trust route.

---

## Phase 4: Proof Template (MVP P1)

**Goal**: Ship the trust page UI using the existing dashboard visual language.

**Independent Test**: `/proof` renders a complete page with summary cards first, followed by methodology, segments, and ledger.

- [ ] T017 [US1] Create `dashboard/templates/proof.html` extending `dashboard/templates/base.html` (FR-001, FR-009)
- [ ] T018 [US1] Add a hero/status section to `dashboard/templates/proof.html` showing the trust framing, freshness badge, and evaluation window (FR-003, FR-004)
- [ ] T019 [US1] Add summary cards for Brier, ECE, accuracy, and sample count with plain-English supporting text (FR-003, FR-007, FR-008)
- [ ] T020 [US3] Add a short “How to read this” or methodology section in `dashboard/templates/proof.html` that distinguishes calibration from accuracy (FR-007, FR-008)
- [ ] T021 [US2] Add innings and phase segment panels in `dashboard/templates/proof.html` using the grouped segment context from `dashboard/app/proof_page.py` (FR-005)
- [ ] T022 [US2] Add a recent proof ledger table or card list in `dashboard/templates/proof.html` with match, predicted side, probability/confidence, result, and timestamp columns (FR-006)
- [ ] T023 [US1] Add not-ready, stale, and partial-state rendering blocks in `dashboard/templates/proof.html` so the layout stays honest and useful under missing data (FR-004, FR-011)
- [ ] T024 [US1] Add trust-to-product CTAs in `dashboard/templates/proof.html` linking back to `/`, `/ipl-prediction-today`, and `/login` where appropriate (FR-010)

**Checkpoint**: The proof page is usable and trust-oriented on its own.

---

## Phase 5: Trust Entry Points from Public Surfaces (MVP P2)

**Goal**: Make the proof page discoverable from existing public pages.

**Independent Test**: Logged-out visitors can see a proof CTA on `/` and at least one public match surface.

- [ ] T025 [US4] Update `dashboard/templates/public.html` to add a visible CTA to `/proof` in the hero or supporting trust area (FR-010)
- [ ] T026 [US4] Update `dashboard/templates/match_public.html` to add a visible proof CTA near the model-detail or trust area (FR-010)
- [ ] T027 [US4] Review `dashboard/templates/partials/nav.html` and add a `/proof` nav item only if it fits the current public navigation cleanly without crowding the layout (FR-010)

**Checkpoint**: Trust is now discoverable from public surfaces.

---

## Phase 6: Proof Page Tests (Blocks Sign-Off)

**Purpose**: Lock in rendering behavior before broader dashboard polish continues.

- [ ] T028 [P] [US1] Create `dashboard/tests/test_proof_page.py` covering ready-state `/proof` rendering without auth (FR-012)
- [ ] T029 [P] [US1] Add stale-state test in `dashboard/tests/test_proof_page.py` verifying freshness/stale copy is visible when the snapshot is old (FR-004)
- [ ] T030 [P] [US1] Add not-ready test in `dashboard/tests/test_proof_page.py` verifying the page renders gracefully when proof artifacts are missing (FR-004, FR-011)
- [ ] T031 [P] [US1] Add partial-state test in `dashboard/tests/test_proof_page.py` where probability metrics are ready but accuracy or ledger is not ready (FR-004, FR-011)
- [ ] T032 [P] [US2] Add segment-rendering test in `dashboard/tests/test_proof_page.py` verifying innings and phase headings render from grouped segment data (FR-005)
- [ ] T033 [P] [US2] Add ledger-rendering test in `dashboard/tests/test_proof_page.py` verifying deterministic recent proof rows appear with expected columns (FR-006)
- [ ] T034 [P] [US4] Add CTA tests in `dashboard/tests/test_proof_page.py` or existing public-page tests verifying `/` and public match pages contain proof links (FR-010)

**Checkpoint**: Proof-page rendering behavior is protected by focused tests.

---

## Final Phase: Regression & Launch Checks

- [ ] T035 Run proof-page tests: `pytest dashboard/tests/test_proof_page.py -v`
- [ ] T036 Run proof loader/contract regression: `pytest dashboard/tests/test_proof_metrics.py -v --noconftest`
- [ ] T037 Run proof builder regression: `pytest tests/unit/analysis/test_proof_metrics.py -q`
- [ ] T038 Start the dashboard locally and manually smoke test `/proof`, `/`, `/ipl-prediction-today`, and one `/match/{slug}` page while logged out
- [ ] T039 Rebuild proof artifacts with `python scripts/build_dashboard_metrics_snapshot.py --league ipl --window all_available` before final visual verification if needed (FR-013)
- [ ] T040 Verify the proof page on mobile-width and desktop-width layouts, ensuring summary cards, methodology, and ledger remain readable (FR-009)

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 -> Baseline verification only
Phase 2 -> Blocks route and template work
Phase 3 -> Depends on Phase 2 context service
Phase 4 -> Depends on Phase 3 route plus Phase 2 context
Phase 5 -> Depends on Phase 4 proof route existence
Phase 6 -> Depends on Phases 2-5
Final   -> Depends on implemented phases
```

### MVP Scope

MVP includes:

- Phase 1
- Phase 2
- Phase 3
- Phase 4
- Phase 6
- Final tasks T035-T040

MVP excludes:

- Optional nav addition in T027 if it clashes with existing layout

### Parallel Opportunities

- T002-T005 can run in parallel after T001.
- T009-T012 can run in parallel once `dashboard/app/proof_page.py` exists.
- T028-T034 can be written in parallel after the route and template shape stabilize.

---

## Task Count

- **Total tasks**: 40
- **MVP tasks**: 37
- **Tasks by story**:
  - US1 public proof overview: 18
  - US2 segments and ledger: 8
  - US3 methodology and caveats: 3
  - US4 public entry points: 4
  - baseline/final verification: 7

---

## Suggested First Commit

The first implementation commit should contain only:

- `dashboard/app/proof_page.py`
- `dashboard/tests/test_proof_page.py`
- minimal `dashboard/app/routers/pages.py` wiring for `/proof` if needed to exercise tests

Do not mix large CTA/template polish into the first proof commit. Lock the proof-page context and rendering states first, then polish the public entry points in a follow-up commit.
