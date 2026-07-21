# Spec 024 — The Hundred Win-Probability Model

**Feature Branch**: `024-hundred-model`  
**Created**: 2026-07-22  
**Status**: Draft — planning and data-contract phase  
**Input**: Build a Hundred model from `hnd_json/`, following the existing T20 model workflow while respecting Hundred-specific rules.

## Goal

Create a production-capable, gender-aware Hundred win-probability model from `hnd_json/`.
The first model track is `hundred_all`: one combined male/female model with an explicit
`gender_female` feature, evaluated by gender before any promotion. This follows the
existing `t20_all` pattern, but uses a 100-legal-ball format configuration and a
legal-ball clock throughout ingestion, feature generation, calibration, simulation, and
live inference.

The current request is for the plan and specification. Implementation and training begin
only after this package is accepted.

## Why Hundred is not ordinary T20

The raw files use Cricsheet's T20-compatible schema and declare `balls_per_over: 5`, but
the model must not inherit six-ball T20 assumptions. The canonical match clock is:

| Rule/model concept | Hundred contract |
|---|---|
| Innings length | 100 legal balls, represented as 20 five-ball overs/fives |
| End changes | After every 10 legal balls; batters do not change ends between fives |
| Bowling quota | Maximum 20 legal balls per bowler in an uninterrupted innings |
| Powerplay | Legal balls 1–25; maximum two fielders outside the circle |
| Non-powerplay fielding | Men: maximum five outside; women: maximum four |
| Strategic timeout | Fielding captain may take one 90-second timeout after ball 25; it may occur mid-five or between fives |
| Normal result | Higher score wins; tie is not a normal binary training label |
| Knockout tie-break | Super Five, a separate five-ball-per-side contest |

These rules are from the current ECB 2026 playing conditions and the official Hundred
competition explanation. See `research.md` for the source links and modeling implications.

## User scenarios and testing

### User Story 1 — Audit and normalize Hundred data (Priority: P1)

As a model developer, I want the Hundred JSON files audited and converted into a
validated legal-ball representation so that five-ball rules and shortened innings are
handled correctly.

**Independent Test**: Run the dataset audit and normalization checks against `hnd_json/`;
the report must include file count, season/gender coverage, outcome buckets, legal-ball
counts, raw-delivery anomalies, and a quarantine manifest.

**Acceptance Scenarios**

1. Given a valid Hundred JSON file, when it is normalized, then every delivery has a
   monotonic `legal_ball_index` based on legal deliveries rather than raw over labels.
2. Given wides/no-balls, when legal-ball position is calculated, then they add runs but do
   not advance the legal-ball clock.
3. Given an innings ending early because of all-out or a successful chase, when it is
   processed, then it remains a valid shortened innings with `balls_remaining` calculated
   from 100 legal balls.
4. Given a D/L match, tie, no-result, super-five innings, or an innings with more than 100
   legal balls, when it is audited, then it is flagged or quarantined rather than silently
   being treated as a standard completed innings.

### User Story 2 — Train and evaluate a Hundred baseline model (Priority: P1)

As a data scientist, I want to train `hundred_all_v1` using the existing ingestion,
feature, XGBLogRegEnsemble, OOF calibration, and registry workflow so that the first
Hundred model is comparable to the existing T20 models.

**Independent Test**: Run the Hundred retrain command on the accepted training set and
verify raw data, feature data, feature store, model, OOF calibrators, metrics, and model
metadata are all produced under versioned paths.

**Acceptance Scenarios**

1. Given the normalized Hundred dataset, when retraining is run, then it resolves a
   Hundred-specific format configuration without changing T20 constants.
2. Given a trained model, when OOF analysis runs, then it reports Brier, log loss, ECE,
   reliability bins, match counts, sample counts, and male/female slices.
3. Given live-style state input, when the model is loaded, then inference uses the same
   100-ball, five-ball, phase, and feature semantics as historical training.

### User Story 3 — Validate promotion and simulation safety (Priority: P2)

As the model owner, I want a controlled comparison against a Hundred resource baseline
before routing the model to production so that a new format model cannot win by leakage or
incorrect T20 assumptions.

**Independent Test**: Run chronological evaluation with 2021–2024 training and 2025
holdout data, compare against the Hundred resource baseline, and inspect all/male/female
gates plus training/live parity tests.

