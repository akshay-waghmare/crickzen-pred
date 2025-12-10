import pandas as pd
import os
import re

def merge_match_data(match_dir, ball_by_ball_dir):
    """
    Merge the ball-by-ball data with the corrected data to create a unified dataset.
    """
    # Read the corrected data
    corrected_data = pd.read_csv(os.path.join(ball_by_ball_dir, 'corrected_data.csv'))
    
    # Read both innings data
    first_innings = pd.read_csv(os.path.join(ball_by_ball_dir, 'First_innings_summary.csv'))
    second_innings = pd.read_csv(os.path.join(ball_by_ball_dir, 'Second_innings_summary.csv'))
    
    # Combine both innings data
    ball_by_ball_data = pd.concat([first_innings, second_innings])
    
    # Rename columns in corrected_data to match with ball_by_ball_data
    corrected_data = corrected_data.rename(columns={
        'innings': 'batting_team',
        'over': 'over_number',
        'fav_team': 'favored_team',
        'win_probability': 'win_percentage'
    })
    
    # Merge based on batting team and over number
    merged_data = pd.merge(
        corrected_data,
        ball_by_ball_data,
        on=['batting_team', 'over_number'],
        how='outer'
    )
    
    # Handle duplicate columns and rename for clarity
    if 'total_runs_x' in merged_data.columns and 'total_runs_y' in merged_data.columns:
        merged_data['total_runs'] = merged_data['total_runs_y'].fillna(merged_data['total_runs_x'])
        merged_data = merged_data.drop(['total_runs_x', 'total_runs_y'], axis=1)
    
    # Clean up and organize columns
    desired_columns = [
        'batting_team', 'over_number', 'ball_number', 'runs_scored', 
        'boundaries', 'dot_balls', 'wickets', 'extras',
        'favored_team', 'win_percentage',
        'batsman1_name', 'batsman1_runs', 'batsman1_balls_faced', 'batsman1_fours', 'batsman1_sixes',
        'batsman2_name', 'batsman2_runs', 'batsman2_balls_faced', 'batsman2_fours', 'batsman2_sixes',
        'bowler1_name', 'bowler1_overs_bowled', 'bowler1_maidens_bowled', 'bowler1_runs_conceded', 'bowler1_wickets_taken',
        'bowler2_name', 'bowler2_overs_bowled', 'bowler2_maidens_bowled', 'bowler2_runs_conceded', 'bowler2_wickets_taken',
        'venue', 'matches_played', 'average_runs_per_wicket', 'average_runs_per_over'
    ]
    
    # Add historical player stats
    merged_data = enrich_with_player_stats(merged_data, ball_by_ball_dir)
    
    # Add new columns to desired_columns
    historical_columns = [
        'batsman1_historical_average', 'batsman1_historical_strike_rate',
        'batsman2_historical_average', 'batsman2_historical_strike_rate',
        'bowler1_historical_average', 'bowler1_historical_economy', 'bowler1_historical_strike_rate',
        'bowler2_historical_average', 'bowler2_historical_economy', 'bowler2_historical_strike_rate'
    ]
    desired_columns.extend(historical_columns)
    
    # Keep only columns that exist in the merged data
    existing_columns = [col for col in desired_columns if col in merged_data.columns]
    merged_data = merged_data[existing_columns]
    
    # Ensure all required columns exist, fill with defaults if missing
    for col in desired_columns:
        if col not in merged_data.columns:
            if col == 'favored_team':
                merged_data[col] = ''
            elif col == 'win_percentage':
                merged_data[col] = 0.0
            if 'name' in col:
                merged_data[col] = ''
            elif any(x in col for x in ['runs', 'balls', 'fours', 'sixes', 'wickets', 'maidens']):
                merged_data[col] = 0
            else:
                merged_data[col] = ''
    
    # Sort columns according to desired order
    merged_data = merged_data[desired_columns]
    
    # Save the merged data
    output_file = os.path.join(ball_by_ball_dir, 'unified_match_data_enriched.csv')
    merged_data.to_csv(output_file, index=False)
    print(f"Merged data saved to: {output_file}")
    
    return merged_data

def clean_player_name(name):
    """Clean player name by removing special characters, captaincy indicators, and normalizing spaces"""
    if pd.isna(name):
        return name
    
    # Remove (c) and (wk) indicators
    name = re.sub(r'\(c\)|\(wk\)', '', name)
    
    # Remove trailing commas
    name = name.strip(',')
    
    # Keep only alphanumeric chars and spaces, handle special characters
    name = ''.join(c for c in name if c.isalnum() or c.isspace() or c in "-'")
    
    # Normalize spaces and strip
    return ' '.join(name.split())

def load_team_stats(match_dir, team, encoding_list=['utf-8', 'latin1', 'cp1252']):
    """Load team statistics with multiple encoding attempts"""
    stats = {}
    
    for file_type in ['batting', 'bowling']:
        filename = os.path.join(match_dir, f'{team}_{file_type}_stats.csv')
        if not os.path.exists(filename):
            print(f"Warning: {filename} not found")
            continue
            
        for encoding in encoding_list:
            try:
                df = pd.read_csv(filename, encoding=encoding)
                df['clean_name'] = df['player_name'].apply(clean_player_name)
                df['lower_name'] = df['clean_name'].str.lower()
                stats[file_type] = df
                print(f"Successfully loaded {team} {file_type} stats with {encoding} encoding")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"Error loading {filename}: {e}")
                break
                
    return stats

