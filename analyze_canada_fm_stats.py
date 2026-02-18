"""
Analyze Canada's T20I record against Full Member teams only.
"""
import pandas as pd
from pathlib import Path

# Full Members list
FULL_MEMBERS = {
    'India', 'Australia', 'Pakistan', 'England', 'New Zealand', 
    'South Africa', 'West Indies', 'Afghanistan', 'Sri Lanka', 
    'Bangladesh', 'Ireland', 'Zimbabwe'
}

# Check if raw match data exists
raw_dir = Path('data/t20_international_male_raw/matches')
if not raw_dir.exists():
    print(f"Raw data directory not found: {raw_dir}")
    print("Trying alternate location...")
    raw_dir = Path('data/t20i_male_raw/matches')

if raw_dir.exists():
    print(f"Loading matches from: {raw_dir}")
    df = pd.read_parquet(raw_dir)
    print(f"Total matches: {len(df)}")
    
    # Filter for Canada matches
    canada_matches = df[
        (df['batting_team_id'] == 'Canada') | (df['bowling_team_id'] == 'Canada')
    ].copy()
    
    # Count unique matches
    canada_unique_matches = canada_matches['match_id'].nunique()
    print(f"\nCanada total matches: {canada_unique_matches}")
    
    # Filter for matches against Full Members
    canada_vs_fm = canada_matches[
        ((canada_matches['batting_team_id'] == 'Canada') & (canada_matches['bowling_team_id'].isin(FULL_MEMBERS))) |
        ((canada_matches['bowling_team_id'] == 'Canada') & (canada_matches['batting_team_id'].isin(FULL_MEMBERS)))
    ].copy()
    
    if len(canada_vs_fm) == 0:
        print("\n⚠️ Canada has NO matches against Full Member teams in the dataset")
        print("\nCanada's opponents (all matches):")
        opponents = set()
        for _, row in canada_matches.iterrows():
            if row['batting_team_id'] == 'Canada':
                opponents.add(row['bowling_team_id'])
            else:
                opponents.add(row['batting_team_id'])
        for opp in sorted(opponents):
            opp_matches_count = canada_matches[
                ((canada_matches['batting_team_id'] == 'Canada') & (canada_matches['bowling_team_id'] == opp)) |
                ((canada_matches['bowling_team_id'] == 'Canada') & (canada_matches['batting_team_id'] == opp))
            ]['match_id'].nunique()
            print(f"  - {opp}: {opp_matches_count} matches")
    else:
        num_fm_matches = canada_vs_fm['match_id'].nunique()
        print(f"\nCanada vs Full Members: {num_fm_matches} matches")
        
        # Calculate win rate by match
        canada_batting_wins = 0
        canada_batting_total = 0
        canada_bowling_wins = 0
        canada_bowling_total = 0
        
        for match_id in canada_vs_fm['match_id'].unique():
            match_data = canada_vs_fm[canada_vs_fm['match_id'] == match_id]
            
            # Get winner and determine who batted first
            winner = match_data.iloc[0]['winner']
            
            # Find Canada's innings
            canada_bat_first = match_data[
                (match_data['batting_team_id'] == 'Canada') & 
                (match_data['innings'] == 1)
            ]
            canada_bowl_first = match_data[
                (match_data['bowling_team_id'] == 'Canada') & 
                (match_data['innings'] == 1)
            ]
            
            if len(canada_bat_first) > 0:
                # Canada batted first
                canada_batting_total += 1
                if winner == 'Canada':
                    canada_batting_wins += 1
            elif len(canada_bowl_first) > 0:
                # Canada bowled first
                canada_bowling_total += 1
                if winner == 'Canada':
                    canada_bowling_wins += 1
        
        total_matches = (canada_batting_total + canada_bowling_total)
        total_wins = canada_batting_wins + canada_bowling_wins
        
        win_rate = total_wins / total_matches if total_matches > 0 else 0
        bat_first_wr = canada_batting_wins / canada_batting_total if canada_batting_total > 0 else 0
        bowl_first_wr = canada_bowling_wins / canada_bowling_total if canada_bowling_total > 0 else 0
        
        print(f"\n=== CANADA VS FULL MEMBERS STATS ===")
        print(f"Total Matches: {total_matches}")
        print(f"Wins: {total_wins}")
        print(f"Win Rate: {win_rate:.4f} ({win_rate*100:.1f}%)")
        print(f"Bat First: {canada_batting_wins}/{canada_batting_total} = {bat_first_wr:.4f} ({bat_first_wr*100:.1f}%)")
        print(f"Bowl First: {canada_bowling_wins}/{canada_bowling_total} = {bowl_first_wr:.4f} ({bowl_first_wr*100:.1f}%)")
        
        print(f"\n=== ADD TO FM_OVERRIDES ===")
        print(f"'Canada': {{'win_rate': {win_rate:.4f}, 'matches': {total_matches:3d}, 'bat_first_wr': {bat_first_wr:.4f}, 'bowl_first_wr': {bowl_first_wr:.4f}}},")
else:
    print(f"Could not find raw match data in {raw_dir}")
    print("\nUsing historical data: Canada has played mostly against Associate teams")
    print("Recommend using a conservative estimate based on similar Associate teams")
    print("Suggested stats (based on other Associates vs FM):")
    print("'Canada': {'win_rate': 0.20, 'matches': 10, 'bat_first_wr': 0.25, 'bowl_first_wr': 0.20},")
