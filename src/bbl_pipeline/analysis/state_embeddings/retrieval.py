from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors


def _same_or_future_row(query_row: pd.Series, neighbor_row: pd.Series) -> bool:
    if str(query_row["match_id"]) != str(neighbor_row["match_id"]):
        return False
    query_tuple = (int(query_row["innings"]), int(query_row["over"]), int(query_row["ball"]))
    neighbor_tuple = (int(neighbor_row["innings"]), int(neighbor_row["over"]), int(neighbor_row["ball"]))
    return neighbor_tuple >= query_tuple


def query_historical_analogues(
    assignments_df: pd.DataFrame,
    output_dir: Path,
    top_k: int = 25,
    query_mask: np.ndarray | None = None,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    embedding_columns = [column for column in assignments_df.columns if column.startswith("embedding_")]
    if not embedding_columns:
        raise ValueError("Assignments DataFrame must contain embedding columns")

    source_df = assignments_df.reset_index(drop=True).copy()
    if query_mask is None:
        query_mask = np.ones(len(source_df), dtype=bool)
    else:
        query_mask = np.asarray(query_mask, dtype=bool)

    max_neighbors = min(len(source_df), max(top_k * 4, top_k + 5))
    neighbors = NearestNeighbors(n_neighbors=max_neighbors, metric="euclidean", algorithm="auto", n_jobs=-1)
    neighbors.fit(source_df[embedding_columns].to_numpy(dtype=float))
    joblib.dump(neighbors, output_dir / "neighbors.joblib")

    query_df = source_df.loc[query_mask].reset_index()
    distances, indices = neighbors.kneighbors(query_df[embedding_columns].to_numpy(dtype=float))

    rows: List[dict] = []
    filtered_for_leakage = 0
    covered = 0
    for query_pos, (_, query_row) in enumerate(query_df.iterrows()):
        rank = 1
        seen_event_keys = set()
        for distance, neighbor_index in zip(distances[query_pos], indices[query_pos]):
            neighbor_row = source_df.iloc[int(neighbor_index)]
            if str(neighbor_row["row_key"]) == str(query_row["row_key"]):
                filtered_for_leakage += 1
                continue
            if int(neighbor_row["order_index"]) >= int(query_row["order_index"]):
                filtered_for_leakage += 1
                continue
            if _same_or_future_row(query_row, neighbor_row):
                filtered_for_leakage += 1
                continue
            event_key = f"{neighbor_row['match_id']}:{neighbor_row['innings']}:{neighbor_row['over']}:{neighbor_row['ball']}"
            if event_key in seen_event_keys:
                filtered_for_leakage += 1
                continue
            seen_event_keys.add(event_key)
            rows.append(
                {
                    "query_row_key": query_row["row_key"],
                    "neighbor_row_key": neighbor_row["row_key"],
                    "rank": rank,
                    "distance": float(distance),
                    "query_match_id": query_row["match_id"],
                    "query_innings": int(query_row["innings"]),
                    "query_over": int(query_row["over"]),
                    "query_ball": int(query_row["ball"]),
                    "neighbor_match_id": neighbor_row["match_id"],
                    "neighbor_innings": int(neighbor_row["innings"]),
                    "neighbor_over": int(neighbor_row["over"]),
                    "neighbor_ball": int(neighbor_row["ball"]),
                    "neighbor_is_winner": int(neighbor_row["is_winner"]),
                    "neighbor_resource_win_prob": float(neighbor_row["resource_win_prob"]),
                    "neighbor_regime_id": int(neighbor_row["regime_id"]),
                    "leakage_filter_applied": True,
                    "query_role": query_row.get("fit_role", "unknown"),
                }
            )
            rank += 1
            if rank > top_k:
                covered += 1
                break

    results_df = pd.DataFrame(rows)
    if not results_df.empty:
        results_df.to_parquet(output_dir / "analogue_results.parquet", index=False)

    summary = {
        "queries": int(query_mask.sum()),
        "queries_with_results": int(covered if covered else results_df["query_row_key"].nunique() if not results_df.empty else 0),
        "coverage": float(
            (covered if covered else results_df["query_row_key"].nunique() if not results_df.empty else 0) / max(1, int(query_mask.sum()))
        ),
        "filtered_for_leakage": int(filtered_for_leakage),
        "top_k": int(top_k),
    }
    (output_dir / "retrieval_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return results_df, summary


def build_analogue_features(results_df: pd.DataFrame, top_k: int = 25) -> pd.DataFrame:
    if results_df.empty:
        return pd.DataFrame(
            columns=[
                "row_key",
                "neighbor_win_rate_k",
                "neighbor_outcome_std_k",
                "neighbor_mean_resource_prob_k",
                "neighbor_distance_mean_k",
            ]
        )
    limited = results_df[results_df["rank"] <= top_k].copy()
    grouped = (
        limited.groupby("query_row_key")
        .agg(
            neighbor_win_rate_k=("neighbor_is_winner", "mean"),
            neighbor_outcome_std_k=("neighbor_is_winner", lambda values: float(np.std(values))),
            neighbor_mean_resource_prob_k=("neighbor_resource_win_prob", "mean"),
            neighbor_distance_mean_k=("distance", "mean"),
        )
        .reset_index()
        .rename(columns={"query_row_key": "row_key"})
    )
    return grouped
