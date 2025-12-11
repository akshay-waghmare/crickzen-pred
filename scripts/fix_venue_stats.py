"""
Fix venue stats in the feature store.
The original venue_avg_score was total match runs (both innings) instead of first innings only.
This script recalculates venue stats correctly using only first innings data.
"""

import pandas as pd
from pathlib import Path
import numpy as np

def main():
    # Load all raw ball-by-ball data
    raw_path = Path('data/wbbl_raw/matches')
    all_files = list(raw_path.rglob('*.parquet'))
    print(f'Loading {len(all_files)} files...')

    df = pd.concat([pd.read_parquet(f) for f in all_files], ignore_index=True)
    print(f'Total balls (with duplicates): {len(df)}')

    # Remove duplicates - the raw data has each row duplicated
    dup_cols = ['match_id', 'innings', 'over', 'ball']
    df = df.drop_duplicates(subset=dup_cols, keep='first')
    print(f'Total balls (after dedup): {len(df)}')

    # Get first innings scores per match
    print('\nCalculating first innings stats per venue...')
    first_innings = df[df['innings'] == 1].groupby(['match_id', 'venue_id', 'date']).agg({
        'runs_total': 'sum',
        'wicket_type': lambda x: x.notna().sum(),
        'winner': 'first',
        'batting_team_id': 'first'
    }).reset_index()

    first_innings.columns = ['match_id', 'venue', 'date', 'first_innings_score', 'first_innings_wickets', 'winner', 'batting_team']

    # Calculate bat_first_win
    first_innings['bat_first_win'] = (first_innings['winner'] == first_innings['batting_team']).astype(int)

    print(f'Matches: {len(first_innings)}')
    print(f'First innings score stats:')
    print(first_innings['first_innings_score'].describe())

    # Calculate venue averages (mean per venue)
    first_innings = first_innings.sort_values('date')

    venue_stats = first_innings.groupby('venue').agg({
        'first_innings_score': 'mean',
        'first_innings_wickets': 'mean', 
        'bat_first_win': 'mean'
    }).reset_index()

    venue_stats.columns = ['venue', 'venue_avg_score', 'venue_avg_wickets', 'venue_bat_first_win_rate']
    venue_stats = venue_stats.set_index('venue')

    print(f'\nVenue stats (corrected):')
    print(venue_stats.head(10))
    print(f'\nvenue_avg_score stats:')
    print(venue_stats['venue_avg_score'].describe())

    # Backup old file
    store_path = Path('data/wbbl_feature_store_v2')
    old_path = store_path / 'venue_stats.parquet'
    if old_path.exists():
        backup_path = store_path / 'venue_stats_backup_wrong.parquet'
        import shutil
        shutil.copy(old_path, backup_path)
        print(f'\nBacked up old (incorrect) venue stats to {backup_path}')

    # Save corrected venue stats
    venue_stats.to_parquet(store_path / 'venue_stats.parquet')
    print(f'Saved corrected venue stats to {store_path / "venue_stats.parquet"}')

    # Verify
    print('\n--- Verification ---')
    df_new = pd.read_parquet(store_path / 'venue_stats.parquet')
    print(f'North Sydney Oval: {df_new.loc["North Sydney Oval"].to_dict() if "North Sydney Oval" in df_new.index else "Not found"}')

if __name__ == '__main__':
    main()
