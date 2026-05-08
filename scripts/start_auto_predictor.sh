#!/bin/bash
# Auto-start watchdog for the live predictor.
#
# Monitors data/dashboard_states/ and automatically starts the live predictor
# when no active match is running. By default auto-discovers live matches from
# https://crex.com/live-matches (no manual schedule editing needed).
#
# Usage:
#   ./scripts/start_auto_predictor.sh              # auto-discover from CREX (default)
#   ./scripts/start_auto_predictor.sh --dry-run    # preview without spawning
#   ./scripts/start_auto_predictor.sh --no-auto-discover  # use data/match_schedule.json only
#
# PM2 example (run once on server, stays alive across match days):
#   pm2 start scripts/start_auto_predictor.sh --name auto-predictor --interpreter bash

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

if [ ! -f "venv/bin/activate" ]; then
  echo "ERROR: virtualenv not found at $REPO_DIR/venv"
  exit 1
fi

source venv/bin/activate 2>/dev/null || true
mkdir -p logs data/dashboard_states

echo "[$(date -Iseconds)] Starting auto-predictor watchdog (CREX auto-discovery enabled)..."

export PYTHONUNBUFFERED=1
python -u -m src.bbl_pipeline.ops.prod_ops_agent auto-start \
  --source-dir data/dashboard_states \
  --schedule-file data/match_schedule.json \
  --interval-seconds 60 \
  --lookahead-minutes 30 \
  --lookback-hours 3 \
  "$@" \
  2>&1 | tee -a logs/auto_predictor.log
