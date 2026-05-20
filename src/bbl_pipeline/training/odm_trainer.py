from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, mean_absolute_error, mean_squared_error, roc_auc_score
from xgboost import XGBClassifier, XGBRegressor

from bbl_pipeline.inference.odm_delta_point import (
    DELTA_POINT_MODE_DIRECTION_SIGNED,
    DELTA_POINT_MODE_DIRECTION_WEIGHTED,
    DELTA_POINT_MODE_MODEL,
    apply_delta_point_mode,
)

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
        'tail_abs_delta_mae': float(_tail_abs_delta_mae(y_true, y_pred)),
    }


def _tail_abs_delta_mae(y_true: pd.Series, y_pred: np.ndarray, quantile: float = 0.9) -> float:
    truth = np.asarray(y_true, dtype=float)
    prediction = np.asarray(y_pred, dtype=float)
    threshold = np.quantile(np.abs(truth), quantile)
    mask = np.abs(truth) >= threshold
    if not np.any(mask):
        return mean_absolute_error(truth, prediction)
    return mean_absolute_error(truth[mask], prediction[mask])


def _interval_metrics(y_true: pd.Series, lower: np.ndarray, upper: np.ndarray) -> Dict[str, Any]:
    ordered_lower = np.minimum(lower, upper)
    ordered_upper = np.maximum(lower, upper)
    coverage = ((y_true >= ordered_lower) & (y_true <= ordered_upper)).mean()
    width = np.mean(ordered_upper - ordered_lower)
    return {
        'rows': int(len(y_true)),
        'coverage_90': float(coverage),
        'avg_width': float(width),
        'lower_mean': float(np.mean(ordered_lower)),
        'upper_mean': float(np.mean(ordered_upper)),
    }


def _conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    if len(scores) == 0:
        return 0.0
    sorted_scores = np.sort(np.asarray(scores, dtype=float))
    rank = int(np.ceil((len(sorted_scores) + 1) * (1.0 - alpha))) - 1
    rank = min(max(rank, 0), len(sorted_scores) - 1)
    return float(sorted_scores[rank])


def _phase_conditioned_conformal_adjustments(
    calibration_df: pd.DataFrame,
    lower: np.ndarray,
    upper: np.ndarray,
    alpha: float,
) -> Dict[str, float]:
    ordered_lower = np.minimum(lower, upper)
    ordered_upper = np.maximum(lower, upper)
    truth = calibration_df['ml_delta_12'].to_numpy()
    scores = np.maximum(
        np.maximum(ordered_lower - truth, truth - ordered_upper),
        0.0,
    )

    adjustments = {'overall': _conformal_quantile(scores, alpha)}
    if 'phase' not in calibration_df.columns:
        return adjustments

    phase_series = calibration_df['phase'].fillna('unknown').astype(str)
    for phase_name in sorted(phase_series.unique()):
        mask = phase_series == phase_name
        if int(mask.sum()) < 100:
            continue
        adjustments[phase_name] = _conformal_quantile(scores[mask.to_numpy()], alpha)

    return adjustments


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


def _interval_slice_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    rows = []
    for league, league_df in df.groupby('league'):
        rows.append({'league': league, **_interval_metrics(league_df['ml_delta_12'], league_df['pred_delta_lower'], league_df['pred_delta_upper'])})
    return {
        'overall': _interval_metrics(df['ml_delta_12'], df['pred_delta_lower'], df['pred_delta_upper']),
        'by_league': rows,
    }


