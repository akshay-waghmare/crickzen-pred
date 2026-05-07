from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.base import BaseEstimator, ClassifierMixin
from scipy.special import logit
from typing import Literal
import numpy as np


class PlattCalibrator:
    """Logistic regression in logit space (Platt scaling) for post-hoc probability calibration.

    Operates on raw probabilities, not on model inputs — the API matches
    ``IsotonicRegression``: call ``.transform(raw_probs)`` to get calibrated probs.

    This is the production calibrator used for MID-phase predictions in IPL v12.
    It preserves prediction spread better than isotonic when the calibration
    dataset is small (< ~5,000 samples per phase).

    Usage::

        cal = PlattCalibrator()
        cal.fit(oof_raw_probs, oof_labels)
        calibrated = cal.transform(new_raw_probs)
    """

    def __init__(self, C: float = 1.0):
        self.C = C
        self._eps = 1e-6
        self._lr: LogisticRegression | None = None

    def fit(self, raw: np.ndarray, y: np.ndarray) -> "PlattCalibrator":
        X = logit(np.clip(raw, self._eps, 1 - self._eps)).reshape(-1, 1)
        self._lr = LogisticRegression(C=self.C, max_iter=2000, random_state=42)
        self._lr.fit(X, y.astype(int))
        return self

    def transform(self, raw: np.ndarray) -> np.ndarray:
        if self._lr is None:
            raise RuntimeError("PlattCalibrator not fitted — call .fit() first.")
        X = logit(np.clip(raw, self._eps, 1 - self._eps)).reshape(-1, 1)
        return self._lr.predict_proba(X)[:, 1]

    # sklearn-style alias so the object works as a drop-in for IsotonicRegression
    def predict(self, raw: np.ndarray) -> np.ndarray:
        return self.transform(raw)

class CalibratedModel(BaseEstimator, ClassifierMixin):
    """
    Wrapper for probability calibration using Isotonic Regression or Platt Scaling.
    Assumes the base estimator is already fitted.
    
    Uses manual calibration to avoid sklearn's classifier detection issues.
    """
    def __init__(self, base_estimator, method: Literal['isotonic', 'sigmoid'] = 'isotonic'):
        self.base_estimator = base_estimator
        self.method = method
        self.calibrator = None
        self.classes_ = np.array([0, 1])

    def fit(self, X, y):
        """
        Fit the calibrator on the validation/calibration set.
        X, y should be the calibration set, NOT the training set used for base_estimator.
        """
        # Get uncalibrated probabilities from base estimator
        uncalibrated_probs = self.base_estimator.predict_proba(X)[:, 1]
        
        if self.method == 'isotonic':
            # Isotonic regression for calibration
            self.calibrator = IsotonicRegression(out_of_bounds='clip')
            self.calibrator.fit(uncalibrated_probs, y)
        else:
            # Platt scaling (sigmoid)
            self.calibrator = LogisticRegression(C=1e10, solver='lbfgs', max_iter=1000)
            self.calibrator.fit(uncalibrated_probs.reshape(-1, 1), y)
        
        return self

    def predict(self, X):
        if self.calibrator is None:
            raise RuntimeError("Model not calibrated. Call fit() first.")
        probs = self.predict_proba(X)[:, 1]
        return (probs >= 0.5).astype(int)

    def predict_proba(self, X):
        if self.calibrator is None:
            raise RuntimeError("Model not calibrated. Call fit() first.")
        
        # Get uncalibrated probabilities
        uncalibrated_probs = self.base_estimator.predict_proba(X)[:, 1]
        
        if self.method == 'isotonic':
            calibrated_probs = self.calibrator.predict(uncalibrated_probs)
        else:
            calibrated_probs = self.calibrator.predict_proba(uncalibrated_probs.reshape(-1, 1))[:, 1]
        
        # Clip to valid probability range
        calibrated_probs = np.clip(calibrated_probs, 0, 1)
        
        return np.column_stack([1 - calibrated_probs, calibrated_probs])
