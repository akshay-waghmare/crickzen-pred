# Implementation Tasks: Scraper Logging Recovery

**Branch**: 001-scraper-logging  
**Spec Reference**: specs/001-scraper-logging/spec.md  
**Plan Reference**: specs/001-scraper-logging/plan.md

## Phase 1 – Setup
**Goal**: Prepare dependencies and repository hygiene to support structured logging work.
**Independent Test Criteria**: Installing Python dependencies and running `python -m src.crex_main_url --help` succeeds without warnings about missing packages or unexpected artifact directories.

- [X] T001 Update structlog dependency pins in requirements.txt and requirements-dev.txt
- [X] T002 Add logs/ and artifacts/ paths to .gitignore to prevent committing diagnostic outputs

## Phase 2 – Foundational Infrastructure
**Goal**: Establish reusable logging and diagnostics primitives required by all user stories.
**Independent Test Criteria**: Importing `src.logging.adapters` initializes JSON logging without raising exceptions.

- [X] T003 Create src/logging/__init__.py to expose logging package defaults
- [X] T004 Implement JSON logger configuration with structlog in src/logging/adapters.py
- [X] T005 Add diagnostic artifact helper utilities in src/logging/diagnostics.py
- [X] T006 Wire structured logger initialization into scraper bootstrap in src/crex_main_url.py

## Phase 3 – User Story 1 (P1) Restore Scraper Observability
**Goal**: Emit structured JSON logs at each critical scraping step.
**Independent Test Criteria**: Running `python -m src.crex_scraper --job sample` produces JSON logs containing navigation, DOM, extraction, validation, persistence, and external call events with correlation IDs.

- [X] T007 [US1] Instrument navigation and DOM readiness logging in src/crex_main_url.py
- [X] T008 [US1] Emit validation outcome logs for each URL in src/crex_scraper.py
- [X] T009 [US1] Capture persistence and external API log context in src/cricket_data_service.py
- [X] T010 [US1] Add unit coverage for logging adapters in tests/unit/test_logging_adapters.py
- [X] T011 [US1] Create integration flow asserting log schema in tests/integration/test_scraper_logging_flow.py

## Phase 4 – User Story 2 (P1) Detect DOM Drift Early
**Goal**: Surface selector failures with actionable warnings and captured context.
**Independent Test Criteria**: Injecting a missing selector during a test run generates WARNING logs with selector path, page URL, and stored HTML snapshot reference.

- [X] T012 [US2] Log selector-miss warnings with remediation hint in src/crex_scraper.py
- [X] T013 [US2] Capture HTML snapshots and register artifact paths in src/logging/diagnostics.py
- [X] T014 [US2] Verify DOM drift logging and artifact capture in tests/unit/test_diagnostics.py

## Phase 5 – User Story 3 (P2) Measure Scraping Performance
**Goal**: Record per-stage timings and resource usage metrics for each scrape cycle.
**Independent Test Criteria**: Three consecutive scrape runs log total duration, per-stage timings, and resource advisories to meet SC-002.

- [X] T015 [US3] Track stage timing metrics throughout the scrape pipeline in src/crex_scraper.py
- [ ] T016 [US3] Emit resource utilization advisories in src/logging/diagnostics.py
- [ ] T017 [US3] Extend integration assertions for performance logs in tests/integration/test_scraper_logging_flow.py

## Phase 6 – User Story 4 (P2) Monitor Background Job Health
**Goal**: Provide lifecycle visibility and health summaries for long-running scraper jobs.
**Independent Test Criteria**: Starting, stopping, and faulting a job updates lifecycle logs and the health endpoint response in under one polling interval.

- [X] T018 [US4] Add correlation-aware lifecycle logging for background jobs in src/crex_main_url.py
- [X] T019 [US4] Implement scraper health endpoint logic in src/cricket_data_service.py
- [ ] T020 [US4] Cover health reporting via API tests in tests/integration/test_api.py

## Phase 7 – User Story 5 (P3) Diagnose Root Cause Rapidly
**Goal**: Enable debug mode to capture screenshots, HTML, and state dumps for outage triage.
**Independent Test Criteria**: Triggering a simulated exception in debug mode produces logs referencing stored artifacts, which are accessible within retention policy.

- [X] T021 [US5] Introduce debug mode configuration flags in src/config.py
- [ ] T022 [US5] Persist screenshots and state dumps using src/logging/diagnostics.py
- [ ] T023 [US5] Validate debug artifacts through targeted tests in tests/unit/test_diagnostics.py

## Phase 8 – Polish & Cross-Cutting Concerns
**Goal**: Finalize retention safeguards, documentation, and operational guidance.
**Independent Test Criteria**: Nightly cleanup script removes expired artifacts, and updated quickstart instructions guide operators through observability tooling.

- [X] T024 Configure retention cleanup routine for artifacts in src/logging/diagnostics.py
- [X] T025 Document logging workflow updates in docs/QUICKSTART.md

## Dependencies
1. Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8
2. T012–T014 depend on foundational diagnostics utilities (T005)
3. T015–T017 depend on structured logs from T007–T011
4. T018–T020 depend on correlation handling from T007 and infrastructure from T003–T006
5. T021–T023 require artifact capture plumbing from T013 and timing metrics from T015

## Parallel Execution Opportunities
- After Phase 2 completes, teams can pursue Phase 4 (US2) and Phase 5 (US3) concurrently.
- Phase 6 (US4) and Phase 7 (US5) can run in parallel once Phase 5 is delivered.
- Documentation polish (T025) may proceed alongside final testing in Phase 8.

## Implementation Strategy
1. **MVP Scope**: Deliver Phases 1–3 to restore core observability and unblock incident diagnostics.
2. **Incremental Delivery**: Add DOM drift detection (Phase 4) and performance metrics (Phase 5), then layer background health monitoring (Phase 6) and debug artifact capture (Phase 7).
3. **Testing Cadence**: Execute targeted pytest suites after each phase (`tests/unit`, `tests/integration`) and keep log snapshots for regression verification.
