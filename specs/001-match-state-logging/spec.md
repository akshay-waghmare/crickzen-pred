# Feature Specification: Match State Data Logging System

**Feature Branch**: `001-match-state-logging`  
**Created**: February 17, 2026  
**Status**: Draft  
**Input**: User description: "Record match state data with calculated inference fields, CREX market odds, and model probabilities for drift detection, calibration analysis, and market edge detection across leagues. Model outputs are state-deviation signals (not true probabilities). Need to track model-market deviation size, return by deviation bucket, volatility curves, and ultimately build a meta-model that predicts price movement (market reverting toward model) rather than match outcome."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record Complete Match State for Analysis (Priority: P1)

A data scientist runs the win probability model during a live match and wants to automatically capture the complete state at each ball, including all calculated features used by the model. This creates a historical record suitable for later drift detection and calibration analysis.

**Why this priority**: This is the foundation for all other analysis. Without comprehensive data collection, drift detection and market comparison are impossible. Delivers immediate value by creating a growing dataset for future analysis.

**Independent Test**: Can be fully tested by running the model on a single match and verifying that all match states are saved with complete feature sets. Delivers value by building the historical dataset needed for future analysis.

**Acceptance Scenarios**:

1. **Given** a live match in progress, **When** the model generates predictions at each ball, **Then** all match state data (runs, wickets, overs, balls remaining, wickets in hand) is captured
2. **Given** the model calculates inference features, **When** a prediction is made, **Then** all calculated fields (resource features, situational features, team strength) are captured alongside raw state
3. **Given** multiple matches across a tournament, **When** recording completes, **Then** all match states are consolidated into a single queryable dataset per league
4. **Given** an error occurs during match state capture, **When** the system encounters the error, **Then** the error is logged but prediction continues without interruption

---

### User Story 2 - Capture Market Odds with Model Predictions (Priority: P2)

A data scientist wants to compare model predictions against market odds (from CREX) at each match state to identify where the model differs significantly from market consensus. This comparison helps identify potential edges and assess model competitiveness.

**Why this priority**: Critical for assessing whether the model beats market efficiency. Market odds provide ground truth for what "sharp" consensus believes, enabling edge detection.

**Independent Test**: Can be tested by capturing market odds from CREX during live matches and confirming they align temporally with model predictions. Delivers value by enabling immediate market comparison analysis.

**Acceptance Scenarios**:

1. **Given** CREX displays market odds for a match, **When** the model generates a prediction, **Then** current market odds for both teams are captured alongside the model probability
2. **Given** market odds change during the match, **When** the model updates predictions, **Then** the updated odds at that timestamp are captured
3. **Given** market odds are temporarily unavailable, **When** a prediction is made, **Then** the match state is still recorded with odds marked as missing
4. **Given** recorded market odds and model predictions, **When** a data scientist queries the dataset, **Then** they can calculate the difference between model probability and implied market probability at any match state

---

### User Story 3 - Multi-League Data Collection (Priority: P3)

A data scientist wants to record match states across different T20 leagues (BBL, ILT20, SA20, WPL, Super Smash, etc.) to compare model calibration and drift patterns between leagues. Each league may have different characteristics (batting/bowling conditions, team balance) that affect model performance.

**Why this priority**: Enables league-specific calibration analysis and helps identify if model performance degrades differently across leagues. Essential for maintaining multi-league model accuracy.

**Independent Test**: Can be tested by recording matches from two different leagues and verifying that league identifiers and league-specific features are correctly tagged. Delivers value by enabling cross-league calibration comparison.

**Acceptance Scenarios**:

1. **Given** matches from different leagues, **When** recording match states, **Then** each record is tagged with the correct league identifier
2. **Given** the same model is used across leagues, **When** analyzing recorded data, **Then** a data scientist can filter and compare calibration metrics by league
3. **Given** league-specific feature stores, **When** recording match states, **Then** the correct feature store version is referenced for each league

---

### User Story 4 - Detect Model Drift Over Time (Priority: P4)

A data scientist wants to analyze recorded match states over a season to detect if model calibration degrades over time. This involves comparing predicted probabilities against actual match outcomes and identifying systematic biases (e.g., over-predicting favorites, under-predicting underdogs).

**Why this priority**: Ensures long-term model reliability. Drift detection triggers model retraining or recalibration before performance degrades noticeably.

**Independent Test**: Can be tested by simulating a season's worth of matches, comparing predictions to outcomes, and calculating calibration metrics (Brier score, ECE). Delivers value by identifying when recalibration is needed.

**Acceptance Scenarios**:

