# Feature Specification: ODI Monte Carlo Standalone Predictor

**Feature Branch**: `009-odi-mc-predictor`  
**Created**: 2026-02-28  
**Status**: Draft  
**Input**: User description: "ODI Monte Carlo standalone predictor with enriched resource calculator and empirical ODI phase distributions for format-agnostic live prediction without ML model dependency"

## Overview

Build a standalone Monte Carlo (MC) predictor mode for ODI (50-over) cricket that works **without requiring a trained ML model or pre-built feature store**. This unlocks live predictions for any ODI/List A match — including obscure domestic competitions (e.g., CSA Provincial Division Two) where we have no training data, no team ratings, and no venue stats.

**Motivation**: Today the live predictor (`crex_live_predictor.py`) requires a trained `XGBLogRegEnsemble` model and a feature store with known teams/venues. When we encounter unknown teams (like "Eastern Storm" vs "Griqualand West"), predictions collapse to 0%/100% because the model can't find team ratings. An MC-only mode uses first-principles simulation — phase-specific run/wicket distributions from empirical ODI data — to produce calibrated win probabilities without any pre-trained artifacts.

**Two Workstreams**:
1. **MC-Only ODI Predictor** — Extend the existing `--mc-only` mode (currently T20-only) to support ODI/50-over format with proper ODI phase distributions and resource tables
2. **Enriched Resource Calculator** — Improve the `ResourceFeatureCalculator` and MC engine with richer, empirically-derived features that represent state-of-the-art in cricket Monte Carlo modeling

## Definitions

- **MC-only mode**: Prediction using Monte Carlo simulation with `resource_win_prob` as terminal evaluator (no ML model). Already exists for T20 reduced-over matches
- **ODI phase system**: 4-phase model (powerplay/middle/setup/death) vs T20's 3-phase model (powerplay/middle/death). ODI phases defined in `FormatConfig.odi()`
- **resource_win_prob**: Heuristic win probability computed from DLS resources remaining, score vs par, wickets, and run rate — the terminal evaluator in MC-only mode
- **Phase distribution**: Empirical per-ball run scoring probabilities (0/1/2/3/4/6) and wicket rates for each match phase, derived from historical ball-by-ball data
- **FormatConfig**: Configuration object holding all format-specific constants (par score, phase boundaries, DLS tables, wicket penalties)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - MC-Only Live Prediction for Unknown ODI Teams (Priority: P1)

As a betting analyst, I want to run live predictions on any ODI/List A match regardless of whether the teams exist in my feature store, so I can cover domestic competitions like CSA Provincial or County Championship without needing to retrain models.

**Why this priority**: This is the core problem — today we simply cannot predict matches with unknown teams. This delivers immediate value for any ODI match worldwide.

**Independent Test**: Run `crex_live_predictor.py --mc-only` against a live CSA Provincial match (e.g., Eastern Storm vs Griqualand West) and verify reasonable win probability predictions (not 0%/100%) throughout the match.

**Acceptance Scenarios**:

1. **Given** a live ODI match between teams not in any feature store (e.g., "Eastern Storm" vs "GRB"), **When** I run the predictor with `--mc-only --model-dir models/odi_v1`, **Then** the system produces win probability predictions between 5-95% that update every ball and reflect match situation (score, wickets, run rate, target).
2. **Given** a second innings chase in an ODI with 184 runs remaining from 162 balls with 8 wickets in hand, **When** the MC engine simulates 5,000 paths, **Then** the mean win probability reflects a "comfortable" chase (roughly 55-75%) with a confidence interval.
3. **Given** a first innings ODI at 250/3 after 40 overs, **When** MC simulates the remaining 10 overs, **Then** the projected final score uses ODI-specific run rate expectations (death overs ~7.3 RPO, not T20 death at ~9.5 RPO).

---

### User Story 2 - ODI-Specific Phase Distributions in MC Engine (Priority: P1)

As a system developer, I want the Monte Carlo sampler to use empirically-derived ODI run/wicket distributions (4 phases: powerplay, middle, setup, death) so that simulated ball outcomes reflect realistic ODI scoring patterns rather than T20 defaults.

