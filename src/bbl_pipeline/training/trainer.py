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
    
    OPTIMIZATION FINDINGS (December 2025):
    =====================================
    1. CALIBRATION: Isotonic calibration HURTS performance on this dataset.
       - With isotonic calibration: Brier = 0.1854
       - Without calibration: Brier = 0.1795 (BEST)
       - XGBoost with logistic loss already produces well-calibrated probabilities
       
    2. HYPERPARAMETERS: Current config is optimal after extensive grid search:
       - max_depth=2 (shallow trees prevent overfitting)
       - learning_rate=0.01 (slow learning for stability)
       - n_estimators=700 (enough trees for convergence)
       - Heavy regularization (reg_alpha=3.5, reg_lambda=4.5)
       
    3. SAMPLING: End-of-over sampling (23K rows) outperforms full ball-by-ball (143K)
       - Less temporal autocorrelation
       - More meaningful decision points
       
    4. FEATURES: DLS-style resource features dominate (resource_win_prob = 10.6% importance)
       - Additional team/venue features added noise, not signal
       
    5. ENSEMBLE: Blending XGB+LGBM+LogReg achieves 0.1787 but adds complexity
    """
    def __init__(self, use_calibration: bool = False, calibration_method: str = 'isotonic'):
        """
        Args:
            use_calibration: Whether to apply post-hoc calibration. 
                             Default False (best Brier score).
            calibration_method: 'isotonic' or 'sigmoid' (Platt scaling)
        """
        self.use_calibration = use_calibration
        self.calibration_method = calibration_method
        
        # Base XGBoost - optimized for Brier score 0.1795 (5-fold CV, no calibration)
        # These hyperparameters were tuned via grid search on end-of-over sampled data
        xgb_model = XGBClassifier(
            objective='binary:logistic', 
            eval_metric='logloss', 
            n_estimators=700,
            max_depth=2,
            learning_rate=0.01,
            subsample=0.45,
            colsample_bytree=0.45,
            min_child_weight=30,
            reg_alpha=3.5,
            reg_lambda=4.5,
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
        
        self.splitter = TimeSeriesCalibrationSplit(n_splits=5, calibration_size=0.15)

    def evaluate_models(self, X: pd.DataFrame, y: pd.Series) -> List[Dict[str, Any]]:
        """
        Runs time-series cross-validation for all models and returns metrics.
        """
        results = []
        
        for name, model in self.models.items():
            logger.info(f"Evaluating model: {name}")
            fold_briers = []
            
            for i, (train_idx, calib_idx, test_idx) in enumerate(self.splitter.split(X)):
                X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
                
                # Clone to ensure fresh start
                base_model = clone(model)
                
                if self.use_calibration:
                    # Split into train/calib
                    X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
                    X_calib, y_calib = X.iloc[calib_idx], y.iloc[calib_idx]
                    
                    base_model.fit(X_train, y_train)
                    
                    calibrated = CalibratedModel(base_model, method=self.calibration_method)
                    calibrated.fit(X_calib, y_calib)
                    
                    probs = calibrated.predict_proba(X_test)[:, 1]
                else:
                    # No calibration - use all training data
                    all_train_idx = np.concatenate([train_idx, calib_idx])
                    X_train, y_train = X.iloc[all_train_idx], y.iloc[all_train_idx]
                    
                    base_model.fit(X_train, y_train)
                    probs = base_model.predict_proba(X_test)[:, 1]
                
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

    def train_final_model(self, model_name: str, X: pd.DataFrame, y: pd.Series, calibration_size: float = 0.15):
        """
        Trains the final model. If use_calibration=False, trains on full data.
        Returns either a CalibratedModel or the base model.
        """
        if model_name not in self.models:
            raise ValueError(f"Unknown model: {model_name}")
        
        base_model = clone(self.models[model_name])
        
        if self.use_calibration:
            # Split into Train/Calibration
            n_samples = len(X)
            n_calib = int(n_samples * calibration_size)
            
            X_train = X.iloc[:-n_calib]
            y_train = y.iloc[:-n_calib]
            X_calib = X.iloc[-n_calib:]
            y_calib = y.iloc[-n_calib:]
            
            logger.info(f"Training final {model_name} model. Train size: {len(X_train)}, Calib size: {len(X_calib)}")
            
            base_model.fit(X_train, y_train)
            
            calibrated = CalibratedModel(base_model, method=self.calibration_method)
            calibrated.fit(X_calib, y_calib)
            
            return calibrated
        else:
            # No calibration - train on full data
            logger.info(f"Training final {model_name} model (no calibration). Train size: {len(X)}")
            base_model.fit(X, y)
            return base_model

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
