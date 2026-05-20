# Implementation Tasks: Telegram Public Signals Agent

**Feature**: [spec.md](spec.md) | [plan.md](plan.md) | **Generated**: 2026-05-01

## Phase 1: Agent and Launch Foundation

**Goal**: Create the repo agent brief and first-hour public channel operating checklist.

- [ ] T001 Create `.github/agents/crickzen.telegram.signals.agent.md` with the CrickZen IPL attention-layer operating brief (FR-001, FR-002)
- [ ] T002 Add pinned "How this channel works" template to the agent brief and launch docs (FR-002)
- [ ] T003 Define approved public invite copy for sharing in cricket/fantasy groups without spam language (FR-002, FR-011)
- [ ] T004 Define channel setup checklist: BotFather, public channel, bot admin permissions, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, test post (FR-015)

**Checkpoint**: Operator can create the public channel and understand what the agent should publish.

---

## Phase 2: Signal Templates and Guardrails

**Goal**: Make all lifecycle post types deterministic and reviewable before any live Telegram publishing.

- [ ] T005 Define pre-match before-toss draft template with match, favorite, confidence, caveat, and CTA (FR-003, FR-004)
- [ ] T006 Define toss update template comparing pre-match favorite to current favorite (FR-003, FR-005)
- [ ] T007 Define powerplay update template for 6-over score, current favorite, probability move, and reason (FR-003, FR-006)
- [ ] T008 Define 10-over/mid-innings and innings break templates for par/chase interpretation (FR-003, FR-006)
- [ ] T009 Define chase midpoint template for runs needed, balls remaining, wickets, favorite, and pressure read (FR-003, FR-006)
- [ ] T010 Define final review template with right/wrong call, what changed, and honest lesson (FR-003, FR-007)
- [ ] T011 Add copy guardrails for no stake sizing, no guarantees, no stale fixtures, no cherry-picking (FR-009, FR-010, FR-011)

**Checkpoint**: The agent can produce every lifecycle post in dry-run form.

---

## Phase 3: Accuracy Tracker Design

**Goal**: Create the simple public record that proves every pre-match signal is reviewed.

- [ ] T012 Define `AccuracyTrackerRow` fields: Date, Match, Pre-match favorite, Final result, Confidence, What changed (FR-008)
- [ ] T013 Choose initial storage format: append-only JSONL unless dashboard table rendering is implemented immediately (FR-008)
- [ ] T014 Add tracker row rules: row opens on pre-match post, completes after final review, never deleted (FR-010)
- [ ] T015 Add examples for right call, wrong call, no result, and DLS/reduced-over match (FR-007, FR-008)

**Checkpoint**: The tracker format can be copied into Telegram and later rendered in the dashboard.

---

## Phase 4: Dry-Run Signal Service

**Goal**: Convert model/dashboard state into publish-ready drafts only when source checks pass.

- [ ] T016 Implement or plan `SignalPostDraft` object with phase, match, source timestamp, probability, text, CTA URL, and readiness status (FR-003, FR-009)
- [ ] T017 Implement fixture verification rule: block publish-ready drafts when fixture/team names are unverified (FR-009)
- [ ] T018 Implement model freshness rule: block publish-ready drafts when prediction timestamp is stale or missing (FR-009)
- [ ] T019 Implement confidence band helper from rounded win probability (FR-004)
- [ ] T020 Implement duplicate lifecycle suppression by match and phase (FR-003)
- [ ] T021 Add dry-run tests for RR vs DC pre-match, CSK vs MI before toss, toss movement, powerplay movement, final review, and stale-state refusal (SC-003, SC-004, SC-005)

**Checkpoint**: Drafting can be tested without live Telegram credentials.

---

## Phase 5: Telegram Posting Integration

**Goal**: Reuse existing Telegram ledger infrastructure for manual approved public posts.

- [ ] T022 Reuse `src/bbl_pipeline/telegram/config.py` for `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHANNEL_ID` (FR-014, FR-015)
- [ ] T023 Reuse `src/bbl_pipeline/telegram/bot_client.py` for posting after operator approval (FR-013, FR-014)
- [ ] T024 Store Telegram message ID and timestamp with each published signal draft (FR-008, FR-014)
- [ ] T025 Ensure tests mock Telegram API and do not require credentials (SC-005)
- [ ] T026 Add manual test steps for private test channel before public channel launch (FR-015)

**Checkpoint**: Live posting is possible, but only after dry-run and operator approval.

---

## Phase 6: Dashboard CTA and Production Readiness

**Goal**: Convert interested Telegram users into the production dashboard after public value is visible.

- [ ] T027 Add `PUBLIC_DASHBOARD_BASE_URL` configuration for CTA generation (FR-012)
- [ ] T028 Generate match-specific public/dashboard URLs when slug is available from public dashboard service (FR-012, FR-014)
- [ ] T029 Omit CTA when dashboard URL is missing or production health check fails (FR-012)
- [ ] T030 Verify CTA copy remains secondary to prediction value in every template (FR-011, FR-012)
- [ ] T031 Smoke test production dashboard `/health` and at least one public match URL before public launch (SC-006)

**Checkpoint**: Telegram posts can upsell the dashboard without feeling like hard-sell betting copy.

---

## Phase 7: First Public Match Run

**Goal**: Execute the exact launch motion the user described.

- [ ] T032 Create CrickZen IPL Probability Telegram channel
- [ ] T033 Set bio: "Ball-by-ball IPL win probability powered by ML. Free pre-match and live prediction updates. Built by CrickZen."
- [ ] T034 Pin "How this channel works"
- [ ] T035 Verify today's fixture from CREX/dashboard before treating RR vs DC as publishable
- [ ] T036 Post RR vs DC pre-match prediction only after IPL v6 state is fresh
- [ ] T037 Share one approved invite in up to three cricket/fantasy groups where links are allowed
- [ ] T038 During the match, post toss, 6-over, 10-over, innings break, and chase midpoint updates when source state is fresh
- [ ] T039 Publish brutally honest final review after match completion
- [ ] T040 Update accuracy tracker row for the match
- [ ] T041 For CSK vs MI, post before-toss prediction only after fixture and model state are verified

**Checkpoint**: First public channel day produces a complete proof trail from pre-match to final review.

---

## Final Validation

- [ ] T042 Confirm every pre-match signal has a final review and tracker row (SC-002)
- [ ] T043 Confirm no public post used banned overclaiming or betting-guarantee language (SC-004)
- [ ] T044 Confirm lifecycle posts covered at least five moments for the match (SC-003)
- [ ] T045 Confirm Telegram drafts work in dry-run mode without credentials (SC-005)
- [ ] T046 Confirm public CTA links land on the intended dashboard/public match surface (SC-006)

## Parallel Work Notes

- Agent brief and launch checklist can be completed before code implementation.
- Signal templates and tracker schema can be written in parallel.
- Telegram posting integration should wait until dry-run tests and source freshness checks exist.
- Dashboard CTA can proceed in parallel with Telegram posting once production URL is known.
