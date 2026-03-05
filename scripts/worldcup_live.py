#!/usr/bin/env python3
"""
T20 World Cup 2026 - Live Match Predictor Launch Script

Quick-start script for running live predictions on T20 World Cup matches using CREX.
Deploys the t20_international_male_v2 model with record-states enabled.

Two modes:
  1. MC-only   (--mc-only): Monte Carlo simulation only, no ML model
  2. ML + MC   (default):   XGBLogRegEnsemble + Monte Carlo simulation

Usage:
  # ML + MC mode (default) — uses trained model + Monte Carlo
  python scripts/worldcup_live.py <CREX_URL>

  # MC-only mode — pure Monte Carlo simulation, no ML model
  python scripts/worldcup_live.py <CREX_URL> --mc-only

  # With ML model for MC terminal evaluation (slower but more accurate)
  python scripts/worldcup_live.py <CREX_URL> --use-ml-model

  # Custom output paths
  python scripts/worldcup_live.py <CREX_URL> --output-json data/wc_state.json

Examples:
  python scripts/worldcup_live.py "https://crex.com/scoreboard/YAA/1UY/2nd-Semi-Final/S/O/eng-vs-ind-2nd-semi-final-t20-world-cup-2026/info"
  python scripts/worldcup_live.py "https://crex.com/scoreboard/YAA/1UY/2nd-Semi-Final/S/O/eng-vs-ind-2nd-semi-final-t20-world-cup-2026/info" --mc-only
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# ── Defaults ────────────────────────────────────────────────────────────
MODEL_DIR = str(ROOT / "models" / "t20_international_male_v2")
FEATURE_STORE_DIR = str(ROOT / "data" / "t20_international_male_feature_store_v2")
LEAGUE = "t20i_male"
STATES_DIR = str(ROOT / "data" / "match_states" / "t20_wc_2026")
OUTPUT_JSON = str(ROOT / "data" / "live_state.json")
POLL_INTERVAL = 2.0


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="T20 World Cup 2026 — Live CREX Predictor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "match_url",
        help="CREX match URL (e.g. https://crex.com/scoreboard/...)",
    )
    parser.add_argument(
        "--mc-only",
        action="store_true",
        default=False,
        help="MC-only mode: skip ML model, use pure Monte Carlo simulation",
    )
    parser.add_argument(
        "--use-ml-model",
        action="store_true",
        default=False,
        help="Use ML model for MC terminal state evaluation (more accurate, ~50ms/2000 sims)",
    )
    parser.add_argument(
        "--output-json",
        default=OUTPUT_JSON,
        help=f"Path for Streamlit JSON output (default: {OUTPUT_JSON})",
    )
    parser.add_argument(
        "--states-dir",
        default=STATES_DIR,
        help=f"Directory for recorded match states (default: {STATES_DIR})",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=POLL_INTERVAL,
        help=f"Seconds between CREX polls (default: {POLL_INTERVAL})",
    )
    parser.add_argument(
        "--venue",
        default=None,
        help="Manually specify venue name (auto-detected from CREX if not set)",
    )
    parser.add_argument(
        "--no-record",
        action="store_true",
        default=False,
        help="Disable match state recording",
    )

    args = parser.parse_args()

    # Import the predictor
    from bbl_pipeline.inference.crex_live_predictor import CrexLivePredictor

    print("=" * 60)
    print("  T20 WORLD CUP 2026 — LIVE PREDICTOR")
    print("=" * 60)
    if args.mc_only:
        print(f"  Mode:          MC-ONLY (no ML model)")
    else:
        print(f"  Mode:          ML + MC")
        print(f"  Model:         {MODEL_DIR}")
        print(f"  Feature Store: {FEATURE_STORE_DIR}")
    print(f"  League:        {LEAGUE}")
    print(f"  Record States: {not args.no_record}")
    print(f"  States Dir:    {args.states_dir}")
    print(f"  Output JSON:   {args.output_json}")
    print(f"  Poll Interval: {args.poll_interval}s")
    print(f"  Match URL:     {args.match_url}")
    print("=" * 60)

    predictor = CrexLivePredictor(
        match_url=args.match_url,
        model_dir=MODEL_DIR,
        headless=True,
        feature_store_dir=FEATURE_STORE_DIR,
        output_json=args.output_json,
        league=LEAGUE,
        use_ml_model=args.use_ml_model,
        record_states=not args.no_record,
        states_dir=args.states_dir,
        venue=args.venue,
        mc_only=args.mc_only,
    )

    asyncio.run(predictor.run(poll_interval=args.poll_interval))


if __name__ == "__main__":
    main()