**Why this priority**: MC accuracy depends entirely on realistic ball-by-ball outcome distributions. Using T20 distributions for ODI gives wrong run rates (T20 avg ~8.3 RPO vs ODI avg ~5.2 RPO), wrong boundary frequencies, and wrong wicket rates. This is a prerequisite for any accurate ODI MC prediction.

**Independent Test**: Simulate 100,000 ODI innings from scratch (0/0, 300 balls) and verify the average total score is approximately 250-260 (matching empirical ODI average of 257.7 for male).

**Acceptance Scenarios**:

1. **Given** ODI powerplay phase (overs 1-10), **When** sampling 100,000 balls, **Then** the average run rate is approximately 4.8-5.0 RPO with dot ball rate ~35-40% and boundary rate ~16-18%.
2. **Given** ODI death phase (overs 41-50), **When** sampling 100,000 balls, **Then** the average run rate is approximately 7.0-7.5 RPO with higher boundary frequency (~22-25%) and higher wicket rate (~7-9% per ball).
3. **Given** ODI setup phase (overs 35-40), **When** sampling 100,000 balls, **Then** the scoring pattern shows acceleration from middle overs (~5.5-6.0 RPO) with moderate boundary increase.
4. **Given** a `MatchState` with `total_balls=300`, **When** the sampler determines phase, **Then** it correctly uses ODI 4-phase boundaries (PP: 1-10, Mid: 11-34, Setup: 35-40, Death: 41-50).

---

### User Story 3 - Enriched Resource Calculator for ODI (Priority: P2)

As a system developer, I want the resource-based terminal evaluator (`resource_win_prob`) to use ODI-calibrated DLS tables, wicket penalties, and chase difficulty parameters so that MC terminal states are evaluated with ODI-appropriate baselines.

**Why this priority**: The terminal evaluator is the "judge" that converts simulated match states into win probabilities. Using T20-calibrated parameters (par=165, DLS tables from 120-ball innings) for ODI (par=258, 300-ball innings) produces wildly wrong evaluations. This builds on Story 2 to complete the ODI MC pipeline.

**Independent Test**: Evaluate `resource_win_prob` for known ODI scenarios: (a) chasing 280 at 150/2 after 30 overs → should show ~65-75% win probability, (b) first innings 180/7 after 40 overs → should show ~25-35% win probability of setting a winning total.

**Acceptance Scenarios**:

1. **Given** an ODI chase of 280 with score 150/2 after 30 overs (RRR=6.5), **When** evaluating resource_win_prob, **Then** the probability reflects a favorable position (65-75%) considering 8 wickets and 120 balls remaining.
2. **Given** a first innings ODI at 180/7 after 40 overs, **When** evaluating resource_win_prob, **Then** the probability reflects a below-par score with depleted batting resources (~25-35%).
3. **Given** the ODI `FormatConfig`, **When** the evaluator uses DLS resource tables, **Then** it uses the empirical ODI DLS table (10 wicket levels × 11 overs-remaining points) from `FormatConfig.odi()`.

---

### User Story 4 - MatchState Support for 300-Ball Innings (Priority: P1)

As a system developer, I want the `MatchState` dataclass to accept `total_balls=300` (50 overs) so that ODI matches can be simulated without validation errors.

**Why this priority**: The current `MatchState` enforces `total_balls` in range 6-120 (T20 only). This is a hard blocker for any ODI simulation — no ODI work can proceed without it.

**Independent Test**: Create a `MatchState(innings=1, score=0, wickets_lost=0, balls_remaining=300, total_balls=300, league="odi", batting_team="Team A", bowling_team="Team B")` without raising `ValueError`.

**Acceptance Scenarios**:

1. **Given** `total_balls=300`, **When** creating a MatchState, **Then** the state is valid and all properties (`overs_completed`, `phase`, `is_over`, `runs_required`) function correctly.
2. **Given** `total_balls=300` and `balls_remaining=120`, **When** checking `phase`, **Then** it returns "death" (overs 31-50 completed, in death phase for ODI).
3. **Given** `total_balls=300`, **When** simulating ball-by-ball, **Then** `apply_outcome()` correctly increments score, decrements balls_remaining, and detects innings completion at 0 balls or 10 wickets.

