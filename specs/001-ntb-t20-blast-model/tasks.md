# Tasks: NTB T20 Blast Model

**Input**: Design documents from `/specs/001-ntb-t20-blast-model/`
**Prerequisites**: plan.md (required), spec.md (required)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (CLI Configuration)

**Purpose**: Add NTB as a valid league to the BBL pipeline CLI

- [ ] T001 [US1] Add `ntb` to `click.Choice` list in `src/bbl_pipeline/cli.py:1419`
- [ ] T002 [US1] Add NTB league config dict in `src/bbl_pipeline/cli.py:1446-1575`
- [ ] T003 [US1] Add `NTB` to `registry_league_names` mapping in `src/bbl_pipeline/cli.py:1713-1727`

**Checkpoint**: `bbl-pipeline retrain --help` shows `ntb` as a valid league choice

---

## Phase 2: Base Model Training (US1 - P1 MVP)

**Purpose**: Run the 7-step retrain pipeline to produce NTB base model

- [ ] T004 [US1] Run `bbl-pipeline retrain --league ntb --version v1`
- [ ] T005 [US1] Verify `models/ntb_v1/champion_model.joblib` exists
- [ ] T006 [US1] Verify `models/model_registry.json` contains NTB entry
- [ ] T007 [US1] Review OOF Brier score and calibration report

**Checkpoint**: NTB base model trained and registered with valid metrics

---

## Phase 3: Phase-Split Model (US2 - P2)

**Purpose**: Build IPL v17-style PP/MID/DEATH phase-split model for innings-2

- [ ] T008 [P] [US2] Create `scripts/build_ntb_v1_phase_features.py` following IPL v17 pattern
- [ ] T009 [US2] Run phase-split build script
- [ ] T010 [US2] Verify `models/ntb_v1_phase/champion_model_{pp,mid,death}.joblib` exist
- [ ] T011 [US2] Review per-phase OOF Brier scores

**Checkpoint**: Phase-split model trained with per-phase calibration

---

## Phase 4: Polish & Validation

**Purpose**: Validate end-to-end functionality

- [ ] T012 [US3] Test predictor loads NTB model successfully
- [ ] T013 Verify all artifacts in `models/ntb_v1/` and `models/ntb_v1_phase/`

---

## Dependencies & Execution Order

- **Phase 1**: No dependencies - start immediately
- **Phase 2**: Depends on Phase 1 (CLI config)
- **Phase 3**: Depends on Phase 2 (needs base features from `data/ntb_features_v1/`)
- **Phase 4**: Depends on Phase 2 and Phase 3

### Within Each Phase

- T001, T002, T003 are in the same file - sequential edits
- T004 blocks T005, T006, T007
- T008 can be written in parallel with T004, but T009 depends on T004

---

## Implementation Strategy

### MVP First (Phase 1 + Phase 2)

1. Complete Phase 1: CLI configuration
2. Complete Phase 2: Run retrain pipeline
3. **STOP and VALIDATE**: Check OOF report and model registry
4. Deploy if ready

### Incremental Delivery

1. Phase 1 + Phase 2 → Base model ready
2. Phase 3 → Phase-split model for improved inn2 predictions
3. Phase 4 → Integration validation

---

## Notes

- NTB data already exists at `data/ntb_json/` (1,489 matches)
- Processor already maps "T20 Blast" to "ntb" slug
- Format type is T20 (20 overs, 10 wickets)
- Season range: 2014-2026 (use 2025+ as OOS test set)
