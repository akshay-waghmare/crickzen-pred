import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional
import structlog
from ..features.calculator import StatsCalculator, ResourceFeatureCalculator
from ..features.format_config import FormatConfig

logger = structlog.get_logger()


ODM_BASE_COLUMNS = [
    'league', 'match_id', 'date', 'season', 'innings', 'over', 'ball',
    'is_super_over',
    'venue_id', 'batting_team_id', 'bowling_team_id', 'batting_team', 'winner',
    'batter_id', 'bowler_id', 'non_striker_id',
    'runs_batter', 'runs_extras', 'runs_total', 'wicket_type', 'player_out_id',
]

# Historical team name → canonical name mapping for franchise renames.
# Applied during feature processing so all seasons use the current name.
TEAM_CANONICAL_NAMES = {
    # IPL renames
    'Royal Challengers Bangalore': 'Royal Challengers Bengaluru',
    'Delhi Daredevils': 'Delhi Capitals',
    'Kings XI Punjab': 'Punjab Kings',
    'Rising Pune Supergiant': 'Rising Pune Supergiants',
    'Deccan Chargers': 'Sunrisers Hyderabad',
    # BBL renames
    'Brisbane Heat': 'Brisbane Heat',
    # Add more as needed
}


def _apply_team_canonical_names(df: pd.DataFrame) -> pd.DataFrame:
    """Replace historical team names with canonical names in team/winner columns."""
    if not TEAM_CANONICAL_NAMES:
        return df
    for col in ['batting_team', 'bowling_team', 'winner']:
        if col in df.columns:
            df[col] = df[col].replace(TEAM_CANONICAL_NAMES)
    return df


