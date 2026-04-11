from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, mean_absolute_error, mean_squared_error, roc_auc_score
from xgboost import XGBClassifier, XGBRegressor

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
LEAKAGE_COLUMNS = ['is_winner', 'match_id']


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
    feature_df = feature_df.drop(columns=['date'] + LEAKAGE_COLUMNS, errors='ignore')
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


def _direction_metrics(y_true: pd.Series, y_pred: np.ndarray, y_score: np.ndarray) -> Dict[str, Any]:
    return {
        'rows': int(len(y_true)),
        'accuracy': float(accuracy_score(y_true, y_pred)),
        'balanced_accuracy': float(balanced_accuracy_score(y_true, y_pred)),
        'macro_f1': float(f1_score(y_true, y_pred, average='macro')),
        'roc_auc': float(roc_auc_score(y_true, y_score)),
        'up_rate_actual': float(np.mean(y_true)),
        'up_rate_pred': float(np.mean(y_pred)),
    }


def _delta_metrics(y_true: pd.Series, y_pred: np.ndarray) -> Dict[str, Any]:
    return {
        'rows': int(len(y_true)),
        'mae': float(mean_absolute_error(y_true, y_pred)),
        'rmse': float(np.sqrt(mean_squared_error(y_true, y_pred))),
        'actual_delta_mean': float(np.mean(y_true)),
        'pred_delta_mean': float(np.mean(y_pred)),
        'sign_accuracy': float(accuracy_score((y_true > 0).astype(int), (y_pred > 0).astype(int))),
    }


def _direction_slice_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    rows = []
    for league, league_df in df.groupby('league'):
        rows.append({'league': league, **_direction_metrics(league_df['direction'], league_df['pred_direction'], league_df['pred_up_prob'])})
    return {
        'overall': _direction_metrics(df['direction'], df['pred_direction'], df['pred_up_prob']),
        'by_league': rows,
    }


def _delta_slice_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    rows = []
    for league, league_df in df.groupby('league'):
        rows.append({'league': league, **_delta_metrics(league_df['ml_delta_12'], league_df['pred_delta'])})
    return {
        'overall': _delta_metrics(df['ml_delta_12'], df['pred_delta']),
        'by_league': rows,
    }


def _baseline_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    majority_class = int(df['direction'].mean() >= 0.5)
    naive_direction = np.full(len(df), majority_class)
    momentum_direction = df['momentum_direction'].to_numpy()
    momentum_score = df['ml_prob_delta_12'].to_numpy()
    zero_delta_pred = np.zeros(len(df))
    momentum_delta_pred = df['momentum_baseline_12'].to_numpy()

    return {
        'naive_direction': {
            'rows': int(len(df)),
            'accuracy': float(accuracy_score(df['direction'], naive_direction)),
            'balanced_accuracy': float(balanced_accuracy_score(df['direction'], naive_direction)),
            'macro_f1': float(f1_score(df['direction'], naive_direction, average='macro')),
            'up_rate_pred': float(np.mean(naive_direction)),
        },
        'momentum_direction': {
            'rows': int(len(df)),
            'accuracy': float(accuracy_score(df['direction'], momentum_direction)),
            'balanced_accuracy': float(balanced_accuracy_score(df['direction'], momentum_direction)),
            'macro_f1': float(f1_score(df['direction'], momentum_direction, average='macro')),
            'roc_auc_like': float(roc_auc_score(df['direction'], momentum_score)),
            'up_rate_pred': float(np.mean(momentum_direction)),
        },
        'zero_delta': {
            'rows': int(len(df)),
            'mae': float(mean_absolute_error(df['ml_delta_12'], zero_delta_pred)),
            'rmse': float(np.sqrt(mean_squared_error(df['ml_delta_12'], zero_delta_pred))),
        },
        'momentum_delta': {
            'rows': int(len(df)),
            'mae': float(mean_absolute_error(df['ml_delta_12'], momentum_delta_pred)),
            'rmse': float(np.sqrt(mean_squared_error(df['ml_delta_12'], momentum_delta_pred))),
            'sign_accuracy': float(accuracy_score(df['direction'], momentum_direction)),
        },
    }


def _save_importance(output_dir: Path, filename: str, feature_columns: List[str], importances: np.ndarray) -> None:
    importance = pd.DataFrame({'feature': feature_columns, 'importance': importances}).sort_values('importance', ascending=False)
    importance.to_csv(output_dir / filename, index=False)


