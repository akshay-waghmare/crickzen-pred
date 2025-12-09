import pandas as pd
import numpy as np
from pathlib import Path
import structlog

logger = structlog.get_logger()

def prepare_runs_data(input_path: str, output_path: str):
    logger.info("Loading data for runs prediction", path=input_path)
    df = pd.read_csv(input_path)
    
    # Filter out invalid innings
    df = df[df['innings_num'].isin([1, 2])]
    
    # Calculate Total Runs per Innings (Target)
    logger.info("Calculating target variable (total runs)")
    total_runs = df.groupby(['match_id', 'innings_num'])['runs_scored'].sum().reset_index()
    total_runs.rename(columns={'runs_scored': 'target_runs'}, inplace=True)
    
    df = df.merge(total_runs, on=['match_id', 'innings_num'], how='left')
    
    # Calculate Current State Features
    logger.info("Calculating current state features")
    # Sort just in case
    df = df.sort_values(['match_id', 'innings_num', 'over_number', 'ball_number'])
    
    df['current_score'] = df.groupby(['match_id', 'innings_num'])['runs_scored'].cumsum()
    df['wickets_lost'] = df.groupby(['match_id', 'innings_num'])['wickets'].cumsum()
    df['balls_bowled'] = df.groupby(['match_id', 'innings_num']).cumcount() + 1
    df['overs_completed'] = df['balls_bowled'] / 6.0
    
    # Current Run Rate
    df['current_run_rate'] = (df['current_score'] / df['balls_bowled']) * 6
    
    # Resources Remaining (Duckworth-Lewis style approximation or simple)
    df['wickets_remaining'] = 10 - df['wickets_lost']
    df['balls_remaining'] = 120 - df['balls_bowled']
    
    # Select Features for Regression
    feature_cols = [
        'current_score', 'wickets_lost', 'balls_remaining', 'wickets_remaining',
        'current_run_rate', 'innings_num',
        # Add historical stats if available in the CSV
        'batsman1_historical_average', 'batsman1_historical_strike_rate',
        'batsman2_historical_average', 'batsman2_historical_strike_rate',
        'bowler1_historical_economy', 'bowler1_historical_average',
        'average_runs_per_over', # Venue stat?
        'target_runs' # Target
    ]
    
    # Filter columns that exist
    existing_cols = [c for c in feature_cols if c in df.columns]
    
    final_df = df[existing_cols].copy()
    
    # Ensure numeric types
    numeric_cols = [
        'batsman1_historical_average', 'batsman1_historical_strike_rate',
        'batsman2_historical_average', 'batsman2_historical_strike_rate',
        'bowler1_historical_economy', 'bowler1_historical_average',
        'average_runs_per_over'
    ]
    
    for col in numeric_cols:
        if col in final_df.columns:
            final_df[col] = pd.to_numeric(final_df[col], errors='coerce')
    
    # Drop NaNs
    final_df = final_df.dropna()
    
    logger.info(f"Saving {len(final_df)} rows to {output_path}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    final_df.to_parquet(output_path)

if __name__ == "__main__":
    # Configure logging
    structlog.configure(processors=[structlog.processors.JSONRenderer()])
    
    prepare_runs_data(
        input_path="ml_predictions/aggregated_match_data.csv",
        output_path="data/runs_prediction_training.parquet"
    )
