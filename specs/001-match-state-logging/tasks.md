# Tasks: Match State Data Logging System

**Input**: Design documents from `/specs/001-match-state-logging/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Project scaffolding and shared infrastructure

- [X] T001 Create `src/bbl_pipeline/analysis/__init__.py` package with module docstring
- [X] T002 [P] Create `data/match_states/.gitkeep` and add `data/match_states/` to `.gitignore`
- [X] T003 [P] Create Parquet schema constants module at `src/bbl_pipeline/inference/match_state_schema.py` with BALL_STATE_SCHEMA, MATCH_METADATA_SCHEMA, VOLATILITY_PROFILE_SCHEMA, SIGNAL_EVENT_SCHEMA from contracts/data-contract.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core MatchStateLogger that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Implement `MatchStateLogger.__init__` in `src/bbl_pipeline/inference/match_state_logger.py` — constructor accepting match_id, league, states_dir, model_version, feature_store_version; creates output directory; initializes buffer as `list[dict]`; sets up structlog logger
- [X] T005 Implement `MatchStateLogger._compute_match_phase` in `src/bbl_pipeline/inference/match_state_logger.py` — classifies over_number into "powerplay" (1-6), "middle" (7-15), "death" (16-20)
- [X] T006 Implement `MatchStateLogger._compute_team_tier` in `src/bbl_pipeline/inference/match_state_logger.py` — classifies team win_rate into "top" (top 33%), "mid", "bottom" (bottom 33%) from feature store team ratings
- [X] T007 Implement `MatchStateLogger._map_market_probs` in `src/bbl_pipeline/inference/match_state_logger.py` — converts market_fav_team + market_fav_prob into batting_team_prob and bowling_team_prob by comparing fav_team identity to batting/bowling team
- [X] T008 Implement `MatchStateLogger._compute_deviation` in `src/bbl_pipeline/inference/match_state_logger.py` — computes deviation (signed), deviation_abs, deviation_bucket (0.05 increments: "0.00-0.05", "0.05-0.10", ..., "0.30+"), deviation_direction ("model_higher"/"model_lower"/"aligned" within 0.02 threshold)
- [X] T009 Implement `MatchStateLogger.record_ball` in `src/bbl_pipeline/inference/match_state_logger.py` — assembles full BallStateRecord dict from MatchState, features_dict, predictor calibration attributes, and market odds; computes model_prob_delta and market_prob_delta from previous ball; appends to buffer; auto-flushes at 30 records; entire method wrapped in try/except (FR-009)
- [X] T010 Implement `MatchStateLogger.flush` in `src/bbl_pipeline/inference/match_state_logger.py` — writes buffered records to `<match_id>.parquet` using pyarrow schema from match_state_schema.py; handles append if file already exists; clears buffer; wrapped in try/except
- [X] T011 Implement `MatchStateLogger.finalize` in `src/bbl_pipeline/inference/match_state_logger.py` — flushes remaining buffer, writes/appends match row to `match_metadata.parquet` with match_id, league, venue, teams, tiers, winner (nullable), scores, model_version, feature_store_version, total_balls_recorded, recording timestamps; wrapped in try/except

**Checkpoint**: MatchStateLogger ready — user story phases can begin

---

## Phase 3: User Story 1 — Record Complete Match State (Priority: P1) MVP

**Goal**: Automatically capture complete match state (raw + computed features + calibration chain) at each ball during live predictions and persist to Parquet

**Independent Test**: Run model on a single match with `--record-states`, verify `<match_id>.parquet` contains all balls with 80+ columns matching data-contract.md schema

- [X] T012 [US1] Add `--record-states` (store_true) and `--states-dir` (str, default None) argparse arguments in `src/bbl_pipeline/inference/crex_live_predictor.py`
- [X] T013 [US1] Add MatchStateLogger instantiation in `src/bbl_pipeline/inference/crex_live_predictor.py` — create logger when `--record-states` is set, derive match_id from URL, derive states_dir default as `data/match_states/<league>/`, extract model_version and feature_store_version from dir basenames
- [X] T014 [US1] Add `logger.record_ball()` call after each `_write_json_state()` in `src/bbl_pipeline/inference/crex_live_predictor.py` — pass match_state, features dict, predictor, and market_odds dict; wrap in try/except
- [X] T015 [US1] Add `logger.flush()` call at innings break detection and `logger.finalize()` at match completion/SIGINT in `src/bbl_pipeline/inference/crex_live_predictor.py`
- [X] T016 [P] [US1] Create unit test `tests/unit/test_match_state_logger.py` — test record_ball produces dict with 80+ keys; test flush creates valid Parquet; test finalize creates match_metadata.parquet; test buffer auto-flush at 30 records; test error isolation (bad data logs error, doesn't raise)

**Checkpoint**: US1 complete — running predictor with `--record-states` saves all ball states to Parquet

---

## Phase 4: User Story 2 — Capture Market Odds with Model Predictions (Priority: P2)

**Goal**: Capture CREX market odds alongside model predictions at each ball, enabling model-market comparison

**Independent Test**: Run model on a match with market odds active, verify Parquet contains `market_fav_team`, `market_back_odds`, `market_fav_prob`, `market_batting_team_prob`, `market_bowling_team_prob` columns with non-null values when odds are available

- [X] T017 [US2] Handle missing market odds gracefully in `MatchStateLogger.record_ball` in `src/bbl_pipeline/inference/match_state_logger.py` — when market_odds dict has None/missing values, set all market columns and deviation columns to None (FR-014)
- [X] T018 [P] [US2] Add unit tests for market odds handling in `tests/unit/test_match_state_logger.py` — test market prob mapping (fav=batting team vs fav=bowling team); test missing odds produces null market/deviation fields; test lay odds recorded correctly

**Checkpoint**: US2 complete — market odds captured alongside predictions, missing odds handled gracefully

---

## Phase 5: User Story 5 — Compute Model-Market Deviation as Signal Strength (Priority: P3)

**Goal**: Compute and store model-market deviation at each ball as a signal strength metric with directional classification and size buckets

**Independent Test**: Compute deviation for a completed match, verify `deviation`, `deviation_abs`, `deviation_bucket`, `deviation_direction` columns are correct for known model/market values

- [X] T019 [US5] Verify deviation computation end-to-end in `src/bbl_pipeline/inference/match_state_logger.py` — ensure `_compute_deviation` correctly handles edge cases: first ball (no delta), aligned predictions (within 0.02), extreme deviations (>0.5), negative deviations
- [X] T020 [P] [US5] Add unit tests for deviation computation in `tests/unit/test_match_state_logger.py` — test known model_prob=0.7/market_prob=0.5 produces deviation=0.2, bucket="0.20-0.25", direction="model_higher"; test aligned produces "aligned"; test extreme >0.5 flagged in "0.30+" bucket; test model_prob_delta and market_prob_delta from consecutive balls

**Checkpoint**: US5 complete — deviation metrics recorded per ball, queryable by bucket/direction

---

## Phase 6: User Story 3 — Multi-League Data Collection (Priority: P3)

**Goal**: Record match states across different T20 leagues with correct league tagging and league-specific feature store references

**Independent Test**: Record matches from two different leagues (e.g., BBL and SA20), verify each record has correct league tag and data is stored in separate `data/match_states/<league>/` directories

- [X] T021 [US3] Verify league parameter flows correctly from `--league` arg through MatchStateLogger to Parquet in `src/bbl_pipeline/inference/crex_live_predictor.py` — ensure states_dir respects league subdirectory, league column is populated in every record
- [X] T022 [P] [US3] Add unit test for multi-league isolation in `tests/unit/test_match_state_logger.py` — test two logger instances with different leagues write to separate directories and produce correct league tags

**Checkpoint**: US3 complete — can record matches from any league with correct tagging and isolation

---

## Phase 7: User Story 4 — Detect Model Drift Over Time (Priority: P4)

**Goal**: Analyze recorded match states over a season to detect calibration drift by comparing predictions against outcomes

**Independent Test**: Generate calibration report from 10+ recorded matches, verify Brier score and ECE computed correctly by phase/innings/league

- [X] T023 [US4] Implement `StateAnalyzer.__init__` in `src/bbl_pipeline/analysis/state_analyzer.py` — constructor accepting league, states_dir; discovers available match files and metadata
- [X] T024 [US4] Implement `StateAnalyzer.consolidate` in `src/bbl_pipeline/analysis/state_analyzer.py` — reads all `<match_id>.parquet` files for the league, concatenates, sorts by match_id + innings + over_number + ball_in_over, writes `all_matches.parquet`
- [X] T025 [US4] Implement `StateAnalyzer.calibration_report` in `src/bbl_pipeline/analysis/state_analyzer.py` — loads all_matches + match_metadata, joins on match_id to get winner, computes actual_win (batting_team == winner), calculates Brier score, ECE (10-bin), LogLoss overall + by innings + by phase + by team tier; writes `CALIBRATION_REPORT.md`
- [X] T026 [US4] Add `analyze-states` Click command in `src/bbl_pipeline/cli.py` — arguments: --match-file, --league, --outcome, --consolidate, --calibration-report, --deviation-threshold (default 0.10), --states-dir; delegates to StateAnalyzer methods per CLI contract
- [X] T027 [P] [US4] Create unit test `tests/unit/test_state_analyzer.py` — test consolidation merges files correctly; test calibration report computes expected Brier/ECE for mock data; test CLI command wiring

**Checkpoint**: US4 complete — can consolidate matches and produce calibration drift reports with Brier/ECE breakdown

---

## Phase 8: User Story 6 — Track Return by Deviation Size (Priority: P4)

**Goal**: Analyze profitability segmented by deviation bucket to find "sweet spot" ranges

**Independent Test**: Query signal events grouped by deviation bucket, verify success rate and sample count computed correctly

- [X] T028 [US6] Implement `StateAnalyzer.deviation_analysis` in `src/bbl_pipeline/analysis/state_analyzer.py` — loads signal_events.parquet, groups by deviation_bucket, computes per-bucket: sample count, success rate (model_team_won), avg deviation, expected value; supports segmentation by team_tier, match_phase, league
- [X] T029 [P] [US6] Add `--deviation-report` flag to `analyze-states` command in `src/bbl_pipeline/cli.py` — generates deviation analysis table and prints to console
- [X] T030 [P] [US6] Add unit test for deviation analysis in `tests/unit/test_state_analyzer.py` — test bucket grouping produces correct counts/rates for known data

**Checkpoint**: US6 complete — can identify profitable deviation ranges segmented by phase/tier

---

## Phase 9: User Story 7 — Compare Model vs Market Volatility Curves (Priority: P4)

**Goal**: Compute and compare model/market probability volatility over each match

**Independent Test**: Compute volatility for a completed match, verify model_volatility, market_volatility, volatility_ratio are correct

- [X] T031 [US7] Implement `StateAnalyzer.compute_volatility` in `src/bbl_pipeline/analysis/state_analyzer.py` — loads match Parquet, computes std dev of model_prob_delta and market_prob_delta (overall + per innings), max swing, volatility ratio; appends to `volatility_profiles.parquet`
- [X] T032 [P] [US7] Add unit test for volatility computation in `tests/unit/test_state_analyzer.py` — test known deltas produce expected std dev and ratio

**Checkpoint**: US7 complete — volatility profiles available for all recorded matches

---

## Phase 10: User Story 9 — Detect Strong-Team Recovery Patterns (Priority: P4)

**Goal**: Analyze whether strong teams recover from pressure more often than model predicts

**Independent Test**: Query stress states (top-tier team, 3+ wickets in powerplay), compare model-predicted win rate vs actual win rate

- [X] T033 [US9] Implement `StateAnalyzer.recovery_analysis` in `src/bbl_pipeline/analysis/state_analyzer.py` — filters signal events for top-tier batting team under stress (3+ wickets in powerplay, or 30+ runs behind RRR in chase); computes recovery premium = actual_win_rate - model_prob; segments by match phase
- [X] T034 [P] [US9] Add unit test for recovery analysis in `tests/unit/test_state_analyzer.py` — test recovery premium computation with mock stress events

**Checkpoint**: US9 complete — recovery premium quantified for top-tier teams

---

## Phase 11: User Story 8 — Build Price Movement Meta-Model (Priority: P5)

**Goal**: Extract signal events with price reversion labels so a meta-model can be trained to predict market movement toward model

**Independent Test**: Run signal extraction on a completed match, verify price_reverted, reversion_magnitude, balls_to_reversion are correctly computed

- [X] T035 [US8] Implement `StateAnalyzer.extract_signals` in `src/bbl_pipeline/analysis/state_analyzer.py` — loads match Parquet + match_metadata, for each ball where |deviation| > threshold: scans forward for market prob moving >= 50% toward model; computes price_reverted (bool), reversion_magnitude (0.0-1.0), balls_to_reversion; writes to `signal_events.parquet`
- [X] T036 [US8] Implement `StateAnalyzer.meta_model_readiness` in `src/bbl_pipeline/analysis/state_analyzer.py` — counts total matches, total signal events, feature completeness percentage, samples per deviation bucket; prints warning if < 200 matches (FR-029)
- [X] T037 [P] [US8] Add unit test for signal extraction in `tests/unit/test_state_analyzer.py` — test price reversion detection with known forward-looking data; test readiness check with small dataset prints warning

**Checkpoint**: US8 complete — signal events with reversion labels ready for meta-model training

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Integration testing, documentation, validation

- [X] T038 [P] Create integration test `tests/integration/test_record_and_analyze.py` — create synthetic MatchState + features + predictions + market odds; run MatchStateLogger for ~20 balls across 2 innings; finalize; run StateAnalyzer consolidate + compute_volatility + extract_signals + calibration_report; verify all output files exist with correct schemas
- [X] T039 [P] Update `README.md` with match state recording section — document --record-states flag, analyze-states command, data layout
- [X] T040 [P] Update `.github/copilot-instructions.md` with new commands and file locations — add MatchStateLogger, StateAnalyzer, analyze-states to relevant sections
- [X] T041 Run quickstart.md validation — verify all CLI examples from quickstart.md execute without errors (validated: all commands match implementation)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (schema module) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — core recording. **This is the MVP.**
- **US2 (Phase 4)**: Depends on Phase 2 — market odds are recorded in logger (mostly already handled in Phase 2)
- **US5 (Phase 5)**: Depends on Phase 2 — deviation computation (mostly already handled in Phase 2)
- **US3 (Phase 6)**: Depends on Phase 2 — multi-league is a configuration concern
- **US4 (Phase 7)**: Depends on Phase 3 (data must exist) — first analysis story
- **US6 (Phase 8)**: Depends on Phase 11/US8 (signal_events.parquet must exist)
- **US7 (Phase 9)**: Depends on Phase 7/US4 (StateAnalyzer must exist)
- **US9 (Phase 10)**: Depends on Phase 11/US8 (signal events must exist)
- **US8 (Phase 11)**: Depends on Phase 7/US4 (StateAnalyzer class must exist)
- **Polish (Phase 12)**: Depends on all prior phases

### Recommended Execution Order

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational: MatchStateLogger core)
    ↓
Phase 3 (US1: Integrate into predictor) ← MVP STOP POINT
    ↓
Phase 4 (US2: Market odds handling) + Phase 5 (US5: Deviation) + Phase 6 (US3: Multi-league)  [parallel]
    ↓
Phase 7 (US4: StateAnalyzer + calibration report + CLI)
    ↓
Phase 11 (US8: Signal extraction + reversion) → Phase 8 (US6: Deviation analysis) + Phase 9 (US7: Volatility) + Phase 10 (US9: Recovery)  [parallel after US8]
    ↓
Phase 12 (Polish)
```