def save_odm_artifacts(
    output_dir: Path,
    models: Dict[str, Any],
    feature_columns: List[str],
    metrics: Dict[str, Any],
    baseline_metrics: Dict[str, Any],
    training_manifest: Dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(models, output_dir / 'champion_model.joblib')
    joblib.dump(models['direction_model'], output_dir / 'direction_model.joblib')
    joblib.dump(models['delta_model'], output_dir / 'delta_model.joblib')
    with open(output_dir / 'feature_columns.json', 'w', encoding='utf-8') as handle:
        json.dump(feature_columns, handle, indent=2)
    with open(output_dir / 'metrics.json', 'w', encoding='utf-8') as handle:
        json.dump(_json_ready(metrics), handle, indent=2)
    with open(output_dir / 'baseline_metrics.json', 'w', encoding='utf-8') as handle:
        json.dump(_json_ready(baseline_metrics), handle, indent=2)
    with open(output_dir / 'training_manifest.json', 'w', encoding='utf-8') as handle:
        json.dump(_json_ready(training_manifest), handle, indent=2)
    _save_importance(output_dir, 'direction_feature_importance.csv', feature_columns, models['direction_model'].feature_importances_)
    _save_importance(output_dir, 'delta_feature_importance.csv', feature_columns, models['delta_model'].feature_importances_)


def _build_prediction_frames(holdout_df: pd.DataFrame, direction_prob: np.ndarray, delta_pred: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
    direction_frame = holdout_df.copy()
    direction_frame['pred_up_prob'] = direction_prob
    direction_frame['pred_direction'] = (direction_prob >= 0.5).astype(int)

    delta_frame = holdout_df.copy()
    delta_frame['pred_delta'] = delta_pred
    delta_frame['pred_direction'] = (delta_pred > 0).astype(int)
    return direction_frame, delta_frame


def _build_comparison(metrics: Dict[str, Any], baseline_metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'direction_lift_vs_momentum_accuracy': (
            metrics['direction_model']['overall']['accuracy'] - baseline_metrics['momentum_direction']['accuracy']
        ),
        'direction_lift_vs_naive_accuracy': (
            metrics['direction_model']['overall']['accuracy'] - baseline_metrics['naive_direction']['accuracy']
        ),
        'delta_mae_improvement_vs_momentum': (
            baseline_metrics['momentum_delta']['mae'] - metrics['delta_model']['overall']['mae']
        ),
        'delta_mae_improvement_vs_zero': (
            baseline_metrics['zero_delta']['mae'] - metrics['delta_model']['overall']['mae']
        ),
        'delta_sign_lift_vs_momentum': (
            metrics['delta_model']['overall']['sign_accuracy'] - baseline_metrics['momentum_delta']['sign_accuracy']
        ),
    }


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

    direction_model = XGBClassifier(
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
    delta_model = XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        reg_lambda=1.0,
        objective='reg:squarederror',
        eval_metric='rmse',
        random_state=random_state,
    )

    direction_model.fit(X_train, train_df['direction'])
    delta_model.fit(X_train, train_df['ml_delta_12'])

    direction_prob = direction_model.predict_proba(X_holdout)[:, 1]
    delta_pred = delta_model.predict(X_holdout)
    direction_frame, delta_frame = _build_prediction_frames(holdout_df, direction_prob, delta_pred)

    metrics = {
        'direction_model': _direction_slice_metrics(direction_frame),
        'delta_model': _delta_slice_metrics(delta_frame),
    }
    baseline_metrics = _baseline_metrics(holdout_df)
    metrics['comparison'] = _build_comparison(metrics, baseline_metrics)

    training_manifest = {
        'input_file': str(input_file),
        'holdout_frac': holdout_frac,
        'random_state': random_state,
        'train_rows': int(len(train_df)),
        'holdout_rows': int(len(holdout_df)),
        'train_matches': int(train_df['match_id'].nunique()),
        'holdout_matches': int(holdout_df['match_id'].nunique()),
        'feature_count': len(feature_columns),
        'model_types': {
            'direction_model': 'xgboost_classifier_on_direction',
            'delta_model': 'xgboost_regressor_on_ml_delta_12',
        },
    }

    save_odm_artifacts(
        output_dir,
        {'direction_model': direction_model, 'delta_model': delta_model},
        feature_columns,
        metrics,
        baseline_metrics,
        training_manifest,
    )
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

    models = joblib.load(model_dir / 'champion_model.joblib')
    with open(model_dir / 'feature_columns.json', 'r', encoding='utf-8') as handle:
        feature_columns = json.load(handle)

    X_all, _ = _prepare_features(df)
    missing = [column for column in feature_columns if column not in X_all.columns]
    for column in missing:
        X_all[column] = 0.0
    X_holdout = X_all.loc[holdout_df.index, feature_columns]

    direction_prob = models['direction_model'].predict_proba(X_holdout)[:, 1]
    delta_pred = models['delta_model'].predict(X_holdout)
    direction_frame, delta_frame = _build_prediction_frames(holdout_df, direction_prob, delta_pred)

    metrics = {
        'direction_model': _direction_slice_metrics(direction_frame),
        'delta_model': _delta_slice_metrics(delta_frame),
    }
    baseline_metrics = _baseline_metrics(holdout_df)
    metrics['comparison'] = _build_comparison(metrics, baseline_metrics)
    return {
        'metrics': metrics,
        'baseline_metrics': baseline_metrics,
    }
