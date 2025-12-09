from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from xgboost import XGBClassifier
from sklearn.metrics import brier_score_loss
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import pandas as pd
import numpy as np
from typing import List, Dict, Any
import structlog

try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

from .evaluation import TimeSeriesCalibrationSplit
from .calibration import CalibratedModel

logger = structlog.get_logger()

class Trainer:
    """
    Orchestrates multi-model training, evaluation, and final model production.
    """
    def __init__(self):
        # Base XGBoost - optimized for Brier score 0.1865 (5-fold CV)
        # Best config from hyperparameter tuning with Platt scaling
        xgb_model = XGBClassifier(
            objective='binary:logistic', 
            eval_metric='logloss', 
            n_estimators=650,
            max_depth=2,
            learning_rate=0.011,
            subsample=0.5,
            colsample_bytree=0.5,
            min_child_weight=28,
            reg_alpha=2.8,
            reg_lambda=3.8,
            tree_method='hist',
            n_jobs=-1
        )
        
        self.models = {
            # XGBoost - high trees, lower lr
            'xgboost': xgb_model,
            # Logistic Regression
            'logreg': Pipeline([
                ('imputer', SimpleImputer(strategy='mean')),
                ('scaler', StandardScaler()),
                ('clf', LogisticRegression(max_iter=1000, C=0.1, solver='lbfgs'))
            ]),
        }
        
        # LightGBM - tuned for calibration
        if HAS_LIGHTGBM:
            lgbm_model = LGBMClassifier(
                objective='binary',
                n_estimators=500,
                max_depth=5,
                learning_rate=0.02,
                num_leaves=31,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_samples=20,
                reg_alpha=0.1,
                reg_lambda=1.0,
                n_jobs=-1,
                verbose=-1
            )
            self.models['lgbm'] = lgbm_model
            
            # Ensemble of XGBoost + LightGBM
            self.models['ensemble'] = VotingClassifier(
                estimators=[
                    ('xgb', clone(xgb_model)),
                    ('lgbm', clone(lgbm_model))
                ],
                voting='soft',
                n_jobs=-1
            )
        
        self.splitter = TimeSeriesCalibrationSplit(n_splits=3)

    def evaluate_models(self, X: pd.DataFrame, y: pd.Series) -> List[Dict[str, Any]]:
        """
        Runs time-series cross-validation for all models and returns metrics.
        """
        results = []
        
        for name, model in self.models.items():
            logger.info(f"Evaluating model: {name}")
            fold_briers = []
            
            for i, (train_idx, calib_idx, test_idx) in enumerate(self.splitter.split(X)):
                X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
                X_calib, y_calib = X.iloc[calib_idx], y.iloc[calib_idx]
                X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
                
                # Clone to ensure fresh start
                base_model = clone(model)
                base_model.fit(X_train, y_train)
                
                calibrated = CalibratedModel(base_model, method='isotonic')
                calibrated.fit(X_calib, y_calib)
                
                probs = calibrated.predict_proba(X_test)[:, 1]
                brier = brier_score_loss(y_test, probs)
                fold_briers.append(brier)
                
                logger.debug(f"Fold {i+1} Brier: {brier:.4f}")
            
            avg_brier = np.mean(fold_briers)
            logger.info(f"Model {name} Average Brier: {avg_brier:.4f}")
            
            results.append({
                'model_name': name,
                'brier_score': avg_brier,
                'base_model_params': model.get_params()
            })
            
        return results

    def train_final_model(self, model_name: str, X: pd.DataFrame, y: pd.Series, calibration_size: float = 0.2) -> CalibratedModel:
        """
        Trains the final model using a Train/Calibration split on the entire dataset.
        """
        if model_name not in self.models:
            raise ValueError(f"Unknown model: {model_name}")
            
        # Split into Train/Calibration (no test set, as we want to use max data)
        # We use the most recent data for calibration
        n_samples = len(X)
        n_calib = int(n_samples * calibration_size)
        
        X_train = X.iloc[:-n_calib]
        y_train = y.iloc[:-n_calib]
        X_calib = X.iloc[-n_calib:]
        y_calib = y.iloc[-n_calib:]
        
        logger.info(f"Training final {model_name} model. Train size: {len(X_train)}, Calib size: {len(X_calib)}")
        
        base_model = clone(self.models[model_name])
        base_model.fit(X_train, y_train)
        
        calibrated = CalibratedModel(base_model, method='isotonic')
        calibrated.fit(X_calib, y_calib)
        
        return calibrated

    def get_feature_importance(self, model_name: str, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """
        Trains a model on the full dataset and extracts feature importance.
        """
        if model_name not in self.models:
            raise ValueError(f"Unknown model: {model_name}")

        model = clone(self.models[model_name])
        model.fit(X, y)
        
        feature_names = X.columns
        importances = []
        
        # Handle Pipeline
        if isinstance(model, Pipeline):
            estimator = model.named_steps['clf']
        else:
            estimator = model
            
        # Extract importance based on model type
        if hasattr(estimator, 'feature_importances_'):
            importances = estimator.feature_importances_
        elif hasattr(estimator, 'coef_'):
            importances = np.abs(estimator.coef_[0])
        else:
            logger.warning(f"Model {model_name} does not support feature importance extraction.")
            return pd.DataFrame()
            
        df_imp = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)
        
        return df_imp
