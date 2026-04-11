from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score
from xgboost import XGBClassifier


ID_COLUMNS = ['league', 'match_id', 'date', 'phase']
TARGET_COLUMNS = [
    'direction',
    'momentum_direction',
    'residual_direction',
    'ml_delta_12',
    'momentum_baseline_12',
    'residual_delta_12',
    'ml_prob_future',
    'ml_prob_past_12',
]


def _json_ready(value: Any) -> Any:
    if hasattr(value, 'item'):
        return value.item()
    if isinstance(value, dict):
        return {key: _json_ready(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    feature_df = df.drop(columns=[col for col in TARGET_COLUMNS if col in df.columns], errors='ignore').copy()
    feature_df = feature_df.drop(columns=['date'], errors='ignore')
    feature_df = pd.get_dummies(feature_df, columns=[col for col in ['league', 'phase'] if col in feature_df.columns], dtype=float)

    bool_cols = feature_df.select_dtypes(include=['bool']).columns.tolist()
    for column in bool_cols:
        feature_df[column] = feature_df[column].astype(float)

    non_numeric = feature_df.select_dtypes(exclude=[np.number]).columns.tolist()
    if non_numeric:
        feature_df = feature_df.drop(columns=non_numeric)

    return feature_df, feature_df.columns.tolist()


def _build_holdout_mask(df: pd.DataFrame, holdout_frac: float) -> pd.Series:
    match_meta = (
        df.groupby(['league', 'match_id'], as_index=False)
        .agg(match_date=('date', 'min'))
        .sort_values(['league', 'match_date', 'match_id'])
    )

    holdout_keys = []
    for league, league_matches in match_meta.groupby('league', sort=False):
        n_holdout = max(1, int(np.ceil(len(league_matches) * holdout_frac)))
        holdout_keys.extend(list(zip([league] * n_holdout, league_matches.tail(n_holdout)['match_id'])))

    holdout_key_set = set(holdout_keys)
    return df.apply(lambda row: (row['league'], row['match_id']) in holdout_key_set, axis=1)


def _binary_metrics(y_true: pd.Series, y_pred: np.ndarray, y_prob: np.ndarray) -> Dict[str, Any]:
    return {
        'rows': int(len(y_true)),
        'accuracy': float(accuracy_score(y_true, y_pred)),
        'balanced_accuracy': float(balanced_accuracy_score(y_true, y_pred)),
        'macro_f1': float(f1_score(y_true, y_pred, average='macro')),
        'roc_auc': float(roc_auc_score(y_true, y_prob)),
        'up_rate_actual': float(np.mean(y_true)),
        'up_rate_pred': float(np.mean(y_pred)),
    }


def _slice_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    rows = []
    for league, league_df in df.groupby('league'):
        rows.append({'league': league, **_binary_metrics(league_df['direction'], league_df['pred_direction'], league_df['pred_up_prob'])})
    return {
        'overall': _binary_metrics(df['direction'], df['pred_direction'], df['pred_up_prob']),
        'by_league': rows,
    }


def _baseline_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    majority_class = int(df['direction'].mean() >= 0.5)
    naive_pred = np.full(len(df), majority_class)
    momentum_pred = df['momentum_direction'].to_numpy()
    momentum_prob = df['ml_prob_delta_12'].to_numpy()

    momentum_auc = float(roc_auc_score(df['direction'], momentum_prob))
    naive = {
        'rows': int(len(df)),
        'accuracy': float(accuracy_score(df['direction'], naive_pred)),
        'balanced_accuracy': float(balanced_accuracy_score(df['direction'], naive_pred)),
        'macro_f1': float(f1_score(df['direction'], naive_pred, average='macro')),
        'up_rate_pred': float(np.mean(naive_pred)),
    }
    momentum = {
        'rows': int(len(df)),
        'accuracy': float(accuracy_score(df['direction'], momentum_pred)),
        'balanced_accuracy': float(balanced_accuracy_score(df['direction'], momentum_pred)),
        'macro_f1': float(f1_score(df['direction'], momentum_pred, average='macro')),
        'roc_auc_like': momentum_auc,
        'up_rate_pred': float(np.mean(momentum_pred)),
    }
    return {'naive': naive, 'momentum': momentum}


def save_odm_artifacts(
    output_dir: Path,
    model: XGBClassifier,
    feature_columns: List[str],
    metrics: Dict[str, Any],
    baseline_metrics: Dict[str, Any],
    training_manifest: Dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_dir / 'champion_model.joblib')
    with open(output_dir / 'feature_columns.json', 'w', encoding='utf-8') as handle:
        json.dump(feature_columns, handle, indent=2)
    with open(output_dir / 'metrics.json', 'w', encoding='utf-8') as handle:
        json.dump(_json_ready(metrics), handle, indent=2)
    with open(output_dir / 'baseline_metrics.json', 'w', encoding='utf-8') as handle:
        json.dump(_json_ready(baseline_metrics), handle, indent=2)
    with open(output_dir / 'training_manifest.json', 'w', encoding='utf-8') as handle:
        json.dump(_json_ready(training_manifest), handle, indent=2)


def train_odm(
    input_file: Path,
    output_dir: Path,
    holdout_frac: float = 0.2,
    random_state: int = 42,
) -> Dict[str, Any]:
    df = pd.read_parquet(input_file).copy()
    df['date'] = pd.to_datetime(df['date'])

    holdout_mask = _build_holdout_mask(df, holdout_frac=holdout_frac)
    train_df = df.loc[~holdout_mask].copy()
    holdout_df = df.loc[holdout_mask].copy()
    if train_df.empty or holdout_df.empty:
        raise ValueError('ODM split failed: empty train or holdout set')

    X_all, feature_columns = _prepare_features(df)
    X_train = X_all.loc[train_df.index]
    X_holdout = X_all.loc[holdout_df.index]
    y_train = train_df['direction']
    y_holdout = holdout_df['direction']

    model = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        reg_lambda=1.0,
        objective='binary:logistic',
        eval_metric='logloss',
        random_state=random_state,
    )
    model.fit(X_train, y_train)

    holdout_prob = model.predict_proba(X_holdout)[:, 1]
    holdout_pred = (holdout_prob >= 0.5).astype(int)

    prediction_frame = holdout_df.copy()
    prediction_frame['pred_up_prob'] = holdout_prob
    prediction_frame['pred_direction'] = holdout_pred

    metrics = _slice_metrics(prediction_frame)
    baseline_metrics = _baseline_metrics(holdout_df)
    metrics['lift_vs_momentum_accuracy'] = (
        metrics['overall']['accuracy'] - baseline_metrics['momentum']['accuracy']
    )
    metrics['lift_vs_naive_accuracy'] = (
        metrics['overall']['accuracy'] - baseline_metrics['naive']['accuracy']
    )

    training_manifest = {
        'input_file': str(input_file),
        'holdout_frac': holdout_frac,
        'random_state': random_state,
        'train_rows': int(len(train_df)),
        'holdout_rows': int(len(holdout_df)),
        'train_matches': int(train_df['match_id'].nunique()),
        'holdout_matches': int(holdout_df['match_id'].nunique()),
        'feature_count': len(feature_columns),
    }

    save_odm_artifacts(output_dir, model, feature_columns, metrics, baseline_metrics, training_manifest)
    return {
        'metrics': metrics,
        'baseline_metrics': baseline_metrics,
        'training_manifest': training_manifest,
    }


def evaluate_odm(input_file: Path, model_dir: Path, holdout_frac: float = 0.2) -> Dict[str, Any]:
    df = pd.read_parquet(input_file).copy()
    df['date'] = pd.to_datetime(df['date'])
    holdout_mask = _build_holdout_mask(df, holdout_frac=holdout_frac)
    holdout_df = df.loc[holdout_mask].copy()

    model = joblib.load(model_dir / 'champion_model.joblib')
    with open(model_dir / 'feature_columns.json', 'r', encoding='utf-8') as handle:
        feature_columns = json.load(handle)

    X_all, _ = _prepare_features(df)
    missing = [column for column in feature_columns if column not in X_all.columns]
    for column in missing:
        X_all[column] = 0.0
    X_holdout = X_all.loc[holdout_df.index, feature_columns]

    holdout_prob = model.predict_proba(X_holdout)[:, 1]
    holdout_pred = (holdout_prob >= 0.5).astype(int)
    prediction_frame = holdout_df.copy()
    prediction_frame['pred_up_prob'] = holdout_prob
    prediction_frame['pred_direction'] = holdout_pred

    metrics = _slice_metrics(prediction_frame)
    baseline_metrics = _baseline_metrics(holdout_df)
    metrics['lift_vs_momentum_accuracy'] = (
        metrics['overall']['accuracy'] - baseline_metrics['momentum']['accuracy']
    )
    metrics['lift_vs_naive_accuracy'] = (
        metrics['overall']['accuracy'] - baseline_metrics['naive']['accuracy']
    )
    return {
        'metrics': metrics,
        'baseline_metrics': baseline_metrics,
    }
