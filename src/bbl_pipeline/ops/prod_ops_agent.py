"""Audit live predictor state and prod deployment wiring."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

DEFAULT_STALE_AFTER_SECONDS = 120
DEFAULT_COMPLETED_GRACE_SECONDS = 600

# How far before/after a scheduled start_time to consider a match eligible for auto-start.
AUTO_START_LOOKAHEAD_MINUTES = 30   # start predictor up to 30 min before match
AUTO_START_LOOKBACK_HOURS = 3       # start predictor up to 3 hrs after scheduled start (match is live)

# Predictor config per league — mirrors scripts/launcher.py LEAGUE_CONFIGS.
_LEAGUE_PREDICTOR_CONFIGS: dict[str, dict[str, str]] = {
    "ipl": {
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/ipl_feature_store_v1",
        "states_dir": "data/match_states/ipl",
    },
    "psl": {
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/psl_feature_store_v1",
        "states_dir": "data/match_states/psl",
    },
    "bbl": {
        "model_dir": "models/bbl_v12",
        "feature_store_dir": "data/bbl_feature_store_v2",
        "states_dir": "data/match_states/bbl",
    },
    "sa20": {
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
        "states_dir": "data/match_states/sa20",
    },
    "ilt20": {
        "model_dir": "models/ilt20_v5",
        "feature_store_dir": "data/ilt_feature_store_v3",
        "states_dir": "data/match_states/ilt20",
    },
    "wpl": {
        "model_dir": "models/wpl_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
        "states_dir": "data/match_states/wpl",
    },
    "t20i_male": {
        "model_dir": "models/t20_international_male_v2",
        "feature_store_dir": "data/t20_international_male_feature_store_v2",
        "states_dir": "data/match_states/t20i",
    },
    "ssm": {
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
        "states_dir": "data/match_states/ssm",
    },
    "bpl": {
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
        "states_dir": "data/match_states/bpl",
    },
}

# CREX URL slug → league code (same patterns as scripts/launcher.py)
_URL_LEAGUE_PATTERNS: list[tuple[str, str]] = [
    (r"indian-premier-league", "ipl"),
    (r"pakistan-super-league", "psl"),
    (r"big-bash-league", "bbl"),
    (r"betway-sa20|sa20-league|sa20", "sa20"),
    (r"international-league-t20|ilt20", "ilt20"),
    (r"womens-premier-league|wpl", "wpl"),
    (r"t20-world-cup|icc-mens-t20", "t20i_male"),
    (r"super-smash", "ssm"),
    (r"bangladesh-premier-league|bpl", "bpl"),
]

CREX_LIVE_MATCHES_URL = "https://crex.com/live-matches"


def _detect_league_from_url(url: str) -> str | None:
    """Return the league code if the CREX URL matches a known league pattern."""
    url_lower = url.lower()
    for pattern, league in _URL_LEAGUE_PATTERNS:
        if re.search(pattern, url_lower):
            return league
    return None


def _match_id_from_url(url: str) -> str:
    """Derive a stable match_id from a CREX scoreboard URL."""
    # e.g. .../rcb-vs-mi-match-45-indian-premier-league-2026/live -> rcb-vs-mi-match-45-...
    parts = [p for p in url.rstrip("/").split("/") if p]
    for i, part in enumerate(reversed(parts)):
        if re.search(r"[a-z]+-vs-[a-z]+", part, re.IGNORECASE):
            return part
    # Fallback: use the last meaningful path segment
    for part in reversed(parts):
        if len(part) > 5 and part not in ("live", "info", "scorecard"):
            return part
    return parts[-1] if parts else "unknown"


async def _discover_crex_live_matches() -> list[dict[str, str]]:
    """
    Fetch live match URLs from https://crex.com/live-matches using Playwright.
    Returns list of dicts with keys: url, match_id, league (only supported leagues).
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[auto-start] WARNING: playwright not installed, CREX discovery unavailable.", flush=True)
        return []

    results: list[dict[str, str]] = []
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(CREX_LIVE_MATCHES_URL, timeout=30000)
                try:
                    await page.wait_for_selector("li.live-card, div.live-card", timeout=15000)
                except Exception:
                    pass  # Page may have loaded without the selector becoming visible
                hrefs = await page.evaluate("""() => {
                    const seen = new Set();
                    const out = [];
                    document.querySelectorAll('li.live-card a, div.live-card a').forEach(a => {
                        const h = a.getAttribute('href');
                        if (h && h.includes('/scoreboard/') && !seen.has(h)) {
                            seen.add(h);
                            out.push(h);
                        }
                    });
                    return out;
                }""")
            finally:
                await browser.close()
    except Exception as exc:
        print(f"[auto-start] WARNING: CREX discovery failed: {exc}", flush=True)
        return []

    for href in hrefs:
        url = f"https://crex.com{href}" if not href.startswith("http") else href
        league = _detect_league_from_url(url)
        if league is None:
            continue  # skip unknown leagues
        results.append({
            "url": url,
            "match_id": _match_id_from_url(url),
            "league": league,
            "record_states": "true",
            "enabled": "true",
        })

    return results


