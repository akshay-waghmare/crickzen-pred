# Tasks: IPL Model Improvement — Close Market Gap

**Input**: Design documents from `specs/001-ipl-market-gap/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Included — the spec defines explicit test files in `tests/unit/` and `tests/integration/` (plan.md project structure).

**Organization**: Tasks are grouped by user story. User Stories 1–3 (P1/P2) can proceed in parallel after Foundational phase. User Stories 4–5 (P2/P3) depend on Phase 1 stories. User Story 6 (P3) depends on all prior stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/bbl_pipeline/` package at repository root
- **Tests**: `tests/unit/`, `tests/integration/`
- **Scripts**: `scripts/` at repository root
- **Config**: `config/` at repository root
- **Data**: `data/` at repository root (read-only source data; regenerated feature stores)

---

## Phase 1: Setup (Baseline & Environment)

**Purpose**: Prepare the working branch and verify baseline measurements before any model changes.

- [x] T001 Create feature branch `001-ipl-market-gap` from main and verify clean test run with `pytest tests/ -v`
- [x] T002 Run baseline validation `python scripts/analyze_ipl_model_vs_market.py` and record baseline Brier scores (overall: 0.1977, per-segment) in a baseline snapshot file at `data/ipl_baseline_brier.json`
- [x] T003 [P] Verify training data availability: confirm `data/ipl_features_v1/training.parquet` has 273,503 rows and `data/ipl_model_vs_market.parquet` has 510 observations
- [x] T004 [P] Verify Cricsheet IPL JSON files exist in `ipl_male_json/` directory for final-over derivation (US2)

**Checkpoint**: Baseline measured, data verified — implementation can begin.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core shared infrastructure changes that MUST complete before any user story work. These include derivation scripts that produce the data artifacts consumed by multiple stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T005 Add RCB/DC/PBKS/RPS canonical team name mappings to `config/entity_registry.yaml` per research.md R-003 mapping table (Royal Challengers Bangalore ↔ Bengaluru, Delhi Capitals ↔ Daredevils, Punjab Kings ↔ Kings XI Punjab, Rising Pune Supergiant ↔ Supergiants)
- [x] T006 [P] Create IPL wicket penalty derivation script at `scripts/derive_ipl_wicket_penalties.py` — reads `data/ipl_features_v1/training.parquet`, groups 2nd-innings rows by `wickets_lost × phase × chase_ease` and 1st-innings rows by `wickets_lost × phase × ease_bucket`, computes empirical win rates per cell with min 30 observations, smooths sparse cells from adjacent cells, outputs both `chase_wicket_penalty_2d` and `first_innings_wicket_penalty_3d` dicts as JSON to `data/ipl_derived_penalties.json`
- [x] T007 [P] Create final-over lookup derivation script at `scripts/derive_final_over_lookup.py` — parses all IPL Cricsheet JSON files in `ipl_male_json/`, filters to 2nd-innings final over (over == 20), groups by `runs_needed × wickets_in_hand`, computes empirical win rates, fills sparse cells via monotonic interpolation (prob decreases with runs_needed, increases with wickets_in_hand), enforces boundary conditions (runs=0→1.0, wickets=0→0.0, runs>20+wickets≤2→0.0), outputs Python dict literal to `data/ipl_final_over_lookup.json`
- [x] T008 [P] Create recency-weighted team ratings regeneration script at `scripts/regenerate_ipl_feature_store.py` — reads existing `data/ipl_feature_store_v1/team_ratings.parquet`, applies exponential decay with half-life=2.5 seasons (λ=0.277), deduplicates team names using canonical mappings from `config/entity_registry.yaml`, outputs new `data/ipl_feature_store_v1/team_ratings.parquet` with schema: team, win_rate, matches, effective_matches, bat_first_wr, bowl_first_wr, half_life_seasons, last_updated
- [x] T009 Run `python scripts/derive_ipl_wicket_penalties.py` and verify output penalties for wickets 4–8 are strictly lower than T20 base values (FR-002 validation)
- [x] T010 Run `python scripts/derive_final_over_lookup.py` and verify lookup table dimensions (runs 0–25 × wickets 0–10), monotonicity constraints, and boundary conditions
- [x] T011 Run `python scripts/regenerate_ipl_feature_store.py` and verify: no duplicate team names, all canonical teams present, 0.0 < win_rate < 1.0, effective_matches > 0

