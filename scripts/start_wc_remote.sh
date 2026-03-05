#!/bin/bash
# T20 World Cup 2026 - Start both predictors on remote server
set -e

cd ~/projects/machine_learning_bbl
source venv/bin/activate

MATCH_URL="https://crex.com/scoreboard/YAA/1UY/2nd-Semi-Final/S/O/eng-vs-ind-2nd-semi-final-t20-world-cup-2026/info"

mkdir -p data/match_states/t20_wc_2026 logs

echo "Starting ML+MC predictor..."
nohup python scripts/worldcup_live.py "$MATCH_URL" \
  --output-json data/wc_live_ml.json \
  --states-dir data/match_states/t20_wc_2026 \
  > logs/wc_ml.log 2>&1 &
ML_PID=$!
echo "ML+MC PID: $ML_PID"

sleep 2

echo "Starting MC-only predictor..."
nohup python scripts/worldcup_live.py "$MATCH_URL" \
  --mc-only \
  --output-json data/wc_live_mc.json \
  --states-dir data/match_states/t20_wc_2026 \
  > logs/wc_mc.log 2>&1 &
MC_PID=$!
echo "MC-only PID: $MC_PID"

sleep 2

echo "Starting Streamlit app..."
nohup streamlit run src/bbl_pipeline/app/live_streamlit_app.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --browser.gatherUsageStats false \
  > logs/streamlit.log 2>&1 &
ST_PID=$!
echo "Streamlit PID: $ST_PID"

echo ""
echo "=== ALL STARTED ==="
echo "ML+MC     -> data/wc_live_ml.json (log: logs/wc_ml.log)   PID: $ML_PID"
echo "MC-only   -> data/wc_live_mc.json (log: logs/wc_mc.log)   PID: $MC_PID"
echo "Streamlit -> http://$(hostname -I | awk '{print $1}'):8501  PID: $ST_PID"
echo ""
echo "In Streamlit, set JSON path to:"
echo "  ML+MC:   data/wc_live_ml.json"
echo "  MC-only: data/wc_live_mc.json"
echo ""
echo "Check logs:      tail -f logs/wc_ml.log logs/wc_mc.log logs/streamlit.log"
echo "Check processes: ps aux | grep -E 'worldcup_live|streamlit'"
echo "Stop all:        kill $ML_PID $MC_PID $ST_PID"
