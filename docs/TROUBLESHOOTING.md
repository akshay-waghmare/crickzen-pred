# Troubleshooting Guide

Common issues and solutions for the Win Probability ML Pipeline.

---

## 1. Team/Venue Not Mapping in Live Predictor

### Symptoms
- Live predictor shows `Unknown` for venue
- Team names show as abbreviations (e.g., `DSG`) instead of full names
- Feature store returns default values (0.5 win rates)
- Logs show: `No stats found for team 'DSG'`

### Root Cause
When adding a new league (e.g., SA20), the inference pipeline needs:
1. **Team abbreviation mappings** in `src/bbl_pipeline/features/store.py`
2. **Venue extraction patterns** in `src/bbl_pipeline/inference/crex_live_predictor.py`
3. **Venue aliases** in `src/bbl_pipeline/features/store.py`

### Solution

#### Step 1: Add Team Abbreviations
Edit `src/bbl_pipeline/features/store.py` and add to `TEAM_ABBREVIATIONS`:

```python
TEAM_ABBREVIATIONS = {
    # SA20 teams
    "DSG": "Durban's Super Giants",
    "MICT": "MI Cape Town",
    "PR": "Paarl Royals",
    "JSK": "Joburg Super Kings",
    "PC": "Pretoria Capitals",
    "SEC": "Sunrisers Eastern Cape",
    # ... existing teams
}
```

#### Step 2: Add Venue Patterns
Edit `src/bbl_pipeline/inference/crex_live_predictor.py` and add venue regex patterns:

```python
venue_patterns = [
    # SA20 venues
    r"Kingsmead[,\s]+Durban",
    r"Newlands[,\s]+Cape\s*Town",
    r"Boland\s+Park[,\s]+Paarl",
    r"Wanderers[,\s]+Johannesburg",
    r"SuperSport\s+Park[,\s]+Centurion",
    r"St\s+George'?s?\s+Park[,\s]+Gqeberha",
    # ... existing patterns
]
```

#### Step 3: Add Venue Aliases
Edit `src/bbl_pipeline/features/store.py` and add to `VENUE_ALIASES`:

```python
VENUE_ALIASES = {
    # SA20 venues (scraped name → feature store name)
    "Kingsmead, Durban": "Kingsmead, Durban",
    "Newlands, Cape Town": "Newlands, Cape Town",
    # ... etc
}
```

---

## 2. Package Installed from Wrong Directory

### Symptoms
- Code changes not reflected when running inference
- Import errors or old behavior persists
- `pip show bbl_pipeline` shows wrong `Location` path

### Root Cause
The `bbl_pipeline` package was installed in editable mode (`pip install -e .`) from a different directory (e.g., `machine_learning` instead of `machine_learning_bbl`).

### Diagnosis
```powershell
pip show bbl_pipeline
```

Check the `Location` field - it should point to your current workspace:
```
Location: c:\users\admins\documents\projects\machine_learning_bbl\src
```

If it shows a different path (e.g., `machine_learning\src`), the package is stale.

### Solution
```powershell
# Uninstall the stale package
pip uninstall bbl_pipeline -y

# Reinstall from correct directory
cd C:\Users\ADMINS\Documents\projects\machine_learning_bbl
pip install -e .
```

---

## 3. Model/Feature Store Mismatch

### Symptoms
- Predictions look wrong or always return ~50%
- Warning: `Feature hash mismatch`
- KeyError for missing features

### Root Cause
The model was trained with a different feature store than what's being used for inference.

### Solution
Retrain the model with the current feature store:

```powershell
# 1. Ingest (if new data added)
bbl-pipeline ingest --input-dir data/sat_male_json --output-dir data/sat_raw

# 2. Process (regenerates feature store)
bbl-pipeline process --input-dir data/sat_raw/matches --output-dir data/sat_features_v1 --feature-store-dir data/sat_feature_store_v1

# 3. Train (creates new model)
bbl-pipeline train --input-file data/sat_features_v1/training.parquet --output-dir models/sat_v1

# 4. Calibrate (generates OOF calibrators)
bbl-pipeline generate-oof --input-file data/sat_features_v1/training.parquet --model-dir models/sat_v1
```

