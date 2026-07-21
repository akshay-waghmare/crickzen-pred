# Research — The Hundred Model

**Date**: 2026-07-22  
**Research status**: Complete for planning; implementation-specific questions remain for execution.

## 1. Authoritative rules

The ECB's current 2026 Playing Conditions apply from 1 April 2026 and define the
competition in 20 five-ball overs. The relevant clauses are:

- Law 17: an over is five balls; two five-ball overs are bowled from each end
  alternately, and batters do not change ends between overs.
- Law 13: no bowler may bowl more than four overs in an uninterrupted innings.
- Law 28: the first five overs/25 balls are the powerplay; two fielders may be outside
  the relevant circle. After that, the men's limit is five outside and the women's limit
  is four.
- Clause 12.8: the fielding captain may take one 90-second strategic timeout when the
  ball is dead; it is not available during the first 25 balls and may be taken mid-over
  or between overs.
- Law 16: normal group-stage ties remain ties; knockout ties use a Super Five.

Sources:

- [ECB The Hundred regulations page](https://www.ecb.co.uk/about/policies/regulations/the-hundred)
- [ECB The Hundred 2026 Playing Conditions](https://resources.ecb.co.uk/ecb/document/2026/03/24/f8005182-b39c-4c25-83bd-1ffff0415b7a/The-Hundred-2026.pdf)
- [Official Hundred competition rules](https://www.thehundred.com/info/competition-rules)

## 2. Why the raw JSON needs a legal-ball adapter

The dataset audit performed on `hnd_json/` found:

| Audit item | Result |
|---|---:|
| JSON files | 322 |
| Seasons | 2021–2025 |
| Male/female files | 167 / 155 |
| Declared format | `T20` in all files |
| Declared balls per over | `5` in all files |
| Raw delivery rows | 62,397 |
| Main innings | 638 |
| Extra innings | 2 Super Five innings in one match |
| Ordinary completed matches | 303 |
| Standard v1 matches after overflow quarantine | 301 |
| D/L matches | 6 |
| No-result matches | 9 |
| Tied matches | 4 |

Raw over arrays can contain more than five deliveries because wides and no-balls are
represented as deliveries that do not consume a legal ball. Therefore:

1. Retain raw `over` and `actual_delivery` for traceability only.
2. Count legal balls from the extras object.
3. Derive `legal_ball_index` globally within the innings.
4. Derive five index and end-change block from the legal-ball index.
5. Validate the derived clock against the 100-ball contract.

Two first innings in the audit produced more than 100 legal deliveries and must be
quarantined for source review. This is a data-integrity issue, not a reason to silently
truncate the innings.

## 3. Existing T20 architecture to reuse

The repository already provides the reusable pieces needed for a first Hundred model:

- `FormatConfig` for format-specific constants.
- `src/bbl_pipeline/data/processor.py` for feature generation.
- XGBLogRegEnsemble training and OOF analysis through the CLI.
- Existing model registry and versioned `data/`/`models/` artifact layout.
- `tests/unit/test_realtime_mapper_training_parity.py` as a parity-test pattern.
- Spec 021's combined-gender model contract.
- Spec 022's evidence-based selective-promotion rule.

The main architecture change is parameterization: any code that assumes six balls per
over or 120 balls per innings must consume `FormatConfig` or the normalized Hundred
state instead.

## 4. Modeling decisions

### 4.1 Combined model first

Use `hundred_all_v1` as the first candidate, matching `t20_all`:

- one model across men and women;
- `gender_female` retained as an explicit feature;
- male/female metrics required before promotion;
- separate male/female candidates are a later experiment, not a hidden fallback.

This avoids overfitting two small league-specific samples while preserving the ability to
measure gender-specific calibration.

### 4.2 Phase boundaries

Use legal-ball boundaries, not six-ball overs:

| Phase | Legal balls | Five units |
|---|---:|---:|
| Powerplay | 1–25 | 1–5 |
| Middle | 26–60 | 6–12 |
| Death | 61–85 | 13–17 |
| Final | 86–100 | 18–20 |

The exact phase cut points remain configurable for an ablation, but the 25-ball
powerplay is a rule constraint and must not be changed by an experiment.

### 4.3 Features

Retain the existing common features where their formulas are parameterized. Add or
validate Hundred-specific fields:

- `legal_ball_index`, `five_index`, `end_block_index`;
- `balls_bowled`, `balls_remaining`, `overs_remaining` using 5-ball units;
- powerplay and phase indicators;
- target, runs needed, required run rate, current run rate, and resource percentage;
- batter/bowler/team/venue rolling features using only information available before the
  current delivery;
- `gender_female` and source competition metadata;
- optional future fields for bowler quota, current spell, and timeout availability only
  when the same state is available in live inference.

Do not add post-delivery fields such as final score, outcome method, or actual timeout
usage to model inputs.

### 4.4 Calibration

First compare:

1. raw model;
2. Hundred resource baseline;
3. OOF-calibrated model by innings and five/phase bucket.

Because the dataset is smaller than the combined T20 corpus, per-ball calibrators are
not assumed safe. Select the least granular OOF calibrator that improves holdout metrics
without unstable small buckets. Any production candidate must meet the repository's
calibration gate and have held-out calibration evidence.

### 4.5 Match inclusion

The v1 standard training cohort includes the 301 ordinary completed matches that remain
after quarantining two legal-ball overflow records. D/L, ties,
no-results, and Super Five innings are retained in audit manifests but excluded from the
standard binary target until their semantics have dedicated contracts.

## 5. Open questions for implementation

- Whether the existing live feed exposes a canonical legal-ball count or requires the same
  adapter at inference time.
- Whether current feature-store player/bowler statistics have sufficient Hundred-specific
  sample support or need shrinkage toward global T20 priors.
- Whether D/L targets can be reconstructed consistently from the source and should become
  a later `hundred_reduced_v1` experiment.
