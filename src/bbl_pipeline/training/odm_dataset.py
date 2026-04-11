from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
import structlog

from bbl_pipeline.training.trainer import XGBLogRegEnsemble
from bbl_pipeline.training.odm_evaluation import build_baseline_report

logger = structlog.get_logger()

KEY_COLUMNS = ['league', 'match_id', 'innings', 'over', 'ball']
TARGET_COLUMNS = [
    'ml_delta_12',
    'momentum_baseline_12',
    'residual_delta_12',
    'ml_prob_delta_6',
    'ml_prob_delta_12',
    'ml_rwp_gap',
    'ml_rwp_gap_delta_6',
]


def _feature_path(features_root: Path, league: str) -> Path:
    return features_root / f'{league}_features_v1' / 'training.parquet'


def _base_path(base_dir: Path, league: str) -> Path:
    return base_dir / f'{league}_odm_base.parquet'


def _expected_overs_remaining(base_df: pd.DataFrame, total_overs: int = 20) -> pd.Series:
    return total_overs - (base_df['over'] + (base_df['ball'] / 6.0))


def _align_base_and_features(base_df: pd.DataFrame, feature_df: pd.DataFrame, league: str) -> pd.DataFrame:
    base_df = base_df.sort_values(KEY_COLUMNS).reset_index(drop=True)
    feature_df = feature_df.reset_index(drop=True)

    if len(base_df) != len(feature_df):
        raise ValueError(
            f'{league}: base row count {len(base_df)} does not match feature row count {len(feature_df)}'
        )

    expected_overs = _expected_overs_remaining(base_df)
    overs_diff = (expected_overs - feature_df['overs_remaining']).abs()
    mismatch_rate = float((overs_diff > 1e-6).mean())
    if mismatch_rate > 0.001:
        raise ValueError(
            f'{league}: overs_remaining alignment check failed with mismatch rate {mismatch_rate:.4%}'
        )

    if 'innings' in feature_df.columns and not base_df['innings'].equals(feature_df['innings']):
        raise ValueError(f'{league}: innings alignment check failed between base and feature exports')

    feature_df = feature_df.drop(columns=[col for col in ['innings'] if col in feature_df.columns])
    merged = pd.concat([base_df, feature_df], axis=1)
    merged['league'] = league
    merged['ball_number'] = merged['over'] * 6 + merged['ball']
    return merged


def generate_ml_probabilities(df: pd.DataFrame, model_path: Path) -> Tuple[pd.Series, List[str]]:
    model = joblib.load(model_path)
    feature_columns = list(getattr(model, 'selected_features_', None) or XGBLogRegEnsemble.TOP_FEATURES)
    missing = [column for column in feature_columns if column not in df.columns]
    if missing:
        raise ValueError(f'Missing ML model feature columns: {missing}')

    probabilities = model.predict_proba(df[feature_columns])[:, 1]
    return pd.Series(probabilities, index=df.index, name='ml_prob'), feature_columns


def add_odm_targets_and_features(df: pd.DataFrame, horizon_balls: int = 12) -> pd.DataFrame:
    df = df.sort_values(KEY_COLUMNS).reset_index(drop=True).copy()
    group_cols = ['league', 'match_id', 'innings']
    grouped = df.groupby(group_cols, sort=False)

    df['phase'] = np.where(
        df['is_powerplay'] == 1,
        'powerplay',
        np.where(df['is_death_overs'] == 1, 'death', 'middle'),
    )

    df['ml_prob_future'] = grouped['ml_prob'].shift(-horizon_balls)
    df['ml_delta_12'] = df['ml_prob_future'] - df['ml_prob']

    df['ml_prob_past_12'] = grouped['ml_prob'].shift(horizon_balls)
    df['momentum_baseline_12'] = df['ml_prob'] - df['ml_prob_past_12']
    df['residual_delta_12'] = df['ml_delta_12'] - df['momentum_baseline_12']

    df['direction'] = (df['ml_delta_12'] > 0).astype(int)
    df['momentum_direction'] = (df['momentum_baseline_12'] > 0).astype(int)
    df['residual_direction'] = (df['residual_delta_12'] > 0).astype(int)

    df['ml_prob_delta_6'] = df['ml_prob'] - grouped['ml_prob'].shift(6)
    df['ml_prob_delta_12'] = df['ml_prob'] - grouped['ml_prob'].shift(12)
    df['ml_rwp_gap'] = df['ml_prob'] - df['resource_win_prob']
    df['ml_rwp_gap_delta_6'] = df['ml_rwp_gap'] - grouped['ml_rwp_gap'].shift(6)

    required = ['ml_delta_12', 'momentum_baseline_12'] + TARGET_COLUMNS[3:]
    trimmed = df.dropna(subset=required).reset_index(drop=True)
    return trimmed


def build_odm_training_dataset(
    leagues: List[str],
    base_dir: Path,
    features_root: Path,
    model_path: Path,
    horizon_balls: int = 12,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    frames: List[pd.DataFrame] = []

    for league in leagues:
        base_path = _base_path(base_dir, league)
        feature_path = _feature_path(features_root, league)
        if not base_path.exists():
            raise FileNotFoundError(f'ODM base export missing for {league}: {base_path}')
        if not feature_path.exists():
            raise FileNotFoundError(f'Feature parquet missing for {league}: {feature_path}')

        logger.info('Loading ODM inputs', league=league, base_path=str(base_path), feature_path=str(feature_path))
        base_df = pd.read_parquet(base_path)
        feature_df = pd.read_parquet(feature_path)
        frames.append(_align_base_and_features(base_df, feature_df, league))

    dataset = pd.concat(frames, ignore_index=True)
    dataset['ml_prob'], model_features = generate_ml_probabilities(dataset, model_path)
    dataset = add_odm_targets_and_features(dataset, horizon_balls=horizon_balls)

    baseline_report = build_baseline_report(dataset)
    baseline_report['metadata'] = {
        'horizon_balls': horizon_balls,
        'model_path': str(model_path),
        'model_feature_count': len(model_features),
        'leagues': leagues,
        'rows': int(len(dataset)),
        'matches': int(dataset['match_id'].nunique()),
    }
    return dataset, baseline_report
