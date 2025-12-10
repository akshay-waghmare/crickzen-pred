import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
import joblib
import structlog

logger = structlog.get_logger()

def verify_overfitting():
    print("Loading ILT20 data...")
    df = pd.read_parquet('data/ilt_features_v2/training_sampled.parquet')
    
    # Load feature list from v2
    champion_v2 = joblib.load('models/ilt_champion_v2/champion_model.joblib')
    features = champion_v2.selected_features_
    
    X = df[features]
    y = df['is_winner']
    
    # Time-based split (80% train, 20% test)
    split_idx = int(len(X) * 0.80)
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"Train size: {len(X_train)}")
    print(f"Test size:  {len(X_test)}")
    
    # --- Model v2 (Baseline) ---
    print("\nTraining v2 (Baseline) on 80% split...")
    # Params from trainer.py (XGBLogRegEnsemble defaults)
    xgb_v2 = XGBClassifier(
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
        n_jobs=-1,
        verbosity=0,
        random_state=42
    )
    xgb_v2.fit(X_train, y_train)
    
    # Evaluate v2
    train_prob_v2 = xgb_v2.predict_proba(X_train)[:, 1]
    test_prob_v2 = xgb_v2.predict_proba(X_test)[:, 1]
    
    train_brier_v2 = brier_score_loss(y_train, train_prob_v2)
    test_brier_v2 = brier_score_loss(y_test, test_prob_v2)
    
    # --- Model v3 (Optimized + Calibrated) ---
    print("Training v3 (Optimized) on 80% split...")
    # Params from optimization
    xgb_v3 = XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        n_estimators=500,
        max_depth=4,           # Deeper
        learning_rate=0.005,   # Slower
        subsample=0.5,
        colsample_bytree=0.4,
        min_child_weight=28,
        reg_alpha=2.8,
        reg_lambda=3.8,
        tree_method='hist',
        n_jobs=-1,
        verbosity=0,
        random_state=42
    )
    
    # Calibrated wrapper
    cal_v3 = CalibratedClassifierCV(xgb_v3, method='isotonic', cv=3)
    cal_v3.fit(X_train, y_train)
    
    # Evaluate v3
    train_prob_v3 = cal_v3.predict_proba(X_train)[:, 1]
    test_prob_v3 = cal_v3.predict_proba(X_test)[:, 1]
    
    train_brier_v3 = brier_score_loss(y_train, train_prob_v3)
    test_brier_v3 = brier_score_loss(y_test, test_prob_v3)
    
    # --- Comparison ---
    print("\n" + "="*60)
    print("OVERFITTING CHECK (Lower Brier is Better)")
    print("="*60)
    
    print(f"{'Metric':<20} {'v2 (Baseline)':<15} {'v3 (Optimized)':<15} {'Diff':<10}")
    print("-" * 60)
    print(f"{'Train Brier':<20} {train_brier_v2:.4f}          {train_brier_v3:.4f}          {train_brier_v3-train_brier_v2:+.4f}")
    print(f"{'Test Brier':<20} {test_brier_v2:.4f}          {test_brier_v3:.4f}          {test_brier_v3-test_brier_v2:+.4f}")
    print("-" * 60)
    
    gap_v2 = test_brier_v2 - train_brier_v2
    gap_v3 = test_brier_v3 - train_brier_v3
    
    print(f"{'Generalization Gap':<20} {gap_v2:.4f}          {gap_v3:.4f}")
    
    print("\nCONCLUSION:")
    if test_brier_v3 < test_brier_v2:
        print("✅ v3 is genuinely better on unseen test data.")
        if gap_v3 > gap_v2 + 0.01:
            print("⚠️ However, v3 shows signs of higher overfitting (larger gap).")
    else:
        print("❌ v3 is overfitting! It performs worse on test data despite better training score.")

if __name__ == "__main__":
    verify_overfitting()
