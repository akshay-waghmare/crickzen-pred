# Feature Specification: NTB T20 Blast Standalone Model

**Feature Branch**: `feature/ntb-t20-blast-model`  
**Created**: 2026-06-06  
**Status**: Draft  
**Input**: User description: "Create a T20 Blast model using the BBL pipeline, just like IPL latest"

## User Scenarios & Testing

### User Story 1 - Train NTB T20 Blast Model via Pipeline (Priority: P1)

As a model trainer, I want to run `bbl-pipeline retrain --league ntb --version v1` to produce a standalone NTB T20 Blast model using the same 7-step pipeline used for IPL, BBL, PSL, and other leagues.

**Why this priority**: This is the core deliverable. Without a trained model, no predictions can be made for T20 Blast matches.

**Independent Test**: Run `bbl-pipeline retrain --league ntb --version v1` and verify `models/ntb_v1/champion_model.joblib` exists with valid OOF metrics.

**Acceptance Scenarios**:

1. **Given** `data/ntb_json/` contains 1,489 Cricsheet JSON files, **When** `bbl-pipeline retrain --league ntb --version v1` is run, **Then** the full 7-step pipeline completes (ingest, process, train, generate-oof, analyze-oof, calibrate-mc, update-registry)
2. **Given** the pipeline completes, **When** checking `models/ntb_v1/`, **Then** `champion_model.joblib`, `isotonic_calibrator.pkl`, and `champion_metadata.json` exist
3. **Given** the pipeline completes, **When** checking `models/model_registry.json`, **Then** `NTB` appears in `active_models` with valid Brier score

---

### User Story 2 - NTB Innings-2 Phase-Split Model (Priority: P2)

As a model trainer, I want to build an IPL-style phase-split model (PP/MID/DEATH) for NTB innings-2 predictions, using the same `XGBLRBlend` + per-over calibration architecture.

**Why this priority**: Phase-split models outperform single models for innings-2 predictions. This follows the proven IPL v17 pattern.

**Independent Test**: Run `python scripts/build_ntb_v1_phase_features.py` and verify phase-specific champion models are saved to `models/ntb_v1_phase/`.

**Acceptance Scenarios**:

1. **Given** NTB training data exists in `data/ntb_features_v1/training.parquet`, **When** the phase-split build script runs, **Then** `champion_model_pp.joblib`, `champion_model_mid.joblib`, `champion_model_death.joblib` are saved
2. **Given** phase models exist, **When** OOF evaluation runs, **Then** per-phase Brier scores are reported and `routing_config.json` is generated

---

### User Story 3 - NTB Live Prediction Integration (Priority: P3)

As a user, I want to use the NTB model for live match predictions via the existing predictor infrastructure.

**Why this priority**: Live prediction is the end goal but depends on P1 and P2 being complete first.

**Independent Test**: Load the NTB model via `Predictor` class and run a prediction on a sample NTB match state.

**Acceptance Scenarios**:

1. **Given** NTB model is registered in `model_registry.json`, **When** `Predictor` is instantiated with `model_dir=models/ntb_v1`, **Then** predictions return valid win probabilities

---

### Edge Cases

- What happens when NTB JSON files have missing or malformed innings data?
- How does the pipeline handle NTB matches with non-standard over counts (e.g., rain-affected)?
- What if some NTB venues have very few historical matches for venue-relative features?

## Requirements

### Functional Requirements

- **FR-001**: System MUST add `ntb` as a valid league choice in the `bbl-pipeline retrain` CLI command
- **FR-002**: System MUST configure NTB league config with `json_dir=data/ntb_json`, `format_type=t20`
- **FR-003**: System MUST add `NTB` to the model registry name mapping
- **FR-004**: System MUST produce a phase-split model following the IPL v17 architecture (PP/MID/DEATH)
- **FR-005**: System MUST use `XGBLRBlend` as the base model class for each phase
- **FR-006**: System MUST generate per-over isotonic calibrators for each phase
- **FR-007**: System MUST produce OOF and OOS evaluation metrics

### Key Entities

- **NTB Match Data**: 1,489 Cricsheet JSON files (2014-2026), 18 English county teams
- **NTB Feature Store**: Computed via `ResourceFeatureCalculator` with T20 format config
- **NTB Phase Models**: PP (overs 1-6), MID (overs 7-15), DEATH (overs 16-20)

## Success Criteria

### Measurable Outcomes

- **SC-001**: `bbl-pipeline retrain --league ntb --version v1` completes all 7 steps without errors
- **SC-002**: OOF Brier score < 0.25 (reasonable for a new league model)
- **SC-003**: Model registry updated with NTB entry including valid metrics
- **SC-004**: Phase-split model produces per-phase Brier scores with PP cell calibration
