# Implementation Plan: ODI Win Probability Model

**Branch**: `007-odi-model` | **Date**: 2026-02-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/007-odi-model/spec.md`

## Summary

Build an ODI (50-over) win probability model by: (1) running empirical analysis on 3,085 ODI matches (2010+, male+female) to derive ODI-specific resource constants, (2) refactoring `ResourceFeatureCalculator` into a parameterized class accepting a format config so one calculator serves both T20 and ODI, (3) adding `odi` as a first-class league in the CLI pipeline, and (4) training an `XGBLogRegEnsemble` model with OOF calibration. Gender-specific resource constants (separate par scores, penalty tables) feed a single combined model with gender as a training feature.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: XGBoost, scikit-learn, pandas, numpy, pyarrow, joblib  
**Storage**: Parquet files (ingested data, features, feature store), joblib (models, calibrators)  
**Testing**: pytest (unit + integration), standalone validation scripts  
**Target Platform**: Windows/Linux (local training, Streamlit for visualization)  
**Project Type**: Single Python package (`bbl_pipeline`) with CLI entry point  
**Performance Goals**: Full pipeline (ingest → train) < 30 min for ~3,085 matches; Brier ≤ 0.22  
**Constraints**: ECE < 0.0021 (constitution mandate); no T20 regression (existing models must continue working)  
**Scale/Scope**: ~3,085 ODI matches → ~500K+ training samples; 31 calculator constants to parameterize; 11 processor hardcodes to refactor

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Scalability & Reusability | **PASS** | Parameterized calculator makes the system format-agnostic (T20, ODI, future T10). Config-driven, not hardcoded. |
| II | Pipeline-Driven & Rapid Retraining | **PASS** | `bbl-pipeline retrain --league odi` provides single-command retraining. Same modular pipeline stages. |
| III | Reproducibility & Versioning | **PASS** | Model artifacts versioned as `models/odi_v1/`. Empirical constants stored as reproducible output. |
| IV | Data Integrity & Entity Consistency | **PASS** | ODI data uses same Cricsheet format. Feature store normalization applies. Gender and date filtering enforced. |
| V | Model Calibration & Observability | **PASS** | OOF calibration with ECE < 0.0021 target. Same 7+ calibration methods. Full metrics reporting. |

**Gate Result**: All 5 principles PASS. No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/007-odi-model/
├── plan.md              # This file
├── research.md          # Phase 0 output - empirical findings & design decisions
├── data-model.md        # Phase 1 output - FormatConfig schema, entity schemas
├── quickstart.md        # Phase 1 output - setup & run instructions
├── contracts/           # Phase 1 output - CLI contract, config schema
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/bbl_pipeline/
├── features/
│   ├── calculator.py        # REFACTOR: Parameterize with FormatConfig
│   ├── format_config.py     # NEW: FormatConfig dataclass + T20/ODI presets
│   └── store.py             # MINOR: Add ODI venue/team aliases
├── data/
│   └── processor.py         # REFACTOR: Accept total_overs/total_balls from config
├── ingestion/
│   └── processor.py         # MINOR: Capture `overs` field, add ODI to super-over filter
├── training/
│   └── trainer.py           # MINOR: Add `gender` to TOP_FEATURES (conditional, only when present in training data)
├── inference/
│   ├── crex_live_predictor.py  # MINOR: Pass format config for ODI matches
│   ├── realtime_mapper.py      # MINOR: Use total_overs from config
│   └── schema.py               # ALREADY parameterized (total_overs default)
├── cli.py                   # ADD: ODI league config entry + format_type field
└── config.py                # EXTEND: Add format_type to PipelineConfig

scripts/
└── analyze_odi_empirical.py # NEW: Empirical analysis script (FR-001 through FR-007)

tests/
├── unit/
│   ├── test_format_config.py    # NEW: FormatConfig validation
│   └── test_odi_calculator.py   # NEW: ODI resource calculations
└── integration/
    └── test_odi_pipeline.py     # NEW: End-to-end ODI pipeline test
```

**Structure Decision**: Single Python package, consistent with existing layout. New files limited to `format_config.py` (new abstraction), `analyze_odi_empirical.py` (one-off analysis script), and test files.

## Phase 0: Research

### Research Findings

