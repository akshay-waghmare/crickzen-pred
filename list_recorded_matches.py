import pandas as pd
from pathlib import Path

# List all recorded matches
match_states_dir = Path('data/match_states/t20i')
parquet_files = list(match_states_dir.glob('*.parquet'))
parquet_files = [f for f in parquet_files if f.name != 'match_metadata.parquet']

print(f'Total recorded T20I matches: {len(parquet_files)}\n')
print('Recorded match files:')
for f in sorted(parquet_files):
    df = pd.read_parquet(f)
    print(f'  {f.stem}')
    print(f'    Balls: {len(df)} | Innings: {sorted(df["innings"].unique().tolist())}')
    print(f'    Market data: {df["market_batting_team_prob"].notna().sum()} non-null')
