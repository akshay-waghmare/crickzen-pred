# Spec 025 — Upcoming Opening Intelligence

Status: planned gate before public rollout
Started: 2026-08-01
Owners: CrickZen model, scraper, and canonical-match SEO workstreams

## Problem

Canonical upcoming match pages are crawlable before play, but the current public
prediction API can only publish a probability produced by a running
ball-by-ball predictor. The existing pre-match brief correctly degrades to
`partial` in that state; it must not turn a fixture, a venue average, or `50%`
into a claimed opening win probability.

The live selector (`/prediction-candidates`) is a finite, scraper-owned slate
and must stay live-only. Adding upcoming rows to that payload would let
auto-retirement stop valid live predictors, so it is not an acceptable shortcut.

## Outcome

For a supported fixture 12–48 hours before start, publish an **exact-source,
calibrated opening probability** only when the pre-match model has sufficient
historical coverage and passes offline quality gates. The row must retain the
same source URL through upcoming, live, and completed lifecycle transitions.

## Public contract

An eligible opening row has all of:

- `match_url`: normalized exact CREX source URL; no team-name-only matching.
- `status: "upcoming"` and `lifecycle: "upcoming"`.
- `win_probability_pct`: calibrated probability for the named team perspective.
- `updated_at`: ISO-8601 UTC with an explicit offset or `Z`.
- `model_label`: distinct pre-match model/version label, never a live-model label.
- `model_source`, `coverage_status`, and a concise uncertainty/explanation field.
- a finite TTL: it is withdrawn or marked stale at toss/start if it cannot be
  replaced by the live predictor.

If any field, team identity, calibration evidence, or coverage is missing, the
canonical page may show fixture context and an honest availability state, but
must not claim a win percentage or prediction answer.

## Required architecture

1. **Separate fixture ingress.** Add a bounded `/prematch-candidates` contract
   sourced from the backend upcoming catalogue. It returns normalized URL,
   teams, format, scheduled start, and series metadata only. It never enters
   `/prediction-candidates`, live-cap selection, fast scraping, or predictor
   retirement.
2. **Chronological pre-match model.** Build a team-strength/fixture model from
   historical outcomes known before scheduled start. It may use past team form,
   competition/format, venue history, and known fixture metadata; it must not
   use toss, score, ball-by-ball state, result text, later lineup facts, or any
   feature derived after start.
3. **Offline proof before serving.** Evaluate chronological out-of-fold rows,
   calibrated probabilities, Brier score, ECE, log loss, coverage, and segment
   cuts by format/gender/competition. Compare against a 0.50 baseline and a
   simple historical-win-rate baseline. Unknown/new-team and low-history rows
   are explicitly `not_ready`, not silently assigned neutral values.
4. **Dedicated service boundary.** The dashboard exposes opening rows through
   a separately named serializer/API path. The live `PublicMatchService` and
   its live-only freshness assumptions stay intact. Canonical SSR consumes the
   common safe public contract only after it can distinguish upcoming opening
   rows from live state.
5. **Lifecycle handoff.** At live start, retain the exact `match_url`, replace
   the opening row with the live predictor when fresh, and retain a final replay
   only when completed-result evidence is valid.

## Non-negotiable gates

- No raw or live score fields are available to the opening estimator.
- The matching key is the normalized source URL, not inferred team labels.
- Offline validation is chronological and has no future-match leakage.
- A model is deployable only if it improves on the agreed baselines on overall
  and required segment gates without material calibration regression.
- Public pages clearly label the row as "Before toss"; they never call it a
  current live probability.
- No Google Indexing API requests are made for ordinary `SportsEvent` pages.

## Acceptance evidence

- fixture-ingress contract tests prove a 12–48-hour supported fixture is
  returned without changing the live five-match selector;
- model tests prove feature-time safety, exact identity, low-coverage fallback,
  chronological validation, and serializer truthfulness;
- a held-out report records baseline and candidate metrics plus segment counts;
- one production upcoming URL has an exact fresh opening row and canonical raw
  SSR shows the same labelled answer to normal and Googlebot user agents;
- `Assert-LiveMatchCohortReadiness.ps1` passes the three lifecycle rows without
  weakening its live/completed checks;
- GSC discovery, indexing, ranking, and engagement remain separately measured.
