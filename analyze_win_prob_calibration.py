"""
EDA: Analyze actual win probabilities from ILT20 data
to calibrate the calculator's phase-specific logistic parameters.
"""
import pandas as pd
import numpy as np

# Load data
df = pd.read_parquet('data/ilt_features_v2/training.parquet')
print("=" * 70)
print("ILT20 WIN PROBABILITY CALIBRATION - EDA")
print("=" * 70)

# Filter to 2nd innings (chasing)
df_chase = df[df['required_run_rate'] > 0].copy()
print(f"\nTotal chase rows: {len(df_chase):,}")
print(f"Overall chase win rate: {df_chase['is_winner'].mean():.1%}")

# Create bins for analysis
df_chase['overs_bowled'] = 20 - df_chase['overs_remaining']

# Define phases
df_chase['phase'] = pd.cut(
    df_chase['overs_bowled'],
    bins=[0, 6, 15, 20],
    labels=['powerplay', 'middle', 'death'],
    include_lowest=True
)

# Calculate difficulty ratio (runs_required / max_gettable)
# We need to reconstruct this from available columns
# chase_difficulty seems related - let's check it
print("\n" + "=" * 70)
print("CHASE DIFFICULTY COLUMN ANALYSIS")
print("=" * 70)
print(f"chase_difficulty range: {df_chase['chase_difficulty'].min():.2f} to {df_chase['chase_difficulty'].max():.2f}")
print(f"chase_difficulty mean: {df_chase['chase_difficulty'].mean():.2f}")

# Win rate by chase_difficulty bins
diff_bins = [-1, 0.3, 0.5, 0.7, 0.9, 1.0, 1.2, 1.5, 2.0, 10]
df_chase['diff_bin'] = pd.cut(df_chase['chase_difficulty'], bins=diff_bins)
print("\nWin rate by chase_difficulty:")
print(df_chase.groupby('diff_bin')['is_winner'].agg(['mean', 'count']))

# Win rate by phase
print("\n" + "=" * 70)
print("WIN RATE BY PHASE")
print("=" * 70)
print(df_chase.groupby('phase')['is_winner'].agg(['mean', 'count']))

# Win rate by wickets lost
print("\n" + "=" * 70)
print("WIN RATE BY WICKETS LOST")
print("=" * 70)
wicket_stats = df_chase.groupby('wickets_lost')['is_winner'].agg(['mean', 'count'])
print(wicket_stats)

# Win rate by required_run_rate bins
print("\n" + "=" * 70)
print("WIN RATE BY REQUIRED RUN RATE")
print("=" * 70)
rrr_bins = [0, 5, 6, 7, 8, 9, 10, 12, 15, 20, 100]
df_chase['rrr_bin'] = pd.cut(df_chase['required_run_rate'], bins=rrr_bins)
print(df_chase.groupby('rrr_bin')['is_winner'].agg(['mean', 'count']))

# Most important: Win rate by phase AND wickets
print("\n" + "=" * 70)
print("WIN RATE BY PHASE AND WICKETS LOST")
print("=" * 70)
pivot = df_chase.pivot_table(
    values='is_winner',
    index='wickets_lost',
    columns='phase',
    aggfunc=['mean', 'count']
)
print(pivot)

# Win rate by phase AND RRR
print("\n" + "=" * 70)
print("WIN RATE BY PHASE AND REQUIRED RUN RATE")
print("=" * 70)
rrr_bins_coarse = [0, 6, 8, 10, 12, 100]
df_chase['rrr_coarse'] = pd.cut(df_chase['required_run_rate'], bins=rrr_bins_coarse)
pivot2 = df_chase.pivot_table(
    values='is_winner',
    index='rrr_coarse',
    columns='phase',
    aggfunc=['mean', 'count']
)
print(pivot2)

# Key scenarios from our test cases
print("\n" + "=" * 70)
print("SPECIFIC SCENARIO ANALYSIS")
print("=" * 70)

# Scenario: Death overs (15+), 4 wickets lost, RRR 7-8
scenario1 = df_chase[
    (df_chase['overs_bowled'] >= 15) &
    (df_chase['wickets_lost'] == 4) &
    (df_chase['required_run_rate'] >= 7) &
    (df_chase['required_run_rate'] <= 8)
]
print(f"\nDeath overs (15+), 4 wickets, RRR 7-8:")
print(f"  Count: {len(scenario1)}")
print(f"  Win rate: {scenario1['is_winner'].mean():.1%}" if len(scenario1) > 0 else "  No data")

# Scenario: Middle overs (10), 3 wickets, RRR 7-8
scenario2 = df_chase[
    (df_chase['overs_bowled'] >= 9) &
    (df_chase['overs_bowled'] <= 11) &
    (df_chase['wickets_lost'] == 3) &
    (df_chase['required_run_rate'] >= 7) &
    (df_chase['required_run_rate'] <= 9)
]
print(f"\nMiddle overs (9-11), 3 wickets, RRR 7-9:")
print(f"  Count: {len(scenario2)}")
print(f"  Win rate: {scenario2['is_winner'].mean():.1%}" if len(scenario2) > 0 else "  No data")

# Scenario: Early overs (1-3), 1 wicket, RRR 7-9
scenario3 = df_chase[
    (df_chase['overs_bowled'] >= 1) &
    (df_chase['overs_bowled'] <= 3) &
    (df_chase['wickets_lost'] == 1) &
    (df_chase['required_run_rate'] >= 7) &
    (df_chase['required_run_rate'] <= 9)
]
print(f"\nEarly overs (1-3), 1 wicket, RRR 7-9:")
print(f"  Count: {len(scenario3)}")
print(f"  Win rate: {scenario3['is_winner'].mean():.1%}" if len(scenario3) > 0 else "  No data")

# Scenario: Death overs, 6 wickets, RRR > 10
scenario4 = df_chase[
    (df_chase['overs_bowled'] >= 15) &
    (df_chase['wickets_lost'] >= 6) &
    (df_chase['required_run_rate'] >= 10)
]
print(f"\nDeath overs (15+), 6+ wickets, RRR > 10:")
print(f"  Count: {len(scenario4)}")
print(f"  Win rate: {scenario4['is_winner'].mean():.1%}" if len(scenario4) > 0 else "  No data")
