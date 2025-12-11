"""
Train WBBL Champion Model v4
- Uses corrected ResourceFeatureCalculator (0 overs = 0 resources)
- Deduplicated training data
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

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bbl_pipeline.features.calculator import ResourceFeatureCalculator

def main():
    print("="*70)
    print("WBBL Champion Model v4 Training")
    print("With corrected ResourceFeatureCalculator")
    print("="*70)

    # Load existing training data
    train_path = Path("data/wbbl_features_v3/training.parquet")
    if not train_path.exists():
        train_path = Path("data/wbbl_features_v2/training.parquet")

    print(f"Loading training data from {train_path}...")
    df = pd.read_parquet(train_path)
    print(f"Loaded {len(df)} rows")

    # Check target column
    target_col = None
    for col in ["is_winner", "batting_team_won", "target", "won", "winner"]:
        if col in df.columns:
            target_col = col
            break
    
    if target_col is None:
        print("ERROR: No target column found!")
        print(f"Available columns: {list(df.columns)}")
        return
    
    print(f"Target column: {target_col}")
    
    # Remove duplicates
    dup_cols = ["match_id", "innings", "over", "ball"]
    available_dup_cols = [c for c in dup_cols if c in df.columns]
    if available_dup_cols:
        before = len(df)
        df = df.drop_duplicates(subset=available_dup_cols, keep="first")
        print(f"After dedup: {len(df)} rows (removed {before - len(df)})")

    # Regenerate resource features with the updated calculator
    print("\nRegenerating resource features with corrected calculator...")
    calc = ResourceFeatureCalculator()

    resource_cols = ["resource_pct", "resource_win_prob", "overs_remaining", 
                     "resources_remaining", "pressure_index", "dls_pressure_index",
                     "batting_team_situation_wr", "bowling_team_situation_wr"]

    # Initialize columns if missing
    for col in resource_cols:
        if col not in df.columns:
            df[col] = 0.0

    # Get column name mappings
    over_col = "over" if "over" in df.columns else "over_number"
    ball_col = "ball" if "ball" in df.columns else "ball_number"
    score_col = "current_score" if "current_score" in df.columns else "total_score"
    wickets_col = "wickets_lost" if "wickets_lost" in df.columns else "total_wickets"
    
    print(f"Column mappings: over={over_col}, ball={ball_col}, score={score_col}, wickets={wickets_col}")

    # Regenerate for all rows
    new_resource_pct = []
    new_resource_win_prob = []
    new_batting_situation_wr = []
    new_bowling_situation_wr = []
    
    for idx in range(len(df)):
        row = df.iloc[idx]
        innings = int(row.get("innings", 1))
        over = int(row.get(over_col, 0))
        ball = int(row.get(ball_col, 0))
        current_score = int(row.get(score_col, 0))
        wickets_lost = int(row.get(wickets_col, 0))
        target_runs = row.get("target_runs") if pd.notna(row.get("target_runs")) else None
        
        features = calc.calculate_all_features(
            innings=innings,
            over=over,
            ball=ball,
            current_score=current_score,
            wickets_lost=wickets_lost,
            target_runs=target_runs
        )
        
        new_resource_pct.append(features.get("resource_pct", 0.0))
        new_resource_win_prob.append(features.get("resource_win_prob", 0.5))
        new_batting_situation_wr.append(features.get("resource_win_prob", 0.5))
        new_bowling_situation_wr.append(1.0 - features.get("resource_win_prob", 0.5))
        
        if idx % 5000 == 0:
            print(f"  Processed {idx}/{len(df)} rows...")

    df["resource_pct"] = new_resource_pct
    df["resource_win_prob"] = new_resource_win_prob
    df["batting_team_situation_wr"] = new_batting_situation_wr
    df["bowling_team_situation_wr"] = new_bowling_situation_wr
    
    print("Done regenerating features!")

    # Check the end-game samples
    innings_col = "innings" if "innings" in df.columns else "innings_number"
    if innings_col in df.columns:
        end_game = df[(df[innings_col] == 2) & (df[over_col] >= 19)]
        print(f"\nEnd-game samples (over >= 19): {len(end_game)}")
        if len(end_game) > 0:
            print(f"  resource_pct range: {end_game['resource_pct'].min():.2f} - {end_game['resource_pct'].max():.2f}")
            print(f"  resource_win_prob range: {end_game['resource_win_prob'].min():.2f} - {end_game['resource_win_prob'].max():.2f}")
    else:
        # Just check by overs_remaining
        end_game = df[df["overs_remaining"] <= 1]
        print(f"\nEnd-game samples (overs_remaining <= 1): {len(end_game)}")
        if len(end_game) > 0:
            print(f"  resource_pct range: {end_game['resource_pct'].min():.2f} - {end_game['resource_pct'].max():.2f}")
            print(f"  resource_win_prob range: {end_game['resource_win_prob'].min():.2f} - {end_game['resource_win_prob'].max():.2f}")

    # Define features for training
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
        # Venue stats
        "batsman_venue_avg", "batsman_venue_sr",
        "bowler_venue_econ", "bowler_venue_sr",
        # Matchup stats
        "batsman_vs_team_avg", "bowler_vs_team_econ",
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
        "situation_advantage", "projected_vs_venue_avg",
    ]
    
    # Filter to available features
    available_features = [f for f in feature_cols if f in df.columns]
    print(f"\nUsing {len(available_features)} features for training")
    
    # Prepare data
    X = df[available_features].copy()
    y = df[target_col].copy()
    
    # Fill NaN
    X = X.fillna(0)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    # Train XGBoost
    print("\nTraining XGBoost model...")
    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        eval_metric="logloss",
        early_stopping_rounds=30,
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=50
    )
    
    # Evaluate
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
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
    output_dir = Path("models/wbbl_champion_v4")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    joblib.dump(model, output_dir / "champion_model.joblib")
    
    # Save metadata
    metadata = {
        "model_name": "XGBoost_Tuned_v4",
        "version": "4.0",
        "features": available_features,
        "metrics": {
            "test_brier": float(brier),
            "test_logloss": float(logloss),
            "test_auc": float(auc),
        },
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "notes": "Trained with corrected ResourceFeatureCalculator (0 overs = 0 resources)"
    }
    
    with open(output_dir / "champion_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    # Copy feature store reference
    print(f"\nModel saved to {output_dir}")
    print("Done!")

if __name__ == "__main__":
    main()