1. **Given** recorded match states with predictions and outcomes, **When** calculating calibration metrics, **Then** the system computes Brier score and ECE for each time window
2. **Given** multiple time windows (e.g., early season vs late season), **When** comparing calibration, **Then** significant drift is flagged when metrics exceed thresholds
3. **Given** detected drift, **When** a data scientist reviews the data, **Then** they can identify which match phases (powerplay, middle, death) or team types (favorites vs underdogs) show degradation

---

### User Story 5 - Compute Model-Market Deviation as Signal Strength (Priority: P3)

A data scientist wants to compute and record the model-market deviation at each ball as a signal strength metric (not a true probability). The model is a state-deviation detector: when it diverges from market, it indicates stress, not calibrated probability. Tracking deviation size enables systematic analysis of when signals are noise vs actionable.

**Why this priority**: Foundational for all edge analysis. Without classifying deviation into signal strength buckets, the data scientist cannot determine which divergences are profitable. Directly enables User Stories 6, 7, and 8.

**Independent Test**: Can be tested by computing deviation = |model_prob - market_implied_prob| for a completed match and verifying buckets are correctly assigned. Delivers value by creating queryable signal-strength data.

**Acceptance Scenarios**:

1. **Given** model probability and market implied probability at a match state, **When** recording, **Then** the system computes and stores the deviation (absolute and directional) as a separate field
2. **Given** deviation values, **When** querying, **Then** data scientist can filter by deviation size buckets (e.g., 0.05–0.10, 0.10–0.20, 0.20–0.30, 0.30+)
3. **Given** a deviation record, **When** reviewing, **Then** the record indicates direction (model higher = model sees undervaluation, model lower = model sees overvaluation)
4. **Given** deviation data across multiple matches, **When** analyzing, **Then** data scientist can compute average deviation by match phase, team strength tier, and league

---

### User Story 6 - Track Return by Deviation Size (Priority: P4)

A data scientist wants to analyze profitability segmented by model-market deviation size. This reveals the "sweet spot" — deviation ranges where signals are consistently profitable vs noise or traps. For example: 0.2 gap = noise, 0.3 gap = gold, 0.6 gap = trap (model overreacting).

**Why this priority**: Critical for position sizing and systematic entry rules. Without this analysis, trading remains partially intuition-driven.

**Independent Test**: Can be tested by querying historical match states with outcomes, grouping by deviation bucket, and computing win rate and expected value per bucket. Delivers value by quantifying which signal strengths produce profit.

**Acceptance Scenarios**:

1. **Given** recorded match states with deviations and outcomes, **When** grouped by deviation bucket (0.05 increments), **Then** the system computes success rate, sample size, and expected value for each bucket
2. **Given** deviation buckets, **When** filtered by team strength tier (top-3, mid, bottom-3), **Then** data scientist can identify if strong-team deviations are more profitable than weak-team deviations
3. **Given** deviation analysis results, **When** comparing across leagues, **Then** data scientist can determine if optimal deviation thresholds vary by league
4. **Given** a deviation bucket showing negative expected value, **When** reviewing match cases, **Then** data scientist can identify whether the model was overreacting to transient state changes

---

### User Story 7 - Compare Model vs Market Volatility Curves (Priority: P4)

A data scientist wants to compare how model probabilities and market odds evolve over the course of a match to measure volatility differences. The model is reactive (updates instantly to state changes), while markets are conservative (update only on irreversible events). Understanding this volatility gap reveals whether the model overfits to state.

**Why this priority**: Quantifying the volatility difference is essential for understanding why model signals work or fail. If model volatility is consistently 3× market volatility, it explains why raw model probabilities shouldn't be trusted as true odds.

**Independent Test**: Can be tested by plotting model_prob and market_prob over overs for a completed match and computing volatility metrics (standard deviation of ball-to-ball changes). Delivers value by quantifying the reactive vs conservative behavior.

**Acceptance Scenarios**:

1. **Given** recorded model and market probabilities over a full match, **When** computing ball-to-ball changes, **Then** the system calculates volatility (std dev of changes) for both model and market
2. **Given** volatility metrics, **When** comparing model vs market, **Then** the system computes volatility ratio (model_volatility / market_volatility) per match
3. **Given** volatility ratios across matches, **When** segmenting by match type (close match vs blowout, strong team batting vs weak team), **Then** data scientist can identify when model overreaction is most extreme
4. **Given** a match where model dropped a strong team to low probability then quickly recovered, **When** reviewing the volatility curve, **Then** the data shows the "V-shape" pattern indicating state-based overreaction

---

### User Story 8 - Build Price Movement Meta-Model (Priority: P5)