class LiveStateError(Exception):
    """Raised when live predictor state cannot be loaded or interpreted."""


@dataclass
class MatchAudit:
    """Summary of one live-state JSON file."""

    json_path: str
    match_id: str
    match: str | None
    timestamp: str | None
    age_seconds: int | None
    batting_team: str | None
    bowling_team: str | None
    score: str | None
    overs: str | None
    target: int | None
    is_second_innings: bool
    has_result: bool
    stale: bool
    status: str
    reasons: list[str]


@dataclass
class DirectoryAudit:
    """Directory-level audit used by the prod ops workflow."""

    source_dir: str
    scanned_at: str
    total_files: int
    current_candidate: MatchAudit | None
    recommended_candidate: MatchAudit | None
    needs_attention: bool
    reasons: list[str]
    audits: list[MatchAudit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit dashboard state files and detect stale or completed current matches.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit", help="Inspect a dashboard state directory once.")
    _add_common_dir_args(audit_parser)
    audit_parser.add_argument("--json", action="store_true", help="Emit JSON only.")

    watch_parser = subparsers.add_parser("watch", help="Continuously audit a dashboard state directory.")
    _add_common_dir_args(watch_parser)
    watch_parser.add_argument("--interval-seconds", type=float, default=30.0, help="Polling interval.")
    watch_parser.add_argument("--once", action="store_true", help="Run one watch iteration and exit.")

    auto_start_parser = subparsers.add_parser(
        "auto-start",
        help="Watchdog: auto-start the predictor when no active match is detected.",
    )
    _add_common_dir_args(auto_start_parser)
    auto_start_parser.add_argument(
        "--schedule-file",
        default="data/match_schedule.json",
        help="JSON file listing upcoming matches (url, league, start_time, match_id).",
    )
    auto_start_parser.add_argument(
        "--interval-seconds", type=float, default=30.0, help="Polling interval."
    )
    auto_start_parser.add_argument(
        "--lookahead-minutes",
        type=int,
        default=AUTO_START_LOOKAHEAD_MINUTES,
        help="Start predictor this many minutes before scheduled start_time.",
    )
    auto_start_parser.add_argument(
        "--lookback-hours",
        type=int,
        default=AUTO_START_LOOKBACK_HOURS,
        help="Start predictor up to this many hours after scheduled start_time (match still live).",
    )
    auto_start_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be started without actually spawning predictors.",
    )
    auto_start_parser.add_argument(
        "--auto-discover",
        action="store_true",
        default=True,
        help="Auto-discover live matches from crex.com/live-matches (default: on). "
             "Falls back to --schedule-file when no supported leagues found on CREX.",
    )
    auto_start_parser.add_argument(
        "--no-auto-discover",
        dest="auto_discover",
        action="store_false",
        help="Disable CREX auto-discovery. Use schedule file only.",
    )

    args = parser.parse_args(argv)

    if args.command == "audit":
        report = audit_state_directory(
            Path(args.source_dir),
            stale_after_seconds=args.stale_after_seconds,
            completed_grace_seconds=args.completed_grace_seconds,
        )
        if args.json:
            print(json.dumps(asdict(report), indent=2))
        else:
            print(render_directory_audit(report))
        return 0 if not report.needs_attention else 2

    if args.command == "watch":
        exit_code = 0
        while True:
            report = audit_state_directory(
                Path(args.source_dir),
                stale_after_seconds=args.stale_after_seconds,
                completed_grace_seconds=args.completed_grace_seconds,
            )
            print(render_directory_audit(report), flush=True)
            if report.needs_attention:
                exit_code = 2
            if args.once:
                return exit_code
            time.sleep(args.interval_seconds)

    if args.command == "auto-start":
        return _cmd_auto_start(args)

    return 1


