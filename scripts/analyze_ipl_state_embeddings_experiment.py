"""
IPL state embeddings experiment (spec: 016-ipl-state-embeddings).

Offline IPL-only pilot that:
1. Builds a leakage-aware corpus from IPL v6 feature rows.
2. Fits train-only PCA + KMeans regimes.
3. Retrieves historical analogues with time-order leakage guards.
4. Compares regime-aware feature variants vs the current IPL baseline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from bbl_pipeline.analysis.state_embeddings import (
    add_reference_deltas,
    add_baseline_deltas,
    apply_inn2_powerplay_variant,
    apply_guarded_regime_phase_calibration,
    build_analogue_features,
    build_embedding_corpus,
    build_regime_feature_frame,
    check_go_no_go,
    collect_reliability_bins,
    collect_segment_metrics,
    fit_guarded_regime_phase_calibration,
    fit_embedding_models,
    get_phase_label,
    make_train_before_test_season_split,
    make_time_ordered_holdout_split,
    query_historical_analogues,
    render_pilot_report,
    summarize_guarded_regime_phase_calibration,
    summarize_regimes,
)
from bbl_pipeline.training.trainer import XGBLogRegEnsemble

CORPUS_DIRNAME = "corpus"
MODELS_DIRNAME = "models"
REGIMES_DIRNAME = "regimes"
RETRIEVAL_DIRNAME = "retrieval"
FEATURES_DIRNAME = "features"
EVALUATION_DIRNAME = "evaluation"

BASELINE_VARIANT = "baseline_ipl_v6_features"
CLUSTER_WINNER_VARIANT = "regime_cluster_features"
POWERPLAY_DIAGNOSTIC_VARIANT = CLUSTER_WINNER_VARIANT
GUARDED_CALIBRATION_VARIANT = "guarded_regime_phase_calibration"
V18A_VARIANT = "v18A_hard_pp_fallback"
V18B_VARIANT = "v18B_confidence_cap"
V18C_VARIANT = "v18C_dominant_cluster_only"
CONSERVATIVE_V18_VARIANTS = [V18A_VARIANT, V18B_VARIANT, V18C_VARIANT]
POWERPLAY_RECENT_SEASONS = ("2025", "2026")
CANDIDATE_VARIANTS = [
    "regime_retrieval_features",
    CLUSTER_WINNER_VARIANT,
    *CONSERVATIVE_V18_VARIANTS,
    "regime_hybrid_features",
    GUARDED_CALIBRATION_VARIANT,
]
SEASON_SLICE_VARIANTS = [
    BASELINE_VARIANT,
    CLUSTER_WINNER_VARIANT,
    *CONSERVATIVE_V18_VARIANTS,
    GUARDED_CALIBRATION_VARIANT,
]
SEASON_SLICE_YEARS = [2024, 2025, 2026]
REGIME_CALIBRATION_MIN_SAMPLES = 200
REGIME_CALIBRATION_MIN_UNIQUE_PROBS = 10

RETRIEVAL_FEATURE_COLUMNS = [
    "neighbor_win_rate_k",
    "neighbor_outcome_std_k",
    "neighbor_mean_resource_prob_k",
    "neighbor_distance_mean_k",
]
CLUSTER_FEATURE_COLUMNS = [
    "regime_id",
    "regime_confidence",
    "regime_cluster_win_rate",
    "regime_cluster_size",
]
PREDICTION_EXPORT_COLUMNS = [
    "row_key",
    "match_id",
    "season",
    "date",
    "innings",
    "over",
    "ball",
    "phase_label",
    "batting_team",
    "bowling_team",
    "winner",
    "is_winner",
    "overs_remaining",
    "resource_win_prob",
    "regime_id",
    "regime_label",
    "stability_flag",
    "regime_confidence",
    "regime_cluster_win_rate",
    "regime_cluster_size",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IPL state embeddings offline experiment")
    parser.add_argument("--input", required=True, help="Input parquet file")
    parser.add_argument("--raw-backfill-dir", required=False, help="Raw backfill directory", default=None)
    parser.add_argument("--output-dir", required=True, help="Output artifact directory")
    parser.add_argument("--mode", choices=["pilot", "full"], default="pilot")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--pca-components", type=int, default=12)
    parser.add_argument("--n-clusters", type=int, default=6)
    parser.add_argument("--top-k", type=int, default=25)
    return parser.parse_args()


def _stage_manifest_path(output_dir: Path) -> Path:
    return output_dir / "stage_manifest.json"


def _load_stage_manifest(output_dir: Path) -> Dict[str, dict]:
    path = _stage_manifest_path(output_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_stage_manifest(output_dir: Path, manifest: Dict[str, dict]) -> None:
    _stage_manifest_path(output_dir).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _baseline_and_feature_orders() -> Dict[str, List[str]]:
    baseline = list(XGBLogRegEnsemble.TOP_FEATURES)
    return {
        BASELINE_VARIANT: baseline,
        "regime_retrieval_features": [*RETRIEVAL_FEATURE_COLUMNS, *baseline],
        "regime_cluster_features": [*CLUSTER_FEATURE_COLUMNS, *baseline],
        "regime_hybrid_features": [*RETRIEVAL_FEATURE_COLUMNS, *CLUSTER_FEATURE_COLUMNS, *baseline],
    }


def _model_for_variant(variant: str) -> XGBLogRegEnsemble:
    feature_order = _baseline_and_feature_orders()[variant]
    return XGBLogRegEnsemble(
        n_features=min(len(feature_order), 64),
        feature_order=feature_order,
        xgb_params={
            "n_estimators": 180,
            "max_depth": 5,
            "learning_rate": 0.04,
            "subsample": 0.85,
            "colsample_bytree": 0.9,
            "tree_method": "hist",
            "random_state": 42,
            "verbosity": 0,
        },
    )


def _prepare_evaluation_frame(
    corpus_df: pd.DataFrame,
    feature_df: pd.DataFrame,
) -> pd.DataFrame:
    feature_payload = feature_df[[column for column in feature_df.columns if column == "row_key" or column not in corpus_df.columns]].copy()
    merged = corpus_df.merge(feature_payload, on="row_key", how="left")
    for column in RETRIEVAL_FEATURE_COLUMNS:
        merged[column] = merged[column].fillna(merged[column].median() if merged[column].notna().any() else 0.0)
    for column in CLUSTER_FEATURE_COLUMNS:
        merged[column] = merged[column].fillna(0.0)
    if "phase_label" not in merged.columns:
        merged["phase_label"] = [get_phase_label(value) for value in merged["overs_remaining"].astype(float).to_numpy()]
    return merged


def _add_reference_delta_columns(metrics_df: pd.DataFrame) -> pd.DataFrame:
    if metrics_df.empty:
        return metrics_df

    output_df = pd.DataFrame(
        add_baseline_deltas(
            metrics_df.to_dict("records"),
            metrics_df[metrics_df["method"] == BASELINE_VARIANT].to_dict("records"),
        )
    )
    if CLUSTER_WINNER_VARIANT in output_df["method"].unique():
        output_df = pd.DataFrame(
            add_reference_deltas(
                output_df.to_dict("records"),
                output_df[output_df["method"] == CLUSTER_WINNER_VARIANT].to_dict("records"),
                "cluster_winner",
            )
        )
    return output_df


def _build_prediction_frame(
    prediction_base_df: pd.DataFrame,
    variant: str,
    split_name: str,
    y_true: np.ndarray,
    predicted_prob: np.ndarray,
    raw_prob: np.ndarray | None = None,
    routing_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    variant_predictions = prediction_base_df.reset_index(drop=True).copy()
    predicted_arr = np.asarray(predicted_prob, dtype=float)
    variant_predictions["method"] = variant
    variant_predictions["split"] = split_name
    variant_predictions["predicted_prob"] = predicted_arr
    variant_predictions["predicted_label"] = (predicted_arr >= 0.5).astype(int)
    variant_predictions["prediction_error"] = np.abs(predicted_arr - np.asarray(y_true, dtype=float))
    variant_predictions["correct"] = variant_predictions["predicted_label"].to_numpy() == np.asarray(y_true, dtype=int)
    variant_predictions["raw_predicted_prob"] = np.asarray(raw_prob if raw_prob is not None else predicted_arr, dtype=float)
    if routing_df is not None and not routing_df.empty:
        aligned = routing_df.reset_index(drop=True)
        for column in aligned.columns:
            if column not in variant_predictions.columns:
                variant_predictions[column] = aligned[column].to_numpy()
    return variant_predictions


def _evaluate_guarded_calibration_variant(
    merged: pd.DataFrame,
    train_idx: np.ndarray,
    val_idx: np.ndarray,
    split_name: str,
    prediction_base_df: pd.DataFrame,
) -> tuple[List[dict], List[dict], List[dict], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    feature_order = _baseline_and_feature_orders()[BASELINE_VARIANT]
    available_columns = [column for column in feature_order if column in merged.columns]
    y_train = merged.loc[train_idx, "is_winner"].astype(int).to_numpy()
    y_val = merged.loc[val_idx, "is_winner"].astype(int).to_numpy()
    innings_val = merged.loc[val_idx, "innings"].astype(int).to_numpy()
    overs_remaining_val = merged.loc[val_idx, "overs_remaining"].astype(float).to_numpy()

    model = _model_for_variant(BASELINE_VARIANT)
    X_train = merged.loc[train_idx, available_columns].copy()
    X_val = merged.loc[val_idx, available_columns].copy()
    model.fit(X_train, pd.Series(y_train))

    train_raw_prob = model.predict_proba(X_train)[:, 1]
    val_raw_prob = model.predict_proba(X_val)[:, 1]
    calibration_bundle, guardrails_df = fit_guarded_regime_phase_calibration(
        df=merged.loc[train_idx, ["regime_id", "innings", "overs_remaining", "phase_label"]].copy(),
        raw_probs=train_raw_prob,
        y_true=y_train,
        min_samples=REGIME_CALIBRATION_MIN_SAMPLES,
        min_unique_probs=REGIME_CALIBRATION_MIN_UNIQUE_PROBS,
    )
    calibrated_val_prob, routing_df = apply_guarded_regime_phase_calibration(
        df=merged.loc[val_idx, ["regime_id", "innings", "overs_remaining", "phase_label"]].copy(),
        raw_probs=val_raw_prob,
        bundle=calibration_bundle,
    )

    metric_rows = collect_segment_metrics(
        GUARDED_CALIBRATION_VARIANT,
        split_name,
        y_val,
        calibrated_val_prob,
        innings_val,
        overs_remaining_val,
    )
    reliability_rows = collect_reliability_bins(
        GUARDED_CALIBRATION_VARIANT,
        split_name,
        y_val,
        calibrated_val_prob,
    )
    prediction_df = _build_prediction_frame(
        prediction_base_df=prediction_base_df,
        variant=GUARDED_CALIBRATION_VARIANT,
        split_name=split_name,
        y_true=y_val,
        predicted_prob=calibrated_val_prob,
        raw_prob=val_raw_prob,
        routing_df=routing_df,
    )

    guardrails_output = guardrails_df.copy()
    if not guardrails_output.empty:
        guardrails_output.insert(0, "split", split_name)
        guardrails_output.insert(1, "method", GUARDED_CALIBRATION_VARIANT)
    calibration_summary_df = summarize_guarded_regime_phase_calibration(
        split=split_name,
        method=GUARDED_CALIBRATION_VARIANT,
        guardrails_df=guardrails_df,
        routing_df=routing_df,
        min_samples=REGIME_CALIBRATION_MIN_SAMPLES,
        min_unique_probs=REGIME_CALIBRATION_MIN_UNIQUE_PROBS,
    )
    return metric_rows, reliability_rows, prediction_df, guardrails_output, calibration_summary_df, routing_df


def _evaluate_variants(
    merged: pd.DataFrame,
    train_idx: np.ndarray,
    val_idx: np.ndarray,
    split_name: str,
    variants: List[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if len(train_idx) == 0 or len(val_idx) == 0:
        raise ValueError(f"Unable to create non-empty split for {split_name}")

    y_train = merged.loc[train_idx, "is_winner"].astype(int).to_numpy()
    y_val = merged.loc[val_idx, "is_winner"].astype(int).to_numpy()
    innings_val = merged.loc[val_idx, "innings"].astype(int).to_numpy()
    overs_remaining_val = merged.loc[val_idx, "overs_remaining"].astype(float).to_numpy()

    metric_rows: List[dict] = []
    segment_rows: List[dict] = []
    reliability_rows: List[dict] = []
    prediction_frames: List[pd.DataFrame] = []
    calibration_guardrail_frames: List[pd.DataFrame] = []
    calibration_summary_frames: List[pd.DataFrame] = []
    prediction_columns = [column for column in PREDICTION_EXPORT_COLUMNS if column in merged.columns]
    prediction_base_df = merged.loc[val_idx, prediction_columns].copy()
    cached_probs: Dict[str, np.ndarray] = {}

    for variant in variants:
        if variant in CONSERVATIVE_V18_VARIANTS:
            continue
        if variant == GUARDED_CALIBRATION_VARIANT:
            (
                calibration_metric_rows,
                calibration_reliability_rows,
                calibration_predictions_df,
                calibration_guardrails_df,
                calibration_summary_df,
                _,
            ) = _evaluate_guarded_calibration_variant(
                merged=merged,
                train_idx=train_idx,
                val_idx=val_idx,
                split_name=split_name,
                prediction_base_df=prediction_base_df,
            )
            metric_rows.extend(calibration_metric_rows)
            segment_rows.extend(calibration_metric_rows)
            reliability_rows.extend(calibration_reliability_rows)
            prediction_frames.append(calibration_predictions_df)
            cached_probs[variant] = calibration_predictions_df["predicted_prob"].to_numpy(dtype=float)
            if not calibration_guardrails_df.empty:
                calibration_guardrail_frames.append(calibration_guardrails_df)
            if not calibration_summary_df.empty:
                calibration_summary_frames.append(calibration_summary_df)
            continue

        model = _model_for_variant(variant)
        feature_order = _baseline_and_feature_orders()[variant]
        available_columns = [column for column in feature_order if column in merged.columns]
        X_train = merged.loc[train_idx, available_columns].copy()
        X_val = merged.loc[val_idx, available_columns].copy()
        model.fit(X_train, pd.Series(y_train))
        val_prob = model.predict_proba(X_val)[:, 1]
        cached_probs[variant] = val_prob
        metric_rows.extend(collect_segment_metrics(variant, split_name, y_val, val_prob, innings_val, overs_remaining_val))
        segment_rows.extend(collect_segment_metrics(variant, split_name, y_val, val_prob, innings_val, overs_remaining_val))
        reliability_rows.extend(collect_reliability_bins(variant, split_name, y_val, val_prob))
        prediction_frames.append(
            _build_prediction_frame(
                prediction_base_df=prediction_base_df,
                variant=variant,
                split_name=split_name,
                y_true=y_val,
                predicted_prob=val_prob,
            )
        )

    if any(variant in variants for variant in CONSERVATIVE_V18_VARIANTS):
        if BASELINE_VARIANT not in cached_probs or CLUSTER_WINNER_VARIANT not in cached_probs:
            raise ValueError("Conservative v18 variants require baseline and regime_cluster_features predictions")
        routing_columns = [
            column
            for column in ["innings", "overs_remaining", "phase_label", "regime_confidence", "regime_cluster_size", "stability_flag"]
            if column in merged.columns
        ]
        routing_frame = merged.loc[val_idx, routing_columns].copy()
        for variant in CONSERVATIVE_V18_VARIANTS:
            if variant not in variants:
                continue
            routed_prob, routing_df = apply_inn2_powerplay_variant(
                df=routing_frame,
                baseline_probs=cached_probs[BASELINE_VARIANT],
                cluster_probs=cached_probs[CLUSTER_WINNER_VARIANT],
                variant=variant,
            )
            metric_rows.extend(collect_segment_metrics(variant, split_name, y_val, routed_prob, innings_val, overs_remaining_val))
            segment_rows.extend(collect_segment_metrics(variant, split_name, y_val, routed_prob, innings_val, overs_remaining_val))
            reliability_rows.extend(collect_reliability_bins(variant, split_name, y_val, routed_prob))
            prediction_frames.append(
                _build_prediction_frame(
                    prediction_base_df=prediction_base_df,
                    variant=variant,
                    split_name=split_name,
                    y_true=y_val,
                    predicted_prob=routed_prob,
                    raw_prob=cached_probs[CLUSTER_WINNER_VARIANT],
                    routing_df=routing_df,
                )
            )

    metrics_df = pd.DataFrame(metric_rows).drop_duplicates(subset=["method", "split", "segment"])
    metrics_df = _add_reference_delta_columns(metrics_df)

    segment_metrics_df = pd.DataFrame(segment_rows).drop_duplicates(subset=["method", "split", "segment"])
    segment_metrics_df = _add_reference_delta_columns(segment_metrics_df)
    reliability_df = pd.DataFrame(reliability_rows)
    predictions_df = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    calibration_guardrails_df = (
        pd.concat(calibration_guardrail_frames, ignore_index=True) if calibration_guardrail_frames else pd.DataFrame()
    )
    calibration_summary_df = (
        pd.concat(calibration_summary_frames, ignore_index=True) if calibration_summary_frames else pd.DataFrame()
    )
    return metrics_df, segment_metrics_df, reliability_df, predictions_df, calibration_guardrails_df, calibration_summary_df


def _run_holdout_evaluation(
    corpus_df: pd.DataFrame,
    feature_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    merged = _prepare_evaluation_frame(corpus_df, feature_df)
    train_idx, val_idx = make_time_ordered_holdout_split(merged)
    return _evaluate_variants(merged, train_idx, val_idx, "holdout", [BASELINE_VARIANT, *CANDIDATE_VARIANTS])


def _run_season_slice_validation(
    corpus_df: pd.DataFrame,
    models_dir: Path,
    seed: int,
    pca_components: int,
    n_clusters: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics_frames: List[pd.DataFrame] = []
    segment_frames: List[pd.DataFrame] = []
    reliability_frames: List[pd.DataFrame] = []
    prediction_frames: List[pd.DataFrame] = []
    calibration_guardrail_frames: List[pd.DataFrame] = []
    calibration_summary_frames: List[pd.DataFrame] = []

    for season_year in SEASON_SLICE_YEARS:
        train_idx, val_idx = make_train_before_test_season_split(corpus_df, season_year)
        if len(train_idx) == 0 or len(val_idx) == 0:
            raise ValueError(f"Season slice train <{season_year} -> test {season_year} is unavailable")

        train_mask = np.zeros(len(corpus_df), dtype=bool)
        train_mask[train_idx] = True
        assignments_df, _, _ = fit_embedding_models(
            corpus_df=corpus_df,
            train_mask=train_mask,
            output_dir=models_dir / f"season_{season_year}",
            seed=seed,
            pca_components=pca_components,
            n_clusters=n_clusters,
        )
        regime_features_df = build_regime_feature_frame(assignments_df, pd.DataFrame())
        merged = _prepare_evaluation_frame(assignments_df, regime_features_df)
        (
            metrics_df,
            segment_metrics_df,
            reliability_df,
            predictions_df,
            calibration_guardrails_df,
            calibration_summary_df,
        ) = _evaluate_variants(
            merged=merged,
            train_idx=train_idx,
            val_idx=val_idx,
            split_name=f"season_{season_year}",
            variants=SEASON_SLICE_VARIANTS,
        )
        metrics_frames.append(metrics_df)
        segment_frames.append(segment_metrics_df)
        reliability_frames.append(reliability_df)
        prediction_frames.append(predictions_df)
        if not calibration_guardrails_df.empty:
            calibration_guardrail_frames.append(calibration_guardrails_df)
        if not calibration_summary_df.empty:
            calibration_summary_frames.append(calibration_summary_df)

    return (
        pd.concat(metrics_frames, ignore_index=True) if metrics_frames else pd.DataFrame(),
        pd.concat(segment_frames, ignore_index=True) if segment_frames else pd.DataFrame(),
        pd.concat(reliability_frames, ignore_index=True) if reliability_frames else pd.DataFrame(),
        pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame(),
        pd.concat(calibration_guardrail_frames, ignore_index=True) if calibration_guardrail_frames else pd.DataFrame(),
        pd.concat(calibration_summary_frames, ignore_index=True) if calibration_summary_frames else pd.DataFrame(),
    )


def _build_powerplay_diagnostics(
    assignments_df: pd.DataFrame,
    holdout_predictions_df: pd.DataFrame,
    output_dir: Path,
) -> List[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pp_predictions_path = output_dir / "inn2_powerplay_predictions.csv"
    overconfident_path = output_dir / "inn2_powerplay_overconfident_wrongs.csv"
    reliability_path = output_dir / "inn2_powerplay_reliability_bins.csv"
    cluster_behavior_path = output_dir / "inn2_powerplay_cluster_behavior.csv"
    recent_behavior_path = output_dir / "inn2_powerplay_cluster_behavior_2025_2026.csv"
    recent_stability_path = output_dir / "inn2_powerplay_cluster_stability_2025_2026.csv"
    recent_summary_path = output_dir / "inn2_powerplay_cluster_stability_2025_2026.json"
    report_path = output_dir / "INNINGS2_POWERPLAY_DIAGNOSTICS.md"

    pp_predictions_df = holdout_predictions_df[
        (holdout_predictions_df["innings"] == 2)
        & (holdout_predictions_df["phase_label"] == "powerplay")
        & (holdout_predictions_df["method"].isin([BASELINE_VARIANT, POWERPLAY_DIAGNOSTIC_VARIANT, *CONSERVATIVE_V18_VARIANTS]))
    ].copy()
    pp_predictions_df.to_csv(pp_predictions_path, index=False)

    pp_reliability_rows: List[dict] = []
    for method in [BASELINE_VARIANT, POWERPLAY_DIAGNOSTIC_VARIANT, *CONSERVATIVE_V18_VARIANTS]:
        method_df = pp_predictions_df[pp_predictions_df["method"] == method]
        if method_df.empty:
            continue
        pp_reliability_rows.extend(
            collect_reliability_bins(
                method=method,
                split="holdout_innings_2_powerplay",
                y_true=method_df["is_winner"].astype(int).to_numpy(),
                y_prob=method_df["predicted_prob"].astype(float).to_numpy(),
            )
        )
    pp_reliability_df = pd.DataFrame(pp_reliability_rows)
    if not pp_reliability_df.empty:
        pp_reliability_df["calibration_gap"] = pp_reliability_df["mean_predicted"] - pp_reliability_df["mean_actual"]
    pp_reliability_df.to_csv(reliability_path, index=False)

    regime_predictions_df = pp_predictions_df[pp_predictions_df["method"] == POWERPLAY_DIAGNOSTIC_VARIANT].copy()
    if not regime_predictions_df.empty:
        regime_predictions_df["confidence_strength"] = np.where(
            regime_predictions_df["predicted_prob"] >= 0.5,
            regime_predictions_df["predicted_prob"],
            1.0 - regime_predictions_df["predicted_prob"],
        )
        regime_predictions_df["wrong_direction"] = np.where(
            regime_predictions_df["correct"],
            "correct",
            np.where(regime_predictions_df["predicted_label"] == 1, "false_positive", "false_negative"),
        )
        overconfident_wrongs_df = regime_predictions_df[
            (~regime_predictions_df["correct"]) & (regime_predictions_df["confidence_strength"] >= 0.8)
        ].sort_values(["confidence_strength", "prediction_error"], ascending=[False, False])
    else:
        overconfident_wrongs_df = pd.DataFrame()
    overconfident_wrongs_df.to_csv(overconfident_path, index=False)

    embedding_columns = [column for column in assignments_df.columns if column.startswith("embedding_")]
    pp_assignments_df = assignments_df[(assignments_df["innings"] == 2) & (assignments_df["phase_label"] == "powerplay")].copy()
    pp_assignments_df["season"] = pp_assignments_df["season"].astype(str)
    pp_cluster_behavior_df = summarize_regimes(pp_assignments_df, embedding_columns)
    if not pp_cluster_behavior_df.empty:
        pp_cluster_behavior_df = pp_cluster_behavior_df.rename(columns={"coverage": "powerplay_share"})
    pp_cluster_behavior_df.to_csv(cluster_behavior_path, index=False)

    recent_assignments_df = pp_assignments_df[pp_assignments_df["season"].isin(POWERPLAY_RECENT_SEASONS)].copy()
    recent_behavior_df = (
        recent_assignments_df.groupby(["season", "regime_id", "regime_label", "stability_flag"], dropna=False)
        .agg(
            rows=("row_key", "size"),
            actual_win_rate=("is_winner", "mean"),
            mean_regime_confidence=("regime_confidence", "mean"),
            mean_cluster_win_rate=("regime_cluster_win_rate", "mean"),
            mean_resource_win_prob=("resource_win_prob", "mean"),
        )
        .reset_index()
    )
    if not recent_behavior_df.empty:
        recent_behavior_df["season_share"] = recent_behavior_df.groupby("season")["rows"].transform(lambda values: values / values.sum())
        recent_behavior_df["cluster_win_rate_gap"] = recent_behavior_df["mean_cluster_win_rate"] - recent_behavior_df["actual_win_rate"]
    recent_behavior_df.to_csv(recent_behavior_path, index=False)

    recent_stability_df = summarize_regimes(recent_assignments_df, embedding_columns)
    if not recent_stability_df.empty:
        recent_stability_df = recent_stability_df.rename(columns={"coverage": "recent_powerplay_share"})
    recent_stability_df.to_csv(recent_stability_path, index=False)

    unstable_recent = []
    if not recent_stability_df.empty:
        unstable_recent = recent_stability_df[recent_stability_df["stability_flag"] != "stable"][
            ["regime_id", "regime_label", "rows", "stability_std", "stability_flag"]
        ].to_dict("records")

    recent_summary = {
        "focus_variant": POWERPLAY_DIAGNOSTIC_VARIANT,
        "recent_seasons": list(POWERPLAY_RECENT_SEASONS),
        "recent_powerplay_rows": int(len(recent_assignments_df)),
        "regimes_observed": int(recent_stability_df["regime_id"].nunique()) if not recent_stability_df.empty else 0,
        "unstable_regime_count": int(len(unstable_recent)),
        "all_regimes_stable": bool(not recent_stability_df.empty and len(unstable_recent) == 0),
        "unstable_regimes": unstable_recent,
    }
    recent_summary_path.write_text(json.dumps(recent_summary, indent=2), encoding="utf-8")

    report_lines = [
        "# Innings 2 Powerplay Diagnostics",
        "",
        f"- Focus variant: `{POWERPLAY_DIAGNOSTIC_VARIANT}`",
        f"- Holdout PP rows exported: {len(pp_predictions_df):,}",
        f"- Focus-variant PP rows: {len(regime_predictions_df):,}",
        f"- Overconfident wrong predictions: {len(overconfident_wrongs_df):,}",
        f"- Recent PP rows (2025-2026): {len(recent_assignments_df):,}",
        "",
        "## PP Reliability Bins",
        "",
    ]
    if pp_reliability_df.empty:
        report_lines.append("_No Innings 2 powerplay reliability rows were generated._")
    else:
        report_lines.extend(
            [
                "| Variant | Bin | N | Mean Pred | Mean Actual | Gap |",
                "|---|---|---:|---:|---:|---:|",
            ]
        )
        for _, row in pp_reliability_df.iterrows():
            report_lines.append(
                f"| `{row['method']}` | {row['bin_low']:.1f}-{row['bin_high']:.1f} | {int(row['n'])} | "
                f"{row['mean_predicted']:.3f} | {row['mean_actual']:.3f} | {row['calibration_gap']:+.3f} |"
            )

    report_lines.extend(["", "## Overconfident Wrong Predictions", ""])
    if overconfident_wrongs_df.empty:
        report_lines.append("_No overconfident wrong predictions met the 0.80 confidence threshold._")
    else:
        report_lines.extend(
            [
                "| Row | Season | Over.Ball | Batting | Regime | Pred | Actual | Direction |",
                "|---|---|---|---|---:|---:|---:|---|",
            ]
        )
        for _, row in overconfident_wrongs_df.head(10).iterrows():
            report_lines.append(
                f"| `{row['row_key']}` | {row['season']} | {int(row['over'])}.{int(row['ball'])} | {row['batting_team']} | "
                f"{int(row['regime_id'])} | {row['predicted_prob']:.3f} | {int(row['is_winner'])} | {row['wrong_direction']} |"
            )

    report_lines.extend(["", "## Cluster Assignment Behaviour", ""])
    if pp_cluster_behavior_df.empty:
        report_lines.append("_No Innings 2 PP cluster assignments were available._")
    else:
        report_lines.extend(
            [
                "| Regime | Label | Rows | PP Share | Win Rate | Mean Conf | Stability |",
                "|---:|---|---:|---:|---:|---:|---|",
            ]
        )
        for _, row in pp_cluster_behavior_df.iterrows():
            report_lines.append(
                f"| {int(row['regime_id'])} | {row['regime_label']} | {int(row['rows'])} | {row['powerplay_share']:.2%} | "
                f"{row['regime_cluster_win_rate']:.3f} | {row['regime_confidence']:.3f} | {row['stability_flag']} |"
            )

    report_lines.extend(["", "## 2025-2026 Stability Check", ""])
    if recent_stability_df.empty:
        report_lines.append("_No 2025-2026 PP rows were available for a recent-stability check._")
    else:
        verdict = "All PP regimes remain stable in 2025-2026." if recent_summary["all_regimes_stable"] else "Some PP regimes are borderline/unstable in 2025-2026."
        report_lines.append(verdict)
        report_lines.extend(
            [
                "",
                "| Regime | Label | Rows | Recent Share | Stability Std | Flag |",
                "|---:|---|---:|---:|---:|---|",
            ]
        )
        for _, row in recent_stability_df.iterrows():
            report_lines.append(
                f"| {int(row['regime_id'])} | {row['regime_label']} | {int(row['rows'])} | {row['recent_powerplay_share']:.2%} | "
                f"{row['stability_std']:.3f} | {row['stability_flag']} |"
            )

    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    return [
        str(pp_predictions_path),
        str(overconfident_path),
        str(reliability_path),
        str(cluster_behavior_path),
        str(recent_behavior_path),
        str(recent_stability_path),
        str(recent_summary_path),
        str(report_path),
    ]


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    raw_backfill_dir = Path(args.raw_backfill_dir) if args.raw_backfill_dir else None
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "corpus": output_dir / CORPUS_DIRNAME,
        "models": output_dir / MODELS_DIRNAME,
        "regimes": output_dir / REGIMES_DIRNAME,
        "retrieval": output_dir / RETRIEVAL_DIRNAME,
        "features": output_dir / FEATURES_DIRNAME,
        "evaluation": output_dir / EVALUATION_DIRNAME,
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)

    stage_manifest = _load_stage_manifest(output_dir)

    print(f"\n{'=' * 72}")
    print(f"IPL State Embeddings Experiment -- mode={args.mode}")
    print(f"Input:  {input_path}")
    print(f"Output: {output_dir}")
    print(f"{'=' * 72}\n")

    # Stage 1: corpus build
    print("[1/4] Building embedding corpus...")
    corpus_output = paths["corpus"] / "embedding_corpus.parquet"
    manifest_output = paths["corpus"] / "corpus_manifest.json"
    if args.resume and corpus_output.exists() and manifest_output.exists():
        corpus_df = pd.read_parquet(corpus_output)
        corpus_manifest = json.loads(manifest_output.read_text(encoding="utf-8"))
    else:
        corpus_df, _, corpus_manifest = build_embedding_corpus(input_path, raw_backfill_dir, paths["corpus"], seed=args.seed)
    stage_manifest["corpus"] = {"status": "done", "artifacts": [str(corpus_output), str(manifest_output)]}
    _save_stage_manifest(output_dir, stage_manifest)
    print(f"  Eligible rows: {len(corpus_df):,}")

    # Stage 2: regimes
    print("\n[2/4] Fitting PCA/KMeans regimes...")
    assignments_output = paths["regimes"] / "regime_assignments.parquet"
    summary_output = paths["regimes"] / "regime_summary.csv"
    if args.resume and assignments_output.exists() and summary_output.exists():
        assignments_df = pd.read_parquet(assignments_output)
        regime_summary_df = pd.read_csv(summary_output)
    else:
        train_idx, val_idx = make_time_ordered_holdout_split(corpus_df)
        train_mask = np.zeros(len(corpus_df), dtype=bool)
        train_mask[train_idx] = True
        assignments_df, _, _ = fit_embedding_models(
            corpus_df=corpus_df,
            train_mask=train_mask,
            output_dir=paths["models"],
            seed=args.seed,
            pca_components=args.pca_components,
            n_clusters=args.n_clusters,
        )
        embedding_columns = [column for column in assignments_df.columns if column.startswith("embedding_")]
        regime_summary_df = summarize_regimes(assignments_df, embedding_columns)
        assignments_df = assignments_df.merge(
            regime_summary_df[["regime_id", "regime_label", "stability_flag"]],
            on="regime_id",
            how="left",
        )
        assignments_df.to_parquet(assignments_output, index=False)
        regime_summary_df.to_csv(summary_output, index=False)
    stage_manifest["regimes"] = {"status": "done", "artifacts": [str(assignments_output), str(summary_output)]}
    _save_stage_manifest(output_dir, stage_manifest)

    # Stage 3: retrieval
    print("\n[3/4] Retrieving historical analogues...")
    results_output = paths["retrieval"] / "analogue_results.parquet"
    retrieval_summary_output = paths["retrieval"] / "retrieval_summary.json"
    if args.resume and results_output.exists() and retrieval_summary_output.exists():
        analogue_results_df = pd.read_parquet(results_output)
        retrieval_summary = json.loads(retrieval_summary_output.read_text(encoding="utf-8"))
    else:
        holdout_train_idx, holdout_val_idx = make_time_ordered_holdout_split(assignments_df)
        query_mask = np.zeros(len(assignments_df), dtype=bool)
        query_mask[holdout_val_idx] = True
        analogue_results_df, retrieval_summary = query_historical_analogues(
            assignments_df=assignments_df,
            output_dir=paths["retrieval"],
            top_k=args.top_k,
            query_mask=query_mask,
        )
    stage_manifest["retrieval"] = {"status": "done", "artifacts": [str(results_output), str(retrieval_summary_output)]}
    _save_stage_manifest(output_dir, stage_manifest)

    # Stage 4: feature generation + evaluation
    print("\n[4/4] Building regime-aware features and evaluating variants...")
    feature_output = paths["features"] / "regime_features.parquet"
    metrics_output = paths["evaluation"] / "metrics.csv"
    segment_output = paths["evaluation"] / "segment_metrics.csv"
    reliability_output = paths["evaluation"] / "reliability_bins.csv"
    calibration_guardrails_output = paths["evaluation"] / "calibration_guardrails.csv"
    calibration_summary_output = paths["evaluation"] / "calibration_summary.csv"
    season_slice_metrics_output = paths["evaluation"] / "season_slice_metrics.csv"
    season_slice_segment_output = paths["evaluation"] / "season_slice_segment_metrics.csv"
    season_slice_reliability_output = paths["evaluation"] / "season_slice_reliability_bins.csv"
    season_slice_calibration_guardrails_output = paths["evaluation"] / "season_slice_calibration_guardrails.csv"
    season_slice_calibration_summary_output = paths["evaluation"] / "season_slice_calibration_summary.csv"
    report_output = paths["evaluation"] / "PILOT_REPORT.md"

    analogue_features_df = build_analogue_features(analogue_results_df, top_k=args.top_k)
    regime_features_df = build_regime_feature_frame(assignments_df, analogue_features_df)
    regime_features_df.to_parquet(feature_output, index=False)

    (
        metrics_df,
        segment_metrics_df,
        reliability_df,
        holdout_predictions_df,
        calibration_guardrails_df,
        calibration_summary_df,
    ) = _run_holdout_evaluation(assignments_df, regime_features_df)
    metrics_df.to_csv(metrics_output, index=False)
    segment_metrics_df.to_csv(segment_output, index=False)
    reliability_df.to_csv(reliability_output, index=False)
    calibration_guardrails_df.to_csv(calibration_guardrails_output, index=False)
    calibration_summary_df.to_csv(calibration_summary_output, index=False)
    (
        season_slice_metrics_df,
        season_slice_segment_metrics_df,
        season_slice_reliability_df,
        _,
        season_slice_calibration_guardrails_df,
        season_slice_calibration_summary_df,
    ) = _run_season_slice_validation(
        corpus_df=corpus_df,
        models_dir=paths["models"],
        seed=args.seed,
        pca_components=args.pca_components,
        n_clusters=args.n_clusters,
    )
    season_slice_metrics_df.to_csv(season_slice_metrics_output, index=False)
    season_slice_segment_metrics_df.to_csv(season_slice_segment_output, index=False)
    season_slice_reliability_df.to_csv(season_slice_reliability_output, index=False)
    season_slice_calibration_guardrails_df.to_csv(season_slice_calibration_guardrails_output, index=False)
    season_slice_calibration_summary_df.to_csv(season_slice_calibration_summary_output, index=False)

    decision = check_go_no_go(metrics_df, segment_metrics_df, BASELINE_VARIANT, CANDIDATE_VARIANTS)
    report_output.write_text(
        render_pilot_report(
            metrics_df=metrics_df,
            segment_metrics_df=segment_metrics_df,
            reliability_df=reliability_df,
            manifest=corpus_manifest,
            retrieval_summary=retrieval_summary,
            regime_summary_df=regime_summary_df,
            decision=decision,
            mode=args.mode,
            season_slice_metrics_df=season_slice_metrics_df,
            calibration_summary_df=pd.concat(
                [frame for frame in [calibration_summary_df, season_slice_calibration_summary_df] if not frame.empty],
                ignore_index=True,
            )
            if (not calibration_summary_df.empty or not season_slice_calibration_summary_df.empty)
            else pd.DataFrame(),
        ),
        encoding="utf-8",
    )
    pp_diagnostic_artifacts = _build_powerplay_diagnostics(assignments_df, holdout_predictions_df, paths["evaluation"])
    stage_manifest["evaluation"] = {
        "status": "done",
        "artifacts": [
            str(feature_output),
            str(metrics_output),
            str(segment_output),
            str(reliability_output),
            str(calibration_guardrails_output),
            str(calibration_summary_output),
            str(season_slice_metrics_output),
            str(season_slice_segment_output),
            str(season_slice_reliability_output),
            str(season_slice_calibration_guardrails_output),
            str(season_slice_calibration_summary_output),
            str(report_output),
            *pp_diagnostic_artifacts,
        ],
    }
    _save_stage_manifest(output_dir, stage_manifest)

    print("\nExperiment complete.")
    print(f"Recommendation: {decision.recommendation.upper()}")
    if decision.winning_variant:
        print(f"Winning variant: {decision.winning_variant}")
    else:
        print("No winning variant. No production change.")


if __name__ == "__main__":
    main()
