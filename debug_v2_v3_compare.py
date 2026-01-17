"""Compare v2 vs v3 resource_win_prob for 1st innings death overs"""

import pandas as pd
import numpy as np

df_v2 = pd.read_parquet('data/bbl_features_v2/training.parquet')
df_v3 = pd.read_parquet('data/bbl_features_v3/training.parquet')

death_v2 = df_v2[(df_v2['innings'] == 1) & (df_v2['overs_remaining'] <= 4)].copy()
death_v3 = df_v3[(df_v3['innings'] == 1) & (df_v3['overs_remaining'] <= 4)].copy()

# Calculate ease ratio
death_v2['ease_ratio'] = death_v2['current_run_rate'] / 9.0
death_v3['ease_ratio'] = death_v3['current_run_rate'] / 9.0

def get_ease(ratio):
    if ratio >= 1.2: return 'well_ahead'
    if ratio >= 1.08: return 'ahead'
    if ratio >= 0.92: return 'par'
    if ratio >= 0.8: return 'behind'
    return 'well_behind'

death_v2['ease_bucket'] = death_v2['ease_ratio'].apply(get_ease)
death_v3['ease_bucket'] = death_v3['ease_ratio'].apply(get_ease)

# High wicket cases (>=5)
high_wkt_v2 = death_v2[death_v2['wickets_lost'] >= 5]
high_wkt_v3 = death_v3[death_v3['wickets_lost'] >= 5]

print('='*80)
print('V2 vs V3: resource_win_prob for high wicket (>=5) death overs')
print('='*80)

for ease in ['well_behind', 'behind', 'par', 'ahead', 'well_ahead']:
    sub_v2 = high_wkt_v2[high_wkt_v2['ease_bucket'] == ease]
    sub_v3 = high_wkt_v3[high_wkt_v3['ease_bucket'] == ease]
    if len(sub_v2) > 5:
        actual = sub_v3['is_winner'].mean()
        v2_pred = sub_v2['resource_win_prob'].mean()
        v3_pred = sub_v3['resource_win_prob'].mean()
        v2_gap = actual - v2_pred
        v3_gap = actual - v3_pred
        better = "BETTER" if abs(v3_gap) < abs(v2_gap) else "WORSE"
        print(f'{ease:12s}: n={len(sub_v2):4d}, actual={actual:.3f}')
        print(f'              v2={v2_pred:.3f} (gap={v2_gap:+.3f})')
        print(f'              v3={v3_pred:.3f} (gap={v3_gap:+.3f}) [{better}]')
        print()

print('='*80)
print('THE ROOT CAUSE')
print('='*80)
print()
print('Looking at the 3D penalty table for death phase:')
print('- We made penalties HARSHER for well_behind (more pessimistic)')
print('- But penalties for behind/par/ahead are actually HIGHER (less pessimistic)')
print('- Yet predictions are still too pessimistic!')
print()
print('This means the resource_win_prob calculation itself is the issue,')
print('not just the wicket penalty table.')

# Check projected score vs actual final score for high wicket cases
print()
print('='*80)
print('PROJECTED SCORE VS ACTUAL (for high wicket death overs)')
print('='*80)

# We need to check if projected_score is being penalized too much
for ease in ['well_behind', 'behind', 'par', 'ahead', 'well_ahead']:
    sub_v3 = high_wkt_v3[high_wkt_v3['ease_bucket'] == ease]
    if len(sub_v3) > 5:
        proj_score = sub_v3['projected_score'].mean()
        exp_final = sub_v3['expected_final_score'].mean()
        score_adj = sub_v3['score_adjusted_by_team'].mean()
        print(f'{ease:12s}: n={len(sub_v3):4d}')
        print(f'              projected_score={proj_score:.1f}')
        print(f'              expected_final_score={exp_final:.1f}')
        print(f'              score_adjusted_by_team={score_adj:.1f}')
        print()
