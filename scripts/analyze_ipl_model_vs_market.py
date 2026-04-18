#!/usr/bin/env python
"""
IPL Model vs Market Analysis
=============================
Compare our T20 model (with IPL temperature scaling) against betx21.live market odds.

Parses betx21 production data (20 IPL matches, Apr 2026), runs our model inference
on reconstructed match states, and compares model probability vs market implied probability.

Usage:
    python scripts/analyze_ipl_model_vs_market.py

Outputs:
    data/ipl_model_vs_market.parquet    — All data joined
    data/ipl_model_vs_market_summary.csv — Per-match/per-phase summary
    data/ipl_model_vs_market_report.md   — Findings + improvement recommendations
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

BETX21_DIR = Path(r"C:\Users\ADMINS\Documents\projects\betx21.live\ipl_matches_download")
MODEL_DIR = PROJECT_ROOT / "models" / "t20_male_v2"
FEATURE_STORE_DIR = PROJECT_ROOT / "data" / "ipl_feature_store_v2"
OUTPUT_DIR = PROJECT_ROOT / "data"

IPL_MATCHES = {
    "35436411": {"t1": "Chennai Super Kings", "t2": "Punjab Kings", "date": "2026-04-03"},
    "35436433": {"t1": "Gujarat Titans", "t2": "Rajasthan Royals", "date": "2026-04-04"},
    "35439742": {"t1": "Delhi Capitals", "t2": "Mumbai Indians", "date": "2026-04-04"},
    "35445130": {"t1": "Sunrisers Hyderabad", "t2": "Lucknow Super Giants", "date": "2026-04-05"},
    "35448572": {"t1": "Royal Challengers Bengaluru", "t2": "Chennai Super Kings", "date": "2026-04-05"},
    "35449675": {"t1": "Kolkata Knight Riders", "t2": "Punjab Kings", "date": "2026-04-06"},
    "35452229": {"t1": "Rajasthan Royals", "t2": "Mumbai Indians", "date": "2026-04-07"},
    "35452241": {"t1": "Delhi Capitals", "t2": "Gujarat Titans", "date": "2026-04-08"},
    "35460131": {"t1": "Kolkata Knight Riders", "t2": "Lucknow Super Giants", "date": "2026-04-09"},
    "35464806": {"t1": "Rajasthan Royals", "t2": "Royal Challengers Bengaluru", "date": "2026-04-10"},
    "35460133": {"t1": "Punjab Kings", "t2": "Sunrisers Hyderabad", "date": "2026-04-11"},
    "35468493": {"t1": "Chennai Super Kings", "t2": "Delhi Capitals", "date": "2026-04-11"},
    "35472691": {"t1": "Lucknow Super Giants", "t2": "Gujarat Titans", "date": "2026-04-12"},
    "35475078": {"t1": "Mumbai Indians", "t2": "Royal Challengers Bengaluru", "date": "2026-04-12"},
    "35479213": {"t1": "Sunrisers Hyderabad", "t2": "Rajasthan Royals", "date": "2026-04-13"},
    "35479923": {"t1": "Chennai Super Kings", "t2": "Kolkata Knight Riders", "date": "2026-04-14"},
    "35483421": {"t1": "Royal Challengers Bengaluru", "t2": "Lucknow Super Giants", "date": "2026-04-15"},
    "35483422": {"t1": "Mumbai Indians", "t2": "Punjab Kings", "date": "2026-04-16"},
    "35491266": {"t1": "Gujarat Titans", "t2": "Kolkata Knight Riders", "date": "2026-04-17"},
    "35495679": {"t1": "Royal Challengers Bengaluru", "t2": "Delhi Capitals", "date": "2026-04-18"},
}

# Team code mapping (for model MatchState)
TEAM_CODES = {
    "Chennai Super Kings": "CSK", "Punjab Kings": "PBKS",
    "Gujarat Titans": "GT", "Rajasthan Royals": "RR",
    "Delhi Capitals": "DC", "Mumbai Indians": "MI",
    "Sunrisers Hyderabad": "SRH", "Lucknow Super Giants": "LSG",
    "Royal Challengers Bengaluru": "RCB", "Kolkata Knight Riders": "KKR",
}

# IPL 2026 venues (match_id → venue) — populated from known schedule
# If not known, we use a generic IPL venue that exists in the feature store
DEFAULT_VENUE = "MA Chidambaram Stadium, Chepauk, Chennai"


# ---------------------------------------------------------------------------
# Phase A: Parse betx21 data
# ---------------------------------------------------------------------------

def safe_read_gz(path: str) -> list[dict]:
    """Read gzip JSONL with error tolerance."""
    records = []
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
    """Parse '156/4 (15.3)' → (runs=156, wickets=4, overs=15.5)"""
    if not score_str or not score_str.strip():
        return None
    m = re.match(r"(\d+)/(\d+)\s*\((\d+\.\d+)\)", score_str.strip())
    if not m:
        return None
    runs = int(m.group(1))
    wickets = int(m.group(2))
    overs_str = m.group(3)
    whole_overs = int(overs_str.split(".")[0])
    balls = int(overs_str.split(".")[1])
    overs_decimal = whole_overs + balls / 6.0
    return runs, wickets, overs_decimal


def load_betx21_scores(event_ids: set[str]) -> dict[str, list[dict]]:
    """Load all score records for given event IDs from betx21 downloads."""
    scores: dict[str, list[dict]] = {ev: [] for ev in event_ids}
    for d in sorted(os.listdir(BETX21_DIR)):
        dp = os.path.join(BETX21_DIR, d)
        if not os.path.isdir(dp):
            continue
        for sf in sorted(Path(dp).glob("*_scores.jsonl.gz")):
            for rec in safe_read_gz(str(sf)):
                ev = rec.get("ev", "")
                if ev in event_ids:
                    scores[ev].append(rec)
    # Sort by timestamp
    for ev in scores:
        scores[ev].sort(key=lambda r: r.get("t", ""))
    return scores


def load_betx21_odds(event_ids: set[str]) -> dict[str, list[dict]]:
    """Load matchOdds records for given event IDs from betx21 downloads."""
    odds: dict[str, list[dict]] = {ev: [] for ev in event_ids}
    for d in sorted(os.listdir(BETX21_DIR)):
        dp = os.path.join(BETX21_DIR, d)
        if not os.path.isdir(dp):
            continue
        for of in sorted(Path(dp).glob("*_odds.jsonl.gz")):
            for rec in safe_read_gz(str(of)):
                ev = rec.get("ev", "")
                if ev in event_ids and rec.get("mt") == "matchOdds":
                    odds[ev].append(rec)
    for ev in odds:
        odds[ev].sort(key=lambda r: r.get("t", ""))
    return odds


@dataclass
class OverState:
    """State at the end of a completed over."""
    event_id: str
    innings: int
    over: int  # 1-based completed over
    batting_team: str
    bowling_team: str
    runs: int
    wickets: int
    run_rate: float
    required_rate: float | None
    target: int | None
    first_innings_score: int | None
    timestamp: str


def extract_over_states(event_id: str, score_records: list[dict]) -> list[OverState]:
    """
    From score records, extract one state per completed over.
    For each over N (1-20), we take the LAST score record where the over
    value >= N (i.e., the state after over N is completed).
    Handles betx21 quirks: s1 can go blank during 2nd innings, recording
    may start mid-over, etc.
    """
    if not score_records:
        return []

    info = IPL_MATCHES.get(event_id, {})
    t1 = info.get("t1", "")
    t2 = info.get("t2", "")

    # Pass 1: collect all parsed score snapshots
    inn1_snapshots: dict[int, tuple] = {}  # over -> (runs, wickets, overs_dec, timestamp)
    inn2_snapshots: dict[int, tuple] = {}
    first_innings_score = None
    last_s1_parsed = None

    for rec in score_records:
        s1_parsed = parse_score_string(rec.get("s1", ""))
        s2_parsed = parse_score_string(rec.get("s2", ""))
        ts = rec.get("t", "")

        # Track s1 for first innings score even if it goes blank later
        if s1_parsed:
            last_s1_parsed = s1_parsed

        s2_text = rec.get("s2", "").strip()
        # First innings: s1 has score and s2 is empty/blank
        if s1_parsed and not s2_text:
            runs, wickets, overs_dec = s1_parsed
            whole_overs = int(overs_dec)
            # Record the most recent state for each completed over
            if whole_overs >= 1:
                inn1_snapshots[whole_overs] = (runs, wickets, overs_dec, ts)
            if whole_overs >= 20 or wickets >= 10:
                first_innings_score = runs

        # Second innings: s2 has score
        if s2_parsed:
            if first_innings_score is None and last_s1_parsed:
                first_innings_score = last_s1_parsed[0]

            runs2, wickets2, overs_dec2 = s2_parsed
            whole_overs2 = int(overs_dec2)
            if whole_overs2 >= 1:
                inn2_snapshots[whole_overs2] = (runs2, wickets2, overs_dec2, ts)

    # Pass 2: Build OverState objects from snapshots
    states: list[OverState] = []

    for over in sorted(inn1_snapshots.keys()):
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

    for over in sorted(inn2_snapshots.keys()):
        runs2, wickets2, overs_dec2, ts = inn2_snapshots[over]
        rr = runs2 / over if over > 0 else 0
        rrq = None
        if target and over < 20:
            remaining_overs = 20 - over
            rrq = (target - runs2) / remaining_overs if remaining_overs > 0 else None

        states.append(OverState(
            event_id=event_id, innings=2, over=over,
            batting_team=t2, bowling_team=t1,
            runs=runs2, wickets=wickets2,
            run_rate=rr, required_rate=rrq,
            target=target, first_innings_score=first_innings_score,
            timestamp=ts,
        ))

    return states


def get_market_prob_at_time(odds_records: list[dict], timestamp: str, team1: str) -> float | None:
    """
    Get market implied probability for team1 at the given timestamp.
    Uses nearest-before-or-at odds tick. R0=team1, R1=team2.
    Returns P(team1 wins) as implied probability from back odds.
    """
    if not odds_records:
        return None

    # Find the last active odds tick at or before timestamp
    best = None
    for rec in odds_records:
        if rec.get("t", "") <= timestamp and rec.get("ms") == "active":
            best = rec

    if not best:
        # Fallback: use nearest tick even if suspended
        for rec in odds_records:
            if rec.get("t", "") <= timestamp:
                best = rec

    if not best:
        return None

    runners = best.get("r", [])
    if len(runners) < 2:
        return None

    # R0 = team1 (t1 in scores). Use midpoint of back/lay for implied prob.
    r0 = runners[0]
    backs = r0.get("b", [])
    lays = r0.get("l", [])

    back_price = backs[0][0] if backs and backs[0] else None
    lay_price = lays[0][0] if lays and lays[0] else None

    if back_price and lay_price and back_price > 0 and lay_price > 0:
        mid_price = (back_price + lay_price) / 2
        return 1.0 / mid_price
    elif back_price and back_price > 0:
        return 1.0 / back_price
    elif lay_price and lay_price > 0:
        return 1.0 / lay_price

    return None


def determine_winner(event_id: str, score_records: list[dict]) -> str | None:
    """Determine which team won from score progression."""
    if not score_records:
        return None

    info = IPL_MATCHES.get(event_id, {})
    t1 = info.get("t1", "")
    t2 = info.get("t2", "")

    # Track the last valid s1 and s2 across all records
    last_s1 = None
    last_s2 = None
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
            return t2  # Team 2 chased successfully
        elif last_s2[2] >= 20.0 or last_s2[1] >= 10:
            return t1  # Team 1 defended
        # Partial match (rain, etc.) — try DLS or just return None
        if last_s2[2] >= 19.5:
            return t1
    return None


# ---------------------------------------------------------------------------
# Phase B: Run model inference
# ---------------------------------------------------------------------------

def load_model():
    """Load the T20 global model with IPL league calibrator."""
    from bbl_pipeline.inference.predictor import Predictor

    print(f"Loading model from {MODEL_DIR}")
    print(f"Feature store from {FEATURE_STORE_DIR}")
    predictor = Predictor.load(str(MODEL_DIR), str(FEATURE_STORE_DIR), league="ipl")
    print(f"Model loaded. League calibrator: {predictor.league_calibrator is not None}")
    if predictor.league_calibrator:
        method = predictor.league_calibrator.get("method", "?")
        print(f"  Calibration method: {method}")
    return predictor


def predict_state(predictor, over_state: OverState) -> dict:
    """Run model prediction on a single over state."""
    from bbl_pipeline.inference.schema import MatchState

    state = MatchState(
        match_id=over_state.event_id,
        venue=DEFAULT_VENUE,
        batting_team=over_state.batting_team,
        bowling_team=over_state.bowling_team,
        innings=over_state.innings,
        over=over_state.over,
        ball=0,  # End of over
        current_score=over_state.runs,
        wickets_lost=over_state.wickets,
        batsman_1="Unknown",
        batsman_2="Unknown",
        bowler="Unknown",
        target_runs=over_state.target,
        first_innings_score=over_state.first_innings_score,
        total_overs=20,
    )

    try:
        prob = predictor.predict(state)
        return {
            "model_prob_batting_wins": prob,
            "model_raw": getattr(predictor, "last_raw_prob", None),
            "model_per_over": getattr(predictor, "last_calibrated_per_over", None),
            "model_phase": getattr(predictor, "last_calibrated_phase", None),
            "model_league": getattr(predictor, "last_league_calibrated", None),
            "error": None,
        }
    except Exception as e:
        return {
            "model_prob_batting_wins": None,
            "model_raw": None,
            "model_per_over": None,
            "model_phase": None,
            "model_league": None,
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
    """Compute Brier score. Lower is better."""
    return np.mean((probs - outcomes) ** 2)


def ece_score(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> float:
    """Compute Expected Calibration Error."""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    total = len(probs)
    for i in range(n_bins):
        mask = (probs >= bin_edges[i]) & (probs < bin_edges[i + 1])
        if i == n_bins - 1:
            mask = (probs >= bin_edges[i]) & (probs <= bin_edges[i + 1])
        n = mask.sum()
        if n > 0:
            avg_pred = probs[mask].mean()
            avg_outcome = outcomes[mask].mean()
            ece += (n / total) * abs(avg_pred - avg_outcome)
    return ece


def log_loss_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Compute log loss."""
    eps = 1e-8
    p = np.clip(probs, eps, 1 - eps)
    return -np.mean(outcomes * np.log(p) + (1 - outcomes) * np.log(1 - p))


