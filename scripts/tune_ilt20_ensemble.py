"""Hyperparameter tuning for the ILT20 ensemble model (Brier score).

Runs a small random search using the same time-series split logic as training.
Saves the best model and metadata to the requested output directory.

Example:
  python scripts/tune_ilt20_ensemble.py --input-file data/ilt_features_v2/training.parquet --output-dir models/ilt20_v3_tuned --trials 25
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss
import structlog

from bbl_pipeline.training.evaluation import TimeSeriesCalibrationSplit
from bbl_pipeline.training.trainer import XGBLogRegEnsemble


logger = structlog.get_logger()


def _evaluate_candidate(
    X: pd.DataFrame,
    y: pd.Series,
    model: XGBLogRegEnsemble,
    splitter: TimeSeriesCalibrationSplit,
) -> Tuple[float, float, List[float]]:
    fold_briers: List[float] = []

    for train_idx, calib_idx, test_idx in splitter.split(X):
        all_train_idx = np.concatenate([train_idx, calib_idx])
        X_train, y_train = X.iloc[all_train_idx], y.iloc[all_train_idx]
        X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]

        model_fold = XGBLogRegEnsemble(**model.get_params())
        model_fold.fit(X_train, y_train)
        probs = model_fold.predict_proba(X_test)[:, 1]
        fold_briers.append(brier_score_loss(y_test, probs))

    mean = float(np.mean(fold_briers))
    std = float(np.std(fold_briers))
    return mean, std, fold_briers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-file', required=True, help='Path to training dataset (parquet)')
    parser.add_argument('--output-dir', required=True, help='Directory to save best model + metadata')
    parser.add_argument('--trials', type=int, default=20, help='Number of random trials (default: 20)')
    parser.add_argument('--seed', type=int, default=42, help='Random seed (default: 42)')
    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(input_path)

    target_col = 'is_winner'
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataset.")

    y = df[target_col]
    X = df.drop(columns=[target_col])

    splitter = TimeSeriesCalibrationSplit(n_splits=5, calibration_size=0.15)

    rng = np.random.default_rng(args.seed)

    def to_jsonable(obj: Any) -> Any:
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {str(k): to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [to_jsonable(v) for v in obj]
        return obj

    # Discrete search space (kept small for practical runtime)
    space = {
        'xgb_weight': [0.35, 0.45, 0.5, 0.55, 0.65],
        'n_features': [18, 20, 22, 25],
        'logreg_c': [0.005, 0.01, 0.02, 0.05],
        'xgb_params': {
            'n_estimators': [350, 500, 650, 800],
            'max_depth': [2, 3],
            'learning_rate': [0.007, 0.011, 0.02],
            'subsample': [0.45, 0.5, 0.65, 0.75],
            'colsample_bytree': [0.45, 0.5, 0.65, 0.75],
            'min_child_weight': [10, 20, 28, 40],
            'reg_alpha': [0.0, 1.0, 2.8, 5.0],
            'reg_lambda': [1.0, 2.0, 3.8, 6.0],
        },
    }

    best = {
        'brier_mean': float('inf'),
        'brier_std': None,
        'params': None,
        'fold_briers': None,
    }

    for t in range(1, args.trials + 1):
        xgb_params = {k: to_jsonable(rng.choice(v)) for k, v in space['xgb_params'].items()}
        params: Dict[str, Any] = {
            'xgb_weight': float(rng.choice(space['xgb_weight'])),
            'n_features': int(rng.choice(space['n_features'])),
            'xgb_params': xgb_params,
            'logreg_c': float(rng.choice(space['logreg_c'])),
        }

        model = XGBLogRegEnsemble(**params)
        mean, std, fold_briers = _evaluate_candidate(X, y, model, splitter)

        logger.info(
            'trial_done',
            trial=t,
            trials=args.trials,
            brier_mean=round(mean, 6),
            brier_std=round(std, 6),
            params=params,
        )

        if mean < best['brier_mean']:
            best = {
                'brier_mean': mean,
                'brier_std': std,
                'params': params,
                'fold_briers': fold_briers,
            }

    if best['params'] is None:
        raise RuntimeError('No tuning trials completed successfully')

    logger.info('best_found', brier_mean=best['brier_mean'], brier_std=best['brier_std'], params=best['params'])

    # Fit best model on full data and save.
    best_model = XGBLogRegEnsemble(**best['params'])
    best_model.fit(X, y)

    joblib.dump(best_model, output_path / 'champion_model.joblib')
    with open(output_path / 'tuning_results.json', 'w', encoding='utf-8') as f:
        json.dump(to_jsonable(best), f, indent=2)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
