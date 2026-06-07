from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from src.bbl_pipeline.analysis.state_embeddings.corpus import (
    _merge_metadata_from_companion,
    _prepare_core_columns,
    build_embedding_corpus,
)


def _base_training_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "current_run_rate": 7.0,
                "overs_remaining": 19.0,
                "resource_win_prob": 0.45,
                "innings": 1,
                "over": 1,
                "ball": 1,
                "wickets_lost": 0,
                "boundary_pct_last_18": 0.20,
                "is_winner": 1,
                "match_id": "1001",
                "season": "2024",
                "batting_team": "MI",
                "bowling_team": "CSK",
                "winner": "MI",
            },
            {
                "current_run_rate": 8.0,
                "overs_remaining": 18.0,
                "resource_win_prob": 0.48,
                "innings": 1,
                "over": 2,
                "ball": 6,
                "wickets_lost": 0,
                "boundary_pct_last_18": 0.25,
                "is_winner": 1,
                "match_id": "1001",
                "season": "2024",
                "batting_team": "MI",
                "bowling_team": "CSK",
                "winner": "MI",
            },
            {
                "current_run_rate": 9.0,
                "overs_remaining": 17.0,
                "resource_win_prob": 0.55,
                "innings": 1,
                "over": 3,
                "ball": 6,
                "wickets_lost": 1,
                "boundary_pct_last_18": 0.30,
                "is_winner": 1,
                "match_id": "1001",
                "season": "2024",
                "batting_team": "MI",
                "bowling_team": "CSK",
                "winner": "MI",
            },
            {
                "current_run_rate": 8.5,
                "overs_remaining": 16.0,
                "resource_win_prob": 0.52,
                "innings": 2,
                "over": 4,
                "ball": 6,
                "wickets_lost": 2,
                "boundary_pct_last_18": 0.28,
                "is_winner": 0,
                "match_id": "1002",
                "season": "2024",
                "batting_team": "RCB",
                "bowling_team": "KKR",
                "winner": "KKR",
            },
        ]
    )


def test_merge_metadata_from_companion_backfills_sampled_rows():
    full_df = _base_training_frame()
    sampled_df = full_df.drop(columns=["match_id", "season", "over", "ball", "batting_team", "bowling_team", "winner"]).iloc[[1, 2]].reset_index(drop=True)

    merged = _merge_metadata_from_companion(sampled_df, full_df)

    assert list(merged["match_id"]) == ["1001", "1001"]
    assert list(merged["over"]) == [2, 3]
    assert list(merged["ball"]) == [6, 6]


def test_prepare_core_columns_creates_stable_row_keys():
    prepared = _prepare_core_columns(_base_training_frame())
    assert prepared.loc[0, "row_key"] == "1001:1:1:1"
    assert prepared.loc[1, "row_key"] == "1001:1:2:6"


def test_build_embedding_corpus_writes_manifest_and_windows(tmp_path: Path):
    feature_dir = tmp_path / "data" / "ipl_features_v6"
    feature_dir.mkdir(parents=True)
    output_dir = tmp_path / "experiments" / "ipl_state_embeddings_v1" / "corpus"
    training_df = _base_training_frame()
    sampled_df = training_df.drop(columns=["match_id", "season", "over", "ball", "batting_team", "bowling_team", "winner"]).iloc[[1, 2]].reset_index(drop=True)

    training_df.to_parquet(feature_dir / "training.parquet", index=False)
    sampled_df.to_parquet(feature_dir / "training_sampled.parquet", index=False)

    raw_json_dir = tmp_path / "ipl_male_json"
    raw_json_dir.mkdir()
    (raw_json_dir / "1001.json").write_text(
        json.dumps({"info": {"dates": ["2024-04-01"], "venue": "Wankhede", "season": "2024"}}),
        encoding="utf-8",
    )

    corpus_df, window_df, manifest = build_embedding_corpus(
        input_path=feature_dir / "training_sampled.parquet",
        raw_backfill_dir=tmp_path / "data" / "ipl_raw" / "matches",
        output_dir=output_dir,
        seed=42,
        window_size_balls=2,
    )

    assert (output_dir / "embedding_corpus.parquet").exists()
    assert (output_dir / "window_corpus.parquet").exists()
    assert (output_dir / "corpus_manifest.json").exists()
    assert len(corpus_df) == 2
    assert len(window_df) == 2
    assert manifest["eligible_rows"] == 2
    assert bool(window_df.iloc[0]["window_complete"]) is False
    assert bool(window_df.iloc[1]["window_complete"]) is True
