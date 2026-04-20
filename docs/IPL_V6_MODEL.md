# IPL v6 Model — Pre-Chase Prior Features

**Date:** 2026-04-20
**Model:** IPL v6 (`models/ipl_v6/`)
**Training:** 278,954 balls, 1,169 matches (IPL historical)
**OOS Validation:** 23 matches true holdout (12 with market comparison)
**Key Change:** Pre-chase prior features (inn1 context + toss + venue chase bias)

---

## Architecture

```
Cricsheet JSON → Ingest → Process (v6 features) → Train → IPL v6 Model
                                                          │
                                                          ▼
                                               Per-Over Isotonic (38)
                                               + Phase fallback (6)
                                                          │
                                                          ▼
                                                    Final Prediction
```

**Pipeline:** `model → brier-optimized per-over isotonic (38 calibrators)` — 32 features, no league calibrator

---

## What Changed: v5 → v6

### New Features (5 additions, 27 → 32)

| Feature | Rank | Importance | Description |
|---------|:----:|:----------:|-------------|
| `venue_chase_success` | #5 | 0.027 | Venue-specific chase win rate (historical) |
| `inn1_death_rr` | #14 | 0.021 | Run rate in overs 16-20 of inn1 (finish momentum) |
| `inn1_pp_runs` | #15 | 0.021 | Total runs in inn1 powerplay (pitch behavior proxy) |
| `batting_won_toss` | #16 | 0.021 | Binary: did current batting team win the toss? |
| `inn1_wickets_lost` | #23 | 0.018 | Wickets fallen in inn1 (180/3 ≠ 180/8) |

### Design Philosophy

The inn2 PP gap vs market was diagnosed as a **cold-start prior deficit**, not a transition bug.
At the start of a chase, the model has weak state information while the market already prices in:
- Venue chasing conditions (dew, pitch wear)
- Toss advantage (chose to chase for a reason)
- Quality of the total set (180/3 with death acceleration ≠ 180/8 with collapse)

These features inject **pre-chase prior information** so the model doesn't start cold.

---

## OOS Results (True Holdout: train pre-2026, test 2026)

*Note: Metrics recomputed with aligned metadata (processor now includes match_id/season in training.parquet).*

### v5 → v6 Improvement (ALL 23 matches, P(batting_team))

| Segment | N | v5 Brier | v6 Brier | Change |
|---------|:-:|:--------:|:--------:|:------:|
| **OVERALL** | 870 | 0.1199 | 0.1129 | **-5.8%** ✅ |
| Inn1 | 450 | 0.1690 | 0.1627 | -3.7% ✅ |
| &nbsp; Inn1 PP | 138 | 0.1848 | 0.1811 | -2.0% |
| &nbsp; Inn1 MID | 203 | 0.1599 | 0.1537 | -3.8% ✅ |
| &nbsp; Inn1 DEA | 109 | 0.1661 | 0.1560 | -6.1% ✅ |
| **Inn2** | 420 | 0.0672 | 0.0595 | **-11.5%** ✅ |
| &nbsp; Inn2 PP | 138 | 0.1023 | 0.0969 | -5.2% ✅ |
| &nbsp; Inn2 MID | 201 | 0.0517 | 0.0419 | **-19.1%** ✅ |
| &nbsp; Inn2 DEA | 81 | 0.0459 | 0.0395 | -14.0% ✅ |

### vs Market (12 matches with Betfair odds, P(inn1_team))

| Segment | N | Market | v6 | vs Market |
|---------|:-:|:------:|:--:|:---------:|
| **OVERALL** | 394 | 0.1540 | 0.1282 | **-16.7%** ✅ |
| Inn1 | 176 | 0.2214 | 0.2093 | -5.4% ✅ |
| &nbsp; Inn1 PP | 54 | 0.2087 | 0.2199 | +5.4% |
| &nbsp; Inn1 MID | 79 | 0.2267 | 0.2065 | -8.9% ✅ |
| &nbsp; Inn1 DEA | 43 | 0.2274 | 0.2013 | -11.5% ✅ |
| **Inn2** | 218 | 0.0996 | 0.0627 | **-37.0%** ✅ |
| &nbsp; Inn2 PP | 72 | 0.1195 | 0.0961 | **-19.5%** ✅ |
| &nbsp; Inn2 MID | 104 | 0.0794 | 0.0458 | **-42.3%** ✅ |
| &nbsp; Inn2 DEA | 42 | 0.1154 | 0.0470 | **-59.2%** ✅ |

