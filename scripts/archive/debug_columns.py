import pandas as pd
from pathlib import Path

input_dir = Path("data/bbl_raw/matches")
match_files = list(input_dir.rglob("*.parquet"))
if match_files:
    df = pd.read_parquet(match_files[0])
    print("Columns:", df.columns.tolist())
else:
    print("No files found")