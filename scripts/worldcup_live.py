#!/usr/bin/env python3
"""
T20 World Cup 2026 - Live Match Predictor Launch Script

Quick-start script for running live predictions on T20 World Cup matches using CREX.
Deploys the t20_international_male_v2 model with record-states enabled.

Three launch modes:
  1. ML + MC   (default):   XGBLogRegEnsemble + Monte Carlo  -> data/wc_live_ml.json
  2. MC-only   (--mc-only): Pure Monte Carlo simulation       -> data/wc_live_mc.json
  3. Both      (--both):    Launches ML+MC AND MC-only side-by-side in separate processes

Usage:
  # ML + MC mode (default)
  python scripts/worldcup_live.py <CREX_URL>

  # MC-only mode
  python scripts/worldcup_live.py <CREX_URL> --mc-only

  # BOTH modes simultaneously (recommended for comparison)
  python scripts/worldcup_live.py <CREX_URL> --both

Streamlit output files:
  ML+MC  -> data/wc_live_ml.json   (history: data/wc_prediction_history_ml.json)
  MC-only -> data/wc_live_mc.json  (history: data/wc_prediction_history_mc.json)

Examples:
  python scripts/worldcup_live.py "https://crex.com/scoreboard/YAA/1UY/2nd-Semi-Final/S/O/eng-vs-ind-2nd-semi-final-t20-world-cup-2026/info" --both
"""

import asyncio
import subprocess
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
OUTPUT_JSON_ML = str(ROOT / "data" / "wc_live_ml.json")
OUTPUT_JSON_MC = str(ROOT / "data" / "wc_live_mc.json")
POLL_INTERVAL = 2.0


def launch_both(args):
    """Launch ML+MC and MC-only as two separate processes side-by-side."""
    script = str(Path(__file__).resolve())
    base_cmd = [sys.executable, script, args.match_url]

    if args.venue:
        base_cmd += ["--venue", args.venue]
    if args.no_record:
        base_cmd += ["--no-record"]
    base_cmd += ["--poll-interval", str(args.poll_interval)]

    ml_cmd = base_cmd + ["--output-json", args.output_json_ml, "--states-dir", args.states_dir]
    mc_cmd = base_cmd + ["--mc-only", "--output-json", args.output_json_mc, "--states-dir", args.states_dir]

    print("=" * 60)
    print("  T20 WORLD CUP 2026 — DUAL LAUNCH")
    print("=" * 60)
    print(f"  ML+MC  output: {args.output_json_ml}")
    print(f"  MC-only output: {args.output_json_mc}")
    print(f"  States Dir:    {args.states_dir}")
    print(f"  Match URL:     {args.match_url}")
    print("=" * 60)
    print()
    print("  Starting ML+MC process...")
    ml_proc = subprocess.Popen(ml_cmd)
    print(f"    PID: {ml_proc.pid}")
    print()
    print("  Starting MC-only process...")
    mc_proc = subprocess.Popen(mc_cmd)
    print(f"    PID: {mc_proc.pid}")
    print()
    print("=" * 60)
    print("  BOTH RUNNING — Streamlit paths:")
    print(f"    ML+MC  : {args.output_json_ml}")
    print(f"    MC-only: {args.output_json_mc}")
    print("=" * 60)
    print()
    print("  Press Ctrl+C to stop both.")

    try:
        ml_proc.wait()
        mc_proc.wait()
    except KeyboardInterrupt:
        print("\n  Stopping both processes...")
        ml_proc.terminate()
        mc_proc.terminate()
        ml_proc.wait()
        mc_proc.wait()
        print("  Done.")


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
        "--both",
        action="store_true",
        default=False,
        help="Launch BOTH ML+MC and MC-only side-by-side (two processes)",
    )
    parser.add_argument(
        "--use-ml-model",
        action="store_true",
        default=False,
        help="Use ML model for MC terminal state evaluation (more accurate, ~50ms/2000 sims)",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Path for Streamlit JSON output (auto-set per mode if not specified)",
    )
    parser.add_argument(
        "--output-json-ml",
        default=OUTPUT_JSON_ML,
        help=f"ML+MC output JSON (used with --both, default: {OUTPUT_JSON_ML})",
    )
    parser.add_argument(
        "--output-json-mc",
        default=OUTPUT_JSON_MC,
        help=f"MC-only output JSON (used with --both, default: {OUTPUT_JSON_MC})",
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

    # ── Dual launch ─────────────────────────────────────────────────────
    if args.both:
        launch_both(args)
        return

    # ── Single mode ─────────────────────────────────────────────────────
    # Auto-pick output JSON based on mode if user didn't override
    if args.output_json is None:
        args.output_json = OUTPUT_JSON_MC if args.mc_only else OUTPUT_JSON_ML

    from bbl_pipeline.inference.crex_live_predictor import CrexLivePredictor

    mode_label = "MC-ONLY" if args.mc_only else "ML + MC"

    print("=" * 60)
    print("  T20 WORLD CUP 2026 — LIVE PREDICTOR")
    print("=" * 60)
    print(f"  Mode:          {mode_label}")
    if not args.mc_only:
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