def process_bbl_data(input_dir: Path, output_dir: Path, feature_store_dir: Path,
                     format_config: Optional[FormatConfig] = None):
    """
    Processes raw BBL parquet files into training data and feature store artifacts.
    """
    if format_config is None:
        format_config = FormatConfig.t20()
    
    total_balls = format_config.total_balls
    total_overs = format_config.total_overs
    balls_per_over = format_config.balls_per_over
    par_score = format_config.par_score
    
    logger.info("Starting BBL data processing", input_dir=str(input_dir))
    
    # 1. Load Data
    # First try to read as a partitioned dataset (preserves season partition column)
    try:
        df = pd.read_parquet(input_dir)
        logger.info(f"Loaded {len(df)} rows as partitioned dataset")
    except Exception:
        # Fallback: read individual files, but extract season from path
        match_files = list(input_dir.rglob("*.parquet"))
        if not match_files:
            raise FileNotFoundError(f"No .parquet files found in {input_dir}")
        
        dfs = []
        for f in match_files:
            file_df = pd.read_parquet(f)
            # Extract season from path (e.g., "season=2023%2F24" -> "2023/24")
            for part in f.parts:
                if part.startswith('season='):
                    season_val = part.replace('season=', '').replace('%2F', '/')
                    file_df['season'] = season_val
                    break
            dfs.append(file_df)
        df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Loaded {len(df)} rows from {len(match_files)} files")
    
    # Ensure bowling_team column exists (it might be named bowling_team_id in raw data)
    if 'bowling_team' not in df.columns and 'bowling_team_id' in df.columns:
        df['bowling_team'] = df['bowling_team_id']
    
    # Canonicalize historical team names (e.g. Delhi Daredevils → Delhi Capitals)
    df = _apply_team_canonical_names(df)
    
    # Remove duplicate rows - raw data often has each ball duplicated
    dup_cols = ['match_id', 'innings', 'over', 'ball']
    original_len = len(df)
    df = df.drop_duplicates(subset=dup_cols, keep='first')
    if len(df) < original_len:
        logger.info(f"Removed {original_len - len(df)} duplicate rows, now {len(df)} rows")
    
    # 2. Calculate Match Results (Who won?)
    # We need to know the winner for the target variable
    # The raw data has 'winner' column usually, let's check.
    # Assuming 'winner' column exists and contains team name.
    
    # Create target: is_winner (1 if batting team won, 0 otherwise)
    # If the batting team is the winner, then is_winner = 1
    df['is_winner'] = (df['batting_team'] == df['winner']).astype(int)

    # Combined men/women models must retain match gender as a model input.
    # Encode male=0, female=1 so the same feature contract works for T20 and ODI.
    if 'gender' in df.columns:
        df['gender_female'] = df['gender'].astype(str).str.lower().eq('female').astype(int)
    else:
        df['gender_female'] = 0
    
    # Calculate cumulative runs and wickets for current_score and wickets_lost
    # Sort by match, innings, over, ball
    df = df.sort_values(['match_id', 'innings', 'over', 'ball'])
    
    # Group by match and innings to calculate cumulative sum
    # Use transform to keep the index aligned
    df['current_score'] = df.groupby(['match_id', 'innings'])['runs_total'].transform('cumsum')
    
    # For wickets, we need to convert player_out_id to boolean (1 if out, 0 if not) first
    df['is_wicket'] = df['player_out_id'].notna().astype(int)
    df['wickets_lost'] = df.groupby(['match_id', 'innings'])['is_wicket'].transform('cumsum')
    
    # 3. Feature Engineering
    # We need rolling stats for batsman and bowler
    
    # Prepare Batting Data
    # Group by match and batsman to get runs per innings
    print("Calculating batting stats...")
    # Note: 'date' is the column name in parquet, not 'start_date'
    # Note: 'batter_id' is the column name, not 'batsman'
    batting_agg = df.groupby(['match_id', 'date', 'batter_id']).agg({
        'runs_batter': 'sum',
        'ball': 'count', # balls faced
        'player_out_id': lambda x: x.notna().sum() # times out
    }).reset_index().rename(columns={
        'date': 'start_date', # Rename for calculator compatibility
        'batter_id': 'batsman',
        'runs_batter': 'runs',
        'ball': 'balls_faced',
        'player_out_id': 'is_out'
    })
    
    calc = StatsCalculator()
    batting_rolling = calc.calculate_rolling_batting_stats(batting_agg)
    
    # Merge back to batting_agg to keep keys
    batting_features = pd.concat([batting_agg, batting_rolling], axis=1)
    
    # --- BATSMAN VENUE-SPECIFIC STATS ---
    print("Calculating batsman venue-specific stats...")
    batting_venue_agg = df.groupby(['match_id', 'date', 'batter_id', 'venue_id']).agg({
        'runs_batter': 'sum',
        'ball': 'count'
    }).reset_index().rename(columns={
        'date': 'start_date',
        'batter_id': 'batsman',
        'venue_id': 'venue',
        'runs_batter': 'runs',
        'ball': 'balls_faced'
    })
    batting_venue_agg = batting_venue_agg.sort_values(['batsman', 'venue', 'start_date'])
    
    # Rolling avg/SR at this venue (last 5 innings at venue)
    batting_venue_agg['batsman_venue_runs_cum'] = batting_venue_agg.groupby(['batsman', 'venue'])['runs'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    )
    batting_venue_agg['batsman_venue_balls_cum'] = batting_venue_agg.groupby(['batsman', 'venue'])['balls_faced'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    )
    batting_venue_agg['batsman_venue_innings'] = batting_venue_agg.groupby(['batsman', 'venue']).cumcount()
    batting_venue_agg['batsman_venue_avg'] = batting_venue_agg['batsman_venue_runs_cum'] / batting_venue_agg['batsman_venue_innings'].replace(0, 1)
    batting_venue_agg['batsman_venue_sr'] = np.where(
        batting_venue_agg['batsman_venue_balls_cum'] > 0,
        (batting_venue_agg['batsman_venue_runs_cum'] / batting_venue_agg['batsman_venue_balls_cum']) * 100,
        0.0
    )
    
    # --- BATSMAN VS TEAM MATCHUP ---
    print("Calculating batsman vs team matchup stats...")
    # Get bowling team for each ball
    batting_vs_team = df.groupby(['match_id', 'date', 'batter_id', 'bowling_team_id']).agg({
        'runs_batter': 'sum',
        'ball': 'count'
    }).reset_index().rename(columns={
        'date': 'start_date',
        'batter_id': 'batsman',
        'bowling_team_id': 'opponent',
        'runs_batter': 'runs',
        'ball': 'balls_faced'
    })
    batting_vs_team = batting_vs_team.sort_values(['batsman', 'opponent', 'start_date'])
    
    # Rolling avg against this team (last 5 innings vs team)
    batting_vs_team['batsman_vs_team_runs_cum'] = batting_vs_team.groupby(['batsman', 'opponent'])['runs'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    )
    batting_vs_team['batsman_vs_team_innings'] = batting_vs_team.groupby(['batsman', 'opponent']).cumcount()
    batting_vs_team['batsman_vs_team_avg'] = batting_vs_team['batsman_vs_team_runs_cum'] / batting_vs_team['batsman_vs_team_innings'].replace(0, 1)
    
    # Prepare Bowling Data
    print("Calculating bowling stats...")
    # Note: 'bowler_id' is the column name, not 'bowler'
    bowling_agg = df.groupby(['match_id', 'date', 'bowler_id']).agg({
        'runs_total': 'sum', # runs conceded
        'ball': 'count', # balls bowled
        'wicket_type': lambda x: x.notna().sum() # wickets taken
    }).reset_index().rename(columns={
        'date': 'start_date',
        'bowler_id': 'bowler',
        'runs_total': 'runs_conceded',
        'ball': 'balls_bowled',
        'wicket_type': 'wickets'
    })
    
    bowling_rolling = calc.calculate_rolling_bowling_stats(bowling_agg)
    bowling_features = pd.concat([bowling_agg, bowling_rolling], axis=1)
    
    # --- BOWLER VENUE-SPECIFIC STATS ---
    print("Calculating bowler venue-specific stats...")
    bowling_venue_agg = df.groupby(['match_id', 'date', 'bowler_id', 'venue_id']).agg({
        'runs_total': 'sum',
        'ball': 'count',
        'wicket_type': lambda x: x.notna().sum()
    }).reset_index().rename(columns={
        'date': 'start_date',
        'bowler_id': 'bowler',
        'venue_id': 'venue',
        'runs_total': 'runs_conceded',
        'ball': 'balls_bowled',
        'wicket_type': 'wickets'
    })
    bowling_venue_agg = bowling_venue_agg.sort_values(['bowler', 'venue', 'start_date'])
    
    # Rolling economy at this venue (last 5 innings at venue)
    bowling_venue_agg['bowler_venue_runs_cum'] = bowling_venue_agg.groupby(['bowler', 'venue'])['runs_conceded'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    )
    bowling_venue_agg['bowler_venue_balls_cum'] = bowling_venue_agg.groupby(['bowler', 'venue'])['balls_bowled'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    )
    bowling_venue_agg['bowler_venue_wickets_cum'] = bowling_venue_agg.groupby(['bowler', 'venue'])['wickets'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    )
    bowling_venue_agg['bowler_venue_econ'] = np.where(
        bowling_venue_agg['bowler_venue_balls_cum'] > 0,
        (bowling_venue_agg['bowler_venue_runs_cum'] / bowling_venue_agg['bowler_venue_balls_cum']) * balls_per_over,
        0.0
    )
    bowling_venue_agg['bowler_venue_sr'] = np.where(
        bowling_venue_agg['bowler_venue_wickets_cum'] > 0,
        bowling_venue_agg['bowler_venue_balls_cum'] / bowling_venue_agg['bowler_venue_wickets_cum'],
        999.0  # High value if no wickets
    )
    
    # --- BOWLER VS TEAM MATCHUP ---
    print("Calculating bowler vs team matchup stats...")
    bowling_vs_team = df.groupby(['match_id', 'date', 'bowler_id', 'batting_team_id']).agg({
        'runs_total': 'sum',
        'ball': 'count',
        'wicket_type': lambda x: x.notna().sum()
    }).reset_index().rename(columns={
        'date': 'start_date',
        'bowler_id': 'bowler',
        'batting_team_id': 'opponent',
        'runs_total': 'runs_conceded',
        'ball': 'balls_bowled',
        'wicket_type': 'wickets'
    })
    bowling_vs_team = bowling_vs_team.sort_values(['bowler', 'opponent', 'start_date'])
    
    # Rolling economy against this team (last 5 innings vs team)
    bowling_vs_team['bowler_vs_team_runs_cum'] = bowling_vs_team.groupby(['bowler', 'opponent'])['runs_conceded'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    )
    bowling_vs_team['bowler_vs_team_balls_cum'] = bowling_vs_team.groupby(['bowler', 'opponent'])['balls_bowled'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    )
    bowling_vs_team['bowler_vs_team_wickets_cum'] = bowling_vs_team.groupby(['bowler', 'opponent'])['wickets'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    )
    bowling_vs_team['bowler_vs_team_econ'] = np.where(
        bowling_vs_team['bowler_vs_team_balls_cum'] > 0,
        (bowling_vs_team['bowler_vs_team_runs_cum'] / bowling_vs_team['bowler_vs_team_balls_cum']) * balls_per_over,
        0.0
    )
    
    # Venue Stats
    print("Calculating venue stats...")
    # First innings score
    # Note: 'venue_id' is the column name, not 'venue'
    first_innings = df[df['innings'] == 1].groupby(['match_id', 'venue_id', 'date'])['runs_total'].sum().reset_index()
    first_innings.columns = ['match_id', 'venue', 'start_date', 'first_innings_score']
    
    # Total wickets in match
    match_wickets = df.groupby(['match_id'])['wicket_type'].count().reset_index()
    match_wickets.columns = ['match_id', 'wickets_total']
    
    # Bat first win?
    # Fix: Handle potential duplicates or NaNs in winner/batting_team
    match_meta = df[['match_id', 'batting_team_id', 'winner', 'innings']].drop_duplicates()
    
    # Find team batting first
    # We want the batting team for innings 1.
    bat_first_team = match_meta[match_meta['innings'] == 1][['match_id', 'batting_team_id']].dropna()
    # Ensure one row per match
    bat_first_team = bat_first_team.drop_duplicates(subset=['match_id'])
    bat_first_team.columns = ['match_id', 'team_bat_first']
    
    # Get winner for each match
    # Drop NaNs and ensure unique
    winners = df[['match_id', 'winner']].dropna().drop_duplicates()
    winners = winners.drop_duplicates(subset=['match_id'])
    
    venue_base = first_innings.merge(match_wickets, on='match_id')
    venue_base = venue_base.merge(bat_first_team, on='match_id')
    venue_base = venue_base.merge(winners, on='match_id')
    venue_base['bat_first_win'] = (venue_base['team_bat_first'] == venue_base['winner']).astype(int)
    
    venue_rolling = calc.calculate_venue_stats(venue_base)
    venue_features = pd.concat([venue_base, venue_rolling], axis=1)

    # --- VENUE-OVER PAR FEATURE ---
    print("Calculating venue-over par...")
    # Expected cumulative score at end of each over, per venue (inn1 only)
    inn1_over_end = (
        df[df['innings'] == 1]
        .groupby(['match_id', 'venue_id', 'date', 'over'])['current_score']
        .last()
        .reset_index()
    )
    inn1_over_end.columns = ['match_id', 'venue', 'start_date', 'over', 'over_end_score']

    # Sort by (venue, over, date, match_id) for stable chronological expanding mean
    inn1_over_end = inn1_over_end.sort_values(
        ['venue', 'over', 'start_date', 'match_id']
    ).reset_index(drop=True)

    # Leave-one-out expanding mean: each match sees only prior matches at this venue+over
    inn1_over_end['venue_over_par'] = inn1_over_end.groupby(['venue', 'over'])['over_end_score'].transform(
        lambda x: x.shift(1).expanding().mean()
    )

    # Expanding global league mean per over (no future leakage) as fallback
    global_sorted = inn1_over_end[['start_date', 'match_id', 'over', 'over_end_score']].sort_values(
        ['over', 'start_date', 'match_id']
    )
    global_sorted['league_over_par'] = global_sorted.groupby('over')['over_end_score'].transform(
        lambda x: x.shift(1).expanding().mean()
    )
    inn1_over_end = inn1_over_end.merge(
        global_sorted[['match_id', 'over', 'league_over_par']].drop_duplicates(subset=['match_id', 'over']),
        on=['match_id', 'over'], how='left'
    )
    inn1_over_end['venue_over_par'] = (
        inn1_over_end['venue_over_par']
        .fillna(inn1_over_end['league_over_par'])
        .fillna(0.0)
    )

    # Merge into main df (only inn1 rows get a value; inn2 rows → NaN → set to 0.0)
    df = df.merge(
        inn1_over_end[['match_id', 'over', 'venue_over_par']].drop_duplicates(subset=['match_id', 'over']),
        on=['match_id', 'over'], how='left'
    )
    df['score_vs_venue_over_par'] = np.where(
        df['innings'] == 1,
        df['current_score'] - df['venue_over_par'].fillna(0.0),
        0.0
    )
    df['score_vs_venue_over_par'] = df['score_vs_venue_over_par'].fillna(0.0)
    df = df.drop(columns=['venue_over_par'], errors='ignore')

    # --- TEAM STRENGTH FEATURES ---
    print("Calculating team strength features...")
    
    # Get unique matches with team info and results
    match_results = df[['match_id', 'date', 'batting_team_id', 'bowling_team_id', 'winner', 'innings']].drop_duplicates()
    
    # Extract batting team for innings 1 (team that batted first)
    innings1 = match_results[match_results['innings'] == 1][['match_id', 'date', 'batting_team_id', 'bowling_team_id']].drop_duplicates(subset=['match_id'])
    innings1.columns = ['match_id', 'date', 'team1', 'team2']
    
    # Get winners
    match_winners = df[['match_id', 'winner']].dropna().drop_duplicates(subset=['match_id'])
    innings1 = innings1.merge(match_winners, on='match_id', how='left')
    
    # Calculate rolling win rate for each team
    def calculate_team_win_rates(matches_df):
        """Calculate rolling win rate for teams."""
        team_stats = []
        
        # Flatten to get all team appearances
        team1_matches = matches_df[['match_id', 'date', 'team1', 'winner']].copy()
        team1_matches.columns = ['match_id', 'date', 'team', 'winner']
        
        team2_matches = matches_df[['match_id', 'date', 'team2', 'winner']].copy()
        team2_matches.columns = ['match_id', 'date', 'team', 'winner']
        
        all_team_matches = pd.concat([team1_matches, team2_matches], ignore_index=True)
        all_team_matches['won'] = (all_team_matches['team'] == all_team_matches['winner']).astype(int)
        all_team_matches = all_team_matches.sort_values(['team', 'date'])
        
        # Rolling win rate (last 10 matches)
        all_team_matches['team_rolling_wins'] = all_team_matches.groupby('team')['won'].transform(
            lambda x: x.shift(1).rolling(window=10, min_periods=1).sum()
        )
        all_team_matches['team_rolling_matches'] = all_team_matches.groupby('team')['won'].transform(
            lambda x: x.shift(1).rolling(window=10, min_periods=1).count()
        )
        all_team_matches['team_win_rate'] = all_team_matches['team_rolling_wins'] / all_team_matches['team_rolling_matches'].replace(0, 1)
        
        return all_team_matches[['match_id', 'team', 'team_win_rate']].drop_duplicates()
    
    team_win_rates = calculate_team_win_rates(innings1)
    
    # --- TEAM BAT FIRST / BOWL FIRST WIN RATES ---
    print("Calculating team batting first / bowling first win rates...")
    
    def calculate_team_bat_bowl_first_rates(matches_df):
        """Calculate rolling win rate when batting first vs bowling first for each team."""
        # Team batting first (team1)
        bat_first = matches_df[['match_id', 'date', 'team1', 'winner']].copy()
        bat_first.columns = ['match_id', 'date', 'team', 'winner']
        bat_first['won'] = (bat_first['team'] == bat_first['winner']).astype(int)
        bat_first = bat_first.sort_values(['team', 'date'])
        
        # Rolling win rate when batting first (last 10 matches)
        bat_first['team_bat_first_wins'] = bat_first.groupby('team')['won'].transform(
            lambda x: x.shift(1).rolling(window=10, min_periods=1).sum()
        )
        bat_first['team_bat_first_matches'] = bat_first.groupby('team')['won'].transform(
            lambda x: x.shift(1).rolling(window=10, min_periods=1).count()
        )
        bat_first['team_bat_first_win_rate'] = bat_first['team_bat_first_wins'] / bat_first['team_bat_first_matches'].replace(0, 1)
        
        # Team bowling first (team2)
        bowl_first = matches_df[['match_id', 'date', 'team2', 'winner']].copy()
        bowl_first.columns = ['match_id', 'date', 'team', 'winner']
        bowl_first['won'] = (bowl_first['team'] == bowl_first['winner']).astype(int)
        bowl_first = bowl_first.sort_values(['team', 'date'])
        
        # Rolling win rate when bowling first (last 10 matches)
        bowl_first['team_bowl_first_wins'] = bowl_first.groupby('team')['won'].transform(
            lambda x: x.shift(1).rolling(window=10, min_periods=1).sum()
        )
        bowl_first['team_bowl_first_matches'] = bowl_first.groupby('team')['won'].transform(
            lambda x: x.shift(1).rolling(window=10, min_periods=1).count()
        )
        bowl_first['team_bowl_first_win_rate'] = bowl_first['team_bowl_first_wins'] / bowl_first['team_bowl_first_matches'].replace(0, 1)
        
        # Combine
        bat_first_rates = bat_first[['match_id', 'team', 'team_bat_first_win_rate']].drop_duplicates()
        bowl_first_rates = bowl_first[['match_id', 'team', 'team_bowl_first_win_rate']].drop_duplicates()
        
        return bat_first_rates, bowl_first_rates
    
    team_bat_first_rates, team_bowl_first_rates = calculate_team_bat_bowl_first_rates(innings1)
    
    # --- HEAD-TO-HEAD TEAM STATS ---
    print("Calculating head-to-head team stats...")
    
    def calculate_h2h_stats(matches_df):
        """Calculate rolling head-to-head win rate between teams."""
        h2h_df = matches_df[['match_id', 'date', 'team1', 'team2', 'winner']].copy()
        
        # Create matchup key (sorted team pair)
        h2h_df['team_pair'] = h2h_df.apply(
            lambda x: tuple(sorted([x['team1'], x['team2']])), axis=1
        )
        h2h_df['team1_won'] = (h2h_df['team1'] == h2h_df['winner']).astype(int)
        h2h_df = h2h_df.sort_values(['team_pair', 'date'])
        
        # Rolling H2H wins for team1 (last 5 meetings)
        h2h_df['h2h_team1_wins'] = h2h_df.groupby('team_pair')['team1_won'].transform(
            lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
        )
        h2h_df['h2h_matches'] = h2h_df.groupby('team_pair')['team1_won'].transform(
            lambda x: x.shift(1).rolling(window=5, min_periods=1).count()
        )
        h2h_df['h2h_team1_win_rate'] = h2h_df['h2h_team1_wins'] / h2h_df['h2h_matches'].replace(0, 1)
        
        return h2h_df[['match_id', 'team1', 'team2', 'h2h_team1_win_rate']]
    
    h2h_stats = calculate_h2h_stats(innings1)
    
    # --- TEAM RECENT FORM (SHORT WINDOW FOR MOMENTUM) ---
    print("Calculating team recent form (momentum)...")
    
    def calculate_team_form(matches_df):
        """Calculate recent form - wins in last 3 matches (momentum indicator)."""
        # Flatten to get all team appearances
        team1_matches = matches_df[['match_id', 'date', 'team1', 'winner']].copy()
        team1_matches.columns = ['match_id', 'date', 'team', 'winner']
        
        team2_matches = matches_df[['match_id', 'date', 'team2', 'winner']].copy()
        team2_matches.columns = ['match_id', 'date', 'team', 'winner']
        
        all_team_matches = pd.concat([team1_matches, team2_matches], ignore_index=True)
        all_team_matches['won'] = (all_team_matches['team'] == all_team_matches['winner']).astype(int)
        all_team_matches = all_team_matches.sort_values(['team', 'date'])
        
        # Recent form - last 3 matches (momentum)
        all_team_matches['recent_wins_3'] = all_team_matches.groupby('team')['won'].transform(
            lambda x: x.shift(1).rolling(window=3, min_periods=1).sum()
        )
        all_team_matches['recent_form'] = all_team_matches['recent_wins_3'] / 3  # Normalize to 0-1
        
        # Win streak (consecutive wins before this match)
        def calc_streak(group):
            streaks = []
            current_streak = 0
            for i, won in enumerate(group):
                if i == 0:
                    streaks.append(0)  # No history for first match
                else:
                    streaks.append(current_streak)
                if won == 1:
                    current_streak += 1
                else:
                    current_streak = 0
            return pd.Series(streaks, index=group.index)
        
        all_team_matches['win_streak'] = all_team_matches.groupby('team')['won'].transform(calc_streak)
        
        return all_team_matches[['match_id', 'team', 'recent_form', 'win_streak']].drop_duplicates()
    
    team_form = calculate_team_form(innings1)
    
    # --- TEAM BATTING/BOWLING FORM (RECENT RUN RATES) ---
    print("Calculating team batting/bowling form...")
    
    # Team batting performance (runs scored per match)
    team_batting = df.groupby(['match_id', 'date', 'batting_team_id', 'innings']).agg({
        'runs_total': 'sum',
        'ball': 'count'
    }).reset_index()
    team_batting.columns = ['match_id', 'date', 'team', 'innings', 'runs', 'balls']
    team_batting['run_rate'] = (team_batting['runs'] / team_batting['balls']) * balls_per_over
    team_batting = team_batting.sort_values(['team', 'date'])
    
    # Rolling team batting run rate (last 5 innings)
    team_batting['team_batting_form'] = team_batting.groupby('team')['run_rate'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).mean()
    )
    
    # Team bowling performance (runs conceded per match)
    team_bowling = df.groupby(['match_id', 'date', 'bowling_team_id', 'innings']).agg({
        'runs_total': 'sum',
        'ball': 'count',
        'wicket_type': lambda x: x.notna().sum()
    }).reset_index()
    team_bowling.columns = ['match_id', 'date', 'team', 'innings', 'runs_conceded', 'balls', 'wickets']
    team_bowling['economy'] = (team_bowling['runs_conceded'] / team_bowling['balls']) * balls_per_over
    team_bowling = team_bowling.sort_values(['team', 'date'])
    
    # Rolling team bowling economy (last 5 innings)
    team_bowling['team_bowling_form'] = team_bowling.groupby('team')['economy'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).mean()
    )
    
    # --- VENUE CHASE SUCCESS RATE ---
    print("Calculating venue chase success rate...")
    
    # Calculate chase success rate at each venue
    venue_chase = venue_base[['match_id', 'venue', 'start_date', 'bat_first_win']].copy()
    venue_chase['chase_win'] = 1 - venue_chase['bat_first_win']  # Chasing team won
    venue_chase = venue_chase.sort_values(['venue', 'start_date'])
    
    # Rolling chase success rate at venue
    venue_chase['venue_chase_success'] = venue_chase.groupby('venue')['chase_win'].transform(
        lambda x: x.shift(1).expanding().mean()
    )
    
    # --- HOME VENUE ADVANTAGE ---
    print("Calculating home venue advantage...")
    
    # Map teams to their home venues
    # BBL teams have specific home grounds
    home_venue_map = {
        'Brisbane Heat': ['Brisbane Cricket Ground, Woolloongabba'],
        'Sydney Sixers': ['Sydney Cricket Ground'],
        'Sydney Thunder': ['Sydney Showground Stadium', 'Stadium Australia'],
        'Melbourne Stars': ['Melbourne Cricket Ground'],
        'Melbourne Renegades': ['Docklands Stadium'],
        'Adelaide Strikers': ['Adelaide Oval'],
        'Hobart Hurricanes': ['Bellerive Oval'],
        'Perth Scorchers': ['Western Australia Cricket Association Ground', 'Perth Stadium', 'Optus Stadium']
    }
    
    # Create home venue lookup
    venue_to_team = {}
    for team, venues in home_venue_map.items():
        for venue in venues:
            venue_to_team[venue] = team
    
    # --- SEASON/TEMPORAL FEATURES ---
    print("Calculating season/temporal features...")
    
    # Ensure season is a string (may be categorical from parquet)
    df['season'] = df['season'].astype(str)
    
    # Extract season number (1-14) and year
    season_order = {s: i+1 for i, s in enumerate(sorted(df['season'].unique()))}
    df['season_num'] = df['season'].map(season_order)
    
    # Extract year from season (e.g., "2023/24" -> 2023)
    df['season_year'] = df['season'].apply(lambda x: int(str(x).split('/')[0]))
    
    # Normalize season year to 0-1 scale for model
    min_year = int(df['season_year'].min())
    max_year = int(df['season_year'].max())
    df['season_year_norm'] = (df['season_year'] - min_year) / (max_year - min_year) if max_year > min_year else 0.5

    # 4. Merge Features back to Ball-by-Ball
    print("Merging features...")
    
    # Merge Batting
    df = df.merge(batting_features[['match_id', 'batsman', 'batsman_rolling_avg', 'batsman_rolling_sr']], 
                  left_on=['match_id', 'batter_id'], right_on=['match_id', 'batsman'], how='left')
    
    # Merge Bowling
    df = df.merge(bowling_features[['match_id', 'bowler', 'bowler_rolling_econ', 'bowler_rolling_sr']], 
                  left_on=['match_id', 'bowler_id'], right_on=['match_id', 'bowler'], how='left')
    
    # Merge Venue
    df = df.merge(venue_features[['match_id', 'venue_avg_score', 'venue_avg_wickets', 'venue_bat_first_win_rate']], 
                  on=['match_id'], how='left')
    
    # Merge Batsman Venue Stats
    df = df.merge(
        batting_venue_agg[['match_id', 'batsman', 'venue', 'batsman_venue_avg', 'batsman_venue_sr']],
        left_on=['match_id', 'batter_id', 'venue_id'],
        right_on=['match_id', 'batsman', 'venue'],
        how='left'
    )
    
    # Merge Batsman vs Team Stats
    df = df.merge(
        batting_vs_team[['match_id', 'batsman', 'opponent', 'batsman_vs_team_avg']],
        left_on=['match_id', 'batter_id', 'bowling_team_id'],
        right_on=['match_id', 'batsman', 'opponent'],
        how='left'
    )
    
    # Merge Bowler Venue Stats
    df = df.merge(
        bowling_venue_agg[['match_id', 'bowler', 'venue', 'bowler_venue_econ', 'bowler_venue_sr']],
        left_on=['match_id', 'bowler_id', 'venue_id'],
        right_on=['match_id', 'bowler', 'venue'],
        how='left',
        suffixes=('', '_bowler_venue')
    )
    
    # Merge Bowler vs Team Stats
    df = df.merge(
        bowling_vs_team[['match_id', 'bowler', 'opponent', 'bowler_vs_team_econ']],
        left_on=['match_id', 'bowler_id', 'batting_team_id'],
        right_on=['match_id', 'bowler', 'opponent'],
        how='left',
        suffixes=('', '_bowler_vs_team')
    )
    
    # Merge Team Win Rates (batting team)
    df = df.merge(team_win_rates.rename(columns={'team': 'batting_team_id', 'team_win_rate': 'batting_team_win_rate'}),
                  on=['match_id', 'batting_team_id'], how='left')
    
    # Merge Team Win Rates (bowling team)
    df = df.merge(team_win_rates.rename(columns={'team': 'bowling_team_id', 'team_win_rate': 'bowling_team_win_rate'}),
                  on=['match_id', 'bowling_team_id'], how='left')
    
    # Merge Team Bat First Win Rates (for batting team in innings 1)
    df = df.merge(team_bat_first_rates.rename(columns={'team': 'batting_team_id', 'team_bat_first_win_rate': 'batting_team_bat_first_wr'}),
                  on=['match_id', 'batting_team_id'], how='left')
    
    # Merge Team Bowl First Win Rates (for bowling team - they bowl first when batting team bats first)
    df = df.merge(team_bowl_first_rates.rename(columns={'team': 'bowling_team_id', 'team_bowl_first_win_rate': 'bowling_team_bowl_first_wr'}),
                  on=['match_id', 'bowling_team_id'], how='left')
    
    # Also get the reverse: batting team's bowl first rate (for when they're chasing)
    df = df.merge(team_bowl_first_rates.rename(columns={'team': 'batting_team_id', 'team_bowl_first_win_rate': 'batting_team_bowl_first_wr'}),
                  on=['match_id', 'batting_team_id'], how='left')
    
    # And bowling team's bat first rate
    df = df.merge(team_bat_first_rates.rename(columns={'team': 'bowling_team_id', 'team_bat_first_win_rate': 'bowling_team_bat_first_wr'}),
                  on=['match_id', 'bowling_team_id'], how='left')
    
    # Merge Head-to-Head Stats
    # For innings 1, batting team = team1; for innings 2, batting team = team2
    # We need to map h2h_team1_win_rate appropriately
    df = df.merge(h2h_stats, on='match_id', how='left')
    
    # Calculate H2H win rate from batting team's perspective
    # If batting_team == team1, use h2h_team1_win_rate directly
    # If batting_team == team2, use 1 - h2h_team1_win_rate
    df['h2h_batting_win_rate'] = np.where(
        df['batting_team_id'] == df['team1'],
        df['h2h_team1_win_rate'],
        1 - df['h2h_team1_win_rate']
    )
    
    # Team strength differential
    df['team_strength_diff'] = df['batting_team_win_rate'].fillna(0.5) - df['bowling_team_win_rate'].fillna(0.5)
    
    # --- MERGE NEW TEAM FORM FEATURES ---
    print("Merging team form features...")
    
    # Merge team recent form for batting team
    df = df.merge(
        team_form.rename(columns={'team': 'batting_team_id', 'recent_form': 'batting_recent_form', 'win_streak': 'batting_win_streak'}),
        on=['match_id', 'batting_team_id'], how='left'
    )
    
    # Merge team recent form for bowling team
    df = df.merge(
        team_form.rename(columns={'team': 'bowling_team_id', 'recent_form': 'bowling_recent_form', 'win_streak': 'bowling_win_streak'}),
        on=['match_id', 'bowling_team_id'], how='left'
    )
    
    # Merge team batting form (run rate)
    df = df.merge(
        team_batting[['match_id', 'team', 'innings', 'team_batting_form']],
        left_on=['match_id', 'batting_team_id', 'innings'],
        right_on=['match_id', 'team', 'innings'],
        how='left'
    )
    
    # Merge team bowling form (economy)
    df = df.merge(
        team_bowling[['match_id', 'team', 'innings', 'team_bowling_form']].rename(columns={'team': 'team_bowl'}),
        left_on=['match_id', 'bowling_team_id', 'innings'],
        right_on=['match_id', 'team_bowl', 'innings'],
        how='left'
    )
    
    # Merge venue chase success rate
    df = df.merge(
        venue_chase[['match_id', 'venue_chase_success']],
        on='match_id', how='left'
    )
    
    # Create home team indicator
    df['batting_is_home'] = df.apply(
        lambda row: 1.0 if venue_to_team.get(row.get('venue', ''), '') == row.get('batting_team', '') else 0.0, 
        axis=1
    )
    df['bowling_is_home'] = df.apply(
        lambda row: 1.0 if venue_to_team.get(row.get('venue', ''), '') == row.get('bowling_team', '') else 0.0, 
        axis=1
    )
    
    # Home advantage feature
    df['home_advantage'] = df['batting_is_home'] - df['bowling_is_home']
    
    # Form difference (batting team form - bowling team form)
    df['form_diff'] = df['batting_recent_form'].fillna(0.5) - df['bowling_recent_form'].fillna(0.5)
    
    # Combined form score (batting team's batting form vs bowling team's bowling form)
    df['batting_vs_bowling_form'] = df['team_batting_form'].fillna(8.0) - df['team_bowling_form'].fillna(8.0)

    # --- BATTING TEAM VENUE WIN RATE (LOO, match-level → map to ball-level) ---
    print("Calculating batting team venue win rates...")
    venue_per_match = df[df['innings'] == 1][['match_id', 'venue_id']].drop_duplicates(subset=['match_id'])
    inn1_venue = innings1.merge(venue_per_match, on='match_id', how='left')

    rows_t1_v = inn1_venue[['match_id', 'date', 'team1', 'venue_id', 'winner']].copy()
    rows_t1_v.columns = ['match_id', 'date', 'team', 'venue', 'winner']
    rows_t1_v['won'] = (rows_t1_v['team'] == rows_t1_v['winner']).astype(int)
    rows_t2_v = inn1_venue[['match_id', 'date', 'team2', 'venue_id', 'winner']].copy()
    rows_t2_v.columns = ['match_id', 'date', 'team', 'venue', 'winner']
    rows_t2_v['won'] = (rows_t2_v['team'] == rows_t2_v['winner']).astype(int)

    team_venue_matches = pd.concat([rows_t1_v, rows_t2_v], ignore_index=True)
    # Stable sort: team, venue, date, match_id prevents same-day leakage
    team_venue_matches = team_venue_matches.sort_values(
        ['team', 'venue', 'date', 'match_id']
    ).reset_index(drop=True)

    # LOO: expanding win rate using only matches BEFORE this one (min 3 for reliability)
    team_venue_matches['batting_team_venue_wr'] = (
        team_venue_matches.groupby(['team', 'venue'])['won']
        .transform(lambda x: x.shift(1).expanding(min_periods=3).mean())
        .fillna(0.5)
    )

    # Map to ball-by-ball df via batting_team_id × venue_id × match_id
    tv_lookup = team_venue_matches.rename(
        columns={'team': 'batting_team_id', 'venue': 'venue_id'}
    )[['match_id', 'batting_team_id', 'venue_id', 'batting_team_venue_wr']]
    df = df.merge(tv_lookup, on=['match_id', 'batting_team_id', 'venue_id'], how='left')
    df['batting_team_venue_wr'] = df['batting_team_venue_wr'].fillna(0.5)

    # Full (non-LOO) version saved separately for inference feature store
    team_venue_full = (
        team_venue_matches.groupby(['team', 'venue'])
        .agg(win_rate=('won', 'mean'), n=('won', 'count'))
        .reset_index()
        .query('n >= 3')
    )

    # --- BATTING TEAM RECENT NRR (last 5 matches, LOO, match-level → ball-level) ---
    print("Calculating batting team recent NRR (last 5)...")
    inn1_sc = df[df['innings'] == 1].groupby('match_id')['runs_total'].sum().rename('inn1_score')
    inn1_bl = df[df['innings'] == 1].groupby('match_id')['ball'].count().rename('inn1_balls')
    inn2_sc = df[df['innings'] == 2].groupby('match_id')['runs_total'].sum().rename('inn2_score')
    inn2_bl = df[df['innings'] == 2].groupby('match_id')['ball'].count().rename('inn2_balls')

    match_scores = pd.concat([inn1_sc, inn1_bl, inn2_sc, inn2_bl], axis=1).reset_index()
    match_scores = match_scores.merge(
        innings1[['match_id', 'date', 'team1', 'team2']], on='match_id', how='left'
    )
    match_scores['rr1'] = match_scores['inn1_score'] / (match_scores['inn1_balls'] / balls_per_over).clip(lower=1)
    match_scores['rr2'] = match_scores['inn2_score'] / (match_scores['inn2_balls'] / balls_per_over).clip(lower=1)
    match_scores['nrr_t1'] = match_scores['rr1'] - match_scores['rr2']

    nrr_t1 = match_scores[['match_id', 'date', 'team1', 'nrr_t1']].rename(
        columns={'team1': 'team', 'nrr_t1': 'nrr'}
    )
    nrr_t2 = match_scores[['match_id', 'date', 'team2', 'nrr_t1']].copy()
    nrr_t2['nrr_t1'] = -nrr_t2['nrr_t1']
    nrr_t2 = nrr_t2.rename(columns={'team2': 'team', 'nrr_t1': 'nrr'})

    nrr_team = pd.concat([nrr_t1, nrr_t2], ignore_index=True)
    nrr_team = nrr_team.sort_values(['team', 'date', 'match_id']).reset_index(drop=True)

    # LOO: rolling NRR of last 5 matches BEFORE current match
    nrr_team['batting_recent_nrr_l5'] = (
        nrr_team.groupby('team')['nrr']
        .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        .fillna(0.0)
    )
    # Full-data version (including current match) for feature store latest values
    nrr_team['nrr_l5_full'] = (
        nrr_team.groupby('team')['nrr']
        .transform(lambda x: x.rolling(5, min_periods=1).mean())
    )
    latest_nrr_map = (
        nrr_team.sort_values(['team', 'date', 'match_id'])
        .groupby('team').last()['nrr_l5_full']
        .fillna(0.0)
        .to_dict()
    )

    # Map LOO NRR to ball-by-ball df via batting_team_id × match_id
    nrr_lookup = nrr_team.rename(columns={'team': 'batting_team_id'})[
        ['match_id', 'batting_team_id', 'batting_recent_nrr_l5']
    ]
    df = df.merge(nrr_lookup, on=['match_id', 'batting_team_id'], how='left')
    df['batting_recent_nrr_l5'] = df['batting_recent_nrr_l5'].fillna(0.0)

    # --- BATTING/BOWLING FIRST ADVANTAGE FEATURES ---
    print("Calculating batting/bowling first advantage features...")
    
    # For innings 1: batting team is batting first, use their bat_first rate
    # For innings 2: batting team is chasing (bowled first initially), use their bowl_first rate
    # This gives the relevant historical win rate for the current situation
    df['batting_team_situation_wr'] = np.where(
        df['innings'] == 1,
        df['batting_team_bat_first_wr'].fillna(0.5),
        df['batting_team_bowl_first_wr'].fillna(0.5)
    )
    
    # Similarly for bowling team
    df['bowling_team_situation_wr'] = np.where(
        df['innings'] == 1,
        df['bowling_team_bowl_first_wr'].fillna(0.5),
        df['bowling_team_bat_first_wr'].fillna(0.5)
    )
    
    # Situation advantage: how much better is batting team in this situation vs bowling team
    df['situation_advantage'] = df['batting_team_situation_wr'] - df['bowling_team_situation_wr']
    
    # --- TOSS FEATURES ---
    print("Calculating toss features...")
    
    # Check if toss columns exist
    if 'toss_winner' in df.columns and 'toss_decision' in df.columns:
        # Batting team won toss?
        df['batting_won_toss'] = (df['batting_team'] == df['toss_winner']).astype(int)
        
        # Toss decision: 1 = bat, 0 = field
        df['toss_chose_bat'] = (df['toss_decision'] == 'bat').astype(int)
        
        # Combined: batting team chose to bat (strategic alignment)
        df['batting_chose_bat'] = (df['batting_won_toss'] & df['toss_chose_bat']).astype(int)
    else:
        df['batting_won_toss'] = 0.5
        df['toss_chose_bat'] = 0.5
        df['batting_chose_bat'] = 0.5
    
    # --- NEW: Advanced Game State Features ---
    print("Calculating advanced game state features...")
    
    # 1. Target Score (for 2nd innings)
    # We already calculated 'first_innings' dataframe earlier.
    # Let's merge it to get the target for every row in the match
    target_map = first_innings[['match_id', 'first_innings_score']]
    df = df.merge(target_map, on='match_id', how='left')
    
    # 2. Balls Remaining
    # Hundred rows carry a legal-ball clock from HundredNormalizer. Legacy
    # formats retain their historical over/ball calculation.
    if format_config.format_name == 'hundred' and 'legal_balls_bowled' in df.columns:
        df['balls_bowled'] = pd.to_numeric(df['legal_balls_bowled'], errors='coerce').fillna(0)
    else:
        df['balls_bowled'] = df['over'] * balls_per_over + df['ball']
    df['balls_remaining'] = total_balls - df['balls_bowled']
    
    # 3. Required Run Rate (RRR)
    # Only valid for innings 2.
    # Target is first_innings_score + 1
    df['target_score'] = df['first_innings_score'] + 1
    df['runs_needed'] = df['target_score'] - df['current_score']
    
    # Avoid division by zero for last ball
    df['required_run_rate'] = np.where(
        (df['innings'] == 2) & (df['balls_remaining'] > 0),
        (df['runs_needed'] / df['balls_remaining']) * balls_per_over,
        0.0 # Default for innings 1 or end of match
    )
    
    # 4. Current Run Rate (CRR)
    df['current_run_rate'] = np.where(
        df['balls_bowled'] > 0,
        (df['current_score'] / df['balls_bowled']) * balls_per_over,
        0.0
    )
    
    # 5. Run Rate Difference (CRR - RRR)
    # Positive means ahead of rate, negative means behind.
    # Only for innings 2.
    df['run_rate_diff'] = np.where(
        df['innings'] == 2,
        df['current_run_rate'] - df['required_run_rate'],
        0.0
    )
    
    # --- ADVANCED FEATURES FOR BETTER PREDICTION ---
    print("Calculating advanced predictive features...")
    
    # 6. Match Phase (Powerplay=1, Middle=2, Death=3)
    # Powerplay: overs 0-5 (0-35 balls)
    # Middle: overs 6-14 (36-89 balls)
    # Death: overs 15-19 (90-119 balls)
    # Phase boundaries derived from config
    pp_balls = format_config.phase_thresholds[format_config.phase_names[0]] * balls_per_over
    mid_end_balls = (format_config.phase_thresholds[format_config.phase_names[1]] + 1) * balls_per_over
    if format_config.format_name == 'hundred':
        phase_bounds = [-1] + [
            format_config.phase_thresholds[name] * balls_per_over
            for name in format_config.phase_names
        ]
        df['match_phase'] = pd.cut(
            df['balls_bowled'],
            bins=phase_bounds,
            labels=list(range(1, len(format_config.phase_names) + 1)),
        ).astype(float)
        df['match_phase_name'] = pd.cut(
            df['balls_bowled'],
            bins=phase_bounds,
            labels=format_config.phase_names,
        ).astype(object)
    else:
        df['match_phase'] = pd.cut(
            df['balls_bowled'],
            bins=[-1, pp_balls, mid_end_balls, total_balls],
            labels=[1, 2, 3]
        ).astype(float)
    
    # 7. Pressure Index (combination of RRR and wickets)
    # Higher RRR + more wickets = more pressure
    df['pressure_index'] = np.where(
        df['innings'] == 2,
        df['required_run_rate'] * (1 + df['wickets_lost'] * 0.15),
        df['wickets_lost'] * 0.5  # For innings 1, just use wickets
    )
    
    # 8. Win Probability Proxy (DLS-like resources remaining)
    # Resources = f(balls_remaining, wickets_in_hand)
    # Simplified: resource_pct = balls_remaining/total_balls * (10 - wickets_lost)/10
    df['resources_remaining'] = (df['balls_remaining'] / total_balls) * ((10 - df['wickets_lost']) / 10)
    
    # --- DLS-STYLE RESOURCE FEATURES (HYBRID MODEL) ---
    print("Calculating DLS-style resource features...")
    resource_calc = ResourceFeatureCalculator(config=format_config)
    
    # Calculate proper DLS resource percentage
    df['overs_remaining'] = (total_balls - df['balls_bowled']) / balls_per_over
    
    # Vectorized DLS resource calculation
    def get_dls_resource_pct(row):
        return resource_calc.calculate_resource_percentage(
            row['overs_remaining'], 
            int(row['wickets_lost'])
        )
    
    df['resource_pct'] = df.apply(get_dls_resource_pct, axis=1)
    
    # Expected final score based on DLS resources
    def get_expected_score(row):
        if row['balls_bowled'] <= 0:
            return par_score  # PAR_SCORE default
        return resource_calc.calculate_expected_score(
            int(row['current_score']),
            row['balls_bowled'] / balls_per_over,  # overs_bowled
            int(row['wickets_lost'])
        )
    
    df['expected_final_score'] = df.apply(get_expected_score, axis=1)
    df['expected_final_vs_venue_avg'] = df['expected_final_score'] - df['venue_avg_score']
    
    # Phase indicators (3-phase: powerplay/middle/death, boundaries from config)
    pp_boundary = format_config.phase_thresholds[format_config.phase_names[0]]
    mid_boundary = format_config.phase_thresholds[format_config.phase_names[1]] + 1
    if format_config.format_name == 'hundred':
        df['is_powerplay'] = (df['balls_bowled'] <= format_config.powerplay_balls).astype(int)
        df['is_middle_overs'] = (
            (df['balls_bowled'] > format_config.powerplay_balls)
            & (df['balls_bowled'] <= format_config.phase_thresholds['middle'] * balls_per_over)
        ).astype(int)
        df['is_death_overs'] = (
            df['balls_bowled'] > format_config.phase_thresholds['middle'] * balls_per_over
        ).astype(int)
    else:
        df['is_powerplay'] = (df['over'] < pp_boundary).astype(int)
        df['is_middle_overs'] = ((df['over'] >= pp_boundary) & (df['over'] < mid_boundary)).astype(int)
        df['is_death_overs'] = (df['over'] >= mid_boundary).astype(int)
    
    # DLS-based pressure index (more accurate than simplified version)
    def get_dls_pressure(row):
        target = row.get('first_innings_score', 0) + 1 if row['innings'] == 2 else None
        return resource_calc.calculate_pressure_index(
            int(row['innings']),
            int(row['current_score']),
            row['balls_bowled'] / balls_per_over,
            int(row['wickets_lost']),
            target_runs=target if pd.notna(target) else None
        )
    
    df['dls_pressure_index'] = df.apply(get_dls_pressure, axis=1)
    
    # DLS-based win probability (structural cricket knowledge)
    def get_dls_win_prob(row):
        target = row.get('first_innings_score', 0) + 1 if row['innings'] == 2 else None
        balls_bowled = int(max(0, row['balls_bowled']))
        if balls_bowled <= 0:
            resource_over, resource_ball = 0, 0
        else:
            resource_over = (balls_bowled - 1) // balls_per_over
            resource_ball = ((balls_bowled - 1) % balls_per_over) + 1
        features = resource_calc.calculate_all_features(
            int(row['innings']),
            int(resource_over),
            int(resource_ball),
            int(row['current_score']),
            int(row['wickets_lost']),
            target_runs=target if pd.notna(target) else None
        )
        return features['resource_win_prob']
    
    df['resource_win_prob'] = df.apply(get_dls_win_prob, axis=1)
    
    # 9. Par Score (expected score at this point based on resources used)
    # For innings 2: compare current score to par
    # Resources used = 1 - resources_remaining
    df['resources_used'] = 1 - df['resources_remaining']
    df['par_score'] = np.where(
        df['innings'] == 2,
        df['first_innings_score'] * df['resources_used'],
        df['venue_avg_score'] * df['resources_used']  # Use venue avg for innings 1
    )
    df['score_vs_par'] = df['current_score'] - df['par_score']
    
    # 10. Momentum - Rolling run rate over last 6/12/18 balls
    # Calculate runs in last N balls within same innings
    df['runs_last_6'] = df.groupby(['match_id', 'innings'])['runs_total'].transform(
        lambda x: x.rolling(window=6, min_periods=1).sum()
    )
    df['runs_last_12'] = df.groupby(['match_id', 'innings'])['runs_total'].transform(
        lambda x: x.rolling(window=12, min_periods=1).sum()
    )
    df['runs_last_18'] = df.groupby(['match_id', 'innings'])['runs_total'].transform(
        lambda x: x.rolling(window=18, min_periods=1).sum()
    )
    
    # 11. Wickets in last N balls (recent pressure)
    df['wickets_last_12'] = df.groupby(['match_id', 'innings'])['is_wicket'].transform(
        lambda x: x.rolling(window=12, min_periods=1).sum()
    )
    
    # 12. Boundary frequency (4s and 6s indicator for aggression)
    df['is_boundary'] = df['runs_batter'].isin([4, 6]).astype(int)
    df['boundaries_last_12'] = df.groupby(['match_id', 'innings'])['is_boundary'].transform(
        lambda x: x.rolling(window=12, min_periods=1).sum()
    )
    
    # 13. Dot ball pressure
    df['is_dot'] = (df['runs_total'] == 0).astype(int)
    df['dots_last_12'] = df.groupby(['match_id', 'innings'])['is_dot'].transform(
        lambda x: x.rolling(window=12, min_periods=1).sum()
    )
    
    # 14. Acceleration potential (wickets in hand * balls remaining normalized)
    df['acceleration_potential'] = ((10 - df['wickets_lost']) * df['balls_remaining']) / (total_balls * 10)
    
    # 15. Chase difficulty (for innings 2)
    # Combines target, resources, and current position
    df['chase_difficulty'] = np.where(
        (df['innings'] == 2) & (df['resources_remaining'] > 0),
        df['runs_needed'] / (df['resources_remaining'] * df['first_innings_score'] + 1),
        0.0
    )
    
    # --- ADVANCED INNINGS 1 FEATURES ---
    print("Calculating advanced innings 1 features...")
    
    # 16. Scoring trajectory (are they accelerating?)
    # Compare recent scoring rate to earlier scoring rate
    df['rr_last_12'] = np.where(
        df['balls_bowled'] >= 12,
        df['runs_last_12'] / 12 * balls_per_over,  # Run rate in last 12 legal balls
        df['current_run_rate']
    )
    df['rr_earlier'] = np.where(
        df['balls_bowled'] > 18,
        ((df['current_score'] - df['runs_last_12']) / (df['balls_bowled'] - 12)) * balls_per_over,
        df['current_run_rate']
    )
    df['scoring_acceleration'] = df['rr_last_12'] - df['rr_earlier']
    
    # 17. Projected final score (innings 1)
    # Based on current run rate and resources remaining
    df['projected_score'] = np.where(
        df['innings'] == 1,
        df['current_score'] + (df['current_run_rate'] * df['balls_remaining'] / balls_per_over),
        0.0
    )
    
    # 18. Projected score vs venue average
    df['projected_vs_venue_avg'] = np.where(
        df['innings'] == 1,
        df['projected_score'] - df['venue_avg_score'],
        0.0
    )
    
    # 19. Partnership stability - wickets in last 30 balls (recent collapse indicator)
    df['wickets_last_30'] = df.groupby(['match_id', 'innings'])['is_wicket'].transform(
        lambda x: x.rolling(window=30, min_periods=1).sum()
    )

    # 20. Wickets in last 6 balls (immediate shock signal, research rank #4 death overs)
    df['wickets_last_6'] = df.groupby(['match_id', 'innings'])['is_wicket'].transform(
        lambda x: x.rolling(window=6, min_periods=1).sum()
    )

    # 21. Boundary ball rate (true ball fraction, not run fraction — bug fix)
    df['boundaries_last_18'] = df.groupby(['match_id', 'innings'])['is_boundary'].transform(
        lambda x: x.rolling(window=18, min_periods=1).sum()
    )
    df['boundary_pct_last_18'] = df['boundaries_last_18'] / df['balls_bowled'].clip(lower=1, upper=18)

    # 22. Dot ball rate over last 12 balls (stagnation indicator, research rank #4/#10)
    df['dot_pct_last_12'] = df['dots_last_12'] / df['balls_bowled'].clip(lower=1, upper=12)

    # 23. Balls since last wicket (partnership stability, research rank #11)
    df['_prev_wickets'] = df.groupby(['match_id', 'innings'])['is_wicket'].transform(
        lambda x: x.shift(1, fill_value=0).cumsum()
    )
    df['balls_since_wicket'] = df.groupby(['match_id', 'innings', '_prev_wickets']).cumcount()
    df.drop(columns=['_prev_wickets'], inplace=True)

    # 24. Set batter exposure (balls faced by current batter in innings, research rank #2/#8)
    df['set_batter_exposure'] = df.groupby(['match_id', 'innings', 'batter_id']).cumcount()
    
    # --- TEAM-SCORE INTERACTION FEATURES ---
    # These help the model learn that a high score matters less when a strong team is bowling
    print("Calculating team-score interaction features...")
    
    # 20a. Score advantage adjusted by team strength
    # If weaker team is scoring well (score_vs_par positive but team_strength_diff negative),
    # the advantage should be reduced
    df['score_adjusted_by_team'] = df['score_vs_par'] * (1 + df['team_strength_diff'])
    
    # 20b. First innings projected score adjusted by bowling team strength
    # A projected 200 against India (strong) is less valuable than against a weaker team
    df['projected_adjusted'] = np.where(
        df['innings'] == 1,
        df['projected_score'] * (1 - df['bowling_team_win_rate'].fillna(0.5) + 0.5),  # Scale by inverse bowling strength
        df['projected_score']
    )
    
    # 20c. Resource probability adjusted by team strength
    # Blend resource_win_prob with team strength for better first innings estimates
    df['resource_team_adjusted'] = df['resource_win_prob'] * (0.7 + 0.6 * df['team_strength_diff'])
    
    # 20d. Team-adjusted run rate difference
    # In first innings, adjust run rate impact by who's bowling
    df['run_rate_team_adj'] = np.where(
        df['innings'] == 1,
        df['current_run_rate'] * (1 + df['team_strength_diff']),  # High RR vs strong bowlers = more valuable
        df['run_rate_diff']
    )

    # 21. Run rate vs winning rate at venue (for innings 1)
    # If current RR is above venue's historical winning first innings RR, more likely to win
    df['rr_vs_venue_winning'] = np.where(
        df['innings'] == 1,
        df['current_run_rate'] - (df['venue_avg_score'] / 20),  # Venue avg RR
        0.0
    )
    
    # 22. Combined current batsmen strength
    # Get non-striker rolling avg too
    # For now, use a proxy: batter strength + small bonus if not many wickets lost
    df['batting_pair_strength'] = df['batsman_rolling_avg'].fillna(20) * (1 + 0.05 * (10 - df['wickets_lost']))

    # 6. Handle Missing Values (Initial matches)
    # Fill with global means or specific defaults
    cols_to_fill = ['batsman_rolling_avg', 'batsman_rolling_sr', 'bowler_rolling_econ', 'bowler_rolling_sr', 
                    'venue_avg_score', 'venue_avg_wickets', 'venue_bat_first_win_rate',
                    'par_score', 'score_vs_par',
                    # New venue/matchup features
                    'batsman_venue_avg', 'batsman_venue_sr', 'batsman_vs_team_avg',
                    'bowler_venue_econ', 'bowler_venue_sr', 'bowler_vs_team_econ']
    for col in cols_to_fill:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].mean())
    
    # Fill H2H with neutral 0.5 (no prior history)
    df['h2h_batting_win_rate'] = df['h2h_batting_win_rate'].fillna(0.5)
            
    # Fill calculated features NaNs (e.g. if first_innings_score missing)
    df['required_run_rate'] = df['required_run_rate'].fillna(0.0)
    df['run_rate_diff'] = df['run_rate_diff'].fillna(0.0)
    df['chase_difficulty'] = df['chase_difficulty'].fillna(0.0)
    df['match_phase'] = df['match_phase'].fillna(1.0)
    df['batting_team_win_rate'] = df['batting_team_win_rate'].fillna(0.5)
    df['bowling_team_win_rate'] = df['bowling_team_win_rate'].fillna(0.5)
    df['team_strength_diff'] = df['team_strength_diff'].fillna(0.0)
    
    # Fill batting/bowling first win rates
    df['batting_team_bat_first_wr'] = df['batting_team_bat_first_wr'].fillna(0.5)
    df['bowling_team_bowl_first_wr'] = df['bowling_team_bowl_first_wr'].fillna(0.5)
    df['batting_team_bowl_first_wr'] = df['batting_team_bowl_first_wr'].fillna(0.5)
    df['bowling_team_bat_first_wr'] = df['bowling_team_bat_first_wr'].fillna(0.5)
    df['batting_team_situation_wr'] = df['batting_team_situation_wr'].fillna(0.5)
    df['bowling_team_situation_wr'] = df['bowling_team_situation_wr'].fillna(0.5)
    df['situation_advantage'] = df['situation_advantage'].fillna(0.0)
    
    # Fill new innings 1 features
    df['scoring_acceleration'] = df['scoring_acceleration'].fillna(0.0)
    df['projected_score'] = df['projected_score'].fillna(0.0)
    df['projected_vs_venue_avg'] = df['projected_vs_venue_avg'].fillna(0.0)
    df['wickets_last_30'] = df['wickets_last_30'].fillna(0.0)
    df['boundary_pct_last_18'] = df['boundary_pct_last_18'].fillna(0.0)
    df['wickets_last_6'] = df['wickets_last_6'].fillna(0.0)
    df['dot_pct_last_12'] = df['dot_pct_last_12'].fillna(0.35)
    df['balls_since_wicket'] = df['balls_since_wicket'].fillna(0.0)
    df['set_batter_exposure'] = df['set_batter_exposure'].fillna(0.0)
    df['rr_vs_venue_winning'] = df['rr_vs_venue_winning'].fillna(0.0)
    
    # Fill DLS-based features
    df['resource_pct'] = df['resource_pct'].fillna(50.0)
    df['expected_final_score'] = df['expected_final_score'].fillna(par_score)
    df['dls_pressure_index'] = df['dls_pressure_index'].fillna(0.5)
    df['resource_win_prob'] = df['resource_win_prob'].fillna(0.5)
    df['overs_remaining'] = df['overs_remaining'].fillna(total_overs / 2.0)
    df['is_powerplay'] = df['is_powerplay'].fillna(0)
    df['is_middle_overs'] = df['is_middle_overs'].fillna(0)
    df['is_death_overs'] = df['is_death_overs'].fillna(0)
    df['batting_pair_strength'] = df['batting_pair_strength'].fillna(20.0)
    
    # Fill new team form features
    df['batting_recent_form'] = df['batting_recent_form'].fillna(0.5)
    df['bowling_recent_form'] = df['bowling_recent_form'].fillna(0.5)
    df['batting_win_streak'] = df['batting_win_streak'].fillna(0)
    df['bowling_win_streak'] = df['bowling_win_streak'].fillna(0)
    df['team_batting_form'] = df['team_batting_form'].fillna(8.0)
    df['team_bowling_form'] = df['team_bowling_form'].fillna(8.0)
    df['venue_chase_success'] = df['venue_chase_success'].fillna(0.5)
    df['batting_is_home'] = df['batting_is_home'].fillna(0.0)
    df['bowling_is_home'] = df['bowling_is_home'].fillna(0.0)
    df['home_advantage'] = df['home_advantage'].fillna(0.0)
    df['form_diff'] = df['form_diff'].fillna(0.0)
    df['batting_vs_bowling_form'] = df['batting_vs_bowling_form'].fillna(0.0)
    df['season_num'] = df['season_num'].fillna(7)  # Middle season
    df['season_year_norm'] = df['season_year_norm'].fillna(0.5)

    # --- INN1 CARRYOVER FEATURES (bridge innings transition) ---
    # These carry first-innings information into the second innings so the ML model
    # doesn't lose context at the innings break.
    print("Calculating innings carryover features...")

    # inn1_defendability: The resource_win_prob at the last ball of inn1,
    # carried forward to all inn2 balls. Tells the model how the SQI model
    # rated the first innings total's defendability.
    inn1_final_rwp = df[df.innings == 1].groupby('match_id')['resource_win_prob'].last()
    df['inn1_defendability'] = df['match_id'].map(inn1_final_rwp)
    df['inn1_defendability'] = np.where(df['innings'] == 2, df['inn1_defendability'], 0.5)
    df['inn1_defendability'] = df['inn1_defendability'].fillna(0.5)

    # target_above_par: How far the first innings score is above/below venue average.
    # Positive = above-par target (harder chase), negative = below-par (easier chase).
    # For inn1, set to 0 (no target yet).
    df['target_above_par'] = np.where(
        df['innings'] == 2,
        df['first_innings_score'] - df['venue_avg_score'],
        0.0
    )
    df['target_above_par'] = df['target_above_par'].fillna(0.0)

    # Inn1 detailed carryover: match context features carried into inn2
    # These give the model a stronger pre-chase prior (180/3 ≠ 180/8).
    inn1_data = df[df['innings'] == 1]

    # Wickets lost in inn1 — how many resources were consumed to set the target
    inn1_wkts = inn1_data.groupby('match_id')['wickets_lost'].last()
    df['inn1_wickets_lost'] = df['match_id'].map(inn1_wkts)
    df['inn1_wickets_lost'] = np.where(df['innings'] == 2, df['inn1_wickets_lost'], 5.0)
    df['inn1_wickets_lost'] = df['inn1_wickets_lost'].fillna(5.0)

    # Death overs run rate (overs 16-20) — finish momentum
    inn1_death = inn1_data[inn1_data['over'] > 15]
    death_rr = inn1_death.groupby('match_id')['runs_total'].mean() * balls_per_over  # per-ball avg × configured set size = RR
    df['inn1_death_rr'] = df['match_id'].map(death_rr)
    df['inn1_death_rr'] = np.where(df['innings'] == 2, df['inn1_death_rr'], 9.0)
    df['inn1_death_rr'] = df['inn1_death_rr'].fillna(9.0)

    # PP runs in inn1 — pitch behavior clue for early chase
    inn1_pp = inn1_data[inn1_data['over'] <= 6]
    pp_runs = inn1_pp.groupby('match_id')['runs_total'].sum()
    df['inn1_pp_runs'] = df['match_id'].map(pp_runs)
    df['inn1_pp_runs'] = np.where(df['innings'] == 2, df['inn1_pp_runs'], 45.0)
    df['inn1_pp_runs'] = df['inn1_pp_runs'].fillna(45.0)

    # --- INTERACTION FEATURES ---
    print("Calculating interaction features...")
    df['crr_times_res'] = df['current_run_rate'] * df['resources_remaining']
    df['wickets_times_balls'] = df['wickets_lost'] * df['balls_remaining']
    df['rrr_times_wickets'] = df['required_run_rate'] * df['wickets_lost']
    df['score_per_wicket'] = df['current_score'] / (df['wickets_lost'] + 1)

    # is_low_target: explicit flag for chases of sub-140 targets (very hard to defend)
    # Uses first_innings_score (available after the target merge earlier in the pipeline)
    df['is_low_target'] = (
        (df['innings'] == 2) & (df['first_innings_score'] < 140)
    ).astype(float)

    # Select columns for training- DLS-enhanced feature set (proven best performance)
    # Based on extensive testing: DLS features + original game state features work best
    feature_cols = [
        # Player stats
        'bowler_rolling_econ',      
        'batsman_rolling_sr',       
        'batting_pair_strength',    
        'bowler_vs_team_econ',      
        'batsman_venue_sr',         
        'batsman_rolling_avg',      
        'bowler_venue_econ',        
        'batsman_vs_team_avg',      
        'batsman_venue_avg',        
        'bowler_rolling_sr',        
        'bowler_venue_sr',          
        # Game state
        'score_vs_par',             
        'required_run_rate',        
        'pressure_index',           
        'run_rate_diff',            
        'chase_difficulty',         
        'current_run_rate',         
        'resources_remaining',      
        'wickets_lost',             
        'projected_vs_venue_avg',   
        'expected_final_vs_venue_avg',
        'team_strength_diff',       
        # Momentum
        'runs_last_12',             
        'runs_last_18',             
        'wickets_last_12',          
        'boundary_pct_last_18',     
        'dot_pct_last_12',          # Stagnation indicator (research rank #4/#10)
        'set_batter_exposure',      # Batter settledness (research rank #2/#8)
        'balls_since_wicket',       # Partnership stability (research rank #11)
        'wickets_last_6',           # Immediate shock window
        # Team win rates
        'batting_team_win_rate',    
        'bowling_team_win_rate',    
        'batting_team_situation_wr', 
        'bowling_team_situation_wr', 
        'situation_advantage',       
        # Additional useful
        'acceleration_potential',   
        'wickets_last_30',          
        'projected_score',          
        # Interaction features
        'score_per_wicket',         
        'rrr_times_wickets',        
        'wickets_times_balls',      
        'crr_times_res',            
        # DLS-STYLE HYBRID FEATURES (cricket domain knowledge)
        'resource_pct',             
        'expected_final_score',     
        'dls_pressure_index',       
        'resource_win_prob',        
        'overs_remaining',          
        'is_powerplay',             
        'is_middle_overs',          
        'is_death_overs',           
        'innings',
        'gender_female',
        # Team-score interaction features (help model learn team context)
        'score_adjusted_by_team',
        'projected_adjusted',
        'resource_team_adjusted',
        'run_rate_team_adj',
        # Inn1 carryover (bridge innings transition)
        'inn1_defendability',
        'target_above_par',
        # Inn1 detailed carryover (pre-chase prior)
        'inn1_wickets_lost',
        'inn1_death_rr',
        'inn1_pp_runs',
        # Context features (toss + venue chase bias)
        'venue_chase_success',
        'batting_won_toss',
        # Venue-over par (how far ahead/behind expected cumulative score at this venue+over)
        'score_vs_venue_over_par',
        # v9: batting team venue WR, recent NRR form, low-target flag
        'batting_team_venue_wr',
        'batting_recent_nrr_l5',
        'is_low_target',
        # Target
        'is_winner'
    ]
    
    # Ensure output directories exist
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_store_dir.mkdir(parents=True, exist_ok=True)
    
    # Include metadata columns for analysis (not used by model)
    metadata_cols = ['match_id', 'season', 'over', 'ball', 'batting_team', 'bowling_team', 'winner']
    all_cols = feature_cols + [c for c in metadata_cols if c in df.columns and c not in feature_cols]
    training_data = df[all_cols].copy()
    training_path = output_dir / "training.parquet"
    logger.info(f"Saving training data to {training_path}")
    training_data.to_parquet(training_path)
    
    # --- ALSO CREATE SAMPLED TRAINING DATA ---
    # Sample key moments: end of each scoring set for more balanced data.
    # The Hundred has five-ball sets; T20/ODI retain their configured six-ball
    # over semantics.
    print("Creating sampled training data (end of each over)...")
    
    # Filter to last ball of each scoring set (or last ball in data).
    sampled = df[df['ball'] == balls_per_over].copy()
    
    # Also include innings 2 final balls for chase scenarios
    final_balls = df.groupby(['match_id', 'innings']).tail(1)
    sampled = pd.concat([sampled, final_balls]).drop_duplicates(
        subset=['match_id', 'innings', 'over', 'ball']
    )
    
    sampled_data = sampled[feature_cols].copy()
    sampled_path = output_dir / "training_sampled.parquet"
    logger.info(f"Saving sampled training data to {sampled_path} ({len(sampled_data)} rows)")
    sampled_data.to_parquet(sampled_path)
    
    # Save Feature Store Artifacts (latest stats)
    logger.info("Saving feature store artifacts")
    
    # Player Stats (Batting)
    latest_batting = batting_features.sort_values('start_date').groupby('batsman').last()[['batsman_rolling_avg', 'batsman_rolling_sr']]
    latest_batting.index.name = 'player_name'
    
    # Player Stats (Bowling)
    latest_bowling = bowling_features.sort_values('start_date').groupby('bowler').last()[['bowler_rolling_econ', 'bowler_rolling_sr']]
    latest_bowling.index.name = 'player_name'
    
    # Merge Batting and Bowling
    player_stats = latest_batting.join(latest_bowling, how='outer')
    player_stats.to_parquet(feature_store_dir / "player_stats.parquet")
    
    # Venue Stats
    latest_venue = venue_features.sort_values('start_date').groupby('venue').last()[['venue_avg_score', 'venue_avg_wickets', 'venue_bat_first_win_rate']]
    latest_venue.to_parquet(feature_store_dir / "venue_stats.parquet")

    # Venue-over par lookup (FULL mean — no LOO — for best inference quality)
    venue_over_par_full = (
        inn1_over_end
        .groupby(['venue', 'over'])
        .agg(venue_over_par=('over_end_score', 'mean'))
        .reset_index()
    )
    venue_over_par_full.to_parquet(feature_store_dir / 'venue_over_par.parquet', index=False)
    
    # Team Stats
    print("Calculating team stats...")
    # Calculate win rate for each team
    # Get unique matches from the dataframe
    matches = df[['match_id', 'date', 'batting_team', 'bowling_team', 'winner', 'innings']].drop_duplicates(subset=['match_id'])
    
    team_stats = []
    all_teams = pd.concat([matches['batting_team'], matches['bowling_team']]).unique()
    
    for team in all_teams:
        team_matches = matches[(matches['batting_team'] == team) | (matches['bowling_team'] == team)]
        wins = team_matches[team_matches['winner'] == team].shape[0]
        total = team_matches.shape[0]
        win_rate = wins / total if total > 0 else 0.5
        
        # Calculate bat first win rate (when team is batting_team and innings == 1)
        bat_first_matches = matches[matches['batting_team'] == team]
        bat_first_wins = bat_first_matches[bat_first_matches['winner'] == team].shape[0]
        bat_first_total = bat_first_matches.shape[0]
        bat_first_wr = bat_first_wins / bat_first_total if bat_first_total > 0 else 0.5
        
        # Calculate bowl first win rate (when team is bowling_team and innings == 1)
        bowl_first_matches = matches[matches['bowling_team'] == team]
        bowl_first_wins = bowl_first_matches[bowl_first_matches['winner'] == team].shape[0]
        bowl_first_total = bowl_first_matches.shape[0]
        bowl_first_wr = bowl_first_wins / bowl_first_total if bowl_first_total > 0 else 0.5
        
        team_stats.append({
            'team': team, 
            'win_rate': win_rate, 
            'matches': total,
            'bat_first_wr': bat_first_wr,
            'bowl_first_wr': bowl_first_wr,
            'recent_nrr': float(latest_nrr_map.get(team, 0.0)),
        })
    
    df_team_stats = pd.DataFrame(team_stats)
    df_team_stats.to_parquet(feature_store_dir / "team_ratings.parquet")
    logger.info(f"Saved team ratings for {len(df_team_stats)} teams")

    # Team × venue win rates for batting_team_venue_wr inference lookup
    team_venue_full.to_parquet(feature_store_dir / 'team_venue_ratings.parquet', index=False)
    logger.info(f"Saved team venue ratings: {len(team_venue_full)} (team,venue) combos (n>=3)")

    logger.info("Processing complete")


def export_odm_base_data(input_dir: Path, output_file: Path, league: Optional[str] = None) -> pd.DataFrame:
    """Export a sequence-preserving legal-ball dataset for ODM training."""
    logger.info("Starting ODM base export", input_dir=str(input_dir), output_file=str(output_file))

    df = pd.read_parquet(input_dir)
    df = _apply_team_canonical_names(df)

    if 'league' not in df.columns or df['league'].isna().all():
        if not league:
            raise ValueError("League must be provided when source data does not contain a usable 'league' column")
        df['league'] = league

    missing = [col for col in ODM_BASE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing ODM base columns: {missing}")

    df = df[ODM_BASE_COLUMNS].copy()

    key_cols = ['league', 'match_id', 'innings', 'over', 'ball']
    original_len = len(df)
    df = df.drop_duplicates(subset=key_cols, keep='first')
    if len(df) != original_len:
        logger.warning("Dropped duplicate ODM base rows", removed=original_len - len(df))

    df = df.sort_values(key_cols).reset_index(drop=True)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_file, index=False)

    logger.info(
        "ODM base export complete",
        rows=len(df),
        matches=int(df['match_id'].nunique()),
        output_file=str(output_file),
    )
    return df
