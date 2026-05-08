# Prod Deployment Map

This repo is the app and orchestration side of the production setup. The separate model repo supplies trained artifacts and inference assets that this repo points at with `--model-dir` and `--feature-store-dir`.

## Runtime topology

1. `app.crickzen.com` is fronted by Caddy.
2. Default traffic is reverse-proxied to `crickzen-dashboard:8000`.
3. `/telegram*` is reverse-proxied to host port `8502`.
4. **Auto-start watchdog** (`pm2: auto-predictor`) queries the backend API and spawns
   `crex_live_predictor` automatically when a live match is detected.
5. The predictor writes live state JSON files into `data/dashboard_states/`.
6. The Streamlit dashboard picks the active state via `resolve_live_state_path`.
7. The Telegram signal runner watches `data/dashboard_states/` and posts lifecycle updates.

```
CREX scraper (port 5000)  ──→  Backend API (port 8099)
                                       │
                              auto-start watchdog (PM2)
                                       │ spawns
                              crex_live_predictor
                                       │ writes
                              data/dashboard_states/<match>.json
                                       │
                     Streamlit dashboard ←  Telegram signal runner
```

Evidence in this repo:

- [src/bbl_pipeline/ops/prod_ops_agent.py](../src/bbl_pipeline/ops/prod_ops_agent.py) — watchdog core
- [scripts/start_auto_predictor.sh](../scripts/start_auto_predictor.sh) — PM2 startup script
- [docs/AUTO_START_WATCHDOG.md](AUTO_START_WATCHDOG.md) — full watchdog guide
- [deploy/caddy/app.crickzen.com.telegram.caddy](../deploy/caddy/app.crickzen.com.telegram.caddy)
- [scripts/start_ipl_signal_runner.sh](../scripts/start_ipl_signal_runner.sh)
- [docs/TELEGRAM_SIGNAL_RUNNER_PROD.md](TELEGRAM_SIGNAL_RUNNER_PROD.md)

## Repo responsibilities

This repo owns:

- live match orchestration and launcher flows
- CREX scraping and live-state generation
- dashboard and Streamlit operator surfaces
- Telegram operator workflows
- prod-state auditing and operational runbooks

The model repo owns:

- trained model artifacts
- feature-store artifacts used for inference
- model retraining and evaluation changes

## Current production risk

If `data/dashboard_states/` keeps a recently touched file for a match that has already completed, anything that chooses the newest JSON can show a non-live match as the current one. That is the failure mode this repo now audits explicitly.

## Operational checks

Audit the current match selection logic:

```bash
python -m src.bbl_pipeline.ops.prod_ops_agent audit --source-dir data/dashboard_states
```

Continuously watch for stale or completed current matches:

```bash
python -m src.bbl_pipeline.ops.prod_ops_agent watch --source-dir data/dashboard_states --interval-seconds 30
```

Run the auto-start watchdog (normally managed by PM2):

```bash
python -m src.bbl_pipeline.ops.prod_ops_agent auto-start \
  --source-dir data/dashboard_states \
  --interval-seconds 60 \
  --auto-discover

# Check status
pm2 status
pm2 logs auto-predictor --lines 30

# Restart
pm2 restart auto-predictor
```

See [docs/AUTO_START_WATCHDOG.md](AUTO_START_WATCHDOG.md) for the full runbook.

## What to confirm on the server

The exact systemd, compose, or supervisor unit that starts `crickzen-dashboard` is not captured in this worktree. On prod, verify:

1. which service starts the dashboard container or process
2. which service writes `data/dashboard_states/`
3. where the model repo is mounted or copied from
4. whether current-match selection is based on newest file, explicit active URL, or an in-memory scheduler slot
