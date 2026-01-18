import joblib
import pandas as pd
import numpy as np

# Load model
model = joblib.load('models/bbl_v9/champion_model.joblib')

# Get feature names from the model
if hasattr(model, 'feature_names'):
    feature_names = model.feature_names
elif hasattr(model, 'xgb') and hasattr(model.xgb, 'feature_names_in_'):
    feature_names = list(model.xgb.feature_names_in_)
else:
    # Hardcoded from training
    feature_names = [
        'batting_team_situation_wr', 'batting_team_win_rate', 'boundary_pct_last_18',
        'bowling_team_situation_wr', 'bowling_team_win_rate', 'chase_difficulty',
        'dls_pressure_index', 'expected_final_score', 'is_powerplay', 'overs_remaining',
        'pressure_index', 'projected_score', 'projected_vs_venue_avg', 'required_run_rate',
        'resource_win_prob', 'rrr_times_wickets', 'run_rate_diff', 'runs_last_12',
        'runs_last_18', 'score_per_wicket', 'score_vs_par', 'situation_advantage',
        'team_strength_diff', 'wickets_last_12', 'wickets_times_balls'
    ]

# Import the actual calculator
from src.bbl_pipeline.features.calculator import ResourceFeatureCalculator

calc = ResourceFeatureCalculator()

# Scenarios for over 19 (estimating based on 202/7 at 19.5)
scenarios = [
    {'over': 18, 'score': 170, 'wickets': 5, 'desc': 'Over 18: 170/5'},
    {'over': 18, 'score': 175, 'wickets': 6, 'desc': 'Over 18: 175/6'},
    {'over': 19, 'score': 185, 'wickets': 6, 'desc': 'Over 19: 185/6'},
    {'over': 19, 'score': 190, 'wickets': 6, 'desc': 'Over 19: 190/6'},
    {'over': 19, 'score': 190, 'wickets': 7, 'desc': 'Over 19: 190/7'},
    {'over': 19, 'score': 195, 'wickets': 7, 'desc': 'Over 19: 195/7'},
    {'over': 19.5, 'score': 202, 'wickets': 7, 'desc': 'Over 19.5: 202/7 (actual end)'},
]

print("=" * 70)
print("PRS Win Probability at Different Points (1st Innings)")
print("Using actual ResourceFeatureCalculator for resource_win_prob")
print("=" * 70)

# Use exact features from live predictor for 19.5 over case to verify
# From the live_state.json history, bat_prob was 0.5768 at 19.5 overs
# Let's understand why - maybe the live predictor uses different feature values

for s in scenarios:
    overs = s['over']
    score = s['score']
    wickets = s['wickets']
    
    # Calculate balls
    if isinstance(overs, float) and overs % 1 != 0:
        balls_in_over = int(round((overs % 1) * 10))
        overs_completed = int(overs)
    else:
        balls_in_over = 0
        overs_completed = int(overs)
    
    balls_bowled = overs_completed * 6 + balls_in_over
    balls_remaining = 120 - balls_bowled
    overs_remaining = balls_remaining / 6
    crr = score / (balls_bowled / 6) if balls_bowled > 0 else 0
    
    # Projected score and venue avg
    projected_score = (score / balls_bowled * 120) if balls_bowled > 0 else 160
    venue_avg = 152.11
    
    # Calculate resource percentage
    resource_pct = calc.calculate_resource_percentage(overs_remaining, wickets)
    
    # Calculate resource_win_prob using actual calculator (like live predictor)
    resource_win_prob = calc.calculate_resource_win_probability(
        innings=1,
        expected_final_score=projected_score,
        target_runs=None,
        resource_pct=resource_pct,
        current_run_rate=crr,
        required_run_rate=0.0,
        current_score=score,
        balls_remaining=balls_remaining,
        wickets_lost=wickets
    )
    
    features = {
        'expected_final_score': projected_score,
        'resource_win_prob': resource_win_prob,  # Using actual calculator!
        'score_vs_par': score - (venue_avg * balls_bowled / 120),
        'dls_pressure_index': (wickets / 10) * (balls_remaining / 120),
        'projected_vs_venue_avg': projected_score - venue_avg,
        'projected_score': projected_score,
        'is_powerplay': 0,
        'score_per_wicket': score / (wickets + 1) if wickets > 0 else score,
        'run_rate_diff': crr - 8.0,  # vs par run rate
        'required_run_rate': 0.0,  # 1st innings
        'chase_difficulty': 0.0,  # 1st innings
        'wickets_times_balls': wickets * balls_remaining,
        'pressure_index': (wickets / 10) * (1 - balls_bowled/120),
        'team_strength_diff': 0.30,  # PRS (70%) - SYT (40%)
        'rrr_times_wickets': 0.0,
        'overs_remaining': overs_remaining,
        'batting_team_win_rate': 0.70,  # PRS
        'bowling_team_win_rate': 0.40,  # SYT
        'batting_team_situation_wr': 0.48,  # PRS bat first WR
        'situation_advantage': 0.48 - 0.52,  # PRS bat_first - SYT bowl_first
        'boundary_pct_last_18': 0.30,
        'bowling_team_situation_wr': 0.52,  # SYT bowl first WR
        'runs_last_12': 12,
        'runs_last_18': 20,
        'wickets_last_12': 1 if wickets >= 6 else 0,
    }
    
    X = pd.DataFrame([features])[feature_names]
    prob = model.predict_proba(X)[0][1]
    
    print(f"{s['desc']:30} -> resource_wp={resource_win_prob:.2%} | Model: PRS={prob*100:.1f}% SYT={(1-prob)*100:.1f}%")

print("=" * 70)
print("\nLive predictor showed PRS: 57.7% at 19.5 overs (202/7)")
print("This is the resource_win_prob value that the model uses.")
