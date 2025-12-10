#!/bin/bash
# Quick Launch Script for Live Match Prediction
# 
# Usage: ./start_live_prediction.sh "MATCH_URL"
# 
# Example:
#   ./start_live_prediction.sh "https://www.espncricinfo.com/series/big-bash-league-2024-25/..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "═══════════════════════════════════════════════════════════════"
echo "           🏏 BBL LIVE MATCH PREDICTOR LAUNCHER               "
echo "═══════════════════════════════════════════════════════════════"
echo -e "${NC}"

# Check if URL provided
if [ -z "$1" ]; then
    echo -e "${RED}❌ Error: No match URL provided${NC}"
    echo ""
    echo "Usage: ./start_live_prediction.sh \"MATCH_URL\""
    echo ""
    echo "Example:"
    echo "  ./start_live_prediction.sh \"https://www.espncricinfo.com/series/...\""
    echo ""
    exit 1
fi

MATCH_URL="$1"
MODEL_DIR="${2:-./models/champion}"
POLL_INTERVAL="${3:-2.0}"

echo -e "${GREEN}📝 Configuration:${NC}"
echo "   Match URL: $MATCH_URL"
echo "   Model Dir: $MODEL_DIR"
echo "   Poll Interval: ${POLL_INTERVAL}s"
echo ""

# Check if model directory exists
if [ ! -d "$MODEL_DIR" ]; then
    echo -e "${RED}❌ Error: Model directory not found: $MODEL_DIR${NC}"
    exit 1
fi

# Check if model file exists
if [ ! -f "$MODEL_DIR/champion_model.joblib" ]; then
    echo -e "${RED}❌ Error: Model file not found: $MODEL_DIR/champion_model.joblib${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Model found!${NC}"
echo ""

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Error: Python not found${NC}"
    exit 1
fi

echo -e "${GREEN}🚀 Starting live prediction...${NC}"
echo ""
echo -e "${BLUE}⌨️  Press Ctrl+C to stop and export results${NC}"
echo ""

# Run the predictor
python src/run_integrated_prediction.py \
    --match-url "$MATCH_URL" \
    --model-dir "$MODEL_DIR" \
    --poll-interval "$POLL_INTERVAL"

echo ""
echo -e "${GREEN}👋 Prediction session ended${NC}"
