# 🚀 How to Start Live Match Prediction

## ⚡ Quick Start (Recommended: Use the Launcher App)

```bash
python scripts/launcher.py
```

This opens a desktop GUI where you can paste a CREX URL, pick a league, and start everything with one click. See [Launcher App](#-launcher-app) below.

---

## 🔧 Manual CLI Start

### Prerequisites

1. **Verify the correct package is installed** (see [Worktree Guide](WORKTREE_PACKAGE_GUIDE.md)):
   ```bash
   python -c "import bbl_pipeline.features.format_config as m; print('Loaded from:', m.__file__)"
   ```
2. **Playwright browser** installed: `playwright install chromium`

### Step 1: Find a Live CREX Match URL

Go to **[crex.com](https://crex.com)** → Find a **LIVE** match → Copy the URL

Example:
```
https://crex.com/cricket-live-score/csk-vs-pbks-7th-match-indian-premier-league-2026-match-updates-10Y5
```

### Step 2: Start the Predictor

```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/bbl_feature_store_v2 \
  --league ipl \
  --output-json data/ipl_live_ml.json \
  --record-states \
  --states-dir data/match_states/ipl
```

### Step 3: Start the Streamlit Visualization (separate terminal)

```bash
streamlit run src/bbl_pipeline/app/live_streamlit_app.py
```

Open **http://localhost:8501** in your browser.

---

## 🏏 League Configurations

| League | `--league` | `--model-dir` | `--feature-store-dir` | `--output-json` |
|--------|-----------|---------------|----------------------|-----------------|
| **IPL** | `ipl` | `models/t20_male_v2` | `data/bbl_feature_store_v2` | `data/ipl_live_ml.json` |
| **BBL** | `bbl` | `models/bbl_v12` | `data/bbl_feature_store_v2` | `data/bbl_live_ml.json` |
| **SA20** | `sa20` | `models/t20_male_v2` | `data/bbl_feature_store_v2` | `data/sa20_live_ml.json` |
| **ILT20** | `ilt20` | `models/ilt20_v5` | `data/ilt_feature_store_v3` | `data/ilt20_live_ml.json` |
| **WPL** | `wpl` | `models/t20_male_v2` | `data/bbl_feature_store_v2` | `data/wpl_live_ml.json` |
| **T20 WC** | `t20i_male` | `models/t20_international_male_v2` | `data/t20_international_male_feature_store_v2` | `data/wc_live_ml.json` |
| **SSM** | `ssm` | `models/t20_male_v2` | `data/bbl_feature_store_v2` | `data/ssm_live_ml.json` |

### IPL-Specific Configuration

The IPL uses a league-specific `FormatConfig.ipl()` with tuned parameters:
- **par_score:** 173.45 (vs 160.0 generic T20) — reflects IPL's higher scoring
- **league_avg_score:** 167.28
- **bat_first_win_rate:** 45.81%
- **Expected run rates:** PP 7.53, Middle 7.51, Death 9.02, Final 10.68

---

## 📊 Venue Average Score

The predictor extracts venue-specific scoring data from CREX's match info page:

1. **Venue Stats section**: Overall venue average 1st innings score
2. **On Venue tab**: Each team's average score at this venue → **simple average** `(Team1_avg + Team2_avg) / 2`

Priority chain (highest first):
1. On-Venue team averages (both teams need ≥2 matches)
2. CREX Venue Stats section (Avg 1st Inns)
3. Feature store historical data
4. Hardcoded IPL venue defaults (e.g., Chepauk: 156)
5. T20 default: 160.0

---

## 📺 Match State Recording

Use `--record-states` to capture ball-by-ball data for post-match analysis:

```bash
--record-states --states-dir data/match_states/ipl
```

Records 80+ columns per ball: raw match state, computed features, calibration chain, CREX market odds, and model metadata. Output: Parquet files in the states directory.

---

## 🖥️ Launcher App

A desktop GUI for one-click match prediction setup:

```bash
python scripts/launcher.py
```

Features:
- Paste any CREX URL and select the league
- Auto-configures model, feature store, and output paths
- Starts predictor + Streamlit with one click
- Record states enabled by default
- Shows live process status and log output
- Stop all processes cleanly

---

## 🚨 Troubleshooting

### Wrong par_score or model behavior
The package may be installed from a different worktree. See [Worktree Guide](WORKTREE_PACKAGE_GUIDE.md).

### "League calibrator not found"
This warning is expected — not all leagues have dedicated calibrators. The phase/per-over calibrators still apply.

### Browser opens but no predictions
- Verify the match is **LIVE** on CREX
- Check the terminal for error messages
- CREX page structure may have changed — check scraper selectors

### "Playwright not installed"
```bash
pip install playwright
playwright install chromium
```
