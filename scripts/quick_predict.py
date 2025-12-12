import argparse
import pandas as pd
import joblib
import sys
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bbl_pipeline.features.calculator import ResourceFeatureCalculator

def load_team_ratings():
    path = Path("data/t20i_feature_store_v1/team_ratings.parquet")
    if path.exists():
        df = pd.read_parquet(path)
        return dict(zip(df['team'], df['win_rate']))
    return {}

def main():
    parser = argparse.ArgumentParser(description="Quick T20I Predictor")
    parser.add_argument("--batting", required=True, help="Batting team name")
    parser.add_argument("--bowling", required=True, help="Bowling team name")
    parser.add_argument("--score", type=int, required=True, help="Current runs")
    parser.add_argument("--wickets", type=int, required=True, help="Wickets lost")
    parser.add_argument("--overs", type=float, required=True, help="Overs bowled (e.g. 5.2)")
    parser.add_argument("--target", type=int, default=None, help="Target score (if chasing)")
    
    # Optional rolling stats with reasonable defaults if not provided
    parser.add_argument("--runs_last_12", type=int, default=None)
    parser.add_argument("--runs_last_18", type=int, default=None)
    parser.add_argument("--wickets_last_12", type=int, default=0)
    parser.add_argument("--boundary_pct", type=float, default=0.16) # ~16% is average
    
    args = parser.parse_args()
    
    # Load resources
    try:
        model = joblib.load("models/t20i_champion_v2/champion_model.joblib")
        team_ratings = load_team_ratings()
        calculator = ResourceFeatureCalculator()
    except Exception as e:
        print(f"Error loading resources: {e}")
        return

    # Derived inputs
    balls_bowled = int(args.overs) * 6 + int((args.overs % 1) * 10)
    overs_val = balls_bowled / 6.0
    overs_remaining = 20.0 - overs_val
    
    # Defaults for rolling stats if not provided
    # Assume current run rate for recent overs if unknown
    crr = args.score / overs_val if overs_val > 0 else 0
    if args.runs_last_12 is None:
        args.runs_last_12 = int(crr * 2) # 2 overs
    if args.runs_last_18 is None:
        args.runs_last_18 = int(crr * 3) # 3 overs

    # Team Strength
    bat_rating = team_ratings.get(args.batting, 0.5)
    bowl_rating = team_ratings.get(args.bowling, 0.5)
    team_strength_diff = bat_rating - bowl_rating

    # Calculator Features
    innings = 2 if args.target else 1
    target = args.target if args.target else 160
    
    resource_pct = calculator.calculate_resource_percentage(overs_remaining, args.wickets)
    
    projected_score = calculator.calculate_expected_score(
        args.score, overs_val, args.wickets
    )
    
    score_vs_par = args.score - (160 * (1 - resource_pct/100))
    
    # RRR
    if args.target:
        runs_needed = args.target - args.score
        balls_rem = 120 - balls_bowled
        if balls_rem > 0:
            rrr = runs_needed / (balls_rem / 6.0)
        else:
            rrr = 99.0
        run_rate_diff = crr - rrr
    else:
        rrr = 0
        run_rate_diff = crr - 8.0
        
    resource_win_prob = calculator.calculate_resource_win_probability(
        innings=innings,
        expected_final_score=projected_score,
        target_runs=target,
        resource_pct=resource_pct,
        current_run_rate=crr,
        required_run_rate=rrr,
        current_score=args.score
    )
    
    pressure_index = calculator.calculate_pressure_index(
        innings=innings,
        current_score=args.score,
        overs_bowled=overs_val,
        wickets_lost=args.wickets,
        target_runs=target,
        current_run_rate=crr
    )

    # Construct Feature Dict (matching trainer.py DEFAULT_FEATURES)
    features = {
        'expected_final_score': projected_score,
        'resource_win_prob': resource_win_prob,
        'score_vs_par': score_vs_par,
        'dls_pressure_index': pressure_index,
        'projected_vs_venue_avg': projected_score - 160,
        'projected_score': projected_score,
        'is_powerplay': 1 if overs_val < 6 else 0,
        'score_per_wicket': args.score / (args.wickets + 1),
        'run_rate_diff': run_rate_diff,
        'required_run_rate': rrr,
        'chase_difficulty': rrr * (args.wickets + 1) if args.target else 0,
        'wickets_times_balls': args.wickets * balls_bowled,
        'pressure_index': pressure_index,
        'team_strength_diff': team_strength_diff,
        'rrr_times_wickets': rrr * args.wickets,
        'overs_remaining': overs_remaining,
        'batting_team_win_rate': bat_rating,
        'bowling_team_win_rate': bowl_rating,
        'batting_team_situation_wr': bat_rating,
        'situation_advantage': bat_rating - bowl_rating,
        'boundary_pct_last_18': args.boundary_pct,
        'bowling_team_situation_wr': bowl_rating,
        'runs_last_12': args.runs_last_12,
        'runs_last_18': args.runs_last_18,
        'wickets_last_12': args.wickets_last_12
    }

    # Create DataFrame
    df = pd.DataFrame([features])
    
    # Ensure columns match model
    if hasattr(model, "selected_features_") and model.selected_features_ is not None:
        model_features = model.selected_features_
    else:
        # Fallback to keys if not stored
        model_features = list(features.keys())
        
    # Add missing columns with 0
    for f in model_features:
        if f not in df.columns:
            df[f] = 0
            
    # Reorder
    df = df[model_features]
    
    # Predict
    prob = model.predict_proba(df)[0][1]
    
    print(f"WIN_PROBABILITY:{prob:.4f}")
    print(f"PROJECTED:{int(projected_score)}")
    print(f"RESOURCE_PROB:{resource_win_prob:.4f}")

if __name__ == "__main__":
    main()
