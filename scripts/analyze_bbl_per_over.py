"""
Analyze BBL model per-over log loss for both calibrators.
Used to generate data for the Streamlit calibration guidance tables.
"""
import joblib
import pandas as pd
import numpy as np
from pathlib import Path

def log_loss(y_true: np.ndarray, y_prob: np.ndarray, clip: float = 0.01) -> float:
    """Calculate log loss (cross-entropy) with confidence clipping."""
    y_prob = np.clip(y_prob, clip, 1 - clip)
    loss = -(y_true * np.log(y_prob) + (1 - y_true) * np.log(1 - y_prob))
    return float(np.mean(loss))

def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculate Brier score."""
    return float(np.mean((y_prob - y_true) ** 2))

def ece_score(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Calculate Expected Calibration Error."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_prob > bin_boundaries[i]) & (y_prob <= bin_boundaries[i + 1])
        if mask.sum() > 0:
            avg_confidence = y_prob[mask].mean()
            avg_accuracy = y_true[mask].mean()
            ece += mask.sum() * abs(avg_accuracy - avg_confidence)
    return ece / len(y_true)

print("Loading BBL v10 model and training data...")
model = joblib.load('models/bbl_v10/champion_model.joblib')
isotonic_cal = joblib.load('models/bbl_v10/isotonic_calibrator.pkl')
per_over_cal = joblib.load('models/bbl_v10/per_over_calibrators.pkl')
df = pd.read_parquet('data/bbl_features_v2/training.parquet')

print(f"Total samples: {len(df):,}")

# Get feature columns
exclude_cols = ['is_winner', 'overs_completed', 'match_id', 'ball_id']
feature_cols = [col for col in df.columns if col not in exclude_cols and not col.startswith('_')]

# Get predictions
X = df[feature_cols].fillna(0)
y_true = df['is_winner'].values
raw_probs = model.predict_proba(X)[:, 1]
resource_probs = df['resource_win_prob'].values

# Innings-specific calibrated probabilities (from isotonic_calibrator.pkl)
innings_cal_probs = np.zeros_like(raw_probs)
for innings in [1, 2]:
    mask = df['innings'] == innings
    if mask.sum() > 0:
        calibrator = isotonic_cal[f'calibrator_innings{innings}']
        innings_cal_probs[mask] = calibrator.predict(raw_probs[mask].reshape(-1, 1)).ravel()

# Per-over calibrated probabilities (from per_over_calibrators.pkl - ECE-optimized)
per_over_cal_probs = np.zeros_like(raw_probs)
df['over'] = (20 - df['overs_remaining']).astype(int)

for innings in [1, 2]:
    for over in range(1, 21):
        mask = (df['innings'] == innings) & (df['over'] == over)
        if mask.sum() > 0:
            over_key = f'inn{innings}_over{over}'
            if over_key in per_over_cal and 'calibrator' in per_over_cal[over_key]:
                cal = per_over_cal[over_key]['calibrator']
                per_over_cal_probs[mask] = cal.predict(raw_probs[mask].reshape(-1, 1)).ravel()
            else:
                per_over_cal_probs[mask] = raw_probs[mask]

print("\n" + "="*150)
print("BBL v10 PER-OVER ANALYSIS: Raw vs Inn-Specific (ECE-Opt) vs Per-Over (Brier-Opt)")
print("="*150)

for innings in [1, 2]:
    print(f"\n### INNINGS {innings} ###")
    print(f"{'Over':<6} {'N':<6} {'LL_Raw':<10} {'LL_ECE':<10} {'LL_Brier':<10} {'B_Raw':<10} {'B_ECE':<10} {'B_Brier':<10} {'ECE_Raw':<10} {'ECE_Cal':<10} {'Best_LL':<12} {'Best_B':<12}")
    print("-"*150)
    
    for over in range(1, 21):
        mask = (df['innings'] == innings) & (df['over'] == over)
        if mask.sum() < 100:
            continue
        
        y_subset = y_true[mask]
        raw_subset = raw_probs[mask]
        ece_subset = innings_cal_probs[mask]  # Inn-specific = ECE-optimized
        brier_subset = per_over_cal_probs[mask]  # Per-over = Brier-optimized
        
        # Log Loss
        ll_raw = log_loss(y_subset, raw_subset)
        ll_ece = log_loss(y_subset, ece_subset)
        ll_brier = log_loss(y_subset, brier_subset)
        
        # Brier
        b_raw = brier_score(y_subset, raw_subset)
        b_ece = brier_score(y_subset, ece_subset)
        b_brier = brier_score(y_subset, brier_subset)
        
        # ECE
        ece_raw = ece_score(y_subset, raw_subset)
        ece_cal = ece_score(y_subset, ece_subset)
        
        # Best for each
        ll_values = [('Raw', ll_raw), ('ECE', ll_ece), ('Brier', ll_brier)]
        b_values = [('Raw', b_raw), ('ECE', b_ece), ('Brier', b_brier)]
        best_ll = min(ll_values, key=lambda x: x[1])[0]
        best_b = min(b_values, key=lambda x: x[1])[0]
        
        print(f"{over:<6} {mask.sum():<6} {ll_raw:<10.4f} {ll_ece:<10.4f} {ll_brier:<10.4f} {b_raw:<10.4f} {b_ece:<10.4f} {b_brier:<10.4f} {ece_raw:<10.4f} {ece_cal:<10.4f} {best_ll:<12} {best_b:<12}")

# Summary
print("\n" + "="*100)
print("SUMMARY")
print("="*100)
for innings in [1, 2]:
    mask = df['innings'] == innings
    y_subset = y_true[mask]
    raw_subset = raw_probs[mask]
    ece_subset = innings_cal_probs[mask]
    brier_subset = per_over_cal_probs[mask]
    
    print(f"\nInnings {innings}:")
    print(f"  Log Loss:  Raw={log_loss(y_subset, raw_subset):.4f}, ECE-Opt={log_loss(y_subset, ece_subset):.4f}, Brier-Opt={log_loss(y_subset, brier_subset):.4f}")
    print(f"  Brier:     Raw={brier_score(y_subset, raw_subset):.4f}, ECE-Opt={brier_score(y_subset, ece_subset):.4f}, Brier-Opt={brier_score(y_subset, brier_subset):.4f}")
