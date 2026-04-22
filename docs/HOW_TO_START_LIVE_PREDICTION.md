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
  --model-dir models/ipl_v6 \
  --feature-store-dir data/ipl_feature_store_v3 \
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
| **IPL** | `ipl` | `models/ipl_v6` | `data/ipl_feature_store_v3` | `data/ipl_live_ml.json` |
| **BBL** | `bbl` | `models/bbl_v12` | `data/bbl_feature_store_v2` | `data/bbl_live_ml.json` |
| **SA20** | `sa20` | `models/t20_male_v2` | `data/bbl_feature_store_v2` | `data/sa20_live_ml.json` |
| **ILT20** | `ilt20` | `models/ilt20_v5` | `data/ilt_feature_store_v3` | `data/ilt20_live_ml.json` |
| **WPL** | `wpl` | `models/t20_male_v2` | `data/bbl_feature_store_v2` | `data/wpl_live_ml.json` |
| **T20 WC** | `t20i_male` | `models/t20_international_male_v2` | `data/t20_international_male_feature_store_v2` | `data/wc_live_ml.json` |
| **SSM** | `ssm` | `models/t20_male_v2` | `data/bbl_feature_store_v2` | `data/ssm_live_ml.json` |

### Reproducible startup template (any league)

```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_URL" \
  --model-dir "MODEL_DIR" \
  --feature-store-dir "FEATURE_STORE_DIR" \
  --league "LEAGUE_CODE" \
  --output-json "OUTPUT_JSON" \
  --record-states \
  --states-dir "STATES_DIR"
```

For IPL, substitute:
- `MODEL_DIR=models/ipl_v6`
- `FEATURE_STORE_DIR=data/ipl_feature_store_v3`
- `LEAGUE_CODE=ipl`
- `OUTPUT_JSON=data/ipl_live_ml.json`
- `STATES_DIR=data/match_states/ipl`

---

## Clean restart (IPL, reproducible)

Use this when predictions look stuck or stale.

```powershell
# 1) Stop existing live runtime processes
Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -match '^python(\.exe)?$' -and
    $_.CommandLine -match 'crex_live_predictor|odm_live_json_bridge|live_streamlit_app.py|scripts\\launcher.py'
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# 2) Remove stale PID file (if present)
if (Test-Path "data/.predictor_pids.json") { Remove-Item "data/.predictor_pids.json" -Force }

# 3) Start fresh IPL predictor (v6)
.\.venv\Scripts\python.exe -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_URL" \
  --model-dir models/ipl_v6 \
  --feature-store-dir data/ipl_feature_store_v3 \
  --league ipl \
  --output-json data/ipl_live_ml.json \
  --record-states \
  --states-dir data/match_states/ipl

# 4) In a second terminal: start ODM mirror bridge for dashboard ML+MC
.\.venv\Scripts\python.exe scripts\odm_live_json_bridge.py \
  --input-json data/ipl_live_ml.json \
  --output-json data/ipl_live_ml_odm.json \
  --feature-store-dir data/ipl_feature_store_v3 \
  --league ipl \
  --odm-model-dir models/odm_v1 \
  --poll-interval 2.0

# 5) Optional: start dashboard
.\.venv\Scripts\python.exe -m streamlit run src/bbl_pipeline/app/live_streamlit_app.py --server.port 8501
```

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
- IPL and PSL ML+MC slots also launch the ODM mirror sidecar and write per-slot `*_live_ml_odm_#.json` feeds
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

### IPL-specific name resolution and calibration pitfalls

The IPL live flow needed extra repository support because several assumptions in the generic T20 path were not true for IPL:

1. **Team abbreviations collided with other leagues**
   - `DC` can mean **Delhi Capitals** in IPL or **Dubai Capitals** in ILT20
   - `RR` can mean **Rajasthan Royals** in IPL or **Rangpur Riders** in BPL
   - `MI` should resolve to **Mumbai Indians** in IPL context
   - Fix: use IPL-specific team abbreviation resolution whenever `--league ipl` is active

2. **Generic venue aliases could mis-map IPL grounds**
   - A very generic alias like `International Cricket Stadium` is unsafe because it can accidentally map an IPL venue to the wrong historical ground
   - Fix: remove overly generic aliases and add IPL-specific venue aliases/priors instead

