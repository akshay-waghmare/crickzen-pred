from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from src.bbl_pipeline.analysis.state_embeddings.embeddings import fit_embedding_models
from src.bbl_pipeline.analysis.state_embeddings.evaluation import (
    apply_inn2_powerplay_variant,
    apply_guarded_regime_phase_calibration,
    check_go_no_go,
    fit_guarded_regime_phase_calibration,
    make_train_before_test_season_split,
    make_time_ordered_cv_splits,
    summarize_regimes,
)


def _corpus_frame() -> pd.DataFrame:
    rows = []
    for idx in range(24):
        rows.append(
            {
                "row_key": f"m{idx // 6}:{1 if idx % 2 == 0 else 2}:{(idx % 6) + 1}:6",
                "match_id": f"m{idx // 6}",
                "season": f"202{idx // 8}",
                "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=idx),
                "innings": 1 if idx % 2 == 0 else 2,
                "over": (idx % 6) + 1,
                "ball": 6,
                "batting_team": "MI",
                "bowling_team": "CSK",
                "winner": "MI" if idx % 3 else "CSK",
                "is_winner": int(idx % 3 != 0),
                "overs_remaining": float(19 - (idx % 6)),
                "resource_win_prob": 0.30 + idx * 0.01,
                "pressure_index": 0.1 + idx * 0.01,
                "acceleration_potential": 0.2 + idx * 0.02,
                "wickets_lost": idx % 5,
                "boundary_pct_last_18": 0.2 + (idx % 4) * 0.05,
                "current_run_rate": 6.0 + (idx % 6),
                "runs_last_12": 8 + idx % 5,
                "runs_last_18": 12 + idx % 6,
                "window_size_balls": min(idx, 6),
                "runs_in_window": float(idx % 7),
                "wickets_in_window": float(idx % 2),
                "boundary_rate_in_window": 0.1 + (idx % 3) * 0.1,
                "resource_delta_window": 0.01 * idx,
                "run_rate_delta_window": 0.02 * idx,
                "order_index": idx,
            }
        )
    return pd.DataFrame(rows)


def test_fit_embedding_models_covers_all_rows(tmp_path: Path):
    corpus_df = _corpus_frame()
    train_mask = np.array([True] * 18 + [False] * 6)

    assignments_df, feature_columns, explained = fit_embedding_models(corpus_df, train_mask, tmp_path, seed=42, pca_components=4, n_clusters=3)

    assert len(assignments_df) == len(corpus_df)
    assert len(feature_columns) > 0
    assert explained["pca_components"] == 4
    assert assignments_df["regime_id"].between(0, 2).all()


def test_summarize_regimes_reports_cluster_coverage(tmp_path: Path):
    corpus_df = _corpus_frame()
    train_mask = np.array([True] * 18 + [False] * 6)
    assignments_df, _, _ = fit_embedding_models(corpus_df, train_mask, tmp_path, seed=42, pca_components=3, n_clusters=3)

    summary_df = summarize_regimes(assignments_df, ["embedding_0", "embedding_1", "embedding_2"])

    assert set(summary_df.columns) >= {"regime_id", "coverage", "regime_label", "stability_flag"}
    assert round(float(summary_df["coverage"].sum()), 6) == 1.0


def test_check_go_no_go_requires_brier_and_logloss_improvement():
    metrics_df = pd.DataFrame(
        [
            {"method": "baseline_ipl_v6_features", "split": "holdout", "segment": "overall", "n": 100, "brier": 0.200, "ece": 0.020, "log_loss": 0.600},
            {"method": "regime_hybrid_features", "split": "holdout", "segment": "overall", "n": 100, "brier": 0.190, "ece": 0.019, "log_loss": 0.580},
        ]
    )
    segment_metrics_df = pd.DataFrame(
        [
            {"method": "baseline_ipl_v6_features", "split": "holdout", "segment": "innings_1", "n": 50, "brier": 0.190, "ece": 0.020, "log_loss": 0.590},
            {"method": "regime_hybrid_features", "split": "holdout", "segment": "innings_1", "n": 50, "brier": 0.189, "ece": 0.019, "log_loss": 0.585},
        ]
    )

    decision = check_go_no_go(metrics_df, segment_metrics_df, "baseline_ipl_v6_features", ["regime_hybrid_features"])

    assert decision.recommendation == "go"
    assert decision.winning_variant == "regime_hybrid_features"


def test_make_time_ordered_cv_splits_is_sequential():
    splits = make_time_ordered_cv_splits(_corpus_frame(), n_splits=4)
    assert len(splits) >= 2
    train_idx, val_idx = splits[0]
    assert train_idx.max() < val_idx.min()


