# Feature Specification: Odds Direction Model with Confidence Intervals

**Feature Branch**: `010-odds-direction-model`  
**Created**: 2026-04-11  
**Status**: Draft / Research  
**Input**: Build a model that predicts the *direction* and *magnitude* of odds movement over the next N balls, with confidence intervals — complementing the existing ML (point-estimate) and MC (simulation CI) models.

---

## Problem Statement

We currently have two models running during live prediction:

| Model | Output | Strength | Gap |
|-------|--------|----------|-----|
| **ML (XGBLogRegEnsemble)** | Point probability (e.g., 62.3%) | Accurate calibrated win prob | No direction signal |
| **MC (Monte Carlo)** | Mean prob + 90% CI (p5/p95) | CI bands from simulation | CI is *state-based*, not *trajectory-based* |

**The missing piece**: Neither model tells us *where the odds are heading*. The ML model says "right now it's 62%", the MC says "CI is [55%, 70%]", but neither says "this probability is likely to drift toward 70% over the next 2 overs because momentum, batting matchup, and phase transition favor the batting team."

**During live betting, this matters because:**
- Market odds react to the same ball-by-ball events we see
- Knowing the current probability is necessary but insufficient — you need to know if the edge is *growing* or *shrinking*
- A 62% win prob moving toward 70% is a BACK signal; the same 62% moving toward 55% is a LAY/PASS signal
- MC CIs show the *range of possible outcomes* but not the *expected trajectory*

---

## Proposed Solution

Build an **Odds Direction Model (ODM)** that predicts:

1. **Direction**: Will batting team win probability increase or decrease over the next N balls? (classification: UP / DOWN / FLAT)
2. **Expected Δ (delta)**: By how much? (regression: predicted change in probability, e.g., +3.2%)
3. **Confidence Interval on Δ**: What's the range of likely movement? (e.g., Δ = +3.2% with 90% CI [-1.1%, +7.5%])

### Output Schema (per prediction)

```
{
  "direction": "UP",                    // UP | DOWN | FLAT (±1% threshold)
  "delta_mean": +0.032,                 // Expected prob change over horizon
  "delta_ci_lower": -0.011,             // 5th percentile of Δ
  "delta_ci_upper": +0.075,             // 95th percentile of Δ
  "horizon_balls": 12,                  // Prediction horizon (balls ahead)
  "confidence": "MEDIUM",               // LOW | MEDIUM | HIGH (based on CI width)
  "contributing_factors": [             // Top 3 drivers of predicted direction
    {"feature": "acceleration_potential", "impact": +0.018},
    {"feature": "phase_transition_to_death", "impact": +0.009},
    {"feature": "bowling_team_wicket_drought", "impact": +0.005}
  ]
}
```

### Integration with Existing System

The ODM runs **alongside** ML + MC during live prediction:

```
Ball Event → Feature Extraction
  ├── ML Model  → Win Prob (62.3%)
  ├── MC Engine → CI [55%, 70%] (state uncertainty)
  └── ODM Model → Direction: UP, Δ: +3.2% CI [-1.1%, +7.5%] (trajectory)

Combined Decision:
  ML says 62.3%, market says 58% → 4.3% edge
  ODM says odds moving UP → edge likely to shrink as market catches up
  → Signal: BACK NOW (before market adjusts)
```

---

## Research Phase: EDA for Feature Engineering

Before building the model, we need EDA to identify which features most strongly predict *direction of probability change*. This is a fundamentally different target variable from "current win probability."

### Phase 1: Target Variable Construction

Using recorded match states from `data/match_states/`, construct the target:

```python
# For each ball i in a match:
target_delta = prob[i + horizon] - prob[i]   # Actual prob change
target_direction = sign(target_delta)          # UP=1, DOWN=-1, FLAT=0 (±1% threshold)
```

**Horizons to investigate**: 6 balls (1 over), 12 balls (2 overs), 30 balls (5 overs)

**Data sources for target construction:**
- `model_final_prob` from recorded match states (ML calibrated probability at each ball)
- `mc_win_prob` from MC simulations (alternative target)
- `market_batting_team_prob` from CREX odds (market-based target — gold standard)

### Phase 2: Candidate Features for EDA

#### A. Momentum / Trend Features (NEW — primary research area)
| Feature | Description | Hypothesis |
|---------|-------------|------------|
| `prob_delta_last_6` | Change in model prob over last 6 balls | Recent trend continues (momentum) |
| `prob_delta_last_12` | Change in model prob over last 12 balls | Medium-term trend |
| `prob_velocity` | Rate of prob change (Δprob / Δballs) | Speed of movement |
| `prob_acceleration` | Change in velocity (2nd derivative) | Trend strengthening/weakening |
| `runs_delta_6v6` | runs_last_6 minus runs_6_to_12_ago | Scoring acceleration |
| `boundary_surge` | boundaries_last_6 / boundaries_6_to_12 | Boundary frequency trend |
| `wicket_cluster` | Wickets in last 12 balls | Collapse detection |
| `dot_ball_streak` | Consecutive dots | Pressure building |
| `scoring_entropy_last_12` | Entropy of run values in last 12 balls | Predictability of scoring |

