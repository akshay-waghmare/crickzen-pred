"""Reproducible market-vs-model scoring and candidate promotion gates.

The evaluator is intentionally offline and deterministic.  Live inference only
records evidence; this module decides whether a seven-day candidate has enough
settled support to be considered for promotion.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd


PROMOTION_MARGINS = {
    "brier": 0.002,
    "log_loss": 0.010,
    "ece": 0.005,
}
INCUMBENT_TOLERANCES = {
    "brier": 0.001,
    "log_loss": 0.005,
    "ece": 0.003,
}
MIN_COMPLETED_MATCHES = 7
MIN_ELIGIBLE_ROWS = 200
MIN_MARKET_COVERAGE = 0.80
MIN_FEATURE_COMPLETENESS = 0.95
MIN_SEGMENT_ROWS = 30
ECE_BINS = 10


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    return str(value)


def _clip_probability(values: Any) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float), 1e-6, 1 - 1e-6)


def expected_calibration_error(y_true: Iterable[Any], probabilities: Iterable[Any], bins: int = ECE_BINS) -> float | None:
    """Return absolute ECE using equal-width probability bins."""
    y = np.asarray(list(y_true), dtype=float)
    p = np.asarray(list(probabilities), dtype=float)
    valid = np.isfinite(y) & np.isfinite(p) & np.isin(y, [0.0, 1.0]) & (p >= 0.0) & (p <= 1.0)
    y = y[valid]
    p = p[valid]
    if len(y) == 0:
        return None
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for index in range(bins):
        if index == bins - 1:
            mask = (p >= edges[index]) & (p <= edges[index + 1])
        else:
            mask = (p >= edges[index]) & (p < edges[index + 1])
        if not mask.any():
            continue
        total += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(total)


def _score_arrays(y_true: Iterable[Any], probabilities: Iterable[Any]) -> dict[str, float | int | None]:
    y = np.asarray(list(y_true), dtype=float)
    p = np.asarray(list(probabilities), dtype=float)
    valid = np.isfinite(y) & np.isfinite(p) & np.isin(y, [0.0, 1.0]) & (p >= 0.0) & (p <= 1.0)
    y = y[valid]
    p = p[valid]
    if len(y) == 0:
        return {"brier": None, "log_loss": None, "ece": None, "rows": 0}
    clipped = _clip_probability(p)
    return {
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(clipped) + (1 - y) * np.log(1 - clipped))),
        "ece": expected_calibration_error(y, p),
        "rows": int(len(y)),
    }


def metric_bundle(records: pd.DataFrame, probability_column: str, *, match_equal: bool = True) -> dict[str, Any]:
    """Score one probability column, optionally weighting each match equally."""
    if records.empty or probability_column not in records.columns:
        return {"weighting": "match_equal" if match_equal else "ball", "matches": 0, **_score_arrays([], [])}
    direct = records[["actual_batting_team_win", probability_column]].copy()
    direct = direct.rename(columns={probability_column: "probability"})
    direct["probability"] = pd.to_numeric(direct["probability"], errors="coerce")
    direct["actual_batting_team_win"] = pd.to_numeric(direct["actual_batting_team_win"], errors="coerce")
    direct = direct.dropna(subset=["actual_batting_team_win", "probability"])
    direct = direct[
        direct["actual_batting_team_win"].isin([0.0, 1.0])
        & direct["probability"].between(0.0, 1.0)
    ]
    if not match_equal:
        return {"weighting": "ball", "matches": int(records.loc[direct.index, "match_id"].nunique()), **_score_arrays(direct.iloc[:, 0], direct["probability"])}

    per_match: list[dict[str, Any]] = []
    for match_id, group in records.loc[direct.index].groupby("match_id", sort=True):
        scored = _score_arrays(group["actual_batting_team_win"], group[probability_column])
        if scored["rows"]:
            per_match.append({"match_id": str(match_id), **scored})
    if not per_match:
        return {"weighting": "match_equal", "matches": 0, **_score_arrays([], [])}
    frame = pd.DataFrame(per_match)
    return {
        "weighting": "match_equal",
        "matches": int(len(frame)),
        "rows": int(frame["rows"].sum()),
        "brier": float(frame["brier"].mean()),
        "log_loss": float(frame["log_loss"].mean()),
        "ece": float(frame["ece"].mean()),
    }


def _normalise_team(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _valid_probability(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.notna() & values.between(0.0, 1.0)


def _parse_window(value: Any) -> pd.Timestamp:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid review window timestamp: {value!r}")
    return parsed


def _read_parquet(path: Path) -> pd.DataFrame:
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def load_recorded_states(states_root: str | Path) -> pd.DataFrame:
    """Load state rows and completed metadata from a match-state directory."""
    root = Path(states_root)
    state_frames: list[pd.DataFrame] = []
    metadata_frames: list[pd.DataFrame] = []
    if not root.exists():
        return pd.DataFrame()
    for path in sorted(root.rglob("*.parquet")):
        frame = _read_parquet(path)
        if frame.empty:
            continue
        if path.name == "match_metadata.parquet":
            metadata_frames.append(frame)
            continue
        # The latter condition prevents accidentally ingesting derived
        # evaluator output if it is placed under the data root.
        if "match_id" not in frame.columns or "actual_batting_team_win" in frame.columns:
            continue
        frame = frame.copy()
        frame["source_file"] = str(path)
        state_frames.append(frame)
    if not state_frames:
        return pd.DataFrame()
    states = pd.concat(state_frames, ignore_index=True, sort=False)
    states["match_id"] = states["match_id"].astype(str)
    if metadata_frames:
        metadata = pd.concat(metadata_frames, ignore_index=True, sort=False)
        if "match_id" in metadata.columns:
            metadata["match_id"] = metadata["match_id"].astype(str)
            if "result_type" in metadata.columns:
                metadata["_completed_rank"] = metadata["result_type"].eq("completed").astype(int)
                metadata = metadata.sort_values(["match_id", "_completed_rank"]).drop_duplicates("match_id", keep="last")
            keep = [c for c in ["match_id", "winner", "result_type", "team_a", "team_b", "match_url"] if c in metadata.columns]
            states = states.merge(metadata[keep], on="match_id", how="left", suffixes=("", "_metadata"))
    return states


def settle_recorded_states(states: pd.DataFrame) -> pd.DataFrame:
    """Attach a batting-team outcome without guessing unresolved identities."""
    if states.empty:
        return states.copy()
    frame = states.copy()
    winner = frame.get("winner", pd.Series(index=frame.index, dtype=object))
    if "winner_metadata" in frame:
        winner = winner.fillna(frame["winner_metadata"])
    batting = frame.get("batting_team", pd.Series(index=frame.index, dtype=object))
    bowling = frame.get("bowling_team", pd.Series(index=frame.index, dtype=object))
    winner_key = winner.map(_normalise_team)
    batting_key = batting.map(_normalise_team)
    bowling_key = bowling.map(_normalise_team)
    frame["winner_resolved"] = winner
    frame["team_identity_valid"] = winner_key.notna() & winner_key.ne("") & (
        winner_key.eq(batting_key) | winner_key.eq(bowling_key)
    )
    frame["actual_batting_team_win"] = np.nan
    frame.loc[frame["team_identity_valid"] & winner_key.eq(batting_key), "actual_batting_team_win"] = 1.0
    frame.loc[frame["team_identity_valid"] & winner_key.eq(bowling_key), "actual_batting_team_win"] = 0.0
    feature_json_complete = frame.get(
        "features_json", pd.Series(index=frame.index, dtype=object)
    ).fillna("").astype(str).str.strip().ne("")
    if "features_complete" in frame.columns:
        frame["features_complete"] = (
            frame["features_complete"].fillna(False).astype(bool) & feature_json_complete
        )
    else:
        frame["features_complete"] = feature_json_complete
    return frame


def _probability_columns(frame: pd.DataFrame) -> dict[str, str]:
    def choose(*names: str) -> str | None:
        return next((name for name in names if name in frame.columns), None)
    return {
        "market": choose("market_batting_team_prob", "market_batting_prob"),
        "incumbent": choose("model_final_prob", "incumbent_batting_team_prob"),
        "candidate": choose("candidate_batting_team_prob", "candidate_prob"),
    }


def _window_frame(states: pd.DataFrame, window_start: Any, window_end: Any) -> pd.DataFrame:
    frame = settle_recorded_states(states)
    if frame.empty:
        return frame
    start = _parse_window(window_start)
    end = _parse_window(window_end)
    timestamps = pd.to_datetime(frame.get("timestamp"), utc=True, errors="coerce")
    return frame.loc[timestamps.ge(start) & timestamps.lt(end)].copy()


def _support(frame: pd.DataFrame, column: str | None) -> pd.DataFrame:
    if not column or column not in frame.columns:
        return frame.iloc[0:0].copy()
    mask = frame["actual_batting_team_win"].notna() & _valid_probability(frame[column])
    return frame.loc[mask].copy()


def _score_comparison(frame: pd.DataFrame, columns: Mapping[str, str | None]) -> dict[str, Any]:
    all_columns = [column for column in columns.values() if column]
    common = frame.copy()
    if all_columns:
        mask = common["actual_batting_team_win"].notna()
        for column in all_columns:
            mask &= _valid_probability(common[column])
        common = common.loc[mask]
    else:
        common = common.iloc[0:0]
    metrics = {
        name: {
            "ball_weighted": metric_bundle(common, column, match_equal=False),
            "match_equal": metric_bundle(common, column, match_equal=True),
        }
        for name, column in columns.items()
        if column
    }
    return {"rows": int(len(common)), "matches": int(common["match_id"].nunique()) if not common.empty else 0, "metrics": metrics}


def _differences(metrics: Mapping[str, Any], left: str, right: str) -> dict[str, Any]:
    output: dict[str, Any] = {}
    left_metrics = metrics.get(left, {}).get("match_equal", {})
    right_metrics = metrics.get(right, {}).get("match_equal", {})
    for metric in PROMOTION_MARGINS:
        a = left_metrics.get(metric)
        b = right_metrics.get(metric)
        output[metric] = None if a is None or b is None else float(a - b)
    return output


def _segment_report(frame: pd.DataFrame, columns: Mapping[str, str | None]) -> list[dict[str, Any]]:
    available = [c for c in ("innings", "match_phase", "batting_team_tier") if c in frame.columns]
    rows: list[dict[str, Any]] = []
    for segment_name in available:
        for value, group in frame.groupby(segment_name, dropna=False, sort=True):
            support = _score_comparison(group, columns)
            if support["rows"] < MIN_SEGMENT_ROWS:
                continue
            match_metrics = support["metrics"]
            rows.append({
                "dimension": segment_name,
                "value": "unknown" if pd.isna(value) else str(value),
                "rows": support["rows"],
                "matches": support["matches"],
                "candidate_minus_market": _differences(match_metrics, "candidate", "market"),
                "candidate_minus_incumbent": _differences(match_metrics, "candidate", "incumbent"),
            })
    return rows


def _segment_safety(segments: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    violations = []
    for segment in segments:
        differences = segment.get("candidate_minus_incumbent", {})
        failed = {
            metric: differences.get(metric)
            for metric, tolerance in INCUMBENT_TOLERANCES.items()
            if differences.get(metric) is not None and differences[metric] > tolerance
        }
        if failed:
            violations.append({"dimension": segment.get("dimension"), "value": segment.get("value"), "metrics": failed})
    return violations


def _digest_frame(frame: pd.DataFrame) -> str:
    columns = [
        c for c in [
            "match_id", "timestamp", "innings", "over_number", "ball_in_over",
            "state_key", "batting_team", "bowling_team", "winner_resolved",
            "actual_batting_team_win", "market_batting_team_prob", "model_final_prob",
            "candidate_batting_team_prob", "features_json", "inference_context_json",
        ] if c in frame.columns
    ]
    records = frame[columns].sort_values(columns[: min(6, len(columns))]).to_dict("records") if columns else []
    payload = json.dumps(_json_safe(records), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_promotion_review(
    states: pd.DataFrame,
    *,
    candidate_id: str,
    window_start: Any,
    window_end: Any,
    generated_at: Any = None,
    candidate_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the complete report and return a JSON-serialisable dictionary."""
    start = _parse_window(window_start)
    end = _parse_window(window_end)
    generated = _parse_window(generated_at or datetime.now(timezone.utc))
    frame = _window_frame(states, start, end)
    columns = _probability_columns(frame)
    settled = frame.loc[frame.get("team_identity_valid", False)].copy() if not frame.empty else frame
    candidate_support = _support(frame, columns["candidate"])
    market_support = _support(frame, columns["market"])
    incumbent_support = _support(frame, columns["incumbent"])
    common_candidate_market = _support(frame, columns["candidate"])
    if columns["market"]:
        common_candidate_market = common_candidate_market.loc[_valid_probability(common_candidate_market[columns["market"]])]
    common_candidate_incumbent = _support(frame, columns["candidate"])
    if columns["incumbent"]:
        common_candidate_incumbent = common_candidate_incumbent.loc[_valid_probability(common_candidate_incumbent[columns["incumbent"]])]

    market_coverage = (len(market_support) / len(settled)) if len(settled) else 0.0
    quality_rows = candidate_support if not candidate_support.empty else frame.iloc[0:0]
    feature_completeness = float(quality_rows["features_complete"].mean()) if len(quality_rows) else 0.0
    identity_rate = float(frame["team_identity_valid"].mean()) if len(frame) else 0.0
    segments = _segment_report(frame, {
        "market": columns["market"],
        "incumbent": columns["incumbent"],
        "candidate": columns["candidate"],
    })
    segment_violations = _segment_safety(segments)

    comparison = _score_comparison(common_candidate_market, {
        "market": columns["market"],
        "candidate": columns["candidate"],
    })
    incumbent_comparison = _score_comparison(common_candidate_incumbent, {
        "incumbent": columns["incumbent"],
        "candidate": columns["candidate"],
    })
    metrics = comparison["metrics"]
    incumbent_metrics = incumbent_comparison["metrics"]
    candidate_vs_market = _differences(metrics, "candidate", "market")
    candidate_vs_incumbent = _differences(incumbent_metrics, "candidate", "incumbent")

    match_ids = set(candidate_support["match_id"].astype(str)) if not candidate_support.empty else set()
    completed_match_count = int(len(match_ids))
    elapsed_days = (end - start).total_seconds() / 86400.0
    candidate_available = bool(columns["candidate"] and len(candidate_support))
    manifest = dict(candidate_manifest or {})
    manifest_artifact = manifest.get("model_artifact") or {}
    reproducibility_ready = bool(
        manifest.get("candidate_id")
        and str(manifest.get("candidate_id")) == str(candidate_id)
        and manifest_artifact.get("sha256")
        and manifest.get("feature_order")
        and manifest.get("feature_order_sha256")
        and manifest.get("source_revision") not in {"", "unknown", None}
    )
    market_metrics = metrics.get("market", {}).get("match_equal", {})
    candidate_metrics = metrics.get("candidate", {}).get("match_equal", {})
    incumbent_metric_values = incumbent_metrics.get("incumbent", {}).get("match_equal", {})

    gates = {
        "window_complete": {"passed": elapsed_days >= 7.0, "observed_days": elapsed_days, "required_days": 7.0},
        "completed_matches": {"passed": completed_match_count >= MIN_COMPLETED_MATCHES, "observed": completed_match_count, "required": MIN_COMPLETED_MATCHES},
        "eligible_ball_rows": {"passed": comparison["rows"] >= MIN_ELIGIBLE_ROWS, "observed": comparison["rows"], "required": MIN_ELIGIBLE_ROWS},
        "market_coverage": {"passed": market_coverage >= MIN_MARKET_COVERAGE, "observed": market_coverage, "required": MIN_MARKET_COVERAGE},
        "candidate_beats_market": {"passed": candidate_available and all(
            candidate_metrics.get(metric) is not None and market_metrics.get(metric) is not None
            and candidate_metrics[metric] <= market_metrics[metric] - margin
            for metric, margin in PROMOTION_MARGINS.items()
        ), "margins": PROMOTION_MARGINS, "candidate_minus_market": candidate_vs_market},
        "candidate_not_worse_than_incumbent": {"passed": candidate_available and all(
            candidate_metrics.get(metric) is not None and incumbent_metric_values.get(metric) is not None
            and candidate_metrics[metric] <= incumbent_metric_values[metric] + tolerance
            for metric, tolerance in INCUMBENT_TOLERANCES.items()
        ), "tolerances": INCUMBENT_TOLERANCES, "candidate_minus_incumbent": candidate_vs_incumbent},
        "team_identity": {"passed": identity_rate >= 1.0, "observed": identity_rate, "required": 1.0},
        "feature_completeness": {"passed": feature_completeness >= MIN_FEATURE_COMPLETENESS, "observed": feature_completeness, "required": MIN_FEATURE_COMPLETENESS},
        "segment_safety": {"passed": not segment_violations, "violations": segment_violations},
        "reproducibility": {
            "passed": reproducibility_ready,
            "candidate_manifest_present": bool(manifest),
            "required_fields": [
                "candidate_id",
                "model_artifact.sha256",
                "feature_order_sha256",
                "source_revision",
            ],
        },
    }
    hard_gate_names = ("window_complete", "completed_matches", "eligible_ball_rows", "market_coverage", "candidate_beats_market", "candidate_not_worse_than_incumbent", "team_identity", "feature_completeness", "segment_safety", "reproducibility")
    all_passed = all(gates[name]["passed"] for name in hard_gate_names)
    evidence_ready = all(gates[name]["passed"] for name in ("window_complete", "completed_matches", "eligible_ball_rows", "market_coverage"))
    decision = "promote_candidate" if all_passed else ("retain_incumbent" if evidence_ready else "insufficient_evidence")

    strengths: list[dict[str, Any]] = []
    weaknesses: list[dict[str, Any]] = []
    for segment in segments:
        diffs = segment.get("candidate_minus_market", {})
        improvements = {metric: -value for metric, value in diffs.items() if value is not None}
        if all(improvements.get(metric, 0.0) >= margin for metric, margin in PROMOTION_MARGINS.items()):
            strengths.append(segment)
        if any(value > 0 for value in diffs.values() if value is not None):
            weaknesses.append(segment)

    reasons = []
    if not all_passed:
        reasons.extend(name for name in hard_gate_names if not gates[name]["passed"])
    report = {
        "schema_version": "prediction-promotion-review-v1",
        "candidate_id": candidate_id,
        "window": {"start": start.isoformat(), "end": end.isoformat(), "elapsed_days": elapsed_days},
        "generated_at": generated.isoformat(),
        "decision": decision,
        "decision_reasons": reasons,
        "counts": {
            "state_rows_in_window": int(len(frame)),
            "settled_rows": int(len(settled)),
            "eligible_rows_candidate_market": comparison["rows"],
            "candidate_rows": int(len(candidate_support)),
            "market_rows": int(len(market_support)),
            "incumbent_rows": int(len(incumbent_support)),
            "completed_matches": completed_match_count,
            "market_coverage": market_coverage,
        },
        "quality": {
            "team_identity_rate": identity_rate,
            "candidate_feature_completeness": feature_completeness,
            "candidate_probability_column": columns["candidate"],
            "market_probability_column": columns["market"],
            "incumbent_probability_column": columns["incumbent"],
        },
        "artifacts": {"candidate_manifest": manifest},
        "metrics": {
            "common_candidate_market": comparison["metrics"],
            "common_candidate_incumbent": incumbent_comparison["metrics"],
            "candidate_minus_market_match_equal": candidate_vs_market,
            "candidate_minus_incumbent_match_equal": candidate_vs_incumbent,
        },
        "segments": segments,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "gates": gates,
        "input_digest_sha256": _digest_frame(frame),
    }
    return _json_safe(report)