def build_comparison_dataframe(
    all_over_states: list[OverState],
    odds_by_event: dict[str, list[dict]],
    scores_by_event: dict[str, list[dict]],
    predictor,
) -> pd.DataFrame:
    """Build the main comparison DataFrame with model and market probabilities."""
    rows = []
    winners = {}

    for ev_id in IPL_MATCHES:
        winner = determine_winner(ev_id, scores_by_event.get(ev_id, []))
        winners[ev_id] = winner

    print(f"\nWinners determined for {sum(1 for w in winners.values() if w)} / {len(IPL_MATCHES)} matches")

    for state in all_over_states:
        ev_id = state.event_id
        info = IPL_MATCHES[ev_id]
        t1, t2 = info["t1"], info["t2"]
        winner = winners.get(ev_id)

        # Market probability: P(team1 wins) at this timestamp
        market_p_t1 = get_market_prob_at_time(
            odds_by_event.get(ev_id, []), state.timestamp, t1
        )

        # Model probability: P(batting_team wins)
        pred = predict_state(predictor, state)
        model_p_batting = pred["model_prob_batting_wins"]

        if model_p_batting is None or market_p_t1 is None:
            continue

        # Convert model prob to P(team1 wins) for consistent comparison
        if state.batting_team == t1:
            model_p_t1 = model_p_batting
        else:
            model_p_t1 = 1.0 - model_p_batting

        # Actual outcome: did team1 win?
        if winner:
            actual_t1_wins = 1.0 if winner == t1 else 0.0
        else:
            continue  # Skip matches where we can't determine winner

        rows.append({
            "event_id": ev_id,
            "date": info["date"],
            "match": f"{TEAM_CODES.get(t1, t1[:3])} vs {TEAM_CODES.get(t2, t2[:3])}",
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
            "model_phase": pred.get("model_phase"),
            "model_league": pred.get("model_league"),
            "model_error": abs(model_p_t1 - actual_t1_wins),
            "market_error": abs(market_p_t1 - actual_t1_wins),
            "model_better": abs(model_p_t1 - actual_t1_wins) < abs(market_p_t1 - actual_t1_wins),
            "prob_diff": model_p_t1 - market_p_t1,
            "timestamp": state.timestamp,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Phase D: Generate Report
# ---------------------------------------------------------------------------

def compute_metrics(df: pd.DataFrame, label: str) -> dict:
    """Compute Brier, ECE, LogLoss for model and market."""
    if len(df) == 0:
        return {}
    model_p = df["model_p_t1"].values
    market_p = df["market_p_t1"].values
    actual = df["actual_t1_wins"].values

    return {
        "segment": label,
        "n": len(df),
        "model_brier": round(brier_score(model_p, actual), 4),
        "market_brier": round(brier_score(market_p, actual), 4),
        "model_ece": round(ece_score(model_p, actual), 4),
        "market_ece": round(ece_score(market_p, actual), 4),
        "model_logloss": round(log_loss_score(model_p, actual), 4),
        "market_logloss": round(log_loss_score(market_p, actual), 4),
        "model_wins_pct": round(df["model_better"].mean() * 100, 1),
        "avg_prob_diff": round(df["prob_diff"].mean(), 4),
        "avg_abs_diff": round(df["prob_diff"].abs().mean(), 4),
    }


def generate_report(df: pd.DataFrame, output_path: Path):
    """Generate the markdown report."""
    lines = [
        "# IPL Model vs Market Analysis Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Matches**: {df['event_id'].nunique()} IPL matches (Apr 2026)",
        f"**Data points**: {len(df)} over-boundary observations",
        f"**Model**: t20_male_v2 global + IPL temperature scaling",
        f"**Market**: betx21.live matchOdds (exchange mid-price)",
        "",
        "---",
        "",
        "## Overall Comparison",
        "",
    ]

    # Overall metrics
    overall = compute_metrics(df, "Overall")
    lines.append(f"| Metric | Model | Market | Winner |")
    lines.append(f"|--------|-------|--------|--------|")
    for metric_name, model_key, market_key in [
        ("Brier Score", "model_brier", "market_brier"),
        ("ECE (10-bin)", "model_ece", "market_ece"),
        ("Log Loss", "model_logloss", "market_logloss"),
    ]:
        mv = overall[model_key]
        mkv = overall[market_key]
        winner = "✅ Model" if mv < mkv else "✅ Market" if mkv < mv else "Tie"
        lines.append(f"| {metric_name} | {mv:.4f} | {mkv:.4f} | {winner} |")

    lines.append("")
    lines.append(f"- Model is better on **{overall['model_wins_pct']:.1f}%** of observations")
    lines.append(f"- Average model-market difference: {overall['avg_prob_diff']:+.4f}")
    lines.append(f"- Average |model-market| gap: {overall['avg_abs_diff']:.4f}")
    lines.append("")

    # By innings
    lines.append("## By Innings")
    lines.append("")
    lines.append("| Innings | N | Model Brier | Market Brier | Gap | Model Wins % |")
    lines.append("|---------|---|-------------|--------------|-----|-------------|")
    for inn in [1, 2]:
        sub = df[df["innings"] == inn]
        m = compute_metrics(sub, f"innings_{inn}")
        if m:
            gap = m["model_brier"] - m["market_brier"]
            lines.append(f"| {inn} | {m['n']} | {m['model_brier']:.4f} | {m['market_brier']:.4f} | {gap:+.4f} | {m['model_wins_pct']:.1f}% |")
    lines.append("")

    # By phase
    lines.append("## By Phase")
    lines.append("")
    lines.append("| Phase | Innings | N | Model Brier | Market Brier | Gap | Model Wins % |")
    lines.append("|-------|---------|---|-------------|--------------|-----|-------------|")
    for phase in ["powerplay", "middle", "death"]:
        for inn in [1, 2]:
            sub = df[(df["phase"] == phase) & (df["innings"] == inn)]
            m = compute_metrics(sub, f"{phase}_inn{inn}")
            if m and m["n"] > 0:
                gap = m["model_brier"] - m["market_brier"]
                lines.append(f"| {phase} | {inn} | {m['n']} | {m['model_brier']:.4f} | {m['market_brier']:.4f} | {gap:+.4f} | {m['model_wins_pct']:.1f}% |")
    lines.append("")

    # By match
    lines.append("## By Match")
    lines.append("")
    lines.append("| Match | Date | N | Model Brier | Market Brier | Gap | Winner |")
    lines.append("|-------|------|---|-------------|--------------|-----|--------|")
    for ev_id in sorted(IPL_MATCHES.keys()):
        sub = df[df["event_id"] == ev_id]
        if len(sub) == 0:
            continue
        m = compute_metrics(sub, ev_id)
        match_name = sub.iloc[0]["match"]
        date = sub.iloc[0]["date"]
        gap = m["model_brier"] - m["market_brier"]
        winner = "Model" if gap < 0 else "Market"
        lines.append(f"| {match_name} | {date} | {m['n']} | {m['model_brier']:.4f} | {m['market_brier']:.4f} | {gap:+.4f} | {winner} |")
    lines.append("")

    # Calibration chain analysis
    lines.append("## Calibration Chain Impact")
    lines.append("")
    chain_cols = ["model_raw", "model_per_over", "model_phase", "model_league"]
    available = [c for c in chain_cols if c in df.columns and df[c].notna().sum() > 0]
    if available:
        lines.append("Average probability at each calibration stage (across all observations):")
        lines.append("")
        for col in available:
            sub = df[df[col].notna()]
            lines.append(f"- **{col.replace('model_', '')}**: mean={sub[col].mean():.4f}, std={sub[col].std():.4f}")
        lines.append("")

    # Overconfidence analysis
    lines.append("## Overconfidence Analysis")
    lines.append("")
    lines.append("Is the model too confident or too conservative vs market?")
    lines.append("")

    # Check if model predictions are more extreme than market
    model_spread = df["model_p_t1"].std()
    market_spread = df["market_p_t1"].std()
    lines.append(f"- Model prediction spread (std): {model_spread:.4f}")
    lines.append(f"- Market prediction spread (std): {market_spread:.4f}")
    if model_spread > market_spread * 1.05:
        lines.append("- **Model is MORE extreme** than market (possibly overconfident)")
    elif model_spread < market_spread * 0.95:
        lines.append("- **Model is MORE conservative** than market (predictions closer to 0.5)")
    else:
        lines.append("- Model and market have similar confidence levels")
    lines.append("")

    # Directional accuracy: when market moves, does model move same direction?
    lines.append("## Directional Agreement")
    lines.append("")
    # Compare within each match
    agreement_counts = 0
    total_transitions = 0
    for ev_id in df["event_id"].unique():
        sub = df[df["event_id"] == ev_id].sort_values(["innings", "over"])
        if len(sub) < 2:
            continue
        model_diff = sub["model_p_t1"].diff().iloc[1:]
        market_diff = sub["market_p_t1"].diff().iloc[1:]
        same_dir = ((model_diff > 0) & (market_diff > 0)) | ((model_diff < 0) & (market_diff < 0)) | ((model_diff == 0) & (market_diff == 0))
        agreement_counts += same_dir.sum()
        total_transitions += len(same_dir)

    if total_transitions > 0:
        pct = agreement_counts / total_transitions * 100
        lines.append(f"- Directional agreement (model & market move same way): **{pct:.1f}%** ({agreement_counts}/{total_transitions})")
        if pct >= 70:
            lines.append("- Strong agreement — model tracks market direction well")
        elif pct >= 55:
            lines.append("- Moderate agreement — model sometimes diverges from market")
        else:
            lines.append("- Weak agreement — model often disagrees with market direction")
    lines.append("")

    # Situational analysis: close matches vs blowouts
    lines.append("## Close Matches vs Blowouts")
    lines.append("")
    lines.append("| Situation | N | Model Brier | Market Brier | Gap |")
    lines.append("|-----------|---|-------------|--------------|-----|")

    for label, condition in [
        ("Close (market 40-60%)", (df["market_p_t1"] >= 0.40) & (df["market_p_t1"] <= 0.60)),
        ("Lean (market 60-75%)", ((df["market_p_t1"] >= 0.60) & (df["market_p_t1"] <= 0.75)) | ((df["market_p_t1"] >= 0.25) & (df["market_p_t1"] <= 0.40))),
        ("Strong (market 75%+)", (df["market_p_t1"] >= 0.75) | (df["market_p_t1"] <= 0.25)),
    ]:
        sub = df[condition]
        if len(sub) > 0:
            m = compute_metrics(sub, label)
            gap = m["model_brier"] - m["market_brier"]
            lines.append(f"| {label} | {m['n']} | {m['model_brier']:.4f} | {m['market_brier']:.4f} | {gap:+.4f} |")
    lines.append("")

    # Team-level analysis
    lines.append("## By Team (as batting team)")
    lines.append("")
    lines.append("| Team | N | Model Brier | Market Brier | Gap |")
    lines.append("|------|---|-------------|--------------|-----|")
    for team in sorted(df["batting_team"].unique()):
        sub = df[df["batting_team"] == team]
        if len(sub) >= 5:
            m = compute_metrics(sub, team)
            gap = m["model_brier"] - m["market_brier"]
            code = TEAM_CODES.get(team, team[:3])
            lines.append(f"| {code} | {m['n']} | {m['model_brier']:.4f} | {m['market_brier']:.4f} | {gap:+.4f} |")
    lines.append("")

    # Wickets fallen analysis
    lines.append("## By Wickets Fallen")
    lines.append("")
    lines.append("| Wickets | N | Model Brier | Market Brier | Gap |")
    lines.append("|---------|---|-------------|--------------|-----|")
    for w_range, w_label in [((0, 1), "0-1"), ((2, 3), "2-3"), ((4, 5), "4-5"), ((6, 10), "6+")]:
        sub = df[(df["wickets"] >= w_range[0]) & (df["wickets"] <= w_range[1])]
        if len(sub) >= 3:
            m = compute_metrics(sub, f"wkts_{w_label}")
            gap = m["model_brier"] - m["market_brier"]
            lines.append(f"| {w_label} | {m['n']} | {m['model_brier']:.4f} | {m['market_brier']:.4f} | {gap:+.4f} |")
    lines.append("")

    # Improvement recommendations
    lines.append("## Improvement Recommendations")
    lines.append("")

    # Compute key gaps to recommend
    inn1_metrics = compute_metrics(df[df["innings"] == 1], "inn1")
    inn2_metrics = compute_metrics(df[df["innings"] == 2], "inn2")

    recs = []
    if inn1_metrics and inn1_metrics.get("model_brier", 0) > inn1_metrics.get("market_brier", 0):
        gap = inn1_metrics["model_brier"] - inn1_metrics["market_brier"]
        recs.append(f"1. **First innings calibration** (gap: {gap:+.4f} Brier): Consider retuning FIRST_INNINGS_WICKET_PENALTY_3D for IPL conditions")

    if inn2_metrics and inn2_metrics.get("model_brier", 0) > inn2_metrics.get("market_brier", 0):
        gap = inn2_metrics["model_brier"] - inn2_metrics["market_brier"]
        recs.append(f"2. **Second innings chase model** (gap: {gap:+.4f} Brier): Improve resource_win_prob for IPL scoring conditions")

    if model_spread < market_spread * 0.95:
        recs.append("3. **Temperature scaling**: Model is too conservative — T parameter may need adjustment (lower T = sharper predictions)")
    elif model_spread > market_spread * 1.05:
        recs.append("3. **Temperature scaling**: Model is overconfident — T parameter may need adjustment (higher T = softer predictions)")

    death_gap = None
    for phase in ["death"]:
        for inn in [1, 2]:
            sub = df[(df["phase"] == phase) & (df["innings"] == inn)]
            m = compute_metrics(sub, f"{phase}_inn{inn}")
            if m and m.get("model_brier", 0) > m.get("market_brier", 0):
                g = m["model_brier"] - m["market_brier"]
                if death_gap is None or g > death_gap:
                    death_gap = g
    if death_gap and death_gap > 0.005:
        recs.append(f"4. **Death overs** (gap: {death_gap:+.4f}): Model underperforms market in death phase — consider IPL-specific death penalty tuning")

    if overall.get("model_brier", 0) > overall.get("market_brier", 0):
        recs.append("5. **Market-aware features**: Consider using betx21 odds as an input signal to the model (market consensus as a feature)")

    if not recs:
        recs.append("✅ Model performs competitively with market across all segments!")

    lines.extend(recs)
    lines.append("")
    lines.append("---")
    lines.append(f"*Analysis generated by `scripts/analyze_ipl_model_vs_market.py`*")

    report = "\n".join(lines)
    output_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved to {output_path}")
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("IPL Model vs Market Analysis")
    print("=" * 70)

    # Check prerequisites
    if not BETX21_DIR.exists():
        print(f"ERROR: betx21 data not found at {BETX21_DIR}")
        sys.exit(1)
    if not MODEL_DIR.exists():
        print(f"ERROR: Model not found at {MODEL_DIR}")
        sys.exit(1)

    event_ids = set(IPL_MATCHES.keys())

    # Phase A: Parse betx21 data
    print("\n--- Phase A: Loading betx21 data ---")
    scores_by_event = load_betx21_scores(event_ids)
    odds_by_event = load_betx21_odds(event_ids)

    total_scores = sum(len(v) for v in scores_by_event.values())
    total_odds = sum(len(v) for v in odds_by_event.values())
    print(f"Loaded {total_scores} score records, {total_odds} matchOdds records")

    # Extract over-boundary states
    all_states: list[OverState] = []
    for ev_id in event_ids:
        states = extract_over_states(ev_id, scores_by_event.get(ev_id, []))
        all_states.extend(states)
        info = IPL_MATCHES[ev_id]
        match_name = f"{TEAM_CODES.get(info['t1'], '?')} vs {TEAM_CODES.get(info['t2'], '?')}"
        winner = determine_winner(ev_id, scores_by_event.get(ev_id, []))
        inn1_overs = sum(1 for s in states if s.innings == 1)
        inn2_overs = sum(1 for s in states if s.innings == 2)
        print(f"  {match_name}: {inn1_overs} inn1 + {inn2_overs} inn2 overs, winner={winner or 'unknown'}")

    print(f"\nTotal over-boundary states: {len(all_states)}")

    # Phase B: Load model and run inference
    print("\n--- Phase B: Running model inference ---")
    predictor = load_model()

    # Phase C: Build comparison
    print("\n--- Phase C: Building comparison ---")
    df = build_comparison_dataframe(all_states, odds_by_event, scores_by_event, predictor)
    print(f"Comparison DataFrame: {len(df)} rows, {df['event_id'].nunique()} matches")

    if len(df) == 0:
        print("ERROR: No valid comparison rows produced")
        sys.exit(1)

    # Save outputs
    print("\n--- Phase D: Saving outputs ---")
    parquet_path = OUTPUT_DIR / "ipl_model_vs_market.parquet"
    df.to_parquet(parquet_path, index=False)
    print(f"Saved {parquet_path}")

    csv_path = OUTPUT_DIR / "ipl_model_vs_market_summary.csv"
    # Per-match summary
    summary_rows = []
    for ev_id in df["event_id"].unique():
        sub = df[df["event_id"] == ev_id]
        m = compute_metrics(sub, ev_id)
        m["match"] = sub.iloc[0]["match"]
        m["date"] = sub.iloc[0]["date"]
        m["winner"] = sub.iloc[0]["winner"]
        summary_rows.append(m)
    pd.DataFrame(summary_rows).to_csv(csv_path, index=False)
    print(f"Saved {csv_path}")

    # Generate report
    report_path = OUTPUT_DIR / "ipl_model_vs_market_report.md"
    report = generate_report(df, report_path)

    # Print key findings
    overall = compute_metrics(df, "Overall")
    print("\n" + "=" * 70)
    print("KEY FINDINGS")
    print("=" * 70)
    print(f"  Model Brier:  {overall['model_brier']:.4f}")
    print(f"  Market Brier: {overall['market_brier']:.4f}")
    gap = overall["model_brier"] - overall["market_brier"]
    if gap > 0:
        print(f"  Market is BETTER by {gap:.4f} Brier ({gap / overall['market_brier'] * 100:+.1f}%)")
    else:
        print(f"  Model is BETTER by {abs(gap):.4f} Brier ({gap / overall['market_brier'] * 100:+.1f}%)")
    print(f"  Model beats market on {overall['model_wins_pct']:.1f}% of observations")


if __name__ == "__main__":
    main()
