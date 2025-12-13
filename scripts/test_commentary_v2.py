import pandas as pd
import numpy as np
import joblib
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    print("Testing model on commentary scenarios for IND vs SA (Chase)")
    
    # Load model
    model_path = "models/t20i_champion_v2/champion_model.joblib"
    model = joblib.load(model_path)
    print(f"Loaded model from {model_path}")
    
    target = 214
    
    # Scenarios from commentary
    scenarios = [
        {'over': 0.1, 'score': 2, 'wickets': 0, 'desc': "0.1: 2/0"},
        {'over': 0.2, 'score': 2, 'wickets': 0, 'desc': "0.2: 2/0"},
        {'over': 0.3, 'score': 8, 'wickets': 0, 'desc': "0.3: 8/0"},
        {'over': 0.4, 'score': 9, 'wickets': 0, 'desc': "0.4: 9/0"},
        {'over': 0.5, 'score': 9, 'wickets': 1, 'desc': "0.5: 9/1 (W)"},
        {'over': 0.6, 'score': 9, 'wickets': 1, 'desc': "0.6: 9/1"},
        {'over': 1.1, 'score': 15, 'wickets': 1, 'desc': "1.1: 15/1"},
        {'over': 1.2, 'score': 16, 'wickets': 1, 'desc': "1.2: 16/1"},
        {'over': 1.3, 'score': 16, 'wickets': 1, 'desc': "1.3: 16/1"},
        {'over': 1.4, 'score': 17, 'wickets': 1, 'desc': "1.4: 17/1"},
        {'over': 1.5, 'score': 19, 'wickets': 1, 'desc': "1.5: 19/1"},
        {'over': 1.6, 'score': 19, 'wickets': 2, 'desc': "1.6: 19/2 (W)"},
        {'over': 2.1, 'score': 19, 'wickets': 2, 'desc': "2.1: 19/2"},
        {'over': 2.2, 'score': 19, 'wickets': 2, 'desc': "2.2: 19/2"},
        {'over': 2.3, 'score': 19, 'wickets': 2, 'desc': "2.3: 19/2"},
        {'over': 2.4, 'score': 21, 'wickets': 2, 'desc': "2.4: 21/2"},
        {'over': 2.5, 'score': 21, 'wickets': 2, 'desc': "2.5: 21/2"},
        {'over': 2.6, 'score': 25, 'wickets': 2, 'desc': "2.6: 25/2"},
    ]
    
    print("\nProbability Progression (IND Win %):")
    print("-" * 60)
    print(f"{'State':<15} | {'Win Prob':<10} | {'Proj':<5} | {'ResProb':<8}")
    print("-" * 60)
    
    for s in scenarios:
        # Feature approximation
        overs = float(s['over'])
        balls = int(overs) * 6 + int((overs % 1) * 10)
        overs_val = balls / 6.0
        
        score = s['score']
        wickets = s['wickets']
        
        if overs_val > 0:
            crr = score / overs_val
        else:
            crr = 0
            
        # Simple projection (Current Rate * 20)
        projected = crr * 20
        
        # Par score approx (Piecewise linear from test_commentary.py)
        if overs_val <= 6:
            par_score = overs_val * 8.5
        elif overs_val <= 15:
            par_score = (6 * 8.5) + ((overs_val - 6) * 7.5)
        else:
            par_score = (6 * 8.5) + (9 * 7.5) + ((overs_val - 15) * 10.0)
            
        score_vs_par = score - par_score
        
        # Chase specifics
        runs_needed = target - score
        balls_rem = 120 - balls
        if balls_rem > 0:
            rrr = runs_needed / (balls_rem / 6.0)
        else:
            rrr = 99.0
            
        run_rate_diff = crr - rrr
        
        # Resources (Heuristic adapted for chase/strong team)
        # India is strong (0.67 win rate vs 0.53)
        base_prob = 0.60 
        
        # Wickets hurt A LOT in a big chase
        wicket_factor = 1 - (wickets * 0.15) 
        
        # RRR pressure
        rrr_pressure = 1.0
        if rrr > 10:
            rrr_pressure = 1.0 - ((rrr - 10) * 0.05) # Drops 5% for every run above 10 RPO
            
        resource_win_prob = base_prob * wicket_factor * rrr_pressure
        resource_win_prob = max(0.01, min(0.99, resource_win_prob))
        
        data = {
            'expected_final_score': projected, 
            'resource_win_prob': resource_win_prob,
            'score_vs_par': score_vs_par,
            'dls_pressure_index': rrr / 8.0, # Simple pressure 
            'projected_vs_venue_avg': projected - 170, 
            'projected_score': projected,
            'is_powerplay': 1 if overs_val <= 6 else 0,
            'score_per_wicket': score / max(1, wickets),
            'run_rate_diff': run_rate_diff, 
            'required_run_rate': rrr, 
            'chase_difficulty': rrr * (wickets + 1), 
            'wickets_times_balls': wickets * balls,
            'pressure_index': rrr / 8.0, 
            'team_strength_diff': 0.138, # IND stronger
            'rrr_times_wickets': rrr * wickets,
            'overs_remaining': 20.0 - overs_val,
            'batting_team_win_rate': 0.6707, # IND
            'bowling_team_win_rate': 0.5327, # SA
            'batting_team_situation_wr': 0.6707,
            'situation_advantage': 0.138,
            'boundary_pct_last_18': 0.16, # Default
            'bowling_team_situation_wr': 0.5327,
            'runs_last_12': int(crr*2),
            'runs_last_18': int(crr*3),
            'wickets_last_12': 0,
        }
        
        # Create DataFrame with correct feature order
        features = model.selected_features_
        X = pd.DataFrame([data])
        
        # Ensure all features exist
        for f in features:
            if f not in X.columns:
                X[f] = 0.0
                
        X = X[features]
        
        # Predict
        prob = model.predict_proba(X)[0, 1]
        print(f"{s['desc']:<15} | {prob:.2%}    | {int(projected):<5} | {resource_win_prob:.2%}")

if __name__ == "__main__":
    main()
