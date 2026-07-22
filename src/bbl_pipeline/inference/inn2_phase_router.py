"""
Inn2PhaseRouter — routes inn2 predictions to phase-specific models.

Architecture (IPL v14 production router):
  Inn1: global v7 model  (unchanged)
  Inn2 PP    (overs 1–6):  champion_model_pp.joblib
  Inn2 Mid   (overs 7–15): champion_model_mid.joblib
  Inn2 Death (overs 16–20):champion_model_death.joblib

Each phase model uses engineered inn2 features (chase labels, momentum, etc.)
and may optionally apply per-over/phase calibration. IPL v14 production
sets apply_calibration=false and uses raw phase-model probabilities.

For IPL v14, PP easy chases (target_above_par < -20) fall back to the
ipl_v12 PP model raw probability because v14 pitch features underperformed
in that segment.

Usage:
    router = Inn2PhaseRouter.load("models/ipl_v14_pitch_features")
    prob, phase = router.predict(feature_dict, over_1indexed=8)
    # Returns (probability, "mid") or raises on total failure

Fail-open contract: predict() raises INN2RouterError.
Callers should catch it and fall back to v7 output.
"""

from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path
from typing import Any, Optional

import joblib
import pandas as pd

from bbl_pipeline.features.inn2_engineering import (
    LOW_CHASE_THRESHOLD,
    engineer_inn2_features,
    get_feature_sets,
)

logger = logging.getLogger(__name__)


class INN2RouterError(RuntimeError):
    """Raised when the router cannot produce a prediction (fail-open sentinel)."""


def _restore_simple_imputer(root) -> None:
    """Patch sklearn 1.8 SimpleImputer state for models saved under 1.7."""
    seen: set = set()
    stack = [root]
    while stack:
        obj = stack.pop()
        oid = id(obj)
        if obj is None or oid in seen:
            continue
        seen.add(oid)
        if type(obj).__name__ == "SimpleImputer":
            if hasattr(obj, "_fit_dtype") and not hasattr(obj, "_fill_dtype"):
                obj._fill_dtype = obj._fit_dtype
        if isinstance(obj, dict):
            stack.extend(obj.values())
        elif isinstance(obj, (list, tuple, set)):
            stack.extend(obj)
        elif hasattr(obj, "__dict__"):
            stack.extend(obj.__dict__.values())