#### B. Phase Transition Features (NEW)
| Feature | Description | Hypothesis |
|---------|-------------|------------|
| `balls_to_phase_change` | Distance to next phase boundary | Approaching death = rate change |
| `entering_death_phase` | Binary: within 2 overs of death | Death overs shift probs sharply |
| `phase_run_rate_ratio` | Current phase RR / expected phase RR | Over/under-performing phase norms |

#### C. Matchup / Situational Features (NEW)
| Feature | Description | Hypothesis |
|---------|-------------|------------|
| `new_batsman_flag` | Wicket fell in last 3 balls | New batsman = temporary slowdown |
| `partnership_balls` | Balls since last wicket | Settled partnership = stability |
| `bowler_economy_vs_phase` | Current bowler eco vs phase average | Strong/weak bowler detection |
| `batting_pair_sr` | Combined SR of current pair | Pair quality signal |

#### D. Existing Features (from ML model — reuse)
| Feature | Description | Use in ODM |
|---------|-------------|------------|
| `resource_win_prob` | DLS-based win probability | Baseline trajectory |
| `score_vs_par` | Score vs venue par | Over/under par → reversion signal |
| `pressure_index` | Cumulative pressure metric | High pressure = volatile movement |
| `run_rate_diff` | CRR minus RRR | Gap closing/widening |
| `acceleration_potential` | Batsman SR vs CRR gap | Upside potential |
| `runs_last_12`, `runs_last_18` | Rolling scoring windows | Existing momentum proxy |
| `boundary_pct_last_18` | Recent boundary % | Aggression trend |
| `wickets_last_12` | Recent wicket loss | Collapse risk |

### Phase 3: EDA Experiments

1. **Correlation Analysis**: Pearson/Spearman correlation of each candidate feature with `target_delta` at each horizon
2. **Feature Importance (RF/XGB)**: Train quick Random Forest on direction classification → extract feature importances
3. **SHAP Analysis**: SHAP values to understand feature interactions and nonlinear effects
4. **Segment Analysis**: Does feature importance change by innings, phase, or match situation?
5. **Market vs Model**: Compare direction prediction when targeting `model_final_prob` delta vs `market_batting_team_prob` delta — are the same features important?

### Phase 4: Baseline Models

Start simple, add complexity only if needed:

1. **Naive Baseline**: Predict FLAT always (majority class) → establishes minimum accuracy
2. **Momentum Baseline**: If prob went up last 6 balls → predict UP → tests pure momentum
3. **Linear**: Logistic regression on top-10 EDA features → direction classification
4. **XGBoost**: Gradient boosted trees on full feature set → direction + magnitude
5. **Quantile Regression**: For CI estimation — predict 5th, 50th, 95th percentile of Δ

---

## User Scenarios

### User Story 1 — EDA Discovery (Priority: P0)

As a model developer, I want to run EDA on recorded match states to discover which features best predict the direction of probability movement, so I can make informed decisions about model architecture.

**Acceptance Criteria:**
1. Load consolidated match state parquet files from `data/match_states/`
2. Construct target variable (prob delta at 6/12/30 ball horizons)
3. Compute correlation matrix and feature importances
4. Produce ranked feature list with effect sizes
5. Generate EDA report with visualizations (correlation heatmap, SHAP summary, segment breakdown)

### User Story 2 — Direction Classification (Priority: P1)

As a betting analyst during live prediction, I want to see whether odds are likely to move UP or DOWN over the next 1-2 overs, so I can time my bets better.

**Acceptance Criteria:**
1. Model predicts UP/DOWN/FLAT with accuracy > 55% (above majority-class baseline)
2. Predictions include confidence level (based on CI width)
3. Output integrates into existing `crex_live_predictor.py` JSON output
4. Latency < 10ms per prediction (lightweight model, no simulation needed)

### User Story 3 — Delta with Confidence Intervals (Priority: P1)

As a betting analyst, I want predicted probability change with a 90% confidence interval, so I can assess the risk/reward of entering a position.

**Acceptance Criteria:**
1. Model outputs `delta_mean`, `delta_ci_lower`, `delta_ci_upper`
2. CI coverage is calibrated: ~90% of actual deltas fall within predicted CI
3. CI width reflects genuine uncertainty (wider in volatile phases, narrower in settled situations)
4. `contributing_factors` shows top 3 features driving the prediction (SHAP-based)

