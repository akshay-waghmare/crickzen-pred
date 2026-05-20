import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_SRC = Path(__file__).resolve().parents[2] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from bbl_pipeline.inference.odds_direction_model import OddsDirectionModel
from bbl_pipeline.inference.odm_delta_point import (
    DELTA_POINT_MODE_DIRECTION_WEIGHTED,
    DELTA_POINT_MODE_MODEL,
    apply_delta_point_mode,
)


def test_model_delta_point_mode_returns_base_estimate():
    base = np.array([-0.1, 0.2])

    result = apply_delta_point_mode(base, np.array([0.9, 0.1]), DELTA_POINT_MODE_MODEL)

    np.testing.assert_allclose(result, base)


@pytest.mark.parametrize(
    ("direction_prob", "expected_sign"),
    [(0.1, -1), (0.4, -1), (0.6, 1), (0.9, 1)],
)
def test_direction_weighted_delta_uses_direction_sign_and_contracts_magnitude(direction_prob, expected_sign):
    base = np.array([-0.12, 0.08])

    result = apply_delta_point_mode(base, direction_prob, DELTA_POINT_MODE_DIRECTION_WEIGHTED)

    assert np.all(np.sign(result) == expected_sign)
    assert np.all(np.abs(result) <= np.abs(base))


def test_direction_weighted_delta_applies_scale():
    result = apply_delta_point_mode(0.10, 0.80, DELTA_POINT_MODE_DIRECTION_WEIGHTED, scale=1.35)

    assert result == pytest.approx(0.081)


def test_unknown_delta_point_mode_raises_clear_error():
    with pytest.raises(ValueError, match="not_a_mode"):
        apply_delta_point_mode(0.1, 0.6, "not_a_mode")


class _ProbModel:
    def predict_proba(self, _frame):
        return np.array([[0.2, 0.8]])


class _PredictModel:
    def __init__(self, value):
        self.value = value

    def predict(self, _frame):
        return np.array([self.value])


def test_live_odm_uses_direction_weighted_delta_point_mode():
    odm = OddsDirectionModel(
        status='ready',
        feature_columns=['ml_prob', 'momentum_baseline_12'],
        training_manifest={
            'selected_delta_mode': 'raw_delta',
            'selected_delta_point_mode': DELTA_POINT_MODE_DIRECTION_WEIGHTED,
            'selected_delta_point_scale': 1.35,
            'interval_conformal_adjustments': {'overall': 0.0},
        },
        models={
            'direction_model': _ProbModel(),
            'delta_model': _PredictModel(-0.10),
            'delta_interval_lower_model': _PredictModel(-0.20),
            'delta_interval_upper_model': _PredictModel(0.20),
        },
    )
    history = [
        {'innings': 1, 'over': index // 6, 'ball': (index % 6) + 1, 'raw_win_prob': 0.50, 'resource_win_prob': 0.45}
        for index in range(12)
    ]

    result = odm.predict(
        live_features={
            'resource_win_prob': 0.50,
            'current_run_rate': 8.0,
            'projected_score': 160.0,
            'is_powerplay': 0,
            'is_death_overs': 0,
        },
        predictor=None,
        batting_team='Team A',
        bowling_team='Team B',
        venue='Venue',
        league='ipl',
        innings=1,
        over=3,
        ball=1,
        target_score=None,
        current_ml_prob=0.55,
        history=history,
    )

    assert result['status'] == 'ready'
    assert result['selected_delta_point_mode'] == DELTA_POINT_MODE_DIRECTION_WEIGHTED
    assert result['selected_delta_point_scale'] == pytest.approx(1.35)
    assert result['delta_12']['point_estimate'] == pytest.approx(0.081)
    assert result['delta_12']['point_estimate_status'] == 'direction_guided'
    assert result['advisory']['use_point_estimate'] is True
