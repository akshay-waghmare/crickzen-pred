# Implementation Tasks: Initial Data Ingestion & Processing Pipeline (BBL)

**Feature Branch**: `001-bbl-data-pipeline`
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

## Phase 1: Setup & Infrastructure
*Goal: Initialize project structure, dependencies, and core utilities.*

- [x] T001 Create project directory structure (src layout, tests, config)
- [x] T002 Create `pyproject.toml` with dependencies (pandas, pyarrow, pandera, rapidfuzz, click, structlog, pyyaml)
- [x] T003 Implement structured logging setup in `src/bbl_pipeline/utils/logging.py`
- [x] T004 Implement configuration loader in `src/bbl_pipeline/config.py`
- [x] T005 Implement configurable error handling policies in `src/bbl_pipeline/utils/errors.py`

## Phase 2: Foundational Components
*Goal: Define data schemas and registry structures required by all user stories.*

- [x] T006 Define Pandera schemas for match data in `src/bbl_pipeline/validation/schema.py`
- [x] T007 Create initial empty `config/entity_registry.yaml`
- [x] T008 Implement Entity Registry loader and accessors in `src/bbl_pipeline/processing/registry.py`

## Phase 3: User Story 1 - Ingest Historical BBL Data
*Goal: Parse JSON, process in chunks, and write to Parquet.*

- [x] T009 Implement JSON loader to parse Cricsheet files in `src/bbl_pipeline/ingestion/loader.py`
- [x] T010 [US1] Implement chunked processing logic (flattening ball-by-ball data) and **Super Over separation** in `src/bbl_pipeline/ingestion/processor.py`
- [x] T011 [US1] Implement Parquet writer with season partitioning and **provenance metadata** in `src/bbl_pipeline/ingestion/writer.py`
- [x] T024 [US1] Implement incremental state tracking (file hashes/timestamps) in `src/bbl_pipeline/ingestion/state.py`
- [x] T012 [US1] Implement CLI `ingest` command and **summary reporting** in `src/bbl_pipeline/cli.py`
- [x] T013 [US1] Add unit tests for JSON loading and processing in `tests/unit/test_ingestion.py`

## Phase 4: User Story 2 - Normalize Entity Names
*Goal: Integrate RapidFuzz for entity resolution and update registry.*

- [x] T014 [US2] Implement fuzzy matching logic using RapidFuzz in `src/bbl_pipeline/processing/resolution.py`
- [x] T015 [US2] Integrate resolution step into `ingestion/processor.py` to map names to IDs
- [x] T016 [US2] Implement CLI `resolve` command to scan for new entities in `src/bbl_pipeline/cli.py`
- [x] T017 [US2] Add unit tests for fuzzy matching and resolution in `tests/unit/test_resolution.py`

## Phase 5: User Story 3 - Rapid Retraining & Workflow
*Goal: Validation, compaction, and advanced pipeline features.*

- [x] T018 [US3] Implement CLI `validate` command using Pandera schemas in `src/bbl_pipeline/cli.py`
- [x] T019 [US3] Implement Parquet file compactor in `src/bbl_pipeline/ingestion/compactor.py`
- [x] T020 [US3] Implement schema migration scaffolding in `src/bbl_pipeline/ingestion/migration.py`
- [x] T021 [US3] Add integration tests for full pipeline flow in `tests/integration/test_pipeline.py`

## Phase 6: Polish & Documentation
*Goal: Finalize documentation and ensure quality.*

- [x] T022 Update `README.md` and `quickstart.md` with usage instructions
- [x] T023 Run full test suite and verify coverage

## Dependencies

- **US1 (Ingestion)** depends on Phase 1 & 2.
- **US2 (Resolution)** depends on US1 (needs data to resolve).
- **US3 (Workflow)** depends on US1 & US2.

## Implementation Strategy

1.  **MVP**: Complete Phase 1, 2, and 3 to get raw data into Parquet.
2.  **Integrity**: Add Phase 4 to ensure entities are normalized.
3.  **Robustness**: Add Phase 5 for validation and optimization.
