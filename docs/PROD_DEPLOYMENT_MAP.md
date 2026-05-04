# Prod Deployment Map

This repo is the app and orchestration side of the production setup. The separate model repo supplies trained artifacts and inference assets that this repo points at with `--model-dir` and `--feature-store-dir`.

## Runtime topology

1. `app.crickzen.com` is fronted by Caddy.
2. Default traffic is reverse-proxied to `crickzen-dashboard:8000`.
3. `/telegram*` is reverse-proxied to host port `8502`.
4. The dashboard/predictor layer writes live state JSON files into `data/dashboard_states/`.
5. The Telegram signal runner watches `data/dashboard_states/` and posts lifecycle updates.

Evidence in this repo:

- [deploy/caddy/app.crickzen.com.telegram.caddy](/abs/path/C:/Users/ADMINS/Documents/projects/machine_learning_bbl_009-odi-mc-predictor-startupos-wt/deploy/caddy/app.crickzen.com.telegram.caddy)
- [scripts/start_ipl_signal_runner.sh](/abs/path/C:/Users/ADMINS/Documents/projects/machine_learning_bbl_009-odi-mc-predictor-startupos-wt/scripts/start_ipl_signal_runner.sh)
- [docs/TELEGRAM_SIGNAL_RUNNER_PROD.md](/abs/path/C:/Users/ADMINS/Documents/projects/machine_learning_bbl_009-odi-mc-predictor-startupos-wt/docs/TELEGRAM_SIGNAL_RUNNER_PROD.md)

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

## What to confirm on the server

The exact systemd, compose, or supervisor unit that starts `crickzen-dashboard` is not captured in this worktree. On prod, verify:

1. which service starts the dashboard container or process
2. which service writes `data/dashboard_states/`
3. where the model repo is mounted or copied from
4. whether current-match selection is based on newest file, explicit active URL, or an in-memory scheduler slot
