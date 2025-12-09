"""Hyperparameter tuning script for BBL prediction model."""
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import TimeSeriesSplit
import warnings
warnings.filterwarnings('ignore')

# Load data
df = pd.read_parquet('data/training_sampled.parquet')
X = df.drop('is_winner', axis=1)
y = df['is_winner']

print(f"Data: {len(X)} samples, {len(X.columns)} features")
print("="*60)

# 5-fold time series CV
tscv = TimeSeriesSplit(n_splits=5)

def evaluate_model(model, calib_method='sigmoid'):
    """Evaluate model with 5-fold time-series CV and calibration."""
    fold_scores = []
    for train_idx, test_idx in tscv.split(X):
        # Split train into train + calibration (80/20)
        train_size = int(len(train_idx) * 0.8)
        train_idx_actual = train_idx[:train_size]
        calib_idx = train_idx[train_size:]
        
        X_train, y_train = X.iloc[train_idx_actual], y.iloc[train_idx_actual]
        X_calib, y_calib = X.iloc[calib_idx], y.iloc[calib_idx]
        X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
        
        # Train base model
        model_clone = model.__class__(**model.get_params())
        model_clone.fit(X_train, y_train)
        
        # Calibrate with Platt scaling (sigmoid) - more robust for smaller datasets
        calibrator = CalibratedClassifierCV(model_clone, method=calib_method, cv='prefit')
        calibrator.fit(X_calib, y_calib)
        
        # Predict
        y_prob = calibrator.predict_proba(X_test)[:, 1]
        brier = brier_score_loss(y_test, y_prob)
        fold_scores.append(brier)
    
    return np.mean(fold_scores), np.std(fold_scores)

# Test configurations with heavy regularization to prevent overfitting
print("\n1. XGBoost Configurations (with Platt scaling):")
print("-"*60)

xgb_configs = [
    # (n_estimators, max_depth, learning_rate, subsample, min_child_weight, reg_alpha, reg_lambda)
    (500, 3, 0.015, 0.5, 20, 2.0, 3.0),
    (600, 3, 0.012, 0.5, 25, 2.5, 3.5),
    (700, 2, 0.010, 0.5, 30, 3.0, 4.0),
    (400, 4, 0.020, 0.6, 15, 1.5, 2.5),
    (500, 2, 0.015, 0.4, 35, 3.5, 4.5),  # Very regularized
    (800, 2, 0.008, 0.4, 40, 4.0, 5.0),  # Very regularized
]

best_xgb_score = 1.0
best_xgb_config = None

for n, d, lr, ss, mcw, ra, rl in xgb_configs:
    model = XGBClassifier(
        n_estimators=n, max_depth=d, learning_rate=lr,
        subsample=ss, colsample_bytree=ss, min_child_weight=mcw,
        reg_alpha=ra, reg_lambda=rl, random_state=42
    )
    mean_brier, std_brier = evaluate_model(model, 'sigmoid')
    print(f"n={n:3d}, d={d}, lr={lr:.3f}, mcw={mcw:2d}, ra={ra:.1f}: {mean_brier:.4f} (+/- {std_brier:.4f})")
    
    if mean_brier < best_xgb_score:
        best_xgb_score = mean_brier
        best_xgb_config = (n, d, lr, ss, mcw, ra, rl)

print(f"\nBest XGBoost: {best_xgb_score:.4f}")

# Test LightGBM
print("\n2. LightGBM Configurations (with Platt scaling):")
print("-"*60)

lgbm_configs = [
    # (n_estimators, max_depth, learning_rate, subsample, min_child_samples, reg_alpha, reg_lambda)
    (500, 3, 0.015, 0.5, 30, 2.0, 3.0),
    (600, 3, 0.012, 0.5, 40, 2.5, 3.5),
    (700, 2, 0.010, 0.5, 50, 3.0, 4.0),
    (400, 4, 0.020, 0.6, 25, 1.5, 2.5),
]

best_lgbm_score = 1.0

for n, d, lr, ss, mcs, ra, rl in lgbm_configs:
    model = LGBMClassifier(
        n_estimators=n, max_depth=d, learning_rate=lr,
        subsample=ss, colsample_bytree=ss, min_child_samples=mcs,
        reg_alpha=ra, reg_lambda=rl, verbose=-1, random_state=42
    )
    mean_brier, std_brier = evaluate_model(model, 'sigmoid')
    print(f"n={n:3d}, d={d}, lr={lr:.3f}, mcs={mcs:2d}, ra={ra:.1f}: {mean_brier:.4f} (+/- {std_brier:.4f})")
    
    if mean_brier < best_lgbm_score:
        best_lgbm_score = mean_brier

print(f"\nBest LightGBM: {best_lgbm_score:.4f}")

# Test isotonic vs sigmoid calibration on best config
print("\n3. Calibration Method Comparison (Best XGBoost config):")
print("-"*60)

if best_xgb_config:
    n, d, lr, ss, mcw, ra, rl = best_xgb_config
    model = XGBClassifier(
        n_estimators=n, max_depth=d, learning_rate=lr,
        subsample=ss, colsample_bytree=ss, min_child_weight=mcw,
        reg_alpha=ra, reg_lambda=rl, random_state=42
    )
    
    for method in ['sigmoid', 'isotonic']:
        mean_brier, std_brier = evaluate_model(model, method)
        print(f"{method:10s}: {mean_brier:.4f} (+/- {std_brier:.4f})")

print("\n" + "="*60)
print(f"BEST OVERALL: {min(best_xgb_score, best_lgbm_score):.4f}")
