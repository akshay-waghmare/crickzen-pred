"""
Train NPL (Nepal Premier League) Champion Model v1.
Uses XGBoost with Isotonic Calibration, similar to WBBL/ILT20 models.
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

def train_npl_v1():
    print("="*70)
    print("NPL Champion Model v1 Training")
    print("="*70)

    # Load training data
    # Use full ball-by-ball data for NPL since dataset is small (46 matches)
    train_path = Path("data/npl_features_v1/training.parquet")
    if not train_path.exists():
        print(f"ERROR: Training data not found at {train_path}")
        print("Please run generate_npl_features.py first.")
        return

    print(f"Loading training data from {train_path}...")
    df = pd.read_parquet(train_path)
    print(f"Loaded {len(df)} rows")

    # Define features (same as ILT20/WBBL v3/v4)
    feature_cols = [
        # Resource features
        "resource_pct", "resource_win_prob", "overs_remaining", "resources_remaining",
        "pressure_index", "batting_team_situation_wr", "bowling_team_situation_wr",
        # Score features  
        "current_run_rate", "required_run_rate", "run_rate_diff",
        # Match phase
        "is_powerplay", "is_middle_overs", "is_death_overs",
        # Player stats
        "batsman_rolling_avg", "batsman_rolling_sr", 
        "bowler_rolling_econ", "bowler_rolling_sr",
        # Team stats
        "batting_team_win_rate", "bowling_team_win_rate",
        # Derived features
        "score_per_wicket", "projected_score", "score_vs_par",
        "chase_difficulty", "dls_pressure_index",
        "crr_times_res", "rrr_times_wickets", "wickets_times_balls",
        # Rolling recent form
        "runs_last_12", "runs_last_18", "wickets_last_12", "wickets_last_30",
        "boundary_pct_last_18", "acceleration_potential",
        # Team strength
        "team_strength_diff", "batting_pair_strength",
        "projected_vs_venue_avg",
    ]
    
    # Filter to available features
    available_features = [f for f in feature_cols if f in df.columns]
    print(f"\nUsing {len(available_features)} features for training")
    
    # Prepare data
    X = df[available_features].copy()
    y = df['is_winner'].copy()
    
    # Fill NaN
    X = X.fillna(0)
    
    # Split data by MATCH ID to prevent leakage
    # We must ensure all balls from the same match are in the same set
    if 'match_id' in df.columns:
        print("Splitting by match_id to prevent data leakage...")
        match_ids = df['match_id'].unique()
        train_matches, test_matches = train_test_split(match_ids, test_size=0.2, random_state=42)
        
        train_mask = df['match_id'].isin(train_matches)
        test_mask = df['match_id'].isin(test_matches)
        
        X_train = X[train_mask]
        y_train = y[train_mask]
        X_test = X[test_mask]
        y_test = y[test_mask]
        print(f"Split by match: {len(train_matches)} train matches, {len(test_matches)} test matches")
    else:
        print("WARNING: match_id not found, falling back to random split (HIGH RISK OF LEAKAGE)")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
    print(f"Train: {len(X_train)} balls, Test: {len(X_test)} balls")
    
    # Train XGBoost (Optimized parameters from ILT20/WBBL)
    print("\nTraining XGBoost model...")
    xgb_model = XGBClassifier(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.005,
        subsample=0.5,
        colsample_bytree=0.4,
        min_child_weight=28,
        gamma=0.1,
        reg_alpha=2.8,
        reg_lambda=3.8,
        random_state=42,
        eval_metric="logloss",
        tree_method='hist',
        n_jobs=-1
    )
    
    # Calibrate model (Isotonic)
    print("Calibrating model (Isotonic)...")
    calibrated_model = CalibratedClassifierCV(
        xgb_model, 
        method='isotonic', 
        cv=5
    )
    
    calibrated_model.fit(X_train, y_train)
    
    # Evaluate
    y_pred_proba = calibrated_model.predict_proba(X_test)[:, 1]
    
    brier = brier_score_loss(y_test, y_pred_proba)
    logloss = log_loss(y_test, y_pred_proba)
    auc = roc_auc_score(y_test, y_pred_proba)
    
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    print(f"Test Brier Score: {brier:.4f}")
    print(f"Test Log Loss: {logloss:.4f}")
    print(f"Test AUC: {auc:.4f}")
    
    # Check end-game calibration
    test_df = X_test.copy()
    test_df["y_true"] = y_test.values
    test_df["y_pred"] = y_pred_proba
    
    end_game_test = test_df[test_df["overs_remaining"] <= 1]
    if len(end_game_test) > 0:
        end_game_brier = brier_score_loss(end_game_test["y_true"], end_game_test["y_pred"])
        print(f"\nEnd-game Brier (overs_remaining <= 1): {end_game_brier:.4f} ({len(end_game_test)} samples)")
    
    # Save model
    output_dir = Path("models/npl_champion_v1")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Attach selected features to model for inference
    calibrated_model.selected_features_ = available_features
    
    joblib.dump(calibrated_model, output_dir / "champion_model.joblib")
    
    # Save metadata
    metadata = {
        "model_name": "NPL_XGBoost_Isotonic_v1",
        "version": "1.0",
        "features": available_features,
        "metrics": {
            "test_brier": float(brier),
            "test_logloss": float(logloss),
            "test_auc": float(auc),
        },
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "notes": "Initial NPL model trained on available data"
    }
    
    with open(output_dir / "champion_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nModel saved to {output_dir}")
    print("Done!")

if __name__ == "__main__":
    train_npl_v1()
