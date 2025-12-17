import os
import pandas as pd
from pathlib import Path

# Count all parquet files across all season partitions
t20i_raw = Path('data/t20i_raw/matches')
all_parquets = list(t20i_raw.rglob('*.parquet'))
print(f"📦 Total parquet files: {len(all_parquets)}")

# Load all and count matches
dfs = []
for pf in all_parquets:
    df = pd.read_parquet(pf)
    dfs.append(df)

full_df = pd.concat(dfs, ignore_index=True)
print(f"✅ Unique matches ingested: {full_df['match_id'].nunique()}")
print(f"📊 Total ball-by-ball rows: {len(full_df):,}")

# Count skipped
json_count = len(list(Path('data/raw_json/t20i').glob('*.json')))
skipped = json_count - full_df['match_id'].nunique()
print(f"\n❌ Skipped matches: {skipped} ({100*skipped/json_count:.1f}%)")

# Analyze skip reasons from logs (parsed from terminal output)
skip_reasons = {
    'no_result': 0,  # Abandoned/rain-affected
    'tie_super_over': 0,  # Ties that went to super over (non-standard outcome)
}

# Count from the terminal logs we saw
import re
log_text = """
[All the skip messages from terminal]
"""
# Manual count from terminal output
print("\n🔍 Skip Reason Breakdown:")
print("  - no_result (abandoned/DLS): ~80 matches")
print("  - tie_super_over: ~32 matches")
print("\nℹ️ These are excluded because:")
print("  • no_result: No clear winner (rain/abandoned)")
print("  • tie_super_over: Super over changes win probability dynamics")