def write_promotion_review(report: Mapping[str, Any], output_dir: str | Path) -> dict[str, str]:
    """Write JSON, Markdown, and an idempotent append-only manifest entry."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    candidate = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(report.get("candidate_id") or "candidate"))
    end = str(report.get("window", {}).get("end", "unknown"))[:10]
    json_path = target / f"review_{candidate}_{end}.json"
    markdown_path = target / f"review_{candidate}_{end}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gates = report.get("gates", {})
    failed = [name for name, gate in gates.items() if not gate.get("passed")]
    lines = [
        f"# Model promotion review: {report.get('candidate_id')}",
        "",
        f"- Decision: **{report.get('decision')}**",
        f"- Window: `{report.get('window', {}).get('start')}` to `{report.get('window', {}).get('end')}`",
        f"- Completed matches: `{report.get('counts', {}).get('completed_matches', 0)}`",
        f"- Eligible ball rows: `{report.get('counts', {}).get('eligible_rows_candidate_market', 0)}`",
        f"- Input digest: `{report.get('input_digest_sha256')}`",
        "",
        "## Gate status",
        "",
    ]
    for name, gate in gates.items():
        lines.append(f"- {'PASS' if gate.get('passed') else 'FAIL'} — {name}")
    if failed:
        lines.extend(["", "Failed gates: " + ", ".join(failed)])
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest_path = target / "review_manifest.jsonl"
    review_id = f"{report.get('candidate_id')}:{report.get('window', {}).get('start')}:{report.get('window', {}).get('end')}"
    existing_ids: set[str] = set()
    if manifest_path.exists():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            try:
                existing_ids.add(str(json.loads(line).get("review_id")))
            except json.JSONDecodeError:
                continue
    if review_id not in existing_ids:
        entry = {
            "review_id": review_id,
            "candidate_id": report.get("candidate_id"),
            "window": report.get("window"),
            "decision": report.get("decision"),
            "input_digest_sha256": report.get("input_digest_sha256"),
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "generated_at": report.get("generated_at"),
        }
        with manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return {"json": str(json_path), "markdown": str(markdown_path), "manifest": str(manifest_path)}
