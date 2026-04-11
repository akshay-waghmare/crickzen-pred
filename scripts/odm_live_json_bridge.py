from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

from bbl_pipeline.features.format_config import FormatConfig
from bbl_pipeline.features.store import InMemoryFeatureStore
from bbl_pipeline.inference.odds_direction_model import OddsDirectionModel


def _load_json(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _history_path(input_json: Path) -> Path:
    return input_json.with_name(f"{input_json.stem}_odm_history.json")


def _load_history(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_history(path: Path, history: List[Dict[str, Any]]) -> None:
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(history[-200:], indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _snapshot_key(item: Dict[str, Any]) -> Tuple[Any, Any, Any]:
    return (item.get("innings"), item.get("over"), item.get("ball"))


def _append_distinct_snapshot(history: List[Dict[str, Any]], live: Dict[str, Any]) -> List[Dict[str, Any]]:
    snapshot = {
        "innings": 2 if live.get("is_second_innings") else 1,
        "over": live.get("over"),
        "ball": live.get("ball"),
        "bat_prob": live.get("bat_win_prob"),
        "raw_win_prob": live.get("raw_win_prob", live.get("bat_win_prob")),
        "resource_win_prob": (live.get("features") or {}).get("resource_win_prob", 0.0),
        "score": live.get("score"),
        "wickets": live.get("wickets"),
        "batting_team": live.get("batting_team"),
        "bowling_team": live.get("bowling_team"),
        "timestamp": live.get("timestamp"),
    }
    if history and _snapshot_key(history[-1]) == _snapshot_key(snapshot):
        history[-1] = snapshot
    else:
        history.append(snapshot)
    return history


def main() -> None:
    parser = argparse.ArgumentParser(description="Continuously enrich live predictor JSON with ODM advisory.")
    parser.add_argument("--input-json", required=True, help="Live predictor JSON file to enrich")
    parser.add_argument("--output-json", default=None, help="Optional output JSON path for enriched live state")
    parser.add_argument("--feature-store-dir", required=True, help="Feature store directory for team/venue stats")
    parser.add_argument("--league", required=True, help="League code, e.g. ipl or psl")
    parser.add_argument("--odm-model-dir", default="models/odm_v1", help="ODM model directory")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Refresh interval in seconds")
    args = parser.parse_args()

    input_json = Path(args.input_json)
    output_json = Path(args.output_json) if args.output_json else input_json
    history_json = _history_path(input_json)
    model = OddsDirectionModel.load(args.odm_model_dir)

    feature_store = InMemoryFeatureStore(
        Path(args.feature_store_dir) / "player_stats.parquet",
        Path(args.feature_store_dir) / "venue_stats.parquet",
    )
    feature_store.load()
    predictor = SimpleNamespace(
        feature_store=feature_store,
        format_config=FormatConfig.from_league(args.league),
    )

    print(f"[ODM-BRIDGE] Watching {input_json}")
    print(f"[ODM-BRIDGE] Writing enriched state to {output_json}")
    print(f"[ODM-BRIDGE] Model status: {model.status}")

    while True:
        live = _load_json(input_json)
        if not live or not isinstance(live.get("features"), dict):
            time.sleep(args.poll_interval)
            continue

        history = _load_history(history_json)
        history = _append_distinct_snapshot(history, live)
        _save_history(history_json, history)

        row = model._build_feature_row(
            live_features=live["features"],
            predictor=predictor,
            batting_team=live.get("batting_team", ""),
            venue=live.get("venue") or "Unknown",
            league=live.get("league") or args.league,
            innings=2 if live.get("is_second_innings") else 1,
            over=int(live.get("over", 0) or 0),
            ball=int(live.get("ball", 0) or 0),
            target_score=live.get("target"),
            current_ml_prob=float(live.get("raw_win_prob", live.get("bat_win_prob", 0.0)) or 0.0),
            history=history,
        )
        missing = [column for column in (model.feature_columns or []) if column not in row]

        odm = model.predict(
            live_features=live["features"],
            predictor=predictor,
            batting_team=live.get("batting_team", ""),
            bowling_team=live.get("bowling_team", ""),
            venue=live.get("venue") or "Unknown",
            league=live.get("league") or args.league,
            innings=2 if live.get("is_second_innings") else 1,
            over=int(live.get("over", 0) or 0),
            ball=int(live.get("ball", 0) or 0),
            target_score=live.get("target"),
            current_ml_prob=float(live.get("raw_win_prob", live.get("bat_win_prob", 0.0)) or 0.0),
            history=history,
        )

        live["odm"] = odm
        live["odm_feature_audit"] = {
            "feature_count": len(model.feature_columns or []),
            "missing_count": len(missing),
            "missing_columns": missing,
            "history_points": len(history),
        }
        _write_json(output_json, live)
        time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