---

## 4. Full Pipeline Restart Required

### When to Restart the Full Pipeline

You **MUST** run the full pipeline (ingest → process → train → calibrate) when:

| Scenario | Ingest | Process | Train | Calibrate |
|----------|--------|---------|-------|-----------|
| New match JSON files added | ✅ | ✅ | ✅ | ✅ |
| Feature engineering code changed | ❌ | ✅ | ✅ | ✅ |
| Model architecture changed | ❌ | ❌ | ✅ | ✅ |
| Calibration method changed | ❌ | ❌ | ❌ | ✅ |
| Team/venue mappings updated (inference only) | ❌ | ❌ | ❌ | ❌ |

### You DON'T Need to Retrain When:
- Adding team abbreviation mappings (inference-only fix)
- Adding venue extraction patterns (inference-only fix)
- Adding venue aliases (inference-only fix)
- Fixing display/UI issues in Streamlit

These are **entity resolution** fixes that only affect how scraped data maps to existing feature store entries.

---

## 5. Quick Commands Reference

### SA20 Live Prediction
```powershell
python -m src.bbl_pipeline.inference.crex_live_predictor `
  --match-url "https://crex.com/scoreboard/.../live" `
  --model-dir models/sat_v1 `
  --feature-store-dir data/sat_feature_store_v1 `
  --output-json data/live_state.json
```

### BBL Live Prediction
```powershell
python -m src.bbl_pipeline.inference.crex_live_predictor `
  --match-url "https://crex.com/scoreboard/.../live" `
  --model-dir models/bbl_v8 `
  --feature-store-dir data/bbl_feature_store_v2 `
  --output-json data/live_state.json
```

### ILT20 Live Prediction
```powershell
python -m src.bbl_pipeline.inference.crex_live_predictor `
  --match-url "https://crex.com/scoreboard/.../live" `
  --model-dir models/ilt20_v4 `
  --feature-store-dir data/ilt_feature_store_v3 `
  --output-json data/live_state.json
```

---

## 6. Adding a New League Checklist

When adding support for a new league (e.g., BPL, NPL):

- [ ] Download Cricsheet JSON files to `data/<league>_json/`
- [ ] Run ingestion: `bbl-pipeline ingest --input-dir data/<league>_json --output-dir data/<league>_raw`
- [ ] Run processing: `bbl-pipeline process --input-dir data/<league>_raw/matches --output-dir data/<league>_features_v1 --feature-store-dir data/<league>_feature_store_v1`
- [ ] Train model: `bbl-pipeline train --input-file data/<league>_features_v1/training.parquet --output-dir models/<league>_v1`
- [ ] Calibrate: `bbl-pipeline generate-oof --input-file data/<league>_features_v1/training.parquet --model-dir models/<league>_v1`
- [ ] Add team abbreviations to `store.py` `TEAM_ABBREVIATIONS`
- [ ] Add venue patterns to `crex_live_predictor.py` `venue_patterns`
- [ ] Add venue aliases to `store.py` `VENUE_ALIASES`
- [ ] Update `models/model_registry.json`
- [ ] Test live prediction with a real match

---

## 7. Dashboard: Zombie Predictors Blocking New Matches

**Date:** 2026-05-16 | **Severity:** P1 — no live predictions served  
**Fixed in:** `dashboard/app/prediction_manager.py` commit `7852b8f`

### Symptoms

- `prediction.crickzen.com` shows today's match as "Awaiting model" or only shows old completed matches
- Dashboard container logs repeat: `Auto-start failed for <today's URL>: You can only run 2 matches at a time`
- `ps aux` on prod shows predictor processes with very high CPU (`40–45%`) running since days ago
- Public API `/api/public/matches` returns `score: "0/0"` for matches that were played days ago

