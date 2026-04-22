# Feature Specification: PSL League Model (v1)

**Feature Branch**: `012-psl-model`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: Add PSL (Pakistan Super League) support with a dedicated trained model (`models/psl_v1`) and feature store (`data/psl_feature_store_v1`), following the same pipeline as IPL v6.

## Definitions

- **PSL v1**: The first dedicated Pakistan Super League win-probability model, trained exclusively on PSL historical data (2017–2026).
- **FormatConfig.psl()**: A PSL-specific scoring environment configuration derived empirically from PSL historical data (par score, run-rate expectations, wicket penalties).
- **Feature store (psl_feature_store_v1)**: The set of derived artefacts — team ratings, player rolling stats, venue stats — built from PSL historical data and used at inference time.
- **Retrain pipeline**: The end-to-end CLI workflow (`bbl-pipeline retrain --league psl --version v1`) that ingests raw JSON → Parquet, engineers features, trains the model, and generates OOF calibrators in one step.
- **League calibrator**: A post-hoc scaling layer applied on top of the base model output; trained against live-market odds to correct any systematic bias in PSL specifically.
- **Hyderabad Kingsmen**: A new PSL franchise added in 2026 that has no prior historical data in the training set.

## Current State

### What Already Exists ✅

- **`psl` in CLI league config**: `bbl-pipeline retrain --league psl --version v1` is already wired; paths resolve to `data/psl_raw`, `data/psl_features_v1`, `data/psl_feature_store_v1`, `models/psl_v1`.
- **`psl` in `update-matches`**: New match files can be copied from `psl_male_json/` (15 recent 2026 files).
- **PSL team abbreviations in feature store**: `TEAM_ABBREVIATIONS_PSL` in `store.py` covers all 7 teams including `HYK`/`HK` → "Hyderabad Kingsmen".
- **Streamlit live feeds configured**: "PSL ML+MC" and "PSL MC-only" entries exist but point to the global `models/t20_male_v2` as a placeholder.
- **Historical JSON data**: `psl_json/` contains 338 match files covering PSL 2017–2026.

### What Is Missing ❌

- **`FormatConfig.psl()`** does not exist; `from_league('psl')` currently falls back to the generic T20 defaults (`par_score=165.0`), which does not reflect PSL's actual scoring environment.
- **Trained `models/psl_v1`** does not exist.
- **`data/psl_feature_store_v1`** does not exist.
- **Model registry entry** for PSL under `active_models` does not exist.
- **Streamlit app** still references `models/t20_male_v2` for PSL feeds.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — PSL-Specific Win Probability Predictions (Priority: P1)

As a live-match analyst, I want win probability predictions for PSL matches to be based on a model trained on PSL data with PSL-specific scoring constants, so that the predictions reflect Pakistan Super League conditions rather than generic T20 averages.

**Why this priority**: The core deliverable. Without a dedicated PSL model the system either falls back to the global T20 model (which uses incorrect scoring environment constants) or cannot serve PSL predictions at all. Everything else in this feature is in support of this story.

**Independent Test**: Run the live predictor against a PSL 2026 match URL using `--model-dir models/psl_v1 --feature-store-dir data/psl_feature_store_v1 --league psl`. Verify that all 7 PSL teams (including Hyderabad Kingsmen) are resolved correctly, that the par score shown matches PSL historical averages, and that win probabilities change meaningfully ball-by-ball.

**Acceptance Scenarios**:

1. **Given** a live PSL 2026 match is in progress at over 8 of innings 1, **When** the predictor is invoked with the PSL v1 model and feature store, **Then** the displayed par score is derived from PSL historical data (not the generic T20 default of 165), and win probability is between 5% and 95%.
2. **Given** the batting team is "Hyderabad Kingsmen" (new 2026 franchise), **When** the predictor runs, **Then** the team name resolves without error (no "unknown team" warning), and the feature store falls back gracefully to league-average ratings for that team.
3. **Given** the PSL v1 model has been trained and calibrated, **When** a historical PSL match is replayed through the predictor, **Then** overall Brier score is at or below the generic T20 model baseline for the same matches.
4. **Given** the psl_json/ directory contains 338 match files, **When** `bbl-pipeline retrain --league psl --version v1` is run, **Then** it completes all 7 pipeline steps without error and produces `models/psl_v1/champion_model.joblib`, `oof_calibrators.pkl`, and `OOF_CALIBRATION_REPORT.md`.

