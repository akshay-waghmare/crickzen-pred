"""
Diagnose which features are causing probability to drop after a six.

Strategy: Compare SHAP-like contributions by setting each feature to its
"before" value one at a time, and seeing how much the prediction changes.
"""
import pandas as pd
import numpy as np
import joblib
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState
from bbl_pipeline.inference.realtime_mapper import RealTimeFeatureMapper
from bbl_pipeline.features.store import InMemoryFeatureStore

# Load model
model = joblib.load('models/ilt_champion_v2/champion_model.joblib')

# Load predictor for feature generation
predictor = Predictor.load("models/ilt_champion_v2", "data/ilt_feature_store_v2")

# Build features for before and after states
def get_features(score, over, ball, target):
    scraped = {
        'innings_num': 2,
        'over_number': over,
        'ball_number': ball,
        'total_score': score,
        'total_wickets': 0,
        'current_batsman': 'Unknown',
        'non_striker': 'Unknown', 
        'current_bowler': 'Unknown',
        'batting_team': 'Gulf Giants',
        'bowling_team': 'Sharjah Warriorz',
        'venue': 'Dubai International Cricket Stadium',
        'target_score': target,
        'runs_needed': target - score,
    }
    return predictor.feature_mapper.create_feature_dataframe(scraped)

# Get features for both states
X_before = get_features(23, 2, 0, 158)
X_after = get_features(29, 2, 1, 158)

# Get predictions
prob_before = model.predict_proba(X_before)[0, 1]
prob_after = model.predict_proba(X_after)[0, 1]

print(f"Baseline - Before six: {prob_before*100:.2f}%")
print(f"Baseline - After six:  {prob_after*100:.2f}%")
print(f"Change: {(prob_after - prob_before)*100:+.2f}%")
print()

# Now find which feature changes are causing the drop
# Start with "after" features and swap each one to "before" value
# See how much prediction changes

print("="*80)
print("FEATURE CONTRIBUTION ANALYSIS")
print("="*80)
print(f"{'Feature':<30} {'Before':<15} {'After':<15} {'Delta':<15} {'Swap Impact':<15}")
print("-"*90)

feature_impacts = []
for col in X_before.columns:
    # Skip non-numeric features
    if X_before[col].dtype == 'object':
        continue
        
    val_before = X_before[col].iloc[0]
    val_after = X_after[col].iloc[0]
    delta = val_after - val_before
    
    # If feature didn't change, skip
    if abs(delta) < 1e-6:
        continue
    
    # Create "swapped" version - after features but with this one set to "before" value
    X_swapped = X_after.copy()
    X_swapped[col] = val_before
    
    prob_swapped = model.predict_proba(X_swapped)[0, 1]
    
    # How much did swapping this feature back change the probability?
    # Positive means this feature was REDUCING probability
    impact = prob_swapped - prob_after
    
    feature_impacts.append((col, val_before, val_after, delta, impact))

# Sort by absolute impact
feature_impacts.sort(key=lambda x: abs(x[4]), reverse=True)

for col, val_before, val_after, delta, impact in feature_impacts:
    direction = "↑" if impact > 0 else "↓"
    bad_mark = "🔴" if impact > 0.01 else ""  # Feature is hurting us
    print(f"{col:<30} {val_before:<15.4f} {val_after:<15.4f} {delta:<+15.4f} {impact*100:<+14.2f}% {bad_mark}")

print()
print("Features with 🔴 are REDUCING probability after the six (counter-intuitive)")
