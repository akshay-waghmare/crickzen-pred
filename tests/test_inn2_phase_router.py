import numpy as np

from bbl_pipeline.inference.inn2_phase_router import Inn2PhaseRouter


class FakeModel:
    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, X):
        return np.array([[1.0 - self.probability, self.probability]])


class FakeCalibrator:
    def __init__(self, probability):
        self.probability = probability

    def predict(self, values):
        return np.array([self.probability])


def make_router(use_calibration=False, pp_low_fallback=None):
    models = {
        "pp": FakeModel(0.40),
        "mid": FakeModel(0.50),
        "death": FakeModel(0.60),
    }
    features = {
        "pp": ["target_above_par"],
        "mid": ["target_above_par"],
        "death": ["target_above_par"],
    }
    calibrators = {
        "pp": {"per_over": {3: FakeCalibrator(0.90)}},
        "mid": {"phase_iso": FakeCalibrator(0.80)},
        "death": {"phase_iso": FakeCalibrator(0.70)},
    }
    return Inn2PhaseRouter(models, features, calibrators, use_calibration, pp_low_fallback)


def test_router_uses_raw_probability_when_calibration_disabled():
    router = make_router(use_calibration=False)

    probability, phase = router.predict({"target_above_par": 0}, over_1indexed=3)

    assert phase == "pp"
    assert probability == 0.40
    assert router.last_model_source == "v14_pp_raw"


def test_router_can_still_apply_calibration_when_enabled():
    router = make_router(use_calibration=True)

    probability, phase = router.predict({"target_above_par": 0}, over_1indexed=3)

    assert phase == "pp"
    assert probability == 0.90
    assert router.last_model_source == "v14_pp_raw"


def test_pp_low_chase_uses_v12_raw_fallback():
    pp_low_fallback = {
        "model": FakeModel(0.25),
        "features": ["target_above_par"],
        "model_dir": "models/ipl_v12",
    }
    router = make_router(use_calibration=True, pp_low_fallback=pp_low_fallback)

    probability, phase = router.predict({"target_above_par": -25}, over_1indexed=3)

    assert phase == "pp"
    assert probability == 0.25
    assert router.last_model_source == "v12_pp_low_raw"
