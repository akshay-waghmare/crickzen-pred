import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
import joblib

def compare_calibration():
    print("Loading ILT20 data...")
    df = pd.read_parquet('data/ilt_features_v2/training_sampled.parquet')
    
    # Load feature list
    champion_v2 = joblib.load('models/ilt_champion_v2/champion_model.joblib')
    features = champion_v2.selected_features_
    
    X = df[features]
    y = df['is_winner']
    
    # Split
    split_idx = int(len(X) * 0.80)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # Base Model (Optimized v3 params)
    xgb = XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        n_estimators=500,
        max_depth=4,
        learning_rate=0.005,
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
    
    print("\nTraining Isotonic (Current)...")
    iso = CalibratedClassifierCV(xgb, method='isotonic', cv=5)
    iso.fit(X_train, y_train)
    iso_brier = brier_score_loss(y_test, iso.predict_proba(X_test)[:, 1])
    
    print("Training Sigmoid (Platt Scaling)...")
    sig = CalibratedClassifierCV(xgb, method='sigmoid', cv=5)
    sig.fit(X_train, y_train)
    sig_brier = brier_score_loss(y_test, sig.predict_proba(X_test)[:, 1])
    
    print("\n" + "="*60)
    print("CALIBRATION COMPARISON")
    print("="*60)
    print(f"Isotonic Brier: {iso_brier:.5f} (Better accuracy, 'steppy' output)")
    print(f"Sigmoid Brier:  {sig_brier:.5f} (Smoother output)")
    
    diff = sig_brier - iso_brier
    print(f"Difference:     {diff:.5f}")
    
    if diff < 0.002:
        print("\nRECOMMENDATION: Switch to Sigmoid.")
        print("The accuracy loss is negligible (< 0.002), but it will fix the")
        print("'identical probability' issue by providing smooth, continuous updates.")
    else:
        print("\nRECOMMENDATION: Stick with Isotonic.")
        print("Sigmoid loses too much accuracy.")

if __name__ == "__main__":
    compare_calibration()
