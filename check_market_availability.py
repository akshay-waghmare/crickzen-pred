import pandas as pd
from pathlib import Path

match_states_dir = Path('data/match_states/t20i')
parquet_files = list(match_states_dir.glob('*.parquet'))
parquet_files = [f for f in parquet_files if f.name != 'match_metadata.parquet']

print("Checking market data availability across all T20I matches:\n")

for file in parquet_files:
    df = pd.read_parquet(file)
    market_count = df['market_batting_team_prob'].notna().sum()
    total_count = len(df)
    print(f'{file.stem:50s} | Market probs: {market_count:4d}/{total_count:4d}')

print("\n" + "="*80)

# Check what's in the match metadata
metadata = pd.read_parquet(match_states_dir / 'match_metadata.parquet')
print(f"\nMatch metadata shape: {metadata.shape}")
print(f"Columns: {metadata.columns.tolist()}")
if len(metadata) > 0:
    print(f"\nFirst match metadata:\n{metadata.iloc[0].to_string()}")
