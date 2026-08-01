# Tasks — Spec 025 Upcoming Opening Intelligence

Status: `[ ]` queued, `[-]` in progress, `[x]` verified, `[!]` blocked by evidence.

## Phase 0

- [x] T001 Inventory historical pre-start outcome fields and identity coverage.
  Evidence: `research.md`; raw T20 rows provide dated team-pair/outcome records.
- [-] T002 Produce time-safe feature contract and leakage test cases.
  Finding: existing `team_ratings.parquet` files have no as-of date and are
  full-history aggregates, so they are prohibited from chronological OOF use.
- [ ] T003 Implement chronological split and 0.50/historical-win-rate baselines.
- [ ] T004 Define written promotion thresholds and required segment samples.

## Phase 1

- [ ] T005 Add a bounded scraper `/prematch-candidates` endpoint.
- [ ] T006 Add contract tests for exact URL, 12–48-hour window, supported format,
  and no live-selector mutation.
- [ ] T007 Add dashboard pre-match candidate status separate from live
  `last_candidates` and retirement logic.

## Phase 2

- [ ] T008 Implement a deterministic team-strength baseline using only as-of
  historical inputs.
- [ ] T009 Generate chronological OOF predictions and calibrate without leakage.
- [ ] T010 Publish an offline report with overall and segment Brier/ECE/log loss
  plus coverage and baseline comparisons.
- [ ] T011 Decide promote, revise, or stop using the written gate.

## Phase 3

- [ ] T012 Add the exact-source upcoming opening serializer, TTL, and explicit
  low-coverage/not-ready fallbacks.
- [ ] T013 Add dashboard/public API contract tests; prove opening rows cannot be
  emitted as live rows.
- [ ] T014 Add canonical SSR rendering and stale rejection tests.
- [ ] T015 Deploy one eligible fixture only; prove normal, Googlebot, and 390px
  browser parity; run `Assert-LiveMatchCohortReadiness.ps1`.

## Phase 4

- [ ] T016 Record sitemap/SSR/GSC discovery timing and analytics receipt for
  the controlled fixture.
- [ ] T017 Review 28-day cohort evidence before expanding the opening model.