A data scientist wants to build a second model that predicts whether market odds will revert toward the model's prediction. This meta-model doesn't predict match outcomes — it predicts price movement. Inputs include model-market gap, team strength differential, match phase, wickets remaining, and required rate pressure. This is the professional trading evolution.

**Why this priority**: The highest-value outcome of this entire system. Moves from "predicting cricket" to "predicting market behavior." Requires substantial data from P1–P4 to train effectively. Should only be attempted after collecting 200+ matches of deviation data.

**Independent Test**: Can be tested by training on early-season data and validating on late-season data. Delivers value by systematizing entry decisions based on price movement prediction rather than intuition.

**Acceptance Scenarios**:

1. **Given** 200+ matches of recorded model-market deviation data, **When** training the meta-model, **Then** the feature set includes: deviation size, deviation direction, team strength rating, match phase, wickets remaining, required run rate, current run rate, and innings number
2. **Given** a trained meta-model, **When** evaluating on held-out data, **Then** it predicts "market will move toward model" with accuracy above random (>55%)
3. **Given** a live match with current model-market deviation, **When** the meta-model scores the deviation, **Then** it outputs a confidence score for "price movement likely" that can be used as entry signal
4. **Given** meta-model predictions, **When** backtesting against historical deviations and outcomes, **Then** the ROI of meta-model-filtered entries exceeds unfiltered entries by at least 20%

---

### User Story 9 - Detect Strong-Team Recovery Patterns (Priority: P4)

A data scientist wants to analyze whether strong teams recover from early pressure more often than the model predicts. The current model is purely state-based and doesn't account for structural dominance — strong teams bat deep, have better recovery capacity, and handle pressure differently. Markets appear to price this in, but the model doesn't.

**Why this priority**: Directly addresses a known model weakness (state-based overreaction on strong teams). Data collected here feeds into both the meta-model (P5) and potential model improvements (strength-weighted inertia).

**Independent Test**: Can be tested by querying matches where a top-3 team was at 30/3 or similar stress state, then computing actual recovery rate vs model-predicted recovery rate. Delivers value by quantifying the structural dominance gap.

**Acceptance Scenarios**:

1. **Given** recorded match states for strong teams (top-3 by win rate) under pressure (e.g., 3+ wickets in powerplay), **When** comparing model prediction vs actual outcome, **Then** data scientist can compute the "recovery premium" (actual win rate minus model-predicted win rate)
2. **Given** recovery premium data, **When** segmented by match phase (powerplay collapse vs middle-overs collapse vs death-overs collapse), **Then** data scientist can identify in which phases the model most underestimates recovery
3. **Given** model and market predictions during stress states, **When** comparing both against actual outcomes, **Then** data scientist can determine whether market captures recovery potential better than model
4. **Given** recovery analysis results, **When** proposing model improvements, **Then** the data provides specific inertia weights for different team strength tiers

---

### Edge Cases

- **What happens when CREX odds are unavailable?** Match state is still recorded with odds marked as missing; deviation fields are set to null
- **What happens when a match is abandoned mid-game?** Partial match states are saved with match outcome marked as "no result"; deviation analysis excludes these matches
- **What happens when inference features fail to calculate?** The error is logged, raw match state is saved, and missing features are marked as null
- **What happens when multiple leagues play simultaneously?** Each match is recorded independently with correct league tagging
- **What happens when the feature store is outdated?** A warning is logged about version mismatch, but recording continues using available features
- **What happens when storage fills up?** System logs a critical error and alerts the user, but continues capturing to memory buffer until storage is resolved
- **What happens when network errors prevent scraping market odds?** The system retries with exponential backoff, and if unsuccessful, records the match state without odds
- **What happens when model-market deviation is extreme (>0.5)?** These are flagged as potential model overreaction zones for manual review
- **What happens when market odds show zero movement over many balls?** This is a valid signal (market confidence is high); recorded as-is for volatility analysis
- **What happens when team strength data is unavailable for meta-model features?** System uses default team strength tier (mid-tier) and flags the record
- **What happens when there are fewer than 200 matches for meta-model training?** Meta-model training is deferred; system continues collecting data and reports sample count

## Requirements *(mandatory)*

### Functional Requirements

#### Data Collection (P1–P3)

