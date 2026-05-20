import numpy as np
import pandas as pd

from bbl_pipeline.training.pp_context_model import (
    ContextCalibratedPPModel,
    apply_hierarchical_isotonic_bundle,
)


class FakeBaseModel:
    def predict_proba(self, X):
        n_rows = len(X)
        probs = np.full(n_rows, 0.30, dtype=float)
        return np.column_stack([1.0 - probs, probs])


class FakeCalibrator:
    def __init__(self, output: float):
        self.output = output

    def transform(self, values):
        return np.full(len(values), self.output, dtype=float)


def test_apply_hierarchical_bundle_uses_most_specific_context_and_blends():
    frame = pd.DataFrame(
        {
            'over': [1, 1, 2],
            'chase_category': [1, 0, 0],
            'pp_score_bin': [5, 2, 3],
            'pp_gap_bin': [6, 4, 1],
        }
    )
    bundle = {
        'global_calibrator': FakeCalibrator(0.40),
        'levels': [
            {
                'columns': ['over', 'chase_category', 'pp_score_bin', 'pp_gap_bin'],
                'calibrators': {(1, 1, 5, 6): FakeCalibrator(0.90)},
            },
            {
                'columns': ['over', 'chase_category'],
                'calibrators': {(1, 0): FakeCalibrator(0.60)},
            },
        ],
        'blend_weight': 0.5,
        'clip_bounds': (0.05, 0.95),
    }

    calibrated = apply_hierarchical_isotonic_bundle(np.array([0.30, 0.30, 0.30]), frame, bundle)

    assert np.allclose(calibrated, np.array([0.60, 0.45, 0.35]))


def test_context_calibrated_model_uses_base_features_only_for_raw_model():
    frame = pd.DataFrame(
        {
            'feature_a': [1.0],
            'feature_b': [2.0],
            'over': [1],
            'chase_category': [1],
            'pp_score_bin': [5],
            'pp_gap_bin': [6],
        }
    )
    bundle = {
        'global_calibrator': FakeCalibrator(0.70),
        'levels': [],
        'blend_weight': 1.0,
        'clip_bounds': (0.05, 0.95),
    }
    model = ContextCalibratedPPModel(
        base_model=FakeBaseModel(),
        base_features=['feature_a', 'feature_b'],
        calibration_bundle=bundle,
        feature_names=frame.columns,
    )

    probs = model.predict_proba(frame)

    assert probs.shape == (1, 2)
    assert np.allclose(probs[0], np.array([0.30, 0.70]))