def _cmd_auto_start(args: argparse.Namespace) -> int:
    """Watchdog loop: start predictor automatically when no active match is running."""
    source_dir = Path(args.source_dir)
    schedule_file = Path(args.schedule_file)
    source_dir.mkdir(parents=True, exist_ok=True)

    # In-memory process registry: match_id -> Popen
    _procs: dict[str, subprocess.Popen] = {}

    _ts = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731

    print(f"[auto-start] {_ts()} Watchdog started. source_dir={source_dir}", flush=True)
    if args.auto_discover:
        print(f"[auto-start] Mode: CREX auto-discovery (crex.com/live-matches) + schedule fallback.", flush=True)
    else:
        print(f"[auto-start] Mode: schedule file only ({schedule_file}).", flush=True)
    if args.dry_run:
        print("[auto-start] DRY RUN — no processes will be spawned.", flush=True)

    while True:
        now = datetime.now(timezone.utc)

        # --- Reap finished processes ---
        for mid in list(_procs):
            proc = _procs[mid]
            if proc.poll() is not None:
                print(f"[auto-start] {_ts()} Predictor for '{mid}' exited (code {proc.returncode}).", flush=True)
                del _procs[mid]

        # --- Check for active match ---
        report = audit_state_directory(
            source_dir,
            stale_after_seconds=args.stale_after_seconds,
            completed_grace_seconds=args.completed_grace_seconds,
            now=now,
        )
        has_active = (
            report.recommended_candidate is not None
            and not report.recommended_candidate.stale
            and not report.recommended_candidate.has_result
        )
        if has_active:
            print(
                f"[auto-start] {_ts()} Active: {report.recommended_candidate.match_id} "
                f"(age {report.recommended_candidate.age_seconds}s). OK.",
                flush=True,
            )
            time.sleep(args.interval_seconds)
            continue

        # --- Build candidate list ---
        candidates: list[dict[str, Any]] = []

        if args.auto_discover:
            print(f"[auto-start] {_ts()} No active match — querying CREX live-matches...", flush=True)
            discovered = asyncio.run(_discover_crex_live_matches())
            if discovered:
                print(
                    f"[auto-start] {_ts()} CREX discovered {len(discovered)} match(es): "
                    + ", ".join(f"{d['match_id']}({d['league']})" for d in discovered),
                    flush=True,
                )
                candidates = discovered
            else:
                print(f"[auto-start] {_ts()} CREX returned no supported matches. Falling back to schedule.", flush=True)

        if not candidates:
            candidates = _load_schedule(schedule_file)
            if not candidates:
                print(f"[auto-start] {_ts()} No candidates from CREX or schedule. Waiting...", flush=True)
                time.sleep(args.interval_seconds)
                continue

        # --- Find first candidate not already running ---
        already_running = set(_procs.keys())
        match_entry = _pick_candidate(candidates, already_running=already_running)

        if match_entry is None:
            print(f"[auto-start] {_ts()} All candidates already running. Waiting...", flush=True)
            time.sleep(args.interval_seconds)
            continue

        mid = match_entry["match_id"]
        league = match_entry.get("league", "ipl")
        print(f"[auto-start] {_ts()} Starting predictor for '{mid}' (league={league})...", flush=True)

        if not args.dry_run:
            proc = _spawn_predictor(match_entry, source_dir)
            if proc is not None:
                _procs[mid] = proc
                print(f"[auto-start] {_ts()} Predictor PID={proc.pid} for '{mid}'.", flush=True)
        else:
            cmd = _build_predictor_cmd(match_entry, source_dir)
            print(f"[auto-start] DRY RUN cmd: {' '.join(cmd)}", flush=True)

        time.sleep(args.interval_seconds)

    return 0  # unreachable


def _pick_candidate(
    candidates: list[dict[str, Any]],
    *,
    already_running: set[str],
) -> dict[str, Any] | None:
    """Return the first enabled candidate not already running."""
    for entry in candidates:
        if not entry.get("enabled", True):
            continue
        mid = entry.get("match_id", "")
        if mid and mid in already_running:
            continue
        if not entry.get("url"):
            continue
        return entry
    return None


