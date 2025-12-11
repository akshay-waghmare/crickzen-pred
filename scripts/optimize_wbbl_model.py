"""
WBBL Model Optimization Study
Compare different configurations:
1. Baseline XGBoost (no calibration)
2. XGBoost + Isotonic Calibration
3. XGBoost + Sigmoid Calibration
4. Hyperparameter Tuned XGBoost
5. Hyperparameter Tuned + Isotonic Calibration
"""
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import RandomizedSearchCV
import warnings
warnings.filterwarnings('ignore')

def run_optimization_study():
    print("Loading WBBL training data...")
    df = pd.read_parquet('data/wbbl_features_v2/training_sampled.parquet')
    
    # Define features
    target_col = 'is_winner'
    exclude_cols = ['is_winner', 'match_id', 'innings', 'over', 'ball', 'batting_team', 
                    'bowling_team', 'venue', 'season', 'current_score', 'wickets_lost',
                    'target_runs', 'first_innings_score', 'runs_required']
    
    feature_cols = [col for col in df.columns if col not in exclude_cols and not col.startswith('_')]
    numeric_df = df[feature_cols].select_dtypes(include=[np.number])
    feature_cols = numeric_df.columns.tolist()
    
    X = df[feature_cols].fillna(0)
    y = df[target_col]
    
    # Time-based split
    split_idx = int(len(X) * 0.80)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    results = {}
    
    # ====================================================================
    # 1. Baseline XGBoost (Default Params, No Calibration)
    # ====================================================================
    print("\n[1/6] Training Baseline XGBoost...")
    xgb_baseline = XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        n_jobs=-1,
        verbosity=0,
        random_state=42
    )
    xgb_baseline.fit(X_train, y_train)
    probs = xgb_baseline.predict_proba(X_test)[:, 1]
    results['1. Baseline XGBoost'] = brier_score_loss(y_test, probs)
    
    # ====================================================================
    # 2. Baseline + Isotonic Calibration
    # ====================================================================
    print("[2/6] Training Baseline + Isotonic...")
    xgb_iso = CalibratedClassifierCV(
        XGBClassifier(
            objective='binary:logistic',
            n_estimators=100, max_depth=3, learning_rate=0.1,
            n_jobs=-1, verbosity=0, random_state=42
        ),
        method='isotonic', cv=5
    )
    xgb_iso.fit(X_train, y_train)
    probs = xgb_iso.predict_proba(X_test)[:, 1]
    results['2. Baseline + Isotonic'] = brier_score_loss(y_test, probs)
    
    # ====================================================================
    # 3. Baseline + Sigmoid Calibration
    # ====================================================================
    print("[3/6] Training Baseline + Sigmoid...")
    xgb_sig = CalibratedClassifierCV(
        XGBClassifier(
            objective='binary:logistic',
            n_estimators=100, max_depth=3, learning_rate=0.1,
            n_jobs=-1, verbosity=0, random_state=42
        ),
        method='sigmoid', cv=5
    )
    xgb_sig.fit(X_train, y_train)
    probs = xgb_sig.predict_proba(X_test)[:, 1]
    results['3. Baseline + Sigmoid'] = brier_score_loss(y_test, probs)
    
    # ====================================================================
    # 4. ILT20-Style Params (No Tuning, No Calibration)
    # ====================================================================
    print("[4/6] Training ILT20-Style Params...")
    xgb_ilt_style = XGBClassifier(
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
    xgb_ilt_style.fit(X_train, y_train)
    probs = xgb_ilt_style.predict_proba(X_test)[:, 1]
    results['4. ILT20-Style Params'] = brier_score_loss(y_test, probs)
    
    # ====================================================================
    # 5. ILT20-Style + Isotonic (Current v1)
    # ====================================================================
    print("[5/6] Training ILT20-Style + Isotonic (Current v1)...")
    xgb_ilt_iso = CalibratedClassifierCV(
        XGBClassifier(
            objective='binary:logistic',
            n_estimators=500, max_depth=4, learning_rate=0.005,
            subsample=0.5, colsample_bytree=0.4, min_child_weight=28,
            reg_alpha=2.8, reg_lambda=3.8, tree_method='hist',
            n_jobs=-1, verbosity=0, random_state=42
        ),
        method='isotonic', cv=5
    )
    xgb_ilt_iso.fit(X_train, y_train)
    probs = xgb_ilt_iso.predict_proba(X_test)[:, 1]
    results['5. ILT20-Style + Isotonic'] = brier_score_loss(y_test, probs)
    
    # ====================================================================
    # 6. Hyperparameter Tuning (RandomizedSearchCV)
    # ====================================================================
    print("[6/6] Running Hyperparameter Tuning (this may take a while)...")
    
    param_dist = {
        'n_estimators': [100, 200, 300, 500, 700],
        'max_depth': [2, 3, 4, 5, 6],
        'learning_rate': [0.001, 0.005, 0.01, 0.05, 0.1],
        'subsample': [0.5, 0.6, 0.7, 0.8],
        'colsample_bytree': [0.3, 0.4, 0.5, 0.6],
        'min_child_weight': [1, 5, 10, 20, 30],
        'reg_alpha': [0, 1, 2, 3],
        'reg_lambda': [1, 2, 3, 4],
    }
    
    xgb_base = XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        tree_method='hist',
        n_jobs=-1,
        verbosity=0,
        random_state=42
    )
    
    search = RandomizedSearchCV(
        xgb_base,
        param_distributions=param_dist,
        n_iter=30,
        scoring='neg_brier_score',
        cv=3,
        random_state=42,
        n_jobs=-1,
        verbose=0
    )
    
    search.fit(X_train, y_train)
    
    best_params = search.best_params_
    print(f"\nBest Parameters Found: {best_params}")
    
    # Evaluate tuned model
    probs = search.predict_proba(X_test)[:, 1]
    results['6. Tuned XGBoost'] = brier_score_loss(y_test, probs)
    
    # ====================================================================
    # 7. Tuned + Isotonic
    # ====================================================================
    print("[7/7] Training Tuned + Isotonic...")
    xgb_tuned_iso = CalibratedClassifierCV(
        XGBClassifier(**best_params, objective='binary:logistic', 
                      tree_method='hist', n_jobs=-1, verbosity=0, random_state=42),
        method='isotonic', cv=5
    )
    xgb_tuned_iso.fit(X_train, y_train)
    probs = xgb_tuned_iso.predict_proba(X_test)[:, 1]
    results['7. Tuned + Isotonic'] = brier_score_loss(y_test, probs)
    
    # ====================================================================
    # Results Summary
    # ====================================================================
    print("\n" + "="*70)
    print("WBBL OPTIMIZATION STUDY RESULTS")
    print("="*70)
    print(f"{'Configuration':<35} | {'Test Brier':<12} | {'Rank'}")
    print("-"*70)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1])
    for rank, (name, brier) in enumerate(sorted_results, 1):
        marker = "🏆 BEST" if rank == 1 else ""
        print(f"{name:<35} | {brier:.5f}      | #{rank} {marker}")
    
    print("-"*70)
    print(f"\nBest Configuration: {sorted_results[0][0]}")
    print(f"Best Brier Score:   {sorted_results[0][1]:.5f}")
    
    if 'Tuned' in sorted_results[0][0]:
        print(f"\nBest Hyperparameters:")
        for k, v in best_params.items():
            print(f"  {k}: {v}")
    
    return sorted_results[0], best_params

if __name__ == "__main__":
    run_optimization_study()
