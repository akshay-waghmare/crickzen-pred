from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from xgboost import XGBClassifier
from sklearn.metrics import brier_score_loss
from sklearn.base import clone, BaseEstimator, ClassifierMixin
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import structlog

try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

from .evaluation import TimeSeriesCalibrationSplit
from .calibration import CalibratedModel

logger = structlog.get_logger()


class XGBLogRegEnsemble(BaseEstimator, ClassifierMixin):
    """
    Best performing ensemble model: XGBoost + LogisticRegression blend.
    
    Achieves Brier Score 0.1777 (5-fold Time Series CV) through:
    1. Feature selection: Uses top 25 features by XGBoost importance
    2. Model blending: 50% XGBoost + 50% LogisticRegression
    
    This outperforms:
    - XGBoost alone (0.1795)
    - Neural networks (best MLP: 0.1838)
    - Other ensemble configurations
    """
    
    # Top 25 features by importance (determined empirically on training data)
    TOP_FEATURES = [
        'expected_final_score', 'resource_win_prob', 'score_vs_par', 
        'dls_pressure_index', 'projected_vs_venue_avg', 'projected_score',
        'is_powerplay', 'score_per_wicket', 'run_rate_diff', 'required_run_rate',
        'chase_difficulty', 'wickets_times_balls', 'pressure_index', 
        'team_strength_diff', 'rrr_times_wickets', 'overs_remaining',
        'batting_team_win_rate', 'bowling_team_win_rate', 'batting_team_situation_wr',
        'situation_advantage', 'boundary_pct_last_18', 'bowling_team_situation_wr',
        'runs_last_12', 'runs_last_18', 'wickets_last_12',
        # Inn1 carryover features (bridge innings transition)
        'inn1_defendability', 'target_above_par',
    ]
    
    def __init__(
        self,
        xgb_weight: float = 0.5,
        n_features: int = 27,
        xgb_params: Optional[Dict[str, Any]] = None,
        logreg_c: float = 0.01,
    ):
        """
        Args:
            xgb_weight: Weight for XGBoost predictions (1 - xgb_weight for LogReg)
            n_features: Number of top features to use (max 25)
        """
        self.xgb_weight = xgb_weight
        self.n_features = min(n_features, len(self.TOP_FEATURES))
        self.xgb_params = xgb_params
        self.logreg_c = logreg_c
        self.selected_features_ = None
        self.xgb_model_ = None
        self.logreg_model_ = None
        self.classes_ = np.array([0, 1])
        
    def fit(self, X: pd.DataFrame, y: pd.Series):
        """Fit both XGBoost and LogisticRegression models."""
        # Select features that exist in the data
        available_features = [f for f in self.TOP_FEATURES[:self.n_features] if f in X.columns]
        
        if len(available_features) < 10:
            # Fallback: use all features if not enough top features available
            logger.warning(f"Only {len(available_features)} top features available, using all features")
            self.selected_features_ = X.columns.tolist()
        else:
            self.selected_features_ = available_features
            
        X_selected = X[self.selected_features_]
        
        default_xgb_params = {
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'n_estimators': 400,
            'max_depth': 5,  # Deeper trees for more feature interactions
            'learning_rate': 0.02,
            'subsample': 0.8,
            'colsample_bytree': 0.9,  # Use most features per tree
            'min_child_weight': 10,  # Allow more splits
            'reg_alpha': 0.5,  # Less regularization = more feature usage
            'reg_lambda': 1.5,
            'tree_method': 'hist',
            'n_jobs': -1,
            'verbosity': 0,
            'random_state': 42,
        }
        if self.xgb_params:
            default_xgb_params.update(self.xgb_params)

        self.xgb_model_ = XGBClassifier(**default_xgb_params)
        
        # LogisticRegression model with scaling
        self.logreg_model_ = Pipeline([
            ('imputer', SimpleImputer(strategy='mean')),
            ('scaler', StandardScaler()),
            ('clf', LogisticRegression(C=self.logreg_c, max_iter=1000, random_state=42))
        ])
        
        # Fit both models
        self.xgb_model_.fit(X_selected, y)
        self.logreg_model_.fit(X_selected, y)
        
        logger.info(f"Trained XGBLogRegEnsemble with {len(self.selected_features_)} features")
        
        return self
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict class probabilities using weighted blend."""
        X_selected = X[self.selected_features_]
        
        probs_xgb = self.xgb_model_.predict_proba(X_selected)[:, 1]
        probs_lr = self.logreg_model_.predict_proba(X_selected)[:, 1]
        
        # Weighted blend
        blended = self.xgb_weight * probs_xgb + (1 - self.xgb_weight) * probs_lr
        
        return np.column_stack([1 - blended, blended])
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict class labels."""
        probs = self.predict_proba(X)[:, 1]
        return (probs >= 0.5).astype(int)
    
    def get_params(self, deep: bool = True) -> dict:
        """Get parameters for this estimator."""
        return {
            'xgb_weight': self.xgb_weight,
            'n_features': self.n_features
            ,
            'xgb_params': self.xgb_params,
            'logreg_c': self.logreg_c,
        }
    
    def set_params(self, **params):
        """Set parameters for this estimator."""
        for key, value in params.items():
            setattr(self, key, value)
        return self
    
    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importances from XGBoost component."""
        if self.xgb_model_ is None:
            raise ValueError("Model not fitted yet")
            
        return pd.DataFrame({
            'feature': self.selected_features_,
            'importance': self.xgb_model_.feature_importances_
        }).sort_values('importance', ascending=False)


class Trainer:
    """
    Orchestrates model training, evaluation, and final model production.
    
    BEST MODEL: XGBLogRegEnsemble (Brier Score 0.1777)
    ==================================================
    - XGBoost (50%) + LogisticRegression (50%) blend
    - Uses top 25 features by importance
    - No post-hoc calibration by default (hurts performance)
    
    OPTIMIZATION FINDINGS (December 2025):
    =====================================
    1. CALIBRATION: Post-hoc calibration did not improve Brier in experiments.
       
    2. ENSEMBLE: XGB + LogReg blend outperforms single models
       - XGBoost alone: 0.1795
       - Neural networks (MLP): 0.1838 (worse)
       - XGB + LogReg blend: 0.1777 (BEST)
       
    3. FEATURES: Top 25 features by importance beat using all 45
       - resource_win_prob, expected_final_score, dls_pressure_index dominate
       
    4. SAMPLING: End-of-over sampling (23K rows) > full ball-by-ball (143K)
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

        # Primary model: XGBLogRegEnsemble (Brier 0.1777)
        self.models = {
            'ensemble': XGBLogRegEnsemble(xgb_weight=0.5, n_features=27),
        }
        
        self.splitter = TimeSeriesCalibrationSplit(n_splits=5, calibration_size=0.30)

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

    def train_final_model(self, model_name: str, X: pd.DataFrame, y: pd.Series, calibration_size: float = 0.30):
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
        
        # Handle XGBLogRegEnsemble
        if isinstance(model, XGBLogRegEnsemble):
            return model.get_feature_importance()
        
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
