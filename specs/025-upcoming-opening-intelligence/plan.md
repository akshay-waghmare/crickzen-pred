# Plan — Spec 025 Upcoming Opening Intelligence

## Phase 0 — Data and leakage audit

1. Inventory usable historical fixture outcomes and their timestamp/identity
   fields for T20 and ODI.
2. Define an as-of feature table: team, opponent, venue, competition, format,
   scheduled start, historical record, and source quality.
3. Build a chronological split and baseline report before selecting a model.

Gate: no candidate uses fields unavailable before the scheduled start.

## Phase 1 — Bounded pre-match fixture ingress

1. Add `GET /prematch-candidates` in the scraper, backed by the upcoming
   catalogue and bounded to supported 12–48-hour fixtures.
2. Preserve the existing `/prediction-candidates` live-only response byte and
   semantics.
3. Add dashboard-side separate pre-match candidate polling/status; do not mix
   it into `last_candidates` used for live prediction retirement.

Gate: a live-selector test proves an upcoming candidate cannot retire a live
prediction.

## Phase 2 — Opening estimator experiment

1. Implement a deterministic chronological team-strength baseline.
2. Generate OOF rows and calibrate only with training-period data.
3. Evaluate overall and segment Brier, ECE, log loss, coverage, and confidence
   distribution versus the two baselines.

Gate: retain only a candidate that passes the written promotion thresholds.

## Phase 3 — Safe public contract and SSR cohort

1. Serialize a distinct `upcoming` opening row with exact URL and TTL.
2. Teach the frontend canonical SSR block to label before-toss intelligence and
   reject stale/low-coverage rows.
3. Run raw SSR normal/Googlebot, 390px hydration, and cohort readiness checks.

Gate: a single current fixture meets all upcoming evidence requirements before
any broader catalogue rollout.

## Phase 4 — Measurement

1. Add the controlled opening URL to the discovery ledger and inspect it in
   GSC before and after start.
2. Validate `match_view` and prediction/explanation engagement at the analytics
   destination.
3. Compare the first 28-day GSC/engagement evidence with the existing baseline.
