from __future__ import annotations

import re
from itertools import combinations
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss

from .types import GateDecision

PHASE_POWERPLAY = "powerplay"
PHASE_MIDDLE = "middle"
PHASE_DEATH = "death"

META_COLUMNS = {
    "row_key",
    "match_id",
    "season",
    "date",
    "venue",
    "innings",
    "over",
    "ball",
    "batting_team",
    "bowling_team",
    "winner",
    "is_winner",
    "eligibility_status",
    "exclusion_reason",
    "source_priority",
    "fit_role",
    "order_index",
    "window_id",
    "anchor_row_key",
    "source_row_keys",
    "window_complete",
    "query_role",
}


def clip_prob(p: np.ndarray | float) -> np.ndarray | float:
    return np.clip(p, 1e-7, 1 - 1e-7)


def compute_brier(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(brier_score_loss(y_true, clip_prob(y_prob)))


def compute_log_loss_metric(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(log_loss(y_true, clip_prob(y_prob)))


def compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 0.0, 1.0)
    y_true = np.asarray(y_true, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(y_prob, bins) - 1, 0, n_bins - 1)
    total = 0.0
    for bin_idx in range(n_bins):
        mask = idx == bin_idx
        if not mask.any():
            continue
        total += mask.mean() * abs(y_prob[mask].mean() - y_true[mask].mean())
    return float(total)


def get_phase_label(overs_remaining: float) -> str:
    overs_done = 20.0 - float(overs_remaining)
    if overs_done < 6:
        return PHASE_POWERPLAY
    if overs_done < 15:
        return PHASE_MIDDLE
    return PHASE_DEATH


def build_row_key(match_id: object, innings: object, over: object, ball: object) -> str:
    return f"{match_id}:{int(innings)}:{int(over)}:{int(ball)}"


def make_time_ordered_holdout_split(
    df: pd.DataFrame,
    train_fraction: float = 0.8,
) -> Tuple[np.ndarray, np.ndarray]:
    if df.empty:
        return np.array([], dtype=int), np.array([], dtype=int)
    ordered = df.sort_values(["date", "season", "match_id", "innings", "over", "ball", "order_index"]).reset_index()
    cut = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
    return ordered.loc[: cut - 1, "index"].to_numpy(), ordered.loc[cut:, "index"].to_numpy()


def make_time_ordered_cv_splits(
    df: pd.DataFrame,
    n_splits: int = 5,
) -> List[Tuple[np.ndarray, np.ndarray]]:
    if df.empty:
        return []
    ordered = df.sort_values(["date", "season", "match_id", "innings", "over", "ball", "order_index"]).reset_index()
    fold_size = max(1, len(ordered) // n_splits)
    splits: List[Tuple[np.ndarray, np.ndarray]] = []
    for fold_idx in range(1, n_splits + 1):
        val_start = fold_size * (fold_idx - 1)
        val_end = len(ordered) if fold_idx == n_splits else min(len(ordered), val_start + fold_size)
        train_idx = ordered.loc[: val_start - 1, "index"].to_numpy()
        val_idx = ordered.loc[val_start: val_end - 1, "index"].to_numpy()
        if len(train_idx) == 0 or len(val_idx) == 0:
            continue
        splits.append((train_idx, val_idx))
    return splits


def make_season_slices(df: pd.DataFrame) -> List[Tuple[str, np.ndarray]]:
    if "season" not in df.columns:
        return []
    season_series = df["season"].fillna("unknown").astype(str)
    seasons = [season for season in season_series.drop_duplicates().tolist() if season]
    return [(season, df.index[season_series == season].to_numpy()) for season in seasons]


def _season_to_year(value: object) -> Optional[int]:
    if pd.isna(value):
        return None
    match = re.search(r"(19|20)\d{2}", str(value))
    if not match:
        return None
    return int(match.group(0))


def make_train_before_test_season_split(
    df: pd.DataFrame,
    test_season: int,
) -> Tuple[np.ndarray, np.ndarray]:
    if "season" not in df.columns or df.empty:
        return np.array([], dtype=int), np.array([], dtype=int)

    season_years = pd.to_numeric(df["season"].map(_season_to_year), errors="coerce")
    train_idx = df.index[season_years.notna() & (season_years < int(test_season))].to_numpy()
    test_idx = df.index[season_years == int(test_season)].to_numpy()
    return train_idx, test_idx


def _metrics_row(method: str, split: str, segment: str, y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    if len(y_true) < 5:
        return {}
    return {
        "method": method,
        "split": split,
        "segment": segment,
        "n": int(len(y_true)),
        "brier": compute_brier(y_true, y_prob),
        "ece": compute_ece(y_true, y_prob),
        "log_loss": compute_log_loss_metric(y_true, y_prob),
    }


def collect_segment_metrics(
    method: str,
    split: str,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    innings: np.ndarray,
    overs_remaining: np.ndarray,
) -> List[dict]:
    rows: List[dict] = []
    overall = _metrics_row(method, split, "overall", y_true, y_prob)
    if overall:
        rows.append(overall)
    for inning in [1, 2]:
        inning_mask = innings == inning
        row = _metrics_row(method, split, f"innings_{inning}", y_true[inning_mask], y_prob[inning_mask])
        if row:
            rows.append(row)
        for phase in [PHASE_POWERPLAY, PHASE_MIDDLE, PHASE_DEATH]:
            phase_mask = inning_mask & np.array([get_phase_label(value) == phase for value in overs_remaining])
            row = _metrics_row(method, split, f"innings_{inning}_{phase}", y_true[phase_mask], y_prob[phase_mask])
            if row:
                rows.append(row)
    return rows


def collect_reliability_bins(
    method: str,
    split: str,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> List[dict]:
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 0.0, 1.0)
    y_true = np.asarray(y_true, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(y_prob, bins) - 1, 0, n_bins - 1)
    rows: List[dict] = []
    for bin_idx in range(n_bins):
        mask = idx == bin_idx
        if not mask.any():
            continue
        rows.append(
            {
                "method": method,
                "split": split,
                "bin_low": round(float(bins[bin_idx]), 2),
                "bin_high": round(float(bins[bin_idx + 1]), 2),
                "n": int(mask.sum()),
                "mean_predicted": float(y_prob[mask].mean()),
                "mean_actual": float(y_true[mask].mean()),
            }
        )
    return rows


def add_baseline_deltas(rows: List[dict], baseline_rows: List[dict]) -> List[dict]:
    return add_reference_deltas(rows, baseline_rows, "baseline")


def add_reference_deltas(rows: List[dict], reference_rows: List[dict], prefix: str) -> List[dict]:
    base_map = {(row["split"], row["segment"]): row for row in reference_rows}
    output: List[dict] = []
    for row in rows:
        updated = dict(row)
        reference = base_map.get((row["split"], row["segment"]))
        if reference:
            updated[f"{prefix}_brier_delta"] = round(row["brier"] - reference["brier"], 6)
            updated[f"{prefix}_ece_delta"] = round(row["ece"] - reference["ece"], 6)
            updated[f"{prefix}_log_loss_delta"] = round(row["log_loss"] - reference["log_loss"], 6)
        else:
            updated[f"{prefix}_brier_delta"] = None
            updated[f"{prefix}_ece_delta"] = None
            updated[f"{prefix}_log_loss_delta"] = None
        output.append(updated)
    return output


def _with_phase_labels(df: pd.DataFrame) -> pd.DataFrame:
    working = df.reset_index(drop=True).copy()
    if "phase_label" not in working.columns:
        if "overs_remaining" not in working.columns:
            raise ValueError("Need phase_label or overs_remaining for regime calibration")
        working["phase_label"] = [get_phase_label(value) for value in working["overs_remaining"].astype(float).to_numpy()]
    return working


def fit_guarded_regime_phase_calibration(
    df: pd.DataFrame,
    raw_probs: np.ndarray,
    y_true: np.ndarray,
    min_samples: int = 200,
    min_unique_probs: int = 10,
) -> Tuple[dict, pd.DataFrame]:
    working = _with_phase_labels(df)
    required = {"regime_id", "innings", "phase_label"}
    missing = required.difference(working.columns)
    if missing:
        raise ValueError(f"Missing regime calibration columns: {sorted(missing)}")

    working["raw_prob"] = np.asarray(raw_probs, dtype=float)
    working["y_true"] = np.asarray(y_true, dtype=int)

    calibrators: Dict[Tuple[object, int, str], IsotonicRegression] = {}
    guardrail_rows: List[dict] = []
    grouped = working.groupby(["regime_id", "innings", "phase_label"], dropna=False, sort=True)
    for keys, group in grouped:
        regime_id, innings, phase_label = keys
        n_samples = int(len(group))
        unique_probs = int(group["raw_prob"].nunique())
        class_count = int(group["y_true"].nunique())
        fit_status = "skipped"
        guard_reason = ""
        if n_samples < int(min_samples):
            guard_reason = f"min_samples<{int(min_samples)}"
        elif unique_probs < int(min_unique_probs):
            guard_reason = f"unique_probs<{int(min_unique_probs)}"
        elif class_count < 2:
            guard_reason = "single_class"
        else:
            calibrator = IsotonicRegression(out_of_bounds="clip")
            calibrator.fit(group["raw_prob"].to_numpy(dtype=float), group["y_true"].to_numpy(dtype=float))
            calibrators[(regime_id, int(innings), str(phase_label))] = calibrator
            fit_status = "fitted"

        guardrail_rows.append(
            {
                "regime_id": regime_id,
                "innings": int(innings),
                "phase_label": str(phase_label),
                "n_samples": n_samples,
                "unique_probs": unique_probs,
                "outcome_classes": class_count,
                "fit_status": fit_status,
                "guard_reason": guard_reason,
            }
        )

    return (
        {
            "group_columns": ["regime_id", "innings", "phase_label"],
            "min_samples": int(min_samples),
            "min_unique_probs": int(min_unique_probs),
            "calibrators": calibrators,
        },
        pd.DataFrame(guardrail_rows),
    )


def apply_guarded_regime_phase_calibration(
    df: pd.DataFrame,
    raw_probs: np.ndarray,
    bundle: dict,
) -> Tuple[np.ndarray, pd.DataFrame]:
    working = _with_phase_labels(df)
    calibrators = bundle.get("calibrators", {})
    raw_arr = np.asarray(raw_probs, dtype=float)
    calibrated = raw_arr.copy()
    route_rows: List[dict] = []

    for idx, row in working.iterrows():
        key = (row["regime_id"], int(row["innings"]), str(row["phase_label"]))
        calibrator = calibrators.get(key)
        source = "raw_fallback"
        calibrated_prob = float(raw_arr[idx])
        if calibrator is not None:
            calibrated_prob = float(np.clip(calibrator.transform([raw_arr[idx]])[0], 0.0, 1.0))
            calibrated[idx] = calibrated_prob
            source = "regime_phase"

        route_rows.append(
            {
                "regime_id": row["regime_id"],
                "innings": int(row["innings"]),
                "phase_label": str(row["phase_label"]),
                "calibration_key": f"{row['regime_id']}|inn{int(row['innings'])}|{row['phase_label']}",
                "calibration_source": source,
                "raw_predicted_prob": float(raw_arr[idx]),
                "calibrated_predicted_prob": calibrated_prob,
            }
        )

    return calibrated, pd.DataFrame(route_rows)


def summarize_guarded_regime_phase_calibration(
    split: str,
    method: str,
    guardrails_df: pd.DataFrame,
    routing_df: pd.DataFrame,
    min_samples: int,
    min_unique_probs: int,
) -> pd.DataFrame:
    fitted = int((guardrails_df.get("fit_status") == "fitted").sum()) if not guardrails_df.empty else 0
    total_slices = int(len(guardrails_df))
    applied_rows = int((routing_df.get("calibration_source") == "regime_phase").sum()) if not routing_df.empty else 0
    total_rows = int(len(routing_df))
    skipped = guardrails_df[guardrails_df["fit_status"] != "fitted"] if not guardrails_df.empty else pd.DataFrame()
    reason_counts = (
        skipped["guard_reason"].value_counts().sort_index().to_dict()
        if not skipped.empty and "guard_reason" in skipped.columns
        else {}
    )
    reason_text = "; ".join(f"{key}:{value}" for key, value in reason_counts.items()) if reason_counts else ""
    return pd.DataFrame(
        [
            {
                "method": method,
                "split": split,
                "min_samples": int(min_samples),
                "min_unique_probs": int(min_unique_probs),
                "candidate_slices": total_slices,
                "fitted_slices": fitted,
                "skipped_slices": max(total_slices - fitted, 0),
                "applied_rows": applied_rows,
                "applied_share": (applied_rows / total_rows) if total_rows else 0.0,
                "fallback_rows": max(total_rows - applied_rows, 0),
                "fallback_share": ((total_rows - applied_rows) / total_rows) if total_rows else 0.0,
                "skip_reason_counts": reason_text,
            }
        ]
    )


def apply_inn2_powerplay_variant(
    df: pd.DataFrame,
    baseline_probs: np.ndarray,
    cluster_probs: np.ndarray,
    variant: str,
    pp_influence_cap: float = 0.04,
    dominant_cluster_quantile: float = 0.75,
    dominant_confidence_min: float = 0.55,
) -> Tuple[np.ndarray, pd.DataFrame]:
    working = _with_phase_labels(df)
    baseline_arr = np.clip(np.asarray(baseline_probs, dtype=float), 0.0, 1.0)
    cluster_arr = np.clip(np.asarray(cluster_probs, dtype=float), 0.0, 1.0)
    if len(working) != len(baseline_arr) or len(working) != len(cluster_arr):
        raise ValueError("Prediction arrays must match the routing frame length")

    if variant not in {"v18A_hard_pp_fallback", "v18B_confidence_cap", "v18C_dominant_cluster_only"}:
        raise ValueError(f"Unsupported Inn2 PP conservative variant: {variant}")

    innings = pd.to_numeric(working.get("innings"), errors="coerce").fillna(0).astype(int)
    phase = working["phase_label"].astype(str)
    pp_mask = (innings == 2) & (phase == PHASE_POWERPLAY)

    regime_confidence = pd.to_numeric(working.get("regime_confidence"), errors="coerce").fillna(0.0)
    regime_cluster_size = pd.to_numeric(working.get("regime_cluster_size"), errors="coerce").fillna(0.0)
    stability_flag = working.get("stability_flag", pd.Series(["unstable"] * len(working), index=working.index)).astype(str)

    dominant_threshold = (
        float(regime_cluster_size[regime_cluster_size > 0].quantile(dominant_cluster_quantile))
        if (regime_cluster_size > 0).any()
        else 0.0
    )

    blended = cluster_arr.copy()
    route_rows: List[dict] = []
    for idx, is_pp in enumerate(pp_mask.to_numpy()):
        predicted_prob = float(cluster_arr[idx])
        route_source = "cluster_features"
        route_reason = "outside_inn2_pp"

        if is_pp:
            if variant == "v18A_hard_pp_fallback":
                predicted_prob = float(baseline_arr[idx])
                route_source = "baseline_fallback"
                route_reason = "hard_inn2_pp_fallback"
            elif variant == "v18B_confidence_cap":
                delta = float(cluster_arr[idx] - baseline_arr[idx])
                capped_delta = float(np.clip(delta, -abs(pp_influence_cap), abs(pp_influence_cap)))
                predicted_prob = float(np.clip(baseline_arr[idx] + capped_delta, 0.0, 1.0))
                route_source = "capped_cluster_features"
                route_reason = "inn2_pp_small_influence_cap"
            else:
                is_dominant_cluster = bool(regime_cluster_size.iloc[idx] >= dominant_threshold)
                is_stable_cluster = stability_flag.iloc[idx] == "stable"
                has_confident_assignment = bool(regime_confidence.iloc[idx] >= dominant_confidence_min)
                if is_dominant_cluster and is_stable_cluster and has_confident_assignment:
                    route_source = "dominant_stable_cluster_features"
                    route_reason = "inn2_pp_dominant_stable_cluster"
                else:
                    predicted_prob = float(baseline_arr[idx])
                    route_source = "baseline_fallback"
                    route_reason = "inn2_pp_non_dominant_or_unstable_cluster"

        blended[idx] = predicted_prob
        route_rows.append(
            {
                "route_source": route_source,
                "route_reason": route_reason,
                "baseline_predicted_prob": float(baseline_arr[idx]),
                "cluster_predicted_prob": float(cluster_arr[idx]),
                "dominant_cluster_threshold": float(dominant_threshold),
                "regime_confidence_threshold": float(dominant_confidence_min),
                "pp_influence_cap": float(pp_influence_cap),
            }
        )

    return blended, pd.DataFrame(route_rows)


def select_model_columns(df: pd.DataFrame) -> List[str]:
    numeric_columns = df.select_dtypes(include=[np.number, "bool"]).columns.tolist()
    return [column for column in numeric_columns if column not in META_COLUMNS]


def summarize_regimes(
    assignments_df: pd.DataFrame,
    embedding_columns: Sequence[str],
) -> pd.DataFrame:
    if assignments_df.empty:
        return pd.DataFrame()

    working_df = assignments_df.copy()
    for column in ["is_powerplay", "is_middle_overs", "is_death_overs"]:
        if column not in working_df.columns:
            working_df[column] = 0.0

    summary = (
        working_df.groupby("regime_id")
        .agg(
            rows=("row_key", "size"),
            coverage=("row_key", lambda values: len(values) / len(working_df)),
            regime_cluster_win_rate=("is_winner", "mean"),
            regime_confidence=("regime_confidence", "mean"),
            centroid_distance=("centroid_distance", "mean"),
            pressure_index=("pressure_index", "mean"),
            wickets_lost=("wickets_lost", "mean"),
            acceleration_potential=("acceleration_potential", "mean"),
            resource_win_prob=("resource_win_prob", "mean"),
            is_powerplay=("is_powerplay", "mean"),
            is_middle_overs=("is_middle_overs", "mean"),
            is_death_overs=("is_death_overs", "mean"),
        )
        .reset_index()
    )

    centroids = working_df.groupby("regime_id")[list(embedding_columns)].mean()
    separation_map: Dict[int, float] = {}
    if len(centroids) > 1:
        for regime_id, centroid in centroids.iterrows():
            distances = [
                float(np.linalg.norm(centroid.to_numpy(dtype=float) - centroids.loc[other].to_numpy(dtype=float)))
                for other in centroids.index
                if other != regime_id
            ]
            separation_map[int(regime_id)] = min(distances) if distances else 0.0
    else:
        separation_map[int(centroids.index[0])] = 0.0

    stability_rows: Dict[int, float] = {}
    if "season" in working_df.columns:
        per_season = (
            working_df.groupby(["regime_id", "season"])["is_winner"]
            .mean()
            .groupby(level=0)
            .std()
            .fillna(0.0)
        )
        stability_rows = {int(index): float(value) for index, value in per_season.items()}

    summary["centroid_separation"] = summary["regime_id"].map(separation_map).fillna(0.0)
    summary["stability_std"] = summary["regime_id"].map(stability_rows).fillna(0.0)
    summary["stability_flag"] = np.where(
        summary["rows"] >= 50,
        np.where(summary["stability_std"] <= 0.08, "stable", "borderline"),
        "unstable",
    )
    summary["regime_label"] = summary.apply(_label_regime_row, axis=1)
    return summary.sort_values("regime_id").reset_index(drop=True)


def _label_regime_row(row: pd.Series) -> str:
    candidates: List[Tuple[str, float]] = [
        ("collapse_risk", float(row.get("wickets_lost", 0.0))),
        ("pressure_state", float(row.get("pressure_index", 0.0))),
        ("acceleration_potential", float(row.get("acceleration_potential", 0.0))),
        ("volatility_regime", abs(float(row.get("regime_cluster_win_rate", 0.5)) - 0.5)),
    ]
    if float(row.get("is_death_overs", 0.0)) >= 0.5:
        candidates.append(("death_overs_acceleration", float(row.get("acceleration_potential", 0.0)) + 0.25))
    if float(row.get("resource_win_prob", 0.5)) < 0.35:
        candidates.append(("defensive_pressure", 0.9 - float(row.get("resource_win_prob", 0.5))))
    return max(candidates, key=lambda item: item[1])[0]


def build_regime_feature_frame(
    assignments_df: pd.DataFrame,
    analogue_features_df: pd.DataFrame,
) -> pd.DataFrame:
    regime_columns = [
        "row_key",
        "regime_id",
        "regime_confidence",
        "regime_cluster_win_rate",
        "regime_cluster_size",
        "regime_label",
    ]
    available_regime_columns = [column for column in regime_columns if column in assignments_df.columns]
    output = assignments_df[available_regime_columns].drop_duplicates("row_key").copy()
    if "regime_label" not in output.columns:
        output["regime_label"] = "unlabeled"
    if not analogue_features_df.empty:
        output = output.merge(analogue_features_df, on="row_key", how="left")
    for column in [
        "neighbor_win_rate_k",
        "neighbor_outcome_std_k",
        "neighbor_mean_resource_prob_k",
        "neighbor_distance_mean_k",
    ]:
        if column not in output.columns:
            output[column] = np.nan
    return output


def check_go_no_go(
    metrics_df: pd.DataFrame,
    segment_metrics_df: pd.DataFrame,
    baseline_variant: str,
    candidate_variants: Iterable[str],
    ece_tolerance: float = 0.0,
    segment_brier_regression_tol: float = 0.003,
    segment_logloss_regression_tol: float = 0.01,
) -> GateDecision:
    if metrics_df.empty:
        return GateDecision("no_go", None, ["No metrics available"], {})

    overall = metrics_df[
        (metrics_df["split"] == "holdout") & (metrics_df["segment"] == "overall")
    ].set_index("method")
    if baseline_variant not in overall.index:
        return GateDecision("no_go", None, ["Baseline metrics missing"], {})

    baseline = overall.loc[baseline_variant]
    gates: Dict[str, bool] = {}
    failures: List[str] = []
    winner: Optional[str] = None
    best_gain = -np.inf

    seg_base = {}
    if not segment_metrics_df.empty:
        seg_base = (
            segment_metrics_df[segment_metrics_df["method"] == baseline_variant]
            .set_index("segment")[["brier", "log_loss"]]
            .to_dict("index")
        )

    for variant in candidate_variants:
        if variant not in overall.index:
            gates[variant] = False
            failures.append(f"[{variant}] Metrics missing")
            continue
        candidate = overall.loc[variant]
        variant_failures: List[str] = []
        brier_delta = float(candidate["brier"] - baseline["brier"])
        log_loss_delta = float(candidate["log_loss"] - baseline["log_loss"])
        ece_delta = float(candidate["ece"] - baseline["ece"])

        if brier_delta >= 0:
            variant_failures.append(f"Brier did not improve (delta={brier_delta:+.4f})")
        if log_loss_delta >= 0:
            variant_failures.append(f"Log loss did not improve (delta={log_loss_delta:+.4f})")
        if ece_delta > ece_tolerance:
            variant_failures.append(f"ECE worsened beyond tolerance (delta={ece_delta:+.4f})")

        if seg_base:
            seg_candidate = (
                segment_metrics_df[segment_metrics_df["method"] == variant]
                .set_index("segment")[["brier", "log_loss"]]
                .to_dict("index")
            )
            for segment, base_values in seg_base.items():
                candidate_values = seg_candidate.get(segment)
                if not candidate_values:
                    continue
                if candidate_values["brier"] - base_values["brier"] > segment_brier_regression_tol:
                    variant_failures.append(
                        f"Segment {segment} Brier regressed by {candidate_values['brier'] - base_values['brier']:+.4f}"
                    )
                if candidate_values["log_loss"] - base_values["log_loss"] > segment_logloss_regression_tol:
                    variant_failures.append(
                        f"Segment {segment} log loss regressed by {candidate_values['log_loss'] - base_values['log_loss']:+.4f}"
                    )

        gates[variant] = not variant_failures
        if variant_failures:
            failures.extend(f"[{variant}] {failure}" for failure in variant_failures)
            continue

        gain = (-brier_delta) + (-log_loss_delta)
        if gain > best_gain:
            best_gain = gain
            winner = variant

    recommendation = "go" if winner else "no_go"
    if not winner and overall.index.difference([baseline_variant]).size > 0 and not any(gates.values()):
        recommendation = "no_go"
    return GateDecision(recommendation, winner, failures, gates)


def render_pilot_report(
    metrics_df: pd.DataFrame,
    segment_metrics_df: pd.DataFrame,
    reliability_df: pd.DataFrame,
    manifest: Dict[str, object],
    retrieval_summary: Dict[str, object],
    regime_summary_df: pd.DataFrame,
    decision: GateDecision,
    mode: str,
    season_slice_metrics_df: Optional[pd.DataFrame] = None,
    calibration_summary_df: Optional[pd.DataFrame] = None,
) -> str:
    lines = [
        "# IPL State Embeddings Offline Pilot Report",
        "",
        f"**Mode**: `{mode}`",
        f"**Corpus coverage**: {float(manifest.get('corpus_coverage', 0.0)):.2%}",
        f"**Retrieval coverage**: {float(retrieval_summary.get('coverage', 0.0)):.2%}",
        "",
        "## Overall Metrics",
        "",
    ]

    if not metrics_df.empty:
        header = (
            "| Variant | N | Brier | Log Loss | ECE | "
            "ΔBrier vs Base | ΔLogLoss vs Base | ΔECE vs Base | "
            "ΔBrier vs Cluster | ΔLogLoss vs Cluster | ΔECE vs Cluster |"
        )
        sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
        lines.extend([header, sep])
        overall = metrics_df[(metrics_df["split"] == "holdout") & (metrics_df["segment"] == "overall")]
        for _, row in overall.iterrows():
            lines.append(
                (
                    "| `{}` | {} | {:.4f} | {:.4f} | {:.4f} | {:+.4f} | {:+.4f} | {:+.4f} | "
                    "{:+.4f} | {:+.4f} | {:+.4f} |"
                ).format(
                    row["method"],
                    int(row["n"]),
                    row["brier"],
                    row["log_loss"],
                    row["ece"],
                    row.get("baseline_brier_delta", 0.0) or 0.0,
                    row.get("baseline_log_loss_delta", 0.0) or 0.0,
                    row.get("baseline_ece_delta", 0.0) or 0.0,
                    row.get("cluster_winner_brier_delta", 0.0) or 0.0,
                    row.get("cluster_winner_log_loss_delta", 0.0) or 0.0,
                    row.get("cluster_winner_ece_delta", 0.0) or 0.0,
                )
            )
    else:
        lines.append("_No metrics available._")

    lines.extend(["", "## Season-Slice Validation", ""])
    if season_slice_metrics_df is not None and not season_slice_metrics_df.empty:
        header = (
            "| Slice | Variant | N | Brier | Log Loss | ECE | "
            "ΔBrier vs Base | ΔLogLoss vs Base | ΔECE vs Base | "
            "ΔBrier vs Cluster | ΔLogLoss vs Cluster | ΔECE vs Cluster |"
        )
        sep = "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
        lines.extend([header, sep])
        overall_slice_rows = season_slice_metrics_df[season_slice_metrics_df["segment"] == "overall"].sort_values(["split", "method"])
        for _, row in overall_slice_rows.iterrows():
            lines.append(
                (
                    "| `{}` | `{}` | {} | {:.4f} | {:.4f} | {:.4f} | {:+.4f} | {:+.4f} | {:+.4f} | "
                    "{:+.4f} | {:+.4f} | {:+.4f} |"
                ).format(
                    row["split"],
                    row["method"],
                    int(row["n"]),
                    row["brier"],
                    row["log_loss"],
                    row["ece"],
                    row.get("baseline_brier_delta", 0.0) or 0.0,
                    row.get("baseline_log_loss_delta", 0.0) or 0.0,
                    row.get("baseline_ece_delta", 0.0) or 0.0,
                    row.get("cluster_winner_brier_delta", 0.0) or 0.0,
                    row.get("cluster_winner_log_loss_delta", 0.0) or 0.0,
                    row.get("cluster_winner_ece_delta", 0.0) or 0.0,
                )
            )
    else:
        lines.append("_No season-slice results available._")

    lines.extend(["", "## Segment Metrics", ""])
    if not segment_metrics_df.empty:
        lines.extend(
            [
                (
                    "| Variant | Segment | Brier | Log Loss | ECE | "
                    "ΔBrier vs Base | ΔLogLoss vs Base | ΔECE vs Base | "
                    "ΔBrier vs Cluster | ΔLogLoss vs Cluster | ΔECE vs Cluster |"
                ),
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for _, row in segment_metrics_df.iterrows():
            lines.append(
                "| `{}` | {} | {:.4f} | {:.4f} | {:.4f} | {:+.4f} | {:+.4f} | {:+.4f} | {:+.4f} | {:+.4f} | {:+.4f} |".format(
                    row["method"],
                    row["segment"],
                    row["brier"],
                    row["log_loss"],
                    row["ece"],
                    row.get("baseline_brier_delta", 0.0) or 0.0,
                    row.get("baseline_log_loss_delta", 0.0) or 0.0,
                    row.get("baseline_ece_delta", 0.0) or 0.0,
                    row.get("cluster_winner_brier_delta", 0.0) or 0.0,
                    row.get("cluster_winner_log_loss_delta", 0.0) or 0.0,
                    row.get("cluster_winner_ece_delta", 0.0) or 0.0,
                )
            )
    else:
        lines.append("_No segment metrics available._")

    lines.extend(["", "## Regime-Conditioned Calibration Guardrails", ""])
    if calibration_summary_df is not None and not calibration_summary_df.empty:
        lines.extend(
            [
                "| Split | Variant | Min Samples | Candidate Slices | Fitted Slices | Applied Rows | Applied Share | Fallback Share | Skip Reasons |",
                "|---|---|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for _, row in calibration_summary_df.sort_values(["split", "method"]).iterrows():
            lines.append(
                "| `{}` | `{}` | {} | {} | {} | {} | {:.2%} | {:.2%} | {} |".format(
                    row["split"],
                    row["method"],
                    int(row["min_samples"]),
                    int(row["candidate_slices"]),
                    int(row["fitted_slices"]),
                    int(row["applied_rows"]),
                    float(row["applied_share"]),
                    float(row["fallback_share"]),
                    row.get("skip_reason_counts", "") or "-",
                )
            )
    else:
        lines.append("_No regime-conditioned calibration summaries available._")

    lines.extend(["", "## Regime Quality", ""])
    if not regime_summary_df.empty:
        lines.extend(
            [
                "| Regime | Label | Rows | Coverage | Win Rate | Separation | Stability |",
                "|---:|---|---:|---:|---:|---:|---|",
            ]
        )
        for _, row in regime_summary_df.iterrows():
            lines.append(
                f"| {int(row['regime_id'])} | {row['regime_label']} | {int(row['rows'])} | {row['coverage']:.2%} | "
                f"{row['regime_cluster_win_rate']:.3f} | {row['centroid_separation']:.3f} | {row['stability_flag']} |"
            )
    else:
        lines.append("_No regime summary available._")

    lines.extend(["", "## Reliability Coverage", ""])
    if not reliability_df.empty:
        lines.append(f"- Saved {len(reliability_df)} reliability-bin rows.")
    else:
        lines.append("- No reliability-bin rows generated.")

    lines.extend(["", "## Verdict", ""])
    if decision.winning_variant:
        lines.append(f"**GO**: `{decision.winning_variant}` beat the baseline on both Brier and log loss without material segment regressions.")
    else:
        lines.append("**NO-GO**: No regime-aware variant beat baseline on both Brier and log loss without material segment regressions.")
        lines.append("**No production change.** This pilot stays offline-only.")

    if decision.gate_failures:
        lines.extend(["", "### Gate failures"])
        lines.extend(f"- {failure}" for failure in decision.gate_failures)

    return "\n".join(lines) + "\n"
