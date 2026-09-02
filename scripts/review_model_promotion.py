"""CLI for the deterministic seven-day market-vs-model review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bbl_pipeline.analysis.market_promotion import (
    build_promotion_review,
    load_recorded_states,
    write_promotion_review,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Review a candidate model against market and incumbent probabilities")
    parser.add_argument("--states-dir", default="data/match_states", help="Recorded per-ball state root")
    parser.add_argument("--candidate-id", required=True, help="Candidate model identifier")
    parser.add_argument("--window-start", required=True, help="ISO-8601 review start")
    parser.add_argument("--window-end", required=True, help="ISO-8601 review end")
    parser.add_argument("--output-dir", default="data/model_reviews", help="Review artifact directory")
    parser.add_argument("--candidate-manifest", default=None, help="Registered candidate_manifest.json")
    args = parser.parse_args()
    states = load_recorded_states(Path(args.states_dir))
    candidate_manifest = None
    if args.candidate_manifest:
        candidate_manifest = json.loads(Path(args.candidate_manifest).read_text(encoding="utf-8"))
    report = build_promotion_review(
        states,
        candidate_id=args.candidate_id,
        window_start=args.window_start,
        window_end=args.window_end,
        candidate_manifest=candidate_manifest,
    )
    paths = write_promotion_review(report, Path(args.output_dir))
    print(f"decision={report['decision']}")
    print(f"json={paths['json']}")
    print(f"markdown={paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
