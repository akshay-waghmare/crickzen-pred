"""
Analyze model calibration by 10% probability bins for both innings.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import joblib

model_dir = Path('models/bbl_v12')
df = pd.read_parquet('data/bbl_features_v4/training.parquet')
model = joblib.load(model_dir / 'champion_model.joblib')

def analyze_innings(df_inn, name):
    y_true = df_inn['is_winner'].values
    raw_prob = model.predict_proba(df_inn)[:, 1]
    
    print('='*80)
    print(f'📊 {name} CALIBRATION BY 10% BINS (N={len(df_inn):,})')
    print('='*80)
    print(f'{"Bin":>10} {"N":>8} {"Predicted":>10} {"Actual":>10} {"Gap":>10} {"Status":>20}')
    print('-'*80)
    
    for i in range(10):
        lo, hi = i/10, (i+1)/10
        if i == 9:
            mask = (raw_prob >= lo) & (raw_prob <= hi)
        else:
            mask = (raw_prob >= lo) & (raw_prob < hi)
        
        if mask.sum() == 0:
            continue
        
        pred = raw_prob[mask].mean()
        actual = y_true[mask].mean()
        gap = actual - pred
        
        if abs(gap) < 0.02:
            status = 'Good'
        elif gap > 0:
            status = f'Under by {gap:.1%}'
        else:
            status = f'Over by {abs(gap):.1%}'
        
        print(f'{i*10}-{(i+1)*10}%  {mask.sum():>8,} {pred:>10.1%} {actual:>10.1%} {gap:>+10.1%} {status:>20}')
    
    print('='*80)
    print()

# First innings
df_inn1 = df[df['innings'] == 1].copy()
analyze_innings(df_inn1, "FIRST INNINGS")

# Second innings
df_inn2 = df[df['innings'] == 2].copy()
analyze_innings(df_inn2, "SECOND INNINGS")