**Acceptance Scenarios**

1. Given a candidate that improves overall Brier score but regresses one gender slice,
   when promotion is evaluated, then the candidate remains research-only.
2. Given a candidate with feature-clock mismatch, when parity tests run, then promotion is
   blocked even if aggregate metrics improve.
3. Given a tie or Super Five, when the normal model is evaluated, then it is excluded from
   the binary normal-match target and handled by a future separate tie-break simulator.

## Edge cases

- Raw over blocks may contain more than five deliveries because of illegal deliveries;
  list position inside an over is not the legal-ball clock.
- A raw file can declare five-ball overs but contain a six-ball over label or a source
  anomaly; retain the raw record, derive the canonical clock, and log the discrepancy.
- An innings can end below 100 legal balls because it is all out or the chase is complete.
- D/L matches require a revised-target contract and are excluded from the first standard
  training cohort unless that target is explicitly extracted and validated.
- No-result and tied matches do not provide a clean binary winner label.
- Super Five innings are not normal innings and must never be appended to the main innings
  target as if they were a third innings.
- Women and men use different non-powerplay fielding-circle limits; this is a rule
  annotation and future feature opportunity, not permission to leak post-event data.
- New team/player/venue names must pass the shared entity resolver rather than creating
  unstable IDs.

## Functional requirements

- **FR-001**: The system MUST expose a `hundred`/`hundred_all` format configuration with
  `total_balls=100` and `balls_per_over=5`.
- **FR-002**: The system MUST derive `legal_ball_index` sequentially from deliveries,
  excluding wides and no-balls from the legal-ball count while retaining their runs and
  wicket metadata.
- **FR-003**: The system MUST calculate `balls_bowled`, `balls_remaining`, current run
  rate, required run rate, resources, and phase from legal-ball position.
- **FR-004**: The system MUST not use six-ball constants in Hundred ingestion, processing,
  calibration, simulation, or live inference.
- **FR-005**: The system MUST represent the 25-ball powerplay and the 10-ball end-change
  block explicitly in the format-aware state/features.
- **FR-006**: The system MUST preserve gender as `gender_female` in the combined model and
  report gender-sliced evaluation.
- **FR-007**: The system MUST support a quarantine manifest with reason codes for malformed,
  D/L, no-result, tie/Super Five, and legal-ball-overflow records.
- **FR-008**: The system MUST keep raw, normalized, processed, feature-store, model, and
  evaluation artifacts versioned and separate from existing T20/ODI artifacts.
- **FR-009**: The system MUST use the existing XGBLogRegEnsemble and OOF calibration
  workflow unless an experiment documents a justified change.
- **FR-010**: The system MUST evaluate chronological generalization using a 2025 holdout,
  plus overall, male, and female slices.
- **FR-011**: The system MUST add training/live feature-parity tests for the legal-ball
  clock, phase, resource, target, and gender fields.
- **FR-012**: The system MUST not route `hundred_all_v1` to production until the promotion
  gates in `plan.md` pass.
- **FR-013**: The system MUST treat Super Five as a separate future simulator contract,
  not as normal match training data.

## Key entities

- **HundredMatch**: Match metadata, season, gender, teams, venue, outcome, toss, and
  competition context.
- **NormalizedDelivery**: Raw delivery plus legal-ball index, five index, end-change block,
  phase, runs, extras, wicket, batter, bowler, and entity IDs.
- **HundredInningsState**: Score, wickets, target, legal balls bowled, balls remaining,
  current five, end block, phase, powerplay status, and chase state.
- **QuarantineRecord**: Match/innings ID, reason code, source path, observed values, and
  whether the record is eligible for future recovery.
- **HundredModelArtifact**: Model files, feature ordering, format identity, gender handling,
  calibration artifacts, data fingerprint, and evaluation metadata.

## Success criteria

- **SC-001**: 100% of source JSON files parse successfully or appear in an explicit audit
  failure report; no file is silently dropped.
- **SC-002**: Every accepted training row has a deterministic legal-ball index and no
  negative or six-ball-derived Hundred clock values.
- **SC-003**: The first candidate beats the Hundred resource baseline on chronological
  holdout Brier score and log loss, or is retained as research-only with the failure
  documented.
- **SC-004**: No male or female holdout slice materially regresses versus the selected
  baseline; exact thresholds are defined in `plan.md` before training.
