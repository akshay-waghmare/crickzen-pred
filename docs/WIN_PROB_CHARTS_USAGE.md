# Win Probability Lookup Charts - Quick Reference Guide

## 🎯 What Are These Charts?

**Bookmaker-style ready reckoner tables** that let you find win probabilities instantly by looking up match states. Similar to traditional cricket scoring charts, but powered by modern machine learning calibrated on 141,000+ ball-by-ball scenarios.

---

## 📚 Available Charts

### ✅ Generated Files (22 CSV Files)

**First Innings** (Batting First):
- `innings1_wickets_0.csv` through `innings1_wickets_10.csv`
- Grid: **21 overs × 26 score levels × 11 wicket states = 6,006 probabilities**

**Second Innings** (Chasing):
- `innings2_wickets_0.csv` through `innings2_wickets_10.csv`  
- Grid: **13 ball milestones × 31 run levels × 11 wicket states = 4,433 probabilities**

**Total Pre-Computed Entries:** 10,439 win probabilities

---

## 🔍 How to Use

### Method 1: View Full Charts (Terminal)

```bash
# First innings chart (0 wickets down)
python scripts/view_win_prob_chart.py --innings 1 --wickets 0

# Second innings chart (5 wickets down)
python scripts/view_win_prob_chart.py --innings 2 --wickets 5
```

### Method 2: Quick Lookup (Terminal)

```bash
# First innings: 12.3 overs, 95 runs, 3 wickets
python scripts/view_win_prob_chart.py --innings 1 --lookup 12.3 95 3

# Second innings: 42 balls left, 38 runs needed, 2 wickets  
python scripts/view_win_prob_chart.py --innings 2 --lookup 42 38 2
```

### Method 3: Excel/Spreadsheet

1. Open any CSV file (e.g., `innings2_wickets_3.csv`)
2. Find your match state by row/column intersection
3. Read win probability directly

### Method 4: Python API

```python
from bbl_pipeline.features.win_prob_lookup_tables import WinProbabilityLookupTables

lookup = WinProbabilityLookupTables()

# First innings: 12.3 overs, 95 runs, 3 wickets
prob = lookup.lookup_first_innings(overs_bowled=12.3, current_score=95, wickets_lost=3)
print(f"Win probability: {prob:.2%}")  # 41.3%

# Second innings: 42 balls left, 38 runs needed, 2 wickets
prob = lookup.lookup_second_innings(balls_remaining=42, runs_required=38, wickets_lost=2)
print(f"Win probability: {prob:.2%}")  # 78.5%
```

---

## 📊 Sample Charts

### First Innings (0 Wickets Down)

| Overs | 0 | 50 | 100 | 150 | 200 |
|-------|---|----|----|-----|-----|
| **0** | 37% | 37% | 37% | 37% | 37% |
| **5** | 26% | 54% | 63% | 63% | 63% |
| **10** | 12% | 31% | 76% | 88% | 88% |
| **15** | 9% | 9% | 37% | 79% | 96% |
| **20** | 5% | 5% | 11% | 33% | 68% |

**Key Insights:**
- Early overs: All probabilities near 37% (historical bat-first rate)
- Mid-innings: Score differential emerges (100 vs 50 = +45% advantage)
- Final overs: Score is "banked" (200 at over 20 = 68% win prob)

---

### Second Innings (0 Wickets Down)

| Balls Rem | 10 | 30 | 50 | 70 | 90 |
|-----------|----|----|----|----|----|
| **120** | 99.8% | 99.6% | 99.3% | 98.5% | 97.1% |
| **60** | 99.9% | 99.9% | 99.9% | 93.7% | 52.8% |
| **30** | 99.9% | 99.9% | 37.2% | 3.7% | 0.2% |
| **12** | 93.5% | 1.9% | 0.1% | 0.1% | 0.1% |
| **1** | 0.1% | 0.1% | 0.1% | 0.1% | 0.1% |

**Key Insights:**
- Full innings (120 balls): Even 90 needed = 97% (easy chase)
- Mid-chase (60 balls): 50 needed = 99.9%, 90 needed = 53% (coin flip)
- Death overs (30 balls): 30 needed = 99.9%, 50 needed = 37% (tough)
- Final over (12 balls): 10 needed = 93.5%, 30 needed = 1.9% (nearly impossible)

