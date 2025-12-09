import pandas as pd
from pathlib import Path

input_dir = Path('data/bbl_raw/matches')
match_files = list(input_dir.rglob("*.parquet"))

print(f"Found {len(match_files)} parquet files.")

df = pd.concat([pd.read_parquet(f) for f in match_files], ignore_index=True)
print(f"Total rows: {len(df)}")

if 'match_id' in df.columns:
    match_counts = df['match_id'].value_counts()
    print(f"Unique matches: {len(match_counts)}")
    print(f"Max rows for a single match: {match_counts.max()}")
    print(f"Min rows for a single match: {match_counts.min()}")
    
    # Check if we have duplicate rows (exact duplicates)
    duplicates = df.duplicated().sum()
    print(f"Exact duplicate rows: {duplicates}")
    
    # Check if we have duplicate (match_id, inning, over, ball)
    if 'inning' in df.columns and 'over' in df.columns and 'ball' in df.columns:
        ball_dupes = df.duplicated(subset=['match_id', 'inning', 'over', 'ball']).sum()
        print(f"Duplicate balls: {ball_dupes}")
