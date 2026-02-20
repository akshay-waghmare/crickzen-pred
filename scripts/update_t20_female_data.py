#!/usr/bin/env python
"""
Update T20 Female Data Pipeline

This script:
1. Copies T20 matches from recently_played_30_female_json to respective league folders
2. Combines all female T20 league folders into data/t20_female_json/
3. Prepares the data for retraining the global T20 female model

Usage:
    python scripts/update_t20_female_data.py --dry-run  # Preview changes
    python scripts/update_t20_female_data.py            # Execute changes
"""

import json
import shutil
from pathlib import Path
from collections import defaultdict
import argparse


# Event name patterns -> target league folder
EVENT_TO_LEAGUE_FOLDER = {
    "Big Bash League": "wbbl_female_json",
    "Women's Big Bash League": "wbbl_female_json",
    "WBBL": "wbbl_female_json",
    
    "Women's Super Smash": "wssm_female_json",
    "Super Smash": "wssm_female_json",  # NZ Super Smash (female version in female folder)
    
    "Women's Premier League": "wpl_female_json",
    "WPL": "wpl_female_json",
    
    "Women's T20 World Cup": "icc_wt20wc_female_json",
    "Women's T20 World Cup Qualifier": "icc_wt20wc_female_json",
    "ICC Women's T20 World Cup": "icc_wt20wc_female_json",
    
    "Charlotte Edwards Cup": "cec_female_json",
    
    "Women's Caribbean Premier League": "wcpl_female_json",
    "WCPL": "wcpl_female_json",
    
    "Women's Caribbean Super League": "wcsl_female_json",
    
    "FairBreak Invitational": "fairbreak_female_json",
    "FairBreak": "fairbreak_female_json",
    
    "The Blaze": "blz_female_json",
    "Rachael Heyhoe Flint Trophy": "blz_female_json",
    
    "Women's T20 Blast": "wt20blast_female_json",
    
    "Women's T20 Challenge": "wt20challenge_female_json",
    
    # SA20 Female
    "SA20": "sa20_female_json",
    
    # Bangladesh Premier League Female
    "Bangladesh Premier League": "bpl_female_json",
    "BPL": "bpl_female_json",
    
    # Lotus Cup
    "Lotus Cup": "lotus_cup_female_json",
    
    # International tours - we'll put these in a generic folder
    "tour": "t20i_female_json",  # Partial match for tours
}

# League folders to include in the global model
FEMALE_T20_LEAGUE_FOLDERS = [
    "wbbl_female_json",
    "wssm_female_json", 
    "wpl_female_json",
    "icc_wt20wc_female_json",
    "cec_female_json",
    "wcpl_female_json",
    "wcsl_female_json",
    "fairbreak_female_json",
    "blz_female_json",
    "wt20blast_female_json",
    "wt20challenge_female_json",
    "t20i_female_json",  # International T20s
    "sa20_female_json",  # SA20 Female
    "bpl_female_json",   # Bangladesh Premier League Female
    "lotus_cup_female_json",  # Lotus Cup
]


def get_target_folder(event_name: str) -> str | None:
    """Map event name to target league folder."""
    event_lower = event_name.lower()
    
    # Direct match first
    for pattern, folder in EVENT_TO_LEAGUE_FOLDER.items():
        if pattern.lower() == event_lower:
            return folder
    
    # Partial match
    for pattern, folder in EVENT_TO_LEAGUE_FOLDER.items():
        if pattern.lower() in event_lower:
            return folder
    
    # Check if it's a tour (international T20)
    if "tour" in event_lower:
        return "t20i_female_json"
    
    return None


