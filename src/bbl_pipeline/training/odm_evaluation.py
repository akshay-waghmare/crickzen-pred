from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd


def _json_ready(value: Any) -> Any:
    if hasattr(value, 'item'):
        return value.item()
    if isinstance(value, dict):
        return {key: _json_ready(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _slice_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    zero_delta_mae = float(df['ml_delta_12'].abs().mean())
    momentum_mae = float((df['ml_delta_12'] - df['momentum_baseline_12']).abs().mean())
    momentum_direction_accuracy = float((df['direction'] == df['momentum_direction']).mean())
    return {
        'rows': int(len(df)),
        'matches': int(df['match_id'].nunique()),
        'zero_delta_mae': zero_delta_mae,
        'momentum_mae': momentum_mae,
        'momentum_direction_accuracy': momentum_direction_accuracy,
        'up_rate': float(df['direction'].mean()),
    }


def _build_slice_report(df: pd.DataFrame, group_cols: Iterable[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for keys, group in df.groupby(list(group_cols), dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        record = {column: value for column, value in zip(group_cols, keys)}
        record.update(_slice_metrics(group))
        rows.append(record)
    return rows


def build_baseline_report(df: pd.DataFrame) -> Dict[str, Any]:
    return {
        'overall': _slice_metrics(df),
        'by_league': _build_slice_report(df, ['league']),
        'by_innings': _build_slice_report(df, ['innings']),
        'by_phase': _build_slice_report(df, ['phase']),
        'by_league_innings_phase': _build_slice_report(df, ['league', 'innings', 'phase']),
    }


def write_baseline_report(report: Dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)

    with open(report_dir / 'baseline_report.json', 'w', encoding='utf-8') as handle:
        json.dump(_json_ready(report), handle, indent=2)

    for key in ['by_league', 'by_innings', 'by_phase', 'by_league_innings_phase']:
        pd.DataFrame(report[key]).to_csv(report_dir / f'{key}.csv', index=False)