- **SC-005**: Training and live feature parity tests pass for representative states at
  balls 0, 24, 25, 59, 60, 84, 85, and 99.
- **SC-006**: No production route selects the candidate unless model loading, calibration,
  registry metadata, and runtime smoke tests pass.

## Out of scope for v1

- Predicting the captain's choice to bowl five versus ten balls.
- Predicting the exact timing of the optional strategic timeout.
- Modeling field placement directly without reliable historical field-position data.
- Modeling DLS-adjusted targets without a validated revised-target extraction path.
- Building a Super Five predictor; only the interface and quarantine behavior are specified.
- Automatically creating separate male/female champion models; those may be later candidates
  if segmented evidence justifies them.

## Frozen promotion protocol

`hundred_all_v1` MUST remain research/shadow-only until every gate below is evaluated on
the same pre-registered data manifest. The existing T20 production model and the Hundred
resource baseline are comparators; neither may be changed during the 2025 evaluation.

### Candidate tracks

The first experiment must compare these isolated tracks:

1. Hundred resource baseline.
2. Existing T20 production model, evaluated through a Hundred-compatible state adapter.
3. T20 production model plus Hundred recalibration.
4. Hundred-only model.
5. T20-pretrained/Hundred-adapted candidate, if the existing trainer supports safe
   feature-compatible initialization.

Only the Hundred-only candidate is eligible for the initial `hundred_all_v1` artifact;
the other tracks explain whether a gain comes from format calibration, transfer, or
Hundred-specific learning.

### Frozen evaluation slices and metrics

- Primary holdout: all untouched 2025 standard-cohort matches.
- Rolling-origin folds: train through 2021 → test 2022; through 2022 → test 2023;
  through 2023 → test 2024; through 2024 → test 2025.
- Open-state slice: rows where the frozen existing-T20 baseline probability is between
  0.05 and 0.95 inclusive. Every model is scored on this same row set.
- Weighting: overall and open-state Brier/log loss are delivery-row metrics; gender
  fairness gates use match-equal-weighted match-level Brier.
- Calibration: 20 fixed equal-width probability bins on [0,1], excluding empty bins;
  `ECE = sum(bin_count / total_count * abs(bin_mean_prediction - bin_observed_rate))`.
  Also report logistic calibration intercept and slope using clipped prediction logits,
  and reliability tables/plots from the same bins.
- Bootstrap: 2,000 match-block bootstrap resamples with a fixed seed, resampling complete
  matches rather than individual deliveries. Improvement is supported when the 95% CI for
  candidate-minus-comparator Brier is entirely below zero.
- Log-loss non-inferiority: candidate-minus-comparator log-loss 95% CI upper bound must be
  no greater than the frozen absolute margin of `0.005`; a negative point estimate is
  still reported as an improvement.

### Frozen tolerances

These tolerances are fixed before reading 2025 candidate metrics:

- Gender material regression: candidate match-equal Brier may not be worse by more than
  `max(0.005 absolute, 5% of the comparator Brier)` for either gender.
- Severe slice regression: any important innings/phase slice with at least 25 matches is
  a failure if Brier worsens by more than `max(0.010 absolute, 10% relative)` or if its
  bootstrap CI is decisively positive for regression.
- Calibration: production promotion requires `ECE <= 0.0021`, absolute intercept `<= 0.05`,
  slope between `0.90` and `1.10`, and no supported reliability bin with absolute gap
  greater than `0.05`. Otherwise the artifact remains shadow/research-only.

### Required promotion decision

Promote only when:

1. Data-contract and inference-parity tests pass.
2. On untouched 2025, Brier beats both the Hundred resource baseline and existing T20
   production model overall.
3. Log loss improves or is statistically non-inferior, using the match-block bootstrap CI.
4. The same directional result holds on the frozen 5%–95% open-state slice.
5. Neither male nor female match-equal Brier violates the frozen tolerance.
6. No important innings or phase slice has a severe regression.
7. Calibration diagnostics pass the frozen definitions and thresholds.
8. Bootstrap CIs support the improvement.
9. Rolling-origin results show no season-level instability or unexplained sign reversal.
10. Runtime model loading, feature order, missing-value behavior, and live state mapping
    tests pass.

If any gate fails, retain the existing production model and label the Hundred artifact
`research` or `shadow` with a complete decision report.
