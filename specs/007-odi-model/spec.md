# Feature Specification: ODI Win Probability Model

**Feature Branch**: `007-odi-model`  
**Created**: 2026-02-20  
**Status**: Draft  
**Input**: User description: "Create an ODI model like the existing T20 models, with an empirical resource calculator derived from ODI match data (male + female combined, 3,085 matches in odis_json/), and adapt the pipeline to support 50-over cricket."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Empirical ODI Resource Analysis (Priority: P1)

A data scientist runs an empirical analysis script on the 3,085 ODI match dataset (both male and female) to derive ODI-specific resource parameters: wicket penalties by phase, expected run rates, par scores, chase difficulty thresholds, and DLS resource percentages — all grounded in actual ODI scoring patterns rather than borrowing T20 values.

**Why this priority**: The entire ODI model depends on having accurate, empirically-derived resource parameters. Without this, any model trained would use T20 assumptions (par 160, death overs at over 15, RRR midpoint 9.5) that are completely wrong for 50-over cricket.

**Independent Test**: Run the analysis script on the ODI dataset and verify it produces a summary report with ODI-specific constants (par score, phase boundaries, expected run rates, wicket penalties, bat-first win rate) that differ meaningfully from T20 values.

**Acceptance Scenarios**:

1. **Given** 3,085 ODI match JSON files in `odis_json/`, **When** the empirical analysis script runs, **Then** it produces a report containing: average first-innings score, average second-innings score, bat-first win rate, run rates by phase, wicket penalty tables, and DLS-style resource percentages — all derived from empirical data.
2. **Given** the analysis output, **When** a user reviews the wicket penalty table, **Then** penalties are broken down by ODI-specific phases (Powerplay overs 1-10, Middle overs 11-34, Setup overs 35-40, Death overs 41-50) and ease buckets, with values reflecting ODI scoring patterns (e.g., death-over penalties less severe than powerplay penalties).
3. **Given** the empirical data, **When** computing the DLS resource table for ODI, **Then** the resource percentages cover 0-50 overs remaining × 0-10 wickets lost and interpolate smoothly between data points.

---

### User Story 2 - ODI Resource Feature Calculator (Priority: P1)

A developer creates an ODI-specific resource calculator (or parameterizes the existing T20 calculator) that uses the empirically-derived constants from Story 1 to compute win probabilities, projected scores, pressure indices, and all resource-based features for 50-over matches.

**Why this priority**: The resource calculator is the engine behind every feature. Until it correctly handles 50-over formats (phases, run rates, wicket penalties, projected scores), no meaningful model training can happen.

**Independent Test**: Feed sample ODI match states (e.g., 150/3 after 30 overs, first innings) into the calculator and verify it produces sensible win probabilities, projected scores, and pressure values — distinct from what the T20 calculator would output.

**Acceptance Scenarios**:

1. **Given** an ODI match state of 150/3 after 30 overs batting first, **When** the calculator computes `resource_win_prob`, **Then** the probability reflects a reasonable ODI assessment (~0.45-0.55), not a T20-based estimate.
2. **Given** a second-innings ODI chase of 280, with the chasing team at 200/4 after 40 overs (RRR = 8.0 off 10 overs), **When** the calculator computes win probability, **Then** the result reflects ODI chase dynamics (tight but achievable, ~0.35-0.45), not T20 thresholds.
3. **Given** overs bowled = 42 in an ODI, **When** asking for match phase, **Then** it returns "death" (overs 41-50), not "middle" or "powerplay".
4. **Given** the calculator uses empirically-derived wicket penalties, **When** a team loses its 5th wicket in the middle overs (over 25), **Then** the penalty applied to projected score is proportional to actual ODI scoring impact, not T20 middle-over penalties.

---

### User Story 3 - Pipeline Compatibility for ODI League (Priority: P2)

A user runs `bbl-pipeline retrain --league odi --version v1` and the full pipeline (ingest → process → train → generate-oof → analyze-oof) executes end-to-end, producing a trained ODI win probability model with calibrators, using the ODI-specific resource calculator and 50-over feature engineering.

**Why this priority**: The pipeline must support ODI as a first-class league alongside existing T20 leagues. This is needed to actually train and evaluate the model, but depends on the resource calculator being ready first.

