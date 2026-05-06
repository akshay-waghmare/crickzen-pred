"""
XGBLRBlend: 50/50 XGBoost + LogisticRegression ensemble.

Package-level definition so joblib serialization uses a stable
``bbl_pipeline.training.blend_model.XGBLRBlend`` class path rather than
``__main__.XGBLRBlend``, which breaks deserialization outside the training
script.
"""

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


class XGBLRBlend:
    """50% XGBoost + 50% LogisticRegression ensemble model."""

    XGB_PARAMS = dict(
        n_estimators=400, max_depth=5, learning_rate=0.02,
        subsample=0.8, colsample_bytree=0.9, min_child_weight=10,
        reg_alpha=0.5, reg_lambda=1.5, tree_method="hist",
        eval_metric="logloss", n_jobs=-1, verbosity=0, random_state=42,
    )

    def __init__(self, xgb_params=None, lr_c=0.01):
        params = {**self.XGB_PARAMS, **(xgb_params or {})}
        self.xgb = XGBClassifier(**params)
        self.lr = Pipeline([
            ("imp", SimpleImputer(strategy="mean")),
            ("sc",  StandardScaler()),
            ("clf", LogisticRegression(C=lr_c, max_iter=1000, random_state=42)),
        ])

    def fit(self, X, y, sample_weight=None):
        sw = {"sample_weight": sample_weight} if sample_weight is not None else {}
        sw_lr = {"clf__sample_weight": sample_weight} if sample_weight is not None else {}
        self.xgb.fit(X, y, **sw)
        self.lr.fit(X, y, **sw_lr)
        return self

    def predict_proba(self, X):
        p_xgb = self.xgb.predict_proba(X)[:, 1]
        p_lr  = self.lr.predict_proba(X)[:, 1]
        blend = 0.5 * p_xgb + 0.5 * p_lr
        return np.column_stack([1 - blend, blend])

    def feature_importance(self, cols):
        return pd.DataFrame({
            "feature":    cols,
            "importance": self.xgb.feature_importances_,
        }).sort_values("importance", ascending=False)
