import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import brier_score_loss
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve

# Load data
df = pd.read_parquet('data/ilt_features_v2/training_sampled.parquet')
y_true = df['is_winner'].values

# Load models
print("Loading models...")
model_v2 = joblib.load('models/ilt_champion_v2/champion_model.joblib')
model_v3 = joblib.load('models/ilt_champion_v3/champion_model.joblib')

features = model_v2.selected_features_
X = df[features]

# Predict
print("Predicting...")
prob_v2 = model_v2.predict_proba(X)[:, 1]
prob_v3 = model_v3.predict_proba(X)[:, 1]

# Calculate Brier scores
brier_v2 = brier_score_loss(y_true, prob_v2)
brier_v3 = brier_score_loss(y_true, prob_v3)

print("\n" + "="*60)
print("MODEL COMPARISON: v2 vs v3")
print("="*60)
print(f"v2 (Baseline):  {brier_v2:.4f}")
print(f"v3 (Optimized): {brier_v3:.4f}")

improvement = brier_v2 - brier_v3
pct_improvement = (improvement / brier_v2) * 100

if improvement > 0:
    print(f"\nSUCCESS: v3 is better by {improvement:.4f} ({pct_improvement:.1f}%)")
else:
    print(f"\nFAILURE: v3 is worse by {-improvement:.4f}")

# Detailed breakdown
def get_brier(mask, name):
    if mask.sum() == 0: return
    s2 = brier_score_loss(y_true[mask], prob_v2[mask])
    s3 = brier_score_loss(y_true[mask], prob_v3[mask])
    diff = s2 - s3
    winner = "v3" if diff > 0 else "v2"
    print(f"{name:<25} v2:{s2:.4f}  v3:{s3:.4f}  Winner: {winner}")

print("\n--- Breakdown ---")
# Innings
mask_1st = df['required_run_rate'] == 0
mask_2nd = df['required_run_rate'] != 0
get_brier(mask_1st, "1st Innings")
get_brier(mask_2nd, "2nd Innings")

# Death Overs
if 'is_death_overs' in df.columns:
    mask_death = df['is_death_overs'] == 1
    get_brier(mask_death, "Death Overs")

# Plot Calibration
plt.figure(figsize=(10, 8))
plt.plot([0, 1], [0, 1], linestyle='--', color='gray')

p2_true, p2_pred = calibration_curve(y_true, prob_v2, n_bins=10)
plt.plot(p2_pred, p2_true, marker='o', label=f'v2 (Brier={brier_v2:.4f})')

p3_true, p3_pred = calibration_curve(y_true, prob_v3, n_bins=10)
plt.plot(p3_pred, p3_true, marker='s', label=f'v3 (Brier={brier_v3:.4f})')

plt.xlabel('Mean Predicted Probability')
plt.ylabel('Fraction of Positives')
plt.title('Calibration Comparison: v2 vs v3')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('docs/calibration_comparison_v2_v3.png')
print("\nCalibration plot saved to docs/calibration_comparison_v2_v3.png")
