"""
Generate NPL (Nepal Premier League) Feature Store and Training Data.
Processes raw NPL parquet data into features for model training.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bbl_pipeline.features.calculator import StatsCalculator, ResourceFeatureCalculator


def generate_npl_features():
    """
    Process NPL raw data into training features.
    Similar to how BBL, WBBL, and ILT20 data is processed.
    """
    print("="*70)
    print("Nepal Premier League (NPL) Feature Generator")
    print("="*70)
    
    # Paths
    input_path = Path("data/npl_raw/npl_raw.parquet")
    output_dir = Path("data/npl_features_v1")
    feature_store_dir = Path("data/npl_feature_store_v1")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_store_dir.mkdir(parents=True, exist_ok=True)
    
    if not input_path.exists():
        print(f"ERROR: Raw data not found at {input_path}")
        print("Please run process_npl_data.py first to generate raw parquet.")
        return
    
    print(f"\nLoading raw data from {input_path}...")
    df = pd.read_parquet(input_path)
    print(f"Loaded {len(df)} rows, {df['match_id'].nunique()} matches")
    
    # Remove duplicate rows
    dup_cols = ['match_id', 'innings', 'over', 'ball']
    original_len = len(df)
    df = df.drop_duplicates(subset=dup_cols, keep='first')
    if len(df) < original_len:
        print(f"Removed {original_len - len(df)} duplicate rows, now {len(df)} rows")
    
    # === 1. Create Target Variable ===
    print("\n[1/10] Creating target variable...")
    df['is_winner'] = (df['batting_team'] == df['winner']).astype(int)
    
    # === 2. Calculate Cumulative Scores ===
    print("[2/10] Calculating cumulative scores...")
    df = df.sort_values(['match_id', 'innings', 'over', 'ball'])
    
    df['current_score'] = df.groupby(['match_id', 'innings'])['runs_total'].transform('cumsum')
    df['is_wicket'] = df['player_out_id'].notna().astype(int)
    df['wickets_lost'] = df.groupby(['match_id', 'innings'])['is_wicket'].transform('cumsum')
    
    # === 3. Calculate Batting Stats ===
    print("[3/10] Calculating batting stats...")
    calc = StatsCalculator()
    
    batting_agg = df.groupby(['match_id', 'date', 'batter_id']).agg({
        'runs_batter': 'sum',
        'ball': 'count',
        'player_out_id': lambda x: x.notna().sum()
    }).reset_index().rename(columns={
        'date': 'start_date',
        'batter_id': 'batsman',
        'runs_batter': 'runs',
        'ball': 'balls_faced',
        'player_out_id': 'is_out'
    })
    
    batting_rolling = calc.calculate_rolling_batting_stats(batting_agg)
    batting_features = pd.concat([batting_agg, batting_rolling], axis=1)
    
    # === 4. Calculate Bowling Stats ===
    print("[4/10] Calculating bowling stats...")
    bowling_agg = df.groupby(['match_id', 'date', 'bowler_id']).agg({
        'runs_total': 'sum',
        'ball': 'count',
        'wicket_type': lambda x: x.notna().sum()
    }).reset_index().rename(columns={
        'date': 'start_date',
        'bowler_id': 'bowler',
        'runs_total': 'runs_conceded',
        'ball': 'balls_bowled',
        'wicket_type': 'wickets'
    })
    
    bowling_rolling = calc.calculate_rolling_bowling_stats(bowling_agg)
    bowling_features = pd.concat([bowling_agg, bowling_rolling], axis=1)
    
    # === 5. Calculate Venue Stats ===
    print("[5/10] Calculating venue stats...")
    
    # First innings scores
    first_innings = df[df['innings'] == 1].groupby(['match_id', 'venue_id', 'date'])['runs_total'].sum().reset_index()
    first_innings.columns = ['match_id', 'venue', 'start_date', 'first_innings_score']
    
    # Get match winners
    match_meta = df[['match_id', 'batting_team_id', 'winner', 'innings']].drop_duplicates()
    bat_first_team = match_meta[match_meta['innings'] == 1][['match_id', 'batting_team_id']].drop_duplicates(subset=['match_id'])
    bat_first_team.columns = ['match_id', 'team_bat_first']
    
    winners = df[['match_id', 'winner']].dropna().drop_duplicates(subset=['match_id'])
    
    # Total wickets in match
    match_wickets = df.groupby(['match_id'])['wicket_type'].count().reset_index()
    match_wickets.columns = ['match_id', 'wickets_total']
    
    venue_base = first_innings.merge(bat_first_team, on='match_id')
    venue_base = venue_base.merge(winners, on='match_id')
    venue_base = venue_base.merge(match_wickets, on='match_id')
    venue_base['bat_first_win'] = (venue_base['team_bat_first'] == venue_base['winner']).astype(int)
    
    venue_rolling = calc.calculate_venue_stats(venue_base)
    venue_features = pd.concat([venue_base, venue_rolling], axis=1)
    
    # === 6. Calculate Team Win Rates ===
    print("[6/10] Calculating team win rates...")
    
    innings1 = match_meta[match_meta['innings'] == 1][['match_id', 'batting_team_id', 'winner']].drop_duplicates(subset=['match_id'])
    innings1 = innings1.merge(df[['match_id', 'date']].drop_duplicates(), on='match_id')
    
    # Get team2 (bowling team in innings 1)
    innings1_full = match_meta[match_meta['innings'] == 1][['match_id', 'batting_team_id']].drop_duplicates(subset=['match_id'])
    innings2_full = match_meta[match_meta['innings'] == 2][['match_id', 'batting_team_id']].drop_duplicates(subset=['match_id'])
    innings2_full.columns = ['match_id', 'team2']
    
    innings1 = innings1.merge(innings2_full, on='match_id', how='left')
    innings1 = innings1.rename(columns={'batting_team_id': 'team1'})
    
    # Calculate rolling win rates
    team1_matches = innings1[['match_id', 'date', 'team1', 'winner']].copy()
    team1_matches.columns = ['match_id', 'date', 'team', 'winner']
    team2_matches = innings1[['match_id', 'date', 'team2', 'winner']].copy()
    team2_matches.columns = ['match_id', 'date', 'team', 'winner']
    
    all_team_matches = pd.concat([team1_matches, team2_matches], ignore_index=True)
    all_team_matches['won'] = (all_team_matches['team'] == all_team_matches['winner']).astype(int)
    all_team_matches = all_team_matches.sort_values(['team', 'date'])
    
    all_team_matches['team_rolling_wins'] = all_team_matches.groupby('team')['won'].transform(
        lambda x: x.shift(1).rolling(window=10, min_periods=1).sum()
    )
    all_team_matches['team_rolling_matches'] = all_team_matches.groupby('team')['won'].transform(
        lambda x: x.shift(1).rolling(window=10, min_periods=1).count()
    )
    all_team_matches['team_win_rate'] = all_team_matches['team_rolling_wins'] / all_team_matches['team_rolling_matches'].replace(0, 1)
    
    team_win_rates = all_team_matches[['match_id', 'team', 'team_win_rate']].drop_duplicates()
    
    # === 7. Calculate Game State Features ===
    print("[7/10] Calculating game state features...")
    
    # Merge first innings score for target calculation
    df = df.merge(first_innings[['match_id', 'first_innings_score']], on='match_id', how='left')
    
    # Balls and overs
    df['balls_bowled'] = df['over'] * 6 + df['ball']
    df['balls_remaining'] = 120 - df['balls_bowled']
    df['overs_remaining'] = (120 - df['balls_bowled']) / 6
    
    # Run rates
    df['current_run_rate'] = np.where(
        df['balls_bowled'] > 0,
        (df['current_score'] / df['balls_bowled']) * 6,
        0.0
    )
    
    df['target_score'] = df['first_innings_score'] + 1
    df['runs_needed'] = df['target_score'] - df['current_score']
    df['required_run_rate'] = np.where(
        (df['innings'] == 2) & (df['balls_remaining'] > 0),
        (df['runs_needed'] / df['balls_remaining']) * 6,
        0.0
    )
    df['run_rate_diff'] = np.where(
        df['innings'] == 2,
        df['current_run_rate'] - df['required_run_rate'],
        0.0
    )
    
    # Match phases
    df['is_powerplay'] = (df['over'] < 6).astype(int)
    df['is_middle_overs'] = ((df['over'] >= 6) & (df['over'] < 15)).astype(int)
    df['is_death_overs'] = (df['over'] >= 15).astype(int)
    
    # Resources
    df['resources_remaining'] = (df['balls_remaining'] / 120) * ((10 - df['wickets_lost']) / 10)
    
    # Pressure index
    df['pressure_index'] = np.where(
        df['innings'] == 2,
        df['required_run_rate'] * (1 + df['wickets_lost'] * 0.15),
        df['wickets_lost'] * 0.5
    )
    
    # === 8. Calculate DLS-Style Features ===
    print("[8/10] Calculating DLS-style features...")
    resource_calc = ResourceFeatureCalculator()
    
    def get_dls_features(row):
        target = row.get('first_innings_score', 0) + 1 if row['innings'] == 2 else None
        features = resource_calc.calculate_all_features(
            int(row['innings']),
            int(row['over']),
            int(row['ball']),
            int(row['current_score']),
            int(row['wickets_lost']),
            target_runs=target if pd.notna(target) else None
        )
        return pd.Series({
            'resource_pct': features.get('resource_pct', 50.0),
            'resource_win_prob': features.get('resource_win_prob', 0.5),
            'dls_pressure_index': features.get('dls_pressure_index', 0.5)
        })
    
    print("  Calculating DLS features (this may take a moment)...")
    dls_features = df.apply(get_dls_features, axis=1)
    df = pd.concat([df, dls_features], axis=1)
    
    # === 9. Merge All Features ===
    print("[9/10] Merging all features...")
    
    # Merge batting features
    df = df.merge(
        batting_features[['match_id', 'batsman', 'batsman_rolling_avg', 'batsman_rolling_sr']],
        left_on=['match_id', 'batter_id'],
        right_on=['match_id', 'batsman'],
        how='left'
    )
    
    # Merge bowling features
    df = df.merge(
        bowling_features[['match_id', 'bowler', 'bowler_rolling_econ', 'bowler_rolling_sr']],
        left_on=['match_id', 'bowler_id'],
        right_on=['match_id', 'bowler'],
        how='left'
    )
    
    # Merge venue features
    df = df.merge(
        venue_features[['match_id', 'venue_avg_score', 'venue_avg_wickets', 'venue_bat_first_win_rate']],
        on='match_id',
        how='left'
    )
    
    # Merge team win rates (batting team)
    df = df.merge(
        team_win_rates.rename(columns={'team': 'batting_team_id', 'team_win_rate': 'batting_team_win_rate'}),
        on=['match_id', 'batting_team_id'],
        how='left'
    )
    
    # Merge team win rates (bowling team)
    df = df.merge(
        team_win_rates.rename(columns={'team': 'bowling_team_id', 'team_win_rate': 'bowling_team_win_rate'}),
        on=['match_id', 'bowling_team_id'],
        how='left'
    )
    
    # Derived features
    df['team_strength_diff'] = df['batting_team_win_rate'].fillna(0.5) - df['bowling_team_win_rate'].fillna(0.5)
    df['batting_team_situation_wr'] = df['batting_team_win_rate'].fillna(0.5)
    df['bowling_team_situation_wr'] = df['bowling_team_win_rate'].fillna(0.5)
    
    # Momentum features
    df['runs_last_12'] = df.groupby(['match_id', 'innings'])['runs_total'].transform(
        lambda x: x.rolling(window=12, min_periods=1).sum()
    )
    df['runs_last_18'] = df.groupby(['match_id', 'innings'])['runs_total'].transform(
        lambda x: x.rolling(window=18, min_periods=1).sum()
    )
    df['wickets_last_12'] = df.groupby(['match_id', 'innings'])['is_wicket'].transform(
        lambda x: x.rolling(window=12, min_periods=1).sum()
    )
    df['wickets_last_30'] = df.groupby(['match_id', 'innings'])['is_wicket'].transform(
        lambda x: x.rolling(window=30, min_periods=1).sum()
    )
    
    # Boundary features
    df['is_boundary'] = df['runs_batter'].isin([4, 6]).astype(int)
    df['boundaries_last_12'] = df.groupby(['match_id', 'innings'])['is_boundary'].transform(
        lambda x: x.rolling(window=12, min_periods=1).sum()
    )
    df['boundary_pct_last_18'] = np.where(
        df['runs_last_18'] > 0,
        df['boundaries_last_12'] * 4 / df['runs_last_18'],
        0.0
    )
    
    # Advanced features
    df['acceleration_potential'] = ((10 - df['wickets_lost']) * df['balls_remaining']) / 1200
    df['score_per_wicket'] = df['current_score'] / (df['wickets_lost'] + 1)
    df['crr_times_res'] = df['current_run_rate'] * df['resources_remaining']
    df['rrr_times_wickets'] = df['required_run_rate'] * df['wickets_lost']
    df['wickets_times_balls'] = df['wickets_lost'] * df['balls_remaining']
    
    # Par score
    df['par_score'] = np.where(
        df['innings'] == 2,
        df['first_innings_score'] * (1 - df['resources_remaining']),
        df['venue_avg_score'].fillna(150) * (1 - df['resources_remaining'])
    )
    df['score_vs_par'] = df['current_score'] - df['par_score']
    
    # Chase difficulty
    df['chase_difficulty'] = np.where(
        (df['innings'] == 2) & (df['resources_remaining'] > 0),
        df['runs_needed'] / (df['resources_remaining'] * df['first_innings_score'] + 1),
        0.0
    )
    
    # Projected score
    df['projected_score'] = np.where(
        df['innings'] == 1,
        df['current_score'] + (df['current_run_rate'] * df['balls_remaining'] / 6),
        0.0
    )
    df['projected_vs_venue_avg'] = np.where(
        df['innings'] == 1,
        df['projected_score'] - df['venue_avg_score'].fillna(150),
        0.0
    )
    
    # Batting pair strength
    df['batting_pair_strength'] = df['batsman_rolling_avg'].fillna(20) * (1 + 0.05 * (10 - df['wickets_lost']))
    
    # === 10. Fill Missing Values and Save ===
    print("[10/10] Filling missing values and saving...")
    
    # Fill missing values
    fill_defaults = {
        'batsman_rolling_avg': 20.0,
        'batsman_rolling_sr': 120.0,
        'bowler_rolling_econ': 8.0,
        'bowler_rolling_sr': 20.0,
        'venue_avg_score': 150.0,
        'venue_avg_wickets': 6.0,
        'venue_bat_first_win_rate': 0.5,
        'batting_team_win_rate': 0.5,
        'bowling_team_win_rate': 0.5,
        'team_strength_diff': 0.0,
        'batting_team_situation_wr': 0.5,
        'bowling_team_situation_wr': 0.5,
        'resource_pct': 50.0,
        'resource_win_prob': 0.5,
        'dls_pressure_index': 0.5,
        'batting_pair_strength': 20.0,
    }
    
    for col, default in fill_defaults.items():
        if col in df.columns:
            df[col] = df[col].fillna(default)
    
    # Fill remaining NaN with 0
    df = df.fillna(0)
    
    # Feature columns for training
    feature_cols = [
        # Player stats
        'batsman_rolling_avg', 'batsman_rolling_sr',
        'bowler_rolling_econ', 'bowler_rolling_sr',
        'batting_pair_strength',
        # Game state
        'current_run_rate', 'required_run_rate', 'run_rate_diff',
        'wickets_lost', 'resources_remaining', 'overs_remaining',
        'is_powerplay', 'is_middle_overs', 'is_death_overs',
        # DLS features
        'resource_pct', 'resource_win_prob', 'dls_pressure_index',
        # Pressure/momentum
        'pressure_index', 'score_vs_par', 'chase_difficulty',
        'runs_last_12', 'runs_last_18', 'wickets_last_12', 'wickets_last_30',
        'boundary_pct_last_18', 'acceleration_potential',
        # Team stats
        'batting_team_win_rate', 'bowling_team_win_rate', 'team_strength_diff',
        'batting_team_situation_wr', 'bowling_team_situation_wr',
        # Venue
        'venue_avg_score', 'venue_bat_first_win_rate',
        # Derived
        'projected_score', 'projected_vs_venue_avg',
        'score_per_wicket', 'crr_times_res', 'rrr_times_wickets', 'wickets_times_balls',
        # Target
        'is_winner',
        # Meta
        'match_id'
    ]
    
    # Filter to available columns
    available_cols = [c for c in feature_cols if c in df.columns]
    print(f"\nUsing {len(available_cols)} features")
    
    # Save full training data
    training_data = df[available_cols].copy()
    training_path = output_dir / "training.parquet"
    training_data.to_parquet(training_path, index=False)
    print(f"Saved training data to {training_path} ({len(training_data)} rows)")
    
    # Save sampled training data (end of each over)
    sampled = df[df['ball'] == 6].copy()
    final_balls = df.groupby(['match_id', 'innings']).tail(1)
    sampled = pd.concat([sampled, final_balls]).drop_duplicates()
    
    sampled_data = sampled[available_cols].copy()
    sampled_path = output_dir / "training_sampled.parquet"
    sampled_data.to_parquet(sampled_path, index=False)
    print(f"Saved sampled training data to {sampled_path} ({len(sampled_data)} rows)")
    
    # === Save Feature Store Artifacts ===
    print("\nSaving feature store artifacts...")
    
    # Player stats (batting)
    latest_batting = batting_features.sort_values('start_date').groupby('batsman').last()[['batsman_rolling_avg', 'batsman_rolling_sr']]
    latest_batting.index.name = 'player_name'
    
    # Player stats (bowling)
    latest_bowling = bowling_features.sort_values('start_date').groupby('bowler').last()[['bowler_rolling_econ', 'bowler_rolling_sr']]
    latest_bowling.index.name = 'player_name'
    
    # Merge batting and bowling
    player_stats = latest_batting.join(latest_bowling, how='outer')
    player_stats.to_parquet(feature_store_dir / "player_stats.parquet")
    print(f"  Saved player stats for {len(player_stats)} players")
    
    # Venue stats
    latest_venue = venue_features.sort_values('start_date').groupby('venue').last()[['venue_avg_score', 'venue_avg_wickets', 'venue_bat_first_win_rate']]
    latest_venue.to_parquet(feature_store_dir / "venue_stats.parquet")
    print(f"  Saved venue stats for {len(latest_venue)} venues")
    
    # Team ratings
    latest_team = team_win_rates.groupby('team').last()[['team_win_rate']]
    latest_team.to_parquet(feature_store_dir / "team_ratings.parquet")
    print(f"  Saved team ratings for {len(latest_team)} teams")
    
    print("\n" + "="*70)
    print("FEATURE GENERATION COMPLETE")
    print("="*70)
    print(f"Training data: {training_path}")
    print(f"Sampled data: {sampled_path}")
    print(f"Feature store: {feature_store_dir}")
    
    return df


if __name__ == "__main__":
    generate_npl_features()