---

### User Story 2 — PSL Scoring Environment Configuration (Priority: P1)

As a pipeline engineer, I want `FormatConfig.psl()` to encode PSL-specific scoring constants (par score, run-rate expectations, wicket penalties) derived empirically from historical PSL data, so that the feature engineering step produces accurate `resource_win_prob` and `score_vs_par` features that reflect PKL conditions.

**Why this priority**: Directly tied to P1 — incorrect scoring constants contaminate every training row and every live prediction. IPL saw measurable Brier improvements after switching from generic T20 constants to league-specific ones; PSL is expected to benefit similarly.

**Independent Test**: After deriving constants from PSL data, verify that `FormatConfig.psl().par_score` differs from `FormatConfig.t20().par_score` (165.0) by at least ±3 runs. Process the same PSL match with both configs; confirm that `score_vs_par` values differ meaningfully (> 2 runs average absolute difference).

**Acceptance Scenarios**:

1. **Given** `FormatConfig.from_league('psl')` is called, **When** the method executes, **Then** it returns a `FormatConfig` instance with PSL-specific par score — not the generic T20 default of 165.0.
2. **Given** PSL historical data is used to derive empirical run-rate and wicket-penalty tables, **When** features are computed using `FormatConfig.psl()`, **Then** the per-phase expected run rates differ from the generic T20 preset and are consistent with observed PSL averages.
3. **Given** the `from_league` dispatcher is updated, **When** any existing code calls `FormatConfig.from_league('psl')`, **Then** it receives the PSL config with no breaking changes to callers of `FormatConfig.t20()` or `FormatConfig.ipl()`.

---

### User Story 3 — Streamlit Live Prediction Dashboard for PSL (Priority: P2)

As a dashboard user, I want the "PSL ML+MC" tab in the Streamlit app to use the dedicated `models/psl_v1` model and `data/psl_feature_store_v1` feature store, rather than the global T20 model, so that PSL-season live predictions benefit from the PSL-specific calibration.

**Why this priority**: The Streamlit app is the primary user-facing interface for live predictions. Switching the PSL feeds from the global placeholder to the dedicated model is what makes the trained model visible to end-users.

**Independent Test**: Open the Streamlit app, select "PSL ML+MC" or "PSL MC-only" feed, point to a recorded PSL state file. Verify the displayed `model_dir` is `models/psl_v1` (not `models/t20_male_v2`) and that calibration chain shows PSL league calibrator in the output.

**Acceptance Scenarios**:

1. **Given** `models/psl_v1` and `data/psl_feature_store_v1` exist on disk, **When** the "PSL ML+MC" feed is selected in Streamlit, **Then** the backend predictor loads from `models/psl_v1` — not the global model — without any user configuration change.
2. **Given** Hyderabad Kingsmen is the batting team, **When** the Streamlit live feed updates, **Then** the team name displays correctly in the UI and no "unknown team" error appears.
3. **Given** the PSL MC-only and PSL ML+MC configs both reference `models/psl_v1`, **When** either feed is used, **Then** the displayed par score reflects PSL-derived constants.

---

### User Story 4 — Model Registry Update (Priority: P2)

As a pipeline maintainer, I want the PSL v1 model to be registered in `models/model_registry.json` under `active_models.PSL`, so that the canonical model path, feature store location, training metrics, and calibrator details are discoverable in one authoritative source.

**Why this priority**: The model registry is the single source of truth for active model paths. Without a PSL entry, tooling that reads the registry (automated reloads, CI checks, documentation generation) will not recognise PSL v1 as a deployed model.