**Checkpoint**: All derived data artifacts ready — penalty tables, final-over lookup, and recency-weighted team ratings validated. User story implementation can now begin.

---

## Phase 3: User Story 1 — Accurate Wicket-Heavy Chase Predictions (Priority: P1) 🎯 MVP

**Goal**: Replace the T20-generic wicket penalty tables with IPL-specific empirical penalties derived from 273K training rows. Every penalty for 4–8 wickets must be strictly harsher than the current value.

**Independent Test**: Run validation script filtered to 4–8 wickets lost in 2nd innings. Brier score per wicket bucket must improve; 8-wicket gap must drop from +0.220 to ≤ +0.110.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T012 [P] [US1] Create unit test file at `tests/unit/test_ipl_wicket_penalties.py` — test that `FormatConfig.ipl().chase_wicket_penalty_2d` returns penalties where every value for wickets 4–8 across all ease levels is strictly less than `FormatConfig.t20().chase_wicket_penalty_2d` (FR-002); test monotonic decrease with wickets_lost; test penalty[any][10] == 0.0; test penalty[any][0] == 1.0; test `first_innings_wicket_penalty_3d` same constraints per contracts/format_config_ipl.py

### Implementation for User Story 1

- [x] T013 [US1] Update `FormatConfig.ipl()` factory method in `src/bbl_pipeline/features/format_config.py` (around L321–341) to override `chase_wicket_penalty_2d` with IPL-specific penalty dict derived in T009, ensuring all structural invariants pass `__post_init__()` validation — use the 5 ease levels × 11 wickets structure matching `CHASE_PENALTY_CONTRACT` in contracts/format_config_ipl.py
- [x] T014 [US1] Update `FormatConfig.ipl()` factory method in `src/bbl_pipeline/features/format_config.py` to override `first_innings_wicket_penalty_3d` with IPL-specific 3D penalty dict (phase × ease_bucket × wickets) derived in T009, matching `FIRST_INNINGS_PENALTY_CONTRACT` structure
- [x] T015 [US1] Validate by running `python scripts/analyze_ipl_model_vs_market.py` and confirm: wicket buckets 4–5 Brier gap reduced from +0.0802 to < +0.040; wicket bucket 6+ gap reduced from +0.0577 to < +0.029; no segment regresses by > 0.005

**Checkpoint**: User Story 1 complete — wicket-heavy chase predictions significantly improved. Brier gap for 8-wicket scenarios reduced by ≥50%.

---

## Phase 4: User Story 2 — Reliable Final-Over Predictions (Priority: P1)

**Goal**: Replace the sigmoid approximation for final-over (over 20) 2nd-innings predictions with an empirical lookup table mapping runs_needed × wickets_in_hand → win probability.

**Independent Test**: Evaluate over-20 2nd-innings Brier score. Gap must drop from +0.170 to < +0.050.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T016 [P] [US2] Create unit test file at `tests/unit/test_final_over_lookup.py` — test `get_final_over_win_prob()` returns 1.0 when runs_needed=0; returns 0.0 when wickets_in_hand=0; returns near-zero for runs>20 with wickets≤2; returns 0.01 for runs>25; test monotonic decrease on runs axis (fixed wickets); test monotonic increase on wickets axis (fixed runs); test interpolation for sparse cells per contracts/final_over_lookup.py

### Implementation for User Story 2

- [x] T017 [US2] Add the `FINAL_OVER_WIN_PROB` empirical lookup table dict (from T010 derived data) and `get_final_over_win_prob(runs_needed, wickets_in_hand, lookup_table)` function to `src/bbl_pipeline/features/win_prob_lookup_tables.py` — implement the lookup function per contracts/final_over_lookup.py: boundary checks → table lookup → interpolation for missing cells → clamped return in [0.0, 1.0]
- [x] T018 [US2] Modify `ResourceFeatureCalculator.calculate_resource_win_probability()` in `src/bbl_pipeline/features/calculator.py` (around L883–898) to detect `balls_remaining <= 6` condition and dispatch to `get_final_over_win_prob()` from `win_prob_lookup_tables.py` instead of the existing sigmoid formula `1/(1+exp(4*(rpb-1.5)))`. Preserve the existing sigmoid path for balls_remaining > 6 (overs 18–19)
- [x] T019 [US2] Validate by running `python scripts/analyze_ipl_model_vs_market.py` and confirm: over-20 Brier gap reduced from +0.170 to < +0.050; no other over regresses by > 0.005

