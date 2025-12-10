"""
Compare Brier scores for endgame scenarios:
1. Model only (no guardrail)
2. Resource-based only (DLS)  
3. Guardrail blended (current approach)

This will tell us if the resource-based approach is better in endgame.
"""
import pandas as pd
import numpy as np
from sklearn.metrics import brier_score_loss
import joblib

# Load the training data (already 2nd innings only)
print("Loading ILT20 training data...")
df = pd.read_parquet('data/ilt_features_v2/training_sampled.parquet')
print(f"Total samples: {len(df)}")
print(f"Columns: {df.columns.tolist()[:10]}...")

# Load the model
model = joblib.load('models/ilt_champion_v2/champion_model.joblib')

# Get target
y = df['is_winner'].values

# Get features for model prediction  
feature_cols = model.selected_features_
X = df[feature_cols]

# Get model predictions
model_probs = model.predict_proba(X)[:, 1]

# Get resource_win_prob from data
resource_probs = df['resource_win_prob'].values

# Calculate over from overs_remaining (20 over match)
df['over'] = 20 - df['overs_remaining']

# Calculate guardrail-blended predictions
def apply_guardrail(model_prob, resource_prob, over):
    """Apply the same guardrail logic as in predictor.py for 2nd innings"""
    blended = model_prob
    
    # Death overs (over >= 16)
    if over >= 16:
        overs_into_death = over - 16
        resource_weight = min(0.90, 0.70 + (overs_into_death * 0.067))
        blended = resource_weight * resource_prob + (1 - resource_weight) * model_prob
    
    # Very easy chase
    if resource_prob > 0.95:
        blended = 0.80 * resource_prob + 0.20 * blended
    # Very hard chase
    elif resource_prob < 0.10:
        blended = 0.80 * resource_prob + 0.20 * blended
    
    return blended

# Apply guardrail
guardrail_probs = np.array([
    apply_guardrail(m, r, o) 
    for m, r, o in zip(model_probs, resource_probs, df['over'])
])

# Calculate Brier scores for different segments
print("\n" + "="*80)
print("BRIER SCORE COMPARISON")
print("="*80)

def calc_brier(mask, name):
    if mask.sum() == 0:
        print(f"\n{name}: NO DATA")
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
    
    # Show improvement
    if guardrail_brier < model_brier:
        pct = ((model_brier - guardrail_brier) / model_brier) * 100
        print(f"  → Guardrail {pct:.1f}% better than model")
    else:
        pct = ((guardrail_brier - model_brier) / model_brier) * 100
        print(f"  → Guardrail {pct:.1f}% worse than model")
    
    return model_brier, resource_brier, guardrail_brier

# Overall (all 2nd innings data)
calc_brier(np.ones(len(df), dtype=bool), "ALL 2ND INNINGS DATA")

# Powerplay (over 0-5)
powerplay = df['is_powerplay'] == 1
calc_brier(powerplay, "POWERPLAY (overs 0-5)")

# Middle overs (6-15)
middle = df['is_middle_overs'] == 1
calc_brier(middle, "MIDDLE OVERS (6-15)")

# Death overs (16-20) - WHERE GUARDRAIL APPLIES
death = df['is_death_overs'] == 1
calc_brier(death, "DEATH OVERS (16-20) - Guardrail Active")

# Break down by over
print("\n" + "-"*80)
print("BREAKDOWN BY OVER:")
print("-"*80)

for o in range(16, 21):
    over_mask = df['over'] == o
    if over_mask.sum() > 0:
        calc_brier(over_mask, f"OVER {o}")

# Easy chases
print("\n" + "-"*80)
print("BY CHASE DIFFICULTY:")
print("-"*80)

easy = resource_probs > 0.90
calc_brier(easy, "EASY CHASES (resource > 90%)")

medium = (resource_probs >= 0.20) & (resource_probs <= 0.80)
calc_brier(medium, "MEDIUM CHASES (20%-80%)")

hard = resource_probs < 0.20
calc_brier(hard, "HARD CHASES (resource < 20%)")

# Extreme cases (where guardrail especially applies)
very_easy = resource_probs > 0.95
calc_brier(very_easy, "VERY EASY (resource > 95%)")

very_hard = resource_probs < 0.10
calc_brier(very_hard, "VERY HARD (resource < 10%)")

# Show distribution
print("\n" + "="*80)
print("SUMMARY:")
print("="*80)
print(f"\nOverall Brier Scores:")
print(f"  Model:     {brier_score_loss(y, model_probs):.4f}")
print(f"  Resource:  {brier_score_loss(y, resource_probs):.4f}")
print(f"  Guardrail: {brier_score_loss(y, guardrail_probs):.4f}")

death_count = death.sum()
all_count = len(df)
print(f"\nDeath overs represent {death_count}/{all_count} = {100*death_count/all_count:.1f}% of data")

# Show where guardrail changes predictions most
diff = np.abs(guardrail_probs - model_probs)
print(f"\nGuardrail adjustment statistics:")
print(f"  Max adjustment: {diff.max():.4f}")
print(f"  Mean adjustment: {diff.mean():.4f}")
print(f"  Adjustments > 0.1: {(diff > 0.1).sum()}")
print(f"  Adjustments > 0.2: {(diff > 0.2).sum()}")

print("\n" + "="*80)
print("CONCLUSION:")
print("Lower Brier score = better calibration")
print("If Guardrail <= Model in death overs, the guardrail is helping!")
print("="*80)
