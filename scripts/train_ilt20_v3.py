import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
import joblib
import os
import json
import structlog

# Setup logging
logger = structlog.get_logger()

def train_v3():
    print("Loading ILT20 data...")
    df = pd.read_parquet('data/ilt_features_v2/training_sampled.parquet')
    
    # Load v2 to get feature list
    champion_v2 = joblib.load('models/ilt_champion_v2/champion_model.joblib')
    features = champion_v2.selected_features_
    
    X = df[features]
    y = df['is_winner']
    
    print(f"Training on {len(X)} samples with {len(features)} features")
    
    # Define optimized XGBoost model
    # Best Parameters: {'subsample': 0.5, 'reg_lambda': 3.8, 'reg_alpha': 2.8, 
    # 'n_estimators': 500, 'min_child_weight': 28, 'max_depth': 4, 
    # 'learning_rate': 0.005, 'colsample_bytree': 0.4}
    
    xgb_optimized = XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        n_estimators=500,
        max_depth=4,           # Increased from 2
        learning_rate=0.005,   # Decreased from 0.011
        subsample=0.5,
        colsample_bytree=0.4,  # Decreased from 0.5
        min_child_weight=28,
        reg_alpha=2.8,
        reg_lambda=3.8,
        tree_method='hist',
        n_jobs=-1,
        verbosity=0,
        random_state=42
    )
    
    # Wrap in CalibratedClassifierCV (Isotonic)
    # cv=5 means it will train 5 models on folds and average them
    calibrated_model = CalibratedClassifierCV(
        xgb_optimized, 
        method='isotonic', 
        cv=5
    )
    
    print("Training calibrated model (this may take a moment)...")
    calibrated_model.fit(X, y)
    
    # Evaluate on training data (sanity check)
    probs = calibrated_model.predict_proba(X)[:, 1]
    train_brier = brier_score_loss(y, probs)
    print(f"Training Brier Score: {train_brier:.4f}")
    
    # Save model
    output_dir = 'models/ilt_champion_v3'
    os.makedirs(output_dir, exist_ok=True)
    
    # Attach selected_features_ to the model object so predictor.py can use it
    calibrated_model.selected_features_ = features
    
    model_path = os.path.join(output_dir, 'champion_model.joblib')
    joblib.dump(calibrated_model, model_path)
    print(f"Model saved to {model_path}")
    
    # Save metadata
    metadata = {
        "model_name": "XGBoost_Optimized_Isotonic",
        "brier_score": train_brier,
        "version": "v3",
        "params": {
            "max_depth": 4,
            "learning_rate": 0.005,
            "calibration": "isotonic"
        }
    }
    
    with open(os.path.join(output_dir, 'champion_metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)

if __name__ == "__main__":
    train_v3()
