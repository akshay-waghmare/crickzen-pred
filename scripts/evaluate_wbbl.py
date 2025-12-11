"""
Evaluate WBBL Model - Detailed Brier Score Analysis
"""
import pandas as pd
import numpy as np
from sklearn.metrics import brier_score_loss
import joblib

def evaluate_wbbl_model():
    print("Loading WBBL training data...")
    df = pd.read_parquet('data/wbbl_features_v2/training_sampled.parquet')
    
    print("Loading WBBL model...")
    model = joblib.load('models/wbbl_champion_v1/champion_model.joblib')
    
    # Get features
    feature_cols = model.selected_features_
    X = df[feature_cols].fillna(0)
    y = df['is_winner']
    
    # Predictions
    probs = model.predict_proba(X)[:, 1]
    
    # Resource-based probability
    resource_probs = df['resource_win_prob'].values if 'resource_win_prob' in df.columns else np.full(len(df), 0.5)
    
    # Infer innings from required_run_rate
    innings = np.where(df['required_run_rate'] > 0, 2, 1) if 'required_run_rate' in df.columns else np.ones(len(df))
    
    # Infer over from overs_remaining
    if 'overs_remaining' in df.columns:
        overs_rem = df['overs_remaining']
        balls_rem = np.round(overs_rem * 6)
        over = (120 - balls_rem) // 6
    else:
        over = np.zeros(len(df))
    
    print("\n" + "="*70)
    print("WBBL MODEL - DETAILED BRIER SCORE ANALYSIS")
    print("="*70)
    
    def calc_brier(mask, name):
        if mask.sum() == 0:
            print(f"{name:<35} | No samples")
            return None
        y_sub = y[mask]
        model_brier = brier_score_loss(y_sub, probs[mask])
        resource_brier = brier_score_loss(y_sub, resource_probs[mask])
        
        better = "Model" if model_brier < resource_brier else "Resource"
        
        print(f"{name:<35} | Model: {model_brier:.4f} | Resource: {resource_brier:.4f} | Better: {better}")
        return model_brier
    
    # 1. Overall
    calc_brier(np.ones(len(df), dtype=bool), "Overall")
    
    # 2. By Innings
    mask_inn1 = innings == 1
    mask_inn2 = innings == 2
    calc_brier(mask_inn1, "1st Innings")
    calc_brier(mask_inn2, "2nd Innings")
    
    # 3. By Phase
    mask_powerplay = over < 6
    mask_middle = (over >= 6) & (over < 15)
    mask_death = over >= 15
    
    calc_brier(mask_powerplay, "Powerplay (0-5)")
    calc_brier(mask_middle, "Middle Overs (6-14)")
    calc_brier(mask_death, "Death Overs (15-20)")
    
    # 4. 2nd Innings Phases
    calc_brier(mask_inn2 & mask_death, "2nd Innings Death Overs")
    
    # 5. Close games (Resource 20-80%)
    mask_close = (resource_probs > 0.2) & (resource_probs < 0.8)
    calc_brier(mask_close, "Close Games (20-80%)")
    
    # 6. Extreme games
    mask_extreme = (resource_probs > 0.95) | (resource_probs < 0.05)
    calc_brier(mask_extreme, "Extreme Games (>95% or <5%)")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    evaluate_wbbl_model()
