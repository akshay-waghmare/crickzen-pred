# Tasks: PSL Model v1 (012-psl-model)

**Input**: `specs/012-psl-model/plan.md`, `specs/012-psl-model/spec.md`
**Feature Branch**: `012-psl-model`
**Date**: 2026-04-22

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on in-progress tasks)
- **[Story]**: User story this task belongs to (US1–US4 map to spec.md priorities)
- Exact file paths are included in all descriptions

---

## Phase 1: Setup (Pre-flight Verification)

**Purpose**: Confirm data preconditions before any code changes. All checks are read-only.

- [ ] T001 Verify `psl_json/` contains 338 match files (`Get-ChildItem psl_json -Filter "*.json" | Measure-Object`)
- [ ] T002 [P] Verify `psl_male_json/` contains ~15 files and is separate from the training archive
- [ ] T003 [P] Confirm `models/psl_v1` and `data/psl_feature_store_v1` do not yet exist on disk

**Checkpoint**: Data preconditions confirmed — code changes can begin.

---

## Phase 2: Foundational (Critical Blocker)

**Purpose**: Fix the one-line CLI bug that points PSL retrain at 15 recent files instead of the 338-file historical archive. This **blocks all user stories** — no pipeline run is valid until this is fixed.

⚠️ **CRITICAL**: Do not run `bbl-pipeline retrain` until T004 is complete.

- [ ] T004 Fix `json_dir` for PSL in `src/bbl_pipeline/cli.py` (line ≈1503): change `'psl_male_json'` → `'psl_json'` so retrain ingests all 338 historical files (FR-009)

**Checkpoint**: After T004, `bbl-pipeline retrain --league psl --version v1` will ingest the correct 338-file archive. User story phases can now proceed.

---

## Phase 3: User Story 2 — PSL Scoring Environment Configuration (Priority: P1)

**Goal**: Add `FormatConfig.psl()` with empirically derived PSL scoring constants so feature engineering produces accurate `resource_win_prob` and `score_vs_par` values.

**Independent Test**: `FormatConfig.from_league('psl').par_score != 165.0` — PSL par score must differ from the generic T20 default by at least 3 runs (SC-004). Callers of `FormatConfig.t20()` and `FormatConfig.ipl()` must be unaffected (FR-006).

- [ ] T005 [US2] Run initial ingestion and processing to produce `data/psl_features_v1/training.parquet`: `bbl-pipeline ingest --input-dir psl_json --output-dir data/psl_raw` then `bbl-pipeline process --input-dir data/psl_raw/matches --output-dir data/psl_features_v1 --feature-store-dir data/psl_feature_store_v1 --league psl` (expected to use T20 defaults at this stage — that is acceptable)
- [ ] T006 [US2] Derive PSL empirical constants from `data/psl_features_v1/training.parquet` by running `scripts/derive_ipl_improvements.py` pointed at PSL data (or copy it to `scripts/derive_psl_improvements.py` and update `DATA_PATH` / `OUTPUT_PY` if the script does not accept CLI args); review output `scripts/psl_derived_tables.py` for `par_score`, `league_avg_score`, `bat_first_win_rate`, per-phase run rates, and `first_innings_wicket_penalty_3d`
- [ ] T007 [US2] Add `FormatConfig.psl()` classmethod to `src/bbl_pipeline/features/format_config.py` immediately after the `ipl()` classmethod (line ≈331), using the `replace(base, ...)` pattern with values from `scripts/psl_derived_tables.py`; fill `par_score`, `league_avg_score`, `bat_first_win_rate`, `expected_run_rates`, `first_innings_score_midpoint`, and `first_innings_wicket_penalty_3d`; set `rrr_midpoint_slope=0.0` if per-over sigmoid fit is unreliable
- [ ] T008 [US2] Update `from_league` dispatcher in `src/bbl_pipeline/features/format_config.py` (line ≈884) to add `if league == "psl": return cls.psl()` immediately after the `ipl` branch (FR-006)

**Checkpoint**: `FormatConfig.from_league('psl').par_score` returns PSL-derived value ≠ 165.0. Other league configs unchanged.

