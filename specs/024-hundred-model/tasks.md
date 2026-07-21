# Tasks — The Hundred Win-Probability Model

**Input**: `spec.md`, `research.md`, `data-model.md`, and `plan.md`  
**Status**: Foundation, isolated pipeline, candidate training, and first promotion evaluation
complete; candidate remains shadow-only because the frozen gates do not pass.

## Phase 1 — Audit and contracts

- [x] T001 Add `scripts/audit_hundred_data.py` to parse every `hnd_json/*.json` and write a
  machine-readable audit report plus quarantine manifest.
- [ ] T002 Add tests for source counts, metadata, outcome buckets, legal-ball counts, and
  the two known legal-ball overflow cases.
- [x] T003 Define reason codes and stable JSON schema for quarantine records.
- [ ] T004 [P] Add representative fixtures for wides, no-balls, early chase, all-out,
  D/L, tie/Super Five, and raw six-ball labels.

## Phase 2 — Format configuration and normalization

- [x] T005 Add `FormatConfig.hundred()` with 100 balls, five-ball units, phase boundaries,
  structural fields, scoring priors, and Hundred resource inputs in
  `src/bbl_pipeline/features/format_config.py`.
- [x] T006 Resolve `hundred` and `hundred_all` in `FormatConfig.from_league()`.
- [x] T007 Add a legal-ball normalizer in the ingestion/data path that retains raw labels
  but derives the canonical legal-ball index, five index, ball-within-five, end block,
  powerplay state, and anomaly flags.
- [x] T008 Parameterize shared processing and live-inference ball/over arithmetic to use `balls_per_over` and
  `total_balls`; audit `src/bbl_pipeline/data/processor.py`, calibration, simulation, and
  inference for six-ball assumptions.
- [x] T009 Add unit tests at legal balls 0, 24, 25, 59, 60, 84, 85, and 99.

## Phase 3 — CLI and feature-store wiring

- [x] T010 Add the `hundred_all` retrain configuration in `src/bbl_pipeline/cli.py` with
  isolated raw/features/store/model paths.
- [x] T011 Preserve `gender_female` and source competition metadata in normalized and
  feature-store outputs.
- [x] T012 Add Hundred-specific legal-ball, five-index, end-block, powerplay, phase, and
  resource features with training/live-safe semantics.
- [x] T013 Add metadata/data-fingerprint output for the Hundred feature store and model.
- [x] T014 [P] Add `tests/unit/test_hundred_format_config.py` and
  `tests/unit/test_hundred_normalization.py`.

## Phase 4 — Baseline training and calibration

- [x] T015 Ingest the standard 301-match completed cohort without mutating the raw source;
  retain the 303-match ordinary-completed count and two overflow exclusions in the manifest.
- [x] T016 Process `hundred_all` features and verify row counts against the audit manifest.
- [x] T017 Train `models/hundred_all_v1` with the existing XGBLogRegEnsemble.
- [x] T018 Generate OOF raw predictions and calibrator candidates.
- [x] T019 Compare resource-only, raw-model, and calibrated-model outputs without using
  2025 holdout data for fitting.
- [x] T020 Save feature order, format snapshot, source fingerprint, and calibration report.

## Phase 5 — OOS evaluation and parity

- [x] T021 Build the 2021–2024 train / 2025 holdout evaluation manifest.
- [x] T022 Report overall, male, female, innings, phase, Brier, log loss, ECE, reliability,
  calibration intercept/slope, open-state metrics, and sample/match counts.
- [x] T023 Add training/live parity tests for legal clock, phase, resource, target, and
  gender fields.
- [x] T024 Add model-load, feature-order, missing-value, and CLI live-state mapping smoke
  tests for `hundred_all`.
- [ ] T025 Add `tests/integration/test_hundred_pipeline.py` covering audit → process →
  train artifact resolution on a small fixture set.

## Phase 6 — Promotion decision and handoff

- [x] T026 Evaluate the promotion gates in `plan.md` using a pre-registered tolerance.
- [x] T027 Keep the candidate research-only if any overall, gender, calibration, or parity
  gate fails; write the decision report either way.
- [ ] T028 Register the model only after all artifact and runtime checks pass.
- [ ] T029 Document D/L, Super Five, timeout, and bowler-spell follow-up experiments.
- [x] T030 Compare Hundred resource, existing T20, T20-recalibration, Hundred-only, and
  T20-pretrained/Hundred-adapted candidate tracks.
- [x] T031 Freeze the 2025 manifest and 5%–95% open-state row selection before candidate
  metrics are inspected.
- [x] T032 Implement match-equal Brier, 2,000 match-block bootstrap CIs, and rolling-origin
  season reports.
- [x] T033 Apply the ten frozen promotion gates and write a promotion/shadow decision file.

## Dependencies

- T005–T009 depend on T001–T004.
- T010–T014 depend on the format and normalization contract.
- T015–T020 depend on CLI and feature-store wiring.
- T021–T025 depend on trained artifacts.
- T026–T029 depend on the complete OOS and parity reports.
