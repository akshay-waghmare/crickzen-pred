# T20 Female v3 Model Documentation

**Version:** v3  
**Created:** January 19, 2026  
**Type:** Unified Women's T20 Model

---

## Overview

The t20_female_v3 model represents a **5x expansion** of the women's T20 dataset, incorporating 10 leagues and achieving state-of-the-art calibration with a Brier score of 0.1610.

---

## Dataset Expansion

### Previous Model (v2)
- **Matches:** 260
- **Samples:** 57,999
- **Leagues:** 2 (WPL, Super Smash)
- **Teams:** 12
- **Calibrated Brier:** 0.1653

### New Model (v3)
- **Matches:** 1,217 (+368%)
- **Samples:** 283,026 (+388%)
- **Leagues:** 10+
- **Teams:** 65
- **Calibrated Brier:** 0.1610 (-2.6% improvement)

---

## Leagues Included

| League | Matches | Slug | Country/Region |
|--------|---------|------|----------------|
| Women's Big Bash League (WBBL) | 519 | `wbb` | Australia |
| Super Smash (Female) | 186 | `super_smash` | New Zealand |
| ICC Women's T20 World Cup | 135 | `icc_womens_t20_world_cup` | International |
| Charlotte Edwards Cup | 124 | `cec` | England |
| Women's Cricket Super League | 95 | `wsl` | England |
| Women's Premier League (WPL) | 74 | `wpl` | India |
| Women's T20 Blast | 56 | `wtb` | England |
| FairBreak Invitational | 39 | `frb` | UAE |
| Women's Caribbean Premier League | 25 | `wcl` | Caribbean |
| Women's T20 Challenge | 13 | `wtc` | India |

---

## Model Performance

### Out-of-Fold (5-Fold Cross-Validation)

**Overall Metrics (283,026 samples):**

| Method | Brier | ECE | LogLoss |
|--------|-------|-----|---------|
| **brier_optimized** | **0.1610** | 0.0000 | 0.4787 |
| innings_phase | 0.1626 | 0.0000 | 0.4836 |
| innings_specific | 0.1632 | 0.0000 | 0.4857 |
| ece_optimized | 0.1632 | 0.0031 | 0.4864 |
| combined | 0.1634 | 0.0000 | 0.4866 |
| raw | 0.1638 | 0.0095 | 0.4880 |
| logloss_optimized | 0.1647 | 0.0200 | 0.4930 |

**Resource Win Prob Baseline:** 0.2042 Brier (21.2% worse than our model)

### By Innings

**Innings 1:**
- Raw Brier: 0.1995
- Calibrated Brier: 0.1964 (brier_optimized)
- ECE: 0.0000

**Innings 2:**
- Raw Brier: 0.1245
- Calibrated Brier: 0.1221 (brier_optimized)
- ECE: 0.0000

### By Phase

| Phase | Brier (Calibrated) | ECE |
|-------|-------------------|-----|
| Inn1 Powerplay | 0.2211 | 0.0000 |
| Inn1 Middle | 0.1924 | 0.0000 |
| Inn1 Death | 0.1809 | 0.0000 |
| Inn2 Powerplay | 0.1685 | 0.0000 |
| Inn2 Middle | 0.1151 | 0.0000 |
| Inn2 Death | 0.0643 | 0.0031 |

---

## Model Architecture

### Ensemble Composition
- **Type:** XGBLogRegEnsemble
- **Weights:** 50% XGBoost + 50% Logistic Regression
- **Features:** 25 predictive features

### Top Features
1. `resource_win_prob` - DLS-style resource calculation
2. `score_vs_par` - Current score vs venue/situation average
3. `required_run_rate` - Target RRR for innings 2
4. `wickets_lost` - Wickets down
5. `pressure_index` - Game state pressure metric

### Calibration Strategy

**Production Calibrator:** Brier-Optimized (Per-Over Isotonic)
- **38 calibrators:** 2-20 overs for each innings
- **Achieves:** Perfect calibration (ECE ≈ 0.0000)
- **Best Brier:** 0.1610 across all methods

---

## Feature Store

**Location:** `data/t20_female_feature_store_v3/`

**Components:**
1. **team_ratings.parquet**
   - 65 teams
   - Columns: team, win_rate, matches, bat_first_wr, bowl_first_wr
   
