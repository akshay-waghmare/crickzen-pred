import pandas as pd
import joblib
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bbl_pipeline.features.calculator import ResourceFeatureCalculator

def get_prediction(model, calculator, team_ratings, batting, bowling, score, wickets, overs, target):
    # Derived inputs
    balls_bowled = int(overs) * 6 + int((overs % 1) * 10)
    overs_val = balls_bowled / 6.0
    overs_remaining = 20.0 - overs_val
    
    # Defaults for rolling stats
    crr = score / overs_val if overs_val > 0 else 0
    runs_last_12 = int(crr * 2)
    runs_last_18 = int(crr * 3)
    wickets_last_12 = 0 # Simplified

    # Team Strength
    bat_rating = team_ratings.get(batting, 0.5)
    bowl_rating = team_ratings.get(bowling, 0.5)
    team_strength_diff = bat_rating - bowl_rating

    # Calculator Features
    resource_pct = calculator.calculate_resource_percentage(overs_remaining, wickets)
    
    projected_score = calculator.calculate_expected_score(
        score, overs_val, wickets
    )
    
    score_vs_par = score - (160 * (1 - resource_pct/100))
    
    # RRR
    if target:
        runs_needed = target - score
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
        innings=2 if target else 1,
        expected_final_score=projected_score,
        target_runs=target if target else 160,
        resource_pct=resource_pct,
        current_run_rate=crr,
        required_run_rate=rrr,
        current_score=score
    )
    
    pressure_index = calculator.calculate_pressure_index(
        innings=2 if target else 1,
        current_score=score,
        overs_bowled=overs_val,
        wickets_lost=wickets,
        target_runs=target if target else 160,
        current_run_rate=crr
    )

    # Construct Feature Dict
    features = {
        'expected_final_score': projected_score,
        'resource_win_prob': resource_win_prob,
        'score_vs_par': score_vs_par,
        'dls_pressure_index': pressure_index,
        'projected_vs_venue_avg': projected_score - 160,
        'projected_score': projected_score,
        'is_powerplay': 1 if overs_val < 6 else 0,
        'score_per_wicket': score / (wickets + 1),
        'run_rate_diff': run_rate_diff,
        'required_run_rate': rrr,
        'chase_difficulty': rrr * (wickets + 1) if target else 0,
        'wickets_times_balls': wickets * balls_bowled,
        'pressure_index': pressure_index,
        'team_strength_diff': team_strength_diff,
        'rrr_times_wickets': rrr * wickets,
        'overs_remaining': overs_remaining,
        'batting_team_win_rate': bat_rating,
        'bowling_team_win_rate': bowl_rating,
        'batting_team_situation_wr': bat_rating,
        'situation_advantage': bat_rating - bowl_rating,
        'boundary_pct_last_18': 0.16,
        'bowling_team_situation_wr': bowl_rating,
        'runs_last_12': runs_last_12,
        'runs_last_18': runs_last_18,
        'wickets_last_12': wickets_last_12
    }

    # Create DataFrame
    df = pd.DataFrame([features])
    
    # Ensure columns match model
    if hasattr(model, "selected_features_") and model.selected_features_ is not None:
        model_features = model.selected_features_
    else:
        model_features = list(features.keys())
        
    for f in model_features:
        if f not in df.columns:
            df[f] = 0
            
    df = df[model_features]
    
    # Predict
    prob = model.predict_proba(df)[0][1]
    return prob, projected_score, resource_win_prob

def main():
    # Load resources
    model = joblib.load("models/t20i_champion_v2/champion_model.joblib")
    
    team_ratings_path = Path("data/t20i_feature_store_v1/team_ratings.parquet")
    if team_ratings_path.exists():
        tr_df = pd.read_parquet(team_ratings_path)
        team_ratings = dict(zip(tr_df['team'], tr_df['win_rate']))
    else:
        team_ratings = {}
        
    calculator = ResourceFeatureCalculator()
    
    # Match Setup
    batting = "India"
    bowling = "South Africa"
    target = 214
    
    # Events extracted from commentary
    # (Overs, Score, Wickets, Event Description)
    events = [
        (0.1, 2, 0, "2 runs"),
        (0.2, 2, 0, "no run"),
        (0.3, 8, 0, "SIX runs"),
        (0.4, 9, 0, "1 run"),
        (0.5, 9, 1, "OUT (Gill)"),
        (0.6, 9, 1, "no run"),
        (1.1, 15, 1, "SIX runs"),
        (1.2, 16, 1, "1 bye"),
        (1.3, 16, 1, "no run"),
        (1.4, 17, 1, "1 run"),
        (1.5, 19, 1, "2 runs"),
        (1.6, 19, 2, "OUT (Abhishek)"),
        (2.1, 19, 2, "no run"),
        (2.2, 19, 2, "no run"),
        (2.3, 19, 2, "no run"),
        (2.4, 21, 2, "2 runs"),
        (2.5, 21, 2, "no run"),
        (2.6, 25, 2, "FOUR runs")
    ]
    
    print(f"### Match Prediction: {batting} vs {bowling} (Target: {target})")
    print("| Over | Score | Event | Win Prob (IND) | Projected | Resource Prob |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for overs, score, wickets, event in events:
        prob, proj, res_prob = get_prediction(
            model, calculator, team_ratings, batting, bowling, score, wickets, overs, target
        )
        print(f"| {overs} | {score}/{wickets} | {event} | **{prob:.1%}** | {int(proj)} | {res_prob:.1%} |")

if __name__ == "__main__":
    main()
