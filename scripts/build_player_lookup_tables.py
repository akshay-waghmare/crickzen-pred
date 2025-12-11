"""
Build player-venue and player-vs-team lookup tables for live inference.
These enable fuzzy-matched historical stats during real-time predictions.
"""

import pandas as pd
from pathlib import Path
import numpy as np

def main():
    # Load all raw ball-by-ball data
    raw_path = Path('data/wbbl_raw/matches')
    all_files = list(raw_path.rglob('*.parquet'))
    print(f'Loading {len(all_files)} files...')

    # Combine all files  
    df = pd.concat([pd.read_parquet(f) for f in all_files], ignore_index=True)
    print(f'Total balls (with duplicates): {len(df)}')
    
    # Remove duplicates - the raw data has each row duplicated
    dup_cols = ['match_id', 'innings', 'over', 'ball']
    df = df.drop_duplicates(subset=dup_cols, keep='first')
    print(f'Total balls (after dedup): {len(df)}')
    
    print(f'Unique batters: {df["batter_id"].nunique()}')
    print(f'Unique bowlers: {df["bowler_id"].nunique()}')
    print(f'Unique venues: {df["venue_id"].nunique()}')
    print(f'Unique teams: {df["batting_team_id"].nunique()}')

    # Create player-venue batting stats
    print('\nComputing player-venue batting stats...')
    batting_venue = df.groupby(['batter_id', 'venue_id']).agg({
        'runs_batter': 'sum',
        'ball': 'count'
    }).reset_index()
    batting_venue.columns = ['player', 'venue', 'runs', 'balls']
    # Approximate innings as balls/20 (typical innings)
    batting_venue['innings'] = (batting_venue['balls'] / 20).clip(lower=1)
    batting_venue['batsman_venue_avg'] = batting_venue['runs'] / batting_venue['innings']
    batting_venue['batsman_venue_sr'] = (batting_venue['runs'] / batting_venue['balls'].clip(lower=1)) * 100
    print(f'Player-venue batting combinations: {len(batting_venue)}')
    print(batting_venue.head())

    # Create player-vs-team batting stats
    print('\nComputing player-vs-team batting stats...')
    batting_vs_team = df.groupby(['batter_id', 'bowling_team_id']).agg({
        'runs_batter': 'sum',
        'ball': 'count'
    }).reset_index()
    batting_vs_team.columns = ['player', 'opponent', 'runs', 'balls']
    batting_vs_team['innings'] = (batting_vs_team['balls'] / 20).clip(lower=1)
    batting_vs_team['batsman_vs_team_avg'] = batting_vs_team['runs'] / batting_vs_team['innings']
    print(f'Player-vs-team batting combinations: {len(batting_vs_team)}')
    print(batting_vs_team.head())

    # Create bowler-venue stats
    print('\nComputing bowler-venue stats...')
    bowling_venue = df.groupby(['bowler_id', 'venue_id']).agg({
        'runs_total': 'sum',
        'ball': 'count',
        'wicket_type': lambda x: x.notna().sum()
    }).reset_index()
    bowling_venue.columns = ['player', 'venue', 'runs_conceded', 'balls', 'wickets']
    bowling_venue['bowler_venue_econ'] = (bowling_venue['runs_conceded'] / bowling_venue['balls'].clip(lower=1)) * 6
    bowling_venue['bowler_venue_sr'] = bowling_venue['balls'] / bowling_venue['wickets'].clip(lower=1)
    print(f'Bowler-venue combinations: {len(bowling_venue)}')

    # Create bowler-vs-team stats
    print('\nComputing bowler-vs-team stats...')
    bowling_vs_team = df.groupby(['bowler_id', 'batting_team_id']).agg({
        'runs_total': 'sum',
        'ball': 'count',
        'wicket_type': lambda x: x.notna().sum()
    }).reset_index()
    bowling_vs_team.columns = ['player', 'opponent', 'runs_conceded', 'balls', 'wickets']
    bowling_vs_team['bowler_vs_team_econ'] = (bowling_vs_team['runs_conceded'] / bowling_vs_team['balls'].clip(lower=1)) * 6
    print(f'Bowler-vs-team combinations: {len(bowling_vs_team)}')

    # Save to feature store
    store_path = Path('data/wbbl_feature_store_v2')
    batting_venue[['player', 'venue', 'batsman_venue_avg', 'batsman_venue_sr']].to_parquet(
        store_path / 'player_venue_batting.parquet', index=False)
    batting_vs_team[['player', 'opponent', 'batsman_vs_team_avg']].to_parquet(
        store_path / 'player_vs_team_batting.parquet', index=False)
    bowling_venue[['player', 'venue', 'bowler_venue_econ', 'bowler_venue_sr']].to_parquet(
        store_path / 'player_venue_bowling.parquet', index=False)
    bowling_vs_team[['player', 'opponent', 'bowler_vs_team_econ']].to_parquet(
        store_path / 'player_vs_team_bowling.parquet', index=False)

    print('\nSaved lookup tables to feature store!')
    print([f.name for f in store_path.glob('*.parquet')])
    
    # Show sample lookups
    print('\n--- Sample data ---')
    print('\nTop batters at Adelaide Oval:')
    print(batting_venue[batting_venue['venue'] == 'Adelaide Oval'].nlargest(5, 'batsman_venue_avg')[['player', 'batsman_venue_avg', 'batsman_venue_sr']])

if __name__ == '__main__':
    main()