### Root Cause

When a match ends, Crex's live score page transitions to a completed-match layout. The predictor process scrapes
the page but can no longer extract live ball data, so it writes `score=0, overs=0.0` to the state JSON
every ~5 seconds indefinitely.

The staleness check (`is_stale_running`) used file modification time (mtime) to decide if a prediction was
stuck. Because the zombie process kept writing fresh mtime stamps, the check **never fired**. Both 2-match
user slots were permanently consumed, and the auto-scheduler could not start today's match.

```
Match 58 MI vs PBKS  (played May 14) → PID 1548969 → writing score=0/overs=0 for 2+ days
Match 59 CSK vs LSG  (played May 15) → PID 2070055 → writing score=0/overs=0 for 1+ day
↳ both counted as "running" by PredictionManager
↳ auto-scheduler tried to start Match 60 KKR vs GT → "You can only run 2 matches at a time"
```

### Immediate Fix (emergency recovery)

1. Find the container-internal PIDs of the zombie predictors:

```bash
docker exec crickzen-dashboard sh -c "grep -rl crex_live /proc/*/cmdline 2>/dev/null"
# e.g. returns /proc/141755/cmdline  /proc/909/cmdline
```

2. Kill them via Python inside the container (no `kill` binary in slim image):

```bash
docker exec crickzen-dashboard python3 -c \
  "import os,signal; os.kill(141755, signal.SIGKILL); os.kill(909, signal.SIGKILL); print('Killed')"
```

3. The auto-scheduler detects the freed slots within 60 s and auto-starts today's match. Verify:

```bash
curl -s http://127.0.0.1:8000/api/public/matches | python3 -m json.tool
# should show today's match as "running" with a real score
```

### Permanent Fix

Added a **"stuck at zero score"** detector to `is_stale_running()` in
`dashboard/app/prediction_manager.py`:

```python
# If prediction has been running for >max(30, STALE_RUNNING_MATCH_MINUTES*3) minutes
# and score is still 0/0, Crex is no longer serving live data for this match.
zero_stuck_cutoff = timedelta(minutes=max(30, settings.STALE_RUNNING_MATCH_MINUTES * 3))
if now - self.created_at > zero_stuck_cutoff:
    state = self.read_state()
    if state is not None and _safe_int(state.get("score")) == 0 and _safe_float(state.get("overs")) == 0.0:
        logger.warning("Prediction %s stuck at 0/0 — marking stale", self.id)
        return True
```

With `STALE_RUNNING_MATCH_MINUTES=10` this triggers after **30 minutes** of zero-score output,
giving legitimate pre-match or delayed-start predictors enough warm-up time.

After applying the fix, rebuild and restart the container:

```bash
cd /home/administrator/projects/machine_learning_bbl
docker build -t crickzen-dashboard:latest -f dashboard/Dockerfile dashboard/
docker stop crickzen-dashboard && docker rm crickzen-dashboard
docker run -d --name crickzen-dashboard --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -v /home/administrator/projects/machine_learning_bbl/data:/app/data:rw \
  -v /home/administrator/projects/machine_learning_bbl/src:/app/src:ro \
  -v /home/administrator/projects/machine_learning_bbl/models:/app/models:ro \
  --env-file /home/administrator/projects/machine_learning_bbl/dashboard/.env \
  crickzen-dashboard:latest
```

### Why `kill` fails with "Operation not permitted"

Zombie predictor processes run as `root` inside the Docker container. SSH sessions run as `administrator`
(non-root), so `kill <PID>` from the SSH shell is rejected. Use `docker exec` with Python as shown above.
The container has no `kill` binary in `$PATH` (slim image), so `os.kill()` via Python is the workaround.

---

*Last updated: 2026-05-16*
