# Implementation Plan: NTB T20 Blast Model

**Branch**: `feature/ntb-t20-blast-model` | **Date**: 2026-06-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-ntb-t20-blast-model/spec.md`

## Summary

Add NTB (NatWest T20 Blast) as a standalone league to the BBL pipeline, train a base model via the 7-step retrain pipeline, then build an IPL v17-style phase-split model for innings-2 predictions.

## Technical Context

**Language/Version**: Python 3.10+  
**Primary Dependencies**: bbl_pipeline (XGBLRBlend, ResourceFeatureCalculator, IsotonicRegression)  
**Storage**: Parquet files, joblib models, JSON configs  
**Testing**: Manual pipeline execution + OOF/OOS metrics  
**Target Platform**: Local development (Windows)  
**Project Type**: Single project (ML pipeline)  
**Performance Goals**: OOF Brier < 0.25  
**Constraints**: 1,489 matches (2014-2026), 18 county teams  
**Scale/Scope**: ~50k innings-2 rows expected

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Tournament-agnostic)**: PASS - Using existing pipeline with config-only changes
- **Principle II (Pipeline-driven)**: PASS - Using standard 7-step retrain command
- **Principle III (Reproducibility)**: PASS - Versioned directories (ntb_v1)
- **Principle IV (Data integrity)**: PASS - Entity registry already maps "T20 Blast" to "ntb"
- **Principle V (Calibration)**: PASS - Per-over isotonic calibration following IPL pattern

## Project Structure

### Documentation (this feature)

```text
specs/001-ntb-t20-blast-model/
├── plan.md              # This file
├── spec.md              # Feature specification
└── tasks.md             # Task list
```

### Source Code (repository root)

```text
src/bbl_pipeline/
├── cli.py               # Add 'ntb' to retrain league choices + config

scripts/
├── build_ntb_v1_phase_features.py   # Phase-split model build script

models/
├── ntb_v1/              # Base model (from retrain pipeline)
├── ntb_v1_phase/        # Phase-split model (PP/MID/DEATH)

data/
├── ntb_json/            # Source data (1,489 JSON files - exists)
├── ntb_raw/             # Ingested parquet (generated)
├── ntb_features_v1/     # Features (generated)
├── ntb_feature_store_v1/ # Feature store (generated)
```

**Structure Decision**: Single project, config-only changes to CLI, new script for phase-split model following IPL v17 pattern.

## Complexity Tracking

No constitution violations. This is a straightforward league addition following the established pattern used for PSL, BBL, and other leagues.