- **FR-001**: System MUST capture all raw match state data at each ball (runs scored, wickets fallen, overs completed, balls remaining, wickets in hand)
- **FR-002**: System MUST capture all calculated inference features (resource features, projected scores, situational features, team strength, player form) used by the model
- **FR-003**: System MUST capture model-generated win probabilities (both raw and calibrated) at each match state
- **FR-004**: System MUST capture CREX market odds (implied probabilities for both teams) at each match state
- **FR-005**: System MUST tag each match state with league identifier (BBL, ILT20, SA20, WPL, SSM, BPL, etc.)
- **FR-006**: System MUST record timestamp for each match state to enable temporal analysis
- **FR-007**: System MUST preserve match metadata (teams, venue, date, match ID) for cross-referencing
- **FR-008**: System MUST store recorded data in a structured format suitable for later analysis (queryable by match, league, team, date range)
- **FR-009**: System MUST continue prediction even if state recording fails (recording errors must not interrupt live predictions)
- **FR-010**: System MUST log errors when data capture fails (missing odds, calculation errors, storage issues)
- **FR-011**: System MUST support recording matches from multiple leagues with league-specific configuration
- **FR-012**: System MUST record the actual match outcome (winner, final scores) for calibration analysis
- **FR-013**: System MUST capture which model version and feature store version were used for each prediction
- **FR-014**: System MUST mark incomplete or missing fields (e.g., unavailable market odds) rather than failing entirely
- **FR-015**: System MUST enable data scientists to query recorded states by match phase (powerplay, middle, death), score situation (ahead/behind), and team role (batting/bowling)

#### Signal & Deviation Analysis (P3–P4)

- **FR-016**: System MUST compute and store the model-market deviation (model_prob − market_implied_prob) at each match state as a dedicated field
- **FR-017**: System MUST classify each deviation into directional categories: "model_higher" (model sees undervaluation), "model_lower" (model sees overvaluation), or "aligned" (within noise threshold)
- **FR-018**: System MUST assign deviation size buckets (e.g., 0.00–0.05, 0.05–0.10, 0.10–0.20, 0.20–0.30, 0.30+) for each match state
- **FR-019**: System MUST record ball-to-ball probability changes for both model and market to enable volatility computation
- **FR-020**: System MUST compute per-match volatility metrics (standard deviation of ball-to-ball probability changes) for both model and market
- **FR-021**: System MUST compute the volatility ratio (model_volatility / market_volatility) per match
- **FR-022**: System MUST record team strength tier (top-3, mid, bottom-3 by league win rate) for each team at each match state

#### Return & Edge Analysis (P4)

- **FR-023**: System MUST enable return analysis by deviation bucket: for each bucket, compute sample count, success rate (model-favored team wins), and theoretical expected value
- **FR-024**: System MUST enable return analysis segmented by team strength tier, match phase, and league
- **FR-025**: System MUST flag "recovery premium" situations: match states where a top-tier team is under pressure (e.g., 3+ early wickets) and compare model prediction vs actual outcome
- **FR-026**: System MUST enable comparison of model accuracy vs market accuracy at each deviation bucket

#### Meta-Model Preparation (P5)

- **FR-027**: System MUST store all features needed for price-movement meta-model training: deviation size, deviation direction, team strength differential, match phase, wickets remaining, required run rate, current run rate, innings number
- **FR-028**: System MUST record whether market odds subsequently moved toward model prediction ("price reversion") within the same match, for each deviation event
- **FR-029**: System MUST report total sample count of recorded deviation events to indicate readiness for meta-model training (target: 200+ matches)

### Key Entities

- **Match State Record**: Represents the complete state of a match at a specific ball, including raw state (runs, wickets, overs), calculated features (resource probability, projected score, team strength), model prediction (raw and calibrated win probability), market odds (implied probabilities), deviation metrics (size, direction, bucket), volatility deltas, metadata (league, teams, venue, timestamp), and model/feature store versions
- **Match Metadata**: Unique identifier, league name, home team, away team, batting first team, venue, match date, match outcome (winner, final scores), tournament/series name, and team strength tiers at match time
- **Model Prediction**: Raw win probability (before calibration), calibrated win probability (after calibration chain), calibration method used (phase/per-over/league), model version identifier, and ball-to-ball delta from previous state
- **Market Odds**: Team A implied probability (from CREX), Team B implied probability, timestamp of odds capture, source (CREX match page), and ball-to-ball delta from previous state
- **Deviation Record**: Model-market gap (signed), absolute deviation size, deviation bucket (0.05 increments), direction category (model_higher / model_lower / aligned), and whether this deviation resulted in price reversion
- **Volatility Profile**: Per-match summary of model volatility (std dev of model deltas), market volatility (std dev of market deltas), volatility ratio, and max single-ball swing for both model and market
- **Signal Event**: A deviation exceeding a configurable threshold, tagged with team strength tier, match phase, required rate, and eventual outcome — the primary unit of analysis for edge detection and meta-model training
- **League Configuration**: League identifier (BBL, ILT20, etc.), model directory path, feature store directory path, calibration method, and league-specific parameters

