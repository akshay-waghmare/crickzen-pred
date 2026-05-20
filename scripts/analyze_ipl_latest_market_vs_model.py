"""
Build the latest IPL market-vs-model comparison from Cricsheet features and betx21 data.

This is the repeatable version of the earlier IPL market analysis:
  - discovers IPL-like betx21 score/odds files
  - maps them to Cricsheet matches by date and team set
  - corrects runner-order flips using final odds vs the known winner
  - scores the IPL model from feature parquet end-of-over rows
  - writes parquet, summary CSV, and markdown report artifacts

Usage:
  python scripts/analyze_ipl_latest_market_vs_model.py \
    --features data/ipl_features_latest/training.parquet \
    --raw data/ipl_raw_latest/matches \
    --model-dir models/ipl_v6
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bbl_pipeline.inference.predictor import _restore_simple_imputer_compatibility  # noqa: E402


DEFAULT_BETX21_DIR = Path(r"C:\Users\ADMINS\Documents\projects\betx21.live\ipl_matches_download")
IPL_TEAM_HINTS = (
    "Chennai", "Punjab", "Gujarat", "Rajasthan", "Delhi", "Mumbai",
    "Sunrisers", "Lucknow", "Royal Challengers", "Kolkata", "RC Bengaluru",
)
TEAM_ALIASES = {
    "RC Bengaluru": "Royal Challengers Bengaluru",
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
}


@dataclass(frozen=True)
class Betx21Event:
    event_id: str
    date: str
    t1: str
    t2: str


@dataclass(frozen=True)
class OverSnapshot:
    event_id: str
    innings: int
    over: int
    timestamp: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Latest IPL model-vs-market comparison")
    parser.add_argument("--features", default="data/ipl_features_latest/training.parquet")
    parser.add_argument("--raw", default="data/ipl_raw_latest/matches")
    parser.add_argument("--model-dir", default="models/ipl_v6")
    parser.add_argument("--betx21-dir", default=str(DEFAULT_BETX21_DIR))
    parser.add_argument("--output", default="data/ipl_latest_market_vs_model.parquet")
    parser.add_argument("--summary", default="data/ipl_latest_market_vs_model_summary.csv")
    parser.add_argument("--report", default="data/ipl_latest_market_vs_model_report.md")
    return parser.parse_args()


def normalize_team(team: str) -> str:
    return TEAM_ALIASES.get(str(team).strip(), str(team).strip())


def phase_of(over_1idx: int) -> str:
    if over_1idx <= 6:
        return "powerplay"
    if over_1idx <= 15:
        return "middle"
    return "death"


def safe_read_gz(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except (EOFError, OSError):
        return rows
    return rows


def first_jsonl_record(path: Path) -> dict | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    return json.loads(line)
    except (EOFError, OSError, json.JSONDecodeError):
        return None
    return None


def discover_ipl_events(betx21_dir: Path) -> dict[str, Betx21Event]:
    events: dict[str, Betx21Event] = {}
    for score_file in sorted(betx21_dir.rglob("*_scores.jsonl.gz")):
        rec = first_jsonl_record(score_file)
        if not rec:
            continue
        t1 = str(rec.get("t1", "")).strip()
        t2 = str(rec.get("t2", "")).strip()
        joined = f"{t1} {t2}"
        if not any(hint.lower() in joined.lower() for hint in IPL_TEAM_HINTS):
            continue
        event_id = score_file.name.split("_")[0]
        events[event_id] = Betx21Event(
            event_id=event_id,
            date=score_file.parent.name,
            t1=normalize_team(t1),
            t2=normalize_team(t2),
        )
    return events


def parse_score_string(score_str: str) -> tuple[int, int, float] | None:
    if not score_str or not str(score_str).strip():
        return None
    match = re.match(r"(\d+)/(\d+)\s*\((\d+)\.(\d+)\)", str(score_str).strip())
    if not match:
        return None
    runs = int(match.group(1))
    wickets = int(match.group(2))
    overs = int(match.group(3)) + int(match.group(4)) / 6.0
    return runs, wickets, overs


def extract_over_snapshots(event_id: str, score_records: list[dict]) -> list[OverSnapshot]:
    inn1: dict[int, str] = {}
    inn2: dict[int, str] = {}
    for rec in score_records:
        ts = rec.get("t", "")
        s1 = parse_score_string(rec.get("s1", ""))
        s2 = parse_score_string(rec.get("s2", ""))
        if s1 and not str(rec.get("s2", "")).strip():
            over = int(s1[2])
            if over >= 1:
                inn1[over] = ts
        if s2:
            over = int(s2[2])
            if over >= 1:
                inn2[over] = ts
    return [
        *(OverSnapshot(event_id, 1, over, ts) for over, ts in sorted(inn1.items())),
        *(OverSnapshot(event_id, 2, over, ts) for over, ts in sorted(inn2.items())),
    ]


def midpoint_prob(runner: dict) -> float | None:
    backs = runner.get("b", [])
    lays = runner.get("l", [])
    back_price = backs[0][0] if backs and backs[0] else None
    lay_price = lays[0][0] if lays and lays[0] else None
    if back_price and lay_price and back_price > 0 and lay_price > 0:
        return 1.0 / ((back_price + lay_price) / 2)
    if back_price and back_price > 0:
        return 1.0 / back_price
    if lay_price and lay_price > 0:
        return 1.0 / lay_price
    return None


def market_r1_prob_at(odds_records: list[dict], timestamp: str) -> float | None:
    best = None
    for rec in odds_records:
        if rec.get("t", "") <= timestamp and rec.get("ms") == "active":
            best = rec
    if best is None:
        for rec in odds_records:
            if rec.get("t", "") <= timestamp:
                best = rec
    if best is None:
        return None
    runners = best.get("r", [])
    if len(runners) < 2:
        return None
    return midpoint_prob(runners[0])


def make_apply_iso(cal_dict):
    per_over = cal_dict.get("per_over_calibrators", {}) if isinstance(cal_dict, dict) else {}
    phase_cal = cal_dict.get("phase_calibrators", {}) if isinstance(cal_dict, dict) else {}
    innings_cal = {
        "innings_1": cal_dict.get("calibrator_innings1") if isinstance(cal_dict, dict) else None,
        "innings_2": cal_dict.get("calibrator_innings2") if isinstance(cal_dict, dict) else None,
    }

    def apply_iso(prob: float, innings: int, over_0idx: int) -> float:
        key = f"inn{innings}_over{over_0idx + 1}"
        if key in per_over:
            return float(per_over[key].predict([prob])[0])
        phase = "powerplay" if over_0idx < 6 else ("middle" if over_0idx < 15 else "death")
        phase_key = f"inn{innings}_{phase}"
        if phase_key in phase_cal:
            return float(phase_cal[phase_key].predict([prob])[0])
        innings_key = f"innings_{innings}"
        if innings_cal.get(innings_key) is not None:
            return float(innings_cal[innings_key].predict([prob])[0])
        if isinstance(cal_dict, dict) and innings in cal_dict:
            return float(cal_dict[innings].predict([prob])[0])
        return float(prob)

    return apply_iso


def load_and_score_features(features_path: Path, model_dir: Path) -> pd.DataFrame:
    model = joblib.load(model_dir / "champion_model.joblib")
    _restore_simple_imputer_compatibility(model)
    calibrator_path = model_dir / "isotonic_calibrator.pkl"
    apply_iso = make_apply_iso(joblib.load(calibrator_path)) if calibrator_path.exists() else None

    features = pd.read_parquet(features_path).copy()
    required = {"match_id", "innings", "over", "ball", "batting_team", "winner"}
    missing = required - set(features.columns)
    if missing:
        raise ValueError(f"Features missing required metadata columns: {sorted(missing)}")

    features["match_id"] = features["match_id"].astype(str)
    features = features.sort_values(["match_id", "innings", "over", "ball"])
    end_over = features.groupby(["match_id", "innings", "over"], as_index=False).tail(1).copy()
    end_over["over_1idx"] = end_over["over"].astype(int) + 1
    raw = model.predict_proba(end_over[model.selected_features_])[:, 1]
    end_over["raw_prob_batting"] = raw
    if apply_iso:
        end_over["iso_prob_batting"] = [
            apply_iso(p, int(inn), int(over))
            for p, inn, over in zip(raw, end_over["innings"], end_over["over"])
        ]
    else:
        end_over["iso_prob_batting"] = raw
    return end_over


def build_match_map(raw_path: Path, events: dict[str, Betx21Event]) -> dict[str, dict]:
    raw = pd.read_parquet(raw_path).copy()
    raw["match_id"] = raw["match_id"].astype(str)
    raw["date"] = raw["date"].astype(str)
    maps: dict[str, dict] = {}
    match_meta = raw.groupby("match_id").agg(
        date=("date", "first"),
        winner=("winner", "first"),
        teams=("batting_team", lambda s: tuple(sorted(normalize_team(x) for x in pd.unique(s)))),
        inn1_team=("batting_team", "first"),
    )

    for event in events.values():
        event_teams = tuple(sorted((event.t1, event.t2)))
        candidates = match_meta[
            (match_meta["date"] == event.date)
            & (match_meta["teams"].apply(lambda teams: tuple(teams) == event_teams))
        ]
        if candidates.empty:
            continue
        row = candidates.iloc[0]
        maps[event.event_id] = {
            "cs_match_id": str(candidates.index[0]),
            "winner": normalize_team(row["winner"]),
            "inn1_team": normalize_team(row["inn1_team"]),
        }
    return maps


def determine_flip(event: Betx21Event, winner: str, odds_records: list[dict], snapshots: list[OverSnapshot]) -> bool:
    if not snapshots:
        return False
    final_ts = max(s.timestamp for s in snapshots)
    final_p = market_r1_prob_at(odds_records, final_ts)
    if final_p is None:
        return False
    t1_won = normalize_team(winner) == event.t1
    # If runner 1 is t1, final probability should favor t1 when t1 won and oppose t1 when t1 lost.
    return (t1_won and final_p < 0.5) or ((not t1_won) and final_p > 0.5)


def compute_metrics(df: pd.DataFrame, prob_col: str, segment: str) -> dict:
    y = df["actual_inn1_wins"].astype(float).to_numpy()
    p = np.clip(df[prob_col].astype(float).to_numpy(), 1e-7, 1 - 1e-7)
    bins = np.linspace(0, 1, 11)
    idx = np.clip(np.digitize(p, bins) - 1, 0, 9)
    ece = 0.0
    for b in range(10):
        mask = idx == b
        if mask.any():
            ece += mask.sum() / len(p) * abs(p[mask].mean() - y[mask].mean())
    return {
        "segment": segment,
        "probability": prob_col,
        "n": len(df),
        "brier": float(np.mean((y - p) ** 2)),
        "ece": float(ece),
        "log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
    }


def write_report(result: pd.DataFrame, summary: pd.DataFrame, path: Path) -> None:
    lines = [
        "# IPL Latest Market vs Model Report",
        "",
        f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Matches mapped**: {result['cs_match_id'].nunique()}",
        f"**Rows**: {len(result)} end-of-over observations",
        "",
        "## Overall",
        "",
        "| Probability | N | Brier | ECE | LogLoss |",
        "|-------------|---|-------|-----|---------|",
    ]
    overall = summary[summary["segment"] == "overall"]
    for row in overall.itertuples():
        lines.append(f"| `{row.probability}` | {row.n} | {row.brier:.4f} | {row.ece:.4f} | {row.log_loss:.4f} |")

    lines += ["", "## Innings/Phase Brier vs Market", "", "| Segment | Market | Raw v6 | Iso v6 |", "|---------|--------|--------|--------|"]
    pivot = summary.pivot(index="segment", columns="probability", values="brier")
    for segment in [s for s in pivot.index if s != "overall"]:
        row = pivot.loc[segment]
        lines.append(
            f"| {segment} | {row.get('market_p_inn1', np.nan):.4f} | "
            f"{row.get('raw_p_inn1', np.nan):.4f} | {row.get('iso_p_inn1', np.nan):.4f} |"
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    betx21_dir = Path(args.betx21_dir)
    features_path = Path(args.features)
    raw_path = Path(args.raw)
    model_dir = Path(args.model_dir)

    events = discover_ipl_events(betx21_dir)
    match_map = build_match_map(raw_path, events)
    scored = load_and_score_features(features_path, model_dir)

    rows: list[dict] = []
    for event_id, event in events.items():
        if event_id not in match_map:
            continue
        score_records = []
        odds_records = []
        for score_file in sorted(betx21_dir.rglob(f"{event_id}_scores.jsonl.gz")):
            score_records.extend(safe_read_gz(score_file))
        for odds_file in sorted(betx21_dir.rglob(f"{event_id}_odds.jsonl.gz")):
            odds_records.extend(rec for rec in safe_read_gz(odds_file) if rec.get("mt") == "matchOdds")
        score_records.sort(key=lambda rec: rec.get("t", ""))
        odds_records.sort(key=lambda rec: rec.get("t", ""))

        snapshots = extract_over_snapshots(event_id, score_records)
        mapping = match_map[event_id]
        flip = determine_flip(event, mapping["winner"], odds_records, snapshots)
        t1_is_inn1 = event.t1 == mapping["inn1_team"]
        actual_inn1_wins = 1.0 if mapping["winner"] == mapping["inn1_team"] else 0.0

        match_features = scored[scored["match_id"] == mapping["cs_match_id"]]
        for snapshot in snapshots:
            market_r1 = market_r1_prob_at(odds_records, snapshot.timestamp)
            if market_r1 is None:
                continue
            if flip:
                market_r1 = 1.0 - market_r1
            market_p_inn1 = market_r1 if t1_is_inn1 else 1.0 - market_r1

            feature_row = match_features[
                (match_features["innings"].astype(int) == snapshot.innings)
                & (match_features["over_1idx"].astype(int) == snapshot.over)
            ]
            if feature_row.empty:
                continue
            feature_row = feature_row.iloc[0]
            batting_is_inn1 = normalize_team(feature_row["batting_team"]) == mapping["inn1_team"]
            raw_p_inn1 = feature_row["raw_prob_batting"] if batting_is_inn1 else 1.0 - feature_row["raw_prob_batting"]
            iso_p_inn1 = feature_row["iso_prob_batting"] if batting_is_inn1 else 1.0 - feature_row["iso_prob_batting"]
            rows.append({
                "betx21_id": event_id,
                "cs_match_id": mapping["cs_match_id"],
                "date": event.date,
                "team1": event.t1,
                "team2": event.t2,
                "inn1_team": mapping["inn1_team"],
                "winner": mapping["winner"],
                "runner_flip": flip,
                "innings": snapshot.innings,
                "over": snapshot.over,
                "phase": phase_of(snapshot.over),
                "actual_inn1_wins": actual_inn1_wins,
                "market_p_inn1": float(market_p_inn1),
                "raw_p_inn1": float(raw_p_inn1),
                "iso_p_inn1": float(iso_p_inn1),
            })

    result = pd.DataFrame(rows)
    if result.empty:
        raise SystemExit("No comparison rows produced. Check feature/raw/betx21 coverage.")

    metrics = []
    segments = [("overall", result)]
    for inn in [1, 2]:
        segments.append((f"innings_{inn}", result[result["innings"] == inn]))
        for phase in ["powerplay", "middle", "death"]:
            segments.append((f"innings_{inn}_{phase}", result[(result["innings"] == inn) & (result["phase"] == phase)]))
    for name, segment_df in segments:
        if len(segment_df) < 5:
            continue
        for col in ["market_p_inn1", "raw_p_inn1", "iso_p_inn1"]:
            metrics.append(compute_metrics(segment_df, col, name))

    summary = pd.DataFrame(metrics)
    output_path = Path(args.output)
    summary_path = Path(args.summary)
    report_path = Path(args.report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output_path, index=False)
    summary.to_csv(summary_path, index=False)
    write_report(result, summary, report_path)

    print(f"Mapped {result['cs_match_id'].nunique()} matches, {len(result)} rows")
    print(summary[summary["segment"].isin(["overall", "innings_2", "innings_2_powerplay"])].to_string(index=False))
    print(f"Wrote {output_path}, {summary_path}, {report_path}")


if __name__ == "__main__":
    main()
