# Full Spec Review Checklist: T20 Reduced-Over Match Support

**Purpose**: Validate requirements quality, completeness, clarity, and consistency across the full specification  
**Created**: 2026-02-21  
**Feature**: [spec.md](../spec.md)

## Requirement Completeness

- [ ] CHK001 — Are requirements defined for what happens when CREX auto-detection returns inconsistent data (e.g., `total_overs=15` but `revised_target` implies 12 overs)? [Gap]
- [ ] CHK002 — Are requirements specified for how `revised_target` interacts with first innings Monte Carlo simulation? FR-002 says "second innings" but does not address what happens if `revised_target` is provided during innings 1. [Completeness, Spec §FR-002]
- [ ] CHK003 — Are requirements defined for the output format of the dual probability (raw + calibrated)? FR-016 requires both but does not specify how they appear in the JSON output, logs, or Streamlit app. [Gap, Spec §FR-016]
- [ ] CHK004 — Is the MC calibrator artifact lifecycle specified — when to retrain, how to version, where to store alongside model artifacts? FR-017 defines training but not ongoing maintenance. [Gap, Spec §FR-017]
- [ ] CHK005 — Are requirements defined for how the betting decision engine (`evaluate_bet()`) uses the calibrated MC probability vs the raw probability? [Gap]
- [ ] CHK006 — Are requirements specified for Streamlit app behavior during reduced-over matches? The app currently displays phase-based visualizations that would need to reflect scaled phases. [Gap]

## Requirement Clarity

- [ ] CHK007 — Is "~30% of total overs" for powerplay scaling sufficiently precise? FR-004 uses `~30%` and `~25%` — are these exact formulas or approximations? The plan specifies `max(2, min(6, round(total_overs * 0.30)))` but the spec uses approximate language. [Ambiguity, Spec §FR-004]
- [ ] CHK008 — Is "within 5% of the DLS-theoretical par" in SC-003 defined with a specific DLS table version or reference implementation? Different DLS versions may yield different theoretical pars. [Clarity, Spec §SC-003]
- [ ] CHK009 — Is "less than 10 percentage points" in SC-004 a meaningful threshold? At par in a 10-over chase, DLS-implied probability is roughly 50% — so the model must be between 40-60%. Is this tight enough for betting? [Measurability, Spec §SC-004]
- [ ] CHK010 — Is "immediately switch" in FR-015 quantified — does it mean on the next scrape cycle, next ball, or within a specific time window? [Ambiguity, Spec §FR-015]
- [x] CHK011 — ~~Is "betting-grade calibration quality" quantified beyond log loss ≤ 0.55? The constitution requires ECE < 0.0021 for production betting — is the spec intentionally relaxing this for MC predictions?~~ **Resolved**: SC-009 added — ECE < 0.0021 required on 20-over backtest; deferred for reduced-over-specific ECE until ≥500 ball-states recorded. [Clarity, Spec §SC-009]

## Requirement Consistency

- [ ] CHK012 — FR-004 defines phase scaling as "~30% powerplay, ~25% death" while the plan/contracts define exact formulas (`round(total_overs * 0.30)`). Are these consistent, and which is authoritative? [Consistency, Spec §FR-004 vs contracts]
- [ ] CHK013 — FR-001 says `total_overs` is "integer, 5–20" but the default is 20. If `total_overs == 20`, FR-014 says to use the standard model. Is a `total_overs=20` passed via CLI treated identically to "not provided"? [Consistency, Spec §FR-001 vs §FR-014]
- [x] CHK014 — ~~SC-001 requires predictions to be "identical" for 20-over matches, but FR-016 introduces a new calibrated MC probability output. Does "identical" mean the primary prediction is unchanged, or that no new output fields appear?~~ **Resolved**: SC-001 clarified — "identical" means the primary win probability for betting is unchanged. New diagnostic MC fields may appear. [Consistency, Spec §SC-001]
- [ ] CHK015 — The spec says "Monte Carlo only" for reduced overs (FR-014), but the existing live predictor already runs MC alongside the trained model for 20-over matches. Does FR-014 mean MC replaces the model output, or that the model is not invoked at all? [Consistency, Spec §FR-014]

