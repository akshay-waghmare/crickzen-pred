"""Final validation of the optimized model."""
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

print("=" * 60)
print("FINAL MODEL VALIDATION")
print("=" * 60)
print(f"Data: {len(X)} samples, {len(X.columns)} features")
print()

# Optimized config
model = XGBClassifier(
    n_estimators=650,
    max_depth=2,
    learning_rate=0.011,
    subsample=0.5,
    colsample_bytree=0.5,
    min_child_weight=28,
    reg_alpha=2.8,
    reg_lambda=3.8,
    random_state=42
)

# 5-fold time series CV with Platt scaling
tscv = TimeSeriesSplit(n_splits=5)
fold_scores = []

print("5-Fold Time Series CV with Platt Scaling:")
print("-" * 60)

for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
    # Split train into train + calibration (80/20)
    train_size = int(len(train_idx) * 0.8)
    train_idx_actual = train_idx[:train_size]
    calib_idx = train_idx[train_size:]
    
    X_train, y_train = X.iloc[train_idx_actual], y.iloc[train_idx_actual]
    X_calib, y_calib = X.iloc[calib_idx], y.iloc[calib_idx]
    X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
    
    # Train and calibrate
    model_clone = XGBClassifier(**model.get_params())
    model_clone.fit(X_train, y_train)
    
    calibrator = CalibratedClassifierCV(model_clone, method='sigmoid', cv='prefit')
    calibrator.fit(X_calib, y_calib)
    
    # Evaluate
    y_prob = calibrator.predict_proba(X_test)[:, 1]
    brier = brier_score_loss(y_test, y_prob)
    fold_scores.append(brier)
    print(f"  Fold {fold+1}: Brier = {brier:.4f} (test size: {len(X_test)})")

mean_brier = np.mean(fold_scores)
std_brier = np.std(fold_scores)

print()
print("=" * 60)
print(f"FINAL RESULT: Brier Score = {mean_brier:.4f} (+/- {std_brier:.4f})")
print("=" * 60)

if mean_brier <= 0.18:
    print("TARGET ACHIEVED! Brier <= 0.18")
else:
    print(f"Target: 0.18, Current: {mean_brier:.4f}, Gap: {mean_brier - 0.18:.4f}")