---

### User Story 5 - Empirical ODI Phase Distribution Generation (Priority: P2)

As a data scientist, I want to derive ODI phase distributions from historical ball-by-ball data (Cricsheet ODI JSONs) so that MC simulations are backed by empirical evidence rather than expert estimates.

**Why this priority**: Estimated distributions will be approximate. Mining actual ODI ball-by-ball data produces accurate, defensible distributions. This improves prediction quality but is not required for initial functionality (can start with expert estimates).

**Independent Test**: Run the distribution extraction script on 1,000+ ODI matches and verify output matches published cricket statistics (e.g., ICC average run rates by phase).

**Acceptance Scenarios**:

1. **Given** 1,600+ male ODI matches from Cricsheet (2010+), **When** extracting phase distributions, **Then** the script produces run probability vectors for each of 4 phases that sum to 1.0 and match known ODI scoring patterns.
2. **Given** extracted distributions, **When** saved as `phase_distributions_odi.json`, **Then** the MC sampler automatically loads and uses them when `league="odi"` is specified.
3. **Given** extracted wicket probabilities by phase and wickets-down, **When** compared against the current T20-derived `WICKET_PROB` and `WICKET_MULTIPLIER`, **Then** ODI-specific values reflect lower overall wicket rates (~3-5% per ball vs T20's ~5-8%) and different lower-order multipliers.

---

### User Story 6 - State-of-the-Art MC Enrichments (Priority: P3)

As a data scientist, I want the MC engine to incorporate advanced cricket simulation features — innings momentum, batting partnership effects, bowler spell patterns, and pitch deterioration — so that simulated paths better reflect real match dynamics and approach state-of-the-art Monte Carlo cricket models.

**Why this priority**: These are accuracy improvements over the basic phase-distribution model. Each enrichment independently improves simulation realism but requires empirical calibration. Can be implemented incrementally after the core ODI MC pipeline is working.

**Independent Test**: Compare base MC predictions against enriched-MC predictions for 100 completed ODI matches (using recorded match states) and measure Brier score improvement.

**Acceptance Scenarios**:

1. **Given** a batting partnership of 100+ runs, **When** the MC sampler generates the next ball, **Then** boundary probability is increased by a partnership momentum factor (e.g., +10-15% boundary rate for established pairs).
2. **Given** a new batsman facing their first 10 balls, **When** the MC sampler generates outcomes, **Then** dot ball probability is elevated (~+5-10%) reflecting typical "playing themselves in" behavior in ODIs.
3. **Given** overs 45-50 of a second innings chase, **When** the pitch deterioration factor is applied, **Then** wicket probability increases relative to early-innings base rates (reflecting tired bowlers but variable bounce).
4. **Given** enriched MC vs base MC predictions across 100+ completed matches, **When** comparing Brier scores, **Then** enriched MC shows measurable improvement (target: 2-5% Brier reduction).

---

### Edge Cases

- What happens when a match has fewer than 50 overs per side (e.g., rain-reduced ODI to 35 overs)? The system should detect reduced overs from CREX and scale phase boundaries proportionally using existing `get_scaled_phase_boundaries()` logic adapted for ODI.
- How does the system handle a D/L revised target mid-match? The `--revised-target` CLI flag already exists; MC should respect it and recalculate chase difficulty from the new target.
- What happens when no phase distribution file exists for the league? Falls back to the default global ODI distributions (derived from all ODI data, not league-specific).
- How does the system handle super overs in an ODI? Treated as a special 1-over match via existing `FormatConfig.t20_reduced(1)` — not within scope of this spec.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `MatchState` dataclass MUST accept `total_balls` values from 6 to 300 (inclusive, divisible by 6) to support T20 through ODI formats.
- **FR-002**: The MC engine (`simulate`, `simulate_vectorized`) MUST correctly simulate ODI matches with 300-ball innings, using ODI phase boundaries for ball sampling.
- **FR-003**: The `NextBallSampler` MUST load and use ODI-specific phase distributions (`phase_distributions_odi.json`) when the match format is ODI (detected via `total_balls=300` or `league` containing "odi"/"odm").
- **FR-004**: ODI phase distributions MUST include 4 phases (powerplay, middle, setup, death) with empirically-derived run probability vectors and wicket rates for each phase.
- **FR-005**: The `TerminalStateEvaluator` MUST use `FormatConfig.odi()` constants (par=257.7, DLS tables, wicket penalties) when evaluating ODI terminal states.
- **FR-006**: The `crex_live_predictor.py` MUST support `--mc-only` mode for ODI matches, bypassing the ML model and producing predictions from MC simulation alone.
- **FR-007**: The MC-only ODI predictor MUST produce calibrated win probabilities using Platt/isotonic calibration trained on historical ODI match states.
- **FR-008**: A script MUST exist to extract ODI phase distributions from Cricsheet JSON match data and produce `phase_distributions_odi.json`.
- **FR-009**: The `get_phase()` function MUST correctly handle ODI phase boundaries (PP: overs 1-10, Middle: 11-34, Setup: 35-40, Death: 41-50) when `total_balls=300`.
- **FR-010**: The MC sampler MUST apply wicket multipliers by wickets-down that are calibrated for ODI (lower base wicket rate, different lower-order progression vs T20).
- **FR-011**: The `--record-states` functionality MUST work in MC-only ODI mode, recording all ball states with calibration chain values to parquet files.
- **FR-012**: Phase distributions MUST support both male and female ODI variants with separate distribution files.

### Key Entities

- **ODI Phase Distribution**: Run probability vector (0/1/2/3/4/5/6 runs per ball) and wicket probability for each of 4 ODI phases. Stored as JSON file loadable by `NextBallSampler`.
- **ODI FormatConfig**: Configuration object with 50-over constants (par=257.7, 300 balls, 4-phase system, ODI DLS tables, ODI wicket penalties). Already partially exists in `FormatConfig.odi()`.
- **MC Calibrator (ODI)**: Platt or isotonic scaling function that maps raw MC `resource_win_prob` to calibrated win probabilities. Trained via OOF cross-validation on historical ODI data.

## Assumptions

- **ODI gender detection**: The system infers gender from the league code (e.g., "odm_female" → female ODI constants). If ambiguous, defaults to male.
- **Unknown teams fallback**: In MC-only mode, team strength is assumed equal (0.5 win rate for both teams) since there is no feature store lookup. This is acceptable for MC-only mode where predictions are driven by match situation, not team ratings.
- **Venue stats fallback**: In MC-only mode, venue statistics default to the ODI global average (par=257.7, bat_first_wr=0.49). CREX-scraped venue stats (if available) can override these.
- **Calibrator training data**: MC calibrators for ODI will be trained on the same ODI match data used for the `odi_v1` model (2,932 matches, 1.58M samples). If this data is insufficient for MC calibration, we accept higher initial Brier scores with a plan to improve as more data is collected.
- **Distribution file location**: Phase distribution JSON files are stored in the model directory (e.g., `models/odi_v1/phase_distributions_odi.json`) or data directory as fallback, consistent with existing T20 distribution loading in `NextBallSampler`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: MC-only predictions for unknown ODI teams produce reasonable win probabilities (5-95% range) throughout all match phases, verified against 10+ completed ODI matches retrospectively.
- **SC-002**: Simulated ODI innings (100,000 simulations from 0/0) produce average totals within ±10 runs of the empirical ODI average (257.7 for male, 227.8 for female).
- **SC-003**: MC-only ODI Brier score is within 15% of the trained ML model's Brier score (odi_v1: 0.1609) when evaluated on the same test set. Target: Brier ≤ 0.185.
- **SC-004**: Live prediction latency in MC-only mode remains under 500ms per ball (including 5,000 MC simulations) on standard hardware.
- **SC-005**: The predictor successfully runs against a live CREX ODI match with unknown teams from start to finish without crashes or extreme predictions.
- **SC-006**: Enriched MC features (partnership momentum, new batsman factor) each demonstrate measurable Brier improvement (≥0.5% reduction) in backtesting against base MC.
