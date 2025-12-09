"""Try alternative strategies to push below 0.18."""
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
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
print("=" * 60)

tscv = TimeSeriesSplit(n_splits=5)

def evaluate_with_config(model_config, calib_split=0.2, calib_method='sigmoid'):
    fold_scores = []
    for train_idx, test_idx in tscv.split(X):
        train_size = int(len(train_idx) * (1 - calib_split))
        train_idx_actual = train_idx[:train_size]
        calib_idx = train_idx[train_size:]
        
        X_train, y_train = X.iloc[train_idx_actual], y.iloc[train_idx_actual]
        X_calib, y_calib = X.iloc[calib_idx], y.iloc[calib_idx]
        X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
        
        model = XGBClassifier(**model_config, random_state=42)
        model.fit(X_train, y_train)
        
        calibrator = CalibratedClassifierCV(model, method=calib_method, cv='prefit')
        calibrator.fit(X_calib, y_calib)
        
        y_prob = calibrator.predict_proba(X_test)[:, 1]
        fold_scores.append(brier_score_loss(y_test, y_prob))
    
    return np.mean(fold_scores), np.std(fold_scores)

# Strategy 1: Try different calibration splits
print("\n1. Varying calibration split size:")
print("-" * 60)
best_config = {
    'n_estimators': 650, 'max_depth': 2, 'learning_rate': 0.011,
    'subsample': 0.5, 'colsample_bytree': 0.5, 'min_child_weight': 28,
    'reg_alpha': 2.8, 'reg_lambda': 3.8
}

for calib_split in [0.15, 0.20, 0.25, 0.30]:
    mean, std = evaluate_with_config(best_config, calib_split, 'sigmoid')
    print(f"  Calib split {calib_split:.0%}: {mean:.4f} (+/- {std:.4f})")

# Strategy 2: Deeper ensemble averaging
print("\n2. Ensemble of multiple XGBoost models:")
print("-" * 60)

# Different random seeds for diversity
seeds = [42, 123, 456, 789, 2024]
ensemble_scores = []

for train_idx, test_idx in tscv.split(X):
    train_size = int(len(train_idx) * 0.8)
    train_idx_actual = train_idx[:train_size]
    calib_idx = train_idx[train_size:]
    
    X_train, y_train = X.iloc[train_idx_actual], y.iloc[train_idx_actual]
    X_calib, y_calib = X.iloc[calib_idx], y.iloc[calib_idx]
    X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
    
    ensemble_probs = []
    for seed in seeds:
        config = {**best_config, 'random_state': seed}
        model = XGBClassifier(**config)
        model.fit(X_train, y_train)
        
        calibrator = CalibratedClassifierCV(model, method='sigmoid', cv='prefit')
        calibrator.fit(X_calib, y_calib)
        
        ensemble_probs.append(calibrator.predict_proba(X_test)[:, 1])
    
    # Average predictions
    avg_probs = np.mean(ensemble_probs, axis=0)
    ensemble_scores.append(brier_score_loss(y_test, avg_probs))

print(f"  5-seed ensemble: {np.mean(ensemble_scores):.4f} (+/- {np.std(ensemble_scores):.4f})")

# Strategy 3: Try slightly different hyperparams
print("\n3. Alternative hyperparameter combinations:")
print("-" * 60)

alt_configs = [
    # Slower learning with more trees
    {'n_estimators': 900, 'max_depth': 2, 'learning_rate': 0.008, 'subsample': 0.5, 
     'colsample_bytree': 0.5, 'min_child_weight': 30, 'reg_alpha': 3.0, 'reg_lambda': 4.0},
    # Slightly deeper
    {'n_estimators': 500, 'max_depth': 3, 'learning_rate': 0.012, 'subsample': 0.5, 
     'colsample_bytree': 0.5, 'min_child_weight': 25, 'reg_alpha': 2.5, 'reg_lambda': 3.5},
    # More stochastic
    {'n_estimators': 700, 'max_depth': 2, 'learning_rate': 0.010, 'subsample': 0.4, 
     'colsample_bytree': 0.4, 'min_child_weight': 30, 'reg_alpha': 3.0, 'reg_lambda': 4.0},
]

for i, cfg in enumerate(alt_configs):
    mean, std = evaluate_with_config(cfg, 0.2, 'sigmoid')
    print(f"  Config {i+1}: {mean:.4f} (+/- {std:.4f})")

# Strategy 4: Weighted ensemble
print("\n4. Weighted XGB + LGBM ensemble:")
print("-" * 60)

try:
    from lightgbm import LGBMClassifier
    
    lgbm_config = {
        'n_estimators': 700, 'max_depth': 2, 'learning_rate': 0.010,
        'subsample': 0.5, 'colsample_bytree': 0.5, 'min_child_samples': 50,
        'reg_alpha': 3.0, 'reg_lambda': 4.0, 'verbose': -1
    }
    
    weighted_scores = []
    for w_xgb in [0.5, 0.6, 0.7]:
        w_lgbm = 1 - w_xgb
        fold_scores = []
        
        for train_idx, test_idx in tscv.split(X):
            train_size = int(len(train_idx) * 0.8)
            train_idx_actual = train_idx[:train_size]
            calib_idx = train_idx[train_size:]
            
            X_train, y_train = X.iloc[train_idx_actual], y.iloc[train_idx_actual]
            X_calib, y_calib = X.iloc[calib_idx], y.iloc[calib_idx]
            X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
            
            # XGBoost
            xgb = XGBClassifier(**best_config, random_state=42)
            xgb.fit(X_train, y_train)
            xgb_cal = CalibratedClassifierCV(xgb, method='sigmoid', cv='prefit')
            xgb_cal.fit(X_calib, y_calib)
            xgb_probs = xgb_cal.predict_proba(X_test)[:, 1]
            
            # LightGBM
            lgbm = LGBMClassifier(**lgbm_config, random_state=42)
            lgbm.fit(X_train, y_train)
            lgbm_cal = CalibratedClassifierCV(lgbm, method='sigmoid', cv='prefit')
            lgbm_cal.fit(X_calib, y_calib)
            lgbm_probs = lgbm_cal.predict_proba(X_test)[:, 1]
            
            # Weighted average
            avg_probs = w_xgb * xgb_probs + w_lgbm * lgbm_probs
            fold_scores.append(brier_score_loss(y_test, avg_probs))
        
        print(f"  XGB:{w_xgb:.0%}/LGBM:{w_lgbm:.0%}: {np.mean(fold_scores):.4f} (+/- {np.std(fold_scores):.4f})")
        weighted_scores.append((w_xgb, np.mean(fold_scores)))
        
except ImportError:
    print("  LightGBM not available")

print("\n" + "=" * 60)
print("Best result from all strategies shown above")