def copy_recently_played_to_leagues(source_dir: Path, dry_run: bool = False) -> dict:
    """Copy T20 matches from recently_played to their respective league folders."""
    results = defaultdict(list)
    skipped = []
    
    for json_file in sorted(source_dir.glob("*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            match_type = data.get('info', {}).get('match_type', '')
            
            # Only process T20 matches
            if match_type != 'T20':
                continue
            
            event_name = data.get('info', {}).get('event', {}).get('name', '')
            teams = data.get('info', {}).get('teams', [])
            dates = data.get('info', {}).get('dates', ['?'])
            
            target_folder = get_target_folder(event_name)
            
            if target_folder:
                target_path = Path(target_folder)
                
                # Create folder if it doesn't exist
                if not target_path.exists() and not dry_run:
                    target_path.mkdir(parents=True, exist_ok=True)
                
                dest_file = target_path / json_file.name
                
                results[target_folder].append({
                    'file': json_file.name,
                    'event': event_name,
                    'teams': ' vs '.join(teams),
                    'date': dates[0] if dates else '?'
                })
                
                if not dry_run:
                    shutil.copy2(json_file, dest_file)
            else:
                skipped.append({
                    'file': json_file.name,
                    'event': event_name,
                    'teams': ' vs '.join(teams)
                })
                
        except Exception as e:
            print(f"Error processing {json_file.name}: {e}")
    
    return dict(results), skipped


def combine_leagues_to_global(output_dir: Path, dry_run: bool = False) -> dict:
    """Combine all female T20 league folders into a single global folder."""
    output_dir = Path(output_dir)
    
    if not dry_run:
        # Clean and recreate the output directory
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    total_files = 0
    
    for league_folder in FEMALE_T20_LEAGUE_FOLDERS:
        league_path = Path(league_folder)
        
        if not league_path.exists():
            results[league_folder] = 0
            continue
        
        json_files = list(league_path.glob("*.json"))
        results[league_folder] = len(json_files)
        total_files += len(json_files)
        
        if not dry_run:
            # Create league subfolder in output
            league_output = output_dir / league_folder.replace("_female_json", "").replace("_json", "")
            league_output.mkdir(parents=True, exist_ok=True)
            
            for json_file in json_files:
                shutil.copy2(json_file, league_output / json_file.name)
    
    results['_total'] = total_files
    return results


def main():
    parser = argparse.ArgumentParser(description="Update T20 Female Data")
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without executing')
    parser.add_argument('--skip-copy', action='store_true', help='Skip copying from recently_played')
    parser.add_argument('--skip-combine', action='store_true', help='Skip combining leagues')
    args = parser.parse_args()
    
    source_dir = Path("recently_played_30_female_json")
    global_output = Path("data/t20_female_json")
    
    print("=" * 60)
    print("  T20 FEMALE DATA UPDATE")
    print("=" * 60)
    
    if args.dry_run:
        print("  MODE: DRY RUN (no files will be modified)")
    print()
    
    # Step 1: Copy recently played to league folders
    if not args.skip_copy:
        print("STEP 1: Copying T20 matches from recently_played to league folders")
        print("-" * 60)
        
        copied, skipped = copy_recently_played_to_leagues(source_dir, args.dry_run)
        
        for folder, matches in sorted(copied.items()):
            print(f"\n{folder}: {len(matches)} matches")
            for m in matches[:5]:  # Show first 5
                print(f"  {m['file']}: {m['teams']} ({m['date']})")
            if len(matches) > 5:
                print(f"  ... and {len(matches) - 5} more")
        
        if skipped:
            print(f"\nSKIPPED (no target folder): {len(skipped)} matches")
            for m in skipped[:5]:
                print(f"  {m['file']}: {m['event']} - {m['teams']}")
            if len(skipped) > 5:
                print(f"  ... and {len(skipped) - 5} more")
        
        total_copied = sum(len(m) for m in copied.values())
        print(f"\nTotal: {'Would copy' if args.dry_run else 'Copied'} {total_copied} T20 matches")
    else:
        print("STEP 1: SKIPPED (--skip-copy)")
    
    print()
    
    # Step 2: Combine all leagues into global folder
    if not args.skip_combine:
        print("STEP 2: Combining all female T20 leagues into data/t20_female_json/")
        print("-" * 60)
        
        league_counts = combine_leagues_to_global(global_output, args.dry_run)
        
        print("\nLeague file counts:")
        for folder, count in sorted(league_counts.items()):
            if folder != '_total':
                status = "✓" if count > 0 else "✗"
                print(f"  {status} {folder}: {count} files")
        
        print(f"\nTotal: {'Would combine' if args.dry_run else 'Combined'} {league_counts['_total']} files into {global_output}/")
    else:
        print("STEP 2: SKIPPED (--skip-combine)")
    
    print()
    print("=" * 60)
    
    if not args.dry_run:
        print("\nNEXT STEPS:")
        print("  1. Run: bbl-pipeline retrain --league t20_female --version v4")
        print("  2. Or manually:")
        print("     bbl-pipeline ingest --input-dir data/t20_female_json --output-dir data/t20_female_raw")
        print("     bbl-pipeline process --input-dir data/t20_female_raw/matches --output-dir data/t20_female_features_v4 --feature-store-dir data/t20_female_feature_store_v4")
        print("     bbl-pipeline calibrate-league --global-model models/t20_female_v4 --input-file data/wpl_features/training.parquet --league wpl")
    else:
        print("\nRun without --dry-run to execute these changes.")


if __name__ == "__main__":
    main()
