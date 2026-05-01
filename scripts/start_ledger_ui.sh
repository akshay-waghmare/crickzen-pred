#!/bin/bash
# Run the Telegram operator ledger UI on prod (port 8502).
#
# Access from your machine via SSH tunnel:
#   ssh -L 8502:localhost:8502 prod
#   Open: http://localhost:8502
#
# Or expose permanently through Caddy by adding a route to Caddyfile.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

if [ ! -f ".env" ]; then
  echo "ERROR: .env not found — run scripts/start_ipl_signal_runner.sh setup first"
  exit 1
fi

set -a; source .env; set +a
source venv/bin/activate 2>/dev/null || true

mkdir -p logs

echo "[$(date -Iseconds)] Starting Telegram Ledger UI on http://localhost:8502"
echo "  SSH tunnel:  ssh -L 8502:localhost:8502 $(hostname)"
echo ""

streamlit run src/bbl_pipeline/app/telegram_ledger_app.py \
  --server.port 8502 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.baseUrlPath telegram \
  --browser.gatherUsageStats false \
  2>&1 | tee -a logs/ledger_ui.log
