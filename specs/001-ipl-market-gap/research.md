# Research: IPL Model Improvement — Close Market Gap

**Phase 0 output** | Generated alongside plan.md

---

## R-001: IPL Wicket Penalty Derivation Strategy

**Question**: How should IPL-specific wicket penalties be derived from the 273K-row training dataset? What grouping dimensions and minimum sample sizes are needed?

**Decision**: Derive penalties by grouping `training.parquet` on `wickets_lost × phase × chase_ease` for 2nd innings (chase) and `wickets_lost × phase × ease_bucket` for 1st innings. Use empirical win rates as the penalty multiplier. Minimum 30 observations per cell; cells below threshold smoothed from adjacent cells.

**Rationale**:
- The current penalty tables are derived from BBL data (67,560 2nd-innings samples per code comment at `calculator.py:195`). IPL has 273K total rows — significantly more data.
- The existing `chase_wicket_penalty_2d` structure (5 ease levels × 11 wicket counts) maps directly to the derivation dimensions.
- The Brier gap report shows the worst penalty errors at 4–8 wickets (gap +0.0802 for 4–5 wickets, +0.0577 for 6+ wickets). The current "easy" and "comfortable" levels give 1.00 (zero penalty) for 5–7 wickets — clearly wrong for IPL.
- Minimum 30 samples balances statistical reliability with granularity. IPL's 273K rows should provide 50–200+ samples per cell for common buckets.

**Alternatives Considered**:
1. **Bayesian smoothing with BBL prior**: Rejected — adds complexity and the BBL priors are the source of the current error (BBL batting is weaker than IPL).
2. **ML-fitted penalties (e.g., isotonic regression per wicket)**: Rejected — overfits to noise in thin cells and loses interpretability.
3. **Single flat penalty table (no ease dimension)**: Rejected — the spec explicitly requires chase-ease-aware penalties (FR-001), and the existing architecture already supports 2D/3D tables.

---

## R-002: Final-Over Empirical Lookup Table Design

**Question**: How should the final-over lookup table be structured, and how should sparse cells be handled?

**Decision**: Build a 2D lookup table mapping `runs_needed (0–25) × wickets_in_hand (1–10)` → win probability. Derive from all IPL second-innings final-over ball-by-ball data in the Cricsheet JSON files. Sparse cells filled by monotonic interpolation (probability decreases as runs_needed increases, increases as wickets_in_hand increases). Boundary defaults: 0 runs needed → 1.0; >20 runs needed with ≤2 wickets → 0.0.