**Independent Test**: After training, verify that `models/model_registry.json` contains an `active_models.PSL` key with correct `path`, `version`, `training.samples`, and `feature_store.path` fields. Confirm the values match the actual artefacts on disk.

**Acceptance Scenarios**:

1. **Given** `bbl-pipeline retrain --league psl --version v1` has completed successfully, **When** `models/model_registry.json` is read, **Then** an `active_models.PSL` entry exists with `path: "models/psl_v1"` and `version: "v1"`.
2. **Given** the registry entry exists, **When** the `feature_store.path` is read, **Then** it resolves to `data/psl_feature_store_v1` — a directory that exists on disk with `team_ratings.parquet`, `player_stats.parquet`, and `venue_stats.parquet`.
3. **Given** training metrics are available from the OOF analysis, **When** the registry entry is reviewed, **Then** it includes at minimum: `training.samples`, `training.date`, `training.brier_score`, and the calibration method used.

---

### Edge Cases

- **Hyderabad Kingsmen with no historical data**: The team joined PSL in 2026 after the training cut-off. The feature store must handle an unseen team by falling back to league-average team ratings rather than raising a KeyError.
- **Rawalpindiz naming inconsistency**: The team is stored as "Rawalpindiz" in historical Cricsheet data (a known quirk). The `TEAM_ABBREVIATIONS_PSL` mapping (`RWP`/`RPZ` → "Rawalpindiz") must be honoured consistently during training and inference so the team is not split into two identities.
- **PSL 2026 vs historical data split**: The 338 training files come from `psl_json/`; the 15 `psl_male_json/` files contain 2026 matches used only for `update-matches`. If `retrain` accidentally ingests from the wrong source directory, the model evaluation metrics will be inflated.
- **FormatConfig fallback when par score unavailable**: If a venue has no historical PSL venue stats in the feature store, the predictor must fall back to `FormatConfig.psl().par_score` — not the generic 165.0.
- **No league calibrator at first training**: PSL v1 will initially lack live-market calibration data. The registry entry and Streamlit config must work correctly using only the base model and OOF calibrators before any live-market league calibrator is trained.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a PSL-specific scoring environment configuration where `par_score`, per-phase expected run rates, and wicket penalties are derived empirically from PSL historical match data — not inherited from generic T20 defaults.
- **FR-002**: The retrain pipeline MUST accept `--league psl --version v1` and complete all 7 steps (ingest, process, train, generate-oof, analyze-oof, update-registry) using `psl_json/` as the source data (338 historical files, PSL 2017–2026).
- **FR-003**: The pipeline MUST produce a trained model at `models/psl_v1/champion_model.joblib` and OOF calibrators at `models/psl_v1/oof_calibrators.pkl` upon successful completion.
- **FR-004**: The feature store at `data/psl_feature_store_v1/` MUST contain `team_ratings.parquet`, `player_stats.parquet`, and `venue_stats.parquet` covering all PSL teams that appear in the training data.
- **FR-005**: The team "Hyderabad Kingsmen" MUST be recognised by its CREX abbreviations (`HYK`, `HK`) and, when absent from the feature store (new team), MUST fall back to league-average team ratings without raising an error.
- **FR-006**: `FormatConfig.from_league('psl')` MUST return the PSL-specific configuration; existing callers of `FormatConfig.t20()` and `FormatConfig.ipl()` MUST be unaffected.
- **FR-007**: The Streamlit "PSL ML+MC" and "PSL MC-only" live feed configurations MUST reference `models/psl_v1` and `data/psl_feature_store_v1` once the model exists on disk.
- **FR-008**: `models/model_registry.json` MUST contain an `active_models.PSL` entry with `path`, `version`, `training.samples`, `training.date`, `training.brier_score`, calibrator details, and `feature_store.path`.
- **FR-009**: Training MUST use `psl_json/` (338 full historical files) for the training dataset; `psl_male_json/` (15 recent files) MUST remain exclusively for the `update-matches` workflow.
- **FR-010**: The OOF calibration analysis report (`models/psl_v1/OOF_CALIBRATION_REPORT.md`) MUST be generated during `retrain`, listing Brier, ECE, and LogLoss by segment (overall, innings, phase).