### Inn2 PP Gap Progression

| Version | Inn2 PP vs Market | Key Change |
|---------|:-----------------:|------------|
| v4 (baseline) | +33.5% | No carryover features |
| v5 | +17.5% | + target_above_par, inn1_defendability |
| **v6** | **-19.5%** | + venue_chase, toss, inn1 momentum/wickets/PP |

v6 now **beats market in every segment except Inn1 PP** (+5.4%).
Inn2 PP flipped from +33.5% worse to **-19.5% better** than market.

---

## Feature Importance (Full 32 Features)

| Rank | Feature | Importance |
|:----:|---------|:----------:|
| 1 | resource_win_prob | 0.254 |
| 2 | dls_pressure_index | 0.128 |
| 3 | score_vs_par | 0.094 |
| 4 | run_rate_diff | 0.037 |
| 5 | **venue_chase_success** | **0.027** |
| 6 | expected_final_score | 0.026 |
| 7 | rrr_times_wickets | 0.025 |
| 8 | target_above_par | 0.024 |
| 9 | situation_advantage | 0.023 |
| 10 | batting_team_win_rate | 0.023 |

---

## Experiments That Failed

### ❌ Inn1 Pitch Proxy Features (Team-Adjusted)
- dot%, boundary%, runs_per_wkt scaled by batting team strength
- Holdout: +0.6% worse overall, +4.8% worse inn2 mid
- Scoreboard-derived aggregate features hit diminishing returns

---

## Lessons Learned

1. **Pre-chase prior features > scoreboard aggregates.** Venue chase success, toss context,
   and inn1 structure (wickets, death RR, PP runs) all provide real signal. Generic pitch
   proxies (dot%, boundary%) do not.

2. **v6 beats market in every segment except Inn1 PP.** The inn2 PP gap flipped from +33.5% (v4)
   to -19.5% better than market. Overall model beats market by 16.7%.

3. **180/3 ≠ 180/8.** Carrying `inn1_wickets_lost` lets the model distinguish between
   strong totals with resources preserved vs inflated/collapse totals.

4. **Toss matters.** `batting_won_toss` ranked #16 — the model learns that choosing to
   chase carries information about conditions.

5. **Venue chase history is very strong.** `venue_chase_success` at #5 is the single
   most impactful new feature. Some venues heavily favor chasing.

6. **Isotonic calibration slightly hurts OOS.** Raw v6 Brier (0.1110) is 1.7% better than
   calibrated (0.1129) on 23 OOS matches. OOF calibrators retrained for v6 (Brier-optimized:
   0.1811). Small sample — monitor on more data.

---

## ⚠️ Data Alignment Bug & Fix (CRITICAL for Future Analysis)

### The Problem

`training.parquet` rows are **NOT position-aligned** with raw parquet files (`data/ipl_raw/matches/`).
The processor (`processor.py`) reorders rows during feature computation via `groupby()`, `merge()`, and
sort operations. This means you **cannot** join metadata from raw parquet onto training features by
row index/position.

### What Went Wrong

Earlier OOS analysis attempted to align training.parquet with raw parquet by row position to get
`match_id`, `season`, `batting_team`, and `winner` columns. This produced ~50% mismatch rate
(essentially random alignment), leading to:

| Metric | Misaligned (WRONG) | Aligned (CORRECT) |
|--------|:------------------:|:------------------:|
| v6 Overall vs Market | -1.9% | **-16.7%** |
| v6 Inn2 PP vs Market | +7.2% | **-19.5%** |
| v5→v6 Overall | -3.1% | **-5.8%** |

The misaligned data severely understated model performance and made it look like Inn2 PP was still
worse than market when in reality v6 already beats it.

### The Fix