---

## Phase 4: User Story 1 — PSL-Specific Win Probability Model (Priority: P1) 🎯 MVP

**Goal**: Run the end-to-end retrain pipeline to produce a trained `models/psl_v1` with all required artefacts, using PSL-specific scoring constants from Phase 3.

**Independent Test**: Run `python -m src.bbl_pipeline.inference.crex_live_predictor --match-url <PSL_URL> --model-dir models/psl_v1 --feature-store-dir data/psl_feature_store_v1 --league psl` and verify: all 7 teams resolve (including Hyderabad Kingsmen via fallback), displayed par score matches `FormatConfig.psl().par_score`, win probability is in range 5–95%.

- [ ] T009 [US1] Run `bbl-pipeline retrain --league psl --version v1` and confirm console shows `📁 Found 338 JSON files in psl_json` at start; allow ~30 min for all 7 pipeline steps (ingest → process → train → generate-oof → analyze-oof → calibrate-mc → update-registry)
- [ ] T010 [US1] Validate model artefacts exist: `models/psl_v1/champion_model.joblib`, `models/psl_v1/oof_calibrators.pkl`, `models/psl_v1/OOF_CALIBRATION_REPORT.md` (FR-003, FR-010)
- [ ] T011 [US1] Validate feature store artefacts exist: `data/psl_feature_store_v1/team_ratings.parquet`, `data/psl_feature_store_v1/player_stats.parquet`, `data/psl_feature_store_v1/venue_stats.parquet` (FR-004)
- [ ] T012 [US1] Verify OOF Brier score < 0.200 from `models/psl_v1/oof_calibration_results.csv` (SC-002) and confirm Hyderabad Kingsmen fallback: call `FeatureStore.load('data/psl_feature_store_v1').get_team_rating('Hyderabad Kingsmen', fallback_to_average=True)` returns league-average rating without `KeyError` (FR-005, SC-005); if `fallback_to_average` is not yet supported in `src/bbl_pipeline/features/store.py`, add a guard that returns mean of all known team ratings when the team key is missing

**Checkpoint**: `models/psl_v1` fully trained, validated, and capable of serving PSL live predictions. US1 independently functional.

---

## Phase 5: User Story 3 — Streamlit PSL Live Feed (Priority: P2)

**Goal**: Point the existing "PSL ML+MC" and "PSL MC-only" Streamlit feed configs to `models/psl_v1` instead of the global T20 placeholder.

**Independent Test**: Launch `streamlit run src/bbl_pipeline/app/live_streamlit_app.py`, select "PSL ML+MC", load a recorded PSL state file. Verify `model_dir` shown is `models/psl_v1` (not `t20_male_v2`), par score reflects PSL-derived constants, and Hyderabad Kingsmen renders correctly with no "unknown team" warning (SC-007, FR-007).

- [ ] T013 [US3] In `src/bbl_pipeline/app/live_streamlit_app.py` (lines ≈482–498), change `"model_dir": "models/t20_male_v2"` to `"model_dir": "models/psl_v1"` for both the "PSL ML+MC" and "PSL MC-only" feed entries (FR-007); leave `"feature_store_dir": "data/psl_feature_store_v1"` and `"league": "psl"` unchanged

**Checkpoint**: PSL Streamlit feeds load from `models/psl_v1`. US3 independently functional.

---

## Phase 6: User Story 4 — Model Registry Entry (Priority: P2)

**Goal**: Ensure `models/model_registry.json` contains a complete, accurate `active_models.PSL` entry with no null or placeholder values.

**Independent Test**: `json.load(open('models/model_registry.json'))['active_models']['PSL']` contains `path == "models/psl_v1"`, `version == "v1"`, `training.samples > 0`, `feature_store.path == "data/psl_feature_store_v1"` (SC-006, FR-008).

