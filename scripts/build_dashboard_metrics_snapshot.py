#!/usr/bin/env python
"""
Rebuild dashboard metrics snapshot artifacts for one or more leagues/windows.

Usage:
    python scripts/build_dashboard_metrics_snapshot.py --league ipl --window all_available
    python scripts/build_dashboard_metrics_snapshot.py --league ipl --window last_7_days
    python scripts/build_dashboard_metrics_snapshot.py --league ipl --window all
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.bbl_pipeline.analysis.proof_metrics import (
    build_unified_snapshot,
    DEFAULT_WINDOWS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path("data")
MATCH_STATES_DIR = DATA_DIR / "match_states"
DASHBOARD_METRICS_DIR = DATA_DIR / "dashboard_metrics"

CONSOLIDATED_CANDIDATES = [
    "all_matches.parquet",
    "cricket-live-score.parquet",
]

SPECIAL_FILES = {
    "match_metadata.parquet",
    "all_matches.parquet",
    "volatility_profiles.parquet",
    "signal_events.parquet",
}


def find_states_file(league: str) -> Path | None:
    """Return the best consolidated match-state file for a league.

    Priority order:
    1. all_matches.parquet (StateAnalyzer consolidation output)
    2. cricket-live-score.parquet (pipeline consolidated file)
    3. Any other non-special .parquet file
    """
    league_dir = MATCH_STATES_DIR / league.lower()
    if not league_dir.exists():
        return None

    candidates = list(league_dir.glob("*.parquet"))
    if not candidates:
        return None

    for preferred in CONSOLIDATED_CANDIDATES:
        path = league_dir / preferred
        if path.exists():
            return path

    for candidate in candidates:
        if candidate.name not in SPECIAL_FILES:
            return candidate
    return None


def find_metadata_file(league: str) -> Path | None:
    league_dir = MATCH_STATES_DIR / league.lower()
    metadata_path = league_dir / "match_metadata.parquet"
    return metadata_path if metadata_path.exists() else None


def main():
    parser = argparse.ArgumentParser(description="Build dashboard metrics snapshot artifacts")
    parser.add_argument("--league", type=str, default="ipl", help="League identifier")
    parser.add_argument("--window", type=str, default="all_available", help="Evaluation window")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for artifacts")
    args = parser.parse_args()

    league = args.league.lower()
    window = args.window
    output_dir = Path(args.output_dir) if args.output_dir else DASHBOARD_METRICS_DIR

    if window == "all":
        windows = DEFAULT_WINDOWS
    else:
        windows = [window]

    states_path = find_states_file(league)
    if states_path is None:
        log.error("No match state files found for league '%s' in %s", league, MATCH_STATES_DIR / league)
        sys.exit(1)

    metadata_path = find_metadata_file(league)
    if metadata_path is None:
        log.warning("No match metadata file found for league '%s', proceeding without winner data", league)

    log.info("States file: %s", states_path)
    log.info("Metadata file: %s", metadata_path)
    log.info("Output directory: %s", output_dir)

    from src.bbl_pipeline.analysis.proof_metrics import _derive_accuracy_from_states

    for w in windows:
        log.info("Building snapshot for league=%s window=%s ...", league, w)
        accuracy_rows = _derive_accuracy_from_states(states_path, metadata_path or Path("nonexistent"), league, w)
        result = build_unified_snapshot(
            states_path=states_path,
            metadata_path=metadata_path or Path("nonexistent"),
            league=league,
            window=w,
            accuracy_rows=accuracy_rows,
            output_dir=output_dir,
        )
        status = result.get("summary", {}).get("status", "unknown")
        prob = result.get("summary", {}).get("probability_metrics", {})
        acc = result.get("summary", {}).get("accuracy_metrics", {})
        ledger = result.get("ledger", [])
        log.info(
            "  status=%s  brier=%s  ece=%s  prob_samples=%s  acc_samples=%s  ledger_rows=%s",
            status,
            prob.get("brier"),
            prob.get("ece"),
            prob.get("sample_count"),
            acc.get("sample_count") if acc else 0,
            len(ledger),
        )

    log.info("Snapshot build complete. Artifacts in %s", output_dir)


if __name__ == "__main__":
    main()
