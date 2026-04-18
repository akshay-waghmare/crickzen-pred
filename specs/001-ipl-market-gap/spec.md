# Feature Specification: IPL Model Improvement — Close Market Gap

**Feature Branch**: `001-ipl-market-gap`  
**Created**: 2025-07-16  
**Status**: Draft  
**Input**: User description: "Improve the IPL cricket prediction model to close the gap with the betting market"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accurate Wicket-Heavy Chase Predictions (Priority: P1)

As a prediction consumer monitoring a second-innings chase where the batting team has lost 4 or more wickets, I expect the model to produce win probabilities that closely reflect the match situation — specifically, that heavy wicket loss drastically reduces the chasing team's chances.

**Why this priority**: The wicket penalty gap is the single largest systematic error in the model. At 8 wickets lost, the model's prediction error is 2.5x worse than the market (Brier 0.366 vs 0.146). Fixing this addresses the widest performance gap across the most observations.

**Independent Test**: Run the validation script against historical IPL chase data filtered to 4–8 wickets lost. Compare model Brier scores per wicket-count bucket before and after the change. Deliverable: measurable Brier reduction at each wicket bucket.

**Acceptance Scenarios**:

1. **Given** a second-innings chase where the batting team has lost 5 wickets in the death phase with a comfortable run rate, **When** the model computes win probability, **Then** it assigns a meaningfully lower probability than it does today (current penalty is 1.00 = zero penalty; the updated penalty must reflect empirical IPL loss rates for that situation).
2. **Given** a chase where 8 wickets have fallen at any phase, **When** the model computes win probability, **Then** the Brier score for that bucket improves by at least 50% relative to the current gap (gap of +0.220 reduced to ≤ +0.110).
3. **Given** the existing 273,503-row IPL training dataset, **When** IPL-specific wicket penalties are derived by grouping empirical win rates by wickets_lost × phase × chase_ease, **Then** every penalty value for 4–8 wickets is strictly less than the current table's value for the same cell.

---

### User Story 2 - Reliable Final-Over Predictions (Priority: P1)

As a prediction consumer watching the final over of a chase, I expect the model to produce a probability that accurately reflects the discrete ball-by-ball dynamics — not a smooth sigmoid approximation.

**Why this priority**: Over 20 in the second innings has the worst single-over gap in the entire analysis (+0.170 Brier gap). The current sigmoid formula is fundamentally too simple for 6-ball endgame situations where exact runs-needed and wickets-in-hand determine the outcome.

**Independent Test**: Evaluate the model on all historical IPL final-over chase situations. Measure Brier score for over-20 predictions before and after the change.

**Acceptance Scenarios**:

1. **Given** the final over of a chase with 8 runs needed and 6 wickets in hand, **When** the model computes win probability, **Then** it uses an empirical lookup based on runs_needed × wickets_in_hand rather than the generic sigmoid formula.
2. **Given** an extreme final-over scenario (e.g., 20 runs needed, 1 wicket in hand), **When** the model computes win probability, **Then** the probability is near zero, consistent with historical IPL outcomes for that situation.
3. **Given** the full set of final-over observations from validation data, **When** the over-20 Brier gap is measured, **Then** it is reduced from +0.170 to less than +0.050.

---

### User Story 3 - Current Team Strength Reflected in Predictions (Priority: P2)

As a prediction consumer viewing a match involving Mumbai Indians or Kolkata Knight Riders, I expect the model to reflect those teams' current form rather than relying on all-time historical averages that dilute recent performance.

**Why this priority**: MI and KKR have the largest team-specific Brier gaps (+0.181 and +0.136 respectively). The feature store uses all-time win rates with no recency weighting, meaning a 2015 match carries the same influence as yesterday's match. Additionally, RCB has duplicate entries causing data inconsistency.

**Independent Test**: Regenerate the IPL feature store with recency-weighted ratings, re-run predictions on the 16-match validation set, and compare team-specific Brier scores before and after.

**Acceptance Scenarios**:

1. **Given** the IPL feature store is regenerated with exponential decay recency weighting, **When** MI's team rating is computed, **Then** it reflects recent-season performance more heavily than matches from 5+ years ago.
2. **Given** the RCB team entries currently list both "Royal Challengers Bengaluru" (60%) and "Royal Challengers Bangalore" (48.7%), **When** the feature store is regenerated, **Then** these are merged into a single canonical entry with a unified rating.
3. **Given** the updated feature store and model, **When** predictions are validated on MI and KKR matches, **Then** the team-specific Brier gap is reduced by at least 50% from the current values.

---

### User Story 4 - Accurate First-Innings Death-Over Projections (Priority: P2)

As a prediction consumer watching the death overs (16–20) of a first innings, I expect the model's win probability to reflect realistic IPL scoring norms — not an outdated par score that underestimates the league's scoring environment.

