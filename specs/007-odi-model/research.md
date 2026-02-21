# Research: ODI Win Probability Model

**Feature**: 007-odi-model  
**Date**: 2026-02-20

## R-001: FormatConfig Design Pattern

**Decision**: Create a `FormatConfig` frozen dataclass that bundles all format-specific constants. Factory methods provide T20 and ODI presets.

**Rationale**: The calculator has 31 T20-hardcoded values spread across ~20 distinct logical groups (phase boundaries, penalty tables, DLS tables, sigmoid parameters). A dataclass groups them logically, supports validation, and can be serialized. Factory methods `FormatConfig.t20()` and `FormatConfig.odi(gender='male')` provide presets while allowing custom configs for experimentation.

**Alternatives considered**:
- (a) **Subclassing** (`ODIResourceFeatureCalculator`) — rejected because 95% code overlap would mean maintaining ~900 duplicated lines.
- (b) **YAML/JSON config files** — rejected because constants are tightly coupled to code logic (e.g., DLS table lookups, penalty indexing) and need compile-time validation. A Python dataclass with type hints provides better IDE support and catches errors earlier.
- (c) **Module-level dicts** — rejected because no validation, no grouping, easy to forget a constant.

## R-002: ODI DLS Resource Table Source

**Decision**: Derive the DLS resource table empirically from the ODI dataset using actual runs-scored-per-remaining-resources methodology.

**Rationale**: The official ICC DLS tables are copyrighted. The existing T20 DLS table was empirically derived from BBL data. The same methodology applied to 2010+ ODI data (estimated ~1,500+ matches after filtering) provides sufficient data density for the OversRemaining(0-50) × Wickets(0-10) grid. Key data points at 0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50 overs remaining cover the space adequately.

**Alternatives considered**:
- (a) Published academic DLS approximations — less accurate than empirical data from actual matches.
- (b) Scale from T20 table — fundamentally different scoring dynamics (T20 death > ODI death run rate multiplier).

## R-003: Gender-Aware Constants

**Decision**: `FormatConfig.odi(gender='male')` and `FormatConfig.odi(gender='female')` return different empirical constants. The processor passes the match's gender to the config factory at processing time.

**Rationale**: Male ODIs average ~250-280 par, female ODIs ~180-200. Using blended constants would produce inaccurate projected scores and win probabilities for both genders. Gender-specific constants with a single combined model (gender as a feature) gives the best of both worlds.

**Implementation detail**: During processing, each match's gender field determines which `FormatConfig` is used for resource calculations. The resulting features (win_prob, projected_score, etc.) are then gender-appropriate, and the model also sees `gender` as an explicit feature.

## R-004: Processor Refactoring Strategy

**Decision**: Add `total_overs`, `total_balls`, and `format_config` parameters to `process_bbl_data()`, all defaulting to T20 values.

**Rationale**: The processor has 11 hardcoded T20 values. These map to exactly 2 derived parameters (total_overs=50, total_balls=300) plus the format config for resource calculations. Default values ensure zero impact on existing T20 workflows.

**Specific replacements**:
| Current hardcode | Replacement |
|-----------------|-------------|
| `120 - balls_bowled` | `total_balls - balls_bowled` |
| `bins=[-1, 36, 90, 120]` | Computed from `format_config.phase_thresholds` |
| `balls_remaining / 120` | `balls_remaining / total_balls` |
| `(120 - balls_bowled) / 6` | `(total_balls - balls_bowled) / 6` |
| `160.0` fallback | `format_config.par_score` |
| `venue_avg / 20` | `venue_avg / total_overs` |
| `/ 1200` | `/ (total_balls * 10)` |
| `over < 6` | From `format_config.phase_thresholds` |
| `over < 15` | From `format_config.phase_thresholds` |
| `over >= 15` | From `format_config.phase_thresholds` |

## R-005: Ingestion Changes

**Decision**: Minimal ingestion changes — add `overs` field capture and `'ODI'` to super-over filter.

**Rationale**: Ingestion is already format-agnostic. It captures `match_type` and `gender`. The only missing piece is the `overs` field from `info.overs` (needed for filtering reduced-overs matches downstream). The super-over detection check at L241 uses a match_type whitelist that needs `'ODI'` added.

## R-006: T20 Regression Safety

**Decision**: Implement T20 regression test as a prerequisite gate before any refactoring. Snapshot 10 diverse T20 match states → current calculator outputs. After refactoring, verify byte-identical outputs.

**Rationale**: Constitution Principle I requires tournament-agnostic architecture without breaking existing functionality. The parameterization must be invisible to existing T20 workflows. Test states should cover: early powerplay, middle overs, death overs, 1st/2nd innings, various wicket counts, and edge cases (all out, last ball).

## R-007: ODI Phase Validation

**Decision**: Use 4 phases — Powerplay (1-10), Middle (11-34), Setup (35-40), Death (41-50). Validate against empirical run-rate data during analysis.

**Rationale**: Modern ODI powerplay rules mandate fielding restrictions in overs 1-10. Run rates typically:
- PP (1-10): ~5.0-5.5 (fielding restrictions, aggressive starts)
- Middle (11-34): ~4.5-5.0 (consolidation, building partnerships)
- Setup (35-40): ~6.0-7.0 (acceleration, setting up for death)
- Death (41-50): ~7.0-9.0 (slog overs, boundary-heavy)

The empirical analysis script will validate these boundaries and the expected run rates. If the data shows a different natural transition point (e.g., acceleration starting at over 36 not 35), the phase boundaries in `FormatConfig.odi()` will be adjusted accordingly.
