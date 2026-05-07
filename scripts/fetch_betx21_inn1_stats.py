#!/usr/bin/env python3
"""
Fetch inn1 stats from betx21 production recordings.

When the CREX live predictor loses inn1 ball history (e.g. mid-match restart),
this script downloads the score progression from betx21 production server
and reconstructs inn1 stats: pp_runs, death_rr, wickets_lost.

Usage:
    # Auto-detect match by team names
    python scripts/fetch_betx21_inn1_stats.py --match-id 35503673

    # Specify date if not today
    python scripts/fetch_betx21_inn1_stats.py --match-id 35503673 --date 2026-04-20

    # Use already-downloaded file
    python scripts/fetch_betx21_inn1_stats.py --local-file data/betx21_live/2026-04-20/35503673_scores.jsonl.gz

    # Output as JSON (for programmatic use)
    python scripts/fetch_betx21_inn1_stats.py --match-id 35503673 --json

    # List all matches for a date
    python scripts/fetch_betx21_inn1_stats.py --list --date 2026-04-20
"""

import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional


PROD_HOST = "administrator@204.12.199.137"
PROD_RECORDINGS = "/home/administrator/betx21.live/data/recordings"
SSH_EXE = r"C:\Program Files\Git\usr\bin\ssh.exe"
SCP_EXE = r"C:\Program Files\Git\usr\bin\scp.exe"
LOCAL_CACHE = Path("data/betx21_live")

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY_SEC = 2