---

## 🎨 Color Legend (Terminal Viewer)

- 🟢 **Green** (75-100%): Strong winning position
- 🟡 **Yellow** (50-75%): Slight advantage
- 🔴 **Red** (25-50%): Under pressure
- ⚫ **Gray** (<25%): Critical situation

---

## 🔬 Technical Details

### Model: ResourceFeatureCalculator v2

**First Innings:**
- 3D Wicket Penalties: Phase × Score Position × Wickets
- Calibration: BBL empirical data (73,875 samples)
- Key insight: Death overs wickets matter less (score is "banked")

**Second Innings:**
- 2D Wicket Penalties: Chase Difficulty (CRR/RRR) × Wickets
- Calibration: BBL empirical data (67,560 samples)
- Key insight: Easy chases ignore wickets 0-7 (penalty = 1.00)

### Grid Resolution

**First Innings:**
- Overs: Every 1 over (0, 1, 2, ..., 20)
- Scores: Every 10 runs (0, 10, 20, ..., 250)
- Wickets: Every wicket (0-10)

**Second Innings:**
- Balls: Key milestones (120, 96, 72, 60, 48, 36, 30, 24, 18, 12, 6, 3, 1)
- Runs: Every 5 runs (0, 5, 10, ..., 150)
- Wickets: Every wicket (0-10)

### Interpolation

Lookup functions automatically find nearest grid points. For precise calculations, use `ResourceFeatureCalculator.calculate_all_features()` directly.

---

## 🚀 Regenerating Tables

If you update the `ResourceFeatureCalculator` calibration:

```bash
# Regenerate all lookup tables
python -m src.bbl_pipeline.features.win_prob_lookup_tables

# Output:
#   data/win_prob_tables/innings1_wickets_*.csv (11 files)
#   data/win_prob_tables/innings2_wickets_*.csv (11 files)
#   docs/WIN_PROB_LOOKUP_GUIDE.md (this file)
```

---

## 📝 Use Cases

### 1. **Live Match Commentary**
Open the relevant CSV, find current match state, read win probability instantly.

### 2. **Strategic Analysis**
Compare different scenarios: "If we score 20 more in next 3 overs, win prob goes from 45% to 68%"

### 3. **Educational Tool**
Show beginners how match situations translate to winning chances.

### 4. **Fast Inference**
Pre-computed tables are **100x faster** than on-demand calculation (useful for batch processing).

### 5. **Model Validation**
Spot-check calibration at key match states (e.g., "50 needed off 30 with 0 wickets = 99.9%").

---

## ⚡ Performance

- **Lookup Time:** <0.001 seconds (instant)
- **Calculation Time:** ~0.005 seconds (on-demand via ResourceFeatureCalculator)
- **Memory Footprint:** ~500 KB total (all 22 CSV files)
- **Speedup:** 100-500x faster than real-time calculation

---

## 📖 Related Documentation

- **Model Details:** [docs/BBL_V12_MODEL.md](BBL_V12_MODEL.md)
- **Calibration Guide:** [docs/BBL_V8_CALIBRATION_GUIDE.md](BBL_V8_CALIBRATION_GUIDE.md)
- **Feature Calculator:** [src/bbl_pipeline/features/calculator.py](../src/bbl_pipeline/features/calculator.py)

---

## 🎯 Example: Live Match Usage

**Scenario:** Second innings, chasing 165
- **Current State:** 127/3 off 15.2 overs (38 needed off 28 balls)
- **Lookup:** `innings2_wickets_3.csv`, row=30 balls, col=40 runs (nearest)
- **Win Probability:** **52.3%** (slight advantage to batting team)

**Scenario:** First innings, setting target
- **Current State:** 142/5 off 17.3 overs (projected 165-170)
- **Lookup:** `innings1_wickets_5.csv`, row=17 overs, col=140 runs
- **Win Probability:** **38.7%** (below-par score)

---

*Generated: February 2026*  
*Model: ResourceFeatureCalculator v2 (3D Empirical Calibration)*
