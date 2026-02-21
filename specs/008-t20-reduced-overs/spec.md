# Feature Specification: T20 Reduced-Over Match Support via Monte Carlo Simulation

**Feature Branch**: `008-t20-reduced-overs`  
**Created**: 2026-02-21  
**Status**: Draft  
**Input**: User description: "For T20 matches we have the Monte Carlo setup, so we can use it to handle reduced-over matches (rain-affected / DLS scenarios). Focus on T20 only."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Monte Carlo Predicts Correctly in a Reduced-Over T20 (Priority: P1)

A live T20 match is reduced to 15 overs per side due to rain. The operator starts the live predictor with the known match length. The Monte Carlo engine simulates forward using 15 overs (90 balls) as the horizon instead of the standard 20 overs (120 balls). The win probability output reflects the shorter game — par scores, phase boundaries, and resource calculations all scale to the reduced length — so the prediction is sensible rather than treating 15 balls remaining as "3 overs left in a 20-over game."

The system outputs both a raw resource-based probability and a calibrated probability optimized for low log loss. The calibrated output is used for betting decisions, where long-term profitability requires sharp, well-calibrated probabilities that outperform market odds.

**Why this priority**: Without this, any reduced-over match produces nonsensical predictions. This is the core capability — everything else builds on it.

**Independent Test**: Provide a match state at over 8 of a 15-over match (e.g., 75/2). Compare Monte Carlo output against the same state in a 20-over match. The reduced-over match should show a meaningfully different (higher) win probability for the batting team because they are proportionally further ahead.

**Acceptance Scenarios**:

1. **Given** a T20 match reduced to 15 overs per side, **When** the live predictor is started with `total_overs=15`, **Then** the Monte Carlo engine simulates exactly 90 balls per innings (not 120) and produces win probability between 0 and 1.
2. **Given** a 12-over match with batting team at 85/3 after 8 overs, **When** Monte Carlo runs, **Then** phase classification treats over 10–12 as death overs (not middle overs as it would in a 20-over game).
3. **Given** a reduced-over match in the first innings, **When** expected score is projected, **Then** the par score is scaled proportionally using DLS resource curves (e.g., 15-over par ≈ 135, not 163).

---

### User Story 2 — Second Innings with Revised DLS Target (Priority: P2)

Rain interrupts during the innings break and the second innings is reduced. The match now has a DLS-revised target. The operator provides the revised target and overs available. The Monte Carlo engine uses the revised target for chase calculations and simulates only the available overs.

**Why this priority**: DLS-adjusted targets are the most common form of rain interruption. Without this, the system would use the first innings total +1 as the target, which is wrong.

**Independent Test**: Set up a match state where team 1 scored 180 in 20 overs, but team 2 has only 15 overs (DLS target 156). Run Monte Carlo with `revised_target=156, total_overs=15`. Verify the chase difficulty calculation uses 156 (not 181) and the horizon is 90 balls.

**Acceptance Scenarios**:

1. **Given** a match where first innings completed normally but second innings is reduced to 15 overs with DLS target 156, **When** the predictor runs, **Then** required run rate and chase calculations use 156 as the target.
2. **Given** a revised target of 120 in 10 overs, **When** the chasing team is at 60/1 after 5 overs, **Then** Monte Carlo correctly assesses the chase as roughly even (required rate ≈ current rate) rather than heavily favoring the chaser (as it would against a target of 181 in 20 overs).

---

### User Story 3 — Different Overs Per Innings (Priority: P3)

In some rain-affected matches, each innings has a different number of overs (e.g., team 1 batted 18 overs before rain stopped play, team 2 gets 15 overs with DLS target). The system handles asymmetric innings lengths, applying the correct total overs and target for each innings independently.

**Why this priority**: Less common than symmetric reductions, but still occurs in live T20 cricket. Builds on P1 and P2 capabilities.

**Independent Test**: Set up a match where innings 1 was 18 overs (team scored 165) and innings 2 is 15 overs (DLS target 145). Run Monte Carlo during innings 2. Verify the system uses 15-over phase boundaries and 145 as the target, not 18-over boundaries or 166.

**Acceptance Scenarios**:

1. **Given** innings 1 completed in 18 overs and innings 2 is set at 15 overs, **When** Monte Carlo simulates the second innings, **Then** it uses 90 balls as the horizon and the DLS-revised target for the chase.
2. **Given** a mid-innings rain interruption that reduces the current innings from 20 to 16 overs, **When** the predictor resumes, **Then** it recalculates with the new total overs and the simulation horizon adjusts to end at over 16.

---

### Edge Cases