**Why this priority**: Overs 16–17 in the first innings show a Brier gap of +0.072 to +0.093 because the model's scoring midpoint (165.0) is 8 runs below the actual IPL par (173.45). This systematically underestimates the value of first-innings runs in the death phase.

**Independent Test**: Retune the first-innings scoring model parameters against IPL data, re-run predictions for first-innings death overs, and compare Brier scores.

**Acceptance Scenarios**:

1. **Given** the first-innings model currently uses a scoring midpoint of 165.0, **When** it is updated using IPL-specific data, **Then** the midpoint is raised to approximately 173 (within ±3 of the empirical IPL par score of 173.45).
2. **Given** the updated midpoint and steepness parameters, **When** overs 16–17 predictions are evaluated, **Then** the Brier gap for those overs is reduced by at least 40%.
3. **Given** venue data is available, **When** the scoring midpoint is computed, **Then** it incorporates venue-specific adjustments so that high-scoring grounds use a higher midpoint than low-scoring grounds.

---

### User Story 5 - State-Aware Calibration (Priority: P3)

As a prediction consumer, I expect the model's calibrated outputs to vary meaningfully based on match phase and situation, rather than applying a single global temperature scaling that barely moves probabilities.

**Why this priority**: The current temperature scaling provides essentially zero improvement (Brier: 0.1831 → 0.1830). Errors are state-dependent — varying by phase, wickets, and team — and a global temperature cannot correct them. Phase-wise calibration can capture these structural biases.

**Independent Test**: Implement phase-wise Platt scaling (6 calibrators: 3 phases × 2 innings), train on the IPL training dataset, and compare calibration metrics against the current single-temperature approach.

**Acceptance Scenarios**:

1. **Given** the IPL calibration currently uses 2 global temperature scalers (one per innings), **When** phase-wise Platt scaling is implemented, **Then** 6 separate calibrators are trained (powerplay/middle/death × innings 1/innings 2).
2. **Given** the segmented calibrators are trained and applied, **When** model Brier is measured on the validation set, **Then** calibration produces a measurable improvement greater than the current near-zero delta.
3. **Given** the segmented calibrators, **When** predictions are examined per phase, **Then** each phase's calibrated Brier score is equal to or better than its uncalibrated score (no phase regresses).

---

### User Story 6 - Market-Informed Ensemble Predictions (Priority: P3)

As a prediction system operator, I want the option to blend model predictions with live market odds to achieve the best possible prediction accuracy when market data is available.

**Why this priority**: This is the highest-potential improvement since the market already outperforms the model on 63.1% of observations. However, it requires an architecture change and should only be pursued after the fundamental model improvements are in place.

**Independent Test**: Sweep blending weight alpha (0.0 to 1.0) across the 510-observation validation dataset and measure Brier at each alpha. Identify the optimal alpha and confirm it outperforms both pure-model and pure-market baselines.

**Acceptance Scenarios**:

1. **Given** a blending formula `final = alpha × model + (1 - alpha) × market`, **When** alpha is swept from 0.0 to 1.0 on the validation set, **Then** the optimal alpha is identified and the blended Brier score is lower than both the pure-model (0.1977) and pure-market (0.1546) scores.
2. **Given** market data is unavailable for a particular match, **When** the ensemble generates predictions, **Then** it gracefully falls back to the pure model output without errors.
3. **Given** the ensemble is deployed, **When** predictions are generated for a live match with market data, **Then** the system produces both a model-only probability and an ensemble probability, preserving traceability.

---

### Edge Cases

- What happens when the chasing team loses all 10 wickets before the innings completes? The wicket penalty must handle the 10-wicket case (match already lost — probability should be 0.0).
- How does the final-over lookup handle scenarios not present in historical data (e.g., 20 runs needed, 0 wickets in hand)? Missing cells should default to boundary probabilities (0.0 or 1.0 as appropriate).
- What if a team appearing in live data has no entry in the updated feature store (e.g., a newly formed franchise)? The system should fall back to a league-average rating.
- How does the venue-adjusted midpoint behave for new venues with no historical data? It should default to the league-wide par score.
- What happens when the market-as-feature ensemble receives stale or delayed market odds? A staleness threshold should be defined; odds older than the threshold should be discarded and the model falls back to pure-model output.
- How does phase-wise calibration handle phases with insufficient training data? A minimum sample size threshold should be enforced; below it, the calibrator falls back to the global innings-level calibrator.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST derive IPL-specific wicket penalty tables from the 273,503-row training dataset by computing empirical win rates grouped by wickets_lost × phase × chase_ease.
- **FR-002**: System MUST replace the current generic wicket penalty values for 4–8 wickets with the IPL-derived values, ensuring every updated penalty is strictly harsher (lower multiplier) than the current value.
- **FR-003**: System MUST build an empirical final-over lookup table mapping runs_needed (1–20) × wickets_in_hand (0–9) to win probability, derived from historical IPL second-innings final-over data.
- **FR-004**: System MUST use the empirical final-over lookup in place of the current sigmoid formula for all over-20 second-innings predictions.
- **FR-005**: System MUST apply exponential decay recency weighting when computing IPL team ratings, so that recent matches contribute more than older matches.
- **FR-006**: System MUST merge duplicate RCB team entries ("Royal Challengers Bengaluru" and "Royal Challengers Bangalore") into a single canonical entry in the feature store.
- **FR-007**: System MUST update the first-innings scoring model midpoint to reflect the empirical IPL par score (approximately 173), replacing the current value of 165.0.
- **FR-008**: System MUST support venue-adjusted scoring midpoints so that the first-innings model accounts for ground-specific scoring tendencies.
- **FR-009**: System MUST implement phase-wise Platt scaling calibration with 6 separate calibrators (powerplay/middle/death × innings 1/innings 2), replacing the current 2 global temperature scalers.
- **FR-010**: System MUST enforce a minimum sample size threshold for each phase-wise calibrator; if insufficient data exists for a phase, it MUST fall back to the innings-level calibrator.
- **FR-011**: System MUST support a market-as-feature ensemble that blends model probability with market probability using a configurable weighting parameter (alpha).
- **FR-012**: System MUST fall back to pure-model output when market data is unavailable or stale, without any errors or degradation.
- **FR-013**: System MUST produce both a model-only probability and an ensemble probability (when market data is available) to preserve prediction traceability.
- **FR-014**: System MUST provide a validation workflow that re-runs the full model-vs-market comparison after any change, producing Brier scores segmented by phase, over, wickets, and team.