3. **The default BBL feature store does not contain IPL historical venue priors**
   - The live predictor uses `data/bbl_feature_store_v2` for the global T20 male model
   - That store is fine for shared player/team plumbing, but IPL venue priors had to be seeded in code so the predictor has sane values even before CREX overrides land
   - CREX venue stats still take precedence at runtime:
     1. On-Venue team averages
     2. CREX Venue Stats section
     3. Seeded historical venue priors
     4. Generic T20 fallback

4. **IPL needed dedicated simulation/calibration artifacts**
   - The live predictor will fall back if these files do not exist:
     - `data/phase_distributions_ipl.json`
     - `models/t20_male_v2/league_calibrators/ipl/league_calibrator.pkl`
   - Once generated, the logs should show:
     - `Loaded IPL league calibrator`
     - `Sampler using league-specific distributions`
     - `[LEAGUE] League (IPL): ...`

5. **Streamlit needed explicit IPL feed support**
   - IPL live JSON feeds are `data/ipl_live_ml.json` and `data/ipl_live_mc.json`
   - These should be exposed directly in the Streamlit dropdown/backend controls so the dashboard opens the correct feed by default

### PSL-specific naming pitfall

The PSL live flow has a similar issue, but the mismatch is between CREX short codes and the historical PSL feature-store team names:

1. **CREX may expose short PSL codes like `ISU` and `RWP`**
   - These need league-specific resolution when `--league psl` is active
   - In this repository, `RWP` must resolve to **Rawalpindiz** because that is the canonical PSL team name stored in the generated feature store

2. **PSL should use its own generated feature store**
   - Use `data/psl_feature_store_v1` for PSL live runs
   - This keeps team and venue lookups aligned with the PSL training parquet and the PSL league calibrator

3. **PSL also needs dedicated simulation/calibration artifacts**
   - `data/phase_distributions_psl.json`
   - `models/t20_male_v2/league_calibrators/psl/league_calibrator.pkl`

### PSL artifact generation workflow

If the PSL calibrator or phase distributions are missing, regenerate them from the PSL historical JSON archive:

```bash
python -m src.bbl_pipeline.cli ingest \
  --input-dir "C:\Users\ADMINS\Downloads\psl_json" \
  --output-dir data/psl_raw

python -m src.bbl_pipeline.cli process \
  --input-dir data/psl_raw/matches \
  --output-dir data/psl_features_v1 \
  --feature-store-dir data/psl_feature_store_v1 \
  --league psl

python scripts/analysis/extract_phase_distributions.py \
  --json-dir "C:\Users\ADMINS\Downloads\psl_json" \
  --league psl \
  --output data/phase_distributions_psl.json

python -m src.bbl_pipeline.cli calibrate-league \
  --global-model models/t20_male_v2 \
  --input-file data/psl_features_v1/training.parquet \
  --league psl \
  --method temperature
```

### IPL artifact generation workflow

If the IPL calibrator or phase distributions are missing, regenerate them from the IPL historical JSON archive:

```bash
python -m src.bbl_pipeline.cli ingest \
  --input-dir "C:\Users\ADMINS\Downloads\ipl_json" \
  --output-dir data/ipl_raw

python -m src.bbl_pipeline.cli process \
  --input-dir data/ipl_raw/matches \
  --output-dir data/ipl_features_v6 \
  --feature-store-dir data/ipl_feature_store_v3 \
  --league ipl

python scripts/analysis/extract_phase_distributions.py \
  --json-dir "C:\Users\ADMINS\Downloads\ipl_json" \
  --league ipl \
  --output data/phase_distributions_ipl.json

python -m src.bbl_pipeline.cli calibrate-league \
  --global-model models/t20_male_v2 \
  --input-file data/ipl_features_v6/training.parquet \
  --league ipl \
  --method temperature
```

### Browser opens but no predictions
- Verify the match is **LIVE** on CREX
- Check the terminal for error messages
- CREX page structure may have changed — check scraper selectors

### "Playwright not installed"
```bash
pip install playwright
playwright install chromium
```
