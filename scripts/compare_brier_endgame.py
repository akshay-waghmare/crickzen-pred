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
def apply_guardrail(model_prob, resource_prob, over, innings, runs_required=None):
    """Apply the same guardrail logic as in predictor.py"""
    if innings != 2:
        return model_prob
    
    # Match won
    if runs_required is not None and runs_required <= 0:
        return 1.0
    
    # Death overs (over >= 16)
    if over >= 16:
        overs_into_death = over - 16
        resource_weight = min(0.90, 0.70 + (overs_into_death * 0.067))
        if resource_prob > 0.90 or resource_prob < 0.15:
            return resource_weight * resource_prob + (1 - resource_weight) * model_prob
    
    # Very easy/hard chase
    if resource_prob > 0.95 and model_prob < resource_prob:
        return 0.80 * resource_prob + 0.20 * model_prob
    elif resource_prob < 0.10 and model_prob > resource_prob:
        return 0.80 * resource_prob + 0.20 * model_prob
    
    return model_prob

# Apply guardrail
guardrail_probs = []
for i in range(len(df)):
    over = df.iloc[i].get('over', 0)
    innings = df.iloc[i].get('innings', 1)
    runs_req = df.iloc[i].get('runs_required', None)
    
    gp = apply_guardrail(model_probs[i], resource_probs[i], over, innings, runs_req)
    guardrail_probs.append(gp)
guardrail_probs = np.array(guardrail_probs)

# Calculate Brier scores for different segments
print("\n" + "="*80)
print("BRIER SCORE COMPARISON")
print("="*80)

def calc_brier(mask, name):
    if mask.sum() == 0:
        return None
    y_sub = y[mask]
    model_brier = brier_score_loss(y_sub, model_probs[mask])
    resource_brier = brier_score_loss(y_sub, resource_probs[mask])
    guardrail_brier = brier_score_loss(y_sub, guardrail_probs[mask])
    
    print(f"\n{name} (n={mask.sum()}):")
    print(f"  Model only:     {model_brier:.4f}")
    print(f"  Resource only:  {resource_brier:.4f}")
    print(f"  Guardrail:      {guardrail_brier:.4f}")
    
    best = min(model_brier, resource_brier, guardrail_brier)
    if guardrail_brier == best:
        print(f"  → Best: Guardrail ✓")
    elif model_brier == best:
        print(f"  → Best: Model")
    else:
        print(f"  → Best: Resource")
    
    return model_brier, resource_brier, guardrail_brier

# Overall
calc_brier(np.ones(len(df), dtype=bool), "ALL DATA")

# 2nd innings only
innings_2 = df['innings'] == 2
calc_brier(innings_2, "2ND INNINGS ONLY")

# Death overs (over >= 16)
death_overs = (df['over'] >= 16) & (df['innings'] == 2)
calc_brier(death_overs, "DEATH OVERS (16-20, 2nd innings)")

# Over 18-19 (last 2 overs)
last_2_overs = (df['over'] >= 18) & (df['innings'] == 2)
calc_brier(last_2_overs, "LAST 2 OVERS (18-19, 2nd innings)")

# Easy chases (resource > 90%)
easy_chase = (resource_probs > 0.90) & (df['innings'] == 2)
calc_brier(easy_chase, "EASY CHASES (resource > 90%)")

# Hard chases (resource < 20%)
hard_chase = (resource_probs < 0.20) & (df['innings'] == 2)
calc_brier(hard_chase, "HARD CHASES (resource < 20%)")

# Powerplay (over < 6)
powerplay = (df['over'] < 6) & (df['innings'] == 2)
calc_brier(powerplay, "POWERPLAY (2nd innings)")

# Middle overs
middle = (df['over'] >= 6) & (df['over'] < 16) & (df['innings'] == 2)
calc_brier(middle, "MIDDLE OVERS (6-15, 2nd innings)")

print("\n" + "="*80)
print("CONCLUSION:")
print("Lower Brier score = better calibration")
print("="*80)