**Independent Test**: Run the full retrain command for ODI and verify it produces `champion_model.joblib`, `oof_calibrators.pkl`, `OOF_CALIBRATION_REPORT.md`, and training metrics (Brier score, ECE, LogLoss).

**Acceptance Scenarios**:

1. **Given** ODI JSON files in `odis_json/`, **When** running `bbl-pipeline ingest --input-dir odis_json --output-dir data/odi_raw`, **Then** ball-by-ball parquet files are created with `match_type=ODI` and `overs=50`.
2. **Given** ingested ODI parquet data, **When** running `bbl-pipeline process` with ODI configuration, **Then** features are computed using 50-over phase boundaries, ODI resource calculator, and ODI par scores — producing a `training.parquet` with all required feature columns.
3. **Given** processed ODI features, **When** running `bbl-pipeline train`, **Then** an `XGBLogRegEnsemble` model is trained and saved to `models/odi_v1/champion_model.joblib`.
4. **Given** a trained ODI model, **When** running `bbl-pipeline analyze-oof`, **Then** a calibration report is generated with Brier score, ECE, and LogLoss metrics for the ODI model.

---

### User Story 4 - Live ODI Match Prediction (Priority: P3)

A user runs the live predictor against an ongoing ODI match, and the system provides real-time win probability updates using the ODI model and ODI feature store, with the correct 50-over resource calculations.

**Why this priority**: Live prediction is the end-user deliverable, but depends on having a trained model and working pipeline first.

**Independent Test**: Point the Crex live predictor at an ODI match URL with the ODI model and verify predictions update each ball with plausible probabilities.

**Acceptance Scenarios**:

1. **Given** a trained ODI model in `models/odi_v1/` and feature store in `data/odi_feature_store/`, **When** running the live predictor with `--league odi`, **Then** predictions are served using ODI-specific resource calculations and calibrators.
2. **Given** an ODI match in the 35th over, **When** the predictor updates, **Then** the match phase is correctly identified as "middle" (not "death") and the projected score uses 50-over calculations.

---

### Edge Cases

- **Reduced-overs ODI matches**: Matches where overs were reduced due to rain/DLS (i.e., `info.overs < 50`) are excluded from training and empirical analysis. Only full 50-over matches are used.
- **No result / abandoned matches**: Matches without a winner (ties, no result, abandoned) should be filtered during ingestion/training, consistent with how T20 models handle them.
- **Very old ODI data**: Matches before 2010 are excluded from empirical constant derivation and training. Only 2010+ matches are used, reflecting modern ODI scoring patterns.
- **Super overs in ODIs**: Rare but possible. Super over deliveries should be excluded from training data, as with T20 models.
- **First innings all-out before 50 overs**: The resource calculator must handle innings ending early due to all-out, with remaining resources correctly set to 0.
- **Gender differences**: Male and female ODIs have different scoring patterns. The resource calculator uses gender-specific empirical constants (separate par scores, penalty tables, DLS tables). Gender is a training feature so the model learns gender-specific dynamics. A single combined model is trained.

## Requirements *(mandatory)*

### Functional Requirements

#### Empirical Analysis

- **FR-001**: System MUST provide a script to analyze ODI match files (2010+ only) and compute empirical constants per gender: average first-innings score, par score, bat-first win rate, and scoring distributions — producing separate male and female constant sets.
- **FR-002**: System MUST compute ODI-specific phase boundaries based on actual scoring rate patterns across the dataset (e.g., when run rates accelerate, when death-over scoring begins).
- **FR-003**: System MUST generate a `FIRST_INNINGS_WICKET_PENALTY_3D` equivalent for ODI, keyed by ODI phases × ease buckets × wickets lost, with penalties derived from actual projected-score ratios in the data.
- **FR-004**: System MUST generate a `WICKET_PENALTY_2D` equivalent for ODI second innings, keyed by chase ease × wickets lost.
- **FR-005**: System MUST compute a DLS-style resource table for 0-50 overs remaining × 0-10 wickets lost, derived from actual ODI scoring patterns.
- **FR-006**: System MUST compute expected run rates by ODI phase to populate ease-bucket thresholds.
- **FR-007**: System MUST output all derived constants to a structured format (Python dict, JSON, or config file) that the resource calculator can consume.