def find_player_match(name, stats_df):
    """Find matching player in stats dataframe using multiple matching strategies"""
    if stats_df is None or stats_df.empty:
        return None
        
    clean_name = clean_player_name(name)
    lower_name = clean_name.lower()
    
    # Try exact match
    match = stats_df[stats_df['lower_name'] == lower_name]
    if not match.empty:
        return match.iloc[0]
    
    # Try partial match
    match = stats_df[stats_df['lower_name'].str.contains(lower_name, na=False)]
    if not match.empty:
        return match.iloc[0]
    
    # Try fuzzy match (remove spaces and special chars)
    simplified_name = re.sub(r'[^a-z]', '', lower_name)
    stats_df['simplified_name'] = stats_df['lower_name'].apply(lambda x: re.sub(r'[^a-z]', '', x))
    match = stats_df[stats_df['simplified_name'].str.contains(simplified_name, na=False)]
    if not match.empty:
        return match.iloc[0]
    
    return None

def enrich_with_player_stats(merged_data, match_dir):
    """Add historical player statistics to the unified match data"""
    teams = merged_data['batting_team'].unique()
    print(f"\nTeams found in merged data: {teams}")
    
    # Initialize stats for all teams
    team_stats = {team: load_team_stats(match_dir, team) for team in teams}
    
    # Initialize historical columns if they don't exist
    historical_columns = {
        'batsman': ['historical_average', 'historical_strike_rate'],
        'bowler': ['historical_average', 'historical_economy', 'historical_strike_rate']
    }
    
    for role in ['batsman1', 'batsman2', 'bowler1', 'bowler2']:
        base = role.replace('1', '').replace('2', '')
        for stat in historical_columns[base]:
            col = f"{role}_{stat}"
            if col not in merged_data.columns:
                merged_data[col] = 0.0
    
    # Process each row
    for idx, row in merged_data.iterrows():
        batting_team = row['batting_team']
        bowling_team = next(team for team in teams if team != batting_team)
        
        # Process batsmen
        for i in [1, 2]:
            batsman_name = row[f'batsman{i}_name']
            if pd.notna(batsman_name) and 'batting' in team_stats[batting_team]:
                stats_df = team_stats[batting_team]['batting']
                match = find_player_match(batsman_name, stats_df)
                if match is not None:
                    merged_data.at[idx, f'batsman{i}_historical_average'] = match['average']
                    merged_data.at[idx, f'batsman{i}_historical_strike_rate'] = match['strike_rate']
                    print(f"Found match for {batsman_name} -> {match['player_name']}")
                else:
                    print(f"No match found for {batsman_name}")
        
        # Process bowlers
        for i in [1, 2]:
            bowler_name = row[f'bowler{i}_name']
            if pd.notna(bowler_name) and 'bowling' in team_stats[bowling_team]:
                stats_df = team_stats[bowling_team]['bowling']
                match = find_player_match(bowler_name, stats_df)
                if match is not None:
                    merged_data.at[idx, f'bowler{i}_historical_average'] = match['average']
                    merged_data.at[idx, f'bowler{i}_historical_economy'] = match['economy']
                    merged_data.at[idx, f'bowler{i}_historical_strike_rate'] = match['strike_rate']
                    print(f"Found match for {bowler_name} -> {match['player_name']}")
                else:
                    print(f"No match found for {bowler_name}")
    
    return merged_data

def generate_team_summary(merged_data):
    """
    Generate a summary of team performance from the merged data.
    """
    # Define available metrics to aggregate
    metrics = {}
    
    # Check which columns are available and add them to metrics dict
    if 'total_runs' in merged_data.columns:
        metrics['total_runs'] = 'sum'
    if 'boundaries' in merged_data.columns:
        metrics['boundaries'] = 'sum'
    if 'dot_balls' in merged_data.columns:
        metrics['dot_balls'] = 'sum'
    if 'wickets' in merged_data.columns:
        metrics['wickets'] = 'sum'
    if 'extras' in merged_data.columns:
        metrics['extras'] = 'sum'
    
    if not metrics:
        print("Warning: No metrics columns found in the data")
        return pd.DataFrame()
    
    team_summary = merged_data.groupby('batting_team').agg(metrics).reset_index()
    
    # Calculate additional metrics only if required columns exist
    if 'boundaries' in team_summary.columns:
        team_summary['boundary_percentage'] = (team_summary['boundaries'] * 100 / 20).round(2)
    if 'dot_balls' in team_summary.columns:
        team_summary['dot_ball_percentage'] = (team_summary['dot_balls'] * 100 / 120).round(2)
    
    return team_summary

if __name__ == "__main__":
    # Example usage
    match_dir = "/path/to/match/directory"
    ball_by_ball_dir = "/path/to/ball_by_ball/directory"
    
    merged_data = merge_match_data(match_dir, ball_by_ball_dir)
    team_summary = generate_team_summary(merged_data)
    print("\nTeam Summary:")
    print(team_summary)
