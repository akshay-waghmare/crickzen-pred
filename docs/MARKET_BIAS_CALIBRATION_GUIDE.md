# Market-Based Bias Calibration Guide

**Last Updated:** 2026-04-19
**Applicable To:** Any T20 league with exchange odds data from betx21.live

---

## Overview

This guide documents the end-to-end workflow for closing the gap between our ML model
and exchange market odds using **logit-space bias correction**. The workflow was developed
and validated on IPL 2026 data and is designed to be reproducible for any league (PSL,
BBL, SA20, etc.) where betx21.live records market data.

### Architecture

```
Model (league-specific or global)
    ↓
Per-Over Isotonic Calibration (38 calibrators)
    ↓
Phase Isotonic Calibration (6 calibrators, fallback)
    ↓
League LogitBias Correction (phase + innings fallback)  ← THIS GUIDE
    ↓
Innings Transition Smoothing (blend inn1 prior for inn2 overs 1-6)
    ↓
Final P(batting_team wins)
```

### Results (IPL 2026, 12 matches, 432 observations)

**Recommended: IPL v3 standalone model (ipl_v3 + ipl_iso + LogitBias + blend)**

| Stage | Brier | vs Market |
|-------|-------|-----------|
| Market (exchange mid-price) | 0.1446 | baseline |
| IPL v3 raw | ~0.1530 | +5.8% |
| + Per-over isotonic | 0.1484 | +2.7% |
| + LogitBias correction | ~0.1430 | −1.1% |
| + Transition smoothing (6 overs) | **0.1407** | **−2.7%** |

**Note:** IPL v3 uses a corrected resource calculator (rrr_beta=0.57) which makes
inn2 predictions better calibrated. As a result, inn2 LogitBias is minimal —
only inn2_powerplay bias is applied; inn2_mid/death use raw isotonic output.

Previous global model pipeline for reference:

| Stage | Brier | vs Market |
|-------|-------|-----------|
| Global raw | 0.1571 | +8.7% |
| + Global isotonic + LogitBias + blend | 0.1445 | −0.1% |

---

## Prerequisites

### 1. betx21.live Market Data

Market data is recorded by the betx21.live production system. Data is organized as:

```
<download_dir>/
├── 2026-04-03/
│   ├── 35479923_odds.jsonl.gz     # Match odds ticks (back/lay prices)
│   ├── 35479923_scores.jsonl.gz   # Ball-by-ball score updates
│   └── 35479923_sessions.jsonl.gz # Session/fancy betting data
├── 2026-04-04/
│   └── ...
```

**Key data files:**
- `*_odds.jsonl.gz`: Contains `matchOdds` market type with runner prices. Each tick has
  timestamp `t`, runners `r` with back `b` and lay `l` arrays, market status `ms`.
- `*_scores.jsonl.gz`: Contains team names `t1`/`t2` and scores `s1`/`s2`.
  **CRITICAL:** `s1` is always team1's score regardless of batting order. Use Cricsheet
  for ground truth on who batted first.

### 2. Cricsheet Data (Ground Truth)

Cricsheet JSON files provide the authoritative batting order, over-by-over state, and
match result. These must be ingested and processed into features:

```bash
bbl-pipeline ingest --input-dir data/raw_json/<league> --output-dir data/<league>_raw
bbl-pipeline process --input-dir data/<league>_raw/matches --output-dir data/<league>_features_v2 \
  --feature-store-dir data/<league>_feature_store_v2
```

### 3. Trained Global Model

The frozen global T20 model at `models/t20_male_v2/` with:
- `champion_model.joblib` — XGBLogRegEnsemble
- `isotonic_calibrator.pkl` — Per-over + phase calibrators

---

## Step-by-Step Workflow

### Step 1: Download Market Data

Download betx21 recordings for the target league. Data is organized by date with
event IDs as filenames.

```python
# Filter for your league by checking team names in *_scores.jsonl.gz
# See scripts/ipl_oos_bias_analysis.py STEP 2 for the parsing pattern
```

**League team sets to define:**
```python
# IPL
IPL_TEAMS = {
    'Chennai Super Kings', 'Mumbai Indians', 'Royal Challengers Bengaluru',
    'Kolkata Knight Riders', 'Delhi Capitals', 'Punjab Kings',
    'Rajasthan Royals', 'Sunrisers Hyderabad', 'Gujarat Titans',
    'Lucknow Super Giants',
}

# PSL (example)
PSL_TEAMS = {
    'Islamabad United', 'Karachi Kings', 'Lahore Qalandars',
    'Multan Sultans', 'Peshawar Zalmi', 'Quetta Gladiators',
}

# BBL (example)
BBL_TEAMS = {
    'Adelaide Strikers', 'Brisbane Heat', 'Hobart Hurricanes',
    'Melbourne Renegades', 'Melbourne Stars', 'Perth Scorchers',
    'Sydney Sixers', 'Sydney Thunder',
}
```

### Step 2: Build Market-to-Cricsheet Alignment

This is the most critical step. The `ipl_oos_bias_analysis.py` script demonstrates
the correct approach:

1. **Load Cricsheet features** as ground truth for innings, over, batting team
2. **Parse betx21 odds** to get timestamped back/lay mid-prices
3. **Match events** by date + team overlap (Cricsheet ↔ betx21)
4. **Map runners to teams** using end-of-match price convergence (winner's runner → p ≈ 1.0)
5. **Align odds to overs** using score timestamps as anchors
6. **Output P(inn1_team wins)** per over — a common reference frame

**⚠️ Critical Pitfalls:**
- betx21 `s1`/`s2` scores are NOT batting order — `s1` is always team1's score
- Runner IDs in odds are opaque strings, not team names
- Use Cricsheet `batting_team` as ground truth, never betx21 field order
- Minimum 10 odds ticks per match; skip matches with sparse data

**Output:** `data/<league>_model_vs_market_v3.parquet` with columns:
```
event_id, match_id, date, inn1_team, inn2_team, innings, over, phase,
batting_team, market_p_inn1, actual_inn1_wins, winner
```

### Step 3: Train LogitBias Calibrator

The `scripts/train_ipl_logit_bias.py` script trains phase-specific bias corrections:

```bash
python scripts/train_ipl_logit_bias.py \
  --model-dir models/t20_male_v2 \
  --market-data data/<league>_model_vs_market_v3.parquet \
  --features-dir data/<league>_features_v2
```

**What it does:**
1. Loads production model + isotonic calibrators
2. Scores ALL features through the full calibration chain (matching predictor.py)
3. Aggregates to per-over (last ball of each over)
4. Merges with market data
5. Computes `LogitBiasScaler` per segment: `bias = mean(logit(market) - logit(model))`
6. Saves to `models/t20_male_v2/league_calibrators/<league>/league_calibrator.pkl`

**Segments (8 calibrators):**
- 6 phase-specific: `inn1_powerplay`, `inn1_middle`, `inn1_death`, `inn2_powerplay`, `inn2_middle`, `inn2_death`
- 2 innings fallback: `innings_1`, `innings_2`

**IMPORTANT:** Biases must be computed in P(batting_team) space because `predictor.py`
applies the league calibrator to P(batting_team), not P(team1).

### Step 4: Validate with Transition Smoothing

```bash
python scripts/validate_transition_smoothing.py
```

This script replays all features through the full chain including transition blending
and compares against market at various blend windows (3, 4, 6, 8 overs).

### Step 5: Deploy

The league calibrator is automatically loaded by `predictor.py` when `--league <code>`
is passed to the live predictor:

```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "<CREX_URL>" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/<league>_feature_store_v2 \
  --league <league> \
  --output-json data/<league>_live_ml.json \
  --record-states --states-dir data/match_states/<league>
```

---

## Reproducing for a New League

### What You Need to Change

| Component | IPL-Specific | What to Change for New League |
|-----------|-------------|-------------------------------|
| Team set | `IPL_TEAMS` in `ipl_oos_bias_analysis.py` | Define `<LEAGUE>_TEAMS` set |
| betx21 data dir | `ipl_matches_download/` | Point to league's download dir |
| Cricsheet data | `data/ipl_raw/`, `data/ipl_features_v2/` | Ingest + process league data |
| Feature store | `data/ipl_feature_store_v2/` | Generate league feature store |
| Season filter | `season == '2026'` | Change to match league's season |
| Team aliases | `TEAM_ALIASES` dict | Add league-specific name variants |
| Output paths | `data/ipl_model_vs_market_v3.parquet` | Change to `data/<league>_model_vs_market_v3.parquet` |
| League calibrator dir | `league_calibrators/ipl/` | `league_calibrators/<league>/` |

### Recommended: Copy and Adapt

```bash
# 1. Copy the analysis script
cp scripts/ipl_oos_bias_analysis.py scripts/<league>_oos_bias_analysis.py

# 2. Edit: change IPL_TEAMS, ODDS_DIR, season filter, paths

# 3. Copy the training script
cp scripts/train_ipl_logit_bias.py scripts/train_<league>_logit_bias.py

# 4. Edit: change default paths and TEAM_ALIASES

# 5. Run the pipeline
python scripts/<league>_oos_bias_analysis.py
python scripts/train_<league>_logit_bias.py --market-data data/<league>_model_vs_market_v3.parquet
```

### Minimum Data Requirements

- **10+ completed matches** with odds data for reliable per-phase bias estimation
- **50+ odds ticks per match** (skip matches with <10 ticks)
- **Both innings** represented in the data
- Each phase (PP/middle/death) should have 5+ observations per innings

---

## Technical Details

### LogitBiasScaler

```python
class LogitBiasScaler:
    """Logit-space additive bias: calibrated_p = sigmoid(logit(p) + bias)"""
    
    def fit(self, model_probs, market_probs):
        bias = mean(logit(market) - logit(model))
    
    def predict(self, probs):
        return sigmoid(logit(probs) + self.bias)
```

**Why logit-space (not additive probability)?**
- Respects [0, 1] bounds naturally
- Handles asymmetry near 0 and 1
- More stable for large corrections (e.g., inn1_death bias = -0.84)
- A bias of -0.23 at p=0.5 shifts to 0.443, but at p=0.9 shifts to 0.871

### Innings Transition Smoothing

At the innings break, the model "forgets" first innings context, causing a probability
cliff (e.g., 89% → 23%). We blend the last inn1 probability as a decaying prior:

```python
if innings == 2 and overs_bowled < TRANSITION_OVERS:
    alpha = max(0, 1 - overs_bowled / TRANSITION_OVERS)
    prob = alpha * inn1_prior + (1 - alpha) * model_prob
```

- `INNINGS_TRANSITION_OVERS = 6` (default, configurable per league)
- `inn1_prior` = 1 - P(inn1_batting_team) at end of inn1 (flipped for inn2 batting team)
- Alpha decays linearly: 1.0 at over 0 → 0.0 at over 6

### Runner-to-Team Mapping

betx21 odds use opaque runner IDs. To map runners to teams:

1. Look at the last 10% of odds ticks
2. The runner with p > 0.7 at match end is the winning team
3. Cross-reference with Cricsheet match winner
4. Skip matches where end-of-match p is between 0.3-0.7 (ambiguous, e.g., rain)

### Calibration Chain Order in predictor.py

```python
# predictor.py predict() method (simplified):
raw_prob = model.predict_proba(features)[:, 1]      # P(batting_team)
prob = apply_per_over_isotonic(raw_prob)              # 38 calibrators
prob = apply_phase_isotonic_fallback(prob)             # 6 calibrators
prob = apply_league_logit_bias(prob, innings, phase)   # 8 calibrators
prob = apply_transition_blend(prob, inn1_prior, alpha)  # Linear decay
return prob
```

---

## IPL-Specific Results (Reference)

### Bias Values (12 matches, 432 observations)

| Segment | Bias | Direction | Interpretation |
|---------|-----:|-----------|---------------|
| inn1_pp | -0.37 | DOWN | Model over-predicts inn1 batting team in PP |
| inn1_mid | -0.23 | DOWN | Same in middle overs |
| inn1_death | -0.84 | DOWN | Strong correction in death overs |
| inn2_pp | +0.27 | UP | Model under-predicts inn2 batting team in PP |
| inn2_mid | +0.38 | UP | Same in middle overs |
| inn2_death | -0.97 | DOWN | Model over-predicts chasers in death |
| innings_1 | -0.42 | DOWN | Fallback |
| innings_2 | +0.09 | UP | Fallback |

### Transition Smoothing Impact (Inn2 Powerplay)

| Blend Window | Inn2 PP Brier | Overall Brier | vs Market |
|-------------|---------------|---------------|-----------|
| No blend | 0.1371 | 0.1480 | +2.4% |
| blend(3) | 0.1286 | 0.1466 | +1.4% |
| blend(4) | 0.1249 | 0.1461 | +1.0% |
| **blend(6)** | **0.1199** | **0.1454** | **+0.5%** |
| blend(8) | 0.1168 | 0.1446 | +0.0% |

### Known Limitations

1. **Inn2 Death** — LogitBias correction makes it slightly worse (+29.5% vs market).
   The -0.97 bias is aggressive. Needs more data (currently ~70 obs).
2. **12 matches is small** — Per-phase biases may shift with more data. Recommend
   re-running after 20+ matches.
3. **betx21 data quality** — Some matches have sparse odds (<10 ticks), rain
   interruptions, or ambiguous runner mappings. The scripts filter these automatically.

---

## Scripts Reference

| Script | Purpose | League-Specific? |
|--------|---------|-----------------|
| `scripts/ipl_oos_bias_analysis.py` | Build market↔Cricsheet aligned dataset | Yes (copy + edit for new league) |
| `scripts/train_ipl_logit_bias.py` | Train LogitBiasScaler from market data | Partially (paths are configurable via args) |
| `scripts/validate_transition_smoothing.py` | Validate transition blending OOS | Yes (hardcoded IPL paths) |
| `src/bbl_pipeline/training/league_calibrator.py` | LogitBiasScaler class definition | No (generic) |
| `src/bbl_pipeline/inference/predictor.py` | Production inference with full chain | No (generic, uses --league) |

### Key Files

| File | Description |
|------|-------------|
| `data/<league>_model_vs_market_v3.parquet` | Aligned market+model dataset |
| `models/t20_male_v2/league_calibrators/<league>/league_calibrator.pkl` | Production calibrator |
| `models/t20_male_v2/isotonic_calibrator.pkl` | Per-over isotonic calibrators |
| `models/t20_male_v2/champion_model.joblib` | Frozen global T20 model |

---

## Changelog

- **2026-04-19:** Initial guide. IPL validated with 12 matches, Brier gap closed from +8.7% to +0.5%.
- **2026-04-19:** Added innings transition smoothing (committed `032c586`).
- **2026-04-19:** Fixed critical batting order bug in betx21 data alignment (commit `a6dc45b`).