### User Story 4 — Combined Betting Signal (Priority: P2)

As a betting analyst, I want the ODM signal combined with the existing ML edge calculation, so I get a single actionable recommendation that accounts for both current edge AND expected direction.

**Acceptance Criteria:**
1. When ML edge > 0 AND ODM direction is favorable → "STRONG BACK" signal
2. When ML edge > 0 BUT ODM direction is unfavorable → "BACK (edge shrinking)" signal
3. When ML edge < 0 AND ODM direction makes it worse → "STRONG PASS" signal
4. Signal displayed in live predictor console output alongside existing betting decision

---

## Technical Architecture

### Training Data

**Source**: Recorded match states from `data/match_states/<league>/` (Parquet files, 80+ columns per ball)

**Leagues available**: BBL, SA20, ILT20, IPL, PSL, SSM (all with recorded states from live prediction)

**Target construction**: Sliding window — for each ball `i`, compute `prob[i+N] - prob[i]` where N = horizon in balls. Last N balls of each innings are excluded (no future data).

### Model Architecture Options (to evaluate during research)

| Approach | Pros | Cons |
|----------|------|------|
| **Quantile XGBoost** | Fast, interpretable, native CI via quantile loss | No sequential context |
| **LightGBM + Conformal Prediction** | Calibrated CIs, fast inference | Two-stage pipeline |
| **NGBoost** | Native probabilistic output (mean + variance) | Slower training |
| **Simple Logistic + Bootstrap** | Very fast, easy to explain | May miss nonlinear patterns |

**Recommended starting point**: Quantile XGBoost (predict p5, p50, p95 of `target_delta`) — familiar tooling, fast inference, straightforward CI interpretation.

### Inference Integration

```python
# In crex_live_predictor.py, after ML + MC predictions:
from bbl_pipeline.inference.odds_direction_model import OddsDirectionPredictor

odm = OddsDirectionPredictor.load("models/odm_v1")
odm_result = odm.predict(
    features=current_features,        # Same features used by ML model
    momentum_features=momentum_feats,  # New momentum features
    current_prob=ml_final_prob,
    horizon_balls=12
)
# odm_result: {direction, delta_mean, delta_ci_lower, delta_ci_upper, confidence, contributing_factors}
```

---

## Evaluation Metrics

| Metric | What it measures | Target |
|--------|-----------------|--------|
| **Direction Accuracy** | % correct UP/DOWN/FLAT calls | > 55% (vs ~45% majority class baseline) |
| **Direction F1** | Balanced precision/recall per class | > 0.50 macro F1 |
| **Delta MAE** | Mean absolute error of predicted Δ | < actual std(Δ) |
| **CI Coverage** | % of actuals within predicted 90% CI | 88-92% (calibrated) |
| **CI Sharpness** | Average CI width (narrower = better) | Minimize while maintaining coverage |
| **Profit Lift** | Simulated profit using ODM timing vs naive timing | > 0 (any improvement) |

---

## Risks & Open Questions

1. **Is direction even predictable?** Efficient market hypothesis suggests odds are a random walk. EDA Phase 1 will test whether momentum/features have real signal. If correlation is < 0.05, pivot to a volatility model instead (predict CI width only).

2. **Market vs Model direction**: We may find that *model* probability direction is predictable (because the model updates deterministically) but *market* direction is not. Need to test both targets.

3. **Overfitting risk**: With 80+ features and relatively small match-level datasets, per-over predictions could overfit. Mitigation: strict cross-validation (leave-match-out), regularization, feature selection from EDA.

4. **Look-ahead bias**: Target construction uses future probability — must ensure no future-leaking features.

5. **Horizon selection**: 6 balls may be too noisy, 30 balls may be too smooth. EDA should test multiple horizons and pick the one with best signal-to-noise.

6. **FLAT class imbalance**: Most balls produce small prob changes (FLAT). May need asymmetric thresholds or drop FLAT class entirely (UP vs DOWN binary).

---

## Milestones

| Phase | Deliverable | Dependencies |
|-------|-------------|--------------|
| **Research / EDA** | Feature correlation report, ranked feature list, EDA notebook | Recorded match states data |
| **Baseline Models** | Direction accuracy benchmarks (naive, momentum, linear) | EDA results |
| **V1 Model** | Quantile XGBoost with CI, evaluated on held-out matches | Baseline results |
| **Integration** | ODM wired into `crex_live_predictor.py`, live output | V1 model artifact |
| **Evaluation** | Simulated P&L with ODM timing vs without | Integration complete |

---

## Out of Scope (for now)

- **Market microstructure modeling** (order book depth, lay/back spread dynamics)
- **Multi-match portfolio optimization** (this is single-match direction)
- **Real-time model retraining** during a match
- **Player-specific direction models** (e.g., "Kohli at crease → prob goes up")
