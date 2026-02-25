"""
Monte Carlo Platt-scaling calibrator.

Fits a logistic regression on ``logit(mc_raw_prob)`` to produce
betting-grade calibrated win probabilities from MC simulation output.

Usage:
    from bbl_pipeline.calibration.mc_calibrator import MCCalibrator

    cal = MCCalibrator()
    cal.fit(mc_probs, actual_outcomes)
    calibrated = cal.calibrate(0.65)
    cal.save("models/t20_male_v2/mc_calibrator.pkl")
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss


_CLIP_LO = 0.001
_CLIP_HI = 0.999


def _safe_logit(p: np.ndarray) -> np.ndarray:
    """Compute logit with clipping to avoid ±inf."""
    p = np.clip(p, _CLIP_LO, _CLIP_HI)
    return np.log(p / (1.0 - p))


@dataclass
class MCCalibrator:
    """Platt-scaling calibrator for Monte Carlo win probabilities.

    Wraps a 1-feature ``LogisticRegression`` on ``logit(mc_prob)``
    to correct systematic MC biases (over-/under-confidence by phase).

    Attributes
    ----------
    model : LogisticRegression | None
        Fitted sklearn model (``None`` before ``fit()``).
    training_samples : int
        Number of samples the calibrator was trained on.
    training_brier : float
        Brier score on the training set.
    training_log_loss : float
        Log loss on the training set.
    fitted_date : str
        ISO-8601 timestamp of the last ``fit()`` call.
    """

    model: Optional[LogisticRegression] = field(default=None, repr=False)
    training_samples: int = 0
    training_brier: float = 0.0
    training_log_loss: float = 0.0
    fitted_date: str = ""

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    def fit(
        self,
        mc_probs: np.ndarray,
        actual_outcomes: np.ndarray,
    ) -> "MCCalibrator":
        """Fit Platt scaling on MC predictions vs actual outcomes.

        Parameters
        ----------
        mc_probs : np.ndarray
            Raw MC win probabilities (0–1), shape ``(n,)``.
        actual_outcomes : np.ndarray
            Binary outcomes (0 or 1), shape ``(n,)``.

        Returns
        -------
        MCCalibrator
            ``self`` for chaining.
        """
        mc_probs = np.asarray(mc_probs, dtype=np.float64)
        actual_outcomes = np.asarray(actual_outcomes, dtype=np.float64)

        if len(mc_probs) != len(actual_outcomes):
            raise ValueError(
                f"Length mismatch: mc_probs={len(mc_probs)}, "
                f"actual_outcomes={len(actual_outcomes)}"
            )

        X = _safe_logit(mc_probs).reshape(-1, 1)
        y = actual_outcomes

        lr = LogisticRegression(
            solver="lbfgs",
            max_iter=1000,
            C=1e10,  # no regularisation — pure Platt scaling
        )
        lr.fit(X, y)

        self.model = lr
        self.training_samples = len(mc_probs)

        # In-sample metrics
        fitted_probs = self.calibrate_batch(mc_probs)
        self.training_brier = float(brier_score_loss(y, fitted_probs))
        self.training_log_loss = float(log_loss(y, fitted_probs))
        self.fitted_date = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return self

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def calibrate(self, mc_raw_prob: float) -> float:
        """Calibrate a single MC probability.

        Parameters
        ----------
        mc_raw_prob : float
            Raw MC win probability (0–1).

        Returns
        -------
        float
            Calibrated probability.
        """
        if self.model is None:
            raise RuntimeError("MCCalibrator has not been fitted yet")

        x = _safe_logit(np.array([mc_raw_prob])).reshape(1, -1)
        return float(self.model.predict_proba(x)[0, 1])

    def calibrate_batch(self, mc_raw_probs: np.ndarray) -> np.ndarray:
        """Calibrate an array of MC probabilities (vectorised).

        Parameters
        ----------
        mc_raw_probs : np.ndarray
            Raw MC win probabilities, shape ``(n,)``.

        Returns
        -------
        np.ndarray
            Calibrated probabilities, shape ``(n,)``.
        """
        if self.model is None:
            raise RuntimeError("MCCalibrator has not been fitted yet")

        mc_raw_probs = np.asarray(mc_raw_probs, dtype=np.float64)
        X = _safe_logit(mc_raw_probs).reshape(-1, 1)
        return self.model.predict_proba(X)[:, 1]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Serialise calibrator to disk via joblib.

        Parameters
        ----------
        path : str
            Output file path (e.g. ``models/v2/mc_calibrator.pkl``).
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "MCCalibrator":
        """Deserialise a saved calibrator.

        Parameters
        ----------
        path : str
            Path to a ``.pkl`` file written by :meth:`save`.

        Returns
        -------
        MCCalibrator
        """
        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(
                f"Expected MCCalibrator, got {type(obj).__name__}"
            )
        return obj

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a one-line summary of training metrics."""
        return (
            f"MCCalibrator(samples={self.training_samples}, "
            f"brier={self.training_brier:.4f}, "
            f"log_loss={self.training_log_loss:.4f}, "
            f"fitted={self.fitted_date})"
        )


