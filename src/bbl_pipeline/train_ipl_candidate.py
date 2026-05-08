from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parsed = json.loads(line)
        if not isinstance(parsed, dict):
            raise ValueError(f"invalid fixture row in {path}: expected object")
        rows.append(parsed)
    return rows


def _normalize_fixture_row(row: dict[str, Any]) -> dict[str, Any]:
    match_state = row.get("match_state")
    if match_state is None:
        return row
    if not isinstance(match_state, dict):
        raise ValueError("fixture row match_state must be an object")
    normalized = dict(match_state)
    normalized["case_id"] = row.get("case_id")
    return normalized


def _validate_fixture_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    required_fields = (
        "case_id",
        "match_id",
        "venue",
        "batting_team",
        "bowling_team",
        "innings_num",
        "over_number",
        "ball_number",
        "total_score",
        "total_wickets",
        "batsman1_name",
        "batsman2_name",
        "bowler1_name",
    )
    for row in rows:
        row = _normalize_fixture_row(row)
        missing = [field for field in required_fields if field not in row]
        if missing:
            raise ValueError(f"fixture row missing required fields: {', '.join(missing)}")
        validated.append(row)
    return validated


def _write_predictions(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = "\n".join(json.dumps(row, separators=(",", ":"), sort_keys=True) for row in rows) + "\n"
    path.write_text(serialized, encoding="utf-8")


def _build_match_state(row: dict[str, Any]) -> MatchState:
    return MatchState(
        match_id=str(row["match_id"]),
        venue=str(row["venue"]),
        batting_team=str(row["batting_team"]),
        bowling_team=str(row["bowling_team"]),
        innings=int(row["innings_num"]),
        over=int(row["over_number"]),
        ball=int(row["ball_number"]),
        current_score=int(row["total_score"]),
        wickets_lost=int(row["total_wickets"]),
        batsman_1=str(row["batsman1_name"]),
        batsman_2=str(row["batsman2_name"]),
        bowler=str(row["bowler1_name"]),
        target_runs=int(row["target_score"]) if row.get("target_score") is not None else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="StartupOS bounded IPL candidate wrapper")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--artifact", type=str, required=True)
    parser.add_argument("--fixtures-file", type=str)
    parser.add_argument("--predictions-out", type=str)
    parser.add_argument("--model-dir", type=str, default="models/t20_male_v2")
    parser.add_argument("--feature-store-dir", type=str, default="data/bbl_feature_store_v2")
    parser.add_argument("--league", type=str, default="ipl")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    model_dir = (repo_root / args.model_dir).resolve()
    feature_store_dir = (repo_root / args.feature_store_dir).resolve()
    artifact_path = Path(args.artifact).resolve()

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    champion_model = model_dir / "champion_model.joblib"
    if not champion_model.is_file():
        raise FileNotFoundError(f"champion model not found at {champion_model}")

    # Bounded artifact creation using the repo's real model artifact.
    shutil.copy2(champion_model, artifact_path)

    # If StartupOS has not been extended to pass fixtures/predictions, stop here.
    # This preserves a truthful boundary: artifact copy is real, but real inference
    # requires structured match-state fixtures and an explicit predictions output path.
    if not args.fixtures_file or not args.predictions_out:
        return 0

    fixtures_path = Path(args.fixtures_file).resolve()
    predictions_path = Path(args.predictions_out).resolve()
    if not fixtures_path.is_file():
        raise FileNotFoundError(f"fixtures file not found at {fixtures_path}")

    rows = _validate_fixture_rows(_load_jsonl(fixtures_path))
    predictor = Predictor.load(model_dir=model_dir, feature_store_dir=feature_store_dir, league=args.league)

    predictions: list[dict[str, str]] = []
    for row in rows:
        probability = float(predictor.predict(_build_match_state(row)))
        predictions.append(
            {
                "case_id": str(row["case_id"]),
                "output": f"{probability:.6f}",
            }
        )

    _write_predictions(predictions_path, predictions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
