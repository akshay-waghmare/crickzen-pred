# Tasks — Spec 025 Upcoming Opening Intelligence

Status: `[ ]` queued, `[-]` in progress, `[x]` verified, `[!]` blocked by evidence.

## Phase 0

- [x] T001 Inventory historical pre-start outcome fields and identity coverage.
  Evidence: `research.md`; raw T20 rows provide dated team-pair/outcome records.
- [x] T002 Produce time-safe feature contract and leakage test cases.
  Evidence: `opening_baseline.py` ignores toss/ball state, canonicalizes the
  fixture pair, scores all same-day fixtures before applying their outcomes,
  and is covered by focused leakage tests. Existing `team_ratings.parquet`
  files remain prohibited because they are full-history aggregates with no
  as-of date.
- [x] T003 Implement chronological split and 0.50/historical-win-rate baselines.
  Evidence: date-disjoint calibration/final-holdout splitting plus neutral and
  prior-only historical-rate comparisons in `scripts/evaluate_opening_baseline.py`.
- [x] T004 Define written promotion thresholds and required segment samples.
  Evidence: `assess_promotion_gate()` requires 1,000 overall holdout rows,
  500 each for female/male, Brier improvement of at least 0.002 over neutral
  and historical rate, lower log loss than both, ECE <= 0.050, and at least
  one named-competition holdout segment.

## Phase 1

- [ ] T005 Add a bounded scraper `/prematch-candidates` endpoint.
- [ ] T006 Add contract tests for exact URL, 12–48-hour window, supported format,
  and no live-selector mutation.
- [ ] T007 Add dashboard pre-match candidate status separate from live
  `last_candidates` and retirement logic.

## Phase 2

- [x] T008 Implement a deterministic team-strength baseline using only as-of
  historical inputs.
  Evidence: expanding, smoothed per-team records use outcomes strictly before
  each fixture date; no live or score fields enter the estimator.
- [x] T009 Generate chronological OOF predictions and calibrate without leakage.
  Evidence: Platt calibration fits only the older 3,444 eligible prediction
  rows and is evaluated only on a date-disjoint 1,491-fixture final holdout.
- [x] T010 Publish an offline report with overall and segment Brier/ECE/log loss
  plus coverage and baseline comparisons.
  Evidence: `artifacts/opening-baseline/t20_all_v0.json` (generated, ignored)
  and the durable results in `research.md`.
- [x] T011 Decide promote, revise, or stop using the written gate.
  Decision (2026-08-01): **shadow-only revise**. The calibrated overall and
  male holdout metrics pass their comparisons, but female ECE is 0.070 > 0.050.
  Exact-ID Cricsheet event metadata now supplies 5,300 named competition rows,
  but the largest recent holdout event has only 49 fixtures, so these segments
  are informational rather than individual calibration gates. No public
  opening probability, fixture ingress rollout, or SSR work is authorized.
- [-] T011a Revise the calibration approach to pass the female holdout gate;
  retain exact event-name segments for reporting and define only adequately
  sized competition grouping before any competition-specific serving claim.

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