## Success Criteria *(mandatory)*

### Measurable Outcomes

#### Data Collection

- **SC-001**: Data scientist can record complete match states for at least 50 matches per league with zero data loss
- **SC-002**: Recorded datasets include all raw state fields, calculated features, model predictions, and market odds with less than 5% missing values (excluding unavailable odds)
- **SC-003**: Data scientist can query recorded match states and compute calibration metrics (Brier score, ECE) within 5 seconds for a full season
- **SC-004**: System captures match states for at least 5 different leagues with correct league tagging and configuration
- **SC-005**: Recording errors occur in less than 2% of match states and do not interrupt live predictions

#### Signal & Deviation Analysis

- **SC-006**: Data scientist can identify all match states where model-market deviation exceeds a configurable threshold (e.g., 10%, 20%, 30%) with a single query
- **SC-007**: Data scientist can produce return-by-deviation-bucket analysis showing sample count, success rate, and expected value for each 0.05-increment bucket
- **SC-008**: Data scientist can produce volatility comparison (model vs market) for any match, showing per-over volatility curves and overall volatility ratio
- **SC-009**: Data scientist can identify "sweet spot" deviation ranges where signals are consistently profitable (positive expected value with 30+ samples)

#### Drift & Recovery Detection

- **SC-010**: Data scientist can produce drift analysis reports comparing early-season vs late-season calibration within 10 minutes
- **SC-011**: Data scientist can compute the "recovery premium" for top-tier teams, comparing model-predicted vs actual win rate when under pressure, within 5 minutes
- **SC-012**: Recorded data captures at least 50 "stress state" events (top-tier team under early pressure) per league to enable statistically meaningful recovery analysis

#### Meta-Model Readiness

- **SC-013**: After 200+ recorded matches, system reports data readiness for meta-model training with full feature availability
- **SC-014**: Recorded data includes "price reversion" labels (did market subsequently move toward model) for at least 80% of large-deviation events
- **SC-015**: Meta-model training dataset includes all required features (deviation, team strength, phase, wickets, required rate) with less than 10% missing values

## Assumptions

- **Storage Format**: Match states will be saved in Parquet format for efficient querying and compression
- **Storage Location**: Data will be stored in `data/match_states/<league>/` directory structure
- **Capture Frequency**: Match states will be captured at every ball (consistent with training data granularity)
- **Market Odds Source**: CREX match page provides real-time market odds that can be scraped
- **League Identification**: League parameter will be passed via command-line (similar to existing `--league` parameter in CLI)
- **Model Execution**: Recording will be integrated into existing live prediction workflow (CREX live predictor)
- **Feature Store Availability**: Feature stores for all target leagues are already available and up-to-date
- **Inference Features**: The set of calculated features used in inference is stable and documented
- **Outcomes Availability**: Actual match outcomes will be available after match completion for calibration analysis
- **Historical Data**: Existing matches will not be retroactively recorded; recording starts from implementation forward
- **Query Tool**: Data scientists will use standard data analysis tools (pandas, SQL) to query recorded data
- **Model Calibration Status Uncertain**: Model outputs ARE calibrated probabilities (isotonic/per-over calibration chain), but calibration quality against live market conditions is unverified. Until drift detection and market comparison confirm calibration accuracy, outputs are conservatively treated as signal intensity rather than true probabilities. One key goal of this system is to determine whether model outputs can be trusted as calibrated probabilities or should remain signal-only. The model is reactive (updates instantly to state changes), while markets are conservative (update on irreversible events).
- **Deviation Thresholds**: Default deviation buckets (0.05 increments) and signal thresholds (e.g., 0.10 for "small", 0.20 for "medium", 0.30+ for "large") are configurable per league
- **Team Strength Tiers**: Teams will be classified into strength tiers (top-3, mid, bottom-3) based on league win rates available in the feature store
- **Price Reversion Window**: "Price reversion" is defined as market odds moving at least 50% of the original deviation toward the model's prediction within the same match
- **Meta-Model Data Requirements**: Meta-model training requires minimum 200 matches (~24,000 ball states) of deviation data before meaningful training is attempted
- **Volatility Measurement**: Ball-to-ball probability changes are the primary unit for volatility computation; over-to-over aggregation is also supported
- **Recovery Premium**: "Stress state" is defined as a top-3 team losing 3+ wickets in the powerplay or being 30+ runs behind required rate in the chase
