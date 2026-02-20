# Research: Monte Carlo Simulation Engine

**Date**: 2026-01-19  
**Feature**: 004-monte-carlo-engine

## 1. Data Sources

| Source | Path | Matches | Balls |
|--------|------|---------|-------|
| **Global T20 Male** | `data/t20_male_raw/**/*.parquet` | 8,135 | 1,893,892 |
| **BBL** | `data/bbl_raw/matches/**/*.parquet` | 604 | 282,870 |
| ILT20 | `data/ilt_raw/matches/**/*.parquet` | ~99 | ~23,000 |
| SA20 | `data/sat_raw/matches/**/*.parquet` | ~121 | ~28,000 |

**Schema**: Each ball has `runs_off_bat` (0-6), `extras` (wides, no-balls), `total_runs`, `dismissal_kind`.

---

## 2. Run Distribution by Phase (Global T20 Male - 1.89M balls)

| Phase | P(0) | P(1) | P(2) | P(3) | P(4) | P(5) | P(6) | E[Runs] |
|-------|------|------|------|------|------|------|------|---------|
| **Powerplay (1-6)** | 44.96% | 31.06% | 5.18% | 0.64% | 14.26% | 0.26% | 3.63% | 1.236 |
| **Middle (7-15)** | 32.44% | 47.20% | 7.36% | 0.41% | 8.16% | 0.13% | 4.27% | 1.222 |
| **Death (16-20)** | 28.68% | 43.15% | 10.03% | 0.53% | 10.52% | 0.18% | 6.84% | 1.494 |

### Key Insights
- **Death overs** have highest E[Runs] (1.494) and highest boundary rate (10.52% + 6.84% = 17.36%)
- **Middle overs** are most conservative with highest singles rate (47.20%)
- **Powerplay** has highest dots (44.96%) but also high 4s (14.26%)

### Innings-Specific Variation
- Inn2 Death: +2% more dots (30.68% vs 27.29%) - chasing teams pace innings
- Inn2 Powerplay: +0.4% more 4s (14.48% vs 14.04%) - field restrictions exploited

---

## 3. Wicket Rate by Phase (Global T20 Male)

| Phase | Innings 1 | Innings 2 | Overall |
|-------|-----------|-----------|---------|
| **Powerplay** | 4.25% | 4.54% | **4.40%** |
| **Middle** | 4.56% | 4.86% | **4.71%** |
| **Death** | 8.68% | 8.49% | **8.60%** |

### Key Insight
Death overs have **~2x the wicket rate** of other phases. This is critical for Monte Carlo - simulating 6 balls in death phase should expect ~0.5 wickets on average.

---

## 4. Wicket Rate by Wickets Already Down

| Phase | 0 wkts | 2 wkts | 4 wkts | 6 wkts | 8 wkts |
|-------|--------|--------|--------|--------|--------|
| **Powerplay** | 4.47% | 4.13% | 3.92% | 7.03% | N/A |
| **Middle** | 4.93% | 4.54% | 4.62% | 5.71% | 7.01% |
| **Death** | 6.83% | 6.96% | 7.57% | 9.20% | 10.73% |

### Key Insight
Wicket probability increases as more wickets fall (lower-order batting effect). Apply a multiplier to base wicket rate:

```python
WICKET_MULTIPLIER = {
    0: 1.00, 1: 1.00, 2: 0.98, 3: 0.96, 4: 0.99,
    5: 1.05, 6: 1.20, 7: 1.30, 8: 1.40, 9: 1.50
}
```

---

## 5. Pressure Effects (Second Innings)

Limited reliable data for RRR-based analysis. Key observations:
- Wicket rate under extreme pressure (~5.7%) only slightly higher than normal (~4.5%)
- **Recommendation**: Model pressure via `pressure_index` from `ResourceFeatureCalculator` rather than raw RRR

---

## 6. Recommended Default Phase Tables

```python
# Run distributions (probabilities sum to 1.0)
RUN_DIST = {
    'powerplay': {0: 0.4496, 1: 0.3106, 2: 0.0518, 3: 0.0064, 4: 0.1426, 5: 0.0026, 6: 0.0363},
    'middle':    {0: 0.3244, 1: 0.4720, 2: 0.0736, 3: 0.0041, 4: 0.0816, 5: 0.0013, 6: 0.0427},
    'death':     {0: 0.2868, 1: 0.4315, 2: 0.1003, 3: 0.0053, 4: 0.1052, 5: 0.0018, 6: 0.0684},
}

# Wicket probabilities per ball (base rates)
WICKET_PROB = {
    'powerplay': 0.0440,
    'middle':    0.0471,
    'death':     0.0860,
}
```