def ssh_command(cmd: str, retries: int = MAX_RETRIES) -> Optional[str]:
    """Run a command on prod via SSH with retries."""
    for attempt in range(retries):
        try:
            result = subprocess.run(
                [SSH_EXE, PROD_HOST, cmd],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return result.stdout
            if attempt < retries - 1:
                import time
                time.sleep(RETRY_DELAY_SEC)
        except subprocess.TimeoutExpired:
            if attempt < retries - 1:
                import time
                time.sleep(RETRY_DELAY_SEC)
        except FileNotFoundError:
            print(f"ERROR: SSH not found at {SSH_EXE}", file=sys.stderr)
            return None
    return None


def scp_download(remote_path: str, local_path: str, retries: int = MAX_RETRIES) -> bool:
    """Download a file from prod via SCP with retries."""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    for attempt in range(retries):
        try:
            result = subprocess.run(
                [SCP_EXE, f"{PROD_HOST}:{remote_path}", local_path],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                return True
            if attempt < retries - 1:
                import time
                time.sleep(RETRY_DELAY_SEC)
        except subprocess.TimeoutExpired:
            if attempt < retries - 1:
                import time
                time.sleep(RETRY_DELAY_SEC)
        except FileNotFoundError:
            print(f"ERROR: SCP not found at {SCP_EXE}", file=sys.stderr)
            return False
    return False


def list_matches(date: str) -> list[dict]:
    """List all matches recorded on a given date."""
    cmd = f"""python3 << 'EOF'
import gzip, json, glob, os
date_dir = '{PROD_RECORDINGS}/{date}'
if not os.path.isdir(date_dir):
    print('[]')
else:
    results = []
    for f in sorted(glob.glob(date_dir + '/*_scores.jsonl.gz')):
        try:
            with gzip.open(f, 'rt') as fh:
                d = json.loads(fh.readline())
                eid = os.path.basename(f).split('_')[0]
                sz = os.path.getsize(f)
                results.append({{'id': eid, 't1': d['t1'], 't2': d['t2'], 'size': sz}})
        except:
            pass
    print(json.dumps(results))
EOF"""
    output = ssh_command(cmd)
    if output:
        try:
            return json.loads(output.strip())
        except json.JSONDecodeError:
            pass
    return []


def download_scores(match_id: str, date: str) -> Optional[Path]:
    """Download scores file from prod, return local path."""
    remote = f"{PROD_RECORDINGS}/{date}/{match_id}_scores.jsonl.gz"
    local = LOCAL_CACHE / date / f"{match_id}_scores.jsonl.gz"

    if local.exists():
        print(f"Using cached: {local}")
        return local

    print(f"Downloading {match_id}_scores.jsonl.gz from prod...")
    if scp_download(remote, str(local)):
        print(f"Saved to: {local}")
        return local
    else:
        print(f"FAILED to download scores for {match_id}", file=sys.stderr)
        return None


def parse_score(s: str):
    """Parse '199/5 (20.0)' -> (runs, wickets, overs)."""
    m = re.match(r"(\d+)/(\d+)\s*\(([\d.]+)\)", s.strip())
    if m:
        return int(m.group(1)), int(m.group(2)), float(m.group(3))
    return None


def load_scores(path: Path) -> list[dict]:
    """Load scores JSONL, handling truncated gzip (live recordings)."""
    lines = []
    try:
        with gzip.open(str(path), "rt") as f:
            for line in f:
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except EOFError:
        pass  # Truncated gzip from live recording — expected
    return lines


def detect_batting_order(lines: list[dict]) -> dict:
    """Detect which team batted first from score progression.

    Returns:
        {'batting_first': 't1'|'t2', 'batting_first_name': str, 'bowling_first_name': str}
    """
    if not lines:
        return {}

    t1_name = lines[0].get("t1", "")
    t2_name = lines[0].get("t2", "")

    # Find the first entry where a score progresses
    # If s1 grows first (while s2 is empty/zero), t1 batted first
    # If s2 grows first (while s1 is empty/zero), t2 batted first
    for d in lines[1:]:
        s1 = parse_score(d.get("s1", ""))
        s2 = parse_score(d.get("s2", ""))

        if s1 and s1[0] > 0 and (not s2 or s2[0] == 0):
            return {"batting_first": "t1", "batting_first_name": t1_name, "bowling_first_name": t2_name}
        if s2 and s2[0] > 0 and (not s1 or s1[0] == 0):
            return {"batting_first": "t2", "batting_first_name": t2_name, "bowling_first_name": t1_name}

    return {"batting_first": "unknown"}


def extract_inn1_stats(lines: list[dict]) -> dict:
    """Extract inn1 stats from betx21 score progression.

    Returns dict with:
        - inn1_pp_runs: runs scored in overs 0-6
        - inn1_death_rr: run rate in overs 16-20
        - inn1_wickets_lost: total wickets lost in inn1
        - inn1_total: total runs scored
        - batting_first: which team batted first
        - data_quality: 'full' | 'partial' | 'none'
    """
    if not lines:
        return {"data_quality": "none"}

    order = detect_batting_order(lines)
    bat_first = order.get("batting_first", "unknown")

    # Determine which score field has inn1 data
    score_field = "s1" if bat_first == "t1" else "s2"

    # Collect all score snapshots for the batting-first team
    snapshots = []
    for d in lines:
        p = parse_score(d.get(score_field, ""))
        if p:
            snapshots.append(p)

    if not snapshots:
        return {"data_quality": "none", **order}

    # Deduplicate by overs (keep last seen at each over)
    by_over = {}
    for runs, wkts, overs in snapshots:
        by_over[overs] = (runs, wkts, overs)

    sorted_overs = sorted(by_over.keys())

    # Find PP end (closest to over 6.0)
    pp_candidates = [(o, by_over[o]) for o in sorted_overs if o <= 6.0]
    pp_score = pp_candidates[-1][1] if pp_candidates else None

    # Find death phase boundaries (over 16-20)
    death_start_candidates = [(o, by_over[o]) for o in sorted_overs if 15.0 <= o <= 16.1]
    death_start = death_start_candidates[0][1] if death_start_candidates else None

    # Find inn1 final (max over <= 20.0 for T20)
    inn1_candidates = [(o, by_over[o]) for o in sorted_overs if o <= 20.0]
    final = inn1_candidates[-1][1] if inn1_candidates else None

    result = {**order}

    if pp_score:
        result["inn1_pp_runs"] = pp_score[0]
        result["pp_over"] = pp_score[2]
    if death_start and final:
        death_overs = final[2] - death_start[2]
        death_runs = final[0] - death_start[0]
        result["inn1_death_rr"] = round(death_runs / death_overs, 2) if death_overs > 0 else 0.0
        result["death_runs"] = death_runs
        result["death_overs"] = round(death_overs, 1)
    if final:
        result["inn1_total"] = final[0]
        result["inn1_wickets_lost"] = final[1]
        result["inn1_overs"] = final[2]

    # Data quality assessment
    max_over = max(sorted_overs)
    if max_over >= 19.5 and pp_score and death_start:
        result["data_quality"] = "full"
    elif max_over >= 10.0:
        result["data_quality"] = "partial"
    else:
        result["data_quality"] = "minimal"

    result["score_ticks"] = len(lines)
    result["unique_overs"] = len(sorted_overs)

    return result


def _parse_ball_value(val: str) -> tuple:
    """Parse a betx21 ball value to (runs, is_wicket, is_boundary).

    betx21 `b` array values:
      "0"-"9" → runs scored
      "4" / "Four" → 4-run boundary
      "6" / "Six"  → 6-run boundary
      "W" / "Wkt"  → wicket (0 runs)
      "Wd" / "Wide" / "Nb" / "NoBall" → extra (0, treat as dot for rolling stats)
      anything else → treat as 0 runs
    """
    val = str(val).strip()
    if val in ("W", "Wkt", "Out", "Wicket"):
        return 0, 1, 0
    if val in ("4", "Four"):
        return 4, 0, 1
    if val in ("6", "Six"):
        return 6, 0, 1
    if val in ("Wd", "Wide", "Nb", "NoBall", "NB", "LB", "Legbye"):
        return 0, 0, 0
    try:
        runs = int(val)
        return runs, 0, (1 if runs >= 4 else 0)
    except (ValueError, TypeError):
        return 0, 0, 0


def extract_ball_history(lines: list, innings_num: int = 1) -> list:
    """Reconstruct ball-by-ball history from betx21 score ticks.

    Each tick's `b` field is a list of ball outcomes for the current over.
    By keeping the last `b` array seen per over we reconstruct ball-by-ball data.

    Args:
        lines:      List of score tick dicts loaded from betx21 JSONL.
        innings_num: 1 = first innings, 2 = second innings.

    Returns:
        List of dicts compatible with _build_ball_history_for_mapper:
          {innings_num, over_number, ball_number, runs_scored,
           is_wicket, is_boundary, total_score, total_wickets}
    """
    if not lines:
        return []

    order = detect_batting_order(lines)
    bat_first = order.get("batting_first", "t1")

    # Which score field tracks this innings
    if innings_num == 1:
        score_field = "s1" if bat_first == "t1" else "s2"
    else:
        score_field = "s2" if bat_first == "t1" else "s1"

    # Collect (over_num, b_array) for each tick that has ball data
    over_balls: dict = {}  # over_num → last seen b array
    for tick in lines:
        score_str = tick.get(score_field, "")
        b_array = tick.get("b", [])
        if not score_str or not b_array:
            continue
        parsed = parse_score(score_str)
        if not parsed:
            continue
        _, _, overs = parsed
        over_num = int(overs)  # floor = current over being played
        over_balls[over_num] = list(b_array)

    # Reconstruct ball-by-ball
    history = []
    running_score = 0
    running_wickets = 0

    for over_num in sorted(over_balls.keys()):
        for ball_idx, ball_val in enumerate(over_balls[over_num]):
            runs, is_wicket, is_boundary = _parse_ball_value(ball_val)
            running_score += runs
            if is_wicket:
                running_wickets += 1
            history.append({
                'innings_num': innings_num,
                'over_number': over_num,
                'ball_number': ball_idx + 1,
                'runs_scored': runs,
                'is_wicket': is_wicket,
                'is_boundary': is_boundary,
                'total_score': running_score,
                'total_wickets': running_wickets,
            })

    return history


def auto_detect_match_id(date: str, batting_team: str, bowling_team: str) -> Optional[str]:
    """Find betx21 match ID by fuzzy-matching team names for a given date.

    Args:
        date:         Date string YYYY-MM-DD.
        batting_team: CREX batting team name (e.g. "Lucknow Super Giants").
        bowling_team: CREX bowling team name (e.g. "Royal Challengers Bengaluru").

    Returns:
        betx21 event ID string, or None if not found.
    """
    matches = list_matches(date)
    if not matches:
        return None

    def _token_overlap(crex_name: str, bx_name: str) -> int:
        crex_tokens = set(crex_name.lower().split())
        bx_tokens = set(bx_name.lower().split())
        return len(crex_tokens & bx_tokens)

    for m in matches:
        t1, t2 = m.get("t1", ""), m.get("t2", "")
        # Each CREX team should overlap at least 1 token with a betx21 team
        bat_match = max(_token_overlap(batting_team, t1), _token_overlap(batting_team, t2))
        bowl_match = max(_token_overlap(bowling_team, t1), _token_overlap(bowling_team, t2))
        if bat_match >= 1 and bowl_match >= 1:
            return m["id"]

    return None


def main():
    parser = argparse.ArgumentParser(description="Fetch inn1 stats from betx21 production")
    parser.add_argument("--match-id", help="betx21 event ID (e.g., 35503673)")
    parser.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"),
                        help="Match date (YYYY-MM-DD, default: today)")
    parser.add_argument("--local-file", help="Use already-downloaded scores file")
    parser.add_argument("--list", action="store_true", help="List matches for the given date")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--download-all", action="store_true",
                        help="Download all match types (odds, scores, sessions)")
    args = parser.parse_args()

    if args.list:
        matches = list_matches(args.date)
        if not matches:
            print(f"No matches found for {args.date}")
            return
        print(f"\nMatches on {args.date}:")
        print(f"{'ID':<12} {'Size':>8}  {'Teams'}")
        print("-" * 60)
        for m in matches:
            print(f"{m['id']:<12} {m['size']:>8,}  {m['t1']} vs {m['t2']}")
        return

    # Load scores
    if args.local_file:
        path = Path(args.local_file)
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            sys.exit(1)
    elif args.match_id:
        path = download_scores(args.match_id, args.date)
        if not path:
            sys.exit(1)

        if args.download_all:
            for suffix in ["odds", "sessions"]:
                remote = f"{PROD_RECORDINGS}/{args.date}/{args.match_id}_{suffix}.jsonl.gz"
                local = LOCAL_CACHE / args.date / f"{args.match_id}_{suffix}.jsonl.gz"
                if not local.exists():
                    scp_download(remote, str(local))
    else:
        parser.error("Specify --match-id or --local-file (or --list to browse)")
        return

    lines = load_scores(path)
    stats = extract_inn1_stats(lines)

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"INN1 STATS — {stats.get('batting_first_name', '?')} batting first")
        print(f"{'='*50}")
        print(f"  Data quality:     {stats.get('data_quality', 'unknown')}")
        print(f"  Score ticks:      {stats.get('score_ticks', 0)}")
        print(f"  Unique overs:     {stats.get('unique_overs', 0)}")
        print()
        if "inn1_total" in stats:
            print(f"  Inn1 total:       {stats['inn1_total']}/{stats['inn1_wickets_lost']} ({stats['inn1_overs']} ov)")
        if "inn1_pp_runs" in stats:
            print(f"  inn1_pp_runs:     {stats['inn1_pp_runs']}  (at over {stats['pp_over']})")
        if "inn1_death_rr" in stats:
            print(f"  inn1_death_rr:    {stats['inn1_death_rr']}  ({stats['death_runs']} runs in {stats['death_overs']} ov)")
        if "inn1_wickets_lost" in stats:
            print(f"  inn1_wickets_lost: {stats['inn1_wickets_lost']}")

        # Compare with defaults
        defaults = {"inn1_pp_runs": 45.0, "inn1_death_rr": 9.0, "inn1_wickets_lost": 5.0}
        print(f"\n  {'Feature':<22} {'Real':>8} {'Default':>8} {'Delta':>8}")
        print(f"  {'-'*48}")
        for feat, default in defaults.items():
            real = stats.get(feat)
            if real is not None:
                delta = real - default
                flag = " ⚠️" if abs(delta) > default * 0.3 else " ✅"
                print(f"  {feat:<22} {real:>8.1f} {default:>8.1f} {delta:>+8.1f}{flag}")


if __name__ == "__main__":
    main()
