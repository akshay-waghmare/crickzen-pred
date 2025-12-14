"""
Train BBL Model v3 (WBBL Params + Isotonic Calibration)
Fixes the ECE degradation observed in v2.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
import joblib
import json
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def train_bbl_v3():
    print("="*70)
    print("BBL Model v3 Training (WBBL Params + Calibration)")
    print("="*70)

    # Load training data
    train_path = Path("data/bbl_features_v1/training_sampled.parquet")
    if not train_path.exists():
        print(f"ERROR: Training data not found at {train_path}")
        return

    print(f"Loading training data from {train_path}...")
    df = pd.read_parquet(train_path)
    
    # Define features (same as v2)
    exclude_cols = ['is_winner', 'match_id', 'innings', 'over', 'ball', 'batting_team', 
                    'bowling_team', 'venue', 'season', 'current_score', 'wickets_lost',
                    'target_runs', 'first_innings_score', 'runs_required', 'date', 'start_date',
                    'batter_id', 'bowler_id', 'player_out_id', 'wicket_type', 'is_wicket',
                    'legal_ball', 'runs_batter', 'runs_extras', 'runs_total', 'balls_bowled',
                    'balls_remaining', 'projected_adjusted', 'score_adjusted_by_team',
                    'resource_team_adjusted', 'run_rate_team_adj']
    
    numeric_df = df.select_dtypes(include=[np.number])
    feature_cols = [c for c in numeric_df.columns if c not in exclude_cols]
    
    X = df[feature_cols].fillna(0)
    y = df['is_winner']
    
    # Split data
    # We need a calibration set. 
    # Split: Train (60%), Calibration (20%), Test (20%)
    X_train_full, X_test, y_train_full, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    X_train, X_calib, y_train, y_calib = train_test_split(X_train_full, y_train_full, test_size=0.25, random_state=42, stratify=y_train_full)
    
    print(f"Train: {len(X_train)}, Calibration: {len(X_calib)}, Test: {len(X_test)}")
    
    # WBBL v3 Parameters
    params = {
        "subsample": 0.8,
        "reg_lambda": 2,
        "reg_alpha": 1,
        "n_estimators": 500,
        "min_child_weight": 5,
        "max_depth": 4,
        "learning_rate": 0.01,
        "colsample_bytree": 0.4,
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "random_state": 42,
        "n_jobs": -1,
        "early_stopping_rounds": 50
    }
    
    print("\n1. Training Base XGBoost model...")
    base_model = XGBClassifier(**params)
    base_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=0)
    
    print("\n2. Calibrating model (Isotonic)...")
    calibrated_model = CalibratedClassifierCV(base_model, method='isotonic', cv='prefit')
    calibrated_model.fit(X_calib, y_calib)
    
    # Evaluate
    probs = calibrated_model.predict_proba(X_test)[:, 1]
    test_brier = brier_score_loss(y_test, probs)
    test_logloss = log_loss(y_test, probs)
    test_auc = roc_auc_score(y_test, probs)
    
    # Calculate ECE
    def calculate_ece(y_true, y_prob, n_bins=10):
        bins = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        for i in range(n_bins):
            mask = (y_prob >= bins[i]) & (y_prob < bins[i+1])
            if mask.sum() > 0:
                avg_pred = y_prob[mask].mean()
                avg_true = y_true[mask].mean()
                ece += mask.sum() * abs(avg_pred - avg_true)
        return ece / len(y_true)
        
    test_ece = calculate_ece(y_test.values, probs)
    
    print(f"\nTest Results (v3):")
    print(f"Brier Score: {test_brier:.4f}")
    print(f"Log Loss:    {test_logloss:.4f}")
    print(f"AUC:         {test_auc:.4f}")
    print(f"ECE:         {test_ece:.4f}")
    
    # Save model
    output_dir = Path('models/bbl_v3')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Attach selected_features_ to the base estimator so we can retrieve them later
    # CalibratedClassifierCV wraps the model.
    calibrated_model.selected_features_ = feature_cols
    
    model_path = output_dir / 'champion_model.joblib'
    joblib.dump(calibrated_model, model_path)
    print(f"\nModel saved to {model_path}")
    
    # Save metadata
    metadata = {
        "model_name": "XGBoost_Calibrated_Isotonic",
        "test_brier_score": float(test_brier),
        "test_log_loss": float(test_logloss),
        "test_auc": float(test_auc),
        "test_ece": float(test_ece),
        "version": "v3",
        "league": "BBL",
        "samples": len(df),
        "features": len(feature_cols),
        "params": params,
        "calibration": "isotonic"
    }
    
    with open(output_dir / 'champion_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
        
    return test_brier

if __name__ == "__main__":
    train_bbl_v3()