def _load_schedule(schedule_file: Path) -> list[dict[str, Any]]:
    """Load the match schedule JSON. Returns empty list on error."""
    if not schedule_file.exists():
        return []
    try:
        with open(schedule_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("schedule", data.get("matches", []))
    except Exception as exc:
        print(f"[auto-start] WARNING: could not read schedule file {schedule_file}: {exc}", flush=True)
    return []


def _find_eligible_match(
    schedule: list[dict[str, Any]],
    *,
    already_running: set[str],
    now: datetime,
    lookahead_minutes: int,
    lookback_hours: int,
) -> dict[str, Any] | None:
    """Return the first scheduled match that should be started right now."""
    window_start = now - timedelta(hours=lookback_hours)
    window_end = now + timedelta(minutes=lookahead_minutes)

    for entry in schedule:
        if not entry.get("enabled", True):
            continue
        mid = entry.get("match_id", "")
        if mid in already_running:
            continue
        if not entry.get("url"):
            continue
        raw_time = entry.get("start_time")
        if not raw_time:
            continue
        start_time = _parse_schedule_time(raw_time)
        if start_time is None:
            continue
        if window_start <= start_time <= window_end:
            return entry

    return None


def _parse_schedule_time(value: Any) -> datetime | None:
    """Parse a start_time string from the schedule file."""
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
        return _ensure_utc(dt)
    except ValueError:
        return None


def _build_predictor_cmd(match_entry: dict[str, Any], source_dir: Path) -> list[str]:
    """Build the crex_live_predictor command for a scheduled match entry."""
    league = match_entry.get("league", "ipl").lower()
    cfg = _LEAGUE_PREDICTOR_CONFIGS.get(league, _LEAGUE_PREDICTOR_CONFIGS["ipl"])
    mid = match_entry["match_id"]
    output_json = str(source_dir / f"{mid}.json")

    cmd = [
        sys.executable, "-m", "src.bbl_pipeline.inference.crex_live_predictor",
        "--match-url", match_entry["url"],
        "--model-dir", match_entry.get("model_dir", cfg["model_dir"]),
        "--feature-store-dir", match_entry.get("feature_store_dir", cfg["feature_store_dir"]),
        "--league", league,
        "--output-json", output_json,
    ]
    if match_entry.get("record_states", True):
        states_dir = match_entry.get("states_dir", cfg["states_dir"])
        cmd += ["--record-states", "--states-dir", states_dir]
    return cmd


def _spawn_predictor(match_entry: dict[str, Any], source_dir: Path) -> subprocess.Popen | None:
    """Spawn the predictor subprocess. Returns the Popen object or None on failure."""
    cmd = _build_predictor_cmd(match_entry, source_dir)
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"predictor_{match_entry['match_id']}.log"
    try:
        log_fh = open(log_path, "a", encoding="utf-8", buffering=1)
        proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=log_fh,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
        )
        print(f"[auto-start] Log: {log_path}", flush=True)
        return proc
    except Exception as exc:
        print(f"[auto-start] ERROR spawning predictor: {exc}", flush=True)
        return None


def _add_common_dir_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source-dir",
        default="data/dashboard_states",
        help="Directory containing dashboard live-state JSON files.",
    )
    parser.add_argument(
        "--stale-after-seconds",
        type=int,
        default=DEFAULT_STALE_AFTER_SECONDS,
        help="Treat a feed as stale after this age.",
    )
    parser.add_argument(
        "--completed-grace-seconds",
        type=int,
        default=DEFAULT_COMPLETED_GRACE_SECONDS,
        help="Keep a completed feed acceptable for this long before flagging it.",
    )


