#!/usr/bin/env python3
"""Compare tail event performance between v10 and v11."""
import pandas as pd
import numpy as np
import joblib

# Load training data
df_v2 = pd.read_parquet('data/bbl_features_v2/training.parquet')
df_v3 = pd.read_parquet('data/bbl_features_v3/training.parquet')

print('='*80)
print('TAIL EVENT COMPARISON: v10 (old features) vs v11 (dynamic penalty)')
print('='*80)

# Load models
model_v10 = joblib.load('models/bbl_v10/champion_model.joblib')
model_v11 = joblib.load('models/bbl_v11/champion_model.joblib')

# Get feature columns (exclude metadata)
meta_cols = ['match_id', 'ball_number', 'innings', 'over', 'ball', 'batting_team', 
             'bowling_team', 'is_winner', 'phase', 'venue']
feature_cols_v10 = [c for c in df_v2.columns if c not in meta_cols and df_v2[c].dtype in ['float64', 'int64']]
feature_cols_v11 = [c for c in df_v3.columns if c not in meta_cols and df_v3[c].dtype in ['float64', 'int64']]

# Predict
X_v2 = df_v2[feature_cols_v10].fillna(0)
X_v3 = df_v3[feature_cols_v11].fillna(0)
y = df_v2['is_winner'].values

probs_v10 = model_v10.predict_proba(X_v2)[:, 1]
probs_v11 = model_v11.predict_proba(X_v3)[:, 1]

# Tail event analysis
print('\n1. TAIL EVENT DISTRIBUTION')
print('-'*60)

for threshold, label in [(0.01, '<1%'), (0.05, '<5%'), (0.95, '>95%'), (0.99, '>99%')]:
    if threshold < 0.5:
        mask_v10 = probs_v10 < threshold
        mask_v11 = probs_v11 < threshold
    else:
        mask_v10 = probs_v10 > threshold
        mask_v11 = probs_v11 > threshold
    
    n_v10 = mask_v10.sum()
    n_v11 = mask_v11.sum()
    wr_v10 = y[mask_v10].mean() if n_v10 > 0 else 0
    wr_v11 = y[mask_v11].mean() if n_v11 > 0 else 0
    
    print(f"Predictions {label}:")
    print(f"  v10: {n_v10:>6} ({n_v10/len(y)*100:.2f}%), actual WR: {wr_v10:.2%}")
    print(f"  v11: {n_v11:>6} ({n_v11/len(y)*100:.2f}%), actual WR: {wr_v11:.2%}")
    print()

# Death over analysis (where the fix matters most)
print('\n2. DEATH OVER PERFORMANCE (Overs 17-20)')
print('-'*60)

death_mask = df_v2['overs_remaining'] <= 4

for inn in [1, 2]:
    inn_mask = (df_v2['innings'] == inn) & death_mask
    
    probs_v10_death = probs_v10[inn_mask]
    probs_v11_death = probs_v11[inn_mask]
    y_death = y[inn_mask]
    
    # Brier score
    brier_v10 = np.mean((probs_v10_death - y_death) ** 2)
    brier_v11 = np.mean((probs_v11_death - y_death) ** 2)
    
    print(f"Innings {inn} Death Overs (n={inn_mask.sum():,}):")
    print(f"  Brier v10: {brier_v10:.4f}")
    print(f"  Brier v11: {brier_v11:.4f}")
    print(f"  Change:    {(brier_v11-brier_v10)/brier_v10*100:+.2f}%")
    print()

# Check resource_win_prob feature
print('\n3. RESOURCE_WIN_PROB FEATURE COMPARISON')
print('-'*60)

print("v10 (old) resource_win_prob stats:")
print(df_v2['resource_win_prob'].describe())
print()

print("v11 (new) resource_win_prob stats:")
print(df_v3['resource_win_prob'].describe())

# Correlation with actual outcome
corr_v10 = df_v2['resource_win_prob'].corr(df_v2['is_winner'])
corr_v11 = df_v3['resource_win_prob'].corr(df_v3['is_winner'])
print(f"\nCorrelation with actual outcome:")
print(f"  v10: {corr_v10:.4f}")
print(f"  v11: {corr_v11:.4f}")
print(f"  Change: {(corr_v11-corr_v10)/corr_v10*100:+.2f}%")