**Rationale**:
- The current endgame sigmoid (`1/(1+e^(4*(rpb-1.5)))` at `calculator.py:887`) is a smooth approximation that ignores wickets_in_hand entirely beyond a penalty multiplier. This loses critical information — 6 runs needed with 8 wickets is very different from 6 runs needed with 1 wicket.
- The over-20 Brier gap is +0.170 (worst single-over gap), confirming the sigmoid is systematically wrong.
- Extending to 25 runs (beyond the spec's 20) handles edge cases like super overs and extraordinary situations.
- Monotonic interpolation constraints ensure the table is physically sensible even for rare cells.

**Alternatives Considered**:
1. **Improved sigmoid with wicket parameter**: `1/(1+e^(a*(rpb-b(w))))` where b varies by wickets. Rejected — still can't capture the discrete, non-smooth nature of 6-ball situations.
2. **Monte Carlo simulation from ball-by-ball model**: Rejected — requires a separate ball-outcome model (doesn't exist) and is computationally expensive for inference.
3. **Larger endgame window (last 3–4 overs)**: Rejected — the sigmoid works reasonably for overs 17–19; the problem is specifically the last over where it breaks down.

---

## R-003: Recency Weighting for Team Ratings

**Question**: What exponential decay half-life should be used for IPL team ratings? How should team name duplicates be resolved?

**Decision**: Use exponential decay with a half-life of 2.5 IPL seasons (~35 matches per season). Weight formula: `w = exp(-λ × age_in_seasons)` where `λ = ln(2) / 2.5 ≈ 0.277`. Team name deduplication via canonical mapping in `entity_registry.yaml`.

**Rationale**:
- The spec assumption (2–3 seasons) is consistent with cricket analysis literature where team composition turns over significantly within 2–3 auction cycles.
- 2.5 seasons means matches from 5 seasons ago carry ~25% weight — still contributing but not dominating.
- The current `team_ratings.parquet` shows clear duplicates:
  - "Royal Challengers Bangalore" (234 matches, 48.7%) vs "Royal Challengers Bengaluru" (30 matches, 60.0%)
  - "Delhi Daredevils" (158 matches) vs "Delhi Capitals" (100 matches) — same franchise
  - "Kings XI Punjab" (186 matches) vs "Punjab Kings" (72 matches) — same franchise
  - "Rising Pune Supergiant" (16) vs "Rising Pune Supergiants" (14) — same team
- All duplicates must be merged into canonical entries per FR-006 and Constitution Principle IV.

**Alternatives Considered**:
1. **Linear decay**: `w = max(0, 1 - age/max_age)`. Rejected — creates a hard cutoff; exponential is smoother.
2. **Rolling window (last N seasons only)**: Rejected — discards data entirely; exponential decay is strictly better.
3. **ELO-style iterative ratings**: Rejected — adds significant complexity and requires tuning K-factor. The exponential-weighted win rate is simpler and directly interpretable.

**Canonical Team Mapping** (to add to `entity_registry.yaml`):

| Canonical ID | Aliases |
|-------------|---------|
| RCB | Royal Challengers Bangalore, Royal Challengers Bengaluru |
| DC | Delhi Capitals, Delhi Daredevils |
| PBKS | Punjab Kings, Kings XI Punjab |
| RPS | Rising Pune Supergiant, Rising Pune Supergiants |

---

## R-004: First-Innings Scoring Midpoint Correction

**Question**: What should the IPL-specific first-innings scoring midpoint be, and should it be venue-adjusted?

**Decision**: Update `first_innings_score_midpoint` in `FormatConfig.ipl()` from the inherited T20 default of 165.0 to 173.0 (within ±3 of the empirical 173.45 per FR-007). Implement venue-adjusted midpoint by adding `venue_avg_score` from `venue_stats.parquet` / IPL venue defaults in `store.py` as a modifier: `effective_midpoint = league_midpoint + 0.7 × (venue_avg - league_avg)`.

**Rationale**:
- The current `FormatConfig.ipl()` (line 330–341 of `format_config.py`) overrides `par_score=173.45` but does NOT override `first_innings_score_midpoint` — it still inherits 165.0 from `FormatConfig.t20()`. This is the root cause of the death-over Brier gap (+0.072 to +0.093).
- IPL venue averages range from 156 (Chepauk) to 184 (Chinnaswamy). A single midpoint can't capture this 28-run spread.
- The 0.7 regression factor prevents over-fitting to venue noise while capturing the bulk of venue effect.
- The `store.py` already seeds 17 IPL venues with `venue_avg_score` (lines 376–398) — this data is already available.

**Alternatives Considered**:
1. **Simple midpoint update only (no venue adjustment)**: Viable for Phase 1 but leaving ~30% of the venue effect on the table. FR-008 explicitly requires venue-adjusted midpoints.
2. **Full venue-specific midpoints (one per ground)**: Rejected — overfits to venue sample sizes; regression-to-mean via the 0.7 factor is more robust.
3. **Dynamic midpoint from recent match scores**: Rejected — adds temporal complexity and risks recency bias from a few recent high/low-scoring matches.

---

## R-005: Phase-Wise Platt Scaling Architecture

**Question**: How should 6 phase-wise calibrators replace the current 2 innings-level temperature scalers?

**Decision**: Extend `LeagueCalibrator` to use 6 Platt scalers (3 phases × 2 innings), keyed as `inn1_powerplay`, `inn1_middle`, `inn1_death`, `inn2_powerplay`, `inn2_middle`, `inn2_death`. Minimum sample threshold: 500 per segment (already the default in `LeagueCalibrator.fit()`). Fallback: if a phase segment has <500 samples, use the innings-level calibrator (FR-010).

**Rationale**:
- The current architecture already supports `phase_specific=True` in `LeagueCalibrator.__init__()` (line 101) — it's just disabled by default. The code at lines 161–171 already fits phase-specific calibrators when enabled.
- The current approach (2 temperature scalers, one per innings) produces near-zero Brier improvement (0.1831→0.1830, per spec).
- Platt scaling (logistic regression on logits) is preferred over temperature scaling because it adds a bias term `b` that can correct systematic over/under-confidence per phase — temperature only scales spread.
- With 273K training rows: assuming ~50% per innings and 3 phases, the smallest segment (powerplay, ~30% of overs) gets ~40K samples — well above the 500 threshold.
- The `predict()` method (lines 185–216) already routes by innings; it needs extension to route by phase within innings.

**Alternatives Considered**:
1. **Isotonic regression per phase**: Rejected — too "steppy" (per the module docstring, line 6) and overfits with discrete jumps.
2. **Beta calibration (3 parameters)**: Rejected — marginal improvement over Platt for this use case, adds fitting complexity.
3. **12 calibrators (4 phases × 3 innings)**: The `final` phase (overs 18–20) could be separated. Rejected — the death+final split creates thin segments, and death already covers overs 14–20 effectively for calibration purposes.

---

## R-006: Market-as-Feature Ensemble Design

**Question**: How should the model-market blending be implemented, and what architecture supports graceful fallback?

**Decision**: Implement a `MarketEnsemble` class in inference that blends: `final = alpha × model_prob + (1 - alpha) × market_prob`. Alpha determined by sweeping 0.0–1.0 on validation set. Fallback to pure model when `market_prob is None` or market data age > 60 seconds.

**Rationale**:
- The market already outperforms the model on 63.1% of observations. A simple linear blend is the standard approach in forecast combination literature (Bates-Granger, 1969).
- The existing infrastructure already extracts market odds: `crex_live_predictor.py` computes `market_fav_prob` from back/lay odds, and `match_state_logger.py` logs `market_batting_team_prob`.
- Staleness threshold of 60 seconds accounts for typical exchange data latency during live matches.
- FR-012 requires graceful fallback; FR-013 requires dual output (model-only + ensemble). Both are naturally satisfied by the blending architecture.
- The validation set (510 observations from 16 matches) has both model and market probabilities already paired in `data/ipl_model_vs_market.parquet`.

**Alternatives Considered**:
1. **Market as a feature in XGBoost retraining**: Rejected — violates the constraint that the core model architecture is frozen. Also creates a dependency on market data at training time.
2. **Dynamic alpha based on match phase**: Interesting but adds complexity. Start with fixed alpha; phase-varying alpha can be a follow-up.
3. **Bayesian model averaging (BMA)**: Rejected — requires posterior probability estimates for each model, adding unnecessary mathematical complexity for marginal gain over linear blending.

---

## R-007: Validation Workflow and Non-Regression Verification

**Question**: How should each change be validated to ensure Pareto improvement (SC-008)?

**Decision**: After each change, run `scripts/analyze_ipl_model_vs_market.py` and compare the segmented Brier report against the baseline (`data/ipl_model_vs_market_report.md`). A change passes if: (a) overall Brier improves, (b) no individual segment (phase, over, team) regresses by more than 0.005 Brier points.

**Rationale**:
- The existing validation script already produces the required segmentation: by innings, phase, match, team, and wickets.
- A 0.005 tolerance accounts for statistical noise in small segments (some team buckets have only 20–40 observations).
- The spec's SC-008 ("no individual segment regresses") is interpreted with this statistical tolerance to avoid blocking improvements due to measurement noise.

**Alternatives Considered**:
1. **Bootstrap confidence intervals per segment**: More rigorous but computationally expensive and complex to automate. Reserved for final overall validation.
2. **Strict zero regression (no tolerance)**: Rejected — with 510 observations, random variation in small segments will always produce some noise. A 0.005 tolerance is ~2.5% of the baseline Brier.
