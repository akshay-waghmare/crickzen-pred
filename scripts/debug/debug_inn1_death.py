"""Debug why 1st innings death overs didn't improve"""

import pandas as pd
import numpy as np

# Load both feature sets
df_v2 = pd.read_parquet('data/bbl_features_v2/training.parquet')
df_v3 = pd.read_parquet('data/bbl_features_v3/training.parquet')

# Filter to innings 1, death overs
inn1_death_v2 = df_v2[(df_v2['innings'] == 1) & (df_v2['overs_remaining'] <= 4)]
inn1_death_v3 = df_v3[(df_v3['innings'] == 1) & (df_v3['overs_remaining'] <= 4)]

print('='*80)
print('ANALYZING BY WICKETS LOST')
print('='*80)

for wkts in range(0, 10):
    v2_wkt = inn1_death_v2[inn1_death_v2['wickets_lost'] == wkts]
    v3_wkt = inn1_death_v3[inn1_death_v3['wickets_lost'] == wkts]
    if len(v2_wkt) > 0:
        diff = v3_wkt['resource_win_prob'].values - v2_wkt['resource_win_prob'].values
        v2_mean = v2_wkt['resource_win_prob'].mean()
        v3_mean = v3_wkt['resource_win_prob'].mean()
        print(f"Wickets={wkts}: n={len(v2_wkt):4d}, v2={v2_mean:.3f}, v3={v3_mean:.3f}, diff={diff.mean():+.4f}")

print()
print('='*80)
print('OLD FLAT PENALTY VS NEW 3D PENALTY')
print('='*80)

from src.bbl_pipeline.processing.calculator import (
    WICKET_PENALTY, 
    FIRST_INNINGS_WICKET_PENALTY_3D
)

print('\nOld flat WICKET_PENALTY table:')
for wkts, penalty in WICKET_PENALTY.items():
    print(f'  Wickets {wkts}: {penalty}')

print('\nNew FIRST_INNINGS_WICKET_PENALTY_3D for death phase:')
for ease in ['behind', 'par', 'ahead', 'dominant']:
    print(f'\n  {ease}:')
    for wkts, penalty in FIRST_INNINGS_WICKET_PENALTY_3D['death'][ease].items():
        print(f'    Wickets {wkts}: {penalty}')

# Check what ease buckets samples fall into
print('\n' + '='*80)
print('SAMPLE EASE BUCKET DISTRIBUTION')
print('='*80)

# Calculate ease for each sample
from src.bbl_pipeline.processing.calculator import ResourceFeatureCalculator
calc = ResourceFeatureCalculator()

# Get score vs par for death overs (high wicket cases)
high_wkt = inn1_death_v3[inn1_death_v3['wickets_lost'] >= 5]
print(f"\nHigh wicket samples (>=5 wickets) in death: {len(high_wkt)}")
print(f"Score vs par distribution:")
print(high_wkt['score_vs_par'].describe())

# Check correlation with outcome for high wicket cases
corr_v2 = inn1_death_v2[inn1_death_v2['wickets_lost'] >= 5]['resource_win_prob'].corr(
    inn1_death_v2[inn1_death_v2['wickets_lost'] >= 5]['is_winner']
)
corr_v3 = inn1_death_v3[inn1_death_v3['wickets_lost'] >= 5]['resource_win_prob'].corr(
    inn1_death_v3[inn1_death_v3['wickets_lost'] >= 5]['is_winner']
)
print(f"\nCorrelation with outcome (>=5 wickets): v2={corr_v2:.4f} -> v3={corr_v3:.4f}")

# What about actual win rate by score position?
print('\n' + '='*80)
print('ACTUAL WIN RATE BY SCORE POSITION (Death, >=5 wickets)')
print('='*80)

high_wkt_v3 = inn1_death_v3[inn1_death_v3['wickets_lost'] >= 5].copy()
bins = [-np.inf, -15, 0, 15, 30, np.inf]
labels = ['far_behind', 'behind', 'par', 'ahead', 'dominant']
high_wkt_v3['score_bucket'] = pd.cut(high_wkt_v3['score_vs_par'], bins=bins, labels=labels)

for bucket in labels:
    subset = high_wkt_v3[high_wkt_v3['score_bucket'] == bucket]
    if len(subset) > 0:
        actual_wr = subset['is_winner'].mean()
        pred_v2 = inn1_death_v2[(inn1_death_v2['wickets_lost'] >= 5) & 
                                 (pd.cut(inn1_death_v2['score_vs_par'], bins=bins, labels=labels) == bucket)]['resource_win_prob'].mean()
        pred_v3 = subset['resource_win_prob'].mean()
        print(f"{bucket:12s}: n={len(subset):4d}, actual_wr={actual_wr:.3f}, v2_pred={pred_v2:.3f}, v3_pred={pred_v3:.3f}")
