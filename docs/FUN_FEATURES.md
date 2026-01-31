# Fun Features & Experimental Tools 🎲

This document catalogs experimental and "just for fun" features in the BBL pipeline that, while not critical to core model performance, provide interesting insights, educational value, or nostalgic cricket analysis tools.

---

## 📊 Win Probability Lookup Charts (Feb 2026)

**Status:** ✅ Production Ready  
**Purpose:** Educational / Fast Lookup / Nostalgia  
**Commit:** `84d5660`

### What Is It?

A bookmaker-style ready reckoner system that pre-computes **10,439 win probabilities** across all common match states, allowing instant lookup without calculation. Think of it as the digital version of those old paper cricket charts bookies used!

### Why We Built It

1. **Nostalgia** - Recreate the experience of old bookmaker cricket charts
2. **Education** - Help newcomers understand how match states translate to winning chances
3. **Performance** - 100-500x faster than real-time calculation for batch analysis
4. **Validation** - Spot-check model calibration at key match states

### Technical Details

**Pre-Computed Grid:**
- First Innings: 21 overs × 26 scores × 11 wickets = **6,006 entries**
- Second Innings: 13 ball milestones × 31 runs × 11 wickets = **4,433 entries**
- Total: **10,439 probabilities** (~500 KB CSV files)

**Performance:**
- Lookup: <0.001 seconds (instant)
- On-demand calculation: ~0.005 seconds
- Speedup: **100-500x faster**

### Files Created

```
src/bbl_pipeline/features/win_prob_lookup_tables.py  # Generator class
scripts/view_win_prob_chart.py                       # Terminal viewer
docs/WIN_PROB_CHARTS_USAGE.md                        # Usage guide
docs/WIN_PROB_LOOKUP_GUIDE.md                        # Sample charts
data/win_prob_tables/                                # 22 CSV files (gitignored)
  ├── innings1_wickets_0.csv through innings1_wickets_10.csv
  └── innings2_wickets_0.csv through innings2_wickets_10.csv
```

### How to Use

#### Generate Tables
```bash
python -m src.bbl_pipeline.features.win_prob_lookup_tables
```

#### View Charts
```bash
# Full chart view
python scripts/view_win_prob_chart.py --innings 1 --wickets 0

# Quick lookup (12.3 overs, 95 runs, 3 wickets)
python scripts/view_win_prob_chart.py --innings 1 --lookup 12.3 95 3
```

#### Python API
```python
from bbl_pipeline.features.win_prob_lookup_tables import WinProbabilityLookupTables

lookup = WinProbabilityLookupTables()
prob = lookup.lookup_first_innings(overs_bowled=12.3, current_score=95, wickets_lost=3)
print(f"Win probability: {prob:.2%}")  # 41.3%
```

#### Excel/Spreadsheet
1. Open `data/win_prob_tables/innings2_wickets_3.csv`
2. Find row (balls remaining) and column (runs required)
3. Read win probability at intersection

### Sample Output

**First Innings (0 Wickets Down):**
```
Overs |    0   50  100  150  200
------|---------------------------
   0  | 37%  37%  37%  37%  37%
   5  | 26%  54%  63%  63%  63%
  10  | 12%  31%  76%  88%  88%
  15  |  9%   9%  37%  79%  96%
  20  |  5%   5%  11%  33%  68%
```

**Second Innings (0 Wickets Down):**
```
Balls |   10   30   50   70   90
------|---------------------------
 120  | 99.8% 99.6% 99.3% 98.5% 97.1%
  60  | 99.9% 99.9% 99.9% 93.7% 52.8%
  30  | 99.9% 99.9% 37.2%  3.7%  0.2%
  12  | 93.5%  1.9%  0.1%  0.1%  0.1%
   1  |  0.1%  0.1%  0.1%  0.1%  0.1%
```

### Use Cases

1. **Live Commentary** - Instant win probability without calculation
2. **Educational Tool** - Show beginners how match states affect outcomes
3. **Strategic Analysis** - Compare scenarios ("20 more runs in 3 overs = +23% win prob")
4. **Batch Processing** - Analyze thousands of historical match states quickly
5. **Model Validation** - Spot-check calibration at key match moments

### Why "Just for Fun"?

While fully functional and production-ready, this feature isn't critical to the core win probability model. The real-time `ResourceFeatureCalculator` provides the same results with only 5ms overhead. However:

- **It's delightful** - There's something satisfying about flipping through CSV tables like old cricket manuals
- **It's educational** - Great for teaching cricket analytics
- **It's nostalgic** - Brings back the era of paper charts and slide rules
- **It's practical** - Actually useful for batch analysis and validation

### Future Enhancements (Maybe!)

- [ ] HTML table generator with heatmap colors
- [ ] Interactive web UI (Streamlit chart browser)
- [ ] League-specific calibrated tables (BBL vs ILT20 vs WPL)
- [ ] Printable PDF charts (actual bookmaker format)
- [ ] ASCII art charts for maximum terminal nostalgia

---

## 🎯 Guidelines for Fun Features

When adding experimental/fun features to this repo:

1. **Document clearly** - Explain what it is and why it exists
2. **Mark status** - Label as "Experimental", "Fun", or "Production Ready"
3. **Keep isolated** - Don't break core functionality
4. **Add value** - Even fun features should teach or demonstrate something
5. **Have fun!** - Cricket analytics should be enjoyable 🏏

---

*"Not all who wander are lost - some are just exploring cricket analytics for fun!"* 🎲📊
