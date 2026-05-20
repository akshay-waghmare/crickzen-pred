from pathlib import Path

import joblib

from bbl_pipeline.inference.post_model_calibration_router import PostModelCalibrationRouter


class LinearCalibrator:
    def __init__(self, shift: float):
        self.shift = shift

    def predict(self, values):
        return [min(0.99, max(0.01, float(value) + self.shift)) for value in values]


def make_router() -> PostModelCalibrationRouter:
    return PostModelCalibrationRouter(
        {
            "enabled": True,
            "low_chase_threshold": -20.0,
            "high_chase_threshold": 20.0,
            "inn1_low_side": {
                "enabled": True,
                "calibrator": LinearCalibrator(-0.10),
                "apply_below": 0.50,
                "floor": 0.02,
                "ceiling": 0.499,
                "blend_start": 0.45,
            },
            "inn2_easy_chase": {
                "enabled": True,
                "calibrator": LinearCalibrator(0.15),
                "min_probability": 0.50,
                "max_probability": 0.85,
                "ceiling": 0.98,
                "blend_width": 0.0,
            },
            "inn2_par_pp_mid": {
                "enabled": True,
                "calibrator": LinearCalibrator(0.12),
                "allowed_phases": ["pp", "mid"],
                "phase_target_above_par_bounds": {"mid": [-20.0, 0.0]},
                "min_probability": 0.50,
                "max_probability": 0.80,
                "ceiling": 0.95,
                "blend_width": 0.0,
            },
        }
    )


def test_inn1_low_side_only_below_50():
    router = make_router()

    corrected, rule = router.apply(0.40, innings=1)
    assert rule == "inn1_low_side"
    assert corrected < 0.40

    unchanged, rule = router.apply(0.55, innings=1)
    assert rule is None
    assert unchanged == 0.55


def test_inn2_easy_chase_sharpens_only_easy_gate():
    router = make_router()

    corrected, rule = router.apply(
        0.70,
        innings=2,
        phase="inn2_death",
        target_above_par=-30.0,
    )
    assert rule == "inn2_easy_chase"
    assert corrected == 0.85

    unchanged, rule = router.apply(
        0.70,
        innings=2,
        phase="inn2_death",
        target_above_par=30.0,
    )
    assert rule is None
    assert unchanged == 0.70


def test_inn2_par_pp_mid_accepts_powerplay_and_middle_segments_only():
    router = make_router()

    corrected, rule = router.apply(
        0.65,
        innings=2,
        phase="inn2_powerplay",
        target_above_par=5.0,
    )
    assert rule == "inn2_par_pp_mid"
    assert corrected == 0.77

    corrected, rule = router.apply(
        0.65,
        innings=2,
        phase="inn2_middle",
        target_above_par=-5.0,
    )
    assert rule == "inn2_par_pp_mid"
    assert corrected == 0.77

    unchanged, rule = router.apply(
        0.65,
        innings=2,
        phase="inn2_middle",
        target_above_par=5.0,
    )
    assert rule is None
    assert unchanged == 0.65

    unchanged, rule = router.apply(
        0.65,
        innings=2,
        phase="inn2_death",
        target_above_par=5.0,
    )
    assert rule is None
    assert unchanged == 0.65


def test_production_router_artifact_keeps_par_correction_enabled_for_mid():
    artifact_path = Path("models/ipl_v14_pitch_features/post_model_calibration_router.pkl")
    artifact = joblib.load(artifact_path)

    allowed_phases = artifact["inn2_par_pp_mid"]["allowed_phases"]
    phase_bounds = artifact["inn2_par_pp_mid"]["phase_target_above_par_bounds"]

    assert allowed_phases == ["pp", "mid"]
    assert phase_bounds == {"mid": [-20.0, 0.0]}
