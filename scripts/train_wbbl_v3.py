"""
Train WBBL Champion Model v3 (Corrected Data)
Uses hyperparameter-tuned XGBoost with deduplicated training data
"""
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.metrics import brier_score_loss
import joblib
import os
import json

def train_wbbl_v3():
    print("Loading WBBL training data v3 (deduplicated)...")
    df = pd.read_parquet('data/wbbl_features_v3/training_sampled.parquet')
    
    print(f"Total samples: {len(df)}")
    
    # Define features
    target_col = 'is_winner'
    exclude_cols = ['is_winner', 'match_id', 'innings', 'over', 'ball', 'batting_team', 
                    'bowling_team', 'venue', 'season', 'current_score', 'wickets_lost',
                    'target_runs', 'first_innings_score', 'runs_required']
    
    feature_cols = [col for col in df.columns if col not in exclude_cols and not col.startswith('_')]
    numeric_df = df[feature_cols].select_dtypes(include=[np.number])
    feature_cols = numeric_df.columns.tolist()
    
    print(f"Using {len(feature_cols)} features")
    
    X = df[feature_cols].fillna(0)
    y = df[target_col]
    
    # Time-based split
    split_idx = int(len(X) * 0.80)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    # Best hyperparameters from optimization study
    best_params = {
        'subsample': 0.8,
        'reg_lambda': 2,
        'reg_alpha': 1,
        'n_estimators': 500,
        'min_child_weight': 5,
        'max_depth': 4,
        'learning_rate': 0.01,
        'colsample_bytree': 0.4
    }
    
    print("\nTraining optimized XGBoost model...")
    model = XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        tree_method='hist',
        n_jobs=-1,
        verbosity=0,
        random_state=42,
        **best_params
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    train_probs = model.predict_proba(X_train)[:, 1]
    test_probs = model.predict_proba(X_test)[:, 1]
    
    train_brier = brier_score_loss(y_train, train_probs)
    test_brier = brier_score_loss(y_test, test_probs)
    
    print("\n" + "="*60)
    print("WBBL MODEL v3 PERFORMANCE")
    print("="*60)
    print(f"Train Brier Score: {train_brier:.4f}")
    print(f"Test Brier Score:  {test_brier:.4f}")
    print(f"Generalization Gap: {test_brier - train_brier:.4f}")
    
    # Compare with previous versions
    print("\nComparison with previous versions:")
    print(f"v1 Test Brier: 0.1836")
    print(f"v2 Test Brier: 0.1828")
    print(f"v3 Test Brier: {test_brier:.4f}")
    
    improvement_v2 = (0.1828 - test_brier) / 0.1828 * 100
    print(f"Improvement over v2: {improvement_v2:.2f}%")
    
    # Save model
    output_dir = 'models/wbbl_champion_v3'
    os.makedirs(output_dir, exist_ok=True)
    
    # Attach selected_features_ to the model object
    model.selected_features_ = feature_cols
    
    model_path = os.path.join(output_dir, 'champion_model.joblib')
    joblib.dump(model, model_path)
    print(f"\nModel saved to {model_path}")
    
    # Save metadata
    metadata = {
        "model_name": "XGBoost_Tuned",
        "train_brier_score": float(train_brier),
        "test_brier_score": float(test_brier),
        "version": "v3",
        "league": "WBBL",
        "samples": len(df),
        "features": len(feature_cols),
        "calibration": "none",
        "params": best_params,
        "changes": [
            "Deduplicated training data (removed 114912 duplicate rows)",
            "Corrected venue_avg_score (was ~280, now ~136)"
        ]
    }
    
    with open(os.path.join(output_dir, 'champion_metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Save feature names
    with open(os.path.join(output_dir, 'feature_names.json'), 'w') as f:
        json.dump(feature_cols, f, indent=2)
    
    print("Metadata and feature names saved.")
    
    return test_brier

if __name__ == "__main__":
    train_wbbl_v3()
