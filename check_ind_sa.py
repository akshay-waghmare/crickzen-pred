import pandas as pd

df = pd.read_parquet('data/match_states/t20i/ind-vs-sa-43rd-t20i--super-8-group-1st-match-t20-world-cup-2026.parquet')

print('IND vs SA Match - Data completeness:')
print(f'Total rows: {len(df)}')

inn1 = df[df['innings'] == 1]
inn2 = df[df['innings'] == 2]

print(f'\nInnings 1: {len(inn1)} rows')
print(f'Innings 2: {len(inn2)} rows')

print('\nInnings 1 market data:')
print(f'market_batting_team_prob non-null: {inn1["market_batting_team_prob"].notna().sum()}')
print(f'Team batting: {inn1["batting_team"].iloc[0] if len(inn1) > 0 else "N/A"}')
print(f'Overs covered: {inn1["over_number"].min()}-{inn1["over_number"].max()}')

if len(inn2) > 0:
    print('\nInnings 2 exists but:')
    print(f'market_batting_team_prob non-null: {inn2["market_batting_team_prob"].notna().sum()}')
else:
    print('\nInnings 2 was NOT recorded')

# Check metadata
metadata = pd.read_parquet('data/match_states/t20i/match_metadata.parquet')
ind_sa = metadata[metadata['match_id'] == 'ind-vs-sa-43rd-t20i--super-8-group-1st-match-t20-world-cup-2026']
if len(ind_sa) > 0:
    print('\nMatch metadata:')
    print(f'Winner: {ind_sa["winner"].values[0]}')
    print(f'Result type: {ind_sa["result_type"].values[0]}')
    print(f'Team A (SA) score: {ind_sa["team_a_score"].values[0]}')
    print(f'Team B (IND) score: {ind_sa["team_b_score"].values[0]}')
    print(f'Recording end time: {ind_sa["recording_end"].values[0]}')
