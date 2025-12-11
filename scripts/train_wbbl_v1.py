"""
Train WBBL Champion Model (v1)
Uses the same optimized approach as ILT20 v3:
- XGBoost with optimized hyperparameters
- Isotonic Calibration
- Holdout validation for overfitting check
"""
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
import joblib
import os
import json

def train_wbbl_model():
    print("Loading WBBL training data...")
    df = pd.read_parquet('data/wbbl_features_v2/training_sampled.parquet')
    
    print(f"Total samples: {len(df)}")
    
    # Define feature columns (same as ILT20/BBL)
    # We need to get the feature list from the data
    target_col = 'is_winner'
    
    # Exclude non-feature columns
    exclude_cols = ['is_winner', 'match_id', 'innings', 'over', 'ball', 'batting_team', 
                    'bowling_team', 'venue', 'season', 'current_score', 'wickets_lost',
                    'target_runs', 'first_innings_score', 'runs_required']
    
    feature_cols = [col for col in df.columns if col not in exclude_cols and not col.startswith('_')]
    
    # Filter to only numeric columns
    numeric_df = df[feature_cols].select_dtypes(include=[np.number])
    feature_cols = numeric_df.columns.tolist()
    
    print(f"Using {len(feature_cols)} features")
    
    X = df[feature_cols].fillna(0)
    y = df[target_col]
    
    # Time-based split (80% train, 20% test)
    split_idx = int(len(X) * 0.80)
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"Train size: {len(X_train)}")
    print(f"Test size:  {len(X_test)}")
    
    # Define optimized XGBoost model (same params as ILT20 v3)
    xgb_optimized = XGBClassifier(
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
    
    # Wrap in CalibratedClassifierCV (Isotonic)
    print("Training calibrated model (this may take a moment)...")
    calibrated_model = CalibratedClassifierCV(
        xgb_optimized, 
        method='isotonic', 
        cv=5
    )
    
    calibrated_model.fit(X_train, y_train)
    
    # Evaluate
    train_probs = calibrated_model.predict_proba(X_train)[:, 1]
    test_probs = calibrated_model.predict_proba(X_test)[:, 1]
    
    train_brier = brier_score_loss(y_train, train_probs)
    test_brier = brier_score_loss(y_test, test_probs)
    
    print("\n" + "="*60)
    print("WBBL MODEL PERFORMANCE")
    print("="*60)
    print(f"Train Brier Score: {train_brier:.4f}")
    print(f"Test Brier Score:  {test_brier:.4f}")
    print(f"Generalization Gap: {test_brier - train_brier:.4f}")
    
    # Save model
    output_dir = 'models/wbbl_champion_v1'
    os.makedirs(output_dir, exist_ok=True)
    
    # Attach selected_features_ to the model object so predictor.py can use it
    calibrated_model.selected_features_ = feature_cols
    
    model_path = os.path.join(output_dir, 'champion_model.joblib')
    joblib.dump(calibrated_model, model_path)
    print(f"\nModel saved to {model_path}")
    
    # Save metadata
    metadata = {
        "model_name": "XGBoost_Optimized_Isotonic",
        "train_brier_score": train_brier,
        "test_brier_score": test_brier,
        "version": "v1",
        "league": "WBBL",
        "samples": len(df),
        "features": len(feature_cols),
        "params": {
            "max_depth": 4,
            "learning_rate": 0.005,
            "calibration": "isotonic"
        }
    }
    
    with open(os.path.join(output_dir, 'champion_metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("Metadata saved.")
    
    return test_brier

if __name__ == "__main__":
    train_wbbl_model()
