"""
Resume recording for incomplete matches that were interrupted.

When a live predictor is stopped mid-match (Ctrl+C), the MatchStateLogger
is designed to allow resuming. This script resumes recording for incomplete
matches from where they left off.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

def check_incomplete_matches(match_states_dir: str = "data/match_states") -> dict:
    """Check for incomplete recorded matches (those without finalized metadata)."""
    match_states_path = Path(match_states_dir)
    
    incomplete = {}
    
    for league_dir in match_states_path.iterdir():
        if not league_dir.is_dir():
            continue
        
        league = league_dir.name
        metadata_file = league_dir / "match_metadata.parquet"
        
        if not metadata_file.exists():
            continue
        
        metadata = pd.read_parquet(metadata_file)
        
        # Check for incomplete matches (result_type != "completed")
        incomplete_rows = metadata[metadata['result_type'] != 'completed']
        
        if len(incomplete_rows) > 0:
            incomplete[league] = {
                'metadata': incomplete_rows,
                'league_dir': league_dir
            }
    
    return incomplete

def summarize_incomplete_matches():
    """Print summary of incomplete matches."""
    incomplete_matches = check_incomplete_matches()
    
    print("\n" + "="*80)
    print("INCOMPLETE MATCH RECORDINGS (Awaiting Innings 2 or Match Completion)")
    print("="*80)
    
    total_incomplete = 0
    
    for league, info in incomplete_matches.items():
        metadata = info['metadata']
        print(f"\n📋 League: {league.upper()}")
        print(f"   Incomplete matches: {len(metadata)}")
        
        for _, row in metadata.iterrows():
            match_id = row['match_id']
            team_a = row['team_a']
            team_b = row['team_b']
            result_type = row['result_type']
            
            # Load ball states to see last recorded ball
            match_file = info['league_dir'] / f"{match_id}.parquet"
            if match_file.exists():
                df = pd.read_parquet(match_file)
                last_inn = df['innings'].max()
                last_ball = len(df[df['innings'] == last_inn])
                last_overs = df[df['innings'] == last_inn]['over_number'].max()
                last_wickets = df[df['innings'] == last_inn]['wickets'].iloc[-1] if len(df) > 0 else 0
                
                print(f"\n   ⚠️  {team_a} vs {team_b}")
                print(f"      Status: {result_type}")
                print(f"      Last recorded: Inn{int(last_inn)} · {last_overs}.{last_ball} overs · {last_wickets} wickets")
                print(f"      Recording paused: {row['recording_end']}")
                print(f"      Match file: {match_file.name}")
                
                total_incomplete += 1
    
    print("\n" + "="*80)
    print(f"TOTAL INCOMPLETE RECORDINGS: {total_incomplete}")
    print("="*80)
    print("\nTo resume recording:")
    print("  1. Re-run: python -m src.bbl_pipeline.inference.crex_live_predictor \\")
    print("               --match-url <CREX_URL> --record-states")
    print("  2. MatchStateLogger will automatically resume (deduplicates using record keys)")
    print("  3. New ball states from Innings 2+ will be appended to existing file")
    print("="*80)

if __name__ == "__main__":
    summarize_incomplete_matches()