**processor.py** (line ~1218) now includes 7 metadata columns in training.parquet output:
```python
metadata_cols = ['match_id', 'season', 'over', 'ball', 'batting_team', 'bowling_team', 'winner']
all_cols = feature_cols + [c for c in metadata_cols if c in df.columns and c not in feature_cols]
training_data = df[all_cols].copy()
```

The model (`XGBLogRegEnsemble`) ignores non-feature columns automatically via its internal
`TOP_FEATURES` list, so this change is backward-compatible.

### Rules for Future OOS Analysis

1. **NEVER** align training.parquet with raw parquet by row position
2. **ALWAYS** use the metadata columns embedded in training.parquet
3. **ALWAYS** verify alignment: check `is_winner == (batting_team == winner)` — mismatch should be 0
4. **ALWAYS** verify `winner` is consistent within each `match_id`
5. After re-processing features, check that metadata columns are present (65 cols, not 58)

### Verification Checklist (run before trusting any OOS metric)

```python
# 1. Metadata present
assert all(c in df.columns for c in ['match_id', 'season', 'batting_team', 'winner'])

# 2. Alignment: is_winner matches batting_team == winner
check = (df['is_winner'] == (df['batting_team'] == df['winner']).astype(int))
assert check.all(), f"Alignment broken: {(~check).sum()} mismatches"

# 3. Winner consistent per match
assert df.groupby('match_id')['winner'].nunique().eq(1).all()
```

### P(batting_team) vs P(inn1_team) Conversion

The model outputs `P(batting_team wins)`. For market comparison (which uses P(inn1_team)):
- **Innings 1:** `P(inn1) = P(batting)` (batting team IS the inn1 team)
- **Innings 2:** `P(inn1) = 1 - P(batting)` (batting team is the chasing/inn2 team)

Ground truth for market comparison: `inn1_wins = (winner == inn1_team)`

---

## Model Artifacts

```
models/ipl_v6/
├── champion_model.joblib      # XGBLogRegEnsemble (32 features)
├── isotonic_calibrator.pkl    # Innings-specific + per-over calibrators
├── feature_importance.csv     # 32 features ranked by importance
└── data_version.json          # Data hash for reproducibility
```

**Training data:** `data/ipl_features_v6/training.parquet`
**Feature store:** `data/ipl_feature_store_v3/`

---

## Production Deployment (2026-04-20)

### Configs Updated

All three production entry points now point to `models/ipl_v6`:

| File | Setting |
|------|---------|
| `scripts/launcher.py` | `LEAGUE_CONFIGS["IPL"]["model_dir"] = "models/ipl_v6"` |
| `src/bbl_pipeline/app/live_streamlit_app.py` | `PREDICTOR_CONFIGS["IPL ML+MC"]["model_dir"] = "models/ipl_v6"` |
| `dashboard/app/config.py` | `LEAGUE_CONFIGS["IPL"]["model_dir"] = "models/ipl_v6"` |

### Calibration Chain

```
Raw model → Per-Over Isotonic (38 calibrators) → Final prediction
            Phase fallback (6 calibrators) for over 1
```

**No league calibrator** — v6 is IPL-specific (trained on IPL data only).
OOF ECE = 0.0000 across all segments with brier-optimized calibration.

### OOF Calibration (5-fold CV, 278,954 samples)

| Method | Brier | ECE | LogLoss |
|--------|:-----:|:---:|:-------:|
| **Brier-Optimized** | **0.1811** | 0.0000 | 0.5282 |
| Innings×Phase | 0.1828 | 0.0000 | 0.5333 |
| ECE-Optimized | 0.1834 | 0.0030 | 0.5352 |
| Raw | 0.1843 | 0.0120 | 0.5387 |

### Realtime Feature Pipeline

Seven inn1 carryover features flow through:

```
CREX page → crex_live_predictor._compute_inn1_carryover_stats()
                    │
                    ▼
            MatchState (toss_winner, toss_decision, inn1_wickets_lost,
                        inn1_pp_runs, inn1_death_rr)
                    │
                    ▼
            predictor.predict() → scraped_data dict
                    │
                    ▼
            realtime_mapper.create_feature_dataframe()
                    │
                    ▼
            7 features computed:
              venue_chase_success   = 1 - venue_bat_first_win_rate
              target_above_par      = first_innings_score - venue_avg_score
              batting_won_toss      = int(batting_team == toss_winner)
              inn1_wickets_lost     = from ball history (inn2) or default 5 (inn1)
              inn1_pp_runs          = sum inn1 overs 0-5 runs (default 45)
              inn1_death_rr         = per-ball avg × 6 for inn1 overs 16+ (default 9.0)
              inn1_defendability    = resource_calculator at inn1 end state (default 0.5)
```

### Fallback Defaults

If carryover data is unavailable (inn1, or toss parse failure):

| Feature | Default | Rationale |
|---------|:-------:|-----------|
| venue_chase_success | from venue stats | Always available |
| target_above_par | 0.0 | No target in inn1 |
| batting_won_toss | 0.5 | Neutral if unknown |
| inn1_wickets_lost | 5.0 | Training mean |
| inn1_pp_runs | 45.0 | Conservative default |
| inn1_death_rr | 9.0 | Training mean |
| inn1_defendability | 0.5 | Neutral prior |

### Backward Compatibility

- All new MatchState fields are `Optional[...]` with `None` default
- Non-IPL models (BBL, PSL, etc.) unaffected — they use 25-feature models that ignore extra features
- v3 league calibrator (LogitBias) is NOT compatible with v6 — that's expected and correct

---

## Live Verification Checklist

Run these checks with a real CREX match URL during a live IPL game:

### 1. CLI Predictor
```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/ipl_v6 \
  --feature-store-dir data/ipl_feature_store_v3 \
  --league ipl \
  --output-json data/ipl_live_ml.json \
  --record-states
```

**Verify in output:**
- [ ] Model loads: `Loaded model: ensemble` with 32 features
- [ ] Calibrator loads: `n_phase_calibrators=6`, `feature_hash=af44ed1239a995f60695950e5739f04f`
- [ ] No `League calibrator not found` warning (expected — no league cal for v6)
- [ ] Venue resolves correctly
- [ ] Team stats load for both IPL teams
- [ ] Predictions are reasonable (0.1–0.9 range)
- [ ] In inn2: carryover features show non-default values in logs
- [ ] Match states recorded to `data/match_states/ipl/`

### 2. Launcher Script
```bash
python scripts/launcher.py --league IPL --match-url "CREX_MATCH_URL"
```

**Verify:**
- [ ] Picks up `models/ipl_v6` from LEAGUE_CONFIGS
- [ ] Predictions update as match progresses

### 3. Streamlit App
```bash
streamlit run src/bbl_pipeline/app/live_streamlit_app.py
```

**Verify:**
- [ ] "IPL ML+MC" config shows in dropdown
- [ ] Starts predictor with `models/ipl_v6`
- [ ] Dashboard shows win probability graph

### 4. Feature Verification (during inn2)
Check the recorded states parquet for non-default carryover values:
```python
import pandas as pd
df = pd.read_parquet("data/match_states/ipl/<match_id>.parquet")
inn2 = df[df.innings == 2]
# These should NOT be default values in inn2:
print(inn2[['inn1_wickets_lost', 'inn1_pp_runs', 'inn1_death_rr',
            'inn1_defendability', 'target_above_par', 'batting_won_toss',
            'venue_chase_success']].describe())
```

---

## Inn1 Ball-History Loss Bug & betx21 Fallback (2026-04-20)

### The Problem

During live inference, three inn1 carryover features (`inn1_pp_runs`, `inn1_death_rr`,
`inn1_wickets_lost`) depend on ball-by-ball data from the first innings. However:

1. **CREX API only provides current innings balls** — when inn2 starts, the `rb` (recent balls)
   field only contains the last ~6-8 inn2 balls, not the full inn1 history.
2. **Predictor restarts lose all state** — if the process is restarted mid-inn2,
   `balls_data` starts empty and inn1 data cannot be recovered from CREX.

**Impact measured on GT vs MI (2026-04-20):**