def test_make_train_before_test_season_split_uses_prior_seasons_only():
    df = pd.DataFrame({"season": ["2023", "2024", "2025", "unknown", "2026"]})

    train_idx, test_idx = make_train_before_test_season_split(df, 2025)

    assert train_idx.tolist() == [0, 1]
    assert test_idx.tolist() == [2]


def test_guarded_regime_phase_calibration_skips_sparse_slices():
    df = pd.DataFrame(
        {
            "regime_id": [0] * 6 + [1] * 4,
            "innings": [1] * 10,
            "overs_remaining": [19.0] * 10,
        }
    )
    raw_probs = np.array([0.10, 0.20, 0.30, 0.40, 0.60, 0.80, 0.15, 0.25, 0.35, 0.45])
    y_true = np.array([0, 0, 0, 1, 1, 1, 0, 1, 0, 1])

    bundle, guardrails_df = fit_guarded_regime_phase_calibration(
        df=df,
        raw_probs=raw_probs,
        y_true=y_true,
        min_samples=5,
        min_unique_probs=3,
    )
    calibrated, routing_df = apply_guarded_regime_phase_calibration(df=df, raw_probs=raw_probs, bundle=bundle)

    fitted_rows = guardrails_df[guardrails_df["fit_status"] == "fitted"]
    skipped_rows = guardrails_df[guardrails_df["fit_status"] == "skipped"]

    assert len(fitted_rows) == 1
    assert fitted_rows.iloc[0]["regime_id"] == 0
    assert len(skipped_rows) == 1
    assert skipped_rows.iloc[0]["guard_reason"] == "min_samples<5"
    assert (routing_df.loc[:5, "calibration_source"] == "regime_phase").all()
    assert (routing_df.loc[6:, "calibration_source"] == "raw_fallback").all()
    assert np.allclose(calibrated[6:], raw_probs[6:])


def test_v18a_hard_pp_fallback_uses_baseline_only_in_innings2_powerplay():
    df = pd.DataFrame(
        {
            "innings": [2, 2, 1],
            "overs_remaining": [19.0, 13.0, 19.0],
            "regime_confidence": [0.8, 0.8, 0.8],
            "regime_cluster_size": [120, 120, 120],
            "stability_flag": ["stable", "stable", "stable"],
        }
    )
    baseline_probs = np.array([0.40, 0.45, 0.35])
    cluster_probs = np.array([0.70, 0.65, 0.55])

    routed, routing_df = apply_inn2_powerplay_variant(df, baseline_probs, cluster_probs, "v18A_hard_pp_fallback")

    assert np.allclose(routed, np.array([0.40, 0.65, 0.55]))
    assert routing_df["route_source"].tolist() == ["baseline_fallback", "cluster_features", "cluster_features"]


def test_v18b_confidence_cap_limits_innings2_powerplay_shift():
    df = pd.DataFrame(
        {
            "innings": [2, 2],
            "overs_remaining": [19.0, 11.0],
            "regime_confidence": [0.9, 0.9],
            "regime_cluster_size": [180, 180],
            "stability_flag": ["stable", "stable"],
        }
    )
    baseline_probs = np.array([0.40, 0.45])
    cluster_probs = np.array([0.70, 0.65])

    routed, routing_df = apply_inn2_powerplay_variant(df, baseline_probs, cluster_probs, "v18B_confidence_cap")

    assert np.allclose(routed, np.array([0.44, 0.65]))
    assert routing_df.loc[0, "route_source"] == "capped_cluster_features"
    assert routing_df.loc[1, "route_source"] == "cluster_features"


def test_v18c_uses_cluster_only_for_dominant_stable_powerplay_assignments():
    df = pd.DataFrame(
        {
            "innings": [2, 2, 2, 1],
            "overs_remaining": [19.0, 19.0, 19.0, 19.0],
            "regime_confidence": [0.80, 0.80, 0.80, 0.80],
            "regime_cluster_size": [220, 80, 220, 220],
            "stability_flag": ["stable", "stable", "borderline", "stable"],
        }
    )
    baseline_probs = np.array([0.40, 0.42, 0.44, 0.46])
    cluster_probs = np.array([0.70, 0.72, 0.74, 0.76])

    routed, routing_df = apply_inn2_powerplay_variant(df, baseline_probs, cluster_probs, "v18C_dominant_cluster_only")

    assert np.allclose(routed, np.array([0.70, 0.42, 0.44, 0.76]))
    assert routing_df["route_source"].tolist() == [
        "dominant_stable_cluster_features",
        "baseline_fallback",
        "baseline_fallback",
        "cluster_features",
    ]