#### Resource Calculator

- **FR-008**: System MUST refactor `ResourceFeatureCalculator` to accept a format configuration (total_overs, total_balls, par_score, phase boundaries, DLS table, wicket penalties, RRR midpoint, etc.) so that one parameterized class serves both T20 and ODI formats. ODI config uses `TOTAL_OVERS=50`, `TOTAL_BALLS=300`, and `PAR_SCORE` derived from empirical analysis.
- **FR-009**: System MUST define 4 ODI match phases: Powerplay (overs 1-10), Middle (overs 11-34), Setup (overs 35-40), Death (overs 41-50). These boundaries are used for wicket penalty tables, expected run rates, and phase-based features.
- **FR-010**: System MUST calculate `resource_win_prob` for ODI using ODI-calibrated SQI parameters, RRR midpoint, and confidence ramp values.
- **FR-011**: System MUST calculate `expected_final_score` with ODI-appropriate projected score ranges (approximately 100-500) and regression toward ODI par score.
- **FR-012**: System MUST calculate `pressure_index` using ODI-calibrated run rate and wicket thresholds.
- **FR-013**: System MUST apply wicket penalties only to future projected runs (not banked score), consistent with the T20 calculator's approach.

#### Pipeline Integration

- **FR-014**: System MUST add `odi` as a recognized league in the CLI with appropriate directory defaults (`odis_json`, `data/odi_raw`, `data/odi_features`, `data/odi_feature_store`, `models/odi_v1`).
- **FR-015**: System MUST support `bbl-pipeline retrain --league odi --version v1` executing the full pipeline: ingest → process → train → generate-oof → analyze-oof → update-registry.
- **FR-016**: Ingestion MUST correctly parse ODI JSON files (which use identical Cricsheet format but with `match_type=ODI` and `overs=50`) and include the `gender` field (male/female) in the ingested data. Matches before 2010 MUST be filtered out during processing. Matches with `info.overs < 50` (reduced-overs/DLS-affected) MUST be excluded.
- **FR-017**: Feature engineering MUST use 50-over phase boundaries, 300-ball totals, and ODI resource calculator when processing ODI data.
- **FR-018**: System MUST generate an ODI feature store (team ratings, player stats, venue stats) from the ODI dataset.
- **FR-019**: Rolling window features MUST be computed with the same ball-window sizes as T20 (6, 12, 18, 30 balls) plus optionally larger ODI-appropriate windows (e.g., 60 balls / 10 overs).

#### Model Training & Evaluation

- **FR-020**: System MUST train an `XGBLogRegEnsemble` model on ODI features, consistent with the T20 model architecture.
- **FR-021**: System MUST support OOF calibration analysis (Brier, ECE, LogLoss) with all calibration methods for the ODI model.
- **FR-022**: Model registry MUST be updated to include the ODI model entry with appropriate metadata.

### Key Entities

- **ODI Match**: A 50-over cricket match with two innings, up to 300 balls per innings. Contains teams, players, venue, toss, outcome. Can be male or female gender.
- **ODI Resource Table**: A mapping of (overs_remaining, wickets_lost) → resource_percentage for 50-over cricket, derived empirically from the dataset.
- **ODI Wicket Penalty Table**: A nested mapping of phase → ease_bucket → wickets_lost → penalty_multiplier, capturing how wickets affect projected scores in different ODI match situations.
- **ODI Phase**: A segment of an ODI innings — Powerplay (overs 1-10), Middle (overs 11-34), Setup (overs 35-40), Death (overs 41-50) — each with distinct scoring patterns and strategic considerations.
- **ODI Feature Store**: Team ratings, player stats, and venue stats computed from ODI match history for use in inference.

## Clarifications

### Session 2026-02-20

