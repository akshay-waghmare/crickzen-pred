"""
Inn2PhaseRouter — routes inn2 predictions to phase-specific models.

Architecture (ipl_v11):
  Inn1: global v7 model  (unchanged)
  Inn2 PP    (overs 1–6):  champion_model_pp.joblib
  Inn2 Mid   (overs 7–15): champion_model_mid.joblib
  Inn2 Death (overs 16–20):champion_model_death.joblib

Each phase model uses engineered inn2 features (chase labels, momentum, etc.)
with per-over isotonic calibrators as the primary calibration path,
falling back to phase-level isotonic, then raw if neither is available.

Usage:
    router = Inn2PhaseRouter.load("models/ipl_inn2_v1")
    prob, phase = router.predict(feature_dict, over_1indexed=8)
    # Returns (calibrated_probability, "mid") or raises on total failure

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
import numpy as np
import pandas as pd

from bbl_pipeline.features.inn2_engineering import engineer_inn2_features, get_feature_sets

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
    """Routes inn2 predictions to PP / Mid / Death phase models with calibration."""

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
        calibrators: dict,     # {phase: {"per_over": {over: iso}, "phase_iso": iso}}
    ):
        self._models     = models
        self._features   = features
        self._calibrators = calibrators

    # ── factory ──────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, model_dir: str | Path) -> "Inn2PhaseRouter":
        """Load phase models, feature lists, and calibrators from model_dir."""
        model_dir = Path(model_dir)

        # Phase models
        models = {}
        for phase in ("pp", "mid", "death"):
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
        if cal_path.exists():
            with open(cal_path, "rb") as f:
                calibrators = pickle.load(f)
            logger.info(f"[INN2Router] Loaded calibrators from {cal_path}")
        else:
            calibrators = {}
            logger.warning("[INN2Router] phase_oof_calibrators.pkl not found — using raw probabilities")

        return cls(models, features, calibrators)

    # ── phase detection ───────────────────────────────────────────────────────

    @staticmethod
    def phase_for_over(over_1indexed: int) -> str:
        if over_1indexed <= 6:
            return "pp"
        elif over_1indexed <= 15:
            return "mid"
        else:
            return "death"

    # ── calibration helper ────────────────────────────────────────────────────

    def _calibrate(self, raw: float, phase: str, over_1indexed: int) -> float:
        """Apply per-over calibrator, falling back to phase_iso, then raw."""
        cal = self._calibrators.get(phase, {})
        if not cal:
            return raw

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

    # ── main predict ──────────────────────────────────────────────────────────

    def predict(
        self,
        feature_dict: dict[str, Any],
        over_1indexed: int,
    ) -> tuple[float, str]:
        """
        Produce a calibrated inn2 probability for the given match state.

        Parameters
        ----------
        feature_dict : dict
            Full feature dict from RealTimeFeatureMapper (X.iloc[0].to_dict()).
            Additional inn2 features are engineered internally.
        over_1indexed : int
            Current over number (1-indexed, e.g. over=3 means start of over 4).

        Returns
        -------
        (calibrated_probability, phase_name)

        Raises
        ------
        INN2RouterError
            If any step fails.  Callers should fall back to the v7 result.
        """
        try:
            phase = self.phase_for_over(over_1indexed)
            model = self._models[phase]
            feat_names = self._features[phase]

            # Build a 1-row DataFrame from the feature dict
            row = pd.DataFrame([feature_dict])

            # Engineer inn2-specific features (adds momentum, chase labels, etc.)
            row = engineer_inn2_features(row)

            # Select features; fill missing with 0
            X = pd.DataFrame(index=row.index)
            for f in feat_names:
                X[f] = row[f] if f in row.columns else 0.0
            X = X.fillna(0.0)

            raw = float(model.predict_proba(X)[0, 1])
            calibrated = self._calibrate(raw, phase, over_1indexed)

            logger.debug(
                f"[INN2Router] inn2 over={over_1indexed} phase={phase} "
                f"raw={raw:.4f} cal={calibrated:.4f}"
            )
            return calibrated, phase

        except Exception as exc:
            raise INN2RouterError(f"Inn2PhaseRouter.predict failed: {exc}") from exc
