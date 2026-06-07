"""
Canonical proof-metrics builder for the CrickenZen dashboard.

Produces versioned metrics snapshots (probability quality + match-call accuracy),
segment metrics, proof-ledger rows, and manifests for the proof page and Ask
CrickenZen surfaces.

Canonical decisions (V1):
- Probability column: model_final_prob
- ECE method: histogram binning (10 bins, matching StateAnalyzer)
- Probability source: completed match-state rows with non-null winner
- Accuracy source: comparable prediction-call rows with predicted side + final result
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss


METRIC_DEFINITIONS = {
    "brier": "Lower is better. Measures probability error (0 = perfect, 1 = worst).",
    "ece": "Lower is better. Measures calibration gap between predicted confidence and actual accuracy.",
    "log_loss": "Lower is better. Penalises confident wrong predictions. Included as supporting context.",
    "accuracy": "Higher is better. Measures discrete pre-match call hit rate. NOT a probability-quality metric.",
}

STALENESS_THRESHOLD_HOURS = 24
DEFAULT_WINDOWS = ["last_7_days", "last_30_days", "all_available"]


@dataclass
class ProbabilityMetricsSummary:
    """Overall probability-quality metrics for one league + window."""

    brier: Optional[float] = None
    ece: Optional[float] = None
    log_loss: Optional[float] = None
    sample_count: int = 0
    excluded_rows: int = 0


@dataclass
class AccuracyMetricsSummary:
    """Overall match-call accuracy metrics for one league + window."""

    accuracy_pct: Optional[float] = None
    wins: int = 0
    losses: int = 0
    sample_count: int = 0
    excluded_rows: int = 0


@dataclass
class SegmentMetricRow:
    """One grouped metric row (by innings, phase, or other slice)."""

    segment_type: str
    segment_key: str
    segment_label: str
    brier: Optional[float] = None
    ece: Optional[float] = None
    log_loss: Optional[float] = None
    sample_count: int = 0


@dataclass
class ProofLedgerRow:
    """One proof row linking a prediction call to the outcome."""

    match_label: str
    league: str
    timestamp: Optional[str] = None
    predicted_side: Optional[str] = None
    predicted_probability_pct: Optional[float] = None
    confidence_band: Optional[str] = None
    final_winner: Optional[str] = None
    result_status: Optional[str] = None
    what_changed: Optional[str] = None
    source_note: Optional[str] = None


@dataclass
class MetricsBuildManifest:
    """Build metadata for a snapshot generation run."""

    build_version: int = 1
    league: str = ""
    evaluation_window: str = ""
    built_at: str = ""
    input_data_window_start: Optional[str] = None
    input_data_window_end: Optional[str] = None
    staleness_threshold_hours: int = STALENESS_THRESHOLD_HOURS
    probability_column: str = "model_final_prob"
    ece_method: str = "histogram_10_bin"
    excluded_rows_total: int = 0
    exclusion_reasons: dict[str, int] = field(default_factory=dict)
    status: str = "not_ready"


def _ece_histogram(y_true: np.ndarray, y_pred: np.ndarray, n_bins: int = 10) -> float:
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_pred, bin_edges[:-1]) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    ece = 0.0
    total = len(y_true)
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / total) * abs(y_true[mask].mean() - y_pred[mask].mean())
    return float(ece)


def _compute_probability_metrics(
    df: pd.DataFrame,
    probability_col: str = "model_final_prob",
) -> ProbabilityMetricsSummary:
    if len(df) == 0:
        return ProbabilityMetricsSummary()

    y_true = df["actual_win"].values
    y_pred = df[probability_col].values

    brier = float(brier_score_loss(y_true, y_pred))
    ece = _ece_histogram(y_true, y_pred, n_bins=10)
    ll = float(log_loss(y_true, y_pred, labels=[0, 1]))

    return ProbabilityMetricsSummary(
        brier=brier,
        ece=ece,
        log_loss=ll,
        sample_count=len(df),
    )


def _compute_segment_metrics(
    df: pd.DataFrame,
    probability_col: str = "model_final_prob",
) -> list[SegmentMetricRow]:
    segments: list[SegmentMetricRow] = []

    if len(df) == 0:
        return segments

    # By innings
    for innings in sorted(df["innings"].unique()):
        sub = df[df["innings"] == innings]
        metrics = _compute_probability_metrics(sub, probability_col)
        segments.append(
            SegmentMetricRow(
                segment_type="innings",
                segment_key=f"innings_{innings}",
                segment_label=f"Innings {innings}",
                brier=metrics.brier,
                ece=metrics.ece,
                log_loss=metrics.log_loss,
                sample_count=metrics.sample_count,
            )
        )

    # By phase
    for phase in ["powerplay", "middle", "death"]:
        sub = df[df["match_phase"] == phase]
        if len(sub) == 0:
            continue
        metrics = _compute_probability_metrics(sub, probability_col)
        segments.append(
            SegmentMetricRow(
                segment_type="phase",
                segment_key=f"phase_{phase}",
                segment_label=phase.capitalize(),
                brier=metrics.brier,
                ece=metrics.ece,
                log_loss=metrics.log_loss,
                sample_count=metrics.sample_count,
            )
        )

    # By batting_team_tier if available
    if "batting_team_tier" in df.columns:
        for tier in sorted(df["batting_team_tier"].dropna().unique()):
            sub = df[df["batting_team_tier"] == tier]
            if len(sub) == 0:
                continue
            metrics = _compute_probability_metrics(sub, probability_col)
            segments.append(
                SegmentMetricRow(
                    segment_type="team_tier",
                    segment_key=f"tier_{tier}",
                    segment_label=f"Team Tier: {tier.capitalize()}",
                    brier=metrics.brier,
                    ece=metrics.ece,
                    log_loss=metrics.log_loss,
                    sample_count=metrics.sample_count,
                )
            )

    return segments


def _filter_by_window(
    df: pd.DataFrame,
    window: str,
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    if window == "all_available":
        return df.copy()
    now = pd.Timestamp.now(tz="UTC")
    if window == "last_7_days":
        cutoff = now - pd.Timedelta(days=7)
    elif window == "last_30_days":
        cutoff = now - pd.Timedelta(days=30)
    else:
        return df.copy()
    return df[df[timestamp_col] >= cutoff].copy()


def _merge_winner(df: pd.DataFrame, metadata_path: Path) -> pd.DataFrame:
    if not metadata_path.exists():
        df = df.copy()
        df["winner"] = None
        return df
    metadata = pd.read_parquet(metadata_path)
    if "winner" not in metadata.columns:
        df = df.copy()
        df["winner"] = None
        return df
    return df.merge(metadata[["match_id", "winner"]], on="match_id", how="left")


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, float) and math.isinf(value):
        return None
    return float(value)


def _to_iso(ts: Any) -> Optional[str]:
    if ts is None:
        return None
    if isinstance(ts, pd.Timestamp):
        return ts.isoformat()
    return str(ts)


def build_probability_snapshot(
    states_path: Path,
    metadata_path: Path,
    league: str,
    window: str = "all_available",
    probability_col: str = "model_final_prob",
    output_dir: Optional[Path] = None,
) -> dict[str, Any]:
    exclusion_reasons: dict[str, int] = {}

    if not states_path.exists():
        return {
            "status": "not_ready",
            "reason": "states_path_not_found",
            "league": league,
            "window": window,
        }

    df = pd.read_parquet(states_path)
    total_rows = len(df)

    df = _merge_winner(df, metadata_path)

    # actual_win: did the batting team win?
    df["actual_win"] = (df["batting_team"] == df["winner"]).astype(int)

    # Exclude rows without outcomes
    before_filter = len(df)
    df = df[df["winner"].notna()].copy()
    excluded_no_winner = before_filter - len(df)
    if excluded_no_winner > 0:
        exclusion_reasons["missing_winner"] = excluded_no_winner

    # Exclude rows missing probability column
    before_filter = len(df)
    df = df[df[probability_col].notna()].copy()
    excluded_missing_prob = before_filter - len(df)
    if excluded_missing_prob > 0:
        exclusion_reasons["missing_probability"] = excluded_missing_prob

    # Apply evaluation window
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = _filter_by_window(df, window)

    eligible_count = len(df)
    excluded_total = total_rows - eligible_count

    # Compute metrics
    prob_metrics = _compute_probability_metrics(df, probability_col)
    segments = _compute_segment_metrics(df, probability_col)

    # Build manifest
    built_at = datetime.now(timezone.utc).isoformat()
    input_start = None
    input_end = None
    if "timestamp" in df.columns and len(df) > 0:
        input_start = _to_iso(df["timestamp"].min())
        input_end = _to_iso(df["timestamp"].max())

    status = "ready" if eligible_count > 0 else "not_ready"

    manifest = MetricsBuildManifest(
        build_version=1,
        league=league,
        evaluation_window=window,
        built_at=built_at,
        input_data_window_start=input_start,
        input_data_window_end=input_end,
        probability_column=probability_col,
        excluded_rows_total=excluded_total,
        exclusion_reasons=exclusion_reasons,
        status=status,
    )

    prob_metrics.excluded_rows = excluded_total

    # Assemble summary
    summary = {
        "league": league,
        "window": window,
        "status": status,
        "probability_metrics": {
            "brier": prob_metrics.brier,
            "ece": prob_metrics.ece,
            "log_loss": prob_metrics.log_loss,
            "sample_count": prob_metrics.sample_count,
            "excluded_rows": excluded_total,
        },
        "accuracy_metrics": None,  # filled by build_accuracy_snapshot
        "freshness": {
            "built_at": built_at,
            "stale": False,
        },
        "definitions": METRIC_DEFINITIONS,
    }

    segment_data = [asdict(s) for s in segments]

    result = {
        "manifest": asdict(manifest),
        "summary": summary,
        "segments": segment_data,
    }

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_snapshot_artifacts(result, league, window, output_dir)

    return result


def build_accuracy_ledger(
    accuracy_rows: list[dict[str, Any]],
    league: str,
    window: str = "all_available",
    output_dir: Optional[Path] = None,
) -> dict[str, Any]:
    exclusion_reasons: dict[str, int] = {}
    excluded_total = 0
    valid_rows: list[ProofLedgerRow] = []
    ledger_rows: list[ProofLedgerRow] = []

    now = pd.Timestamp.now(tz="UTC")
    if window == "last_7_days":
        cutoff = now - pd.Timedelta(days=7)
    elif window == "last_30_days":
        cutoff = now - pd.Timedelta(days=30)
    else:
        cutoff = None

    for row in accuracy_rows:
        predicted_side = row.get("predicted_side") or row.get("pre_match_favorite")
        final_winner = row.get("winner") or row.get("final_result")
        match_label = row.get("match") or row.get("match_label", "Unknown match")
        timestamp_raw = row.get("timestamp") or row.get("source_timestamp") or row.get("date")
        timestamp = _to_iso(timestamp_raw)

        if cutoff is not None:
            parsed = None
            if isinstance(timestamp_raw, pd.Timestamp):
                parsed = timestamp_raw
            elif isinstance(timestamp_raw, str):
                try:
                    parsed = pd.Timestamp(timestamp_raw)
                except (ValueError, TypeError):
                    pass
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.tz_localize("UTC")
                if parsed < cutoff:
                    excluded_total += 1
                    exclusion_reasons["outside_window"] = exclusion_reasons.get("outside_window", 0) + 1
                    continue
            else:
                excluded_total += 1
                exclusion_reasons["missing_timestamp_for_window"] = exclusion_reasons.get("missing_timestamp_for_window", 0) + 1
                continue

        # Validate required fields
        if not predicted_side:
            exclusion_reasons["missing_predicted_side"] = exclusion_reasons.get("missing_predicted_side", 0) + 1
            excluded_total += 1
            continue
        if not final_winner:
            exclusion_reasons["missing_final_result"] = exclusion_reasons.get("missing_final_result", 0) + 1
            excluded_total += 1
            continue

        is_correct = predicted_side == final_winner
        result_status = "correct" if is_correct else "incorrect"

        prob_pct = row.get("win_probability_pct")
        if prob_pct is None and row.get("probability") is not None:
            prob_pct = row["probability"] * 100

        confidence_band = row.get("confidence_band") or row.get("confidence")
        what_changed = row.get("what_changed") or row.get("reason") or row.get("review")

        ledger_row = ProofLedgerRow(
            match_label=match_label,
            league=league,
            timestamp=timestamp,
            predicted_side=predicted_side,
            predicted_probability_pct=_safe_float(prob_pct),
            confidence_band=confidence_band,
            final_winner=final_winner,
            result_status=result_status,
            what_changed=what_changed,
            source_note=row.get("source_note"),
        )
        ledger_rows.append(ledger_row)
        valid_rows.append(ledger_row)

    wins = sum(1 for r in valid_rows if r.result_status == "correct")
    losses = len(valid_rows) - wins
    total = wins + losses

    accuracy_pct = None
    if total > 0:
        accuracy_pct = round((wins / total) * 100, 1)

    built_at = datetime.now(timezone.utc).isoformat()
    status = "ready" if total > 0 else "not_ready"

    accuracy_summary = {
        "league": league,
        "window": window,
        "status": status,
        "accuracy_metrics": {
            "accuracy_pct": accuracy_pct,
            "wins": wins,
            "losses": losses,
            "sample_count": total,
            "excluded_rows": excluded_total,
        },
        "freshness": {
            "built_at": built_at,
            "stale": False,
        },
        "definitions": {
            "accuracy": METRIC_DEFINITIONS["accuracy"],
        },
    }

    result = {
        "accuracy_summary": accuracy_summary,
        "ledger": [asdict(r) for r in ledger_rows],
    }

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_accuracy_artifacts(result, league, window, output_dir)

    return result


def build_unified_snapshot(
    states_path: Path,
    metadata_path: Path,
    league: str,
    window: str = "all_available",
    accuracy_rows: Optional[list[dict[str, Any]]] = None,
    probability_col: str = "model_final_prob",
    output_dir: Optional[Path] = None,
) -> dict[str, Any]:
    prob_result = build_probability_snapshot(
        states_path=states_path,
        metadata_path=metadata_path,
        league=league,
        window=window,
        probability_col=probability_col,
    )

    if accuracy_rows is None:
        accuracy_rows = _derive_accuracy_from_states(
            states_path, metadata_path, league, window
        )

    acc_result = build_accuracy_ledger(
        accuracy_rows=accuracy_rows,
        league=league,
        window=window,
    )

    # Merge accuracy into summary
    prob_result["summary"]["accuracy_metrics"] = acc_result["accuracy_summary"]["accuracy_metrics"]

    result = {
        "manifest": prob_result["manifest"],
        "summary": prob_result["summary"],
        "segments": prob_result["segments"],
        "accuracy_summary": acc_result["accuracy_summary"],
        "ledger": acc_result["ledger"],
    }

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_snapshot_artifacts(prob_result, league, window, output_dir)
        _write_accuracy_artifacts(acc_result, league, window, output_dir)
        _write_manifest(prob_result["manifest"], league, window, output_dir)

    return result


def _write_snapshot_artifacts(
    prob_result: dict[str, Any],
    league: str,
    window: str,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    league_lower = league.lower()

    # Summary
    summary_path = output_dir / f"{league_lower}_{window}_summary.json"
    with open(summary_path, "w") as f:
        json.dump(prob_result["summary"], f, indent=2)

    # Segments
    segments_path = output_dir / f"{league_lower}_{window}_segments.json"
    with open(segments_path, "w") as f:
        json.dump(prob_result["segments"], f, indent=2)

    # Latest symlink copies
    latest_dir = output_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ["summary", "segments"]:
        src_path = output_dir / f"{league_lower}_{window}_{suffix}.json"
        dst_path = latest_dir / f"{league_lower}_{suffix}.json"
        try:
            dst_path.unlink(missing_ok=True)
        except OSError:
            pass
        with open(src_path, "r") as fsrc, open(dst_path, "w") as fdst:
            fdst.write(fsrc.read())


def _write_accuracy_artifacts(
    acc_result: dict[str, Any],
    league: str,
    window: str,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    league_lower = league.lower()

    # Accuracy summary
    acc_summary_path = output_dir / f"{league_lower}_{window}_accuracy.json"
    with open(acc_summary_path, "w") as f:
        json.dump(acc_result["accuracy_summary"], f, indent=2)

    # Ledger
    ledger_path = output_dir / f"{league_lower}_{window}_ledger.json"
    with open(ledger_path, "w") as f:
        json.dump(acc_result["ledger"], f, indent=2)

    # Latest copies
    latest_dir = output_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ["accuracy", "ledger"]:
        src_path = output_dir / f"{league_lower}_{window}_{suffix}.json"
        dst_path = latest_dir / f"{league_lower}_{suffix}.json"
        try:
            dst_path.unlink(missing_ok=True)
        except OSError:
            pass
        with open(src_path, "r") as fsrc, open(dst_path, "w") as fdst:
            fdst.write(fsrc.read())


def _write_manifest(
    manifest: dict[str, Any],
    league: str,
    window: str,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    league_lower = league.lower()
    manifest_path = output_dir / f"{league_lower}_{window}_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Latest copy
    latest_dir = output_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    dst_path = latest_dir / f"{league_lower}_manifest.json"
    try:
        dst_path.unlink(missing_ok=True)
    except OSError:
        pass
    with open(manifest_path, "r") as fsrc, open(dst_path, "w") as fdst:
        fdst.write(fsrc.read())


def _derive_accuracy_from_states(
    states_path: Path,
    metadata_path: Path,
    league: str,
    window: str = "all_available",
    probability_col: str = "model_final_prob",
) -> list[dict[str, Any]]:
    if not states_path.exists() or not metadata_path.exists():
        return []

    try:
        states_df = pd.read_parquet(states_path, columns=["match_id", "batting_team", "bowling_team", probability_col, "timestamp"])
        metadata_df = pd.read_parquet(metadata_path)
    except Exception:
        return []

    if "winner" not in metadata_df.columns:
        return []

    completed = metadata_df[metadata_df["winner"].notna()].copy()
    if len(completed) == 0:
        return []

    if "timestamp" in states_df.columns:
        states_df["timestamp"] = pd.to_datetime(states_df["timestamp"], utc=True)
    else:
        states_df["timestamp"] = None

    now = pd.Timestamp.now(tz="UTC")
    if window == "last_7_days":
        cutoff = now - pd.Timedelta(days=7)
    elif window == "last_30_days":
        cutoff = now - pd.Timedelta(days=30)
    else:
        cutoff = None

    accuracy_rows: list[dict[str, Any]] = []
    for _, meta_row in completed.iterrows():
        match_id = meta_row["match_id"]
        winner = meta_row["winner"]

        match_states = states_df[states_df["match_id"] == match_id]
        if len(match_states) == 0:
            continue

        first_ball = match_states.iloc[0]
        match_ts = first_ball.get("timestamp")
        if cutoff is not None and match_ts is not None:
            if isinstance(match_ts, pd.Timestamp) and match_ts < cutoff:
                continue

        batting_team = str(first_ball.get("batting_team", ""))
        bowling_team = str(first_ball.get("bowling_team", ""))
        prob = first_ball.get(probability_col)
        if pd.isna(prob):
            continue

        predicted_side = batting_team if float(prob) >= 0.5 else bowling_team
        match_label = f"{batting_team} vs {bowling_team}"

        accuracy_rows.append({
            "match_label": match_label,
            "match_id": match_id,
            "timestamp": _to_iso(match_ts),
            "predicted_side": predicted_side,
            "win_probability_pct": round(float(prob) * 100),
            "winner": winner,
        })

    return accuracy_rows


def compute_accuracy_from_prematch_rows(
    prematch_rows: list[dict[str, Any]],
    results: dict[str, str],
    league: str,
    window: str = "all_available",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in prematch_rows:
        match_id = row.get("match_id") or row.get("match")
        if match_id and match_id in results:
            row["winner"] = results[match_id]
        if "winner" not in row and "final_result" not in row:
            row["final_result"] = row.get("winner")
        rows.append(row)

    return build_accuracy_ledger(
        accuracy_rows=rows,
        league=league,
        window=window,
    )
