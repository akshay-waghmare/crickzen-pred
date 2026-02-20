# Implementation Plan: Match State Data Logging System

**Branch**: `001-match-state-logging` | **Date**: February 17, 2026 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-match-state-logging/spec.md`

## Summary

Build a match state recording system that persists the complete prediction context (raw match state, 50+ computed features, full calibration chain, CREX market odds) to Parquet at every ball during live predictions. This is achieved by:

1. **Adding a `MatchStateLogger` class** in the inference package that buffers ball-level records and flushes to per-match Parquet files.
2. **Modifying `crex_live_predictor.py`** to accept a `--record-states` flag and pipe existing data (already 90% captured in `_write_json_state()`) into the logger.
3. **Adding an `analyze-states` Click command** to `cli.py` for post-match analysis: consolidation, calibration metrics, volatility profiles, signal event extraction with price reversion labels.
4. **Post-match batch processing** computes derived artifacts (VolatilityProfile, SignalEvent) that require look-ahead data.

The system enables drift detection, calibration verification, model-market deviation analysis, and meta-model dataset creation across all supported T20 leagues.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pandas, pyarrow, numpy, scikit-learn (brier_score_loss), structlog, click (CLI), playwright (CREX scraping — existing)
**Storage**: Apache Parquet (snappy compression) at `data/match_states/<league>/`
**Testing**: pytest (unit + integration)
**Target Platform**: Windows desktop (primary), Linux server (compatible)
**Project Type**: Single project — extends existing `src/bbl_pipeline/` package
**Performance Goals**: <50ms per ball to buffer a record; <10s to consolidate 50 matches; <30s for full calibration report
**Constraints**: Logger MUST NOT add >100ms latency to the prediction loop; logger failures MUST NOT interrupt predictions
**Scale/Scope**: ~120 balls per match × 50+ matches per league → ~6,000 rows per league per season; 80+ columns per row

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Check

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | **Scalability & Reusability** (tournament-agnostic) | PASS | League is a parameter, not hardcoded. `MatchStateLogger` works for any league. Data stored per `<league>/` subdirectory. No BBL-specific logic in logger. |
| II | **Pipeline-Driven Architecture** | PASS | Recording is a composable add-on (opt-in flag). Analysis is a separate CLI command. Each step is distinct and independent. |
| III | **Reproducibility & Versioning** | PASS | Every record includes `model_version` and `feature_store_version`. Parquet files are immutable per-match. |
| IV | **Data Integrity & Entity Consistency** | PASS | Team/venue names sourced from existing `InMemoryFeatureStore` canonical mappings. Parquet schema enforced via `pyarrow.Schema`. |
| V | **Model Calibration & Observability** | PASS | Records ALL calibration chain stages (raw > combined > innings > phase > per-over > league). Enables ECE/Brier computation on live data. Directly supports "Live Monitoring" requirement from constitution. |

### Post-Design Re-check

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Scalability & Reusability | PASS | `MatchStateLogger` accepts `league: str`, `states_dir: Path`. No league-specific branches. |
| II | Pipeline-Driven | PASS | Three stages: record (live) > consolidate (batch) > analyze (batch). Each independently runnable. |
| III | Reproducibility | PASS | Per-match Parquet files with version metadata. Consolidation is deterministic (sorted by match_id, ball). |
| IV | Data Integrity | PASS | Schema validation on flush. Nullable fields for missing market odds. Team names from feature store. |
| V | Calibration & Observability | PASS | System IS the observability layer — records predictions vs outcomes for ECE/Brier tracking. |

**Gate result: ALL PASS — no violations.**

## Project Structure

### Documentation (this feature)

```text
specs/001-match-state-logging/
├── plan.md              # This file
├── spec.md              # Feature specification (9 user stories, 29 FRs)
├── research.md          # Phase 0 research (10 decisions)
├── data-model.md        # Entity schemas (BallStateRecord, MatchMetadata, etc.)
├── quickstart.md        # CLI usage examples + Python analysis snippets
├── checklists/
│   └── requirements.md  # Spec quality checklist
├── contracts/
│   ├── cli-contract.md  # CLI argument contracts
│   └── data-contract.md # Parquet schema contracts
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/bbl_pipeline/
├── inference/
│   ├── crex_live_predictor.py   # MODIFY: add --record-states, --states-dir args
│   ├── match_state_logger.py    # NEW: MatchStateLogger class
│   ├── predictor.py             # READ-ONLY (access calibration intermediates)
│   └── realtime_mapper.py       # READ-ONLY (access computed features)
├── analysis/
│   ├── __init__.py              # NEW: analysis subpackage
│   └── state_analyzer.py        # NEW: StateAnalyzer class
└── cli.py                       # MODIFY: add analyze-states Click command