- **5-over match (minimum viable T20):** System must handle matches as short as 5 overs per side — phases compress appropriately (powerplay may be only 2 overs).
- **Overs reduced mid-innings:** If rain interrupts during the innings and the total overs change while batting is in progress, the CREX scraper detects the updated overs from the match page automatically. The system recalculates with the new total immediately on the next scrape cycle — no operator intervention or restart required.
- **Match where total_overs is not provided:** System defaults to 20 overs and behaves identically to the current production behavior. No regressions.
- **Target exactly 1 run in a 5-over match:** Chase Win probability should be very high (near 1.0) — not broken by edge-case par/resource scaling.
- **Wickets-heavy reduced match (e.g., 8/5 in 3 overs of a 10-over game):** Resource calculations must handle high wicket counts in compressed formats realistically.
- **Second innings score exceeds revised target on the exact last ball:** System recognizes the chase as successful.
- **Super over after a tied reduced-over match:** If a reduced-over match is tied and goes to a super over, the system reverts to standard 1-over (6 balls) per side behavior. The super over is treated as an independent mini-match — `total_overs` resets to 1, phases are irrelevant (all death), and the MC engine simulates 6 balls. No special configuration needed beyond accepting `total_overs=1` (relaxing the minimum from 5 to 1 for super overs only).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a `total_overs` parameter (integer, 1–20) for each innings, defaulting to 20 when not specified. The value 1 is reserved for super overs only; standard reduced matches use 5–20. Input sources in priority order: (1) CLI arguments `--total-overs` and `--revised-target` override all else, (2) auto-detection from CREX match page (data found near the odds portal section), (3) default to 20 overs if neither source provides a value. Mid-innings reductions are detected automatically via CREX scraping on each poll cycle.
- **FR-002**: System MUST accept an optional `revised_target` parameter for the second innings, representing the DLS-adjusted target score. Same input priority: CLI override → CREX auto-detect → not set.
- **FR-003**: Monte Carlo simulation engine MUST use `total_overs × 6` as the total balls for simulation horizon instead of the hardcoded 120.
- **FR-004**: Phase boundaries (powerplay, middle, death) MUST scale proportionally to the total overs. Scaling rules:
  - Powerplay: ~30% of total overs (minimum 2, maximum 6)
  - Death: last ~25% of total overs (minimum 2)
  - Middle: all overs between powerplay and death
- **FR-005**: Par score projection MUST scale to reduced overs using the existing DLS resource curve, not linearly. Example: 15-over par ≈ 83% of 20-over par (not 75%).
- **FR-006**: Expected score calculations MUST be relative to the reduced-over par score, not the 20-over par score.
- **FR-007**: Resource percentage calculations MUST be relative to the actual total overs — "5 overs remaining in a 15-over match" has different resource implications than "5 overs remaining in a 20-over match."
- **FR-008**: When `revised_target` is provided for the second innings, required run rate and chase probability calculations MUST use the revised target instead of first innings total + 1.
- **FR-009**: Match state validation MUST allow `balls_remaining` values from 0 up to `total_overs × 6` (not hardcoded 0–120).
- **FR-010**: The `overs_completed` calculation MUST use actual total balls (`total_overs × 6`) instead of hardcoded 120.
- **FR-011**: When `total_overs` is not provided or not detected, the system MUST default to 20 overs with identical behavior to the current production system (zero regression).
- **FR-012**: Match state recording MUST capture `total_overs` and `revised_target` fields alongside all existing logged columns, for future calibration analysis.
- **FR-013**: The live predictor MUST log the effective total overs and any revised target when they differ from default (20 overs, no revision).
- **FR-014**: When `total_overs < 20`, the system MUST use Monte Carlo simulation as the sole prediction engine (bypassing the trained XGBLogRegEnsemble model and its calibration chain). When `total_overs == 20`, the standard model + calibration chain is used as today.
- **FR-015**: When a match transitions from 20 overs to reduced overs mid-innings (detected via CREX), the system MUST immediately switch to Monte Carlo-only prediction mode and log the transition (previous prediction mode, new total overs, ball at which the switch occurred).
- **FR-016**: Monte Carlo output for reduced-over matches MUST include both a raw resource-based win probability and a calibrated win probability. The calibrated probability MUST be optimized for low log loss, as predictions are used for live betting where long-term profitability depends on calibration sharpness.
- **FR-017**: The calibration method for Monte Carlo predictions MUST be trained on full-length T20 match data: run Monte Carlo on historical 20-over matches (141K+ samples available), compare MC predictions to actual match outcomes, and fit a lightweight calibrator (Platt scaling or temperature scaling). This calibrator is then applied to MC output for both full-length and reduced-over matches, since MC's structural biases are consistent regardless of match length.

### Key Entities

