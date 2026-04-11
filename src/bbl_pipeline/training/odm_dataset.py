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

HISTORICAL_SCORE_FEATURES = [
    'venue_avg_innings_score',
    'batting_team_avg_innings_score',
    'batting_team_venue_avg_innings_score',
    'batting_team_high_innings_score',
    'batting_team_venue_high_innings_score',
    'venue_avg_run_rate',
    'batting_team_avg_run_rate',
    'batting_team_venue_avg_run_rate',
    'batting_team_high_run_rate',
    'batting_team_venue_high_run_rate',
    'projected_vs_team_avg_score',
    'projected_vs_team_venue_avg_score',
    'projected_vs_team_high_score',
    'projected_vs_team_venue_high_score',
    'crr_minus_venue_avg_rr',
    'crr_minus_team_avg_rr',
    'crr_minus_team_venue_avg_rr',
    'target_score',
    'target_implied_run_rate',
    'crr_minus_target_rr',
    'target_minus_venue_avg_score',
    'target_minus_team_avg_score',
    'target_minus_team_venue_avg_score',
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


def _shifted_expanding_mean(series: pd.Series) -> pd.Series:
    return series.shift(1).expanding().mean()


def _shifted_cummax(series: pd.Series) -> pd.Series:
    return series.shift(1).cummax()


def add_historical_scoring_features(df: pd.DataFrame, total_overs: int = 20) -> pd.DataFrame:
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])

    innings_summary = (
        df.groupby(['league', 'match_id', 'innings'], as_index=False)
        .agg(
            date=('date', 'first'),
            venue_id=('venue_id', 'first'),
            batting_team_id=('batting_team_id', 'first'),
            innings_total=('runs_total', 'sum'),
        )
        .sort_values(['league', 'date', 'match_id', 'innings'])
        .reset_index(drop=True)
    )

    innings_summary['venue_avg_innings_score'] = (
        innings_summary.groupby(['league', 'venue_id', 'innings'])['innings_total']
        .transform(_shifted_expanding_mean)
    )
    innings_summary['batting_team_avg_innings_score'] = (
        innings_summary.groupby(['league', 'batting_team_id', 'innings'])['innings_total']
        .transform(_shifted_expanding_mean)
    )
    innings_summary['batting_team_venue_avg_innings_score'] = (
        innings_summary.groupby(['league', 'batting_team_id', 'venue_id', 'innings'])['innings_total']
        .transform(_shifted_expanding_mean)
    )
    innings_summary['batting_team_high_innings_score'] = (
        innings_summary.groupby(['league', 'batting_team_id', 'innings'])['innings_total']
        .transform(_shifted_cummax)
    )
    innings_summary['batting_team_venue_high_innings_score'] = (
        innings_summary.groupby(['league', 'batting_team_id', 'venue_id', 'innings'])['innings_total']
        .transform(_shifted_cummax)
    )

    innings_summary['venue_avg_run_rate'] = innings_summary['venue_avg_innings_score'] / total_overs
    innings_summary['batting_team_avg_run_rate'] = innings_summary['batting_team_avg_innings_score'] / total_overs
    innings_summary['batting_team_venue_avg_run_rate'] = (
        innings_summary['batting_team_venue_avg_innings_score'] / total_overs
    )
    innings_summary['batting_team_high_run_rate'] = innings_summary['batting_team_high_innings_score'] / total_overs
    innings_summary['batting_team_venue_high_run_rate'] = (
        innings_summary['batting_team_venue_high_innings_score'] / total_overs
    )

    global_avg_by_innings = innings_summary.groupby('innings')['innings_total'].mean().to_dict()
    global_rr_by_innings = {innings: score / total_overs for innings, score in global_avg_by_innings.items()}
    global_max_by_innings = innings_summary.groupby('innings')['innings_total'].max().to_dict()

    for column in [
        'venue_avg_innings_score',
        'batting_team_avg_innings_score',
        'batting_team_venue_avg_innings_score',
    ]:
        innings_summary[column] = innings_summary[column].fillna(innings_summary['innings'].map(global_avg_by_innings))

    for column in ['batting_team_high_innings_score', 'batting_team_venue_high_innings_score']:
        innings_summary[column] = innings_summary[column].fillna(innings_summary['innings'].map(global_max_by_innings))

    for column in [
        'venue_avg_run_rate',
        'batting_team_avg_run_rate',
        'batting_team_venue_avg_run_rate',
    ]:
        innings_summary[column] = innings_summary[column].fillna(innings_summary['innings'].map(global_rr_by_innings))

    for column in ['batting_team_high_run_rate', 'batting_team_venue_high_run_rate']:
        innings_summary[column] = innings_summary[column].fillna(
            innings_summary['innings'].map({innings: value / total_overs for innings, value in global_max_by_innings.items()})
        )

    match_targets = (
        innings_summary[innings_summary['innings'] == 1][['league', 'match_id', 'innings_total']]
        .rename(columns={'innings_total': 'first_innings_total'})
    )
    match_targets['target_score'] = match_targets['first_innings_total'] + 1

    df = df.merge(
        innings_summary[
            ['league', 'match_id', 'innings'] + HISTORICAL_SCORE_FEATURES[:10]
        ],
        on=['league', 'match_id', 'innings'],
        how='left',
    )
    df = df.merge(match_targets[['league', 'match_id', 'target_score']], on=['league', 'match_id'], how='left')

    df['target_score'] = np.where(df['innings'] == 2, df['target_score'], np.nan)
    df['target_implied_run_rate'] = df['target_score'] / total_overs

    df['projected_vs_team_avg_score'] = np.where(
        df['innings'] == 1,
        df['projected_score'] - df['batting_team_avg_innings_score'],
        0.0,
    )
    df['projected_vs_team_venue_avg_score'] = np.where(
        df['innings'] == 1,
        df['projected_score'] - df['batting_team_venue_avg_innings_score'],
        0.0,
    )
    df['projected_vs_team_high_score'] = np.where(
        df['innings'] == 1,
        df['projected_score'] - df['batting_team_high_innings_score'],
        0.0,
    )
    df['projected_vs_team_venue_high_score'] = np.where(
        df['innings'] == 1,
        df['projected_score'] - df['batting_team_venue_high_innings_score'],
        0.0,
    )

    df['crr_minus_venue_avg_rr'] = df['current_run_rate'] - df['venue_avg_run_rate']
    df['crr_minus_team_avg_rr'] = df['current_run_rate'] - df['batting_team_avg_run_rate']
    df['crr_minus_team_venue_avg_rr'] = df['current_run_rate'] - df['batting_team_venue_avg_run_rate']
    df['crr_minus_target_rr'] = np.where(
        df['innings'] == 2,
        df['current_run_rate'] - df['target_implied_run_rate'],
        0.0,
    )
    df['target_minus_venue_avg_score'] = np.where(
        df['innings'] == 2,
        df['target_score'] - df['venue_avg_innings_score'],
        0.0,
    )
    df['target_minus_team_avg_score'] = np.where(
        df['innings'] == 2,
        df['target_score'] - df['batting_team_avg_innings_score'],
        0.0,
    )
    df['target_minus_team_venue_avg_score'] = np.where(
        df['innings'] == 2,
        df['target_score'] - df['batting_team_venue_avg_innings_score'],
        0.0,
    )
    return df


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
    dataset = add_historical_scoring_features(dataset)
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