- [ ] T014 [US4] Verify the auto-generated `active_models.PSL` entry in `models/model_registry.json` after retrain: confirm `path`, `version`, and `training.samples` were written correctly by Step 7 of `retrain` (note: `registry_league_names.get('psl', 'psl'.upper())` should produce `'PSL'` — verify the key name)
- [ ] T015 [US4] Manually complete any missing fields in the `active_models.PSL` entry in `models/model_registry.json`: fill `training.matches` (338), `training.date`, `training.brier_score` (from OOF results), `calibrator.type` (`per_over_brier_optimized`), `calibrator.n_calibrators`, `feature_store.statistics.teams` (6), `feature_store.statistics.players`, `feature_store.statistics.venues`, and add `notes` documenting no league calibrator at v1 launch and HYK fallback behaviour (FR-008)

**Checkpoint**: Registry entry complete and machine-readable. US4 independently functional.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Regression verification and SC-003 baseline comparison.

- [ ] T016 [P] Run `FormatConfig` smoke tests: assert `psl.par_score != t20.par_score`, `psl.par_score != ipl.par_score`, `from_league('psl').par_score == psl.par_score`, `from_league('t20')` and `from_league('ipl')` unchanged (SC-004, FR-006) — commands in `plan.md` § 7.1
- [ ] T017 Run existing test suite `python -m pytest tests/ -x -q` to confirm no regressions in `FormatConfig`, `from_league` dispatch, or feature store tests
- [ ] T018 [P] Run SC-003 baseline comparison: load `data/psl_features_v1/training.parquet`, compare Brier of `models/psl_v1` vs `models/t20_male_v2` on PSL data using script in `plan.md` § 7.3; assert PSL v1 Brier < global T20 Brier on same data

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)          → No dependencies. Run immediately.
Phase 2 (Foundational)   → Depends on Phase 1 confirmation. BLOCKS all user stories.
Phase 3 (US2)            → Depends on Phase 2 (CLI fix must precede ingestion).
Phase 4 (US1)            → Depends on Phase 3 (FormatConfig.psl() must exist before retrain).
Phase 5 (US3)            → Depends on Phase 4 (models/psl_v1 must exist on disk).
Phase 6 (US4)            → Depends on Phase 4 (retrain must have run for registry data).
Final Phase              → Depends on Phases 3 + 4 + 5 + 6 all complete.
```

### User Story Dependencies

| Story | Depends On | Can Proceed After |
|-------|-----------|-------------------|
| **US2 (P1)** — FormatConfig | Phase 2 (CLI fix) | T004 complete |
| **US1 (P1)** — Trained model | US2 complete | T008 complete |
| **US3 (P2)** — Streamlit | US1 complete | T012 complete |
| **US4 (P2)** — Registry | US1 complete | T012 complete |

**US3 and US4 can execute in parallel once US1 is complete.**

### Within Each Phase

- Feature derivation (T006) must complete before writing `FormatConfig.psl()` (T007)
- `FormatConfig.psl()` (T007) must exist before updating `from_league` (T008)
- Retrain (T009) must complete before validation tasks T010–T012
- T014 (verify auto-written entry) before T015 (manual completion)

---

## Parallel Opportunities

### Phase 1

T002 and T003 can run in parallel with T001.

### Phase 5 + Phase 6

Once T012 (retrain validated) is done, T013 (Streamlit) and T014 (Registry verify) can run in parallel:

```
T012 ──┬── T013 (US3 Streamlit update)
       └── T014 → T015 (US4 Registry completion)
```

### Final Phase

T016, T017, T018 can run in parallel once all implementation phases are complete.

---

## MVP Scope

**US1 + US2 only** (Phases 1–4) is the minimum deliverable — a trained `models/psl_v1` backed by PSL-specific scoring constants and reachable via the live predictor CLI. US3 (Streamlit) and US4 (Registry) polish the handoff to end-users and tooling but are not required for the model to function.

**Total tasks**: 18  
**Task count by story**: US2 → 4, US1 → 4, US3 → 1, US4 → 2, Setup/Foundation/Polish → 7  
**Parallel opportunities**: Phases 5+6 (after T012), Final Phase (all 3 tasks), Phase 1 (T002+T003)
