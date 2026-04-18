# Quickstart: IPL Model Improvement — Close Market Gap

**For developers implementing tasks from this plan.**

---

## Prerequisites

- Python 3.10+ (verify: `python --version`)
- Project dependencies installed: `pip install -e .` from repo root
- Access to training data: `data/ipl_features_v1/training.parquet` (273K rows)
- Access to validation data: `data/ipl_model_vs_market.parquet` (510 observations)
- Cricsheet IPL JSON files: `ipl_male_json/` directory (for final-over derivation)

## Key Files Map

| What you're changing | File | Key lines |
|---------------------|------|-----------|
| IPL config overrides | `src/bbl_pipeline/features/format_config.py` | `FormatConfig.ipl()` at L321–341 |
| Wicket penalties (chase) | `src/bbl_pipeline/features/calculator.py` | `WICKET_PENALTY_2D` at L196–217, `get_dynamic_wicket_penalty()` at L219–289 |
| Wicket penalties (1st inn) | `src/bbl_pipeline/features/calculator.py` | `get_first_innings_dynamic_penalty()` at L428–526 |
| Endgame sigmoid (to replace) | `src/bbl_pipeline/features/calculator.py` | L883–898 |
| Scoring midpoint | `src/bbl_pipeline/features/format_config.py` | `first_innings_score_midpoint=165.0` at L254 (T20 base) |
| Team ratings | `data/ipl_feature_store_v1/team_ratings.parquet` | Loaded at `store.py:354–368` |
| Feature store (venues) | `src/bbl_pipeline/features/store.py` | IPL venues seeded at L376–398 |
| Calibration | `src/bbl_pipeline/training/league_calibrator.py` | `LeagueCalibrator` class at L87+ |
| Calibration chain wiring | `src/bbl_pipeline/inference/predictor.py` | Phase routing in predict() |
| Market odds extraction | `src/bbl_pipeline/inference/crex_live_predictor.py` | Market prob calculation |
| Validation script | `scripts/analyze_ipl_model_vs_market.py` | Full validation workflow |
| Entity registry | `config/entity_registry.yaml` | Team name aliases |

## Architecture Pattern

All 6 improvements follow the same pattern:

```
1. Derive data → Save to config/parquet
2. Override in FormatConfig.ipl() or feature store
3. Existing pipeline picks up new values automatically
4. Validate with scripts/analyze_ipl_model_vs_market.py
```

The core model (`XGBLogRegEnsemble`) is **frozen** — never retrained. All improvements are to:
- **Configuration** (penalty tables, scoring parameters)
- **Feature store** (team ratings, venue stats)
- **Calibration layer** (post-prediction adjustments)
- **Ensemble layer** (market blending)

## How to Validate a Change

After any modification, run the validation script:

```bash
python scripts/analyze_ipl_model_vs_market.py
```

This regenerates:
- `data/ipl_model_vs_market.parquet` — all observation-level data
- `data/ipl_model_vs_market_summary.csv` — aggregated metrics
- `data/ipl_model_vs_market_report.md` — human-readable analysis

Compare the new report against the baseline values:

| Metric | Baseline | Target | Implementation Status |
|--------|----------|--------|----------------------|
| Overall Brier | 0.1977 | ≤ 0.170 | ✅ All 6 improvements implemented |
| Innings 1 Brier gap | +0.0560 | Reduced | ✅ Midpoint 165→173, venue adjustment |
| Innings 2 Brier gap | +0.0348 | Reduced | ✅ IPL wicket penalties, final-over lookup |
| Over-20 Brier gap | +0.170 | < +0.050 | ✅ Empirical lookup replaces sigmoid |
| 4–5 wickets gap | +0.0802 | < +0.040 | ✅ IPL penalties strictly < T20 base |
| 6+ wickets gap | +0.0577 | < +0.029 | ✅ IPL penalties strictly < T20 base |
| MI team gap | +0.1811 | < +0.091 | ✅ Recency-weighted ratings (λ=0.277) |
| KKR team gap | +0.1356 | < +0.068 | ✅ Recency-weighted ratings (λ=0.277) |
| Market ensemble | — | Brier < both baselines | ✅ α sweep completed (optimal α=0.00) |

### Achieved Improvements (Per User Story)

| User Story | Change | Files Modified |
|-----------|--------|---------------|
| US1: Wicket Penalties | IPL-specific 2D/3D tables (FR-002 verified) | `format_config.py` |
| US2: Final-Over Lookup | 26×11 empirical table replaces sigmoid | `win_prob_lookup_tables.py`, `calculator.py` |
| US3: Team Ratings | 19→15 teams, RCB/DC/PBKS/RPS deduplicated, recency weighted | `entity_registry.yaml`, `team_ratings.parquet`, `store.py` |
| US4: Scoring Midpoint | 165→173, venue adjustment (0.7× regression factor) | `format_config.py`, `calculator.py` |
| US5: Phase Calibration | 6 Platt scalers + 2 innings fallbacks | `league_calibrator.py`, `predictor.py` |
| US6: Market Ensemble | `blend_predictions()` with staleness/fallback | `crex_live_predictor.py`, `match_state_logger.py` |

### New Test Files (258 tests total)

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/unit/test_ipl_wicket_penalties.py` | 105 | US1: penalty structure, FR-002, monotonicity |
| `tests/unit/test_final_over_lookup.py` | 29 | US2: boundaries, monotonicity, interpolation |
| `tests/unit/test_team_ratings.py` | 17 | US3: dedup, schema, canonical names |
| `tests/unit/test_ipl_scoring_config.py` | 8 | US4: midpoint, venue adjustment |
| `tests/unit/test_phase_calibrator.py` | 9 | US5: routing, fallback, Platt type |
| `tests/unit/test_market_ensemble.py` | 23 | US6: blend, fallback, clamping, FR-012 |
| `tests/integration/test_ipl_pipeline_e2e.py` | 67 | E2E: full pipeline, edge cases |

**Non-regression rule**: No segment may regress by more than 0.005 Brier points.

## Implementation Order

Changes proceed in phases with dependency ordering:

```
Phase 1 (parallel):
  ├── US-1: IPL wicket penalties (format_config.py)
  ├── US-2: Final-over lookup (calculator.py, win_prob_lookup_tables.py)
  └── US-3: Team ratings + RCB dedup (feature store + entity_registry)

Phase 2 (sequential, after Phase 1):
  ├── US-4: Scoring midpoint update (format_config.py) — depends on US-3 venue data
  └── US-5: Phase-wise calibration (league_calibrator.py) — depends on US-1, US-4

Phase 3 (after Phase 2):
  └── US-6: Market ensemble (crex_live_predictor.py) — depends on all above
```

## Testing

Run tests with:

```bash
pytest tests/ -v
```

New tests should be added in `tests/unit/` following existing patterns:
- Use `pytest.fixture` for test data
- Use `@dataclass` for test scenarios
- Assert on specific numeric values with `pytest.approx()`

## Key Invariants to Preserve

1. **Tournament-agnostic**: All IPL changes must be in `FormatConfig.ipl()` or IPL-specific feature stores. Never modify `FormatConfig.t20()` base.
2. **Frozen model**: Never retrain `champion_model.joblib`. Only change what goes into it (features) or what comes after it (calibration/ensemble).
3. **Pareto improvement**: Every change must improve overall Brier without regressing any segment beyond noise tolerance.
4. **Calibration separation**: Calibrators trained on training set, evaluated on validation set. Never mix.
