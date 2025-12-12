"""
EDA: Analyze first innings win probability patterns from ILT20 data
to calibrate the calculator for 1st innings.
"""
import pandas as pd
import numpy as np

# Load data
df = pd.read_parquet('data/ilt_features_v2/training.parquet')

# First innings = rows where required_run_rate is 0 or negative (no target yet)
df_first = df[df['required_run_rate'] <= 0].copy()

print("=" * 70)
print("FIRST INNINGS WIN PROBABILITY ANALYSIS - ILT20")
print("=" * 70)
print(f"Total 1st innings rows: {len(df_first):,}")
print(f"Overall batting first win rate: {df_first['is_winner'].mean():.1%}")
print()

# Key columns
print("Key columns:")
print(f"  expected_final_score range: {df_first['expected_final_score'].min():.0f} to {df_first['expected_final_score'].max():.0f}")
print(f"  current_run_rate range: {df_first['current_run_rate'].min():.1f} to {df_first['current_run_rate'].max():.1f}")
print()

# Win rate by projected score bins
print("=" * 70)
print("WIN RATE BY PROJECTED FINAL SCORE")
print("=" * 70)
df_first['proj_score_bin'] = pd.cut(
    df_first['expected_final_score'], 
    bins=[0, 120, 140, 150, 160, 170, 180, 200, 300]
)
proj_stats = df_first.groupby('proj_score_bin', observed=True)['is_winner'].agg(['mean', 'count'])
print(proj_stats)
print()

# Win rate by wickets
print("=" * 70)
print("WIN RATE BY WICKETS LOST")
print("=" * 70)
wicket_stats = df_first.groupby('wickets_lost')['is_winner'].agg(['mean', 'count'])
print(wicket_stats)
print()

# Win rate by phase
print("=" * 70)
print("WIN RATE BY PHASE")
print("=" * 70)
df_first['overs_bowled'] = 20 - df_first['overs_remaining']
df_first['phase'] = pd.cut(
    df_first['overs_bowled'], 
    bins=[0, 6, 15, 20], 
    labels=['powerplay', 'middle', 'death']
)
phase_stats = df_first.groupby('phase', observed=True)['is_winner'].agg(['mean', 'count'])
print(phase_stats)
print()

# Win rate by projected score AND wickets
print("=" * 70)
print("WIN RATE BY PROJECTED SCORE AND WICKETS")
print("=" * 70)
df_first['proj_score_coarse'] = pd.cut(
    df_first['expected_final_score'],
    bins=[0, 150, 160, 170, 180, 300],
    labels=['<150', '150-160', '160-170', '170-180', '>180']
)
pivot = df_first.pivot_table(
    values='is_winner',
    index='wickets_lost',
    columns='proj_score_coarse',
    aggfunc=['mean', 'count'],
    observed=True
)
print(pivot)
print()

# Specific scenarios
print("=" * 70)
print("SPECIFIC SCENARIOS")
print("=" * 70)

# Scenario: Powerplay 50/0 (projected ~170)
s1 = df_first[
    (df_first['overs_bowled'] <= 6) &
    (df_first['wickets_lost'] == 0) &
    (df_first['expected_final_score'] >= 165) &
    (df_first['expected_final_score'] <= 180)
]
print(f"Powerplay, 0 wickets, proj 165-180: {s1['is_winner'].mean():.1%} (n={len(s1)})")

# Scenario: Powerplay 50/3 (projected ~150)
s2 = df_first[
    (df_first['overs_bowled'] <= 6) &
    (df_first['wickets_lost'] >= 3) &
    (df_first['expected_final_score'] >= 140) &
    (df_first['expected_final_score'] <= 160)
]
print(f"Powerplay, 3+ wickets, proj 140-160: {s2['is_winner'].mean():.1%} (n={len(s2)})")

# Scenario: Death overs 150/3 (projected ~175)
s3 = df_first[
    (df_first['overs_bowled'] >= 15) &
    (df_first['wickets_lost'] <= 3) &
    (df_first['expected_final_score'] >= 170) &
    (df_first['expected_final_score'] <= 185)
]
print(f"Death, 0-3 wickets, proj 170-185: {s3['is_winner'].mean():.1%} (n={len(s3)})")

# Scenario: Death overs 130/6 (projected ~155)
s4 = df_first[
    (df_first['overs_bowled'] >= 15) &
    (df_first['wickets_lost'] >= 6) &
    (df_first['expected_final_score'] >= 145) &
    (df_first['expected_final_score'] <= 165)
]
print(f"Death, 6+ wickets, proj 145-165: {s4['is_winner'].mean():.1%} (n={len(s4)})")