def _apply_phase_adjustments(df: pd.DataFrame, lower: np.ndarray, upper: np.ndarray, adjustments: Dict[str, float]) -> Tuple[np.ndarray, np.ndarray]:
    ordered_lower = np.minimum(lower, upper).astype(float)
    ordered_upper = np.maximum(lower, upper).astype(float)
    default_adjustment = float(adjustments.get('overall', 0.0))
    widened_lower = ordered_lower.copy()
    widened_upper = ordered_upper.copy()

    phase_series = df['phase'].fillna('unknown').astype(str) if 'phase' in df.columns else pd.Series(['unknown'] * len(df), index=df.index)
    for phase_name in phase_series.unique():
        mask = (phase_series == phase_name).to_numpy()
        adjustment = float(adjustments.get(phase_name, default_adjustment))
        widened_lower[mask] = ordered_lower[mask] - adjustment
        widened_upper[mask] = ordered_upper[mask] + adjustment

    return widened_lower, widened_upper


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


def _make_delta_regressor(random_state: int) -> XGBRegressor:
    return XGBRegressor(
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


def _train_delta_candidates(
    X_train: pd.DataFrame,
    X_holdout: pd.DataFrame,
    train_df: pd.DataFrame,
    holdout_df: pd.DataFrame,
    random_state: int,
) -> Tuple[Dict[str, Any], Dict[str, pd.DataFrame], Dict[str, Any]]:
    raw_model = _make_delta_regressor(random_state)
    raw_model.fit(X_train, train_df['ml_delta_12'])
    raw_pred = raw_model.predict(X_holdout)
    _, raw_frame = _build_prediction_frames(holdout_df, np.full(len(holdout_df), 0.5), raw_pred)
    raw_metrics = _delta_slice_metrics(raw_frame)

    residual_model = _make_delta_regressor(random_state)
    residual_model.fit(X_train, train_df['residual_delta_12'])
    residual_component = residual_model.predict(X_holdout)
    residual_pred = holdout_df['momentum_baseline_12'].to_numpy() + residual_component
    _, residual_frame = _build_prediction_frames(holdout_df, np.full(len(holdout_df), 0.5), residual_pred)
    residual_metrics = _delta_slice_metrics(residual_frame)

    candidates = {
        'raw_delta': {
            'model': raw_model,
            'prediction_frame': raw_frame,
            'metrics': raw_metrics,
            'target_description': 'xgboost_regressor_on_ml_delta_12',
        },
        'residual_delta': {
            'model': residual_model,
            'prediction_frame': residual_frame,
            'metrics': residual_metrics,
            'target_description': 'xgboost_regressor_on_residual_delta_12_plus_momentum_baseline',
        },
    }
    chosen_name = min(candidates, key=lambda name: candidates[name]['metrics']['overall']['mae'])
    chosen = candidates[chosen_name]
    chosen['mode'] = chosen_name
    return chosen, {name: payload['prediction_frame'] for name, payload in candidates.items()}, {
        name: payload['metrics'] for name, payload in candidates.items()
    }


def _select_delta_point_candidate(
    candidate_metrics: Dict[str, Dict[str, Any]],
    direction_accuracy: float,
) -> Tuple[str, Dict[str, Any]]:
    best_mae = min(payload['overall']['mae'] for payload in candidate_metrics.values())
    sign_floor = direction_accuracy - 0.005
    mae_ceiling = best_mae * 1.02
    priority = [
        DELTA_POINT_MODE_DIRECTION_WEIGHTED,
        DELTA_POINT_MODE_DIRECTION_SIGNED,
        DELTA_POINT_MODE_MODEL,
    ]

    for mode in priority:
        overall = candidate_metrics[mode]['overall']
        if overall['sign_accuracy'] >= sign_floor and overall['mae'] <= mae_ceiling:
            return mode, {
                'rule': 'direction_sign_within_mae_ceiling',
                'direction_accuracy': direction_accuracy,
                'sign_floor': sign_floor,
                'best_mae': best_mae,
                'mae_ceiling': mae_ceiling,
            }

    chosen_mode = min(candidate_metrics, key=lambda mode: candidate_metrics[mode]['overall']['mae'])
    return chosen_mode, {
        'rule': 'lowest_mae_fallback',
        'direction_accuracy': direction_accuracy,
        'best_mae': best_mae,
    }


def _build_delta_point_candidates(
    holdout_df: pd.DataFrame,
    direction_prob: np.ndarray,
    base_delta_pred: np.ndarray,
) -> Tuple[str, float, pd.DataFrame, Dict[str, Any], Dict[str, Any]]:
    direction_accuracy = float(accuracy_score(holdout_df['direction'], (direction_prob >= 0.5).astype(int)))
    frames: Dict[str, pd.DataFrame] = {}
    metrics: Dict[str, Any] = {}
    scales: Dict[str, float] = {
        DELTA_POINT_MODE_MODEL: 1.0,
        DELTA_POINT_MODE_DIRECTION_SIGNED: 1.0,
        DELTA_POINT_MODE_DIRECTION_WEIGHTED: _select_direction_weighted_scale(
            holdout_df,
            direction_prob,
            base_delta_pred,
        ),
    }
    for mode in [
        DELTA_POINT_MODE_MODEL,
        DELTA_POINT_MODE_DIRECTION_SIGNED,
        DELTA_POINT_MODE_DIRECTION_WEIGHTED,
    ]:
        point_pred = apply_delta_point_mode(base_delta_pred, direction_prob, mode, scale=scales[mode])
        _, frame = _build_prediction_frames(holdout_df, np.full(len(holdout_df), 0.5), point_pred)
        frames[mode] = frame
        metrics[mode] = _delta_slice_metrics(frame)

    chosen_mode, selection = _select_delta_point_candidate(metrics, direction_accuracy)
    selection['candidate_scales'] = scales
    return chosen_mode, scales[chosen_mode], frames[chosen_mode], metrics, selection


def _select_direction_weighted_scale(
    holdout_df: pd.DataFrame,
    direction_prob: np.ndarray,
    base_delta_pred: np.ndarray,
) -> float:
    y_true = holdout_df['ml_delta_12']
    best_scale = 1.0
    best_rmse = np.inf
    for scale in np.linspace(0.5, 1.75, 26):
        pred = apply_delta_point_mode(
            base_delta_pred,
            direction_prob,
            DELTA_POINT_MODE_DIRECTION_WEIGHTED,
            scale=float(scale),
        )
        rmse = np.sqrt(mean_squared_error(y_true, pred))
        if rmse < best_rmse:
            best_rmse = rmse
            best_scale = float(scale)
    return best_scale


def _make_quantile_regressor(quantile: float, random_state: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss='quantile',
        quantile=quantile,
        max_depth=5,
        learning_rate=0.05,
        max_iter=200,
        min_samples_leaf=50,
        l2_regularization=0.1,
        random_state=random_state,
    )


def _train_interval_models(
    X_interval_train: pd.DataFrame,
    X_interval_calibration: pd.DataFrame,
    X_holdout: pd.DataFrame,
    interval_train_df: pd.DataFrame,
    interval_calibration_df: pd.DataFrame,
    holdout_df: pd.DataFrame,
    selected_delta_mode: str,
    random_state: int,
    alpha: float = 0.1,
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    target_column = 'residual_delta_12' if selected_delta_mode == 'residual_delta' else 'ml_delta_12'
    lower_model = _make_quantile_regressor(0.05, random_state)
    upper_model = _make_quantile_regressor(0.95, random_state)
    lower_model.fit(X_interval_train, interval_train_df[target_column])
    upper_model.fit(X_interval_train, interval_train_df[target_column])

    calibration_lower = lower_model.predict(X_interval_calibration)
    calibration_upper = upper_model.predict(X_interval_calibration)
    if selected_delta_mode == 'residual_delta':
        calibration_baseline = interval_calibration_df['momentum_baseline_12'].to_numpy()
        calibration_lower = calibration_baseline + calibration_lower
        calibration_upper = calibration_baseline + calibration_upper
    conformal_adjustments = _phase_conditioned_conformal_adjustments(
        interval_calibration_df,
        calibration_lower,
        calibration_upper,
        alpha,
    )

    lower_pred = lower_model.predict(X_holdout)
    upper_pred = upper_model.predict(X_holdout)
    if selected_delta_mode == 'residual_delta':
        baseline = holdout_df['momentum_baseline_12'].to_numpy()
        lower_pred = baseline + lower_pred
        upper_pred = baseline + upper_pred

    interval_frame = holdout_df.copy()
    widened_lower, widened_upper = _apply_phase_adjustments(holdout_df, lower_pred, upper_pred, conformal_adjustments)
    interval_frame['pred_delta_lower'] = widened_lower
    interval_frame['pred_delta_upper'] = widened_upper

    return {
        'lower_model': lower_model,
        'upper_model': upper_model,
        'target_column': target_column,
        'alpha': alpha,
        'conformal_adjustments': conformal_adjustments,
        'calibration_rows': int(len(interval_calibration_df)),
    }, interval_frame


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
    joblib.dump(models['delta_interval_lower_model'], output_dir / 'delta_interval_lower_model.joblib')
    joblib.dump(models['delta_interval_upper_model'], output_dir / 'delta_interval_upper_model.joblib')
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

    interval_calibration_mask = _build_holdout_mask(train_df, holdout_frac=0.15)
    interval_train_df = train_df.loc[~interval_calibration_mask].copy()
    interval_calibration_df = train_df.loc[interval_calibration_mask].copy()
    if interval_train_df.empty or interval_calibration_df.empty:
        raise ValueError('ODM interval split failed: empty train or calibration set')

    X_all, feature_columns = _prepare_features(df)
    X_train = X_all.loc[train_df.index]
    X_holdout = X_all.loc[holdout_df.index]
    X_interval_train = X_all.loc[interval_train_df.index]
    X_interval_calibration = X_all.loc[interval_calibration_df.index]

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
    direction_model.fit(X_train, train_df['direction'])

    direction_prob = direction_model.predict_proba(X_holdout)[:, 1]
    chosen_delta, _candidate_frames, candidate_delta_metrics = _train_delta_candidates(
        X_train, X_holdout, train_df, holdout_df, random_state
    )
    base_delta_pred = chosen_delta['prediction_frame']['pred_delta'].to_numpy()
    selected_delta_point_mode, selected_delta_point_scale, delta_frame, candidate_delta_point_metrics, delta_point_selection = _build_delta_point_candidates(
        holdout_df,
        direction_prob,
        base_delta_pred,
    )
    direction_frame, _ = _build_prediction_frames(holdout_df, direction_prob, base_delta_pred)
    interval_models, interval_frame = _train_interval_models(
        X_interval_train,
        X_interval_calibration,
        X_holdout,
        interval_train_df,
        interval_calibration_df,
        holdout_df,
        selected_delta_mode=chosen_delta['mode'],
        random_state=random_state,
    )

    metrics = {
        'direction_model': _direction_slice_metrics(direction_frame),
        'delta_model': _delta_slice_metrics(delta_frame),
        'interval_model': _interval_slice_metrics(interval_frame),
        'delta_candidates': candidate_delta_metrics,
        'delta_point_candidates': candidate_delta_point_metrics,
    }
    baseline_metrics = _baseline_metrics(holdout_df)
    metrics['comparison'] = _build_comparison(metrics, baseline_metrics)
    metrics['comparison']['selected_delta_mode'] = chosen_delta['mode']
    metrics['comparison']['selected_delta_point_mode'] = selected_delta_point_mode
    metrics['comparison']['selected_delta_point_scale'] = selected_delta_point_scale
    metrics['comparison']['delta_point_selection'] = delta_point_selection

    training_manifest = {
        'input_file': str(input_file),
        'holdout_frac': holdout_frac,
        'random_state': random_state,
        'train_rows': int(len(train_df)),
        'interval_train_rows': int(len(interval_train_df)),
        'interval_calibration_rows': int(len(interval_calibration_df)),
        'holdout_rows': int(len(holdout_df)),
        'train_matches': int(train_df['match_id'].nunique()),
        'interval_train_matches': int(interval_train_df['match_id'].nunique()),
        'interval_calibration_matches': int(interval_calibration_df['match_id'].nunique()),
        'holdout_matches': int(holdout_df['match_id'].nunique()),
        'feature_count': len(feature_columns),
        'model_types': {
            'direction_model': 'xgboost_classifier_on_direction',
            'delta_model': chosen_delta['target_description'],
            'delta_point_estimator': selected_delta_point_mode,
            'interval_model': f"hist_gradient_boosting_quantiles_on_{interval_models['target_column']}_with_phase_conditioned_split_conformal_adjustment",
        },
        'selected_delta_mode': chosen_delta['mode'],
        'selected_delta_point_mode': selected_delta_point_mode,
        'selected_delta_point_scale': selected_delta_point_scale,
        'delta_point_selection': delta_point_selection,
        'interval_alpha': interval_models['alpha'],
        'interval_conformal_adjustments': interval_models['conformal_adjustments'],
    }

    save_odm_artifacts(
        output_dir,
        {
            'direction_model': direction_model,
            'delta_model': chosen_delta['model'],
            'delta_interval_lower_model': interval_models['lower_model'],
            'delta_interval_upper_model': interval_models['upper_model'],
        },
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
    training_manifest = json.load(open(model_dir / 'training_manifest.json', 'r', encoding='utf-8'))
    selected_delta_mode = training_manifest.get('selected_delta_mode', 'raw_delta')
    if selected_delta_mode == 'residual_delta':
        base_delta_pred = holdout_df['momentum_baseline_12'].to_numpy() + models['delta_model'].predict(X_holdout)
    else:
        base_delta_pred = models['delta_model'].predict(X_holdout)
    selected_delta_point_mode = training_manifest.get('selected_delta_point_mode', DELTA_POINT_MODE_MODEL)
    selected_delta_point_scale = float(training_manifest.get('selected_delta_point_scale', 1.0))
    delta_pred = apply_delta_point_mode(
        base_delta_pred,
        direction_prob,
        selected_delta_point_mode,
        scale=selected_delta_point_scale,
    )
    direction_frame, delta_frame = _build_prediction_frames(holdout_df, direction_prob, delta_pred)

    lower_pred = models['delta_interval_lower_model'].predict(X_holdout)
    upper_pred = models['delta_interval_upper_model'].predict(X_holdout)
    if selected_delta_mode == 'residual_delta':
        baseline = holdout_df['momentum_baseline_12'].to_numpy()
        lower_pred = baseline + lower_pred
        upper_pred = baseline + upper_pred
    conformal_adjustments = training_manifest.get('interval_conformal_adjustments', {'overall': 0.0})
    interval_frame = holdout_df.copy()
    widened_lower, widened_upper = _apply_phase_adjustments(holdout_df, lower_pred, upper_pred, conformal_adjustments)
    interval_frame['pred_delta_lower'] = widened_lower
    interval_frame['pred_delta_upper'] = widened_upper

    metrics = {
        'direction_model': _direction_slice_metrics(direction_frame),
        'delta_model': _delta_slice_metrics(delta_frame),
        'interval_model': _interval_slice_metrics(interval_frame),
    }
    baseline_metrics = _baseline_metrics(holdout_df)
    metrics['comparison'] = _build_comparison(metrics, baseline_metrics)
    metrics['comparison']['selected_delta_mode'] = selected_delta_mode
    metrics['comparison']['selected_delta_point_mode'] = selected_delta_point_mode
    metrics['comparison']['selected_delta_point_scale'] = selected_delta_point_scale
    return {
        'metrics': metrics,
        'baseline_metrics': baseline_metrics,
    }