- **Reduced Match Configuration**: The effective match parameters for a shortened game — total overs per innings, scaled phase boundaries, adjusted par score, DLS resource percentages. Derived from `total_overs` and the existing DLS resource tables.
- **Revised Target**: The DLS-calculated target for the chasing team in a rain-affected second innings. Replaces the standard "first innings score + 1" target and changes all chase-related metrics (required run rate, chase difficulty, pressure index).
- **Match State (extended)**: The existing ball-by-ball match state enriched with `total_overs` and `revised_target` fields so downstream components know the match is reduced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a standard 20-over match, the **primary win probability output** (the value used for betting decisions) MUST be identical to current production — no regression in Brier score, ECE, or log loss. New diagnostic fields (e.g., `mc_raw_prob`, `mc_calibrated_prob`) MAY appear in the output JSON and recorded states, but they do not affect the primary prediction for 20-over matches.
- **SC-002**: For reduced-over matches (5–19 overs), Monte Carlo simulations complete within the same time budget as 20-over simulations (under 1 second per prediction cycle).
- **SC-003**: Par score for a 15-over match is within 5% of the DLS-theoretical par (~135 runs), not the 20-over par (163).
- **SC-004**: In a 10-over chase scenario, the difference between the model's predicted win probability and the DLS-implied probability is less than 10 percentage points when the chaser is at par.
- **SC-005**: Phase classification is correct for all supported match lengths — e.g., over 10 in a 12-over match is correctly classified as death, not middle.
- **SC-006**: All existing unit and integration tests pass without modification (backward compatibility).
- **SC-007**: Calibrated Monte Carlo probabilities for reduced-over matches achieve log loss ≤ 0.55 when backtested against full-length T20 MC simulations (using the existing league temperature or Platt calibrators). This ensures betting-grade calibration quality.
- **SC-008**: The calibrated probability output is at least as sharp as the raw MC output (calibration does not collapse predictions toward 0.5).
- **SC-009**: The MC Platt calibrator MUST achieve ECE < 0.0021 when evaluated on the 20-over backtest held-out set (constitutional requirement). For reduced-over-specific ECE, the threshold is deferred until ≥500 reduced-over match ball-states have been recorded, at which point the same ECE < 0.0021 standard applies. Until then, log loss ≤ 0.55 is the interim gate for reduced-over predictions.

## Clarifications

### Session 2026-02-21

- Q: How are `total_overs` and `revised_target` provided — CLI only, CREX auto-detect only, or both? → A: Both. Auto-detect from CREX (data appears near the odds portal), with CLI arguments as fallback if CREX data not found.
- Q: Should reduced-over matches use Monte Carlo only, blend MC + trained model, or adapt the trained model? → A: Monte Carlo only for reduced-over matches (< 20 overs). Standard XGBLogRegEnsemble + calibration chain for full 20-over matches.
- Q: How does the system learn about mid-innings overs reductions — restart, live update command, or CREX auto-detect? → A: CREX auto-detect only. The scraper already watches the match page; it finds the div where updated overs/DLS data is displayed and picks up changes automatically.
- Q: When a match switches from 20 overs to reduced mid-innings, how does the prediction mode transition? → A: Immediate switch to Monte Carlo-only with a log message. No gradual blending.
- Q: Where does the calibration training data for MC predictions come from? → A: Full-length T20 MC backtest. Run Monte Carlo on historical 20-over matches (141K+ samples), fit calibrator (Platt/temperature) on MC predictions vs actual outcomes. Transfers to reduced overs because MC's structural biases are the same regardless of match length.
- Q: Does the ECE < 0.0021 constitutional requirement apply to MC reduced-over predictions? → A: Yes on 20-over backtest data (must pass). Deferred for reduced-over-specific ECE until ≥500 recorded ball-states. Log loss ≤ 0.55 is the interim gate.
- Q: Does "identical" in SC-001 mean no new output fields for 20-over matches? → A: No — "identical" refers to the primary win probability used for betting. New diagnostic MC fields may appear in output but don't affect the primary prediction.
- Q: What happens in a super over following a tied reduced-over match? → A: The system reverts to standard 1-over behavior. Super overs are treated as independent mini-matches with total_overs=1.

## Assumptions

- The DLS resource tables already present in `FormatConfig` are sufficient for scaling par scores to reduced overs. No new resource curves need to be derived.
- Reduced-over matches use the same ball-by-ball run and wicket distributions (powerplay/middle/death phase rates) as full-length T20s — just compressed into fewer overs. This is a reasonable approximation given limited reduced-over training data.
- The trained XGBLogRegEnsemble model and its per-over calibrators are not suitable for reduced-over matches because they were calibrated on full 20-over data. Monte Carlo simulation is the correct approach since it adapts structurally to any match length.
- MC calibration can be trained on full-length 20-over match data and transferred to reduced-over scenarios. MC's biases (e.g., overconfident in death phases, underconfident early) are structural to the simulation engine, not specific to match length, so a calibrator fitted on 20-over MC output generalizes to 15-over or 10-over MC output.
- The operator (or the CREX data source) provides the `total_overs` and `revised_target` externally. The system does not calculate DLS targets on its own.
- Only T20 format is in scope. ODI reduced-over handling will be addressed separately if needed.
- The minimum viable match length is 5 overs per side, consistent with ICC rules for a result in T20 cricket.