### Key Entities

- **Wicket Penalty Table**: A multi-dimensional lookup encoding the win-probability multiplier for each combination of wickets_lost, match phase (powerplay/middle/death), and chase_ease (comfortable/tight/difficult). Derived empirically from IPL training data.
- **Final-Over Lookup Table**: A two-dimensional lookup mapping runs_needed (1–20) × wickets_in_hand (0–9) to empirical win probability, sourced from historical IPL final-over data.
- **Team Rating**: A per-team strength metric incorporating exponential decay recency weighting, computed from historical match outcomes. Each team has a single canonical entry (no duplicates).
- **Phase-wise Calibrator**: A set of 6 Platt scaling calibrators (3 phases × 2 innings) trained on IPL-specific data to correct systematic biases in the model's raw probabilities.
- **Market Ensemble**: A blending mechanism that combines model predictions with market odds using a tunable weight (alpha), with fallback behavior when market data is absent.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Overall model Brier score drops from 0.1977 to the range of 0.165–0.170, closing 60–70% of the gap to the market's 0.1546.
- **SC-002**: Wicket penalty Brier gap for 4–8 wickets lost is reduced by more than 50% (e.g., 8-wicket gap drops from +0.220 to ≤ +0.110).
- **SC-003**: Over-20 second-innings Brier gap is reduced from +0.170 to less than +0.050.
- **SC-004**: MI and KKR team-specific Brier gaps are each reduced by more than 50% (MI from +0.181, KKR from +0.136).
- **SC-005**: First-innings death-over (overs 16–17) Brier gap is reduced by at least 40% from the current +0.072 to +0.093 range.
- **SC-006**: Phase-wise calibration produces a measurably larger Brier improvement than the current near-zero delta of the global temperature approach.
- **SC-007**: The market-informed ensemble (when market data is available) achieves a Brier score lower than both the pure-model baseline (0.1977) and the pure-market baseline (0.1546).
- **SC-008**: No individual segment (phase, over, or team) regresses in Brier score after any change — improvements must be Pareto-improving or at worst neutral on all segments.

## Assumptions

- The 273,503-row IPL training dataset is representative and sufficient for deriving empirical wicket penalties, final-over lookup tables, and phase-wise calibrators.
- The 16-match, 510-observation validation set is large enough to detect meaningful Brier improvements of the targeted magnitude (0.02–0.03 absolute improvement).
- The current model architecture (XGBLogRegEnsemble, 50/50 blend) remains unchanged; all improvements are to input features, penalty tables, calibration, and ensemble blending — not to the core model training.
- Exponential decay half-life for team ratings will be determined empirically (starting assumption: approximately 2–3 IPL seasons).
- Market data from the exchange will continue to be available in the same format for the market-as-feature ensemble.
- IPL par score of 173.45 is based on recent seasons and may shift over time; the midpoint should be configurable rather than hardcoded.

## Dependencies & Ordering

- **Phase 1** (User Stories 1, 2, 3) can proceed in parallel — they address independent model components.
- **Phase 2** (User Stories 4, 5) depends on Phase 1 completion:
  - User Story 4 (death-over tuning) benefits from User Story 3 (better venue data in feature store).
  - User Story 5 (segmented calibration) should be trained after User Stories 1 and 4 have corrected systematic errors.
- **Phase 3** (User Story 6) depends on Phase 1 and Phase 2 — the market ensemble should only be built on top of an already-improved model to measure true additive value.
