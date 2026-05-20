from __future__ import annotations

from typing import Any

import numpy as np

DELTA_POINT_MODE_MODEL = 'model_delta'
DELTA_POINT_MODE_DIRECTION_SIGNED = 'direction_signed_abs_delta'
DELTA_POINT_MODE_DIRECTION_WEIGHTED = 'direction_weighted_abs_delta'

DELTA_POINT_MODES = {
    DELTA_POINT_MODE_MODEL,
    DELTA_POINT_MODE_DIRECTION_SIGNED,
    DELTA_POINT_MODE_DIRECTION_WEIGHTED,
}


def _return_scalar_if_needed(value: Any) -> Any:
    value_array = np.asarray(value)
    return float(value_array.item()) if value_array.ndim == 0 else value


def apply_delta_point_mode(base_delta: Any, direction_up_prob: Any, mode: str, scale: float = 1.0) -> Any:
    """Post-process a base delta estimate into the configured ODM point estimate."""
    if mode not in DELTA_POINT_MODES:
        raise ValueError(f"Unknown ODM delta point mode: {mode}")

    base_array = np.asarray(base_delta, dtype=float)
    if mode == DELTA_POINT_MODE_MODEL:
        return _return_scalar_if_needed(base_array)

    prob_array = np.asarray(direction_up_prob, dtype=float)
    prob_array = np.nan_to_num(prob_array, nan=0.5, posinf=1.0, neginf=0.0)
    prob_array = np.clip(prob_array, 0.0, 1.0)
    magnitude = np.abs(np.nan_to_num(base_array, nan=0.0))

    if mode == DELTA_POINT_MODE_DIRECTION_SIGNED:
        result = np.where(prob_array >= 0.5, magnitude, -magnitude)
    else:
        result = (2.0 * prob_array - 1.0) * magnitude

    return _return_scalar_if_needed(result * float(scale))