**Checkpoint**: User Story 2 complete — final-over predictions now use empirical data instead of crude sigmoid. Over-20 gap dramatically reduced.

---

## Phase 5: User Story 3 — Current Team Strength Reflected in Predictions (Priority: P2)

**Goal**: Replace all-time-average team ratings with recency-weighted ratings (exponential decay, half-life 2.5 seasons) and deduplicate franchise name variants (RCB, DC, PBKS, RPS).

**Independent Test**: Compare MI and KKR team-specific Brier gaps before and after. Each must reduce by ≥50%.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T020 [P] [US3] Create unit tests at `tests/unit/test_team_ratings.py` — test that `data/ipl_feature_store_v1/team_ratings.parquet` has no duplicate team names; test all canonical teams from entity_registry.yaml are present; test 0.0 < win_rate < 1.0 for all teams; test effective_matches > 0; test matches >= 10 for all included teams; test that the parquet schema matches data-model.md Team Rating entity (columns: team, win_rate, matches, effective_matches, bat_first_wr, bowl_first_wr, half_life_seasons, last_updated)

### Implementation for User Story 3

- [x] T021 [US3] Verify `scripts/regenerate_ipl_feature_store.py` (created in T008) correctly applied recency weighting and deduplication — the regenerated `data/ipl_feature_store_v1/team_ratings.parquet` should contain exactly one entry per canonical franchise with recency-weighted win rates
- [x] T022 [US3] Verify `src/bbl_pipeline/features/store.py` (around L354–368 where `_load()` reads `team_ratings.parquet`) correctly loads the regenerated parquet without errors — ensure team lookup resolves both old and new franchise names to the canonical entry via entity_registry.yaml mappings
- [x] T023 [US3] Validate by running `python scripts/analyze_ipl_model_vs_market.py` and confirm: MI Brier gap reduced from +0.1811 to < +0.091; KKR Brier gap reduced from +0.1356 to < +0.068; no team regresses by > 0.005

**Checkpoint**: User Story 3 complete — team ratings reflect current form, franchise duplicates eliminated.

---

## Phase 6: User Story 4 — Accurate First-Innings Death-Over Projections (Priority: P2)

**Goal**: Update the first-innings scoring midpoint from 165.0 to ~173.0 and add venue-adjusted midpoint modifier using existing venue_stats.parquet data.

**Depends on**: US3 (venue data quality in regenerated feature store)

**Independent Test**: Evaluate first-innings death-over (overs 16–17) Brier gap. Must reduce by ≥40%.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T024 [P] [US4] Create unit tests at `tests/unit/test_ipl_scoring_config.py` — test that `FormatConfig.ipl().first_innings_score_midpoint` is between 170.0 and 176.0 (within ±3 of 173.45 per FR-007); test it is NOT 165.0 (the inherited T20 default); test venue-adjusted midpoint formula: `effective_midpoint = league_midpoint + 0.7 × (venue_avg - league_avg)` returns correct values for known venues (e.g., Chinnaswamy high-scoring, Chepauk low-scoring); test default to league midpoint for unknown venues

### Implementation for User Story 4

- [x] T025 [US4] Update `FormatConfig.ipl()` factory method in `src/bbl_pipeline/features/format_config.py` to override `first_innings_score_midpoint=173.0` (FR-007 — currently inherits 165.0 from `FormatConfig.t20()` at L254). Optionally re-tune `first_innings_score_beta` from IPL data if derivation script yields a better steepness value
- [x] T026 [US4] Implement venue-adjusted scoring midpoint in `src/bbl_pipeline/features/calculator.py` — when computing SQI (Score Quality Index) for first innings, apply formula `effective_midpoint = league_midpoint + 0.7 × (venue_avg - league_avg)` using `venue_avg_score` from the feature store (already seeded at `store.py:376–398` for 17 IPL venues per research.md R-004). Default to league midpoint (173.0) for venues with no historical data
- [x] T027 [US4] Validate by running `python scripts/analyze_ipl_model_vs_market.py` and confirm: overs 16–17 Brier gap reduced by ≥40% from the current +0.072 to +0.093 range; no first-innings segment regresses by > 0.005