#### R-001: FormatConfig Design Pattern
**Decision**: Create a `FormatConfig` dataclass that bundles all format-specific constants.
**Rationale**: The calculator has 31 T20-hardcoded values. A config dataclass groups them logically and can be serialized. Factory methods `FormatConfig.t20()` and `FormatConfig.odi(gender='male')` provide presets.
**Alternatives considered**: (a) Subclassing — rejected, too much code duplication. (b) YAML config files — rejected, constants are tightly coupled to code logic and need compile-time validation.

#### R-002: ODI DLS Resource Table Source
**Decision**: Derive empirically from the ODI dataset using the same methodology as T20 (actual runs scored per remaining resources).
**Rationale**: The official ICC DLS tables are copyrighted and not usable. Empirical derivation from 3,085 matches (filtered to 2010+) provides sufficient data density for OversRemaining(0-50) × Wickets(0-10) grid cells.
**Alternatives considered**: (a) Use published academic approximations — rejected, less accurate than empirical data. (b) Interpolate from T20 table — rejected, fundamentally different scoring dynamics.

#### R-003: Gender-Aware Constants Multiplexing
**Decision**: `FormatConfig.odi(gender='male')` and `FormatConfig.odi(gender='female')` return different par scores, penalty tables, and DLS tables. The processor passes the match's gender field to the config factory.
**Rationale**: Male ODI par ~250-260, female ODI par ~180-200. Using a blended par score would degrade predictions for both.
**Alternatives considered**: (a) Single blended constants — rejected (clarified in spec). (b) Separate models — rejected, temperature scaling can be added later.

#### R-004: Processor Refactoring Strategy
**Decision**: Add `total_overs` and `total_balls` parameters to `process_bbl_data()`, defaulting to T20 values (20, 120). ODI calls with (50, 300). Phase boundaries derived from config.
**Rationale**: Minimally invasive. Existing T20 callers need zero changes (defaults preserved). The 11 hardcoded values map cleanly to 2 parameters + format config.
**Alternatives considered**: (a) Completely separate ODI processor — rejected, 95% code overlap. (b) Auto-detect from data — rejected, explicit is better.

#### R-005: Ingestion Changes
**Decision**: Add `overs` field capture in `extract_match_metadata()`. Add `'ODI'` to super-over detection match types. No other changes needed — ingestion is already format-agnostic.
**Rationale**: The `overs` field is needed downstream for filtering (exclude reduced-overs) and format detection. The existing ingestion captures `match_type` and `gender` already.

#### R-006: T20 Regression Safety
**Decision**: All refactoring preserves T20 defaults. `FormatConfig.t20()` returns exactly the current hardcoded values. Unit tests verify T20 calculator output is byte-identical before and after refactoring.
**Rationale**: Constitution Principle I requires no regression. The parameterization must be invisible to existing T20 workflows.

## Phase 1: Design

### Data Model

See [data-model.md](data-model.md) for full entity schemas.

**Key entities:**

1. **FormatConfig** (new dataclass)
   - `total_overs: int` (20 or 50)
   - `total_balls: int` (120 or 300)
   - `par_score: float` (160 or ~250)
   - `league_avg_score: float`
   - `bat_first_win_rate: float` (0.37 or ~0.48)
   - `phase_thresholds: dict` (phase_name → over_boundary)
   - `expected_run_rates: dict` (phase_name → expected_rr)
   - `dls_resource_table: dict` (wickets → {overs_remaining: pct})
   - `first_innings_wicket_penalty_3d: dict` (phase → ease → wickets → penalty)
   - `chase_wicket_penalty_2d: dict` (ease → wickets → penalty)
   - `rrr_midpoint: float` (9.5 or ~6.0)
   - `rrr_beta: float`
   - `sqi_beta: float`
   - `confidence_full_overs: float` (12 or ~25)
   - `score_std_early: float`
   - `score_std_late: float`
   - `score_cap_min: float` (100)
   - `score_cap_max: float` (280 or 500)
   - `endgame_balls: int` (12 or ~30)

2. **ODI League Config** (CLI extension)
   - `json_dir: 'odis_json'`
   - `raw_dir: 'data/odi_raw'`
   - `features_dir: 'data/odi_features'`
   - `feature_store_dir: 'data/odi_feature_store'`
   - `model_prefix: 'odi'`
   - `format_type: 'odi'` (new field, defaults to `'t20'` for existing leagues)

### Implementation Phases

