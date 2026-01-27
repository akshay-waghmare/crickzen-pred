# Implementation Tasks: Telegram Prediction Ledger

**Feature**: [spec.md](spec.md) | [plan.md](plan.md) | **Generated**: 2026-01-27

## Task Organization

Tasks are organized by user story priority (P1, P2, P3) to enable independent, incremental delivery. Each user story represents a complete, testable feature increment.

**Legend**:
- `- [ ]` = Not started
- `[T###]` = Task ID (sequential)
- `[P]` = Parallelizable (can be done in parallel with other [P] tasks)
- `[US#]` = User Story number (maps to spec.md user stories)

---

## Phase 1: Setup & Infrastructure

**Goal**: Establish project foundation and shared infrastructure

### Setup Tasks

- [X] T001 Add dependencies to pyproject.toml (python-telegram-bot>=20.0, python-decouple>=3.8)
- [X] T002 Create src/bbl_pipeline/telegram/ module directory structure
- [X] T003 Create config/.env.example with Telegram configuration template
- [X] T004 Update .gitignore to ensure .env is excluded
- [X] T005 Create data/ directory for telegram_predictions.jsonl storage
- [X] T006 Create tests/telegram/ directory for test modules

**Test**: Run `pip install -e .` successfully, import telegram module without errors

---

## Phase 2: Foundational Components

**Goal**: Build core shared components used by all user stories

### Configuration & Bot Client

- [X] T007 [P] Implement config.py in src/bbl_pipeline/telegram/config.py (load env vars, validate token format)
- [X] T008 [P] Implement BotClient class in src/bbl_pipeline/telegram/bot_client.py (send_message method, error handling)
- [X] T009 [P] Implement append-only storage in src/bbl_pipeline/telegram/storage.py (append_record, read_records methods)
- [X] T010 Write unit tests for config.py in tests/telegram/test_config.py
- [X] T011 Write unit tests for bot_client.py in tests/telegram/test_bot_client.py (mock Telegram API)
- [X] T012 Write unit tests for storage.py in tests/telegram/test_storage.py

**Test**: Unit tests pass; can load config, send test message to Telegram, write/read storage file

---

## Phase 3: User Story 1 - Post Pre-Match Prediction (P1)

**Goal**: Enable users to post pre-match predictions to Telegram channel

**Story**: A user has completed a pre-match analysis using the model and wants to create a verifiable public record of their prediction before the match begins.

**Independent Test**: Create bot, display button, capture input in modal, format message, post to Telegram successfully

### Implementation Tasks

- [X] T013 [US1] Implement PreMatchPrediction dataclass in src/bbl_pipeline/telegram/models.py (SKIPPED - using dicts)
- [X] T014 [US1] Implement format_prematch_prediction function in src/bbl_pipeline/telegram/message_formatter.py
- [X] T015 [US1] Write unit tests for format_prematch_prediction in tests/telegram/test_message_formatter.py
- [X] T016 [US1] Create telegram_ledger_app.py skeleton in src/bbl_pipeline/app/telegram_ledger_app.py
- [X] T017 [US1] Implement pre-match prediction modal UI with @st.dialog in telegram_ledger_app.py
- [X] T018 [US1] Implement form validation for pre-match prediction modal (all required fields)
- [X] T019 [US1] Implement post_prematch_prediction function integrating bot_client + formatter + storage
- [X] T020 [US1] Add success/error feedback UI (st.success, st.error messages)
- [X] T021 [US1] Add edge calculation helper (model_edge = (1/odds - 1/(prob/100)) * 100)

**Integration Test**: Complete flow from button click → modal → Telegram post → storage write

### Testing Tasks

- [ ] T022 [US1] Manual test: Post pre-match prediction to test Telegram channel
- [ ] T023 [US1] Verify: Message appears in Telegram with correct format
- [ ] T024 [US1] Verify: Record written to telegram_predictions.jsonl with correct fields
- [ ] T025 [US1] Verify: Missing field validation prevents submission
- [ ] T026 [US1] Verify: Telegram API error shows user-friendly error message

**Story Complete When**: User can successfully post a pre-match prediction from Streamlit to Telegram, record is stored locally, all validations work

---

