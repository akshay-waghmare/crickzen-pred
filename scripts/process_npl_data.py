"""
Process Nepal Premier League (NPL) JSON data from Cricsheet.
Converts raw JSON files to parquet format for feature engineering.
"""
import pandas as pd
import json
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bbl_pipeline.ingestion.loader import load_match_file, iter_match_files
from src.bbl_pipeline.ingestion.processor import process_match

def process_npl_json_to_parquet():
    """
    Process NPL JSON files to raw parquet format.
    Similar to how WBBL and ILT20 data is processed.
    """
    print("="*70)
    print("Nepal Premier League (NPL) Data Processor")
    print("="*70)
    
    # Paths
    input_dir = Path("nepal_premier_leage_data/npl_json")
    output_dir = Path("data/npl_raw")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not input_dir.exists():
        print(f"ERROR: Input directory not found: {input_dir}")
        return
    
    # Collect all match records
    all_records = []
    super_over_records = []
    match_count = 0
    
    print(f"\nProcessing JSON files from {input_dir}...")
    
    for file_path in sorted(input_dir.glob("*.json")):
        try:
            match_id = file_path.stem  # e.g., "1462596"
            match_data = load_match_file(file_path)
            
            # Process the match
            main_records, so_records = process_match(match_data, match_id)
            
            all_records.extend(main_records)
            super_over_records.extend(so_records)
            match_count += 1
            
            if match_count % 10 == 0:
                print(f"  Processed {match_count} matches...")
                
        except Exception as e:
            print(f"  WARNING: Failed to process {file_path.name}: {e}")
            continue
    
    print(f"\nProcessed {match_count} matches total")
    print(f"Total ball-by-ball records: {len(all_records)}")
    
    if not all_records:
        print("ERROR: No records extracted!")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(all_records)
    
    # Add league identifier
    df['league'] = 'NPL'
    
    # Sort by match, innings, over, ball
    df = df.sort_values(['match_id', 'innings', 'over', 'ball'])
    
    # Save to parquet
    output_path = output_dir / "npl_raw.parquet"
    df.to_parquet(output_path, index=False)
    print(f"\nSaved raw data to {output_path}")
    
    # Print summary
    print("\n" + "="*70)
    print("DATA SUMMARY")
    print("="*70)
    print(f"Total matches: {df['match_id'].nunique()}")
    print(f"Total ball-by-ball records: {len(df)}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"\nTeams:")
    for team in sorted(df['batting_team'].dropna().unique()):
        matches = df[df['batting_team'] == team]['match_id'].nunique()
        print(f"  - {team}: {matches} matches")
    
    print(f"\nVenues:")
    for venue in sorted(df['venue_id'].dropna().unique()):
        matches = df[df['venue_id'] == venue]['match_id'].nunique()
        print(f"  - {venue}: {matches} matches")
    
    print(f"\nColumns: {list(df.columns)}")
    
    # Also save super over data if any
    if super_over_records:
        so_df = pd.DataFrame(super_over_records)
        so_df['league'] = 'NPL'
        so_path = output_dir / "npl_super_overs.parquet"
        so_df.to_parquet(so_path, index=False)
        print(f"\nSaved {len(so_df)} super over records to {so_path}")
    
    return df


if __name__ == "__main__":
    process_npl_json_to_parquet()
