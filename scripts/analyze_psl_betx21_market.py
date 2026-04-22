#!/usr/bin/env python
"""
PSL Model vs Market Analysis (betx21.live)
==========================================
Compare PSL v1 standalone model against betx21.live matchOdds for 17 PSL 2026 matches.

Uses the same pipeline as analyze_ipl_model_vs_market.py:
  1. Parse betx21 scores for per-over state reconstruction
  2. Parse betx21 odds for market implied probabilities
  3. Run psl_v1 model inference on each over state
  4. Compare model Brier / ECE / LogLoss vs market

Usage:
    python scripts/analyze_psl_betx21_market.py

Outputs:
    data/psl_betx21_model_vs_market.parquet     -- All joined data
    data/psl_betx21_summary.csv                 -- Per-match/per-phase summary
    data/psl_betx21_report.md                   -- Market-beating findings
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

BETX21_DIR = Path(r"C:\Users\ADMINS\Documents\projects\betx21.live\ipl_matches_download")
MODEL_DIR = PROJECT_ROOT / "models" / "psl_v4"
FEATURE_STORE_DIR = PROJECT_ROOT / "data" / "psl_feature_store_v4"
OUTPUT_DIR = PROJECT_ROOT / "data"

# 17 PSL matches (Apr 2026) found in betx21.live data
PSL_MATCHES = {
    "35440113": {"t1": "Lahore Qalandars",   "t2": "Multan Sultans",    "date": "2026-04-03"},
    "35445109": {"t1": "Rawalpindi Pindiz",  "t2": "Islamabad United",  "date": "2026-04-04"},
    "35449778": {"t1": "Quetta Gladiators",  "t2": "Multan Sultans",    "date": "2026-04-05"},
    "35456643": {"t1": "Multan Sultans",     "t2": "Rawalpindi Pindiz", "date": "2026-04-06"},
    "35439737": {"t1": "Hyderabad Kingsmen", "t2": "Peshawar Zalmi",    "date": "2026-04-08"},
    "35452262": {"t1": "Lahore Qalandars",   "t2": "Islamabad United",  "date": "2026-04-09"},
    "35468421": {"t1": "Karachi Kings",      "t2": "Peshawar Zalmi",    "date": "2026-04-09"},
    "35460327": {"t1": "Quetta Gladiators",  "t2": "Rawalpindi Pindiz", "date": "2026-04-10"},
    "35472699": {"t1": "Peshawar Zalmi",     "t2": "Lahore Qalandars",  "date": "2026-04-11"},
    "35472829": {"t1": "Karachi Kings",      "t2": "Hyderabad Kingsmen","date": "2026-04-11"},
    "35479053": {"t1": "Hyderabad Kingsmen", "t2": "Islamabad United",  "date": "2026-04-12"},
    "35479193": {"t1": "Peshawar Zalmi",     "t2": "Multan Sultans",    "date": "2026-04-13"},
    "35487378": {"t1": "Peshawar Zalmi",     "t2": "Quetta Gladiators", "date": "2026-04-15"},
    "35483479": {"t1": "Karachi Kings",      "t2": "Islamabad United",  "date": "2026-04-16"},
    "35483476": {"t1": "Hyderabad Kingsmen", "t2": "Rawalpindi Pindiz", "date": "2026-04-16"},
    "35495766": {"t1": "Lahore Qalandars",   "t2": "Quetta Gladiators", "date": "2026-04-17"},
    "35499526": {"t1": "Lahore Qalandars",   "t2": "Rawalpindi Pindiz", "date": "2026-04-18"},
}

# Team alias mapping (betx21 name → feature store name)
# Feature store uses "Rawalpindiz" as shorthand for the new PSL team
TEAM_ALIASES: dict[str, str] = {
    "Rawalpindi Pindiz": "Rawalpindiz",
}

# Short codes for display
TEAM_CODES: dict[str, str] = {
    "Lahore Qalandars": "LAH",
    "Multan Sultans":   "MUL",
    "Rawalpindi Pindiz":"RAW",
    "Rawalpindiz":      "RAW",
    "Islamabad United": "ISL",
    "Quetta Gladiators":"QUE",
    "Peshawar Zalmi":   "PES",
    "Karachi Kings":    "KAR",
    "Hyderabad Kingsmen":"HYK",
}

# Heuristic venue mapping: t1 (home team) → venue
# PSL 2026 home venues
TEAM_VENUES: dict[str, str] = {
    "Lahore Qalandars":   "Gaddafi Stadium, Lahore",
    "Karachi Kings":      "National Stadium, Karachi",
    "Multan Sultans":     "Multan Cricket Stadium",
    "Rawalpindi Pindiz":  "Rawalpindi Cricket Stadium",
    "Rawalpindiz":        "Rawalpindi Cricket Stadium",
    "Islamabad United":   "Rawalpindi Cricket Stadium",
    "Peshawar Zalmi":     "Rawalpindi Cricket Stadium",
    "Quetta Gladiators":  "National Stadium, Karachi",
    "Hyderabad Kingsmen": "National Stadium, Karachi",
}

DEFAULT_VENUE = "Gaddafi Stadium, Lahore"


# ---------------------------------------------------------------------------
# Phase A: Parse betx21 data
# ---------------------------------------------------------------------------

def safe_read_gz(path: str | Path) -> list[dict]:
    """Read gzip JSONL with error tolerance."""
    records: list[dict] = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                try:
                    records.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    pass
    except (EOFError, OSError):
        pass
    return records


def parse_score_string(score_str: str) -> tuple[int, int, float] | None:
    """Parse '156/4 (15.3)' → (runs=156, wickets=4, overs_decimal=15.5)"""
    if not score_str or not score_str.strip():
        return None
    m = re.match(r"(\d+)/(\d+)\s*\((\d+\.\d+)\)", score_str.strip())
    if not m:
        return None
    runs = int(m.group(1))
    wickets = int(m.group(2))
    overs_str = m.group(3)
    whole, balls = int(overs_str.split(".")[0]), int(overs_str.split(".")[1])
    return runs, wickets, whole + balls / 6.0


def load_betx21_scores(event_ids: set[str]) -> dict[str, list[dict]]:
    scores: dict[str, list[dict]] = {ev: [] for ev in event_ids}
    for d in sorted(os.listdir(BETX21_DIR)):
        dp = BETX21_DIR / d
        if not dp.is_dir():
            continue
        for sf in sorted(dp.glob("*_scores.jsonl.gz")):
            for rec in safe_read_gz(sf):
                ev = rec.get("ev", "")
                if ev in event_ids:
                    scores[ev].append(rec)
    for ev in scores:
        scores[ev].sort(key=lambda r: r.get("t", ""))
    return scores


def load_betx21_odds(event_ids: set[str]) -> dict[str, list[dict]]:
    odds: dict[str, list[dict]] = {ev: [] for ev in event_ids}
    for d in sorted(os.listdir(BETX21_DIR)):
        dp = BETX21_DIR / d
        if not dp.is_dir():
            continue
        for of in sorted(dp.glob("*_odds.jsonl.gz")):
            for rec in safe_read_gz(of):
                ev = rec.get("ev", "")
                if ev in event_ids and rec.get("mt") == "matchOdds":
                    odds[ev].append(rec)
    for ev in odds:
        odds[ev].sort(key=lambda r: r.get("t", ""))
    return odds


@dataclass
class OverState:
    event_id: str
    innings: int
    over: int          # 1-based completed over number
    batting_team: str  # betx21 name
    bowling_team: str  # betx21 name
    runs: int
    wickets: int
    run_rate: float
    required_rate: float | None
    target: int | None
    first_innings_score: int | None
    timestamp: str


def extract_over_states(event_id: str, score_records: list[dict]) -> list[OverState]:
    if not score_records:
        return []

    info = PSL_MATCHES[event_id]
    t1, t2 = info["t1"], info["t2"]

    inn1_snapshots: dict[int, tuple] = {}
    inn2_snapshots: dict[int, tuple] = {}
    first_innings_score: int | None = None
    last_s1_parsed = None

    for rec in score_records:
        s1_parsed = parse_score_string(rec.get("s1", ""))
        s2_parsed = parse_score_string(rec.get("s2", ""))
        ts = rec.get("t", "")

        if s1_parsed:
            last_s1_parsed = s1_parsed

        s2_text = rec.get("s2", "").strip()

        # First innings: s1 has score, s2 empty
        if s1_parsed and not s2_text:
            runs, wickets, overs_dec = s1_parsed
            whole = int(overs_dec)
            if whole >= 1:
                inn1_snapshots[whole] = (runs, wickets, overs_dec, ts)
            if whole >= 20 or wickets >= 10:
                first_innings_score = runs

        # Second innings: s2 has score
        if s2_parsed:
            if first_innings_score is None and last_s1_parsed:
                first_innings_score = last_s1_parsed[0]
            runs2, wickets2, overs_dec2 = s2_parsed
            whole2 = int(overs_dec2)
            if whole2 >= 1:
                inn2_snapshots[whole2] = (runs2, wickets2, overs_dec2, ts)

    states: list[OverState] = []

    for over in sorted(inn1_snapshots):
        runs, wickets, overs_dec, ts = inn1_snapshots[over]
        states.append(OverState(
            event_id=event_id, innings=1, over=over,
            batting_team=t1, bowling_team=t2,
            runs=runs, wickets=wickets,
            run_rate=runs / over if over > 0 else 0,
            required_rate=None, target=None,
            first_innings_score=None, timestamp=ts,
        ))

    target = (first_innings_score + 1) if first_innings_score else None

    for over in sorted(inn2_snapshots):
        runs2, wickets2, overs_dec2, ts = inn2_snapshots[over]
        rr = runs2 / over if over > 0 else 0
        rrq: float | None = None
        if target and over < 20:
            rem = 20 - over
            rrq = (target - runs2) / rem if rem > 0 else None
        states.append(OverState(
            event_id=event_id, innings=2, over=over,
            batting_team=t2, bowling_team=t1,
            runs=runs2, wickets=wickets2,
            run_rate=rr, required_rate=rrq,
            target=target, first_innings_score=first_innings_score,
            timestamp=ts,
        ))

    return states


def get_market_prob_at_time(
    odds_records: list[dict],
    timestamp: str,
    team1: str,
) -> float | None:
    """P(team1 wins) from betx21 matchOdds at or just before `timestamp`."""
    if not odds_records:
        return None

    best = None
    for rec in odds_records:
        if rec.get("t", "") <= timestamp and rec.get("ms") == "active":
            best = rec
    if not best:
        for rec in odds_records:
            if rec.get("t", "") <= timestamp:
                best = rec
    if not best:
        return None

    runners = best.get("r", [])
    if len(runners) < 2:
        return None

    # Runner 0 = t1 (home team), Runner 1 = t2
    r0 = runners[0]
    backs = r0.get("b", [])
    lays = r0.get("l", [])
    back_price = backs[0][0] if backs and backs[0] else None
    lay_price  = lays[0][0]  if lays  and lays[0]  else None

    if back_price and lay_price and back_price > 0 and lay_price > 0:
        return 1.0 / ((back_price + lay_price) / 2)
    elif back_price and back_price > 0:
        return 1.0 / back_price
    elif lay_price and lay_price > 0:
        return 1.0 / lay_price
    return None


def determine_winner(event_id: str, score_records: list[dict]) -> str | None:
    info = PSL_MATCHES.get(event_id, {})
    t1, t2 = info.get("t1", ""), info.get("t2", "")

    # First try: parse the msg field for explicit "X won by Y" text
    # betx21 emits this in the final score record when a match completes
    for rec in reversed(score_records):
        msg = rec.get("msg", "")
        if msg and ("won" in msg.lower() or "wins" in msg.lower()):
            # Check if t1 team name appears before "won"
            if t1.lower() in msg.lower():
                return t1
            elif t2.lower() in msg.lower():
                return t2
            # Partial match: check if any team word appears
            for team in [t1, t2]:
                for word in team.split():
                    if len(word) > 4 and word.lower() in msg.lower():
                        return team

    # Second try: infer from final scores
    last_s1 = last_s2 = None
    for rec in score_records:
        p1 = parse_score_string(rec.get("s1", ""))
        p2 = parse_score_string(rec.get("s2", ""))
        if p1:
            last_s1 = p1
        if p2:
            last_s2 = p2

    if last_s1 and last_s2:
        target = last_s1[0] + 1
        if last_s2[0] >= target:
            return t2
        elif last_s2[2] >= 20.0 or last_s2[1] >= 10:
            return t1
        if last_s2[2] >= 19.5:
            return t1
    return None


# ---------------------------------------------------------------------------
# Phase B: Model inference
# ---------------------------------------------------------------------------

def load_model():
    from bbl_pipeline.inference.predictor import Predictor
    print(f"Loading PSL model from {MODEL_DIR}")
    predictor = Predictor.load(str(MODEL_DIR), str(FEATURE_STORE_DIR))
    print("PSL v1 model loaded.")
    return predictor


def canonical_team(name: str) -> str:
    """Map betx21 team name to feature-store canonical name."""
    return TEAM_ALIASES.get(name, name)


def predict_state(predictor, state: OverState) -> dict:
    from bbl_pipeline.inference.schema import MatchState

    info = PSL_MATCHES[state.event_id]
    t1 = info["t1"]
    t2 = info["t2"]
    venue = TEAM_VENUES.get(t1, DEFAULT_VENUE)

    ms = MatchState(
        match_id=state.event_id,
        venue=venue,
        batting_team=canonical_team(state.batting_team),
        bowling_team=canonical_team(state.bowling_team),
        innings=state.innings,
        over=state.over,
        ball=0,
        current_score=state.runs,
        wickets_lost=state.wickets,
        batsman_1="Unknown",
        batsman_2="Unknown",
        bowler="Unknown",
        target_runs=state.target,
        first_innings_score=state.first_innings_score,
        total_overs=20,
    )

    try:
        prob = predictor.predict(ms)
        return {
            "model_prob_batting_wins": prob,
            "model_raw": getattr(predictor, "last_raw_prob", None),
            "model_per_over": getattr(predictor, "last_calibrated_per_over", None),
            "model_phase": getattr(predictor, "last_calibrated_phase", None),
            "error": None,
        }
    except Exception as e:
        return {
            "model_prob_batting_wins": None,
            "model_raw": None,
            "model_per_over": None,
            "model_phase": None,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Phase C: Comparison
# ---------------------------------------------------------------------------

def get_phase(over: int) -> str:
    if over <= 6:
        return "powerplay"
    elif over <= 15:
        return "middle"
    else:
        return "death"


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    return float(np.mean((probs - outcomes) ** 2))


def ece_score(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> float:
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    total = len(probs)
    for i in range(n_bins):
        mask = (probs >= bin_edges[i]) & (
            probs <= bin_edges[i + 1] if i == n_bins - 1 else probs < bin_edges[i + 1]
        )
        n = mask.sum()
        if n > 0:
            ece += (n / total) * abs(probs[mask].mean() - outcomes[mask].mean())
    return ece


def log_loss_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    eps = 1e-8
    p = np.clip(probs, eps, 1 - eps)
    return float(-np.mean(outcomes * np.log(p) + (1 - outcomes) * np.log(1 - p)))


def build_comparison_df(
    all_states: list[OverState],
    odds_by_event: dict[str, list[dict]],
    scores_by_event: dict[str, list[dict]],
    predictor,
) -> pd.DataFrame:
    winners: dict[str, str | None] = {}
    for ev_id in PSL_MATCHES:
        winners[ev_id] = determine_winner(ev_id, scores_by_event.get(ev_id, []))

    resolved = sum(1 for w in winners.values() if w)
    print(f"\nWinners resolved: {resolved}/{len(PSL_MATCHES)} matches")
    for ev, w in sorted(winners.items()):
        info = PSL_MATCHES[ev]
        status = w if w else "UNKNOWN"
        print(f"  {ev} {info['t1']} vs {info['t2']}: {status}")

    rows: list[dict] = []
    skipped_no_market = 0
    skipped_no_winner = 0
    skipped_no_model  = 0

    for state in all_states:
        ev_id = state.event_id
        info = PSL_MATCHES[ev_id]
        t1, t2 = info["t1"], info["t2"]
        winner = winners.get(ev_id)

        if not winner:
            skipped_no_winner += 1
            continue

        market_p_t1 = get_market_prob_at_time(
            odds_by_event.get(ev_id, []), state.timestamp, t1
        )
        if market_p_t1 is None:
            skipped_no_market += 1
            continue

        pred = predict_state(predictor, state)
        model_p_batting = pred["model_prob_batting_wins"]
        if model_p_batting is None:
            skipped_no_model += 1
            continue

        # Convert to P(t1 wins)
        model_p_t1 = model_p_batting if state.batting_team == t1 else 1.0 - model_p_batting
        actual_t1_wins = 1.0 if winner == t1 else 0.0

        t1_code = TEAM_CODES.get(t1, t1[:3])
        t2_code = TEAM_CODES.get(t2, t2[:3])

        rows.append({
            "event_id": ev_id,
            "date": info["date"],
            "match": f"{t1_code} vs {t2_code}",
            "team1": t1,
            "team2": t2,
            "winner": winner,
            "innings": state.innings,
            "over": state.over,
            "phase": get_phase(state.over),
            "batting_team": state.batting_team,
            "runs": state.runs,
            "wickets": state.wickets,
            "run_rate": round(state.run_rate, 2),
            "required_rate": round(state.required_rate, 2) if state.required_rate else None,
            "target": state.target,
            "model_p_t1": round(model_p_t1, 4),
            "market_p_t1": round(market_p_t1, 4),
            "actual_t1_wins": actual_t1_wins,
            "model_raw": pred.get("model_raw"),
            "model_per_over": pred.get("model_per_over"),
            "model_error": abs(model_p_t1 - actual_t1_wins),
            "market_error": abs(market_p_t1 - actual_t1_wins),
            "model_better": abs(model_p_t1 - actual_t1_wins) < abs(market_p_t1 - actual_t1_wins),
            "prob_diff": round(model_p_t1 - market_p_t1, 4),
            "timestamp": state.timestamp,
        })

    print(f"\nRows built: {len(rows)} "
          f"(skipped: no_winner={skipped_no_winner}, "
          f"no_market={skipped_no_market}, no_model={skipped_no_model})")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Phase D: Report
# ---------------------------------------------------------------------------

def compute_metrics(df: pd.DataFrame, label: str) -> dict:
    if len(df) == 0:
        return {}
    model_p  = df["model_p_t1"].values
    market_p = df["market_p_t1"].values
    actual   = df["actual_t1_wins"].values
    return {
        "segment":       label,
        "n":             len(df),
        "model_brier":   round(brier_score(model_p, actual), 4),
        "market_brier":  round(brier_score(market_p, actual), 4),
        "model_ece":     round(ece_score(model_p, actual), 4),
        "market_ece":    round(ece_score(market_p, actual), 4),
        "model_logloss": round(log_loss_score(model_p, actual), 4),
        "market_logloss":round(log_loss_score(market_p, actual), 4),
        "model_wins_pct":round(df["model_better"].mean() * 100, 1),
        "avg_prob_diff": round(df["prob_diff"].mean(), 4),
        "avg_abs_diff":  round(df["prob_diff"].abs().mean(), 4),
    }


def generate_report(df: pd.DataFrame, output_path: Path) -> None:
    lines = [
        "# PSL Model vs Market Analysis Report (betx21.live)",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Matches**: {df['event_id'].nunique()} PSL 2026 matches (Apr 2026)",
        f"**Data points**: {len(df)} over-boundary observations",
        f"**Model**: PSL v1 standalone  (brier_optimized OOF = 0.1834)",
        f"**Market**: betx21.live matchOdds (exchange mid-price implied prob)",
        "",
        "---",
        "",
    ]

    overall = compute_metrics(df, "Overall")

    lines += [
        "## Overall Comparison",
        "",
        "| Metric | Model | Market | Winner |",
        "|--------|-------|--------|--------|",
    ]
    for name, mk, mkv_key in [
        ("Brier Score ↓", "model_brier",   "market_brier"),
        ("ECE (10-bin) ↓","model_ece",     "market_ece"),
        ("Log Loss ↓",    "model_logloss", "market_logloss"),
    ]:
        mv  = overall[mk]
        mkv = overall[mkv_key]
        w   = "✅ **Model**" if mv < mkv else "✅ **Market**" if mkv < mv else "Tie"
        lines.append(f"| {name} | {mv:.4f} | {mkv:.4f} | {w} |")

    lines += [
        "",
        f"- Model is better on **{overall['model_wins_pct']:.1f}%** of observations (lower abs error per over)",
        f"- Average model−market difference: {overall['avg_prob_diff']:+.4f}  "
        f"({'model overestimates' if overall['avg_prob_diff'] > 0 else 'model underestimates'} batting team vs market)",
        f"- Average |model−market| spread: {overall['avg_abs_diff']:.4f}",
        "",
    ]

    # By innings
    lines += [
        "## By Innings",
        "",
        "| Innings | N | Model Brier | Market Brier | Gap | Model Win % |",
        "|---------|---|-------------|--------------|-----|-------------|",
    ]
    for inn in [1, 2]:
        m = compute_metrics(df[df["innings"] == inn], f"inn{inn}")
        if m:
            gap = m["model_brier"] - m["market_brier"]
            marker = " ✅" if gap < 0 else ""
            lines.append(
                f"| {inn} | {m['n']} | {m['model_brier']:.4f} | "
                f"{m['market_brier']:.4f} | {gap:+.4f}{marker} | {m['model_wins_pct']:.1f}% |"
            )
    lines.append("")

    # By phase × innings
    lines += [
        "## By Phase × Innings",
        "",
        "| Phase | Inn | N | Model Brier | Market Brier | Gap | Model Win % |",
        "|-------|-----|---|-------------|--------------|-----|-------------|",
    ]
    for phase in ["powerplay", "middle", "death"]:
        for inn in [1, 2]:
            sub = df[(df["phase"] == phase) & (df["innings"] == inn)]
            m = compute_metrics(sub, f"{phase}_inn{inn}")
            if m and m["n"] >= 5:
                gap = m["model_brier"] - m["market_brier"]
                marker = " ✅" if gap < 0 else ""
                lines.append(
                    f"| {phase} | {inn} | {m['n']} | {m['model_brier']:.4f} | "
                    f"{m['market_brier']:.4f} | {gap:+.4f}{marker} | {m['model_wins_pct']:.1f}% |"
                )
    lines.append("")

    # Per-match summary
    lines += [
        "## Per-Match Summary",
        "",
        "| Match | Date | Winner | N | Model Brier | Market Brier | Gap |",
        "|-------|------|--------|---|-------------|--------------|-----|",
    ]
    for ev_id in sorted(df["event_id"].unique()):
        sub = df[df["event_id"] == ev_id]
        m = compute_metrics(sub, ev_id)
        if m:
            info = PSL_MATCHES[ev_id]
            winner_code = TEAM_CODES.get(sub["winner"].iloc[0], sub["winner"].iloc[0][:3])
            gap = m["model_brier"] - m["market_brier"]
            marker = " ✅" if gap < 0 else ""
            lines.append(
                f"| {sub['match'].iloc[0]} | {info['date']} | {winner_code} | {m['n']} | "
                f"{m['model_brier']:.4f} | {m['market_brier']:.4f} | {gap:+.4f}{marker} |"
            )
    lines.append("")

    # Bias analysis
    lines += [
        "## Calibration Bias Analysis",
        "",
        "Positive diff = model gives higher probability to t1 (batting team in inn1) than market.",
        "",
        "| Segment | Avg Diff | Avg |Diff| | Interpretation |",
        "|---------|----------|----------|----------------|",
    ]
    for inn in [1, 2]:
        for phase in ["powerplay", "middle", "death"]:
            sub = df[(df["innings"] == inn) & (df["phase"] == phase)]
            if len(sub) >= 5:
                avg = sub["prob_diff"].mean()
                avg_abs = sub["prob_diff"].abs().mean()
                interp = (
                    "model overestimates batting" if avg > 0.03
                    else "model underestimates batting" if avg < -0.03
                    else "well-calibrated to market"
                )
                lines.append(
                    f"| Inn{inn} {phase} | {avg:+.4f} | {avg_abs:.4f} | {interp} |"
                )
    lines.append("")

    # OOF reference
    lines += [
        "## OOF Training Context",
        "",
        "| Method | OOF Brier | OOF ECE |",
        "|--------|-----------|---------|",
        "| PSL v1 brier_optimized | 0.1834 | 0.0000 |",
        "| PSL v1 raw baseline | 0.1955 | 0.0480 |",
        "",
        "> Note: OOF Brier is computed on historical PSL data (2017-2026, 338 matches).",
        "> Live market Brier above is on OOS PSL 2026 data (17 matches).",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("PSL Model vs Market Analysis (betx21.live)")
    print("=" * 60)
    print(f"\nPSL matches to process: {len(PSL_MATCHES)}")

    event_ids = set(PSL_MATCHES.keys())

    print("\nLoading betx21 scores …")
    scores_by_event = load_betx21_scores(event_ids)
    total_score_recs = sum(len(v) for v in scores_by_event.values())
    print(f"  {total_score_recs} score records across {len(PSL_MATCHES)} matches")
    for ev, recs in scores_by_event.items():
        info = PSL_MATCHES[ev]
        print(f"  {ev} {info['t1']} vs {info['t2']}: {len(recs)} score records")

    print("\nLoading betx21 odds …")
    odds_by_event = load_betx21_odds(event_ids)
    total_odds_recs = sum(len(v) for v in odds_by_event.values())
    print(f"  {total_odds_recs} matchOdds records across {len(PSL_MATCHES)} matches")

    print("\nExtracting over states …")
    all_states: list[OverState] = []
    for ev in event_ids:
        states = extract_over_states(ev, scores_by_event[ev])
        all_states.extend(states)
        inn1 = sum(1 for s in states if s.innings == 1)
        inn2 = sum(1 for s in states if s.innings == 2)
        print(f"  {ev}: {len(states)} over states (inn1={inn1}, inn2={inn2})")
    print(f"  Total: {len(all_states)} over states")

    print("\nLoading PSL v1 model …")
    predictor = load_model()

    print("\nBuilding comparison DataFrame …")
    df = build_comparison_df(all_states, odds_by_event, scores_by_event, predictor)

    if df.empty:
        print("ERROR: No comparison rows. Check data paths and match IDs.")
        return

    print(f"\nFinal DataFrame: {len(df)} rows, {df['event_id'].nunique()} matches")

    # Save
    out_parquet = OUTPUT_DIR / "psl_betx21_model_vs_market.parquet"
    out_csv     = OUTPUT_DIR / "psl_betx21_summary.csv"
    out_report  = OUTPUT_DIR / "psl_betx21_report.md"

    df.to_parquet(out_parquet, index=False)
    print(f"Saved: {out_parquet}")

    summary_rows = []
    for segment, sub in [
        ("overall", df),
        *[(f"inn{i}", df[df["innings"] == i]) for i in [1, 2]],
        *[(f"{ph}_inn{i}", df[(df["phase"] == ph) & (df["innings"] == i)])
          for ph in ["powerplay", "middle", "death"] for i in [1, 2]],
    ]:
        m = compute_metrics(sub, segment)
        if m:
            summary_rows.append(m)
    pd.DataFrame(summary_rows).to_csv(out_csv, index=False)
    print(f"Saved: {out_csv}")

    generate_report(df, out_report)

    # Print headline results
    print("\n" + "=" * 60)
    print("HEADLINE RESULTS")
    print("=" * 60)
    overall = compute_metrics(df, "Overall")
    model_beats_market = overall["model_brier"] < overall["market_brier"]
    print(f"\n  Model Brier:  {overall['model_brier']:.4f}")
    print(f"  Market Brier: {overall['market_brier']:.4f}")
    print(f"  {'[MODEL BEATS MARKET]' if model_beats_market else '[Market beats model]'}")
    print(f"\n  Model ECE:    {overall['model_ece']:.4f}")
    print(f"  Market ECE:   {overall['market_ece']:.4f}")
    print(f"\n  Model better on {overall['model_wins_pct']:.1f}% of observations")
    print(f"  Avg model-market spread: {overall['avg_prob_diff']:+.4f}")

    print("\nPer-innings:")
    for inn in [1, 2]:
        m = compute_metrics(df[df["innings"] == inn], f"inn{inn}")
        if m:
            gap = m["model_brier"] - m["market_brier"]
            print(f"  Inn{inn}: model={m['model_brier']:.4f} market={m['market_brier']:.4f} gap={gap:+.4f}")


if __name__ == "__main__":
    main()
