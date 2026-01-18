#!/usr/bin/env python3
"""
Check how the BBL model handles tail events (extreme probabilities).

Specifically checking the scenario: 181-5 (16.5), CRR=10.75, RR=2.84
"""
import pandas as pd
import numpy as np
import joblib

# Load model and calibrators
model = joblib.load('models/bbl_v10/champion_model.joblib')
iso_cals = joblib.load('models/bbl_v10/isotonic_calibrator.pkl')

print('=== Tail Event Analysis ===')
print('Scenario: 181-5 (16.5 overs), CRR: 10.75, RR: 2.84')
print('This is a near-certain win position\n')

# Load training data
df = pd.read_parquet('data/bbl_features_v2/training.parquet')
df_inn2 = df[df['innings'] == 2].copy()

# Find extreme winning positions (RR < 3 and CRR > 10)
# Note: 'over' column not in features, using ball_number to filter death overs
if 'required_run_rate' in df_inn2.columns and 'current_run_rate' in df_inn2.columns:
    extreme_mask = (
        (df_inn2['required_run_rate'] < 3.5) & 
        (df_inn2['current_run_rate'] > 9)
    )
    extreme_cases = df_inn2[extreme_mask]
    
    print(f'Similar extreme scenarios in training: {len(extreme_cases)}')
    if len(extreme_cases) > 0:
        actual_win_rate = extreme_cases['is_winner'].mean()
        print(f'Actual win rate: {actual_win_rate:.4f} ({actual_win_rate*100:.1f}%)\n')
        
        # Get raw predictions for these cases
        X = extreme_cases.drop(['match_id', 'ball', 'innings', 'is_winner'], 
                               axis=1, errors='ignore')
        raw_probs = model.predict_proba(X)
        
        print(f'RAW MODEL:')
        print(f'  Mean: {raw_probs.mean():.4f}')
        print(f'  Min:  {raw_probs.min():.4f}')
        print(f'  Max:  {raw_probs.max():.4f}')
        print(f'  Std:  {raw_probs.std():.4f}')
        
        # Apply innings-specific calibration
        if 'innings_2' in iso_cals:
            cal_probs = iso_cals['innings_2'].predict(raw_probs)
            cal_probs = np.clip(cal_probs, 0, 1)
            
            print(f'\nINNINGS-SPECIFIC CALIBRATED:')
            print(f'  Mean: {cal_probs.mean():.4f}')
            print(f'  Min:  {cal_probs.min():.4f}')
            print(f'  Max:  {cal_probs.max():.4f}')
            print(f'  Std:  {cal_probs.std():.4f}')
            
            # Calculate metrics for this segment
            brier_raw = np.mean((raw_probs - extreme_cases['is_winner'].values) ** 2)
            brier_cal = np.mean((cal_probs - extreme_cases['is_winner'].values) ** 2)
            
            print(f'\nMETRICS (Tail Events Only):')
            print(f'  Brier (raw):        {brier_raw:.6f}')
            print(f'  Brier (calibrated): {brier_cal:.6f}')
            print(f'  Improvement:        {((brier_raw-brier_cal)/brier_raw*100):+.2f}%')
            
            # Check calibration quality
            print(f'\nCALIBRATION CHECK:')
            print(f'  Actual win rate:     {actual_win_rate:.4f}')
            print(f'  Raw model avg:       {raw_probs.mean():.4f} (error: {(raw_probs.mean()-actual_win_rate):.4f})')
            print(f'  Calibrated avg:      {cal_probs.mean():.4f} (error: {(cal_probs.mean()-actual_win_rate):.4f})')
            
            # Count predictions at boundaries
            n_at_max_raw = (raw_probs >= 0.99).sum()
            n_at_max_cal = (cal_probs >= 0.99).sum()
            
            print(f'\nBOUNDARY ANALYSIS:')
            print(f'  Raw probs >= 0.99:        {n_at_max_raw} ({n_at_max_raw/len(raw_probs)*100:.1f}%)')
            print(f'  Calibrated probs >= 0.99: {n_at_max_cal} ({n_at_max_cal/len(cal_probs)*100:.1f}%)')
            
            if n_at_max_raw > 0 or n_at_max_cal > 0:
                print(f'\n  ⚠️  TAIL EVENT ISSUE DETECTED:')
                print(f'  The model/calibrator is producing extreme probabilities (≥0.99)')
                print(f'  for {n_at_max_cal} cases, but actual win rate is {actual_win_rate:.4f}')
                print(f'  This suggests poor calibration at the tails.')
else:
    print('Required features not found in dataset')

# Now check overall tail event distribution
print('\n\n=== OVERALL TAIL EVENT DISTRIBUTION ===')
df_full = pd.read_parquet('data/bbl_features_v2/training.parquet')
X_full = df_full.drop(['match_id', 'ball', 'innings', 'is_winner'], 
                      axis=1, errors='ignore')
probs_full = model.predict_proba(X_full)

# Analyze extreme predictions
n_very_low = (probs_full < 0.01).sum()
n_very_high = (probs_full > 0.99).sum()
n_extreme = n_very_low + n_very_high

print(f'Total predictions: {len(probs_full):,}')
print(f'Extreme low  (< 0.01): {n_very_low:,} ({n_very_low/len(probs_full)*100:.2f}%)')
print(f'Extreme high (> 0.99): {n_very_high:,} ({n_very_high/len(probs_full)*100:.2f}%)')
print(f'Total extreme:         {n_extreme:,} ({n_extreme/len(probs_full)*100:.2f}%)')

# Check actual outcomes for extreme predictions
if n_very_high > 0:
    mask_high = probs_full > 0.99
    actual_wins_high = df_full.loc[mask_high, 'is_winner'].mean()
    avg_prob_high = probs_full[mask_high].mean()
    
    print(f'\nExtreme HIGH predictions (> 0.99):')
    print(f'  Predicted avg: {avg_prob_high:.4f}')
    print(f'  Actual wins:   {actual_wins_high:.4f}')
    print(f'  Calibration error: {abs(avg_prob_high - actual_wins_high):.4f}')
    
if n_very_low > 0:
    mask_low = probs_full < 0.01
    actual_wins_low = df_full.loc[mask_low, 'is_winner'].mean()
    avg_prob_low = probs_full[mask_low].mean()
    
    print(f'\nExtreme LOW predictions (< 0.01):')
    print(f'  Predicted avg: {avg_prob_low:.4f}')
    print(f'  Actual wins:   {actual_wins_low:.4f}')
    print(f'  Calibration error: {abs(avg_prob_low - actual_wins_low):.4f}')
