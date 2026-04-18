# Data Model: IPL Model Improvement — Close Market Gap

**Phase 1 output** | Entities, fields, relationships, validation rules

---

## Entity: IPL FormatConfig Override

**Location**: `src/bbl_pipeline/features/format_config.py` → `FormatConfig.ipl()` factory  
**Type**: Immutable dataclass (frozen=True)  
**Relationship**: Inherits all fields from `FormatConfig.t20()`, overrides IPL-specific values

### Fields (overridden from T20 base)

| Field | Type | Current Value | New Value | Source |
|-------|------|---------------|-----------|--------|
| `par_score` | float | 173.45 | 173.45 (unchanged) | Historical IPL data |
| `league_avg_score` | float | 167.28 | 167.28 (unchanged) | Historical IPL data |
| `bat_first_win_rate` | float | 0.4581 | 0.4581 (unchanged) | Historical IPL data |
| `expected_run_rates` | Dict[str, float] | {pp:7.53, mid:7.51, death:9.02, final:10.68} | unchanged | Historical IPL data |
| `first_innings_score_midpoint` | float | 165.0 (inherited, NOT overridden) | **173.0** | FR-007, empirical IPL par |
| `first_innings_score_beta` | float | 0.04 (inherited) | **TBD (re-tune)** | Re-derive from IPL data |
| `chase_wicket_penalty_2d` | Dict[str, Dict[int, float]] | T20 generic | **IPL-specific** | FR-001, derived from training data |
| `first_innings_wicket_penalty_3d` | Dict[str, Dict[str, Dict[int, float]]] | T20 generic | **IPL-specific** | FR-001, derived from training data |
| `endgame_balls` | int | 12 (inherited) | 12 (unchanged) | last 2 overs |

### Validation Rules

- `first_innings_score_midpoint` MUST be within ±3 of 173.45 (FR-007)
- Every penalty value in `chase_wicket_penalty_2d` for wickets 4–8 MUST be strictly less than the T20 base value (FR-002)
- `__post_init__()` validates all structural invariants (existing)

---

## Entity: Final-Over Lookup Table

**Location**: `src/bbl_pipeline/features/win_prob_lookup_tables.py` (new content)  
**Type**: Dict[int, Dict[int, float]] — `runs_needed → {wickets_in_hand → win_probability}`  
**Relationship**: Used by `ResourceFeatureCalculator.calculate_resource_win_probability()` when `balls_remaining <= 6`

### Schema

| Dimension | Range | Description |
|-----------|-------|-------------|
| `runs_needed` | 0–25 | Runs required to win (key dimension) |
| `wickets_in_hand` | 0–10 | Wickets remaining (0 = all out, 10 = none lost) |
| `win_probability` | 0.0–1.0 | Empirical win rate from IPL final-over data |

### Invariants

- `win_prob(runs_needed=0, any wickets) = 1.0` (already won)
- `win_prob(any runs, wickets_in_hand=0) = 0.0` (all out)
- Monotonic decrease as `runs_needed` increases (fixed wickets)
- Monotonic increase as `wickets_in_hand` increases (fixed runs)
- `win_prob(runs > 20, wickets <= 2) = 0.0` (boundary default)

### State Transitions

```
Before over 20 (balls_remaining > 6):
  → Use standard RRR-based sigmoid + dynamic wicket penalty (existing)

Over 20 starts (balls_remaining ≤ 6):
  → Switch to final-over lookup table
  → If (runs_needed, wickets_in_hand) not in table: interpolate from nearest cells
  → If runs_needed > 25: return 0.01 (near-impossible)
```

---

## Entity: Team Rating (Recency-Weighted)

**Location**: `data/ipl_feature_store_v1/team_ratings.parquet`  
**Type**: Parquet file with per-team rows  
**Relationship**: Loaded by `InMemoryFeatureStore._load()` via `store.py:354–368`

### Schema

| Column | Type | Description |
|--------|------|-------------|
| `team` | str | Canonical team name (deduplicated) |
| `win_rate` | float | Recency-weighted overall win rate |
| `matches` | int | Total matches (unweighted count) |
| `effective_matches` | float | Sum of weights (effective sample size) |
| `bat_first_wr` | float | Recency-weighted batting-first win rate |
| `bowl_first_wr` | float | Recency-weighted bowling-first win rate |
| `half_life_seasons` | float | Decay parameter used (for reproducibility) |
| `last_updated` | str | ISO date of last match included |

### Deduplication Mapping

