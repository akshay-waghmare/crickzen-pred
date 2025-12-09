"""Final push to reach 0.18 Brier score target."""
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

def evaluate(model_config, calib_split=0.15):
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
        
        calibrator = CalibratedClassifierCV(model, method='sigmoid', cv='prefit')
        calibrator.fit(X_calib, y_calib)
        
        y_prob = calibrator.predict_proba(X_test)[:, 1]
        fold_scores.append(brier_score_loss(y_test, y_prob))
    
    return np.mean(fold_scores), np.std(fold_scores)

# Fine-tune with 15% calibration split around best config
print("\nFine-tuning with 15% calibration split:")
print("-" * 60)

configs = [
    # Baseline
    {'n_estimators': 650, 'max_depth': 2, 'learning_rate': 0.011, 'subsample': 0.5, 
     'colsample_bytree': 0.5, 'min_child_weight': 28, 'reg_alpha': 2.8, 'reg_lambda': 3.8},
    # Variations
    {'n_estimators': 600, 'max_depth': 2, 'learning_rate': 0.012, 'subsample': 0.5, 
     'colsample_bytree': 0.5, 'min_child_weight': 26, 'reg_alpha': 2.6, 'reg_lambda': 3.5},
    {'n_estimators': 700, 'max_depth': 2, 'learning_rate': 0.010, 'subsample': 0.5, 
     'colsample_bytree': 0.5, 'min_child_weight': 30, 'reg_alpha': 3.0, 'reg_lambda': 4.0},
    {'n_estimators': 650, 'max_depth': 2, 'learning_rate': 0.011, 'subsample': 0.55, 
     'colsample_bytree': 0.55, 'min_child_weight': 25, 'reg_alpha': 2.5, 'reg_lambda': 3.5},
    {'n_estimators': 750, 'max_depth': 2, 'learning_rate': 0.009, 'subsample': 0.5, 
     'colsample_bytree': 0.5, 'min_child_weight': 32, 'reg_alpha': 3.2, 'reg_lambda': 4.2},
]

best_score = 1.0
best_cfg = None
for i, cfg in enumerate(configs):
    mean, std = evaluate(cfg, 0.15)
    status = " <-- BEST" if mean < best_score else ""
    if mean < best_score:
        best_score = mean
        best_cfg = cfg
    print(f"Config {i+1}: {mean:.4f} (+/- {std:.4f}){status}")

# Try calibration splits around 15%
print("\nFine-tune calibration split around 15%:")
print("-" * 60)

for calib_split in [0.12, 0.14, 0.15, 0.16, 0.18]:
    mean, std = evaluate(best_cfg, calib_split)
    status = " <-- BEST" if mean < best_score else ""
    if mean < best_score:
        best_score = mean
    print(f"  Calib {calib_split:.0%}: {mean:.4f} (+/- {std:.4f}){status}")

print("\n" + "=" * 60)
print(f"BEST ACHIEVED: {best_score:.4f}")
print(f"TARGET: 0.1800")
print(f"GAP: {best_score - 0.18:.4f}")
if best_score <= 0.18:
    print("TARGET ACHIEVED!")
print("=" * 60)
