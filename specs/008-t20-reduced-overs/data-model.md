# Data Model: T20 Reduced-Over Match Support

**Feature**: 008-t20-reduced-overs  
**Date**: 2026-02-21

## Entities

### 1. ReducedMatchConfig (derived from FormatConfig)

A scaled T20 match configuration for matches shorter than 20 overs.

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `total_overs` | int | Input (5-20) | Total overs per innings |
| `total_balls` | int | Derived (`total_overs * 6`) | Total balls per innings |
| `par_score` | float | Derived (DLS resource curve) | Expected score for this match length |
| `phase_thresholds` | dict[str, int] | Derived (proportional scaling) | Phase boundary overs: powerplay, middle, death, final |
| `powerplay_end` | int | Derived | Last over of powerplay phase |
| `death_start` | int | Derived | First over of death phase |

**Derivation rules**:
- `par_score = t20_par (160) × DLS_resource_pct(total_overs, wickets=0)`
- Phase scaling: powerplay = 30% of overs (min 2, max 6), death = last 25% (min 2)
- `phase_thresholds["final"]` must equal `total_overs` (FormatConfig validation)
- All other FormatConfig fields (DLS table, run rates, wicket penalties) inherited from T20 base

**Relationships**: Created by `FormatConfig.t20_reduced(total_overs)`. Consumed by `ResourceFeatureCalculator`, simulation engine, and live predictor.

**State transitions**: Immutable after creation. A new config is created if `total_overs` changes mid-match (rain interruption detected by CREX).

---

### 2. SimulationMatchState (extended)

The simulation-layer match state, extended with `total_balls`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `innings` | int | — | Current innings (1 or 2) |
| `score` | int | — | Current score |
| `wickets_lost` | int | — | Wickets fallen (0-10) |
| `balls_remaining` | int | — | Balls left in innings (0 to `total_balls`) |
| `target_runs` | int? | None | Chase target (innings 2 only) |
| **`total_balls`** | **int** | **120** | **Total balls in this innings (new field)** |
| `league` | str? | None | League code for calibration |
| `batting_team` | str? | None | Batting team name |
| `bowling_team` | str? | None | Bowling team name |
| `venue` | str? | None | Venue name |
| `batting_team_win_rate` | float? | None | Batting team's overall win rate |
| `bowling_team_win_rate` | float? | None | Bowling team's overall win rate |

**Validation rules**:
- `0 <= balls_remaining <= total_balls` (was: `0 <= balls_remaining <= 120`)
- `total_balls = total_overs * 6` where `5 <= total_overs <= 20`
- `0 <= wickets_lost <= 10`

**Derived properties** (must use `total_balls`):
- `overs_completed = (total_balls - balls_remaining) / 6`
- `phase = get_phase(balls_remaining, total_balls)` (was: `get_phase(balls_remaining)`)

---

### 3. MCCalibrator

Platt scaling calibrator for Monte Carlo raw predictions.

| Field | Type | Description |
|-------|------|-------------|
| `calibrator` | LogisticRegression | Fitted sklearn logistic regression on logit(mc_pred) |
| `training_samples` | int | Number of samples used for fitting |
| `training_brier` | float | Brier score on training data |
| `training_log_loss` | float | Log loss on training data |
| `fitted_date` | str | ISO date when fitted |

**Fitting process**:
1. Run MC on historical 20-over match states → collect `mc_raw_prob`
2. Pair with actual outcomes → `(logit(mc_raw_prob), actual_win)`
3. Fit logistic regression → Platt calibrator
4. Serialize as `mc_calibrator.pkl`

**Usage**: `calibrated_prob = calibrator.predict_proba(logit(mc_raw_prob))`

---

### 4. Recorded Ball State (extended schema)

Two new columns added to the PyArrow BALL_STATE_SCHEMA for match state recording.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| **`total_overs`** | **int16** | **20** | Total overs for this innings |
| **`revised_target`** | **int16?** | **null** | DLS-revised target (null if standard) |

**Relationships**: Written by `MatchStateLogger`, read by `StateAnalyzer` for calibration reports.

## Entity Relationship Diagram

```
FormatConfig.t20_reduced(total_overs)
    │
    ├──► ResourceFeatureCalculator(config)
    │        └── calculate_all_features() → resource_win_prob (raw)
    │
    ├──► SimulationMatchState(total_balls=total_overs*6)
    │        │
    │        ├──► MonteCarloEngine.simulate(state, horizon)
    │        │        └── NextBallSampler(phase from scaled boundaries)
    │        │
    │        └──► TerminalStateEvaluator(state)
    │                 └── uses state.total_balls for overs_completed
    │
    └──► LivePredictor
             ├── CREX scraper → detects total_overs, revised_target
             ├── CLI args → --total-overs, --revised-target (override)
             ├── Mode switch: total_overs < 20 → MC-only
             └── MCCalibrator → calibrated_prob (betting-grade)
```