@dataclass
class InningsMCCalibrators:
    """Container for innings-specific MC Platt calibrators.

    Holds separate ``MCCalibrator`` instances for innings 1 and innings 2
    so each innings can have its own bias-correction mapping.

    Attributes
    ----------
    inn1 : MCCalibrator | None
        Calibrator for innings 1 (batting-first).
    inn2 : MCCalibrator | None
        Calibrator for innings 2 (chasing).
    """

    inn1: Optional[MCCalibrator] = None
    inn2: Optional[MCCalibrator] = None

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def get(self, innings: int) -> Optional[MCCalibrator]:
        """Return the calibrator for the given innings (1 or 2)."""
        if innings == 1:
            return self.inn1
        return self.inn2

    def calibrate(self, mc_raw_prob: float, innings: int) -> float:
        """Calibrate a single MC probability using the innings-specific calibrator.

        Falls back to returning the raw probability if no calibrator exists
        for the given innings.
        """
        cal = self.get(innings)
        if cal is None or cal.model is None:
            return mc_raw_prob
        return cal.calibrate(mc_raw_prob)

    def calibrate_batch(self, mc_raw_probs: np.ndarray, innings: int) -> np.ndarray:
        """Calibrate an array of MC probabilities for a specific innings.

        Falls back to returning raw probabilities if no calibrator exists.
        """
        cal = self.get(innings)
        if cal is None or cal.model is None:
            return mc_raw_probs
        return cal.calibrate_batch(mc_raw_probs)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Serialise both calibrators to disk via joblib."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "InningsMCCalibrators":
        """Deserialise a saved innings-specific calibrator pair."""
        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(
                f"Expected InningsMCCalibrators, got {type(obj).__name__}"
            )
        return obj

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a multi-line summary of both calibrators."""
        parts = ["InningsMCCalibrators:"]
        if self.inn1 and self.inn1.model is not None:
            parts.append(f"  Inn1: {self.inn1.summary()}")
        else:
            parts.append("  Inn1: (none)")
        if self.inn2 and self.inn2.model is not None:
            parts.append(f"  Inn2: {self.inn2.summary()}")
        else:
            parts.append("  Inn2: (none)")
        return "\n".join(parts)


# Phase names used as keys
PHASE_PP = "pp"
PHASE_MID = "mid"
PHASE_DEATH = "death"
VALID_PHASES = {PHASE_PP, PHASE_MID, PHASE_DEATH}


def over_to_phase(over: int) -> str:
    """Map a 0-indexed over number to a phase key.

    Parameters
    ----------
    over : int
        Over number (0-indexed: 0 = first over, 19 = last over of T20).

    Returns
    -------
    str
        One of ``'pp'``, ``'mid'``, ``'death'``.
    """
    if over < 6:
        return PHASE_PP
    if over < 15:
        return PHASE_MID
    return PHASE_DEATH


@dataclass
class InningsPhaseCalibrators:
    """Container for innings × phase MC Platt calibrators (6 total).

    Holds separate ``MCCalibrator`` instances for each combination of
    innings (1, 2) and phase (pp, mid, death).

    Keys follow the pattern ``inn{1,2}_{pp,mid,death}``.
    """

    calibrators: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Access helpers
    # ------------------------------------------------------------------

    def _key(self, innings: int, phase: str) -> str:
        return f"inn{innings}_{phase}"

    def set(self, innings: int, phase: str, cal: MCCalibrator) -> None:
        """Store a calibrator for a given innings + phase."""
        if phase not in VALID_PHASES:
            raise ValueError(f"Invalid phase '{phase}'. Must be one of {VALID_PHASES}")
        self.calibrators[self._key(innings, phase)] = cal

    def get(self, innings: int, phase: str) -> Optional[MCCalibrator]:
        """Return the calibrator for the given innings + phase, or ``None``."""
        return self.calibrators.get(self._key(innings, phase))

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def calibrate(self, mc_raw_prob: float, innings: int, phase: str) -> float:
        """Calibrate a single MC probability using innings × phase calibrator.

        Falls back to raw probability if no calibrator is available.
        """
        cal = self.get(innings, phase)
        if cal is None or cal.model is None:
            return mc_raw_prob
        return cal.calibrate(mc_raw_prob)

    def calibrate_batch(
        self, mc_raw_probs: np.ndarray, innings: int, phase: str
    ) -> np.ndarray:
        """Calibrate an array of MC probabilities for a specific innings + phase."""
        cal = self.get(innings, phase)
        if cal is None or cal.model is None:
            return mc_raw_probs
        return cal.calibrate_batch(mc_raw_probs)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Serialise all calibrators to disk via joblib."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "InningsPhaseCalibrators":
        """Deserialise a saved innings × phase calibrator set."""
        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(
                f"Expected InningsPhaseCalibrators, got {type(obj).__name__}"
            )
        return obj

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a multi-line summary of all 6 calibrators."""
        parts = ["InningsPhaseCalibrators:"]
        for innings in [1, 2]:
            for phase in [PHASE_PP, PHASE_MID, PHASE_DEATH]:
                key = self._key(innings, phase)
                cal = self.calibrators.get(key)
                if cal and cal.model is not None:
                    parts.append(f"  {key}: {cal.summary()}")
                else:
                    parts.append(f"  {key}: (none)")
        return "\n".join(parts)
