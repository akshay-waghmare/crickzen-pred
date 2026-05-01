#!/bin/bash
# Start the IPL Telegram signal runner on production.
#
# Usage:
#   ./scripts/start_ipl_signal_runner.sh            # continuous watch mode
#   ./scripts/start_ipl_signal_runner.sh --once     # scan once and exit (dry-run)
#
# Prerequisites:
#   1. .env configured at project root with TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
#   2. Dashboard predictor running (crickzen-dashboard container)
#   3. At least one JSON in data/dashboard_states/
#
# Approval workflow (run in a separate terminal):
#   python -m bbl_pipeline.telegram.signal_runner list --status pending
#   python -m bbl_pipeline.telegram.signal_runner approve <queue_id>
#   python -m bbl_pipeline.telegram.signal_runner reject <queue_id> --note "reason"

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

if [ ! -f ".env" ]; then
  echo "ERROR: .env not found at $REPO_DIR/.env"
  echo "Copy config/.env.example to .env and fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID"
  exit 1
fi

# Load .env into current shell so decouple picks it up
set -a
source .env
set +a

source venv/bin/activate 2>/dev/null || true

mkdir -p logs data

echo "[$(date -Iseconds)] Starting IPL signal runner — watching data/dashboard_states/"
echo "  Press Ctrl+C to stop."
echo ""

python -m bbl_pipeline.telegram.signal_runner watch \
  --source-dir data/dashboard_states \
  --interval-seconds 20 \
  "$@" \
  2>&1 | tee -a logs/signal_runner.log
