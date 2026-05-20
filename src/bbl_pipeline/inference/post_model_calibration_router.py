"""Gated post-model calibration for IPL production probabilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np


class PostModelCalibrationRouter:
    """Apply narrow, guardrailed calibration corrections after model inference."""

    def __init__(self, artifact: dict[str, Any]):
        self.artifact = artifact
        self.enabled = bool(artifact.get("enabled", True))
        self.last_rule: str | None = None
        self.last_input_probability: float | None = None
        self.last_output_probability: float | None = None

    @classmethod
    def load(cls, path: str | Path) -> "PostModelCalibrationRouter":
        return cls(joblib.load(path))

    @staticmethod
    def _clip_probability(probability: float) -> float:
        return float(np.clip(probability, 1e-6, 1.0 - 1e-6))

    @staticmethod
    def _predict(calibrator: Any, probability: float) -> float:
        if hasattr(calibrator, "predict"):
            return float(np.asarray(calibrator.predict([probability])).reshape(-1)[0])
        if hasattr(calibrator, "transform"):
            return float(np.asarray(calibrator.transform([probability])).reshape(-1)[0])
        raise TypeError(f"Unsupported calibrator type: {type(calibrator)!r}")

    @staticmethod
    def _phase_key(phase: str | None) -> str:
        normalized = (phase or "").strip().lower()
        if normalized in {"powerplay", "pp", "inn1_powerplay", "inn2_powerplay"}:
            return "pp"
        if normalized in {"middle", "mid", "inn1_middle", "inn2_middle"}:
            return "mid"
        if normalized in {"death", "inn1_death", "inn2_death"}:
            return "death"
        return normalized

    def apply(
        self,
        probability: float,
        *,
        innings: int,
        phase: str | None = None,
        target_above_par: float | None = None,
    ) -> tuple[float, str | None]:
        """Return the corrected probability and the applied rule name, if any."""

        probability = self._clip_probability(probability)
        self.last_rule = None
        self.last_input_probability = probability
        self.last_output_probability = probability

        if not self.enabled:
            return probability, None

        if innings == 1:
            return self._apply_inn1(probability)

        if innings == 2:
            return self._apply_inn2(probability, phase, target_above_par)

        return probability, None

    def _apply_inn1(self, probability: float) -> tuple[float, str | None]:
        config = self.artifact.get("inn1_low_side")
        if not config or not bool(config.get("enabled", True)):
            return probability, None

        apply_below = float(config.get("apply_below", 0.50))
        if probability >= apply_below:
            return probability, None

        calibrator = config["calibrator"]
        floor = float(config.get("floor", 0.02))
        ceiling = float(config.get("ceiling", apply_below - 1e-6))
        blend_start = float(config.get("blend_start", 0.45))
        blend_width = max(apply_below - blend_start, 1e-6)

        calibrated = np.clip(self._predict(calibrator, probability), floor, ceiling)
        weight = np.clip((apply_below - probability) / blend_width, 0.0, 1.0)
        corrected = float(weight * calibrated + (1.0 - weight) * probability)
        return self._finish(corrected, "inn1_low_side")

    def _apply_inn2(
        self,
        probability: float,
        phase: str | None,
        target_above_par: float | None,
    ) -> tuple[float, str | None]:
        if target_above_par is None:
            return probability, None

        target_above_par = float(target_above_par)
        phase_key = self._phase_key(phase)
        low_threshold = float(self.artifact.get("low_chase_threshold", -20.0))
        high_threshold = float(self.artifact.get("high_chase_threshold", 20.0))

        easy = self.artifact.get("inn2_easy_chase")
        if (
            easy
            and bool(easy.get("enabled", True))
            and target_above_par < low_threshold
            and float(easy.get("min_probability", 0.50)) <= probability <= float(easy.get("max_probability", 0.85))
        ):
            return self._apply_upward_rule(probability, easy, "inn2_easy_chase")

        par_mid = self.artifact.get("inn2_par_pp_mid")
        allowed_phases = set(par_mid.get("allowed_phases", ["pp"])) if par_mid else set()
        phase_bounds = par_mid.get("phase_target_above_par_bounds", {}) if par_mid else {}
        phase_low = low_threshold
        phase_high = high_threshold
        if phase_key in phase_bounds:
            bounds = phase_bounds[phase_key]
            if len(bounds) != 2:
                raise ValueError(f"Invalid phase_target_above_par_bounds for {phase_key}: {bounds!r}")
            phase_low = float(bounds[0])
            phase_high = float(bounds[1])
        if (
            par_mid
            and bool(par_mid.get("enabled", True))
            and phase_low <= target_above_par <= phase_high
            and phase_key in allowed_phases
            and float(par_mid.get("min_probability", 0.50)) <= probability <= float(par_mid.get("max_probability", 0.80))
        ):
            return self._apply_upward_rule(probability, par_mid, "inn2_par_pp_mid")

        return probability, None

    def _apply_upward_rule(
        self,
        probability: float,
        config: dict[str, Any],
        rule_name: str,
    ) -> tuple[float, str | None]:
        calibrator = config["calibrator"]
        ceiling = float(config.get("ceiling", 0.98))
        calibrated = np.clip(self._predict(calibrator, probability), 1e-6, ceiling)
        calibrated = max(probability, float(calibrated))

        min_probability = float(config.get("min_probability", 0.50))
        max_probability = float(config.get("max_probability", 0.85))
        blend_width = float(config.get("blend_width", 0.05))
        if blend_width > 0:
            lower_weight = np.clip((probability - min_probability) / blend_width, 0.0, 1.0)
            upper_weight = np.clip((max_probability - probability) / blend_width, 0.0, 1.0)
            weight = min(float(lower_weight), float(upper_weight))
        else:
            weight = 1.0

        corrected = float(weight * calibrated + (1.0 - weight) * probability)
        return self._finish(corrected, rule_name)

    def _finish(self, probability: float, rule_name: str) -> tuple[float, str]:
        corrected = self._clip_probability(probability)
        self.last_rule = rule_name
        self.last_output_probability = corrected
        return corrected, rule_name