| Feature | Default | Actual (betx21) | Error |
|---------|:-------:|:----------------:|:-----:|
| `inn1_pp_runs` | 45.0 | **46.0** | +2% (negligible) |
| `inn1_death_rr` | 9.0 | **15.4** | **-72%** ⚠️ |
| `inn1_wickets_lost` | 5.0 | **5.0** | 0% (lucky) |

The death-over run rate was **72% wrong** with defaults — MI scored at 15.4 RPO in the death
but the model assumed 9.0 RPO. This significantly underestimates the total's quality and
the difficulty of the chase.

### Three-Tier Fallback Chain

```
crex_live_predictor._compute_inn1_carryover_stats()
│
├─ 1. Ball History (best)
│     Parse balls_data for innings==1 entries
│     ✅ Exact values from CREX ball-by-ball scrape
│     ❌ Only works if predictor ran continuously through inn1
│
├─ 2. Instance Cache (good)
│     _inn1_cached_stats dict, updated each poll during inn1
│     ✅ Survives innings break within same process
│     ❌ Lost on process restart
│
└─ 3. betx21 Production Download (fallback)
      SSH to prod server, download score progression, reconstruct
      ✅ Always available (betx21 records all IPL matches)
      ✅ Over-level granularity sufficient for PP/death stats
      ⚠️ Adds ~3-5s latency on first call (SSH + SCP)
      ⚠️ Requires SSH key (~/.ssh/id_server_wc)
```

### betx21 Data Architecture

The `betx21.live` project runs on production (`204.12.199.137`) and records all IPL match data:

```
/home/administrator/betx21.live/data/recordings/
└── YYYY-MM-DD/
    ├── {eventId}_odds.jsonl.gz      # Betting odds ticks
    ├── {eventId}_scores.jsonl.gz    # Ball-by-ball score updates
    └── {eventId}_sessions.jsonl.gz  # Session/fancy market data
```

**Score record format** (gzip JSONL):
```json
{
  "t": 1713626400000,
  "ev": 35503673,
  "t1": "Gujarat Titans",
  "s1": "199/5 (20.0)",
  "t2": "Mumbai Indians",
  "s2": "43/3 (5.1)",
  "b": ["0", "1", "4", "W", "0", "2"]
}
```

**Key details:**
- `s1`/`s2` are NOT batting order — `t1`/`t2` are fixed per match, detect who batted first by which score grows
- `b` field is "recent balls" (max ~8), NOT full ball history — useless for reconstruction
- Score ticks: ~170-320 per match, enough for over-level granularity
- Live recordings may have truncated gzip — handled with `EOFError` fallback

### Inn1 Stats Reconstruction

From betx21 score progression:
- **`inn1_pp_runs`**: Score at first tick where overs ≥ 6.0
- **`inn1_death_rr`**: `(final_runs - runs_at_over_16) / (final_overs - 16.0) * 6`
- **`inn1_wickets_lost`**: Wickets from final inn1 score string (e.g., "199/5" → 5)

### Team Matching (CREX → betx21)

CREX provides team names; betx21 uses numeric event IDs. Matching is done by:
1. SSH to list today's files: `ls /home/administrator/betx21.live/data/recordings/YYYY-MM-DD/`
2. Download each `_scores.jsonl.gz` candidate
3. Compare `t1`/`t2` names against CREX team names (case-insensitive substring match)

### Standalone Script

`scripts/fetch_betx21_inn1_stats.py` provides CLI access to betx21 data:

```bash
# List all matches for a date
python scripts/fetch_betx21_inn1_stats.py --list --date 2026-04-20

# Get inn1 stats for a specific match
python scripts/fetch_betx21_inn1_stats.py --match-id 35503673

# JSON output for programmatic use
python scripts/fetch_betx21_inn1_stats.py --match-id 35503673 --json

# Use already-downloaded file
python scripts/fetch_betx21_inn1_stats.py --local-file data/betx21_live/2026-04-20/35503673_scores.jsonl.gz
```

### SSH Configuration

```
Host: 204.12.199.137
User: administrator
Key:  ~/.ssh/id_server_wc
SSH:  "C:\Program Files\Git\usr\bin\ssh.exe"  (Windows)
SCP:  "C:\Program Files\Git\usr\bin\scp.exe"  (Windows)
```

