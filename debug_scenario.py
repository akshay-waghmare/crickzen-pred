import pandas as pd
import joblib
import numpy as np
from src.bbl_pipeline.features.calculator import ResourceFeatureCalculator

def test_scenario():
    # 1. Setup the Scenario
    print("--- Scenario Setup ---")
    print("Match: India vs South Africa (2nd T20I)")
    print("Target: 214")
    print("Current State: 19/2 after 2.0 overs")
    print("Batsmen: Axar Patel, SKY")
    print("Bowlers: Ngidi, Jansen")
    
    # State variables
    current_score = 19
    wickets_lost = 2
    overs_bowled = 2.0
    target = 214
    
    # 2. Calculate Features using the NEW Calculator
    calc = ResourceFeatureCalculator()
    
    # Get resource percentage
    overs_remaining = 20.0 - overs_bowled
    resource_pct = calc.calculate_resource_percentage(overs_remaining, wickets_lost)
    
    # Get max gettable (debug)
    max_gettable = (resource_pct / 100.0) * calc.PAR_SCORE_T20 * 1.3
    runs_required = target - current_score
    
    print(f"\n--- Calculator Internals ---")
    print(f"Resources Remaining: {resource_pct:.1f}%")
    print(f"Runs Required: {runs_required}")
    print(f"Max Gettable (Theoretical): {max_gettable:.1f}")
    print(f"Is Impossible? {'YES' if runs_required > max_gettable else 'NO'}")
    
    # Calculate all features
    features = calc.calculate_all_features(
        innings=2,
        over=1, # 0-indexed, so over 1 is the 2nd over (finished)
        ball=6, # Finished over
        current_score=current_score,
        wickets_lost=wickets_lost,
        target_runs=target
    )
    
    print(f"\n--- Feature Values ---")
    print(f"RRR: {features['required_run_rate']:.2f}")
    print(f"Pressure Index: {features['pressure_index']:.3f}")
    print(f"Resource Win Prob (Baseline): {features['resource_win_prob']:.3f}")
    
    # 3. Load Model and Predict
    print(f"\n--- ML Model Prediction ---")
    try:
        model_path = "models/t20i_champion_v2/champion_model.joblib"
        model = joblib.load(model_path)
        
        # Create a single-row DataFrame with all expected features
        # We need to mock the other features (team strengths, venue, etc.) with reasonable defaults
        # or 0s if they are standardized.
        
        # Get feature names from the model
        if hasattr(model, 'feature_names_in_'):
            feature_names = model.feature_names_in_
        else:
            # Fallback if not directly available (e.g. pipeline)
            feature_names = [
                'overs_remaining', 'wickets_remaining', 'runs_required', 'required_run_rate',
                'current_run_rate', 'resource_pct', 'resource_win_prob', 'pressure_index',
                'run_rate_differential', 'is_powerplay', 'is_death_overs',
                'bat_team_rating', 'bowl_team_rating', 'venue_avg_score'
            ]
            
        # Construct input vector
        input_data = {
            'overs_remaining': 18.0,
            'wickets_remaining': 8,
            'runs_required': 195,
            'required_run_rate': 10.83,
            'current_run_rate': 9.5,
            'resource_pct': resource_pct,
            'resource_win_prob': features['resource_win_prob'],
            'pressure_index': features['pressure_index'],
            'run_rate_differential': 9.5 - 10.83,
            'is_powerplay': 1,
            'is_middle_overs': 0,
            'is_death_overs': 0,
            
            # Mock Team Ratings (India Strong, SA Strong)
            'bat_team_rating': 110.0, # Above average
            'bowl_team_rating': 105.0,
            'venue_avg_score': 170.0,
            'toss_winner_is_batting': 0,
            'is_chasing': 1
        }
        
        # Fill missing features with 0
        df_input = pd.DataFrame([input_data])
        for col in feature_names:
            if col not in df_input.columns:
                df_input[col] = 0.0
                
        # Reorder
        df_input = df_input[feature_names]
        
        # Predict
        prob = model.predict_proba(df_input)[0][1]
        print(f"Final Win Probability (India): {prob*100:.1f}%")
        
    except Exception as e:
        print(f"Could not run ML model: {e}")

if __name__ == "__main__":
    test_scenario()
