import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import joblib
import structlog

# Setup logging
logger = structlog.get_logger()

def optimize_ilt20():
    print("Loading ILT20 data...")
    df = pd.read_parquet('data/ilt_features_v2/training_sampled.parquet')
    
    # Load current champion model to get features
    champion = joblib.load('models/ilt_champion_v2/champion_model.joblib')
    features = champion.selected_features_
    
    X = df[features]
    y = df['is_winner']
    
    print(f"Data shape: {X.shape}")
    print(f"Features: {len(features)}")
    
    # Time series split for validation
    tscv = TimeSeriesSplit(n_splits=5)
    
    # 1. Baseline (Current Parameters)
    print("\nEvaluating Baseline (Current Parameters)...")
    
    # Recreate the XGBoost part of the ensemble with current params
    # (Taken from trainer.py)
    xgb_baseline = XGBClassifier(
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
    
    baseline_scores = []
    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        xgb_baseline.fit(X_train, y_train)
        probs = xgb_baseline.predict_proba(X_val)[:, 1]
        score = brier_score_loss(y_val, probs)
        baseline_scores.append(score)
        
    print(f"Baseline CV Brier Score: {np.mean(baseline_scores):.4f} (+/- {np.std(baseline_scores):.4f})")
    
    # 2. Hyperparameter Tuning
    print("\nRunning Hyperparameter Tuning for ILT20...")
    
    param_dist = {
        'n_estimators': [500, 650, 800, 1000],
        'max_depth': [2, 3, 4],  # Maybe ILT20 needs slightly deeper trees?
        'learning_rate': [0.005, 0.01, 0.011, 0.02],
        'subsample': [0.4, 0.5, 0.6],
        'colsample_bytree': [0.4, 0.5, 0.6],
        'min_child_weight': [20, 28, 35],
        'reg_alpha': [1.0, 2.8, 4.0],
        'reg_lambda': [2.0, 3.8, 5.0]
    }
    
    xgb_tune = XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        tree_method='hist',
        n_jobs=-1,
        verbosity=0,
        random_state=42
    )
    
    random_search = RandomizedSearchCV(
        xgb_tune, 
        param_distributions=param_dist, 
        n_iter=20, 
        scoring='neg_brier_score', 
        cv=tscv, 
        verbose=1,
        n_jobs=-1,
        random_state=42
    )
    
    random_search.fit(X, y)
    
    print(f"\nBest Parameters: {random_search.best_params_}")
    print(f"Best CV Brier Score: {-random_search.best_score_:.4f}")
    
    best_xgb = random_search.best_estimator_
    
    # 3. Calibration Check
    print("\nChecking Calibration on Best Model...")
    
    # Split data for calibration check (last 20% as holdout)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # Fit best uncalibrated model
    best_xgb.fit(X_train, y_train)
    prob_uncal = best_xgb.predict_proba(X_test)[:, 1]
    brier_uncal = brier_score_loss(y_test, prob_uncal)
    print(f"Uncalibrated Holdout Brier: {brier_uncal:.4f}")
    
    # Isotonic
    iso = CalibratedClassifierCV(best_xgb, method='isotonic', cv=3)
    iso.fit(X_train, y_train)
    prob_iso = iso.predict_proba(X_test)[:, 1]
    brier_iso = brier_score_loss(y_test, prob_iso)
    print(f"Isotonic Calibration Brier: {brier_iso:.4f}")
    
    # Sigmoid (Platt)
    sig = CalibratedClassifierCV(best_xgb, method='sigmoid', cv=3)
    sig.fit(X_train, y_train)
    prob_sig = sig.predict_proba(X_test)[:, 1]
    brier_sig = brier_score_loss(y_test, prob_sig)
    print(f"Sigmoid Calibration Brier:  {brier_sig:.4f}")
    
    # Recommendation
    print("\n" + "="*60)
    print("RECOMMENDATION")
    print("="*60)
    
    improvement = np.mean(baseline_scores) - (-random_search.best_score_)
    if improvement > 0.0005:
        print(f"1. UPDATE HYPERPARAMETERS: Found better params (improvement: {improvement:.4f})")
        print(random_search.best_params_)
    else:
        print("1. KEEP CURRENT HYPERPARAMETERS: No significant improvement found.")
        
    if min(brier_iso, brier_sig) < brier_uncal - 0.0005:
        method = 'isotonic' if brier_iso < brier_sig else 'sigmoid'
        print(f"2. ENABLE CALIBRATION: {method} calibration improves Brier score.")
    else:
        print("2. NO CALIBRATION: Post-hoc calibration does not improve performance.")

if __name__ == "__main__":
    optimize_ilt20()
