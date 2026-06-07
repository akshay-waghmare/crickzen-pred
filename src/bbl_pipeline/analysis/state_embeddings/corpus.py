from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .evaluation import build_row_key, get_phase_label
from .types import CorpusManifest

REQUIRED_INPUT_COLUMNS = [
    "innings",
    "over",
    "ball",
    "resource_win_prob",
    "overs_remaining",
    "is_winner",
]

WINDOW_FIELDS = [
    "window_size_balls",
    "window_complete",
    "runs_in_window",
    "wickets_in_window",
    "boundary_rate_in_window",
    "resource_delta_window",
    "run_rate_delta_window",
]


def load_input_and_context(
    input_path: Path,
    raw_backfill_dir: Optional[Path] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    input_df = pd.read_parquet(input_path).copy()
    input_df["_input_row_index"] = np.arange(len(input_df))

    companion_df = None
    if _needs_metadata_backfill(input_df):
        companion_path = input_path.with_name("training.parquet")
        if input_path.name == "training.parquet":
            companion_path = input_path
        if companion_path.exists():
            companion_df = pd.read_parquet(companion_path).copy()
            companion_df = _attach_match_metadata(companion_df, raw_backfill_dir)
            input_df = _merge_metadata_from_companion(input_df, companion_df)
    input_df = _attach_match_metadata(input_df, raw_backfill_dir)
    context_df = companion_df if companion_df is not None else input_df.copy()
    if "_input_row_index" not in context_df.columns:
        context_df["_input_row_index"] = np.arange(len(context_df))
    context_df = _attach_match_metadata(context_df, raw_backfill_dir)
    return input_df, context_df


def build_embedding_corpus(
    input_path: Path,
    raw_backfill_dir: Optional[Path],
    output_dir: Path,
    seed: int = 42,
    window_size_balls: int = 6,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    anchor_df, context_df = load_input_and_context(input_path, raw_backfill_dir)
    anchor_df = _prepare_core_columns(anchor_df)
    context_df = _prepare_core_columns(context_df)

    missing = [column for column in REQUIRED_INPUT_COLUMNS if column not in anchor_df.columns]
    if missing:
        raise ValueError(f"Missing required input columns: {missing}")

    exclusion_reasons = anchor_df.apply(_get_exclusion_reason, axis=1)
    anchor_df["exclusion_reason"] = exclusion_reasons
    anchor_df["eligibility_status"] = np.where(exclusion_reasons.isna(), "eligible", "excluded")
    anchor_df["source_priority"] = np.where(anchor_df["date"].notna(), "feature_row_with_raw_backfill", "feature_row")

    eligible_df = anchor_df[anchor_df["eligibility_status"] == "eligible"].copy()
    eligible_df = eligible_df.sort_values(["date", "season", "match_id", "innings", "over", "ball", "order_index"]).reset_index(drop=True)
    window_df = _build_window_records(eligible_df, context_df, window_size_balls)
    if not window_df.empty:
        eligible_df = eligible_df.merge(window_df.drop(columns=["source_row_keys"]), left_on="row_key", right_on="anchor_row_key", how="left")

    embedding_path = output_dir / "embedding_corpus.parquet"
    window_path = output_dir / "window_corpus.parquet"
    manifest_path = output_dir / "corpus_manifest.json"

    eligible_df.to_parquet(embedding_path, index=False)
    window_df.to_parquet(window_path, index=False)

    feature_columns = [
        column
        for column in eligible_df.select_dtypes(include=[np.number, "bool"]).columns
        if column not in {"is_winner", "innings", "over", "ball", "order_index"}
    ]
    manifest = CorpusManifest(
        corpus_version="ipl_state_embeddings_v1",
        input_path=str(input_path),
        raw_backfill_dir=str(raw_backfill_dir) if raw_backfill_dir else None,
        eligible_rows=int(len(eligible_df)),
        excluded_rows=int(len(anchor_df) - len(eligible_df)),
        exclusion_breakdown={key: int(value) for key, value in Counter(anchor_df["exclusion_reason"].dropna()).items()},
        feature_columns=feature_columns,
        window_fields=WINDOW_FIELDS,
        pca_components=0,
        random_seed=seed,
        fit_split_policy="time_ordered_holdout_80_20",
        source_rows=int(len(anchor_df)),
        corpus_coverage=float(len(eligible_df) / max(1, len(anchor_df))),
    ).to_dict()
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return eligible_df, window_df, manifest


def _needs_metadata_backfill(df: pd.DataFrame) -> bool:
    return any(column not in df.columns for column in ["match_id", "season", "over", "ball", "batting_team", "bowling_team", "winner"])


def _prepare_core_columns(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    if "_input_row_index" not in output.columns:
        output["_input_row_index"] = np.arange(len(output))
    if "match_id" not in output.columns:
        output["match_id"] = output["_input_row_index"].astype(str)
    output["match_id"] = output["match_id"].astype(str)
    for column in ["innings", "over", "ball"]:
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0).astype(int)
    output["season"] = output.get("season", "unknown").fillna("unknown").astype(str)
    output["date"] = pd.to_datetime(output.get("date"), errors="coerce")
    output["venue"] = output.get("venue", pd.Series([None] * len(output))).astype(object)
    output["batting_team"] = output.get("batting_team", pd.Series(["unknown"] * len(output))).astype(str)
    output["bowling_team"] = output.get("bowling_team", pd.Series(["unknown"] * len(output))).astype(str)
    output["winner"] = output.get("winner", pd.Series([None] * len(output))).astype(object)
    output["row_key"] = [
        build_row_key(match_id, innings, over, ball)
        for match_id, innings, over, ball in zip(output["match_id"], output["innings"], output["over"], output["ball"])
    ]
    output["order_index"] = np.arange(len(output))
    output["phase_label"] = output["overs_remaining"].map(get_phase_label) if "overs_remaining" in output.columns else "unknown"
    return output.sort_values(["date", "season", "match_id", "innings", "over", "ball", "_input_row_index"]).reset_index(drop=True)


def _merge_metadata_from_companion(sample_df: pd.DataFrame, companion_df: pd.DataFrame) -> pd.DataFrame:
    metadata_columns = [column for column in ["match_id", "season", "over", "ball", "batting_team", "bowling_team", "winner"] if column in companion_df.columns]
    shared_columns = [column for column in sample_df.columns if column in companion_df.columns and column not in metadata_columns + ["_input_row_index"]]
    if not shared_columns or not metadata_columns:
        return sample_df

    sample = sample_df.copy()
    companion = companion_df.copy()
    sample["_join_hash"] = pd.util.hash_pandas_object(sample[shared_columns], index=False).astype(str)
    companion["_join_hash"] = pd.util.hash_pandas_object(companion[shared_columns], index=False).astype(str)
    sample["_hash_rank"] = sample.groupby("_join_hash").cumcount()
    companion["_hash_rank"] = companion.groupby("_join_hash").cumcount()
    merged = sample.merge(
        companion[["_join_hash", "_hash_rank", *metadata_columns]],
        on=["_join_hash", "_hash_rank"],
        how="left",
        suffixes=("", "_ctx"),
    )
    merged = merged.drop(columns=["_join_hash", "_hash_rank"])
    return merged


def _attach_match_metadata(df: pd.DataFrame, raw_backfill_dir: Optional[Path]) -> pd.DataFrame:
    output = df.copy()
    if "match_id" not in output.columns:
        return output
    match_ids = {str(match_id) for match_id in output["match_id"].dropna().astype(str).unique().tolist()}
    metadata = _load_match_metadata(match_ids, raw_backfill_dir)
    if not metadata:
        return output

    metadata_df = pd.DataFrame.from_dict(metadata, orient="index").reset_index().rename(columns={"index": "match_id"})
    output["match_id"] = output["match_id"].astype(str)
    output = output.merge(metadata_df, on="match_id", how="left", suffixes=("", "_backfill"))
    for column in ["date", "venue", "season"]:
        backfill_column = f"{column}_backfill"
        if backfill_column not in output.columns:
            continue
        if column in output.columns:
            output[column] = output[column].where(output[column].notna(), output[backfill_column])
        else:
            output[column] = output[backfill_column]
        output = output.drop(columns=[backfill_column])
    return output


def _load_match_metadata(match_ids: Iterable[str], raw_backfill_dir: Optional[Path]) -> Dict[str, Dict[str, object]]:
    metadata: Dict[str, Dict[str, object]] = {}
    if raw_backfill_dir and raw_backfill_dir.exists():
        for parquet_path in sorted(raw_backfill_dir.glob("*.parquet")):
            stem = parquet_path.stem
            if stem not in match_ids:
                continue
            try:
                raw_df = pd.read_parquet(parquet_path)
                if raw_df.empty:
                    continue
                first_row = raw_df.iloc[0]
                metadata[stem] = {
                    "date": first_row.get("date"),
                    "venue": first_row.get("venue"),
                    "season": str(first_row.get("season") or pd.to_datetime(first_row.get("date"), errors="coerce").year or "unknown"),
                }
            except Exception:
                continue

    candidate_json_dir = None
    if raw_backfill_dir and raw_backfill_dir.exists():
        json_dir = raw_backfill_dir.parent.parent / "ipl_male_json"
        if json_dir.exists():
            candidate_json_dir = json_dir
    if candidate_json_dir is None:
        repo_root = Path(__file__).resolve().parents[4]
        json_dir = repo_root / "ipl_male_json"
        if json_dir.exists():
            candidate_json_dir = json_dir
    if candidate_json_dir is None:
        return metadata

    for match_id in match_ids:
        if match_id in metadata:
            continue
        json_path = candidate_json_dir / f"{match_id}.json"
        if not json_path.exists():
            continue
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            info = payload.get("info", {})
            dates = info.get("dates") or []
            metadata[match_id] = {
                "date": dates[0] if dates else None,
                "venue": info.get("venue"),
                "season": str(info.get("season") or dates[0][:4] if dates else "unknown"),
            }
        except Exception:
            continue
    return metadata


def _get_exclusion_reason(row: pd.Series) -> Optional[str]:
    if int(row.get("innings", 0)) not in (1, 2):
        return "invalid_innings"
    if int(row.get("over", 0)) <= 0 or int(row.get("ball", 0)) <= 0 or int(row.get("ball", 0)) > 6:
        return "invalid_ball_context"
    if int(row.get("over", 0)) > 20:
        return "non_standard_match"
    if float(row.get("overs_remaining", 0.0)) <= 0:
        return "terminal_no_balls_remaining"
    if pd.isna(row.get("match_id")) or pd.isna(row.get("winner")):
        return "missing_match_context"
    return None


def _estimate_score(row: pd.Series) -> float:
    overs_done = max(0.0, 20.0 - float(row.get("overs_remaining", 0.0)))
    return float(row.get("current_run_rate", 0.0)) * overs_done


def _build_window_records(anchor_df: pd.DataFrame, context_df: pd.DataFrame, window_size_balls: int) -> pd.DataFrame:
    if anchor_df.empty:
        return pd.DataFrame(columns=["window_id", "anchor_row_key", "window_size_balls", "source_row_keys", *WINDOW_FIELDS])

    context_lookup = {}
    ordered_context = context_df.sort_values(["date", "season", "match_id", "innings", "over", "ball", "order_index"]).reset_index(drop=True)
    for _, row in ordered_context.iterrows():
        context_lookup.setdefault((row["match_id"], int(row["innings"])), []).append(row)

    rows: List[dict] = []
    for _, anchor in anchor_df.iterrows():
        key = (anchor["match_id"], int(anchor["innings"]))
        candidates = context_lookup.get(key, [])
        anchor_position = next((idx for idx, row in enumerate(candidates) if row["row_key"] == anchor["row_key"]), None)
        if anchor_position is None:
            continue
        source_rows = candidates[max(0, anchor_position - window_size_balls) : anchor_position]
        if source_rows:
            first_row = source_rows[0]
            runs_in_window = max(0.0, _estimate_score(anchor) - _estimate_score(first_row))
            wickets_in_window = max(0.0, float(anchor.get("wickets_lost", 0.0)) - float(first_row.get("wickets_lost", 0.0)))
            resource_delta = float(anchor.get("resource_win_prob", 0.0)) - float(first_row.get("resource_win_prob", 0.0))
            run_rate_delta = float(anchor.get("current_run_rate", 0.0)) - float(first_row.get("current_run_rate", 0.0))
            boundary_rate = float(np.mean([float(row.get("boundary_pct_last_18", 0.0)) for row in source_rows]))
        else:
            runs_in_window = 0.0
            wickets_in_window = 0.0
            resource_delta = 0.0
            run_rate_delta = 0.0
            boundary_rate = 0.0
        rows.append(
            {
                "window_id": f"{anchor['row_key']}:w{window_size_balls}",
                "anchor_row_key": anchor["row_key"],
                "window_size_balls": int(len(source_rows)),
                "source_row_keys": [row["row_key"] for row in source_rows],
                "window_complete": bool(len(source_rows) == window_size_balls),
                "runs_in_window": float(runs_in_window),
                "wickets_in_window": float(wickets_in_window),
                "boundary_rate_in_window": float(boundary_rate),
                "resource_delta_window": float(resource_delta),
                "run_rate_delta_window": float(run_rate_delta),
            }
        )
    return pd.DataFrame(rows)
