from sklearn.calibration import CalibratedClassifierCV
from sklearn.base import BaseEstimator, ClassifierMixin
from typing import Literal

class CalibratedModel(BaseEstimator, ClassifierMixin):
    """
    Wrapper for probability calibration using Isotonic Regression or Platt Scaling.
    Assumes the base estimator is already fitted.
    """
    def __init__(self, base_estimator, method: Literal['isotonic', 'sigmoid'] = 'isotonic'):
        self.base_estimator = base_estimator
        self.method = method
        self.calibrator = None

    def fit(self, X, y):
        """
        Fit the calibrator on the validation/calibration set.
        X, y should be the calibration set, NOT the training set used for base_estimator.
        """
        self.calibrator = CalibratedClassifierCV(
            estimator=self.base_estimator,
            method=self.method,
            cv="prefit"
        )
        self.calibrator.fit(X, y)
        return self

    def predict(self, X):
        if self.calibrator is None:
            raise RuntimeError("Model not calibrated. Call fit() first.")
        return self.calibrator.predict(X)

    def predict_proba(self, X):
        if self.calibrator is None:
            raise RuntimeError("Model not calibrated. Call fit() first.")
        return self.calibrator.predict_proba(X)