#### Phase A: Empirical Analysis Script (FR-001 → FR-007)
**Scope**: New standalone script `scripts/analyze_odi_empirical.py`
**Inputs**: `odis_json/` + `odis_female_json/` (raw Cricsheet JSON)
**Outputs**: Console report + `scripts/odi_empirical_constants.json`
**Logic**:
1. Parse all ODI JSONs, filter to 2010+, overs=50, has winner
2. Separate male/female stats
3. Compute per gender: avg 1st/2nd innings scores, bat-first win rate
4. Compute run rates by over → confirm 4-phase boundaries (PP 1-10, Mid 11-34, Setup 35-40, Death 41-50)
5. Compute projected score ratios by phase×ease×wickets → `FIRST_INNINGS_WICKET_PENALTY_3D`
6. Compute chase ease × wickets → `WICKET_PENALTY_2D`
7. Compute actual runs scored per resource bucket → `DLS_RESOURCE_TABLE`
8. Output all as structured JSON + Python dict literals for copy-paste into `format_config.py`

#### Phase B: FormatConfig Abstraction (FR-008)
**Scope**: New file `src/bbl_pipeline/features/format_config.py`
**Logic**:
1. Define `@dataclass FormatConfig` with all 20+ fields
2. Factory method `FormatConfig.t20()` → returns current T20 hardcoded values (exact copies)
3. Factory method `FormatConfig.odi(gender='male')` → returns ODI values from empirical analysis
4. Factory method `FormatConfig.odi(gender='female')` → returns female ODI values
5. Validation: ensure all tables have correct dimensions, phases match thresholds

#### Phase C: Calculator Refactoring (FR-008 → FR-013)
**Scope**: Modify `src/bbl_pipeline/features/calculator.py`
**Strategy**: 
1. Add `config: FormatConfig = None` parameter to `ResourceFeatureCalculator.__init__()`
2. Default to `FormatConfig.t20()` if None (preserves backward compat)
3. Replace all 31 hardcoded constants with `self.config.<field>` references
4. Phase boundaries, expected run rates, penalty tables all from config
5. **Critical**: T20 regression test — snapshot current T20 outputs for 10 match states, verify identical after refactoring

#### Phase D: Processor Refactoring (FR-017)
**Scope**: Modify `src/bbl_pipeline/data/processor.py`
**Strategy**:
1. Add `format_config: FormatConfig = None` parameter to `process_bbl_data()`, defaulting to `FormatConfig.t20()` when None. All format-specific values (total_overs, total_balls, phase bins, par score) are read from the config.
2. Replace 11 hardcoded values with `format_config.<field>` references
3. Phase bins derived from `format_config.phase_thresholds`
4. Resource calculator instantiated with `format_config`
5. Default values preserve existing T20 behavior

#### Phase E: Pipeline Integration (FR-014 → FR-019)
**Scope**: Modify `cli.py`, `ingestion/processor.py`, `config.py`
**Changes**:
1. Add `odi` entry to league config with `format_type: 'odi'`
2. Add `overs` field capture to ingestion `extract_match_metadata()`
3. Add `'ODI'` to super-over detection match types
4. In `retrain` command: detect `format_type`, pass appropriate `FormatConfig` to processor
5. Add date filtering (2010+) and overs filtering (exclude < 50) in processing step
6. Add `gender` as a training feature column

#### Phase F: Model Training & Evaluation (FR-020 → FR-022)
**Scope**: Run the pipeline, no code changes needed in trainer
**Steps**:
1. `bbl-pipeline retrain --league odi --version v1`
2. Review OOF calibration report
3. Update model registry
4. Verify Brier ≤ 0.22, ECE < 0.0021

### Constitution Re-Check (Post-Design)

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Scalability & Reusability | **PASS** | `FormatConfig` makes any cricket format addable via config. No format-specific code paths. |
| II | Pipeline-Driven & Rapid Retraining | **PASS** | Single `retrain --league odi` command. Same pipeline stages. |
| III | Reproducibility & Versioning | **PASS** | Empirical constants versioned in `format_config.py`. Model in `models/odi_v1/`. |
| IV | Data Integrity & Entity Consistency | **PASS** | Date/overs filtering gates. Gender field captured. Feature store normalization. |
| V | Model Calibration & Observability | **PASS** | Same OOF analysis with 7+ methods. ECE threshold enforced. |

**Gate Result**: All 5 principles PASS post-design. No violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
