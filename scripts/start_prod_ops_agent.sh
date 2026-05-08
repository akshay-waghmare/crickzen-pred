#!/bin/bash
# Watch dashboard state files and flag stale/completed current matches.

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

export PYTHONUNBUFFERED=1
python -u -m src.bbl_pipeline.ops.prod_ops_agent watch \
  --source-dir data/dashboard_states \
  --interval-seconds 30 \
  "$@"