def audit_state_directory(
    source_dir: Path,
    *,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    completed_grace_seconds: int = DEFAULT_COMPLETED_GRACE_SECONDS,
    now: datetime | None = None,
) -> DirectoryAudit:
    """Audit all dashboard state JSON files in a directory."""
    now_utc = _ensure_utc(now or datetime.now(timezone.utc))
    candidates = _state_json_candidates(source_dir)
    audits = [
        audit_match_file(
            path,
            stale_after_seconds=stale_after_seconds,
            completed_grace_seconds=completed_grace_seconds,
            now=now_utc,
        )
        for path in candidates
    ]

    current_candidate = max(audits, key=lambda item: Path(item.json_path).stat().st_mtime) if audits else None
    recommended_candidate = _pick_recommended_candidate(audits)

    reasons: list[str] = []
    needs_attention = False

    if current_candidate is None:
        needs_attention = True
        reasons.append("No dashboard state JSON files were found.")
    else:
        if current_candidate.stale:
            needs_attention = True
            reasons.append(
                f"Current candidate {current_candidate.match_id} is stale ({current_candidate.age_seconds}s old).",
            )
        if current_candidate.has_result and _older_than(current_candidate, completed_grace_seconds):
            needs_attention = True
            reasons.append(
                f"Current candidate {current_candidate.match_id} is a completed match that was not rotated out.",
            )
        if recommended_candidate and recommended_candidate.json_path != current_candidate.json_path:
            needs_attention = True
            reasons.append(
                f"Recommended active match is {recommended_candidate.match_id}, not the newest file {current_candidate.match_id}.",
            )

    return DirectoryAudit(
        source_dir=str(source_dir),
        scanned_at=now_utc.isoformat(),
        total_files=len(audits),
        current_candidate=current_candidate,
        recommended_candidate=recommended_candidate,
        needs_attention=needs_attention,
        reasons=reasons,
        audits=audits,
    )


def choose_active_state_json(
    source_dir: Path,
    *,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    completed_grace_seconds: int = DEFAULT_COMPLETED_GRACE_SECONDS,
    now: datetime | None = None,
) -> Path | None:
    """Return the best live-state JSON to treat as current."""
    report = audit_state_directory(
        source_dir,
        stale_after_seconds=stale_after_seconds,
        completed_grace_seconds=completed_grace_seconds,
        now=now,
    )
    if report.recommended_candidate is None:
        return None
    return Path(report.recommended_candidate.json_path)


def audit_match_file(
    json_path: Path,
    *,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    completed_grace_seconds: int = DEFAULT_COMPLETED_GRACE_SECONDS,
    now: datetime | None = None,
) -> MatchAudit:
    """Audit one live-state JSON file."""
    del completed_grace_seconds  # Used at the directory decision layer.
    now_utc = _ensure_utc(now or datetime.now(timezone.utc))
    live_state = load_live_signal_state(json_path)
    main_state = live_state.main_state
    sidecar_state = live_state.sidecar_state or {}
    sidecar_live_state = sidecar_state.get("state", {})

    timestamp = _parse_timestamp(main_state.get("timestamp"))
    age_seconds = int((now_utc - timestamp).total_seconds()) if timestamp else None
    batting_team, bowling_team = _resolve_match_teams(main_state)
    target = _safe_int(main_state.get("target"))
    score_value = _safe_int(main_state.get("score"))
    wickets = _safe_int(main_state.get("wickets"))
    overs = main_state.get("overs")
    is_second_innings = bool(main_state.get("is_second_innings"))
    winner = _determine_winner(main_state)
    stale = age_seconds is None or age_seconds > stale_after_seconds

    reasons: list[str] = []
    status = "active"
    if stale:
        status = "stale"
        reasons.append("Feed timestamp is stale or missing.")
    if winner is not None:
        status = "completed"
        reasons.append(f"Winner already determined: {winner}.")
    if not batting_team or not bowling_team:
        reasons.append("Match teams could not be resolved cleanly.")
    if sidecar_live_state.get("last_ball_number") in (None, "", "0.0") and score_value in (None, 0):
        reasons.append("Feed may still be in pre-match or not fully initialized.")

    return MatchAudit(
        json_path=str(json_path),
        match_id=json_path.stem,
        match=_render_match_name(batting_team, bowling_team, is_second_innings),
        timestamp=timestamp.isoformat() if timestamp else None,
        age_seconds=age_seconds,
        batting_team=batting_team,
        bowling_team=bowling_team,
        score=_score_text(score_value, wickets),
        overs=str(overs) if overs is not None else None,
        target=target,
        is_second_innings=is_second_innings,
        has_result=winner is not None,
        stale=stale,
        status=status,
        reasons=reasons,
    )


