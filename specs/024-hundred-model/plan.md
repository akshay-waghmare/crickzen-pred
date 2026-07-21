# Plan — The Hundred Win-Probability Model

**Branch**: `024-hundred-model`  
**Date**: 2026-07-22  
**Spec**: [spec.md](spec.md)

## Summary

Add a Hundred-specific, combined-gender model track by reusing the repository's T20
pipeline contracts and replacing six-ball assumptions with a validated 100-legal-ball,
five-ball format configuration. The first candidate is `hundred_all_v1`; existing T20 and
ODI artifacts remain untouched until the frozen promotion protocol in `spec.md` supports
a separate route.

## Technical context

**Language**: Python 3.x  
**Dependencies**: pandas, NumPy, scikit-learn, XGBoost, pytest, existing CLI  
**Storage**: Cricsheet JSON, Parquet feature data, versioned model directories  
**Testing**: pytest plus focused CLI/data audits  
**Target**: local training pipeline and later live prediction integration  
**Primary paths**: `src/bbl_pipeline/`, `scripts/`, `tests/`, `data/`, `models/`, `specs/`

## Constitution check

- **Scalability/reuse**: pass — use `FormatConfig` and a `hundred_all` CLI entry rather
  than copying T20 code.
- **Pipeline architecture**: pass — audit → normalize → process → train → calibrate →
  evaluate remains modular.
- **Reproducibility**: pass — source fingerprint, versioned directories, frozen feature
  order, and chronological holdout are required.
- **Data integrity**: pass — legal-ball validation, entity resolution, and quarantine are
  first-class gates.
- **Calibration/observability**: pass — OOF calibration and all/male/female reports are
  mandatory; production requires the constitution's ECE gate.

## Phase 0 — Data audit and rule contract

1. Add or run a reusable Hundred audit that reports file validity, seasons, genders,
   outcomes, innings lengths, raw delivery counts, legal-ball counts, and anomalies.
2. Freeze the legal-ball rules and source data fingerprint in the experiment manifest.
3. Confirm the normal training cohort: ordinary completed matches only; quarantine D/L,
   no-result, ties/Super Five, and legal-ball overflow.

## Phase 1 — Format and normalization foundation

1. Add `FormatConfig.hundred()` with `total_legal_balls=100`, `scoring_set_size=5`,
   `end_change_interval=10`, `powerplay_balls=25`, `max_balls_per_bowler=20`, Hundred
   phases, scoring priors, and resource table inputs.
2. Extend `FormatConfig.from_league()` to resolve `hundred` and `hundred_all`.
3. Add a legal-ball normalizer or parameterize the existing processor so raw delivery
   labels never determine the Hundred clock.
4. Add Hundred CLI configuration with source `hnd_json/` and isolated artifact paths.
5. Add schema/data-contract tests before training.

## Phase 2 — Feature and inference parity

1. Replace six-ball calculations in the shared path with `format_config.balls_per_over`.
2. Add a `HundredNormalizer` that emits raw delivery index, legal-ball index, five index,
   ball-within-five, ten-ball end block, powerplay state, and anomaly flags.
3. Add legal-ball, five-index, end-block, powerplay, phase, and 100-ball resource fields.
4. Ensure the live mapper/predictor can construct the same fields from a live state.
5. Add parity fixtures at legal balls 0, 24, 25, 59, 60, 84, 85, and 99.
6. Keep optional bowler-spell and timeout fields out of the model until live availability
   is proven.

## Phase 3 — Baseline training and OOF calibration

1. Ingest and process the accepted standard cohort into versioned paths.
2. Train `hundred_all_v1` with the existing XGBLogRegEnsemble.
3. Generate OOF predictions and compare raw, resource-only, and calibrated outputs.
4. Select a calibration granularity only when every selected bucket has adequate support;
   prefer phase/five grouping over sparse per-ball calibration.
5. Save feature list, config snapshot, source fingerprint, and metrics beside artifacts.

## Phase 4 — Chronological validation and promotion gate

Use the exact frozen protocol in `spec.md`: untouched 2025 holdout, fixed 5%–95%
open-state subset selected from the existing T20 baseline, rolling-origin season folds,
and 2,000 match-block bootstrap resamples. Report:

- Brier score, log loss, ECE, reliability bins;
- overall, male, female, innings 1, innings 2, and phase slices;
- match-level aggregation and sample/match counts;
- standard cohort versus quarantined cohort counts;
- resource, existing-T20, T20-recalibration, Hundred-only, and transfer-candidate tracks;
- open-state, match-equal gender, and bootstrap confidence intervals;
- inference parity and model-load smoke checks.

### Promotion gate

Promote only if all ten conditions in the frozen promotion protocol in `spec.md` hold.
In particular, the candidate must beat both the Hundred resource baseline and the
existing T20 production model on untouched 2025 Brier, also win on the 5%–95% open-state
slice, pass gender/phase/innings gates, and have bootstrap-supported improvement.

If any gate fails, keep the candidate artifacts, retain the current production routing,
and record the failure rather than tuning against the holdout.

## Phase 5 — Later extensions, not v1 blockers

- D/L/reduced-ball target support.
- Super Five simulator.
- Bowler five/ten-ball choice and quota-aware simulation.
- Optional timeout-state feature if live feeds expose it.
- Separate male/female model candidates.
- Market comparison when Hundred market snapshots are available.

## Project structure

```text
specs/024-hundred-model/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md

src/bbl_pipeline/features/format_config.py
src/bbl_pipeline/data/processor.py
src/bbl_pipeline/ingestion/
src/bbl_pipeline/inference/
src/bbl_pipeline/simulation/
src/bbl_pipeline/cli.py
scripts/
tests/unit/
tests/integration/
```