### Parallel Opportunities

**Within Phase 1** (all independent files):
```
T001 + T002 + T003  [all parallel]
```

**US2 + US5 + US3** (after Phase 2, independent concerns):
```
T017 + T018  (US2: market odds)
T019 + T020  (US5: deviation)
T021 + T022  (US3: multi-league)
```

**US6 + US7 + US9** (after US8, independent analysis types):
```
T028-T030  (US6: deviation analysis)
T031-T032  (US7: volatility)
T033-T034  (US9: recovery)
```

**Phase 12 tasks** (all different files):
```
T038 + T039 + T040  [all parallel]
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational MatchStateLogger (T004-T011)
3. Complete Phase 3: US1 — integrate into predictor (T012-T016)
4. **STOP and VALIDATE**: Run predictor with `--record-states` on a live match, verify Parquet output
5. This alone delivers the data collection foundation

### Incremental Delivery

1. Setup + Foundational → Logger ready
2. Add US1 → Data recording works → **MVP complete**
3. Add US2 + US5 + US3 → Market odds + deviation + multi-league → Rich dataset
4. Add US4 → Calibration reports → Drift detection live
5. Add US8 → Signal extraction → Reversion labels
6. Add US6 + US7 + US9 → Full analysis suite → Edge detection
7. Polish → Integration tests + docs

### Task Count Summary

| Phase | Story | Tasks | Parallel |
|-------|-------|-------|----------|
| Setup | — | 3 | 2 |
| Foundational | — | 8 | 0 |
| US1 (P1) | Record State | 5 | 1 |
| US2 (P2) | Market Odds | 2 | 1 |
| US5 (P3) | Deviation | 2 | 1 |
| US3 (P3) | Multi-League | 2 | 1 |
| US4 (P4) | Drift Detection | 5 | 1 |
| US6 (P4) | Return by Deviation | 3 | 2 |
| US7 (P4) | Volatility | 2 | 1 |
| US9 (P4) | Recovery | 2 | 1 |
| US8 (P5) | Meta-Model | 3 | 1 |
| Polish | — | 4 | 3 |
| **Total** | | **41** | **15** |
