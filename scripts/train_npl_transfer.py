"""
Train NPL Model using Transfer Learning from ILT20.
Uses the robust ILT20 model as a base, and fine-tunes with NPL-specific data.
Target Brier Score: < 0.175
"""
import pandas as pd
import numpy as np
from pathlib import Path
from xgboost import XGBClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, GroupKFold, cross_val_score
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
import joblib
import json
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def train_transfer_learning():
    print("="*70)
    print("NPL Transfer Learning (Base: ILT20)")
    print("="*70)

    # 1. Load Data and Base Model
    npl_path = Path("data/npl_features_v1/training.parquet")
    base_model_path = Path("models/ilt_champion_v2/champion_model.joblib")
    
    if not npl_path.exists():
        print(f"ERROR: NPL data not found at {npl_path}")
        return
    if not base_model_path.exists():
        print(f"ERROR: ILT20 model not found at {base_model_path}")
        return

    print("Loading NPL data...")
    df = pd.read_parquet(npl_path)
    print(f"Loaded {len(df)} NPL rows")
    
    print("Loading ILT20 Base Model...")
    base_model = joblib.load(base_model_path)
    
    # Get features expected by base model
    if hasattr(base_model, 'selected_features_'):
        base_features = base_model.selected_features_
    else:
        # Fallback if attribute missing (shouldn't happen with our pipeline)
        print("WARNING: Base model has no selected_features_, trying to infer...")
        # Try to load metadata
        meta_path = base_model_path.parent / "champion_metadata.json"
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)
                base_features = meta.get('features', [])
        else:
            print("ERROR: Could not determine base model features.")
            return

    print(f"Base model expects {len(base_features)} features")
    
    # 2. Prepare NPL data for Base Model
    # Ensure all columns exist
    X_base = df.copy()
    missing_cols = [c for c in base_features if c not in X_base.columns]
    if missing_cols:
        print(f"WARNING: Missing columns in NPL data: {missing_cols}")
        for c in missing_cols:
            X_base[c] = 0
            
    X_base = X_base[base_features].fillna(0)
    
    # 3. Generate Base Predictions
    print("Generating base predictions (Transfer Step)...")
    base_probs = base_model.predict_proba(X_base)[:, 1]
    df['base_prob'] = base_probs
    
    print(f"Base Model Performance on NPL Data:")
    print(f"  Brier: {brier_score_loss(df['is_winner'], base_probs):.4f}")
    print(f"  AUC:   {roc_auc_score(df['is_winner'], base_probs):.4f}")
    
    # 4. Train Correction Model (Stacking)
    # Features: Base Prob + NPL Specifics (Team Strength, Venue)
    transfer_features = [
        'base_prob',
        'team_strength_diff',
        'batting_team_win_rate',
        'bowling_team_win_rate',
        'batting_team_situation_wr',
        'bowling_team_situation_wr',
        'venue_avg_score',
        'venue_bat_first_win_rate',
        'home_advantage' # If available
    ]
    
    # Filter available
    transfer_features = [f for f in transfer_features if f in df.columns]
    print(f"\nTraining Correction Model with features: {transfer_features}")
    
    X_transfer = df[transfer_features].copy()
    y = df['is_winner'].copy()
    groups = df['match_id'].copy()
    
    # Split by match
    match_ids = df['match_id'].unique()
    train_matches, test_matches = train_test_split(match_ids, test_size=0.2, random_state=42)
    
    train_mask = df['match_id'].isin(train_matches)
    test_mask = df['match_id'].isin(test_matches)
    
    X_train, y_train = X_transfer[train_mask], y[train_mask]
    X_test, y_test = X_transfer[test_mask], y[test_mask]
    
    print(f"Train: {len(X_train)} balls ({len(train_matches)} matches)")
    print(f"Test:  {len(X_test)} balls ({len(test_matches)} matches)")
    
    # Model A: Logistic Regression (Simple, Robust)
    lr = LogisticRegression(C=1.0, random_state=42)
    lr.fit(X_train, y_train)
    probs_lr = lr.predict_proba(X_test)[:, 1]
    brier_lr = brier_score_loss(y_test, probs_lr)
    
    # Model B: Shallow XGBoost (Non-linear corrections)
    xgb = XGBClassifier(
        n_estimators=100,
        max_depth=2,
        learning_rate=0.05,
        subsample=0.7,
        colsample_bytree=0.7,
        random_state=42,
        eval_metric='logloss'
    )
    # Calibrate XGB
    cal_xgb = CalibratedClassifierCV(xgb, method='sigmoid', cv=3)
    cal_xgb.fit(X_train, y_train)
    probs_xgb = cal_xgb.predict_proba(X_test)[:, 1]
    brier_xgb = brier_score_loss(y_test, probs_xgb)
    
    print("\n" + "="*70)
    print("TRANSFER LEARNING RESULTS")
    print("="*70)
    print(f"Base Model Only:      {brier_score_loss(y_test, base_probs[test_mask]):.4f}")
    print(f"Logistic Correction:  {brier_lr:.4f}")
    print(f"XGBoost Correction:   {brier_xgb:.4f}")
    
    # Select Best
    best_model = None
    best_brier = min(brier_lr, brier_xgb)
    model_name = ""
    
    if best_brier == brier_lr:
        best_model = lr
        model_name = "Transfer_Logistic"
    else:
        best_model = cal_xgb
        model_name = "Transfer_XGBoost"
        
    if best_brier < 0.175:
        print(f"\nSUCCESS: Target 0.175 reached with {model_name}!")
    else:
        print(f"\nWARNING: Target 0.175 not reached. Best: {best_brier:.4f}")
        
    # Save
    output_dir = Path("models/npl_champion_v1")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # We need to save a wrapper that does the two-step prediction
    # Since we can't easily pickle a custom class without defining it in a shared module,
    # we'll save the correction model and the feature list.
    # The inference script will need to load Base + Correction.
    
    joblib.dump(best_model, output_dir / "correction_model.joblib")
    
    metadata = {
        "model_name": f"NPL_{model_name}",
        "version": "1.2_Transfer",
        "base_model": "ilt_champion_v2",
        "correction_features": transfer_features,
        "metrics": {
            "test_brier": float(best_brier),
            "test_auc": float(roc_auc_score(y_test, best_model.predict_proba(X_test)[:, 1]))
        }
    }
    
    with open(output_dir / "champion_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
        
    print(f"Correction model saved to {output_dir}")
    print("NOTE: Inference requires loading both ILT20 base model and this correction model.")

if __name__ == "__main__":
    train_transfer_learning()