2. **player_stats.parquet**
   - Rolling averages for batters and bowlers
   - Venue-specific and matchup-specific stats
   
3. **venue_stats.parquet**
   - Average scores by phase
   - Chase success rates

---

## League Calibration

### WPL (Women's Premier League)

**Training Data:** 17,062 samples from 74 WPL matches

**Temperature Scaling:**
- Innings 1: T = 0.8295 (slight sharpening)
- Innings 2: T = 0.9793 (minimal adjustment)

**Performance on WPL:**
- Raw Brier: 0.1482
- Calibrated Brier: 0.1482 (already well-calibrated)
- LogLoss: 0.4423 → 0.4405 (+0.4%)

**Saved to:** `models/t20_female_v3/league_calibrators/wpl/`

**Note:** Temperature values close to 1.0 indicate the global model generalizes well to WPL without requiring significant adjustment.

---

## Usage

### Training Data
```bash
data/t20_female_features_v3/training.parquet  # 283,026 samples
```

### Model Artifacts
```bash
models/t20_female_v3/champion_model.joblib           # Main model
models/t20_female_v3/isotonic_calibrator.pkl         # OOF calibrators
models/t20_female_v3/oof_calibration_results.csv     # Detailed metrics
models/t20_female_v3/OOF_CALIBRATION_REPORT.md       # Analysis report
```

### League Calibrators
```bash
models/t20_female_v3/league_calibrators/wpl/league_calibrator.pkl
models/t20_female_v3/league_calibrators/wpl/isotonic_calibrator.pkl  # OOF-compatible
```

### Live Inference
```python
from bbl_pipeline.inference.crex_live_predictor import CrexLivePredictor

predictor = CrexLivePredictor(
    model_dir="models/t20_female_v3",
    feature_store_dir="data/t20_female_feature_store_v3",
    league="wpl"  # Optional: applies league-specific calibration
)

predictions = predictor.predict(match_url="CREX_URL")
```

---

## Comparison to Previous Versions

| Metric | v1 | v2 | v3 |
|--------|----|----|-----|
| Matches | 74 (WPL only) | 260 | 1,217 |
| Samples | 17,062 | 57,999 | 283,026 |
| Raw Brier | 0.1821 | 0.1821 | 0.1638 |
| Calibrated Brier | 0.1653 | 0.1653 | 0.1610 |
| ECE | 0.0000 | 0.0000 | 0.0000 |
| Leagues | 1 | 2 | 10+ |

**Key Improvements in v3:**
- 5x more training data
- Global coverage across 10+ leagues
- Better generalization (lower raw Brier)
- Best calibrated performance

---

## Download Script Updates

Updated `scripts/download_cricsheet_t20.py` with correct female league slugs:

```python
FEMALE_LEAGUES = [
    "wbb",                      # Women's Big Bash League
    "wpl",                      # Women's Premier League
    "super_smash",              # Super Smash (female portion)
    "wcl",                      # Women's Caribbean Premier League
    "cec",                      # Charlotte Edwards Cup
    "wsl",                      # Women's Cricket Super League
    "wtb",                      # Women's T20 Blast
    "frb",                      # FairBreak Invitational
    "wtc",                      # Women's T20 Challenge
    "icc_womens_t20_world_cup", # ICC Women's T20 World Cup
]
```

---

## Notes

### Data Quality
- All matches processed through standard BBL pipeline
- Skipped: Super Over ties, no-result matches
- 21 seasons covered (2004-2026)

### Model Registry
Updated `models/model_registry.json` with v3 metadata:
- Created: 2026-01-19
- Type: unified_female
- Notes: "Expanded from v2 (260 matches) to v3 (1217 matches) - 368% increase"

### Future Improvements
1. Add league column to processed features for true league-specific calibration
2. Include more ICC tournament data (ODI World Cup conversion to T20 features)
3. Expand to include The Hundred (women's) when available
4. Fine-tune per-league calibrators with more recent data

---

## References

- **OOF Analysis:** `models/t20_female_v3/OOF_CALIBRATION_REPORT.md`
- **Model Registry:** `models/model_registry.json`
- **Download Script:** `scripts/download_cricsheet_t20.py`
- **Cricsheet:** https://cricsheet.org/downloads/
