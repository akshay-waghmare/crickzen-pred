"""
Optimize NPL Model to improve Brier Score.
Target: < 0.175
Strategies:
1. Hyperparameter Tuning with GroupKFold (to prevent leakage)
2. Feature Selection
3. Calibration Comparison (Isotonic vs Sigmoid)
"""
import pandas as pd
import numpy as np
from pathlib import Path
from xgboost import XGBClassifier
from sklearn.model_selection import RandomizedSearchCV, GroupKFold, cross_val_score
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
import joblib
import json
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def optimize_npl():
    print("="*70)
    print("NPL Model Optimization")
    print("Target Brier Score: < 0.175")
    print("="*70)

    # Load training data
    train_path = Path("data/npl_features_v1/training.parquet")
    if not train_path.exists():
        print(f"ERROR: Training data not found at {train_path}")
        return

    print(f"Loading data from {train_path}...")
    df = pd.read_parquet(train_path)
    
    # Filter out super overs if any (usually match_id handles it, but good to be safe)
    # Assuming standard processing
    
    # Define features
    feature_cols = [
        # Core Game State
        "required_run_rate", "current_run_rate", "run_rate_diff",
        "overs_remaining", "wickets_lost", "resources_remaining",
        "score_vs_par", "chase_difficulty",
        
        # DLS Features (High value)
        "resource_pct", "resource_win_prob", "dls_pressure_index",
        
        # Team Strength (Critical for small datasets)
        "batting_team_win_rate", "bowling_team_win_rate", "team_strength_diff",
        "batting_team_situation_wr", "bowling_team_situation_wr",
        
        # Player Stats (Aggregated)
        "batting_pair_strength", "batsman_rolling_avg", "bowler_rolling_econ",
        
        # Momentum
        "runs_last_12", "wickets_last_12", "acceleration_potential"
    ]
    
    available_features = [f for f in feature_cols if f in df.columns]
    print(f"Selected {len(available_features)} high-value features")
    
    X = df[available_features].copy()
    y = df['is_winner'].copy()
    groups = df['match_id'].copy() # For GroupKFold
    
    X = X.fillna(0)
    
    # 1. Baseline: Logistic Regression (often better for small data)
    print("\n[1/3] Testing Logistic Regression Baseline...")
    lr = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
    
    gkf = GroupKFold(n_splits=5)
    
    # Cross-validate LR
    lr_scores = []
    for train_idx, test_idx in gkf.split(X, y, groups):
        X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
        y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
        
        lr.fit(X_tr, y_tr)
        probs = lr.predict_proba(X_te)[:, 1]
        score = brier_score_loss(y_te, probs)
        lr_scores.append(score)
        
    print(f"Logistic Regression CV Brier: {np.mean(lr_scores):.4f} (+/- {np.std(lr_scores):.4f})")

    # 2. XGBoost Hyperparameter Tuning
    print("\n[2/3] Tuning XGBoost...")
    
    # Parameter grid for small dataset
    # Focus on high regularization and shallow trees
    param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [2, 3, 4],           # Shallow trees to prevent overfitting
        'learning_rate': [0.01, 0.05, 0.1],
        'subsample': [0.5, 0.7, 0.8],
        'colsample_bytree': [0.5, 0.7, 0.8],
        'min_child_weight': [5, 10, 20],  # High weight to prevent leafing on noise
        'reg_alpha': [0.1, 1.0, 5.0],     # L1 Regularization
        'reg_lambda': [1.0, 5.0, 10.0]    # L2 Regularization
    }
    
    xgb = XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        tree_method='hist',
        random_state=42,
        n_jobs=-1
    )
    
    search = RandomizedSearchCV(
        xgb,
        param_distributions=param_grid,
        n_iter=20,
        scoring='neg_brier_score',
        cv=gkf, # Use GroupKFold
        verbose=1,
        random_state=42,
        n_jobs=-1
    )
    
    search.fit(X, y, groups=groups)
    
    print(f"Best XGB Params: {search.best_params_}")
    print(f"Best XGB CV Brier: {-search.best_score_:.4f}")
    
    best_xgb = search.best_estimator_
    
    # 3. Calibration Comparison
    print("\n[3/3] Comparing Calibration Methods...")
    
    # Split for final validation
    train_matches, test_matches = [], []
    unique_matches = groups.unique()
    np.random.seed(42)
    np.random.shuffle(unique_matches)
    split_idx = int(len(unique_matches) * 0.8)
    train_matches = unique_matches[:split_idx]
    test_matches = unique_matches[split_idx:]
    
    train_mask = groups.isin(train_matches)
    test_mask = groups.isin(test_matches)
    
    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]
    
    print(f"Train matches: {len(train_matches)}, Test matches: {len(test_matches)}")
    
    # Method A: Isotonic (Non-parametric, needs more data)
    cal_iso = CalibratedClassifierCV(best_xgb, method='isotonic', cv=3)
    cal_iso.fit(X_train, y_train)
    probs_iso = cal_iso.predict_proba(X_test)[:, 1]
    brier_iso = brier_score_loss(y_test, probs_iso)
    
    # Method B: Sigmoid (Platt Scaling, better for small data)
    cal_sig = CalibratedClassifierCV(best_xgb, method='sigmoid', cv=3)
    cal_sig.fit(X_train, y_train)
    probs_sig = cal_sig.predict_proba(X_test)[:, 1]
    brier_sig = brier_score_loss(y_test, probs_sig)
    
    # Method C: Uncalibrated
    best_xgb.fit(X_train, y_train)
    probs_raw = best_xgb.predict_proba(X_test)[:, 1]
    brier_raw = brier_score_loss(y_test, probs_raw)
    
    print(f"Uncalibrated Brier: {brier_raw:.4f}")
    print(f"Isotonic Brier:     {brier_iso:.4f}")
    print(f"Sigmoid Brier:      {brier_sig:.4f}")
    
    # Select winner
    best_model = None
    best_brier = min(brier_raw, brier_iso, brier_sig)
    method_name = ""
    
    if best_brier == brier_iso:
        best_model = cal_iso
        method_name = "XGBoost_Isotonic"
    elif best_brier == brier_sig:
        best_model = cal_sig
        method_name = "XGBoost_Sigmoid"
    else:
        best_model = best_xgb
        method_name = "XGBoost_Raw"
        
    print(f"\nWinner: {method_name} with Brier {best_brier:.4f}")
    
    if best_brier > 0.175:
        print("WARNING: Target 0.175 not reached. Dataset might be too small or noisy.")
    else:
        print("SUCCESS: Target 0.175 reached!")
        
    # Save Best Model
    output_dir = Path("models/npl_champion_v1")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Attach features
    best_model.selected_features_ = available_features
    
    joblib.dump(best_model, output_dir / "champion_model.joblib")
    
    # Save metadata
    metadata = {
        "model_name": f"NPL_Optimized_{method_name}",
        "version": "1.1",
        "features": available_features,
        "metrics": {
            "test_brier": float(best_brier),
            "test_auc": float(roc_auc_score(y_test, best_model.predict_proba(X_test)[:, 1]))
        },
        "params": search.best_params_,
        "notes": "Optimized with GroupKFold and Feature Selection"
    }
    
    with open(output_dir / "champion_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
        
    print(f"Model saved to {output_dir}")

if __name__ == "__main__":
    optimize_npl()
