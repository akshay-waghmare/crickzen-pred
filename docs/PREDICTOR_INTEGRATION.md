# Predictor ↔ Dashboard Integration

This document explains how the live predictor writes match state and how the dashboard reads it.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TERMINAL 1                                  │
│                                                                     │
│  crex_live_predictor.py                                             │
│  ┌─────────────┐   scrapes   ┌──────────────┐   writes every ball  │
│  │  Crex.live  │ ──────────► │  Predictor   │ ──────────────────►  │
│  │  scoreboard │             │  (Python)    │   data/live_state.json│
│  └─────────────┘             └──────────────┘                       │
│                                    │                                │
│                            calibration chain:                       │
│                            Raw → Phase → PerOver → League           │
└────────────────────────────────────┬────────────────────────────────┘
                                     │
                              shared file on disk
                                     │
┌────────────────────────────────────▼────────────────────────────────┐
│                         TERMINAL 2                                  │
│                                                                     │
│  uvicorn dashboard (FastAPI)                                        │
│  ┌──────────────┐  polls every  ┌───────────────┐   SSE / JSON     │
│  │  live_state  │ ◄──────────── │  prediction/  │ ────────────────►│
│  │   .json      │   5 seconds   │  router.py    │   to browser     │
│  └──────────────┘               └───────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## `live_state.json` Format

The predictor writes (and overwrites) this file after every ball:

```json
{
  "match_id": "afg-vs-can-2026-t20wc",
  "timestamp": "2026-06-14T10:33:21Z",
  "status": "live",
  "innings": 1,
  "over": 17,
  "ball": 3,
  "batting_team": "Afghanistan",
  "bowling_team": "Canada",
  "score": 142,
  "wickets": 3,
  "target": null,
  "required_runs": null,
  "required_rr": null,
  "current_rr": 8.35,
  "batsman1": {"name": "Ibrahim Zadran", "runs": 68, "balls": 52},
  "batsman2": {"name": "Najibullah Zadran", "runs": 31, "balls": 19},
  "win_probability": {
    "batting_team": 70.8,
    "bowling_team": 29.2,
    "raw": 70.2,
    "phase_calibrated": 70.4,
    "per_over_calibrated": 70.8,
    "league_calibrated": 70.8,
    "calibration_label": "inn1_over17",
    "league": "t20i"
  },
  "model": {
    "name": "t20_male_v2",
    "version": "v2",
    "feature_store": "bbl_feature_store_v2"
  }
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `win_probability.batting_team` | float | Final calibrated probability (%) for batting team |
| `win_probability.bowling_team` | float | Complement of batting team |
| `win_probability.raw` | float | Uncalibrated XGBLogReg output |
| `win_probability.phase_calibrated` | float | After innings×phase isotonic |
| `win_probability.per_over_calibrated` | float | After per-over isotonic (38 calibrators) |
| `win_probability.league_calibrated` | float | After league temperature/Platt scaling |
| `win_probability.calibration_label` | string | Which calibrator was used (e.g. `inn2_over11`) |
| `status` | string | `live`, `completed`, `abandoned` |
| `target` | int \| null | Second innings target (null in first innings) |
| `required_runs` | int \| null | Runs still needed (second innings only) |

---

## Starting the Predictor

### Recommended (global model + league calibration)
```bash
.venv/bin/python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "https://crex.live/scoreboard/<match-slug>" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/bbl_feature_store_v2 \
  --league <LEAGUE> \
  --output-json data/live_state.json \
  --record-states
```

### League codes
| League | `--league` |
|--------|-----------|
| T20 Internationals | `t20i` |
| Big Bash League | `bbl` |
| SA20 | `sa20` |
| ILT20 | `ilt20` |
| NTQ / Super Smash | `ssm` |
| WPL | `wpl` |
| Women's Super Smash | `wssm` |

### Legacy league-specific models
```bash
# BBL v12
.venv/bin/python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "URL" \
  --model-dir models/bbl_v12 \
  --feature-store-dir data/bbl_feature_store_v2 \
  --output-json data/live_state.json

# SA20 v2
.venv/bin/python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "URL" \
  --model-dir models/sa20_v2 \
  --feature-store-dir data/bbl_feature_store_v2 \
  --output-json data/live_state.json
```

---

## Dashboard Polling Behaviour

- The dashboard backend polls `live_state.json` every **5 seconds** via a background task.
- Changes are pushed to connected browsers via **Server-Sent Events (SSE)** on `/prediction/stream`.
- If `live_state.json` does not exist or is stale (>60 s old), the dashboard shows a "Waiting for live data…" banner.
- If the predictor crashes, the last valid state remains visible; the banner appears after the stale timeout.

---

## Calibration Chain (Console Output)

The predictor prints the full chain every ball:

```
[CAL] Raw: 70.2% | Phase (inn1_death): 70.4% | PerOver (inn1_over17): 70.8%
      League (T20I): 70.8% → 70.8%
```

These four values correspond directly to the four fields in `win_probability`.

---

## Recording Match States

Pass `--record-states` to save a Parquet file with every ball's features + predictions:

```bash
.venv/bin/python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/bbl_feature_store_v2 \
  --league bbl \
  --output-json data/live_state.json \
  --record-states \
  --states-dir data/match_states/bbl_2026
```

Files are saved to `data/match_states/<league>/<match_id>.parquet`.  
Use `bbl-pipeline analyze-states --league bbl --calibration-report` to analyse.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `_fill_dtype` on startup | scikit-learn 1.8 | `.venv/bin/pip install scikit-learn==1.7.2` |
| Dashboard shows stale data | Predictor stopped | Restart predictor command |
| `503 Capacity` on Crex | Rate-limited | Wait 30 s, predictor retries automatically |
| `KeyError: 'league_calibrated'` | Old `live_state.json` from another run | Delete file; predictor rewrites on next ball |
| `FileNotFoundError: live_state.json` | Predictor hasn't written first ball yet | Wait for first ball, or check predictor logs |

---

## Related Docs

- [`dashboard/README.md`](../dashboard/README.md) — Dashboard local setup
- [`docs/DASHBOARD_DEPLOY.md`](DASHBOARD_DEPLOY.md) — Production deploy
- [`docs/LIVE_PREDICTION_README.md`](LIVE_PREDICTION_README.md) — Full predictor options
