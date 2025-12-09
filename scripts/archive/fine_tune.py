"""Fine-tune around the best config (n=700, d=2, lr=0.010, mcw=30, ra=3.0) achieving 0.1865."""
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

# 5-fold time series CV
tscv = TimeSeriesSplit(n_splits=5)

def evaluate_model(model, calib_method='sigmoid'):
    """Evaluate model with 5-fold time-series CV and calibration."""
    fold_scores = []
    for train_idx, test_idx in tscv.split(X):
        train_size = int(len(train_idx) * 0.8)
        train_idx_actual = train_idx[:train_size]
        calib_idx = train_idx[train_size:]
        
        X_train, y_train = X.iloc[train_idx_actual], y.iloc[train_idx_actual]
        X_calib, y_calib = X.iloc[calib_idx], y.iloc[calib_idx]
        X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
        
        model_clone = model.__class__(**model.get_params())
        model_clone.fit(X_train, y_train)
        
        calibrator = CalibratedClassifierCV(model_clone, method=calib_method, cv='prefit')
        calibrator.fit(X_calib, y_calib)
        
        y_prob = calibrator.predict_proba(X_test)[:, 1]
        brier = brier_score_loss(y_test, y_prob)
        fold_scores.append(brier)
    
    return np.mean(fold_scores), np.std(fold_scores)

# Fine-tune configs around best (n=700, d=2, lr=0.010, mcw=30, ra=3.0, rl=4.0)
print("\nFine-tuning XGBoost around best config:")
print("-" * 60)

configs = [
    # Baseline best
    (700, 2, 0.010, 0.5, 30, 3.0, 4.0),
    # Slight variations
    (750, 2, 0.009, 0.5, 32, 3.2, 4.2),
    (700, 2, 0.010, 0.45, 30, 3.5, 4.5),
    (650, 2, 0.011, 0.5, 28, 2.8, 3.8),
    (700, 2, 0.010, 0.4, 35, 4.0, 5.0),
    (800, 2, 0.008, 0.5, 35, 3.5, 4.5),
    # More aggressive regularization
    (750, 2, 0.008, 0.4, 40, 4.5, 5.5),
    (850, 2, 0.007, 0.4, 45, 5.0, 6.0),
    # Less regularization (check if overfit)
    (600, 2, 0.012, 0.55, 25, 2.5, 3.0),
    (550, 2, 0.014, 0.6, 22, 2.0, 2.5),
    # Different colsample
    (700, 2, 0.010, 0.5, 30, 3.0, 4.0),  # with colsample=0.6
    (700, 2, 0.010, 0.5, 30, 3.0, 4.0),  # with colsample=0.7
]

best_score = 1.0
best_config = None

for i, (n, d, lr, ss, mcw, ra, rl) in enumerate(configs):
    # Vary colsample for last two configs
    cs = 0.6 if i == len(configs) - 2 else (0.7 if i == len(configs) - 1 else ss)
    
    model = XGBClassifier(
        n_estimators=n, max_depth=d, learning_rate=lr,
        subsample=ss, colsample_bytree=cs, min_child_weight=mcw,
        reg_alpha=ra, reg_lambda=rl, random_state=42
    )
    mean_brier, std_brier = evaluate_model(model, 'sigmoid')
    print(f"n={n:3d}, d={d}, lr={lr:.3f}, ss={ss:.2f}, cs={cs:.2f}, mcw={mcw:2d}, ra={ra:.1f}, rl={rl:.1f}: {mean_brier:.4f} (+/- {std_brier:.4f})")
    
    if mean_brier < best_score:
        best_score = mean_brier
        best_config = (n, d, lr, ss, cs, mcw, ra, rl)

print("\n" + "=" * 60)
print(f"BEST SCORE: {best_score:.4f}")
print(f"BEST CONFIG: n={best_config[0]}, d={best_config[1]}, lr={best_config[2]:.3f}, ss={best_config[3]:.2f}, cs={best_config[4]:.2f}, mcw={best_config[5]}, ra={best_config[6]:.1f}, rl={best_config[7]:.1f}")

# Test with isotonic too for the best config
print("\nCalibration comparison for best config:")
print("-" * 60)
n, d, lr, ss, cs, mcw, ra, rl = best_config
model = XGBClassifier(
    n_estimators=n, max_depth=d, learning_rate=lr,
    subsample=ss, colsample_bytree=cs, min_child_weight=mcw,
    reg_alpha=ra, reg_lambda=rl, random_state=42
)

for method in ['sigmoid', 'isotonic']:
    mean_brier, std_brier = evaluate_model(model, method)
    print(f"{method:10s}: {mean_brier:.4f} (+/- {std_brier:.4f})")
