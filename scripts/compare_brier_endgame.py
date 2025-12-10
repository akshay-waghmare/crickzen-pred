"""
Compare Brier scores for endgame scenarios:
1. Model only (no guardrail)
2. Resource-based only (DLS)
3. Guardrail blended (current approach)

This will tell us if the guardrail actually improves or hurts calibration.
"""
import pandas as pd
import numpy as np
from sklearn.metrics import brier_score_loss
import joblib

from bbl_pipeline.features.calculator import ResourceFeatureCalculator

# Load the training data
print("Loading ILT20 training data...")
df = pd.read_parquet('data/ilt_features_v2/training_sampled.parquet')

print(f"Total samples: {len(df)}")

# Load the model
model = joblib.load('models/ilt_champion_v2/champion_model.joblib')

# Get target
y = df['is_winner']

# Get features for model prediction
feature_cols = model.selected_features_
X = df[feature_cols]

# Get model predictions
model_probs = model.predict_proba(X)[:, 1]

# Get resource_win_prob from data
resource_probs = df['resource_win_prob'].values if 'resource_win_prob' in df.columns else None

if resource_probs is None:
    print("resource_win_prob not in dataset, calculating...")
    calc = ResourceFeatureCalculator()
    resource_probs = []
    for _, row in df.iterrows():
        f = calc.calculate_all_features(
            innings=int(row.get('innings', 1)),
            over=int(row.get('over', 0)),
            ball=int(row.get('ball', 0)),
            current_score=int(row.get('current_score', 0)),
            wickets_lost=int(row.get('wickets_lost', 0)),
            target_runs=row.get('target_runs') or row.get('first_innings_score')
        )
        resource_probs.append(f['resource_win_prob'])
    resource_probs = np.array(resource_probs)

# Calculate guardrail-blended predictions
def apply_guardrail(model_prob, resource_prob, over, ball, innings, runs_required=None, wickets_lost=0):
    """Apply the same guardrail logic as in predictor.py"""
    if innings != 2:
        return model_prob
    
    # Match won
    if runs_required is not None and runs_required <= 0:
        return 1.0
    
    if runs_required is not None:
        balls_remaining = (20 - over) * 6 - ball
        wickets_remaining = 10 - wickets_lost
        
        # --- ENDGAME GUARDRAILS ---
        # 1. "Victory Lap" Scenarios: Explicitly handle obvious wins
        if runs_required <= 6 and wickets_remaining >= 3:
            return max(model_prob, 0.99)
            
        if runs_required <= 12 and runs_required < balls_remaining and wickets_remaining >= 4:
            return max(model_prob, 0.98)

        # 2. Resource-based Guardrails (for other high-prob situations)
        if resource_prob > 0.97:
            floor = 0.95
            if resource_prob > 0.99: floor = 0.98
            return max(model_prob, floor)

        # 3. Loss Guardrails
        if resource_prob < 0.03:
            if resource_prob < 0.005:
                return min(model_prob, 0.01)
            elif resource_prob < 0.01:
                return min(model_prob, 0.02)
            else:
                return min(model_prob, 0.05)
    
    return model_prob

# Apply guardrail
guardrail_probs = []
for i in range(len(df)):
    row = df.iloc[i]
    
    # Infer state from features
    overs_rem = row.get('overs_remaining', 0)
    rrr = row.get('required_run_rate', 0)
    
    # Infer innings
    innings = 2 if rrr > 0 else 1
    
    # Infer over/ball
    balls_rem = round(overs_rem * 6)
    balls_bowled = 120 - balls_rem
    over = int(balls_bowled // 6)
    ball = int(balls_bowled % 6)
    
    # Infer runs required
    runs_req = rrr * overs_rem if innings == 2 else None
    
    wickets = row.get('wickets_lost', 0)
    
    gp = apply_guardrail(model_probs[i], resource_probs[i], over, ball, innings, runs_req, wickets)
    guardrail_probs.append(gp)
guardrail_probs = np.array(guardrail_probs)

# Calculate Brier scores for different segments
print("\n" + "="*80)
print("BRIER SCORE COMPARISON")
print("="*80)

# Re-create masks based on inferred data
inferred_innings = np.where(df['required_run_rate'] > 0, 2, 1)
inferred_over = (120 - np.round(df['overs_remaining'] * 6)) // 6

def calc_brier(mask, name):
    if mask.sum() == 0:
        print(f"{name:<30} | No samples")
        return None
    y_sub = y[mask]
    model_brier = brier_score_loss(y_sub, model_probs[mask])
    resource_brier = brier_score_loss(y_sub, resource_probs[mask])
    guardrail_brier = brier_score_loss(y_sub, guardrail_probs[mask])
    
    print(f"{name:<30} | Model: {model_brier:.4f} | Resource: {resource_brier:.4f} | Guardrail: {guardrail_brier:.4f}")
    return guardrail_brier

# 1. Overall
calc_brier(np.ones(len(df), dtype=bool), "Overall")

# 2. 2nd Innings
mask_inn2 = inferred_innings == 2
calc_brier(mask_inn2, "2nd Innings")

# 3. Death Overs (16-20)
mask_death = inferred_over >= 16
calc_brier(mask_death, "Death Overs (16-20)")

# 4. 2nd Innings Death Overs
mask_inn2_death = (inferred_innings == 2) & (inferred_over >= 16)
calc_brier(mask_inn2_death, "2nd Innings Death Overs")

# 5. Close Games (Resource Prob between 0.2 and 0.8)
mask_close = (resource_probs > 0.2) & (resource_probs < 0.8)
calc_brier(mask_close, "Close Games (20-80%)")

# 6. Extreme Games (Resource Prob > 0.95 or < 0.05)
mask_extreme = (resource_probs > 0.95) | (resource_probs < 0.05)
calc_brier(mask_extreme, "Extreme Games (>95% or <5%)")
