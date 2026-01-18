"""
Analyze model performance for easy chases and low scoring matches
"""
import pandas as pd
import numpy as np
from sklearn.metrics import brier_score_loss
import joblib

# Load data
df = pd.read_parquet('data/bbl_features_v4/training.parquet')
model = joblib.load('models/bbl_v12/champion_model.joblib')
FEATURES = model.selected_features_

X = df[FEATURES]
y = df['is_winner'].astype(int)

# Get predictions
preds = model.predict_proba(X)[:, 1]
df['pred'] = preds
df['actual'] = y

# Second innings only
inn2 = df[df['innings'] == 2].copy()

print('=' * 80)
print('MODEL PERFORMANCE BY CHASE DIFFICULTY')
print('=' * 80)

# Analyze by required run rate
print()
print('BY REQUIRED RUN RATE (Second Innings):')
print(f'{"RRR Range":<15} {"N":>8} {"Actual":>10} {"Pred":>10} {"Error":>8} {"Brier":>8}')
print('-' * 70)

rrr_bins = [(0, 4), (4, 6), (6, 8), (8, 10), (10, 15), (15, 30)]
for lo, hi in rrr_bins:
    mask = (inn2['required_run_rate'] >= lo) & (inn2['required_run_rate'] < hi)
    n = mask.sum()
    if n > 100:
        actual = inn2.loc[mask, 'actual'].mean() * 100
        pred = inn2.loc[mask, 'pred'].mean() * 100
        err = pred - actual
        brier = brier_score_loss(inn2.loc[mask, 'actual'], inn2.loc[mask, 'pred'])
        print(f'{lo}-{hi} RRR        {n:>8,}   {actual:>7.1f}%   {pred:>7.1f}%  {err:>+6.1f}%   {brier:.4f}')

# Analyze easy chases (RRR < 6 with wickets in hand)
print()
print('EASY CHASE ANALYSIS (RRR < 6):')
print(f'{"Wickets Lost":<15} {"N":>8} {"Actual":>10} {"Pred":>10} {"Error":>8}')
print('-' * 60)

easy_chase = inn2[inn2['required_run_rate'] < 6].copy()
for wkts in range(0, 10):
    mask = easy_chase['wickets_lost'] == wkts
    n = mask.sum()
    if n > 50:
        actual = easy_chase.loc[mask, 'actual'].mean() * 100
        pred = easy_chase.loc[mask, 'pred'].mean() * 100
        err = pred - actual
        print(f'{wkts} wickets      {n:>8,}   {actual:>7.1f}%   {pred:>7.1f}%  {err:>+6.1f}%')

# Analyze by target score (low vs high scoring)
print()
print('BY TARGET SCORE (using expected_final_score as proxy):')
if 'expected_final_score' in inn2.columns:
    target_proxy = inn2['expected_final_score']
    print(f'{"Target Range":<15} {"N":>8} {"Actual":>10} {"Pred":>10} {"Error":>8} {"Brier":>8}')
    print('-' * 70)
    
    target_bins = [(0, 120), (120, 140), (140, 160), (160, 180), (180, 220)]
    for lo, hi in target_bins:
        mask = (target_proxy >= lo) & (target_proxy < hi)
        n = mask.sum()
        if n > 100:
            actual = inn2.loc[mask, 'actual'].mean() * 100
            pred = inn2.loc[mask, 'pred'].mean() * 100
            err = pred - actual
            brier = brier_score_loss(inn2.loc[mask, 'actual'], inn2.loc[mask, 'pred'])
            print(f'{lo}-{hi}           {n:>8,}   {actual:>7.1f}%   {pred:>7.1f}%  {err:>+6.1f}%   {brier:.4f}')

# Very easy chase: RRR < 4, wickets >= 6
print()
print('=' * 80)
print('VERY EASY CHASE (RRR < 4, 6+ wickets in hand):')
print('=' * 80)
very_easy = inn2[(inn2['required_run_rate'] < 4) & (inn2['wickets_lost'] <= 4)]
if len(very_easy) > 50:
    actual = very_easy['actual'].mean() * 100
    pred = very_easy['pred'].mean() * 100
    resource = very_easy['resource_win_prob'].mean() * 100
    print(f'  N = {len(very_easy):,}')
    print(f'  Actual Win%: {actual:.1f}%')
    print(f'  Model Pred:  {pred:.1f}% (error: {pred-actual:+.1f}%)')
    print(f'  Resource WP: {resource:.1f}%')
    print()
    
    # Check by over
    print('  By Over (RRR < 4, <=4 wickets lost):')
    print(f'  {"Over":<8} {"N":>6} {"Actual":>8} {"Pred":>8} {"Resource":>10} {"Err":>8}')
    for over in range(1, 21):
        mask = (very_easy['overs_remaining'] >= 20-over) & (very_easy['overs_remaining'] < 21-over)
        n = mask.sum()
        if n > 20:
            actual = very_easy.loc[mask, 'actual'].mean() * 100
            pred = very_easy.loc[mask, 'pred'].mean() * 100
            res = very_easy.loc[mask, 'resource_win_prob'].mean() * 100
            err = pred - actual
            print(f'  Over {over:<3}  {n:>6}  {actual:>6.1f}%  {pred:>6.1f}%    {res:>6.1f}%   {err:>+6.1f}%')

# Low scoring matches
print()
print('=' * 80)
print('LOW SCORING MATCHES (expected_final_score < 130):')
print('=' * 80)
low_scoring = inn2[inn2['expected_final_score'] < 130]
if len(low_scoring) > 100:
    actual = low_scoring['actual'].mean() * 100
    pred = low_scoring['pred'].mean() * 100
    print(f'  N = {len(low_scoring):,}')
    print(f'  Actual Win%: {actual:.1f}%')
    print(f'  Model Pred:  {pred:.1f}% (error: {pred-actual:+.1f}%)')
    print()
    
    # By RRR in low scoring
    print('  By RRR (low scoring matches):')
    for lo, hi in [(0, 4), (4, 6), (6, 8), (8, 15)]:
        mask = (low_scoring['required_run_rate'] >= lo) & (low_scoring['required_run_rate'] < hi)
        n = mask.sum()
        if n > 30:
            actual = low_scoring.loc[mask, 'actual'].mean() * 100
            pred = low_scoring.loc[mask, 'pred'].mean() * 100
            err = pred - actual
            print(f'    RRR {lo}-{hi}: N={n:,}, Actual={actual:.1f}%, Pred={pred:.1f}%, Err={err:+.1f}%')
