# Research: Match State Data Logging System

**Feature**: `001-match-state-logging`  
**Date**: February 17, 2026

## R1: What data does the CREX live predictor already capture?

**Decision**: The live predictor already captures ~90% of what we need per-ball, but in volatile JSON format (overwritten each cycle). We need to persist it in append-only Parquet.

**Rationale**: 
- `output-json` already contains: all raw state, all calibration chain probabilities (raw, smoothed, combined, phase, per-over, league), all computed features dict, market odds (fav_team, back_odds, lay_odds, fav_prob), match metadata
- `prediction_history` is minimal (8 fields only, no features/odds)
- `livematch.json` has full debug payload but is overwritten each poll cycle
- **Gap**: No persistent structured storage, no outcome recording, no deviation computation, no league tagging in history, no model version tracking

**Alternatives considered**:
- Build from scratch: Rejected — 90% of data capture already exists in `_write_json_state()`
- Parse `livematch.json` retroactively: Rejected — overwritten each cycle, data lost

## R2: What is the exact feature set to record?

**Decision**: Record ALL features from `RealTimeFeatureMapper.create_feature_dataframe()` (same as training schema), not just TOP_FEATURES used by model.

**Rationale**: 
- Training parquet has 50+ columns; inference computes the same via `realtime_mapper.py`
- TOP_FEATURES (25 features) are what model uses, but recording ALL features enables future analysis of unused features
- Features already returned as `dict[str, float|str]` in the `features` field of output JSON
- Key features for deviation/edge analysis: `team_strength_diff`, `resource_win_prob`, `pressure_index`, `projected_score`, `score_vs_par`

**Alternatives considered**:
- Record only TOP_FEATURES: Rejected — recording all is cheap (50 floats per ball) and enables future flexibility

## R3: How should market odds be captured and converted?

**Decision**: Capture raw CREX odds (back/lay strings) AND compute implied probabilities for both teams (not just favorite).

**Rationale**:
- CREX API provides odds for favorite only via `market_fav_team`, `market_back_odds`, `market_fav_prob`
- Currently `market_fav_prob = 100 / (100 + back_odds)` — only for the favorite team
- For deviation analysis, we need implied probability for BOTH teams: `batting_team_market_prob` and `bowling_team_market_prob`
- Need to map `market_fav_team` to batting/bowling team identity to compute correct deviation direction
- Back/lay odds should be stored raw for spread analysis

**Alternatives considered**:
- Store only favorite prob: Rejected — need per-team implied probability for model-market deviation computation

## R4: Where should match state data be stored?

**Decision**: Append-only Parquet files at `data/match_states/<league>/<match_id>.parquet`, consolidated per league.

**Rationale**:
- Parquet is already the standard format in this project (training data, feature stores)
- Per-match files avoid concurrency issues and enable incremental processing
- League subdirectories align with existing `data/` structure (`data/bbl_raw/`, `data/ilt_raw/`, etc.)
- Consolidation into `data/match_states/<league>/all_matches.parquet` for analysis queries
- Match outcome can be appended as metadata column after match completion

**Alternatives considered**:
- SQLite: Rejected — adds dependency, project already standardized on Parquet
- Single CSV per match: Rejected — Parquet is more efficient and typed
- Append to single file: Rejected — risk of corruption on crash, harder to manage

## R5: How to integrate logging without disrupting live predictions?

**Decision**: Add a `MatchStateLogger` class that wraps the existing prediction loop, called from `_write_json_state()` with try/except to isolate failures.

**Rationale**:
- Constitution requires prediction continuity (FR-009)
- `_write_json_state()` already has all data assembled in one place
- Logger should be a separate class with its own error handling
- Enable/disable via `--record-states` CLI flag (opt-in, no impact on existing usage)
- Buffer in memory, flush to disk at innings break or match end

**Alternatives considered**:
- Separate process/thread: Rejected — adds complexity, data is already available in main loop
- Always-on logging: Rejected — opt-in is safer for existing users

## R6: How to compute and store price reversion labels?

**Decision**: Compute price reversion labels as a post-match batch process, not real-time.

**Rationale**:
- Price reversion = "did market odds subsequently move ≥50% toward model prediction within same match"
- This requires looking at future states (impossible in real-time)
- Post-match processing: load per-match Parquet, for each ball state where |deviation| > threshold, check if market moved toward model in subsequent balls
- Store as additional column: `price_reverted` (bool), `reversion_magnitude` (float), `balls_to_reversion` (int)

**Alternatives considered**:
- Real-time reversion tracking: Rejected — requires look-ahead data
- External labeling script: Possible but integrated post-processing is cleaner

## R7: How to handle match outcome recording?

**Decision**: Record outcome in a separate match metadata file, then join with ball-level data during analysis.

**Rationale**:
- Match outcome is known only after match completion
- Ball-level Parquet shouldn't be rewritten just to add outcome
- Store `data/match_states/<league>/match_metadata.parquet` with columns: `match_id`, `match_url`, `date`, `team_a`, `team_b`, `winner`, `team_a_score`, `team_b_score`, `league`, `venue`, `model_version`, `feature_store_version`
- Outcome can be scraped from CREX match page after completion, or manually entered

**Alternatives considered**:
- Embed outcome in every ball row: Rejected — wasteful and requires rewriting data
- Skip outcome recording: Rejected — essential for calibration analysis

## R8: Model calibration status — signal vs probability

**Decision**: Model outputs ARE calibrated probabilities (multi-stage isotonic calibration chain), but calibration quality against live market conditions is currently unverified. Record both raw and all calibration stages to enable verification.

**Rationale**:
- The model applies 4-5 calibration stages: raw → combined isotonic → innings-specific → phase-specific → per-over → league scaling
- OOF analysis shows ECE ≈ 0.0000 on training data for per-over calibration
- BUT: no verification against live market outcomes has been done
- By recording all calibration stages AND market odds AND outcomes, we can finally determine:
  1. Is the model truly calibrated against live data? (Brier/ECE on recorded matches)
  2. At what calibration stage does performance degrade? (compare raw vs per-over vs league)
  3. Is the model better treated as signal (deviation from market) or as probability (direct probability)?
- This is a primary goal of the entire system

**Alternatives considered**:
- Assume signal only: Rejected — premature conclusion without evidence
- Assume calibrated: Rejected — unverified claim

## R9: Team strength tier classification

**Decision**: Use feature store win rates to classify teams into top-3, mid, bottom-3 tiers per league at match time.

**Rationale**:
- Feature store already has `team_ratings.parquet` with win rates per team
- For T20I, `FM_OVERRIDES` dict in `store.py` has explicit win rates
- Classification is simple: sort teams by win_rate, top 33% = top, bottom 33% = bottom, rest = mid
- Store tier as string field (`"top"`, `"mid"`, `"bottom"`) for both batting and bowling team

**Alternatives considered**:
- Use team_strength_diff directly: Also stored, but tier labels are more human-readable for analysis
- ELO ratings: Not available in current system

## R10: CLI integration pattern

**Decision**: Add `--record-states` flag to `crex_live_predictor.py` argparse (not a new CLI command), since the live predictor is invoked directly via `python -m`.

**Rationale**:
- Live predictor uses argparse, not Click (unlike `bbl-pipeline` CLI)
- Adding a flag is the minimal change to enable recording
- Also add a separate Click command `analyze-states` to `cli.py` for post-match analysis
- The `--record-states` flag takes an optional output directory (default: `data/match_states/<league>/`)

**Alternatives considered**:
- New Click command: Rejected — live predictor is standalone, not in Click CLI
- Always record: Rejected — opt-in is safer, some users only want predictions
