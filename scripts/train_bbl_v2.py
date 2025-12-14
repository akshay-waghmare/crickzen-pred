"""
Train BBL Model v2 (Using WBBL v3 Hyperparameters)
"""
import pandas as pd
import numpy as np
from pathlib import Path
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
import joblib
import json
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def train_bbl_v2():
    print("="*70)
    print("BBL Model v2 Training (WBBL v3 Params)")
    print("="*70)

    # Load training data
    train_path = Path("data/bbl_features_v1/training_sampled.parquet")
    if not train_path.exists():
        print(f"ERROR: Training data not found at {train_path}")
        return

    print(f"Loading training data from {train_path}...")
    df = pd.read_parquet(train_path)
    print(f"Loaded {len(df)} rows")

    # Define features (same as BBL v1 / WBBL v3)
    # We'll use the columns available in the dataframe, excluding non-features
    exclude_cols = ['is_winner', 'match_id', 'innings', 'over', 'ball', 'batting_team', 
                    'bowling_team', 'venue', 'season', 'current_score', 'wickets_lost',
                    'target_runs', 'first_innings_score', 'runs_required', 'date', 'start_date',
                    'batter_id', 'bowler_id', 'player_out_id', 'wicket_type', 'is_wicket',
                    'legal_ball', 'runs_batter', 'runs_extras', 'runs_total', 'balls_bowled',
                    'balls_remaining', 'projected_adjusted', 'score_adjusted_by_team',
                    'resource_team_adjusted', 'run_rate_team_adj']
    
    # Also exclude any object type columns just in case
    numeric_df = df.select_dtypes(include=[np.number])
    feature_cols = [c for c in numeric_df.columns if c not in exclude_cols]
    
    print(f"\nUsing {len(feature_cols)} features")
    print(f"Features: {feature_cols}")
    
    X = df[feature_cols].fillna(0)
    y = df['is_winner']
    
    # Split data (Time-based split would be better but random for now to match v1 evaluation)
    # Ideally we should split by match_id
    if 'match_id' in df.columns:
        match_ids = df['match_id'].unique()
        train_matches, test_matches = train_test_split(match_ids, test_size=0.2, random_state=42)
        train_mask = df['match_id'].isin(train_matches)
        test_mask = df['match_id'].isin(test_matches)
        X_train, X_test = X[train_mask], X[test_mask]
        y_train, y_test = y[train_mask], y[test_mask]
    else:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
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
    
    print("\nTraining XGBoost model with WBBL v3 parameters...")
    model = XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)
    
    # Evaluate
    probs = model.predict_proba(X_test)[:, 1]
    test_brier = brier_score_loss(y_test, probs)
    test_logloss = log_loss(y_test, probs)
    test_auc = roc_auc_score(y_test, probs)
    
    print(f"\nTest Results:")
    print(f"Brier Score: {test_brier:.4f}")
    print(f"Log Loss:    {test_logloss:.4f}")
    print(f"AUC:         {test_auc:.4f}")
    
    # Save model
    output_dir = Path('models/bbl_v2')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Attach selected_features_
    model.selected_features_ = feature_cols
    
    model_path = output_dir / 'champion_model.joblib'
    joblib.dump(model, model_path)
    print(f"\nModel saved to {model_path}")
    
    # Save metadata
    metadata = {
        "model_name": "XGBoost_WBBL_Params",
        "test_brier_score": float(test_brier),
        "test_log_loss": float(test_logloss),
        "test_auc": float(test_auc),
        "version": "v2",
        "league": "BBL",
        "samples": len(df),
        "features": len(feature_cols),
        "params": params
    }
    
    with open(output_dir / 'champion_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
        
    return test_brier

if __name__ == "__main__":
    train_bbl_v2()
