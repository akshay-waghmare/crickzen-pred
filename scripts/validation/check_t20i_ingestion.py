import os
import pandas as pd
from pathlib import Path

# Count JSON files
json_dir = Path('data/raw_json/t20i')
json_files = list(json_dir.glob('*.json'))
print(f"📁 JSON files in raw_json/t20i: {len(json_files)}")

# Count parquet files
parquet_dir = Path('data/t20i_raw/matches')
if parquet_dir.exists():
    parquet_files = list(parquet_dir.glob('*.parquet'))
    print(f"📦 Parquet files created: {len(parquet_files)}")
    
    # Load all parquet files and count unique matches
    dfs = []
    for pf in parquet_files:
        try:
            df = pd.read_parquet(pf)
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {pf.name}: {e}")
    
    if dfs:
        full_df = pd.concat(dfs, ignore_index=True)
        unique_matches = full_df['match_id'].nunique()
        print(f"✅ Unique matches ingested: {unique_matches}")
        print(f"📊 Total ball-by-ball rows: {len(full_df):,}")
        print(f"\n❌ Skipped matches: {len(json_files) - unique_matches} ({100*(len(json_files) - unique_matches)/len(json_files):.1f}%)")
        
        # Check what matches are missing
        json_match_ids = set(int(f.stem) for f in json_files)
        ingested_match_ids = set(full_df['match_id'].unique())
        skipped_ids = json_match_ids - ingested_match_ids
        
        if skipped_ids:
            print(f"\n🔍 Sample skipped match IDs: {list(skipped_ids)[:10]}")
            
            # Try to load a skipped match and see why it was skipped
            import json
            sample_skipped = list(skipped_ids)[0]
            sample_path = json_dir / f"{sample_skipped}.json"
            with open(sample_path, 'r') as f:
                data = json.load(f)
            
            print(f"\n📋 Analyzing skipped match {sample_skipped}:")
            print(f"  Match type: {data['info'].get('match_type', 'unknown')}")
            print(f"  Has innings: {len(data.get('innings', []))}")
            print(f"  Has outcome: {'outcome' in data['info']}")
            if 'outcome' in data['info']:
                print(f"  Outcome: {data['info']['outcome']}")
            print(f"  Teams: {data['info'].get('teams', [])}")
else:
    print("❌ No parquet directory found - ingestion may not have run")