def render_directory_audit(report: DirectoryAudit) -> str:
    """Render a human-readable audit summary."""
    lines = [
        f"[prod-ops] scanned={report.scanned_at} source={report.source_dir}",
        f"[prod-ops] files={report.total_files} needs_attention={'yes' if report.needs_attention else 'no'}",
    ]

    if report.current_candidate:
        lines.append("[prod-ops] current=" + _render_match_line(report.current_candidate))
    else:
        lines.append("[prod-ops] current=none")

    if report.recommended_candidate:
        lines.append("[prod-ops] recommended=" + _render_match_line(report.recommended_candidate))
    else:
        lines.append("[prod-ops] recommended=none")

    for reason in report.reasons:
        lines.append(f"[prod-ops] attention: {reason}")

    for audit in report.audits[:5]:
        lines.append("[prod-ops] audit=" + _render_match_line(audit))

    return "\n".join(lines)


def _render_match_line(audit: MatchAudit) -> str:
    return (
        f"{audit.match_id} status={audit.status} age={audit.age_seconds}s "
        f"match={audit.match or 'unknown'} score={audit.score or '-'} overs={audit.overs or '-'}"
    )


def _pick_recommended_candidate(audits: list[MatchAudit]) -> MatchAudit | None:
    active = [audit for audit in audits if not audit.stale and not audit.has_result]
    if active:
        return max(active, key=lambda item: Path(item.json_path).stat().st_mtime)

    recent_completed = [audit for audit in audits if audit.has_result and not audit.stale]
    if recent_completed:
        return max(recent_completed, key=lambda item: Path(item.json_path).stat().st_mtime)

    if audits:
        return max(audits, key=lambda item: Path(item.json_path).stat().st_mtime)
    return None


def load_live_signal_state(json_path: str | Path) -> _LiveSignalState:
    """Load live predictor JSON and optional sidecar payloads."""
    main_path = Path(json_path)
    if not main_path.exists():
        raise LiveStateError(f"Live predictor JSON not found: {main_path}")

    main_state = _read_json(main_path)
    if not isinstance(main_state, dict):
        raise LiveStateError(f"Unexpected live predictor payload in {main_path}")

    history_path = main_path.with_name(f"{main_path.stem}_history.json")
    if history_path.exists():
        history_payload = _read_json(history_path)
        if isinstance(history_payload, dict):
            history = history_payload.get("history", [])
            if len(history) > len(main_state.get("history", []) or []):
                main_state["history"] = history

    sidecar_path = main_path.with_name(f"{main_path.stem}_livematch.json")
    sidecar_state = _read_json(sidecar_path) if sidecar_path.exists() else None

    return _LiveSignalState(
        json_path=str(main_path),
        main_state=main_state,
        sidecar_state=sidecar_state,
    )


def _state_json_candidates(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        return []
    return sorted(
        [
            path
            for path in source_dir.glob("*.json")
            if not path.stem.endswith("_history") and not path.stem.endswith("_livematch")
        ],
        key=lambda path: path.stat().st_mtime,
    )


def _render_match_name(batting_team: str | None, bowling_team: str | None, is_second_innings: bool) -> str | None:
    if not batting_team or not bowling_team:
        return None
    if is_second_innings:
        return f"{bowling_team} vs {batting_team}"
    return f"{batting_team} vs {bowling_team}"


def _resolve_match_teams(main_state: dict[str, Any]) -> tuple[str | None, str | None]:
    batting_team = main_state.get("batting_team")
    bowling_team = main_state.get("bowling_team")
    return batting_team, bowling_team


def _score_text(score: int | None, wickets: int | None) -> str | None:
    if score is None or wickets is None:
        return None
    return f"{score}/{wickets}"


def _older_than(audit: MatchAudit, seconds: int) -> bool:
    return audit.age_seconds is not None and audit.age_seconds > seconds


def _determine_winner(main_state: dict[str, Any]) -> str | None:
    if not main_state.get("is_second_innings"):
        return None
    batting_team = main_state.get("batting_team")
    bowling_team = main_state.get("bowling_team")
    score = _safe_int(main_state.get("score"), 0) or 0
    wickets = _safe_int(main_state.get("wickets"), 0) or 0
    overs = _safe_float(main_state.get("overs"), 0.0) or 0.0
    total_overs = _safe_float(main_state.get("total_overs"), 20.0) or 20.0
    target = _safe_int(main_state.get("target"))
    if not target:
        return None
    if score >= target:
        return batting_team
    if wickets >= 10 or overs >= total_overs:
        return bowling_team
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _ensure_utc(datetime.fromisoformat(value))
    except ValueError:
        return None


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


@dataclass
class _LiveSignalState:
    json_path: str
    main_state: dict[str, Any]
    sidecar_state: dict[str, Any] | None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