## Phase 4: User Story 2 - Post Match Start Context (P2)

**Goal**: Enable users to log match start conditions (toss info) as separate record

**Story**: When the match begins and the user starts their live predictor (e.g., CREX), they want to log the actual match conditions (toss winner, toss decision) as a separate immutable record.

**Independent Test**: Display second button, capture toss data in modal, post separate message to Telegram

### Implementation Tasks

- [X] T027 [P] [US2] Implement MatchStartRecord dataclass in src/bbl_pipeline/telegram/models.py (SKIPPED - using dicts)
- [X] T028 [P] [US2] Implement format_match_start function in src/bbl_pipeline/telegram/message_formatter.py
- [X] T029 [US2] Write unit tests for format_match_start in tests/telegram/test_message_formatter.py
- [X] T030 [US2] Implement match start modal UI with @st.dialog in telegram_ledger_app.py
- [X] T031 [US2] Implement form validation for match start modal (required fields, toss decision enum)
- [X] T032 [US2] Implement post_match_start function integrating bot_client + formatter + storage
- [X] T033 [US2] Add success/error feedback UI for match start posting

**Integration Test**: Complete flow from "Post Match Start Info" button → modal → Telegram post → storage write

### Testing Tasks

- [ ] T034 [US2] Manual test: Post match start info to test Telegram channel
- [ ] T035 [US2] Verify: Separate message appears in Telegram with toss details
- [ ] T036 [US2] Verify: Match start record written to storage with post_type="match_start"
- [ ] T037 [US2] Verify: Can post match start without prior pre-match prediction (independent)

**Story Complete When**: User can post match start info independently, message formatted correctly, stored with proper post_type

---

## Phase 5: User Story 3 - Post Match Result (P3)

**Goal**: Enable users to post final match outcome and prediction correctness

**Story**: After the match concludes, the user wants to post the final result and document whether their model prediction was correct.

**Independent Test**: Display third button, capture winner, calculate correctness, post result message

### Implementation Tasks

- [X] T038 [P] [US3] Implement ResultRecord dataclass in src/bbl_pipeline/telegram/models.py (SKIPPED - using dicts)
- [X] T039 [P] [US3] Implement format_match_result function in src/bbl_pipeline/telegram/message_formatter.py
- [X] T040 [US3] Write unit tests for format_match_result in tests/telegram/test_message_formatter.py
- [X] T041 [US3] Implement match result modal UI with @st.dialog in telegram_ledger_app.py
- [X] T042 [US3] Implement lookup_original_prediction helper to find pre-match prediction by match_id
- [X] T043 [US3] Implement calculate_correctness logic (BACK: winner==selected, LAY: winner!=selected)
- [X] T044 [US3] Implement post_match_result function integrating lookup + bot_client + formatter + storage
- [X] T045 [US3] Add success/error feedback UI for result posting

**Integration Test**: Complete flow from "Post Match Result" → lookup prediction → calculate correctness → post to Telegram

### Testing Tasks

- [ ] T046 [US3] Manual test: Post match result after posting pre-match prediction
- [ ] T047 [US3] Verify: Result message shows correct/incorrect based on BACK selection
- [ ] T048 [US3] Verify: Result message shows correct/incorrect based on LAY selection
- [ ] T049 [US3] Verify: Can post result without prior prediction (graceful handling)
- [ ] T050 [US3] Verify: Result record written to storage with model_call_correct boolean

**Story Complete When**: User can post match results, correctness calculated properly for BACK/LAY, all three posting types work end-to-end

---

## Phase 6: Polish & Cross-Cutting Concerns

**Goal**: Enhance UX, documentation, and production readiness

### UX Enhancements

- [X] T051 Add spinner with st.spinner("Posting to Telegram...") during API calls
- [X] T052 Add confirmation preview before posting (show formatted message in modal before submit)
- [X] T053 Add league selector dropdown with all supported leagues (BBL, SA20, ILT20, WPL, SSM, T20I, etc.)
- [X] T054 Add input placeholders and help text for all form fields
- [X] T055 Implement HTML escaping for user input in message formatter (prevent injection)

### Error Handling & Logging

