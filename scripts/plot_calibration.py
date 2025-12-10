import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss
import os

# Ensure docs directory exists
os.makedirs('docs', exist_ok=True)

# Load data
print("Loading data...")
try:
    df = pd.read_parquet('data/ilt_features_v2/training_sampled.parquet')
except FileNotFoundError:
    print("Error: Could not find data file. Please ensure 'data/ilt_features_v2/training_sampled.parquet' exists.")
    exit(1)

y_true = df['is_winner'].values

# Load model
print("Loading model...")
try:
    model = joblib.load('models/ilt_champion_v2/champion_model.joblib')
except FileNotFoundError:
    print("Error: Could not find model file. Please ensure 'models/ilt_champion_v2/champion_model.joblib' exists.")
    exit(1)

features = model.selected_features_
X = df[features]

# Predict
print("Predicting...")
y_prob = model.predict_proba(X)[:, 1]

# Calculate Brier score
brier = brier_score_loss(y_true, y_prob)
print(f"Brier Score: {brier:.4f}")

# Calibration curve
print("Calculating calibration curve...")
prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=10, strategy='uniform')

# Plot
plt.figure(figsize=(10, 8))

# Plot calibration curve
plt.plot([0, 1], [0, 1], linestyle='--', color='gray', label='Perfectly Calibrated')
plt.plot(prob_pred, prob_true, marker='o', linewidth=2, label=f'Model v2 (Brier={brier:.4f})')

# Add histogram of predictions
plt.hist(y_prob, range=(0, 1), bins=10, density=True, color='navy', alpha=0.1, label='Prediction Distribution')

plt.xlabel('Mean Predicted Probability')
plt.ylabel('Fraction of Positives (Actual Win Rate)')
plt.title('Calibration Curve - ILT20 Model v2')
plt.legend(loc='best')
plt.grid(True, alpha=0.3)

# Save
output_path = 'docs/calibration_curve_v2.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"Plot saved to {output_path}")