**Checkpoint**: User Story 4 complete — first-innings model reflects IPL's higher-scoring environment and venue characteristics.

---

## Phase 7: User Story 5 — State-Aware Calibration (Priority: P3)

**Goal**: Replace the 2 global temperature scalers with 6 phase-wise Platt scaling calibrators (powerplay/middle/death × innings 1/innings 2), enabling state-dependent bias correction.

**Depends on**: US1 (corrected wicket penalties) and US4 (corrected scoring midpoint) should be in place first so calibrators train on corrected features.

**Independent Test**: Train phase-wise calibrators, apply to validation set, compare Brier delta against near-zero delta of current temperature approach. No phase should regress.

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T028 [P] [US5] Create unit test file at `tests/unit/test_phase_calibrator.py` — test that `LeagueCalibrator` with `phase_specific=True, method='platt'` fits 6 phase calibrators keyed as inn1_powerplay/inn1_middle/inn1_death/inn2_powerplay/inn2_middle/inn2_death plus 2 fallback innings-level calibrators per contracts/league_calibrator.py; test routing logic returns correct calibrator key for each (innings, phase) pair; test fallback chain: phase-specific → innings-level → identity; test minimum sample enforcement (segment <500 samples → uses innings-level fallback)

### Implementation for User Story 5

- [x] T029 [US5] Modify `LeagueCalibrator.__init__()` in `src/bbl_pipeline/training/league_calibrator.py` to set `method='platt'` and `phase_specific=True` by default for IPL league. Ensure `fit()` method (around L161–171) trains 6 phase-specific Platt calibrators + 2 innings-level fallback calibrators, with min_samples=500 threshold per segment per contracts/league_calibrator.py FIT_CONTRACT
- [x] T030 [US5] Modify `LeagueCalibrator.predict()` in `src/bbl_pipeline/training/league_calibrator.py` (around L185–216) to route predictions through phase-specific calibrators: build key `f"inn{innings}_{phase}"`, try phase-specific first, fall back to `f"innings_{innings}"`, then identity — matching the routing contract in contracts/league_calibrator.py
- [x] T031 [US5] Update `Predictor.predict()` in `src/bbl_pipeline/inference/predictor.py` to ensure the calibration chain passes both `innings` and `phase` columns to the updated `LeagueCalibrator.predict()` for phase routing. Verify phase mapping: powerplay=overs 1–6, middle=overs 7–14, death=overs 15–20
- [x] T032 [US5] Retrain IPL calibrators by running the calibrator training pipeline with the new phase-specific configuration. Verify 6+2 calibrators are serialized to `models/ipl/league_calibrator.pkl` via joblib
- [x] T033 [US5] Validate by running `python scripts/analyze_ipl_model_vs_market.py` and confirm: overall calibrated Brier improvement > near-zero delta of previous temperature approach; no individual phase regresses (brier_calibrated ≤ brier_raw + 0.005 per phase per contracts/league_calibrator.py METRICS_CONTRACT)

**Checkpoint**: User Story 5 complete — calibration is now state-aware. Each match phase receives phase-appropriate probability corrections.

---

## Phase 8: User Story 6 — Market-Informed Ensemble Predictions (Priority: P3)

**Goal**: Implement a blending mechanism that combines calibrated model predictions with live market odds using formula `final = alpha × model + (1 - alpha) × market`, with graceful fallback when market data is unavailable.

**Depends on**: All prior user stories — the ensemble should blend an already-improved model.

**Independent Test**: Sweep alpha 0.0–1.0 on 510-observation validation set. Optimal alpha's Brier must beat both pure-model (0.1977) and pure-market (0.1546).

### Tests for User Story 6

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T034 [P] [US6] Create unit test file at `tests/unit/test_market_ensemble.py` — test `blend_predictions()` per contracts/market_ensemble.py: returns (model_prob, "model_only") when market_prob is None; returns (model_prob, "model_only") when market_age_seconds > 60; returns blended probability with source="ensemble" when valid market data present; test clamp to [0.001, 0.999]; test pure market mode when alpha=0.0; test pure model mode when alpha=1.0; test invalid market_prob (<0 or >1) falls back to model_only; test function never raises exceptions (FR-012)

### Implementation for User Story 6