- Q: Should the model split by gender (separate constants/models for male vs female ODIs) or train combined? → A: Single combined model with gender-aware resource constants. The resource calculator uses gender-specific par scores, wicket penalty tables, and DLS tables. Gender is included as a training feature. One model, two sets of empirical constants.
- Q: Should the model use all eras equally or filter/weight by recency? → A: Cutoff year filter (2010+). Only include matches from 2010 onward for empirical constant derivation. This removes outdated scoring patterns while retaining sufficient data for robust analysis.
- Q: Should the ODI calculator be a separate class or a parameterized version of the existing T20 calculator? → A: Parameterized calculator. Refactor `ResourceFeatureCalculator` to accept a format config (total_overs, par_score, phases, DLS table, penalties) so one class serves both T20 and ODI. No code duplication.
- Q: How many phases should ODI use and what are the boundaries? → A: 4 phases — Powerplay (1-10), Middle (11-34), Setup (35-40), Death (41-50). This captures the consolidation period, the acceleration setup, and death-over scoring separately. Matches the T20 penalty table's 4-phase structure.
- Q: Should reduced-overs (DLS-affected) ODI matches be included in training? → A: Exclude them. Only train on matches where both innings had 50 overs available. This keeps training data clean and focused on full 50-over dynamics.

## Assumptions

1. **Combined male + female dataset with gender-aware constants**: The ODI files in `odis_json/` and `odis_female_json/` contain both male and female matches. The model trains on all of them together as a single `XGBLogRegEnsemble`, with `gender` included as a training feature. The resource calculator uses **gender-specific** empirical constants (separate par scores, wicket penalty tables, DLS resource tables for male vs female).
2. **Phase boundaries**: 4 phases — Powerplay (overs 1-10), Middle (overs 11-34), Setup (overs 35-40), Death (overs 41-50). This captures distinct ODI scoring dynamics: fielding restrictions in the powerplay, consolidation in the middle, acceleration in the setup phase, and slog/death batting.
3. **Par score**: Assumed ~250 for combined ODI data. Empirical analysis will provide the exact value.
4. **Bat-first win rate**: Assumed ~0.48-0.50 for ODIs (much closer to 50/50 than T20's 0.37). Empirical analysis will confirm.
5. **RRR midpoint**: Assumed ~6.0 for ODI second innings (vs T20's 9.5). Empirical analysis will calibrate.
6. **Era cutoff (2010+)**: Only matches from 2010 onward are used for empirical constant derivation (par scores, run rates, wicket penalties, DLS resource tables). The full dataset may still be ingested, but training features and resource constants are derived from modern-era matches only.
7. **Same model architecture**: The `XGBLogRegEnsemble` (50/50 XGBoost + Logistic Regression) architecture used for T20 is assumed sufficient for ODI. No architecture changes are planned.
8. **Parameterized calculator**: The existing `ResourceFeatureCalculator` will be refactored to accept a format config dict/dataclass. Existing T20 behavior is preserved by defaulting to T20 constants. ODI passes a different config. This avoids duplicating ~900 lines of calculator code and makes future formats (T10, The Hundred) trivial to add.
9. **Ingestion format compatibility**: ODI JSON files from Cricsheet use the identical ball-by-ball JSON structure as T20, just with `overs: 50` and `match_type: ODI`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Empirical analysis script processes all 3,085 ODI matches and produces a complete set of ODI-specific constants (par score, phase boundaries, resource table, wicket penalties, bat-first win rate) in under 10 minutes.
- **SC-002**: The ODI resource calculator produces win probabilities between 0.05 and 0.95 for typical ODI match states, with sensible monotonicity (win probability increases as batting team scores more / takes more wickets).
- **SC-003**: The full pipeline (`bbl-pipeline retrain --league odi --version v1`) completes end-to-end without errors, producing a trained model, calibrators, and an OOF calibration report.
- **SC-004**: The trained ODI model achieves a Brier score of 0.22 or lower on OOF evaluation (comparable to T20 models adjusted for ODI's longer format and higher variance).
- **SC-005**: ODI model predictions are correctly calibrated: ECE (10-bin) below 0.03 after calibration. *(Note: Constitution mandates ECE < 0.0021 for T20 betting-grade models. The relaxed 0.03 threshold is accepted for ODI v1 given the smaller dataset, mixed gender data, and exploratory nature of this first ODI model. Tighter calibration will be targeted in subsequent versions.)*
- **SC-006**: The ODI model handles both male and female matches without producing degenerate predictions (e.g., always predicting 0.5).
- **SC-007**: For a second-innings ODI chase, the model's win probability converges toward 1.0 or 0.0 as the match approaches conclusion, not remaining stuck at 0.5.
