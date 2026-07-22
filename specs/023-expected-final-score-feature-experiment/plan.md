# Plan: Expected-Final Score Feature Experiment

## Objective

Test whether replacing the simple linear `projected_score` family with resource-aware `expected_final_score` features improves T20 and ODI win-probability models without harming any gender slice.

Production models and routing remain unchanged until the experiment passes all gates.

## Hypothesis

`expected_final_score` is the more realistic innings projection because it incorporates format resources, wickets, phase, and DLS-style context. The model should use it directly and for venue-relative context, rather than using the simpler current-run-rate extrapolation.

## Candidate feature contract

Remove from the candidate model:

- `projected_score`
- `projected_vs_venue_avg`
- `projected_adjusted`
- Any additional feature whose value is derived from those fields

Add or retain:

- `expected_final_score`
- `expected_final_vs_venue_avg = expected_final_score - venue_avg_score`
- Expected-final team-strength adjustment, if justified and implemented identically in training and live inference
- Existing DLS/resource, par-score, score-vs-par, phase, team, venue, and momentum features

## Execution sequence

1. Audit the processor, trainer, realtime mapper, predictor, dashboard payload, feature lists, and tests for every projected-score dependency.
2. Define one canonical feature builder used by historical training and live inference.
3. Add training/inference parity tests for expected-final and venue-relative features.
4. Train isolated candidate artifacts:
   - `models/t20_all_v3_expected_final_candidate`
   - `models/odi_all_v3_expected_final_candidate`
5. Keep current production baselines:
   - `models/t20_all_v2`
   - `models/odi_all_v2`
6. Evaluate both candidates chronologically using train-before-2025 and test-2025+ data.
7. Report overall, male, and female Brier score, log loss, calibration/ECE, reliability bins, and sample counts.
8. Run parity checks using identical match states through the baseline and candidate inference paths.
9. Run dashboard smoke tests to confirm expected final is displayed correctly and no projected-only value reaches prediction inputs.

## Promotion gate

Promote a candidate only when all conditions hold:

- Overall Brier score improves versus v2.
- Male Brier score does not regress.
- Female Brier score does not regress.
- Calibration/ECE does not materially regress.
- No training/live feature mismatch is detected.
- The candidate passes the relevant unit, integration, and model-loading tests.

If any condition fails, retain v2, record the result, and keep the candidate artifacts for research only.

## Deliverables

- Candidate model artifacts and metadata
- OOS comparison CSV/JSON
- Feature dependency audit
- Tests covering feature values and model input columns
- Promotion decision
- Updated repo documentation and Obsidian decision record