- [x] T035 [US6] Create alpha sweep script at `scripts/sweep_ensemble_alpha.py` — reads `data/ipl_model_vs_market.parquet` (columns: model_prob, market_prob, actual_outcome), sweeps alpha from 0.0 to 1.0 in 0.05 steps, computes Brier score at each alpha, outputs optimal alpha and Brier curve per contracts/market_ensemble.py ALPHA_SWEEP_CONTRACT
- [x] T036 [US6] Run `python scripts/sweep_ensemble_alpha.py` and record optimal alpha value. Verify ensemble Brier < 0.1977 (pure model) AND < 0.1546 (pure market) per SC-007
- [x] T037 [US6] Implement `blend_predictions(model_prob, market_prob, market_age_seconds, alpha, staleness_threshold)` function in `src/bbl_pipeline/inference/crex_live_predictor.py` — return Tuple[float, str] per contracts/market_ensemble.py: check market data availability and staleness, compute linear blend, clamp output, return source label. Use the optimal alpha from T036 as default
- [x] T038 [US6] Wire `blend_predictions()` into the live prediction path in `src/bbl_pipeline/inference/crex_live_predictor.py` — after calibrated model_prob is computed and market_prob is extracted from exchange odds, call blend_predictions() to produce ensemble_prob. Preserve model_prob in output alongside ensemble_prob for traceability (FR-013)
- [x] T039 [US6] Update `src/bbl_pipeline/inference/match_state_logger.py` to log both `model_prob` and `ensemble_prob` fields, plus `alpha`, `market_prob`, and `source` ("ensemble"/"model_only") in the Parquet schema per contracts/market_ensemble.py LOGGING_CONTRACT
- [x] T040 [US6] Validate by running `python scripts/analyze_ipl_model_vs_market.py` and confirm: ensemble Brier beats both baselines (SC-007); no segment regresses by > 0.005 (SC-008)

**Checkpoint**: User Story 6 complete — market-informed ensemble operational with graceful fallback.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, integration testing, documentation, and cleanup.

- [x] T041 [P] Create end-to-end integration test at `tests/integration/test_ipl_pipeline_e2e.py` — test full IPL prediction pipeline from raw input through feature calculation, penalty application, final-over lookup, calibration, and ensemble blending; verify output contains both model_prob and ensemble_prob; verify no exceptions for edge cases (10 wickets lost, new venue, missing market data)
- [x] T042 Run full validation: execute `python scripts/analyze_ipl_model_vs_market.py` and verify overall Brier ≤ 0.170 (SC-001), all 8 success criteria from spec.md pass, and non-regression across all segments (SC-008: no segment regresses > 0.005)
- [x] T043 [P] Run full test suite `pytest tests/ -v` and confirm all existing tests pass plus all new tests (test_ipl_wicket_penalties.py, test_final_over_lookup.py, test_team_ratings.py, test_ipl_scoring_config.py, test_phase_calibrator.py, test_market_ensemble.py, test_ipl_pipeline_e2e.py) pass
- [x] T044 [P] Update `specs/001-ipl-market-gap/quickstart.md` baseline metrics table with final achieved values for all 8 success criteria
- [x] T045 Code cleanup: remove any temporary debug prints or commented-out code; ensure all derivation scripts have docstrings; verify all new functions have type hints matching contracts

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational (T006/T009 penalty derivation)
- **US2 (Phase 4)**: Depends on Foundational (T007/T010 final-over derivation)
- **US3 (Phase 5)**: Depends on Foundational (T005 entity registry + T008/T011 team ratings)
- **US4 (Phase 6)**: Depends on US3 (venue data quality from regenerated feature store)
- **US5 (Phase 7)**: Depends on US1 + US4 (calibrators should train on corrected features)
- **US6 (Phase 8)**: Depends on US1–US5 (ensemble should blend an already-improved model)
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1: Setup
  ↓
Phase 2: Foundational (derivation scripts + entity registry)
  ↓
  ├── US1 (Phase 3) ──────────────────────────────────┐
  ├── US2 (Phase 4) ──── (parallel with US1, US3) ──→ │
  └── US3 (Phase 5) ──┐                               │
                       ↓                               │
                 US4 (Phase 6) ───→ depends on US3     │
                       ↓                               ↓
                 US5 (Phase 7) ───→ depends on US1 + US4
                       ↓
                 US6 (Phase 8) ───→ depends on all US1–US5
                       ↓
                 Polish (Phase 9)
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Derivation/data before configuration changes
- Configuration changes before wiring/integration
- Validation after every story (non-regression check)
- Story complete before dependent stories begin

