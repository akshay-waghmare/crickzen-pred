from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from src.bbl_pipeline.analysis.state_embeddings.retrieval import build_analogue_features, query_historical_analogues


def _assignments_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "row_key": "m1:1:1:1",
                "match_id": "m1",
                "innings": 1,
                "over": 1,
                "ball": 1,
                "order_index": 0,
                "resource_win_prob": 0.40,
                "is_winner": 1,
                "regime_id": 0,
                "fit_role": "train",
                "embedding_0": 0.00,
                "embedding_1": 0.00,
            },
            {
                "row_key": "m1:1:2:1",
                "match_id": "m1",
                "innings": 1,
                "over": 2,
                "ball": 1,
                "order_index": 1,
                "resource_win_prob": 0.42,
                "is_winner": 1,
                "regime_id": 0,
                "fit_role": "train",
                "embedding_0": 0.02,
                "embedding_1": 0.01,
            },
            {
                "row_key": "m2:1:1:1",
                "match_id": "m2",
                "innings": 1,
                "over": 1,
                "ball": 1,
                "order_index": 2,
                "resource_win_prob": 0.60,
                "is_winner": 0,
                "regime_id": 1,
                "fit_role": "validation",
                "embedding_0": 0.01,
                "embedding_1": 0.00,
            },
        ]
    )


def test_query_historical_analogues_excludes_self_and_future(tmp_path: Path):
    assignments = _assignments_frame()
    query_mask = np.array([False, False, True])

    results_df, summary = query_historical_analogues(assignments, tmp_path, top_k=2, query_mask=query_mask)

    assert summary["coverage"] == 1.0
    assert list(results_df["query_row_key"].unique()) == ["m2:1:1:1"]
    assert "m2:1:1:1" not in set(results_df["neighbor_row_key"])
    assert set(results_df["neighbor_row_key"]) == {"m1:1:1:1", "m1:1:2:1"}
    assert list(results_df["rank"]) == [1, 2]


def test_build_analogue_features_aggregates_top_k():
    results_df = pd.DataFrame(
        [
            {"query_row_key": "a", "rank": 1, "neighbor_is_winner": 1, "neighbor_resource_win_prob": 0.4, "distance": 0.1},
            {"query_row_key": "a", "rank": 2, "neighbor_is_winner": 0, "neighbor_resource_win_prob": 0.6, "distance": 0.3},
        ]
    )

    features_df = build_analogue_features(results_df, top_k=2)

    assert list(features_df["row_key"]) == ["a"]
    assert round(float(features_df.loc[0, "neighbor_win_rate_k"]), 3) == 0.5
    assert round(float(features_df.loc[0, "neighbor_mean_resource_prob_k"]), 3) == 0.5
