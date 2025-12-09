import pandas as pd
import os

file_path = 'data/training.parquet'
if os.path.exists(file_path):
    df = pd.read_parquet(file_path)
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")
    print(f"Duplicate rows: {df.duplicated().sum()}")
    # Check for duplicate match_id + ball combinations if possible
    if 'match_id' in df.columns and 'ball' in df.columns and 'inning' in df.columns:
         print(f"Duplicate balls: {df.duplicated(subset=['match_id', 'inning', 'over', 'ball']).sum()}")
else:
    print("File not found")
