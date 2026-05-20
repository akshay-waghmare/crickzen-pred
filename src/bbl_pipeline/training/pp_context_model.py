from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression


class ContextCalibratedPPModel:
    """Wrap a base PP model and apply context-aware internal calibration."""

    def __init__(
        self,
        base_model: Any,
        base_features: Iterable[str],
        calibration_bundle: dict[str, Any],
        feature_names: Iterable[str] | None = None,
    ):
        self.base_model = base_model
        self.base_features = list(base_features)
        self.calibration_bundle = calibration_bundle
        self.feature_names = list(feature_names) if feature_names is not None else None
        self.classes_ = np.array([0, 1])

    def _to_frame(self, X: pd.DataFrame | np.ndarray) -> pd.DataFrame:
        if isinstance(X, pd.DataFrame):
            return X.copy()
        if self.feature_names is None:
            raise ValueError("feature_names are required when predict_proba receives an array")
        return pd.DataFrame(X, columns=self.feature_names)

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        frame = self._to_frame(X)
        raw = self.base_model.predict_proba(frame[self.base_features])[:, 1]
        calibrated = apply_hierarchical_isotonic_bundle(raw, frame, self.calibration_bundle)
        return np.column_stack([1.0 - calibrated, calibrated])

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def fit_hierarchical_isotonic_bundle(
    raw: np.ndarray,
    y: np.ndarray,
    context_df: pd.DataFrame,
    levels: Iterable[dict[str, Any]],
    blend_weight: float = 0.68,
    clip_bounds: tuple[float, float] = (0.05, 0.95),
) -> dict[str, Any]:
    context = context_df.reset_index(drop=True).copy()
    raw_arr = np.asarray(raw, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    global_cal = IsotonicRegression(out_of_bounds='clip')
    global_cal.fit(raw_arr, y_arr)

    fitted_levels: list[dict[str, Any]] = []
    for level in levels:
        columns = list(level['columns'])
        min_samples = int(level.get('min_samples', 80))
        tmp = context[columns].copy()
        tmp['raw'] = raw_arr
        tmp['y'] = y_arr
        calibrators: dict[tuple[Any, ...], Any] = {}
        for keys, group in tmp.groupby(columns, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            if len(group) < min_samples or group['raw'].nunique() <= 1:
                continue
            cal = IsotonicRegression(out_of_bounds='clip')
            cal.fit(group['raw'].to_numpy(dtype=float), group['y'].to_numpy(dtype=float))
            calibrators[keys] = cal
        fitted_levels.append({'columns': columns, 'min_samples': min_samples, 'calibrators': calibrators})

    return {
        'global_calibrator': global_cal,
        'levels': fitted_levels,
        'blend_weight': float(blend_weight),
        'clip_bounds': (float(clip_bounds[0]), float(clip_bounds[1])),
    }


def apply_hierarchical_isotonic_bundle(
    raw: np.ndarray,
    context_df: pd.DataFrame,
    bundle: dict[str, Any],
) -> np.ndarray:
    context = context_df.reset_index(drop=True).copy()
    raw_arr = np.asarray(raw, dtype=float)
    global_cal = bundle.get('global_calibrator')
    levels = bundle.get('levels', [])
    blend_weight = float(bundle.get('blend_weight', 1.0))
    clip_lo, clip_hi = bundle.get('clip_bounds', (0.0, 1.0))

    calibrated = np.empty_like(raw_arr)
    for idx, raw_value in enumerate(raw_arr):
        cal_value = None
        for level in levels:
            columns = level.get('columns', [])
            if any(column not in context.columns for column in columns):
                continue
            key = tuple(context.loc[idx, columns].tolist())
            calibrator = level.get('calibrators', {}).get(key)
            if calibrator is not None:
                cal_value = float(calibrator.transform([raw_value])[0])
                break
        if cal_value is None:
            cal_value = float(global_cal.transform([raw_value])[0]) if global_cal is not None else float(raw_value)
        blended = (1.0 - blend_weight) * float(raw_value) + blend_weight * cal_value
        calibrated[idx] = np.clip(blended, clip_lo, clip_hi)
    return calibrated
