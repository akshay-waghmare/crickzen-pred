#!/usr/bin/env python3
"""Analyze BBL v10 ECE by phase to determine best probability source."""

import pandas as pd
import numpy as np
import joblib

# Load data and model
df = pd.read_parquet('data/bbl_features_v2/training.parquet')
model = joblib.load('models/bbl_v10/champion_model.joblib')
calibrator = joblib.load('models/bbl_v10/isotonic_calibrator.pkl')

# Prepare features
exclude_cols = ['is_winner', 'innings']
feature_cols = [c for c in df.columns if c not in exclude_cols]
X = df[feature_cols]
y = df['is_winner'].values

# Get probabilities
raw_prob = model.predict_proba(X)[:, 1]
resource_prob = df['resource_win_prob'].values

# Apply innings-specific calibration
inn1_mask = df['innings'] == 1
inn2_mask = df['innings'] == 2
calibrated_prob = np.zeros_like(raw_prob)
calibrated_prob[inn1_mask] = calibrator['calibrator_innings1'].predict(raw_prob[inn1_mask])
calibrated_prob[inn2_mask] = calibrator['calibrator_innings2'].predict(raw_prob[inn2_mask])

# Metrics
def brier(y, p): 
    return np.mean((p - y) ** 2)

def ece(y, p, n=10):
    e = 0.0
    for i in range(n):
        m = (p >= i/n) & (p < (i+1)/n)
        if m.sum() > 0: 
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return e

# Calculate current over
over = np.ceil(20 - df['overs_remaining']).astype(int) + 1

print('='*70)
print('BBL v10 - ECE ANALYSIS BY INNINGS x PHASE')
print('='*70)

phases = [('powerplay', 1, 6), ('middle', 7, 15), ('death', 16, 20)]
results = []

for inn in [1, 2]:
    print(f"\nINNINGS {inn}")
    print("-"*70)
    inn_mask = df['innings'] == inn
    
    for phase, start, end in phases:
        phase_mask = inn_mask & (over >= start) & (over <= end)
        yp = y[phase_mask]
        rawp = raw_prob[phase_mask]
        calp = calibrated_prob[phase_mask]
        resp = resource_prob[phase_mask]
        
        e_raw = ece(yp, rawp)
        e_cal = ece(yp, calp)
        e_res = ece(yp, resp)
        
        best = 'Raw' if e_raw <= e_cal and e_raw <= e_res else ('Cal' if e_cal <= e_res else 'Res')
        best_val = min(e_raw, e_cal, e_res)
        
        results.append({
            'phase': f'inn{inn}_{phase}',
            'ece_raw': e_raw,
            'ece_cal': e_cal,
            'ece_res': e_res,
            'best': best,
            'best_val': best_val
        })
        
        print(f"  {phase:12} ECE: Raw={e_raw:.4f}, Cal={e_cal:.4f}, Res={e_res:.4f}  --> Best: {best}")

print("\n" + "="*70)
print("SUMMARY: ECE-OPTIMIZED SOURCE FOR BBL")
print("="*70)
print(f"{'Phase':<20} {'Best Source':>12} {'ECE':>10}")
print("-"*70)
for r in results:
    print(f"{r['phase']:<20} {r['best']:>12} {r['best_val']:>10.4f}")

print("\n" + "="*70)
print("KEY INSIGHT FOR BBL:")
print("="*70)
print("""
Unlike SA20, BBL has a larger dataset (618 matches vs 99).
The existing innings-specific calibrator works well for most phases.

For ECE optimization in BBL:
- Inn1: Use RAW model (already well-calibrated)
- Inn2: Use CALIBRATED (innings-specific isotonic)
- Exception: Inn2 Middle may benefit from Resource probability
""")
