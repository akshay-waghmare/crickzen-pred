# Data Model: ODI Monte Carlo Standalone Predictor

**Feature**: `009-odi-mc-predictor`  
**Date**: 2026-02-28

## Entities

### 1. ODI Phase Distribution

Run probability vectors and wicket rates for ODI-specific match phases.

| Field | Type | Description |
|-------|------|-------------|
| `phase_name` | string | One of: `powerplay`, `middle`, `setup`, `death` |
| `run_distribution` | dict[int, float] | Probability of scoring 0/1/2/3/4/5/6 runs per ball. Values sum to 1.0. |
| `wicket_probability` | float | Base probability of a wicket falling per ball in this phase (0.0–1.0) |
| `expected_run_rate` | float | Expected runs per over in this phase (informational) |

**ODI Phase Boundaries** (50-over format):

| Phase | Overs | Description |
|-------|-------|-------------|
| `powerplay` | 1–10 | Fielding restrictions, opening onslaught |
| `middle` | 11–34 | Consolidation, building platform |
| `setup` | 35–40 | Acceleration phase, preparing for death |
| `death` | 41–50 | Final assault, highest scoring rate |

**Relationships**: Loaded by `NextBallSampler` at init. Used per-ball during simulation to sample outcomes.

**Validation rules**:
- Run distribution values must sum to 1.0 (±0.001 tolerance)
- All 7 run outcomes (0–6) must be present
- Wicket probability must be in range [0.01, 0.15]
- At least 3 phases must be defined

---

### 2. ODI Wicket Multiplier Table

Adjustments to base wicket probability based on how many wickets have already fallen.

| Field | Type | Description |
|-------|------|-------------|
| `wickets_down` | int | Number of wickets lost (0–9) |
| `multiplier` | float | Factor applied to base wicket probability (1.0 = no change) |

**Example** (ODI-specific, lower-order more vulnerable):

| Wickets Down | Multiplier | Reasoning |
|:---:|:---:|---|
| 0 | 1.00 | Established openers |
| 1 | 1.00 | Still top order |
| 2 | 0.95 | Experienced middle order |
| 3 | 0.95 | Experienced middle order |
| 4 | 1.00 | Middle/lower order transition |
| 5 | 1.05 | Lower order begins |
| 6 | 1.15 | Lower order |
| 7 | 1.25 | Tail begins |
| 8 | 1.35 | Tail-ender |
| 9 | 1.50 | Last pair |

**Validation**: All multipliers must be in range [0.5, 2.0].

---

### 3. MatchState (Extended)

Existing `MatchState` dataclass with relaxed validation for ODI support.

| Field | Type | Change | Description |
|-------|------|--------|-------------|
| `total_balls` | int | **Modified** | Valid range extended from `6-120` to `6-300`. Must be divisible by 6. |
| All other fields | — | Unchanged | innings, score, wickets_lost, balls_remaining, target_runs, league, batting_team, bowling_team, venue, win rates |

**State transitions**: Unchanged — `apply_outcome()` increments score, decrements balls_remaining, optionally increments wickets_lost.

---

### 4. Phase Distribution File

JSON artifact stored in model directory or data directory.

**File naming**: `phase_distributions_{league}.json` where league is `odi`, `odm`, `odi_female`, etc.

**Schema**:

```json
{
  "format": "odi",
  "gender": "male",
  "total_matches": 3085,
  "total_balls": 876432,
  "extraction_date": "2026-02-28",
  "run_dist": {
    "powerplay": {"0": 0.38, "1": 0.32, "2": 0.05, "3": 0.005, "4": 0.14, "5": 0.005, "6": 0.03},
    "middle":    {"0": 0.35, "1": 0.38, "2": 0.06, "3": 0.004, "4": 0.09, "5": 0.003, "6": 0.035},
    "setup":     {"0": 0.30, "1": 0.34, "2": 0.07, "3": 0.005, "4": 0.12, "5": 0.004, "6": 0.05},
    "death":     {"0": 0.26, "1": 0.30, "2": 0.09, "3": 0.005, "4": 0.15, "5": 0.005, "6": 0.08}
  },
  "wicket_prob": {
    "powerplay": 0.035,
    "middle": 0.038,
    "setup": 0.045,
    "death": 0.070
  },
  "wicket_multiplier": {
    "0": 1.00, "1": 1.00, "2": 0.95, "3": 0.95,
    "4": 1.00, "5": 1.05, "6": 1.15, "7": 1.25,
    "8": 1.35, "9": 1.50
  }
}
```

**Note**: Values above are placeholder estimates. Actual values will be extracted from empirical data in User Story 5.

---

### 5. MC Calibrator (ODI)

Platt-scaling calibrator mapping raw MC `resource_win_prob` to calibrated probabilities.

| Field | Type | Description |
|-------|------|-------------|
| `calibrator_type` | string | `"platt"` or `"isotonic"` |
| `innings` | int | 1 or 2 (innings-specific calibration) |
| `training_samples` | int | Number of samples used for fitting |
| `training_brier` | float | Brier score on training data |
| `fitted_date` | string | ISO format date when calibrator was fit |

**Persistence**: Serialized via joblib to `mc_calibrator.pkl` or `mc_calibrators_innings.pkl`.

**Relationship**: Used by `simulate()` and `simulate_vectorized()` to calibrate final aggregated mean probability.

## State Transitions

### ODI Match Simulation Flow

```
Start: MatchState(innings=N, score=0, wickets=0, balls_remaining=300)
  │
  ├─ For each ball (up to 300):
  │   ├─ Determine phase from balls_remaining (PP/Mid/Setup/Death)
  │   ├─ Sample run outcome from phase distribution
  │   ├─ Sample wicket outcome from phase wicket_prob × wicket_multiplier[wickets]
  │   ├─ Apply outcome: score += runs, balls_remaining -= 1, wickets += is_wicket
  │   └─ Check terminal: wickets >= 10 OR balls_remaining <= 0 OR (inn2 AND score >= target)
  │
  └─ Terminal state reached
      ├─ Innings 1: Evaluate via resource_win_prob (projected total vs par)
      └─ Innings 2: 
          ├─ Target chased → win_prob = 1.0
          ├─ All out / overs done → win_prob = 0.0
          └─ Otherwise → resource_win_prob (remaining resources vs required runs)
```