---

## 7. BBL vs Global T20 Comparison

BBL is very close to global averages:
- Boundary rates: -1.4% lower in powerplay, nearly identical elsewhere
- Wicket rates: Within ±0.2% across all phases
- Expected runs/ball: BBL slightly higher in middle/death (+0.04)

**Decision**: Use global T20 tables as defaults. League-specific adjustments via temperature scaling.

---

## 8. Performance Optimization Patterns

### NumPy Vectorization Strategy

To achieve 2000 sims × 6 balls < 500ms:

1. **Pre-compute cumulative distributions** for `np.searchsorted()` sampling
2. **Vectorize across simulations**: Run all 2000 simulations in parallel, not sequentially
3. **Batch state updates**: Update score/wickets/balls as arrays, not in loops
4. **Terminal evaluation once**: Call `ResourceFeatureCalculator` once at the end with the 2000 terminal states

```python
# Pseudo-vectorized approach
states = np.tile(initial_state, (n_sims, 1))  # (2000, state_dim)
for ball in range(horizon_balls):
    outcomes = sample_outcomes_vectorized(states)  # (2000,) runs, (2000,) wickets
    states = update_states_vectorized(states, outcomes)
probs = evaluate_terminal_states(states)  # (2000,) win probs
return SimulationResult(mean=probs.mean(), std=probs.std(), p5=np.percentile(probs, 5), ...)
```

### Caching Strategy
- Cache `ResourceFeatureCalculator` DLS tables in NumPy arrays
- Pre-compute phase boundaries (over → phase mapping)
- Memoize team/venue stats if used

---

## 9. ResourceFeatureCalculator Interface

### Required Inputs for Terminal Evaluation

From [calculator.py](../../src/bbl_pipeline/features/calculator.py):

```python
def calculate_all_features(
    innings: int,           # 1 or 2
    score: int,             # Current score
    wickets_lost: int,      # 0-10
    balls_remaining: int,   # 1-120
    target: Optional[int],  # Inn2 only
    batting_team: str,      # Team name
    bowling_team: str,      # Team name
    venue: str,             # Venue name (optional)
    league: str = 'bbl'     # League for calibration
) -> Dict[str, float]
```

### Key Output Features

| Feature | Description | Use in Monte Carlo |
|---------|-------------|-------------------|
| `resource_win_prob` | DLS-based win probability | **Primary evaluation metric** |
| `pressure_index` | 0-1 pressure scale | Wicket rate adjustment |
| `score_vs_par` | Score vs expected | Debugging/validation |
| `overs_completed` | For phase detection | Already known from state |

### Integration Point

The Monte Carlo engine will call:
```python
features = ResourceFeatureCalculator().calculate_all_features(
    innings=state.innings,
    score=state.score,
    wickets_lost=state.wickets_lost,
    balls_remaining=state.balls_remaining,
    target=state.target_runs,
    batting_team=state.batting_team,
    bowling_team=state.bowling_team,
    venue=state.venue,
    league=state.league
)
resource_win_prob = features['resource_win_prob']
```

Then apply temperature calibration:
```python
calibrated_prob = apply_temperature(resource_win_prob, T=temperature_by_innings[state.innings])
```

---

## 10. Existing Analysis Scripts

| Script | Purpose |
|--------|---------|
| `scripts/ball_by_ball_analysis.py` | Match-specific ball-by-ball win probability analysis |
| `scripts/analysis/analyze_bbl_calibration.py` | Phase-based calibration analysis |
| `src/bbl_pipeline/training/oof_analyzer.py` | OOF metrics computation |

---

## Decisions Made

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Use global T20 tables (not league-specific) | BBL within ±1.5% of global; temperature handles league differences | League-specific tables (rejected: too many tables, insufficient data for some leagues) |
| Model pressure via `pressure_index` not RRR | ResourceFeatureCalculator already computes this; RRR data sparse | Raw RRR (rejected: sparse data in "easy chase" buckets) |
| Vectorize across simulations | Required for 500ms target | Sequential loops (rejected: too slow) |
| Evaluate only at terminal state | Reduces evaluator calls from 6×2000 to 2000 | Per-ball evaluation (rejected: too slow) |