## Acceptance Criteria Quality

- [ ] CHK016 — Can User Story 1 acceptance scenario 1 be objectively verified? "Produces win probability between 0 and 1" is trivially true for any valid output — is a more meaningful range or sanity check needed? [Measurability, Spec §US-1 AS-1]
- [ ] CHK017 — Is User Story 2 acceptance scenario 2 ("roughly even") measurable? "Roughly even" should be quantified (e.g., win probability between 40-60% for the chasing team). [Measurability, Spec §US-2 AS-2]
- [ ] CHK018 — SC-007 measures log loss on "backtested against full-length T20 MC simulations." Is this testing calibration on the same distribution it was trained on, or is there a held-out test set? [Measurability, Spec §SC-007]

## Scenario Coverage

- [x] CHK019 — ~~Are requirements defined for super overs following a reduced-over match? A tied 15-over match goes to a super over — does the system revert to standard behavior?~~ **Resolved**: Edge case added — super overs treated as independent 1-over mini-match; FR-001 updated to accept total_overs=1 for super overs. [Coverage, Spec §Edge Cases]
- [ ] CHK020 — Are requirements defined for the second rain interruption scenario — overs reduced twice (e.g., 20→15→12) during the same innings? [Coverage, Edge Case]
- [ ] CHK021 — Are requirements specified for what happens when a match is abandoned (no result) after being reduced? Does the system gracefully stop predictions? [Coverage, Exception Flow]
- [ ] CHK022 — Are requirements defined for the transition from innings 1 to innings 2 when innings 1 was reduced and innings 2 may have different overs? How does the system reset/reconfigure between innings? [Coverage, Spec §US-3]

## Edge Case Coverage

- [ ] CHK023 — Is the behavior defined when `total_overs` is provided via CLI AND detected differently from CREX (e.g., CLI says 15, CREX says 12)? FR-001 says CLI overrides, but should the system warn about the mismatch? [Edge Case, Spec §FR-001]
- [ ] CHK024 — Is the behavior defined when the detected `revised_target` is lower than the current score (e.g., target 80 but team already at 85)? [Edge Case, Gap]
- [ ] CHK025 — Are requirements defined for a 5-over match where all 10 wickets fall in 3 overs (all-out before reduced total)? Does the system handle early termination identically to 20-over matches? [Edge Case, Spec §Edge Cases]
- [ ] CHK026 — Is behavior specified when CREX shows "DLS" text but the extracted target is missing or unparseable? [Edge Case, Spec §FR-002]

## Non-Functional Requirements

- [ ] CHK027 — Are memory/resource requirements specified for creating multiple `FormatConfig` instances during a match with multiple interruptions? [Non-Functional, Gap]
- [ ] CHK028 — SC-002 requires "under 1 second per prediction cycle" — is this the same target as 20-over MC, or should reduced-over MC be faster due to fewer balls simulated? [Clarity, Spec §SC-002]
- [ ] CHK029 — Are logging/observability requirements defined for the prediction mode switch (model→MC)? FR-015 says "log the transition" but doesn't specify log level, format, or alerting. [Completeness, Spec §FR-015]

## Dependencies & Assumptions

- [ ] CHK030 — Is the assumption "MC's biases are consistent regardless of match length" validated or testable? What evidence supports this claim? [Assumption]
- [ ] CHK031 — Is the assumption "DLS resource tables in FormatConfig are sufficient for reduced overs" validated? Do the tables cover the full 5-20 overs range with adequate interpolation? [Assumption]
- [ ] CHK032 — The spec assumes "operator provides total_overs and revised_target externally" but also says CREX auto-detects. Are these contradictory, or does the assumption only apply as a fallback? [Assumption vs Spec §FR-001]

## Notes

- **Focus**: Full specification review across all domains (simulation, calibration, integration, CREX)
- **Depth**: Standard (~32 items)
- **Audience**: Reviewer (pre-implementation review)
- **Traceability**: 28/32 items (87.5%) include spec section references or gap markers
