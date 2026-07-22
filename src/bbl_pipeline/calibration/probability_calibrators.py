"""Small serializable probability calibrators used by inference."""

import numpy as np


class BetaCalibrator:
    """Apply beta calibration to scalar or vector probabilities."""

    def __init__(self, coefficients, intercept):
        self.coefficients = np.asarray(coefficients, dtype=float)
        self.intercept = float(intercept)

    def predict(self, probabilities):
        p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1.0 - 1e-6)
        logits = (
            self.intercept
            + self.coefficients[0] * np.log(p)
            + self.coefficients[1] * np.log1p(-p)
        )
        return 1.0 / (1.0 + np.exp(-np.clip(logits, -40.0, 40.0)))
