# Telegram Signal Runner on Prod

This documents the production Telegram signal flow that is currently working for
the IPL public channel.

## What is live

- Dashboard: `https://app.crickzen.com`
- Telegram operator UI: `https://app.crickzen.com/telegram/`
- Public channel posting: `@trueoddsML`
- Live state source: `data/dashboard_states/<match-hash>.json`

## Runtime pieces

### 1. Live predictor

The dashboard auto-scheduler starts the live predictor and writes match state to:

- `data/dashboard_states/<match-hash>.json`
- `data/dashboard_states/<match-hash>_history.json`
- `data/dashboard_states/<match-hash>_livematch.json`

The `<match-hash>` changes every live match.

### 2. Telegram signal runner

Start script:

- [scripts/start_ipl_signal_runner.sh](/abs/path/C:/Users/ADMINS/Documents/projects/machine_learning_bbl_009-odi-mc-predictor-startupos-wt/scripts/start_ipl_signal_runner.sh)

Current behavior:

- auto-discovers the active live state from `--source-dir data/dashboard_states`
- ignores stale feeds and completed matches when a fresher active match exists
- scans every 20 seconds
- logs heartbeat lines when no signal is due
- auto-approves by default except `final_review`, which stays queued for manual approval

Manual mode:

```bash
./scripts/start_ipl_signal_runner.sh --no-auto
```

One-shot scan:

```bash
./scripts/start_ipl_signal_runner.sh --once
```

### 3. Telegram operator UI

Start script:

- [scripts/start_ledger_ui.sh](/abs/path/C:/Users/ADMINS/Documents/projects/machine_learning_bbl_009-odi-mc-predictor-startupos-wt/scripts/start_ledger_ui.sh)

This serves the Streamlit operator UI on host port `8502` with base path
`/telegram`.

## Signal lifecycle

The lifecycle implemented in the runner is now:

1. `pre_match`
2. `toss`
3. `powerplay`
4. `mid_innings`
5. `death_overs`
6. `innings_break`
7. `chase_midpoint`
8. `final_review`

## Production Caddy route

The prod `/telegram` route currently proxied on `app.crickzen.com` is captured
in:

- [deploy/caddy/app.crickzen.com.telegram.caddy](/abs/path/C:/Users/ADMINS/Documents/projects/machine_learning_bbl_009-odi-mc-predictor-startupos-wt/deploy/caddy/app.crickzen.com.telegram.caddy)

That snippet mirrors the current production behavior:

- `/telegram*` -> `172.18.0.1:8502`
- all other traffic -> `crickzen-dashboard:8000`

## Required env

Root `.env` on prod must contain at least:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=@trueoddsML
PUBLIC_DASHBOARD_BASE_URL=https://app.crickzen.com
```

Optional but supported:

```env
TELEGRAM_STORAGE_PATH=data/telegram_predictions.jsonl
TELEGRAM_SIGNAL_TRACKER_PATH=data/telegram_signal_accuracy_tracker.csv
TELEGRAM_SIGNAL_QUEUE_PATH=data/telegram_signal_queue.json
TELEGRAM_SIGNAL_SOURCE_JSON=data/ipl_live_ml.json
```

Note: the production runner does not rely on a fixed `TELEGRAM_SIGNAL_SOURCE_JSON`
because it uses `--source-dir data/dashboard_states`.

## Files that hold operational history

- Signal post history: `data/telegram_predictions.jsonl`
- Review queue: `data/telegram_signal_queue.json`
- Accuracy tracker: `data/telegram_signal_accuracy_tracker.csv`
- Runner log: `logs/signal_runner.log`
- Ledger UI log: `logs/ledger_ui.log`

## Verified production result

For `Rajasthan Royals vs Delhi Capitals` on May 1, 2026:

- `innings_break` posted
- `chase_midpoint` posted
- `final_review` posted

The `final_review` Telegram message id was `7`.

## Remaining external cleanup

These items are still operational, not code-complete:

1. Commit the `/telegram` Caddy route to the infra repo that owns
   `/home/administrator/victoryline-monorepo/Caddyfile.prod`.
2. Push prod cherry-picks and prod-only dashboard runtime changes into the
   canonical git branches.
3. Rotate the Telegram bot token before real audience growth.
