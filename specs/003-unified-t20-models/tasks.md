# Tasks: Unified T20 Models

**Feature Branch**: `3-unified-t20-models`
**Feature Name**: "Unified T20 Models"
**Specification**: [spec.md](spec.md)

## Phase 1: Setup & Data Acquisition
*Goal: Secure valid source data for all leagues.*

- [x] T001 [US1] Run `python scripts/download_cricsheet_t20.py` to download raw data for all leagues
- [ ] T002 [P] [US1] Create validation script `scripts/validation/validate_league_jsons.py` to check JSON integrity and required fields
- [ ] T003 [US1] Run validation script and remove any corrupted files to ensure clean input

## Phase 2: Foundational (Ingestion Infrastructure)
*Goal: Upgrade pipeline to handle multi-league, multi-gender dataset.*

- [x] T004 [US2] Update `src/bbl_pipeline/ingestion/loader.py` to use `rglob` and yield parent directory name (league slug)
- [x] T005 [P] [US2] Update `src/bbl_pipeline/ingestion/processor.py` to accept and store `league_slug` in metadata
- [x] T006 [US2] Update `src/bbl_pipeline/ingestion/writer.py` to add `league`, `gender` to output schema
- [x] T007 [US2] Modify `ingest` command in `src/bbl_pipeline/cli.py` to handle recursive folder structures and pass league info to processor
- [ ] T008 [US2] Update `src/bbl_pipeline/processing/resolution.py` to handle unknown entities gracefully (auto-generate ID)

## Phase 3: Unified Data Processing
*Goal: Create raw and feature-engineered Parquet datasets.*

- [x] T009 [US2] Run ingestion for Male T20s: `bbl-pipeline ingest --input-dir data/t20_male_json --output-dir data/t20_male_raw`
- [x] T010 [US2] Run ingestion for Female T20s: `bbl-pipeline ingest --input-dir data/t20_female_json --output-dir data/t20_female_raw`
- [x] T011 [US2] Run feature processing for Male T20s to `data/t20_male_features_v1`
- [x] T012 [US2] Run feature processing for Female T20s to `data/t20_female_features_v1`

## Phase 4: Model Training (Unified)
*Goal: Train and validate unified models.*

- [x] T013 [US3] Train Unified Male Model: `bbl-pipeline train --input-dir data/t20_male_features_v1 --output-dir models/t20_male_v1`
- [x] T014 [US3] Generate OOF for Male Model: `bbl-pipeline generate-oof --model-dir models/t20_male_v1`
- [x] T015 [US3] Analyze OOF for Male Model: `bbl-pipeline analyze-oof --model-dir models/t20_male_v1`
- [x] T016 [P] [US3] Train Unified Female Model: `bbl-pipeline train --input-dir data/t20_female_features_v1 --output-dir models/t20_female_v1`
- [x] T017 [US3] Generate OOF for Female Model and analyze results

## Phase 5: Polish & Deployment
*Goal: Finalize artifacts and registry.*

- [x] T018 Update `models/model_registry.json` to include `t20_male_v1` and `t20_female_v1`
- [ ] T019 Update `README.md` with new model details and instructions
- [ ] T020 Delete old single-league models (optional/if needed)

## Dependencies
1. US1 (Download) blocks US2 (Ingestion)
2. US2 (Ingestion/Features) blocks US3 (Training)
3. Male/Female trainings are independent and parallelizable in Phase 3/4.

## Parallel Execution Opportunities
- T002 (Validation script) can be built while T001 (Download) runs.
- T005 & T006 (Processor/Writer updates) can be done in parallel by separate devs, though T007 (CLI) needs both.
- T013 (Train Male) and T016 (Train Female) can run simultaneously on separate GPUs/threads.