- [ ] T056 Add structured logging with structlog for all Telegram API calls
- [ ] T057 Add retry button for failed posts (show "Retry" button on error)
- [X] T058 Implement specific error messages for all Telegram error types (NetworkError, Unauthorized, BadRequest)
- [ ] T059 Add startup validation check (verify bot token format, test Telegram connection)

### Documentation & Setup

- [X] T060 Create comprehensive docstrings for all public functions and classes
- [X] T061 Add type hints to all function signatures
- [ ] T062 Update project README.md with Telegram Ledger feature section
- [ ] T063 Create video/GIF walkthrough of posting workflow for documentation

### Integration

- [ ] T064 Add link to telegram_ledger_app.py from main live_streamlit_app.py (navigation)
- [ ] T065 Test integration with existing Streamlit app navigation structure
- [ ] T066 Verify no conflicts with existing app state management

---

## Dependencies & Execution Order

### Story Completion Order

1. **Phase 1-2 (Setup & Foundational)**: MUST complete before any user stories
2. **User Story 1 (P1)**: Can start immediately after Phase 2
3. **User Story 2 (P2)**: Can start in parallel with US1 (independent modals)
4. **User Story 3 (P3)**: Can start in parallel with US1/US2 (independent modal)
5. **Phase 6 (Polish)**: After all user stories complete

### Parallel Execution Opportunities

**Phase 2 - Foundational Components** (T007-T009 parallelizable):
- T007 (config.py) ← Independent
- T008 (bot_client.py) ← Depends on T007
- T009 (storage.py) ← Independent

**User Story Implementation** (T027-T028, T038-T039 parallelizable):
- US1 dataclass + formatter (T013-T014) ← Can be done together
- US2 dataclass + formatter (T027-T028) ← Can be done in parallel with US1
- US3 dataclass + formatter (T038-T039) ← Can be done in parallel with US1/US2

**Testing** (All test tasks can be parallelized after implementation tasks complete):
- T010, T011, T012 ← After T007-T009
- T015, T029, T040 ← After corresponding formatter implementations

---

## Implementation Strategy

### MVP Scope (Week 1)
Focus on **User Story 1 (P1)** only for initial MVP:
- Complete Phase 1 (Setup) - T001-T006
- Complete Phase 2 (Foundational) - T007-T012
- Complete Phase 3 (US1) - T013-T026

**Deliverable**: Functional pre-match prediction posting system

### Iteration 2 (Week 2)
Add **User Stories 2 & 3 (P2, P3)**:
- Complete Phase 4 (US2) - T027-T037
- Complete Phase 5 (US3) - T038-T050

**Deliverable**: Complete prediction lifecycle (pre-match → start → result)

### Iteration 3 (Week 3)
Polish and production readiness:
- Complete Phase 6 (Polish) - T051-T066

**Deliverable**: Production-ready feature with UX enhancements and comprehensive error handling

---

## Task Statistics

- **Total Tasks**: 66
- **Setup/Infrastructure**: 6 tasks (Phase 1)
- **Foundational**: 6 tasks (Phase 2)
- **User Story 1 (P1)**: 14 tasks (Phase 3)
- **User Story 2 (P2)**: 11 tasks (Phase 4)
- **User Story 3 (P3)**: 13 tasks (Phase 5)
- **Polish**: 16 tasks (Phase 6)

- **Parallelizable Tasks**: 10 tasks marked with [P]
- **User Story Tasks**: 38 tasks (mapped to specific stories)

---

## Validation Checklist

Before marking feature complete, verify:

- [ ] All 27 functional requirements from spec.md are implemented
- [ ] All 6 success criteria are met and measurable
- [ ] All edge cases from spec.md are handled
- [ ] Unit tests pass (pytest coverage > 80%)
- [ ] Manual testing completed for all three posting types
- [ ] quickstart.md instructions are accurate and tested
- [ ] No security issues (.env excluded from git, token never logged)
- [ ] Constitution compliance maintained (no violations introduced)

---

## Notes

- **Task IDs are sequential** (T001-T066) for tracking purposes
- **[P] marker** indicates tasks that can be done in parallel with other [P] tasks
- **[US#] marker** links tasks to specific user stories for traceability
- Each phase is independently testable with clear success criteria
- MVP delivers value with just Phase 1-3 (User Story 1)
