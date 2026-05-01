#!/bin/bash
# Start the IPL Telegram signal runner on production (auto-approve mode).
#
# Usage:
#   ./scripts/start_ipl_signal_runner.sh              # auto-approve, continuous
#   ./scripts/start_ipl_signal_runner.sh --once       # scan once and exit (dry-run)
#   ./scripts/start_ipl_signal_runner.sh --no-auto    # manual approval via UI
#
# Prerequisites:
#   1. .env configured at project root with TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
#   2. Dashboard predictor running (crickzen-dashboard container)
#   3. At least one JSON in data/dashboard_states/

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

if [ ! -f ".env" ]; then
  echo "ERROR: .env not found at $REPO_DIR/.env"
  exit 1
fi

set -a; source .env; set +a
source venv/bin/activate 2>/dev/null || true
mkdir -p logs data

# Allow --no-auto to disable auto-approve for manual review
AUTO_FLAG="--auto-approve"
EXTRA_ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--no-auto" ]; then
    AUTO_FLAG=""
  else
    EXTRA_ARGS+=("$arg")
  fi
done

echo "[$(date -Iseconds)] Starting IPL signal runner — auto_approve=$([ -n "$AUTO_FLAG" ] && echo yes || echo no)"

export PYTHONUNBUFFERED=1
python -u -m src.bbl_pipeline.telegram.signal_runner watch \
  --source-dir data/dashboard_states \
  --interval-seconds 20 \
  $AUTO_FLAG \
  "${EXTRA_ARGS[@]}" \
  2>&1 | tee -a logs/signal_runner.log