tests/
├── unit/
│   ├── test_match_state_logger.py   # NEW: logger unit tests
│   └── test_state_analyzer.py       # NEW: analyzer unit tests
└── integration/
    └── test_record_and_analyze.py   # NEW: end-to-end test

data/match_states/                   # NEW: output directory (gitignored)
├── <league>/
│   ├── <match_id>.parquet
│   ├── match_metadata.parquet
│   ├── all_matches.parquet
│   ├── volatility_profiles.parquet
│   ├── signal_events.parquet
│   └── CALIBRATION_REPORT.md
└── ...
```

**Structure Decision**: Single project. New code adds 2 files to `src/bbl_pipeline/inference/` (logger) and creates a new `src/bbl_pipeline/analysis/` subpackage (analyzer). Modifications to 2 existing files (crex_live_predictor.py, cli.py). This follows the existing pattern of inference modules in `inference/` and analysis in dedicated packages.

## Implementation Phases

### Phase A: Core Logger (FR-001 to FR-014)

**Goal**: Record complete match state to Parquet during live predictions.

#### A1: Create MatchStateLogger class

**File**: `src/bbl_pipeline/inference/match_state_logger.py`

- `MatchStateLogger(match_id, league, states_dir, model_version, feature_store_version)`
- `record_ball(match_state, features_dict, predictor, market_odds)` — assembles one BallStateRecord dict
- `flush()` — writes buffered records to `<match_id>.parquet` using pyarrow schema
- `finalize(winner, team_a_score, team_b_score)` — writes/appends to `match_metadata.parquet`
- Internal buffer: `list[dict]`, flushed at innings break, match end, or every 30 balls
- All public methods wrapped in try/except — log errors, never raise (FR-009)
- Computes `deviation`, `deviation_abs`, `deviation_bucket`, `deviation_direction`, `model_prob_delta`, `market_prob_delta` from raw inputs
- Maps `market_fav_team` to batting/bowling team probabilities
- Classifies team strength tiers from feature store win rates

**Dependencies**: pandas, pyarrow, structlog, pathlib

#### A2: Integrate logger into crex_live_predictor.py

**File**: `src/bbl_pipeline/inference/crex_live_predictor.py`

- Add argparse args: `--record-states` (flag), `--states-dir` (str, default `data/match_states/<league>/`)
- Instantiate `MatchStateLogger` when `--record-states` is set
- After each `_write_json_state()` call, invoke `logger.record_ball()` with:
  - `match_state` (existing MatchState dataclass)
  - `features` dict (already computed in the prediction loop)
  - `predictor` object (has `last_raw_prob`, `last_calibrated_*` attributes)
  - Market odds dict (already extracted from CREX API)
- Call `logger.flush()` at innings break detection
- Call `logger.finalize()` at match completion or SIGINT
- Wrap all logger calls in try/except (belt-and-suspenders with logger's own try/except)

#### A3: Unit tests for logger

**File**: `tests/unit/test_match_state_logger.py`

- Test record_ball produces correct dict shape (80+ keys)
- Test flush creates valid Parquet file with correct schema
- Test finalize creates/appends match_metadata.parquet
- Test error isolation (logger.record_ball with bad data — logs error, doesn't raise)
- Test deviation computation (known model_prob/market_prob — expected deviation)
- Test team tier classification (known win rates — expected tiers)
- Test market prob mapping (fav team — batting/bowling team probs)
- Test buffer flush at 30 records

### Phase B: Analysis Engine (FR-015 to FR-026)

**Goal**: Post-match analysis, consolidation, and derived metrics.

#### B1: Create StateAnalyzer class

**File**: `src/bbl_pipeline/analysis/state_analyzer.py`

- `StateAnalyzer(league, states_dir)`
- `consolidate()` — reads all `<match_id>.parquet` files, writes `all_matches.parquet`
- `compute_volatility(match_id)` — computes VolatilityProfile, appends to `volatility_profiles.parquet`
- `extract_signals(match_id, threshold, winner)` — computes SignalEvents with price reversion labels, appends to `signal_events.parquet`
- `calibration_report()` — computes Brier, ECE, LogLoss overall + by phase/innings/league; writes `CALIBRATION_REPORT.md`
- `deviation_analysis()` — return-by-deviation-bucket grouped by phase, tier, league
- Price reversion computation: for each ball where |deviation| > threshold, scan forward in same match for market movement toward model

#### B2: Add analyze-states Click command

**File**: `src/bbl_pipeline/cli.py`

- New Click command following existing patterns (grouped under analysis commands)
- Arguments per CLI contract: `--match-file`, `--league`, `--outcome`, `--consolidate`, `--calibration-report`, `--deviation-threshold`, `--states-dir`
- Delegates to `StateAnalyzer` methods
- Modes: single-match, consolidate, calibration-report, full-analysis

#### B3: Unit tests for analyzer

**File**: `tests/unit/test_state_analyzer.py`

- Test consolidation merges multiple match files correctly
- Test volatility computation (known deltas — expected std dev)
- Test signal extraction (known deviations — correct events with reversion labels)
- Test calibration report (mock data — expected Brier/ECE values)
- Test deviation bucket assignment (known values — correct bucket strings)

### Phase C: Integration and Polish (FR-027 to FR-029, SC-001 to SC-015)

**Goal**: End-to-end validation, meta-model readiness, documentation.

#### C1: Integration test

**File**: `tests/integration/test_record_and_analyze.py`

- Create synthetic MatchState + features + predictions + market odds
- Run `MatchStateLogger.record_ball()` for ~20 balls across 2 innings
- Run `MatchStateLogger.finalize()`
- Run `StateAnalyzer.consolidate()` + `compute_volatility()` + `extract_signals()`
- Verify all output files exist with correct schemas
- Verify calibration report generates without errors

#### C2: Gitignore and data directory setup

- Add `data/match_states/` to `.gitignore`
- Ensure `MatchStateLogger` creates directories on first use (makedirs)

#### C3: Meta-model readiness reporting

- `StateAnalyzer.meta_model_readiness()` — reports match count, feature completeness, sample size per deviation bucket
- Prints warning if < 200 matches recorded (FR-029)

#### C4: Update documentation

- Update `README.md` with match state recording section
- Update `.github/copilot-instructions.md` with new commands and file locations

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage format | Parquet (per-match files) | Project standard, typed, efficient. Per-match avoids corruption. |
| Logger isolation | try/except at every public method | Constitution mandates prediction continuity (FR-009). Double-layered with caller try/except. |
| Feature recording | ALL features, not just TOP_25 | Cheap (~50 floats/ball), enables future analysis of unused features. |
| Deviation computation | In logger, real-time | Deviation = simple subtraction, no look-ahead needed. |
| Price reversion | Post-match batch | Requires look-ahead data; computed in `StateAnalyzer.extract_signals()`. |
| Team tiers | From feature store win rates | Already available, no extra computation. Sorted, top/bottom 33%. |
| CLI integration | argparse flag on predictor, Click command for analysis | Predictor uses argparse (standalone), analysis uses Click (bbl-pipeline). |

## Complexity Tracking

> No constitution violations detected. No complexity justifications needed.
