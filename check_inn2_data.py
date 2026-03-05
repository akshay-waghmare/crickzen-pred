import pandas as pd

df = pd.read_parquet('data/match_states/t20i/ind-vs-ned-36th-match-t20-world-cup-2026.parquet')

print('INNINGS 1:')
inn1 = df[df['innings'] == 1]
print(f'  Total rows: {len(inn1)}')
print(f'  model_final_prob non-null: {inn1["model_final_prob"].notna().sum()}')
print(f'  market_batting_team_prob non-null: {inn1["market_batting_team_prob"].notna().sum()}')

print('\nINNINGS 2:')
inn2 = df[df['innings'] == 2]
print(f'  Total rows: {len(inn2)}')
print(f'  model_final_prob non-null: {inn2["model_final_prob"].notna().sum()}')
print(f'  market_batting_team_prob non-null: {inn2["market_batting_team_prob"].notna().sum()}')

print('\nSample Inn2 probabilities:')
print(inn2[['over_number', 'ball_in_over', 'total_runs', 'wickets', 'model_final_prob', 'market_batting_team_prob']].head(10).to_string())