class Inn2PhaseRouter:
    """Routes inn2 predictions to PP / Mid / Death phase models."""

    # Over ranges (1-indexed) for each phase
    PHASE_OVERS = {
        "pp":    range(1, 7),    # 1–6
        "mid":   range(7, 16),   # 7–15
        "death": range(16, 21),  # 16–20
    }

    def __init__(
        self,
        models: dict,          # {phase: XGBLRBlend}
        features: dict,        # {phase: [feature_names]}
        calibrators: dict,     # {phase: {"per_over": {over: iso}, "phase_iso": iso,
                               #          "per_cell": {(over, cat): iso}}}
        use_calibration: bool = True,
        pp_low_fallback: Optional[dict[str, Any]] = None,
    ):
        self._models     = models
        self._features   = features
        self._calibrators = calibrators
        self._use_calibration = use_calibration
        self._pp_low_fallback = pp_low_fallback
        self._phase_ranges = {"pp": (1, 6), "mid": (7, 15), "death": (16, 20)}
        self.last_model_source: Optional[str] = None
        self.last_raw_probability: Optional[float] = None
        self.last_output_probability: Optional[float] = None

    # ── factory ──────────────────────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        model_dir: str | Path,
        use_calibration: Optional[bool] = None,
        pp_low_fallback_model_dir: str | Path | None = None,
    ) -> "Inn2PhaseRouter":
        """Load phase models, feature lists, and calibrators from model_dir."""
        model_dir = Path(model_dir)

        routing_cfg = {}
        routing_cfg_path = model_dir / "routing_config.json"
        if routing_cfg_path.exists():
            with open(routing_cfg_path, encoding="utf-8") as f:
                routing_cfg = json.load(f)

        if use_calibration is None:
            use_calibration = bool(routing_cfg.get("apply_calibration", True))
        phase_ranges = routing_cfg.get("phase_ranges")
        if pp_low_fallback_model_dir is None:
            pp_low_fallback_model_dir = routing_cfg.get("pp_low_fallback_model_dir")

        phase_names = list((phase_ranges or {"pp": (1, 6), "mid": (7, 15), "death": (16, 20)}).keys())

        # Phase models
        models = {}
        for phase in phase_names:
            path = model_dir / f"champion_model_{phase}.joblib"
            if not path.exists():
                raise FileNotFoundError(f"Phase model not found: {path}")
            m = joblib.load(path)
            _restore_simple_imputer(m)
            models[phase] = m
            logger.info(f"[INN2Router] Loaded {phase} model from {path}")

        # Feature lists
        feat_path = model_dir / "phase_features.json"
        if feat_path.exists():
            with open(feat_path) as f:
                features = json.load(f)
        else:
            # Fallback: use canonical feature sets
            features = get_feature_sets()
            logger.warning("[INN2Router] phase_features.json not found — using canonical feature sets")

        # Calibrators
        cal_path = model_dir / "phase_oof_calibrators.pkl"
        if not use_calibration:
            calibrators = {}
        elif cal_path.exists():
            with open(cal_path, "rb") as f:
                calibrators = pickle.load(f)
            logger.info(f"[INN2Router] Loaded calibrators from {cal_path}")
        else:
            calibrators = {}
            logger.warning("[INN2Router] phase_oof_calibrators.pkl not found — using raw probabilities")

        pp_low_fallback = None
        if pp_low_fallback_model_dir:
            fallback_dir = Path(pp_low_fallback_model_dir)
            fallback_model_path = fallback_dir / "champion_model_pp.joblib"
            fallback_features_path = fallback_dir / "phase_features.json"
            if not fallback_model_path.exists():
                raise FileNotFoundError(f"PP low-chase fallback model not found: {fallback_model_path}")
            if not fallback_features_path.exists():
                raise FileNotFoundError(f"PP low-chase fallback features not found: {fallback_features_path}")

            fallback_model = joblib.load(fallback_model_path)
            _restore_simple_imputer(fallback_model)
            with open(fallback_features_path, encoding="utf-8") as f:
                fallback_features_all = json.load(f)
            pp_low_fallback = {
                "model": fallback_model,
                "features": fallback_features_all["pp"],
                "model_dir": str(fallback_dir),
            }
            logger.info(f"[INN2Router] Loaded PP low-chase fallback from {fallback_dir}")

        if use_calibration:
            logger.info("[INN2Router] Calibration enabled")
        else:
            logger.info("[INN2Router] Calibration disabled — using raw phase probabilities")

        router = cls(models, features, calibrators, use_calibration, pp_low_fallback)
        if phase_ranges:
            router._phase_ranges = {k: tuple(v) for k, v in phase_ranges.items()}
        return router

    # ── phase detection ───────────────────────────────────────────────────────

    def phase_for_over(self, over_1indexed: int) -> str:
        for phase, (lo, hi) in self._phase_ranges.items():
            if lo <= over_1indexed <= hi:
                return phase
        return next(reversed(self._phase_ranges))

    # ── calibration helper ────────────────────────────────────────────────────

    def _calibrate(self, raw: float, phase: str, over_1indexed: int, chase_category: int = 0) -> float:
        """Apply per-cell (over × chase_category) calibrator, falling back to
        per-over, then phase_iso, then raw."""
        cal = self._calibrators.get(phase, {})
        if not cal:
            return raw

        # 0. Try per-cell calibrator (over × chase_category) — used by v17+
        per_cell = cal.get("per_cell", {})
        if per_cell:
            key = (over_1indexed, int(chase_category))
            if key in per_cell:
                return float(per_cell[key].predict([raw])[0])

        # 1. Try per-over calibrator
        per_over = cal.get("per_over", {})
        if per_over and over_1indexed in per_over:
            return float(per_over[over_1indexed].predict([raw])[0])

        # 2. Fall back to phase-level isotonic calibrator
        phase_iso = cal.get("phase_iso")
        if phase_iso is not None:
            return float(phase_iso.predict([raw])[0])

        # 3. Raw
        return raw

    def _model_for_row(self, phase: str, row: pd.DataFrame) -> tuple[Any, list[str], str]:
        """Select the phase model, with v12 raw fallback for PP easy chases."""
        if phase == "pp" and self._pp_low_fallback is not None:
            target_above_par = (
                float(row["target_above_par"].iloc[0])
                if "target_above_par" in row.columns
                else 0.0
            )
            if target_above_par < LOW_CHASE_THRESHOLD:
                return (
                    self._pp_low_fallback["model"],
                    self._pp_low_fallback["features"],
                    "v12_pp_low_raw",
                )

        phase_source = {
            "pp": "v17_pp_raw",
            "mid": "v14_mid_raw",
            "death": "v14_death_raw",
        }.get(phase, f"{phase}_candidate_raw")
        return self._models[phase], self._features[phase], phase_source

    # ── main predict ──────────────────────────────────────────────────────────

    def predict(
        self,
        feature_dict: dict[str, Any],
        over_1indexed: int,
    ) -> tuple[float, str]:
        """
        Produce an inn2 probability for the given match state.

        Parameters
        ----------
        feature_dict : dict
            Full feature dict from RealTimeFeatureMapper (X.iloc[0].to_dict()).
            Additional inn2 features are engineered internally.
        over_1indexed : int
            Current over number (1-indexed, e.g. over=3 means start of over 4).

        Returns
        -------
        (probability, phase_name)

        Raises
        ------
        INN2RouterError
            If any step fails.  Callers should fall back to the v7 result.
        """
        try:
            phase = self.phase_for_over(over_1indexed)

            # Build a 1-row DataFrame from the feature dict
            row = pd.DataFrame([feature_dict])

            # Engineer inn2-specific features (adds momentum, chase labels, etc.)
            row = engineer_inn2_features(row)
            model, feat_names, model_source = self._model_for_row(phase, row)

            # Select features; fill missing with 0
            X = pd.DataFrame(index=row.index)
            for f in feat_names:
                X[f] = row[f] if f in row.columns else 0.0
            X = X.fillna(0.0)

            raw = float(model.predict_proba(X)[0, 1])
            output = raw
            if self._use_calibration and not model_source.startswith("v12_"):
                chase_category = int(row["chase_category"].iloc[0]) if "chase_category" in row.columns else 0
                output = self._calibrate(raw, phase, over_1indexed, chase_category)

            self.last_model_source = model_source
            self.last_raw_probability = raw
            self.last_output_probability = output

            logger.debug(
                f"[INN2Router] inn2 over={over_1indexed} phase={phase} "
                f"source={model_source} raw={raw:.4f} output={output:.4f}"
            )
            return output, phase

        except Exception as exc:
            raise INN2RouterError(f"Inn2PhaseRouter.predict failed: {exc}") from exc