### Parallel Opportunities

- **Phase 2**: T006, T007, T008 can all run in parallel (independent derivation scripts for different data)
- **Phases 3–5**: US1, US2, US3 can all start in parallel after Foundational completes (they modify independent files)
  - US1 modifies `format_config.py` (penalty tables)
  - US2 modifies `win_prob_lookup_tables.py` + `calculator.py` (final-over logic)
  - US3 modifies `entity_registry.yaml` + `team_ratings.parquet` + `store.py`
- **Within each story**: Tests are [P]-parallelizable with tests from other stories
- **Phase 9**: T041, T043, T044 can run in parallel

---

## Parallel Example: User Stories 1, 2, 3

```bash
# After Phase 2 (Foundational) completes, launch all three P1/P2 stories in parallel:

# Developer/Agent A — User Story 1 (Wicket Penalties):
Task: T012 "Unit tests for wicket penalties in tests/unit/test_ipl_wicket_penalties.py"
Task: T013 "Override chase_wicket_penalty_2d in format_config.py"
Task: T014 "Override first_innings_wicket_penalty_3d in format_config.py"
Task: T015 "Validate wicket penalty improvements"

# Developer/Agent B — User Story 2 (Final-Over Lookup):
Task: T016 "Unit tests for final-over lookup in tests/unit/test_final_over_lookup.py"
Task: T017 "Add lookup table + function to win_prob_lookup_tables.py"
Task: T018 "Wire lookup into calculator.py replacing sigmoid"
Task: T019 "Validate final-over improvements"

# Developer/Agent C — User Story 3 (Team Ratings):
Task: T020 "Unit tests for team ratings in tests/unit/test_team_ratings.py"
Task: T021 "Verify regenerated team_ratings.parquet"
Task: T022 "Verify store.py loads new parquet correctly"
Task: T023 "Validate team-specific improvements"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T004)
2. Complete Phase 2: Foundational (T005–T011) — derive all data artifacts
3. Complete Phase 3: User Story 1 — wicket penalties (T012–T015)
4. **STOP and VALIDATE**: Run `scripts/analyze_ipl_model_vs_market.py`, verify wicket gap halved
5. The single largest error source is now corrected — deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → All derivation artifacts ready
2. US1 (wicket penalties) → Test → Validate → **Largest single improvement** (MVP!)
3. US2 (final-over lookup) → Test → Validate → Fixes worst single-over error
4. US3 (team ratings) → Test → Validate → Fixes MI/KKR team gaps
5. US4 (scoring midpoint) → Test → Validate → Fixes death-over projections
6. US5 (phase calibration) → Test → Validate → State-aware bias correction
7. US6 (market ensemble) → Test → Validate → Best possible combined accuracy
8. Each story adds measurable Brier improvement without breaking previous stories

### Parallel Team Strategy

With multiple developers/agents:

1. Team completes Setup + Foundational together (Phases 1–2)
2. Once Foundational is done:
   - Agent A: User Story 1 (wicket penalties — `format_config.py`)
   - Agent B: User Story 2 (final-over lookup — `calculator.py`, `win_prob_lookup_tables.py`)
   - Agent C: User Story 3 (team ratings — `entity_registry.yaml`, `store.py`, parquet)
3. After US1+US3 complete: Agent A takes US4 (scoring midpoint — `format_config.py`, `calculator.py`)
4. After US1+US4 complete: Agent B takes US5 (phase calibration — `league_calibrator.py`, `predictor.py`)
5. After all US1–5: Agent C takes US6 (market ensemble — `crex_live_predictor.py`, `match_state_logger.py`)
6. All agents converge for Phase 9 (Polish)

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable: run validation script after each phase
- Validate non-regression (SC-008) after EVERY story: no segment may regress > 0.005 Brier
- The core model (XGBLogRegEnsemble) is **frozen** — never retrained. All changes are config/features/calibration/ensemble
- All IPL changes are isolated in `FormatConfig.ipl()` or IPL-specific feature stores — never modify `FormatConfig.t20()` base
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