| Canonical Name | Merged From | Total Matches |
|---------------|-------------|---------------|
| Royal Challengers Bangalore | Royal Challengers Bangalore, Royal Challengers Bengaluru | 264 |
| Delhi Capitals | Delhi Capitals, Delhi Daredevils | 258 |
| Punjab Kings | Punjab Kings, Kings XI Punjab | 258 |
| Rising Pune Supergiants | Rising Pune Supergiant, Rising Pune Supergiants | 30 |

### Validation Rules

- No duplicate team names (UNIQUE constraint on `team`)
- `0.0 < win_rate < 1.0` for all teams
- `matches >= 10` for any team included (below threshold → excluded or marked provisional)
- `effective_matches > 0`

---

## Entity: Phase-Wise Calibrator Set

**Location**: `models/<league>/league_calibrator.pkl` (serialized via joblib)  
**Type**: `LeagueCalibrator` instance with `calibrators: Dict[str, PlattScaler]`  
**Relationship**: Applied in `Predictor.predict()` calibration chain

### Calibrator Keys

| Key | Phase | Innings | Minimum Samples |
|-----|-------|---------|-----------------|
| `inn1_powerplay` | Overs 1–6 | 1st | 500 |
| `inn1_middle` | Overs 7–14 | 1st | 500 |
| `inn1_death` | Overs 15–20 | 1st | 500 |
| `inn2_powerplay` | Overs 1–6 | 2nd | 500 |
| `inn2_middle` | Overs 7–14 | 2nd | 500 |
| `inn2_death` | Overs 15–20 | 2nd | 500 |
| `innings_1` | All overs | 1st | 500 (fallback) |
| `innings_2` | All overs | 2nd | 500 (fallback) |

### Fallback Chain

```
Phase-specific calibrator (inn1_powerplay)
  → if not fitted: innings-level calibrator (innings_1)
    → if not fitted: identity (raw probability)
```

### Calibrator Parameters (PlattScaler)

| Parameter | Type | Description |
|-----------|------|-------------|
| `model.coef_[0]` | float | Slope `a` in `sigmoid(a × logit(p) + b)` |
| `model.intercept_` | float | Bias `b` — corrects systematic over/under-confidence |

---

## Entity: Market Ensemble

**Location**: `src/bbl_pipeline/inference/` (new module or extension of `crex_live_predictor.py`)  
**Type**: Blending logic within inference pipeline  
**Relationship**: Receives model prediction + market odds, produces ensemble prediction

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `model_prob` | float | Calibrated model win probability (0.0–1.0) |
| `market_prob` | float \| None | Market implied probability from exchange odds |
| `market_age_seconds` | float \| None | Age of market data point |
| `alpha` | float | Blending weight (0.0 = pure market, 1.0 = pure model) |
| `ensemble_prob` | float | Final blended probability |
| `source` | str | "ensemble" or "model_only" (traceability per FR-013) |

### Blending Formula

```
if market_prob is not None and market_age_seconds <= 60:
    ensemble_prob = alpha × model_prob + (1 - alpha) × market_prob
    source = "ensemble"
else:
    ensemble_prob = model_prob
    source = "model_only"
```

### Validation Rules

- `0.0 ≤ alpha ≤ 1.0`
- `ensemble_prob` MUST be in `[0.001, 0.999]` (clamp after blending)
- Both `model_prob` and `ensemble_prob` MUST be logged (FR-013)
- Fallback MUST NOT raise exceptions (FR-012)

---

## Entity Relationship Diagram

```
FormatConfig.ipl()
  ├── chase_wicket_penalty_2d ──→ ResourceFeatureCalculator.get_dynamic_wicket_penalty()
  ├── first_innings_wicket_penalty_3d ──→ ResourceFeatureCalculator.get_first_innings_dynamic_penalty()
  ├── first_innings_score_midpoint ──→ ResourceFeatureCalculator (SQI calculation)
  └── endgame_balls ──→ triggers FinalOverLookup (new)
                            │
FinalOverLookup             │
  └── runs_needed × wickets_in_hand ──→ win_probability (replaces sigmoid)
                            │
TeamRatings (recency)       │
  └── team_ratings.parquet ──→ InMemoryFeatureStore._team_stats
                            │
PhaseWiseCalibratorSet      │
  └── inn{N}_{phase} ──→ LeagueCalibrator.predict() ──→ calibrated_prob
                            │
MarketEnsemble              │
  └── alpha × model_prob + (1-alpha) × market_prob ──→ ensemble_prob
```