### Files Changed

| Commit | File | Change |
|--------|------|--------|
| `6568bba` | `crex_live_predictor.py` | Toss abbreviation → full name resolution, carryover fields in all scraped_data |
| `7774034` | `crex_live_predictor.py` | Inn1 caching + betx21 fallback chain (~200 lines) |
| `7774034` | `scripts/fetch_betx21_inn1_stats.py` | Standalone betx21 data fetcher (354 lines) |
| `7774034` | `.gitignore` | Added `data/betx21_live/` |

---

## Live Verification Results (GT vs MI, 2026-04-20)

### Match Details
- **Gujarat Titans vs Mumbai Indians**, IPL 2026 Match 30
- **Venue:** Narendra Modi Stadium, Ahmedabad
- **MI batted first:** 199/5 (20.0 overs)
- **GT chasing:** 200 target
- **CREX URL:** `crex.com/cricket-live-score/gt-vs-mi-30th-match-indian-premier-league-2026-match-updates-118B`

### Verified Behaviors

| Check | Status | Notes |
|-------|:------:|-------|
| Model loads 32 features | ✅ | `Loaded model: ensemble` |
| Per-over isotonic calibrators | ✅ | 38 calibrators + 6 phase fallback |
| Venue resolves | ✅ | Narendra Modi Stadium |
| Team stats load | ✅ | Both GT and MI found in feature store |
| Inn1: defaults used (correct) | ✅ | inn1_pp_runs=45, inn1_death_rr=9.0 (constant during inn1) |
| Inn2: betx21 fallback triggered | ✅ | SSH download, team match by name |
| Inn2: real values populated | ✅ | pp_runs=46, death_rr=15.4, wickets=5 |
| Predictions reasonable | ✅ | GT 23.1% at 45/3 (5.4 ov) |
| Calibration chain active | ✅ | Raw → Phase → PerOver |
| JSON output updates | ✅ | `data/ipl_live_ml.json` every ~15s |
| Streamlit reads JSON | ✅ | Dashboard live at :8501 |

### Feature Values During Inn2 (at 45/3, 5.4 overs)

| Feature | Value | Source |
|---------|:-----:|--------|
| `venue_chase_success` | 0.40 | Feature store (venue stats) |
| `target_above_par` | 13.0 | 200 - 187 (venue avg) |
| `batting_won_toss` | 0.50 | Default (toss parse failed) |
| `inn1_wickets_lost` | 5.0 | **betx21 fallback** |
| `inn1_pp_runs` | 46.0 | **betx21 fallback** |
| `inn1_death_rr` | 15.4 | **betx21 fallback** |
| `inn1_defendability` | 0.6242 | Resource calculator |

### Known Issues

1. **`batting_won_toss = 0.5`** — Toss text not parsed from CREX info page.
   Regex pattern `r'([A-Z0-9\-]+)\s+opt\s+to\s+(Bat|Bowl)'` not matching page format
   during inn2. Low impact (~1.4% feature importance).

2. **No league calibrator** — `models/ipl_v6/league_calibrators/ipl/league_calibrator.pkl`
   not found. Expected — v6 is IPL-specific, no additional league calibration needed.

---

## Next Steps

1. **Collect more OOS data** — 12 matches with market is thin. Full IPL 2026 (~60 matches)
   will give much more reliable per-segment conclusions.

2. **Inn1 PP gap** — The only segment where v6 loses to market (+5.4%). Could benefit
   from stronger early-innings features (e.g., team depth indices, pre-match priors).

3. **Inn1 closing probability as chase prior** — Use the full model's calibrated prediction
   at inn1 end as a feature. Requires stacking/OOF approach to avoid leakage.

4. **Monitor v6 in production** — Compare live predictions against Betfair odds to validate
   OOS metrics hold on new data. Check for any venue/team coverage gaps in feature store.

5. **Fix toss parsing** — Debug CREX info page format to reliably extract toss winner.
   Consider adding betx21 toss data as an alternative source.

6. **Pre-fetch optimization** — Trigger betx21 download proactively on innings change
   detection instead of waiting for first inn2 poll. Would eliminate 3-5s latency.