### Key Entities

- **PSL Model `psl_v1`**: Trained `XGBLogRegEnsemble` (25 features) plus per-over Brier-optimised OOF calibrators. Artefacts: `champion_model.joblib`, `oof_calibrators.pkl`, `OOF_CALIBRATION_REPORT.md`. Optional: `league_calibrators/psl/` after live-match data is available.
- **PSL Feature Store `psl_feature_store_v1`**: Three Parquet artefacts covering team win rates (overall, bat-first, bowl-first), player rolling averages, and venue scoring statistics — all derived exclusively from PSL match data.
- **PSL FormatConfig**: A league-specific `FormatConfig` instance holding PSL par score, per-phase run-rate expectations, first-innings wicket penalties, and chase parameters, derived from the PSL training dataset.
- **PSL Team Registry**: The set of 7 PSL teams (Islamabad United, Karachi Kings, Lahore Qalandars, Multan Sultans, Peshawar Zalmi, Quetta Gladiators, Hyderabad Kingsmen) with their CREX abbreviation mappings and default ratings for any team absent from the feature store.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The `bbl-pipeline retrain --league psl --version v1` command completes without errors and all required model artefacts exist on disk afterwards.
- **SC-002**: PSL v1 Brier score (OOF 5-fold CV) is below 0.200 overall — consistent with other league-specific models trained on equivalent data volumes.
- **SC-003**: PSL v1 OOF Brier score is lower than the equivalent score produced by applying the global `models/t20_male_v2` with generic T20 config to the same PSL training data, demonstrating that PSL-specific constants add value.
- **SC-004**: `FormatConfig.psl().par_score` differs from `FormatConfig.t20().par_score` (165.0) — confirming that empirically derived PSL constants have been applied.
- **SC-005**: All 7 PSL teams are present in `data/psl_feature_store_v1/team_ratings.parquet` except Hyderabad Kingsmen (new 2026 franchise), which falls back to league-average ratings without raising errors during inference.
- **SC-006**: `models/model_registry.json` contains a complete `active_models.PSL` entry readable by any tooling that consumes the registry, with no null or placeholder values in mandatory fields.
- **SC-007**: The Streamlit app's "PSL ML+MC" feed, when loaded against a recorded PSL match state, displays predictions sourced from `models/psl_v1` — not the global T20 model — as confirmed by the calibration chain shown in the output.

---

## Assumptions

- The 338 files in `psl_json/` are sufficient to produce a stable model. PSL has 8–10 games per team per season; 338 historical matches is comparable to the ILT20 (99 matches) and SA20 (121 matches) datasets that produced acceptable models.
- PSL scoring constants will be derived by running `scripts/derive_ipl_improvements.py` (or an equivalent analysis script) against the PSL training rows — the same empirical derivation method as IPL v6.
- No live-market calibration data (league calibrator) is available at v1 launch. The model will ship with OOF calibrators only; a league calibrator will be trained once live PSL matches are recorded.
- Rawalpindiz appears as a PSL team with an intentional spelling quirk in Cricsheet data; no data-cleansing rename is required — the existing abbreviation mapping is sufficient.
- The retrain pipeline uses `psl_json/` (historical archive) as source; `psl_male_json/` is treated as the "recently played" update source per the existing `update-matches` convention.

## Dependencies

- `psl_json/` must be present with 338 match files before running the retrain.
- `scripts/derive_ipl_improvements.py` (or equivalent PSL analysis script) must be run to derive empirical FormatConfig constants before finalising `FormatConfig.psl()`.
- `bbl-pipeline update-registry` (run automatically as part of `retrain`) must succeed to write the model registry entry.
