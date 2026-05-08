# Auto-Start Watchdog for Live Predictions

## Problem

The live prediction dashboard used to show stale match data every day because the
`crex_live_predictor` process had to be started manually.  Nobody was doing that
consistently, so predictions were missing and the dashboard showed an old, completed match.

## Solution

A watchdog (`prod_ops_agent auto-start`) runs continuously, detects when no active
predictor is running, discovers the current live match, and spawns `crex_live_predictor`
automatically.

## Architecture

```
CREX scraper (port 5000)
  │  /scrape-live-matches-link  ← watchdog pings this to trigger fresh discovery
  │  writes to ↓
Backend API (port 8099)
  │  /cricket-data/live-matches  ← watchdog reads live match URLs from here
  │
  ▼
auto-start watchdog
  │  spawns
  ▼
crex_live_predictor  →  data/dashboard_states/<match_id>.json
                                │
                                ▼
                    Streamlit dashboard (resolves active state automatically)
```

### Discovery chain

1. **Local backend API** (`http://127.0.0.1:8099/cricket-data/live-matches`)
   — fast, no browser needed, already populated by the running scraper.
2. **Playwright scrape** of `https://crex.com/live-matches`
   — fallback if backend is empty (requires browser; may fail behind auth wall).
3. **Schedule file** (`data/match_schedule.json`)
   — manual fallback; pre-enter match URLs here when auto-discovery can't find the match.

> **Why the scraper, not direct CREX?**  
> `crex.com/live-matches` requires a logged-in session.  The scraper already handles
> that auth internally and posts URLs to the backend.  Querying the backend avoids any
> auth wall.

## Deployment

### First time on prod

```bash
# Pull latest code
git pull origin startupos/safe-match-gen-20260411

# Start the watchdog with PM2
pm2 start scripts/start_auto_predictor.sh --name auto-predictor --interpreter bash
pm2 save
```

### Restart after code change

```bash
git pull origin startupos/safe-match-gen-20260411
pm2 restart auto-predictor
```

### Check logs

```bash
pm2 logs auto-predictor --lines 50
```

## Configuration

The `start_auto_predictor.sh` script sets these defaults:

| Flag | Default | Description |
|------|---------|-------------|
| `--interval-seconds` | 60 | How often the watchdog polls for active predictors |
| `--auto-discover` | on | Query backend API + Playwright to find live matches |
| `--source-dir` | `data/dashboard_states` | Where predictor JSON files are written |
| `--schedule-file` | `data/match_schedule.json` | Fallback schedule for manual URL entry |

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://127.0.0.1:8099` | Local backend API base URL |
| `SCRAPER_URL` | `http://127.0.0.1:5000` | CREX scraper service base URL |

## Manual fallback — schedule file

If auto-discovery is not finding the match (e.g. the backend is empty during a cold start),
add the match manually:

```json
[
  {
    "match_id": "rcb-vs-mi-match-50-ipl-2026",
    "url": "https://crex.com/scoreboard/XXX/rcb-vs-mi-match-50-indian-premier-league-2026/live",
    "league": "ipl",
    "enabled": true,
    "record_states": true
  }
]
```

Save to `data/match_schedule.json`.  The watchdog picks it up on the next poll cycle.

## Dashboard — match status display

`crex_live_predictor` now writes a `match_status` field to the state JSON.  The
dashboard reads this and shows a human-readable badge instead of just "STALE" or "LIVE":

| `match_status` | Badge |
|----------------|-------|
| `live` | 🔴 LIVE |
| `interrupted` | ⏸️ INTERRUPTED |
| `innings_break` | ♔ INNINGS BREAK |
| `delayed` | 🌧️ DELAYED |
| `toss` | 🪙 TOSS DONE |
| `scheduled` | ⏳ NOT STARTED |
| `completed` | ✅ RESULT |

When `prediction_available` is `false`, the dashboard shows a friendly message
(`prediction_status_reason`) instead of an empty chart.

## Key files

| File | Purpose |
|------|---------|
| `src/bbl_pipeline/ops/prod_ops_agent.py` | Core watchdog: `auto-start`, `audit`, `watch` subcommands |
| `src/bbl_pipeline/app/live_state_discovery.py` | `resolve_live_state_path` — picks active state JSON for dashboard |
| `scripts/start_auto_predictor.sh` | PM2 startup script |
| `data/match_schedule.json` | Manual match URL fallback |

## Operational runbook

### No predictions after deploy

1. Check PM2: `pm2 status` — is `auto-predictor` running?
2. Check logs: `pm2 logs auto-predictor --lines 30`
3. Check backend: `curl http://127.0.0.1:8099/cricket-data/live-matches`
4. Check scraper: `curl http://127.0.0.1:5000/health`
5. If backend empty: add the match URL manually to `data/match_schedule.json`

### Predictor started but dashboard still stale

1. Check `data/dashboard_states/` — is there a recently updated `.json` file?
2. Check the dashboard "Source" selector — it should be on "Auto current match".
3. Check `choose_active_state_json` logic in `live_state_discovery.py`.

### Duplicate predictors

The watchdog keeps an in-memory process registry.  If the watchdog is restarted, it
re-checks `data/dashboard_states/` for a fresh file before spawning a new predictor
(file age < 5 minutes means the predictor is probably already running).
