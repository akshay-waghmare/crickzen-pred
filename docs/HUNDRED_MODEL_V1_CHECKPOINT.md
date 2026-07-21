# Hundred Model v1 — Implementation Checkpoint

Date: 2026-07-22  
Status: `SHADOW_ONLY`  
Production routing: unchanged

## Outcome

The Hundred pipeline is implemented end to end, but `hundred_all_v1` is not promoted.
The untouched 2025 evaluation rejects the candidate under the frozen promotion protocol.
This is an intentional research/shadow result, not a production failure.

| Track | 2025 Brier | Open-state Brier | ECE |
|---|---:|---:|---:|
| Hundred-only raw | 0.1634 | 0.1841 | 0.0287 |
| T20 feature-adapted | 0.1653 | 0.1862 | 0.0305 |
| Hundred-only logit recalibrated | 0.1635 | 0.1839 | 0.0303 |
| T20 + Hundred logit recalibrated | 0.1545 | 0.1739 | 0.0491 |
| Hundred resource baseline | 0.1714 | 0.1929 | — |
| Existing `t20_all_v2` production model | 0.1537 | 0.1730 | — |

The raw Hundred-only candidate beats the resource baseline, but loses to the existing T20
production model. It also fails the frozen calibration, bootstrap, gender, phase/innings,
and rolling-origin stability gates. The recalibrated T20 track is close on Brier but fails
calibration slope/ECE and remains non-promotable.

## Data contract

The source audit covers 322 parseable Cricsheet files across 2021–2025:

- 301 standard training matches.
- 21 quarantined records: 9 no-result, 4 tie/Super Five, 6 D/L, and 2 main-innings
  legal-ball overflow matches.
- 62,397 raw delivery rows before duplicate removal.
- 57,975 processed feature rows across the 301-match cohort.

The raw source remains untouched. The standard v1 cohort is enforced during Hundred
ingestion and independently recorded in `experiments/hundred_v1/audit/`.

## Implemented architecture

- `FormatConfig.hundred()` defines 100 legal balls, five-ball scoring sets, 10-ball end
  changes, 25-ball powerplay, 20-ball bowler maximum, phase boundaries, and gender-aware
  priors.
- `HundredNormalizer` derives legal-ball index, five index, ball-within-five, end block,
  powerplay state, phase, gender, and anomaly flags while retaining raw coordinates.
- Shared feature processing and live mapping use configured `balls_per_over`; Hundred
  inference prefers the explicit normalized legal-ball count over raw coordinates.
- `hundred_all` has isolated raw data, feature, feature-store, model, and evaluation paths.
- OOF calibrators, per-over/innings-phase reports, reliability tables, match-block bootstrap
  intervals, and rolling-origin season metrics are written as research artifacts.
- Evaluated tracks include Hundred-only raw, T20-feature-adapted, Hundred-only recalibrated,
  and T20-plus-Hundred recalibrated variants.

## Validation

Focused Hundred tests pass: 10 tests covering format configuration, legal-ball anomalies,
phase boundaries, legal-clock parity, feature order, missing-value defaults, and live state
mapping. The generic ingestion tests still contain pre-existing no-outcome fixture failures;
they are outside the Hundred contract and do not change the shadow decision.

## Artifacts

- Source audit: `experiments/hundred_v1/audit/audit_report.json`
- Quarantine manifest: `experiments/hundred_v1/audit/quarantine_manifest.json`
- Candidate: `models/hundred_all_v1/`
- OOF calibration report: `models/hundred_all_v1/OOF_CALIBRATION_REPORT.md`
- Frozen evaluation: `experiments/hundred_v1/evaluation/promotion_metrics.json`
- Gate decision: `experiments/hundred_v1/evaluation/promotion_decision.json`
- Evaluator: `scripts/evaluate_hundred_promotion.py`

## Next work before any promotion attempt

1. Diagnose male and innings-1 degradation against `t20_all_v2`.
2. Improve calibration using only pre-2025 chronological calibration data.
3. Add explicit D/L and Super Five handling as separate tracks rather than broadening v1.
4. Re-run the frozen evaluator; promotion remains forbidden unless every gate passes.
