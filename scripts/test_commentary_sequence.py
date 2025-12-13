import pandas as pd
import joblib
import numpy as np
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.bbl_pipeline.inference.realtime_mapper import RealTimeFeatureMapper
from src.bbl_pipeline.features.store import InMemoryFeatureStore

# Mock Feature Store
class MockFeatureStore:
    def get_player_stats(self, name):
        return {}
    def get_venue_stats(self, name):
        return {'venue_avg_score': 170.0}
    def get_team_stats(self, name):
        if "India" in name:
            return {'win_rate': 0.65, 'rating': 110.0}
        if "South Africa" in name:
            return {'win_rate': 0.55, 'rating': 105.0}
        return {'win_rate': 0.5}

def run_sequence():
    print("--- Running Commentary Sequence Prediction ---")
    print("Match: India vs South Africa (2nd T20I)")
    print("Target: 214")
    
    # Setup
    feature_store = MockFeatureStore()
    global_stats = {
        'global_batting_avg': 25.0, 'global_batting_sr': 135.0,
        'global_bowling_econ': 8.0, 'global_bowling_sr': 20.0
    }
    mapper = RealTimeFeatureMapper(feature_store, global_stats)
    
    try:
        model = joblib.load("models/t20i_champion_v2/champion_model.joblib")
    except:
        print("Error: Could not load model. Make sure models/t20i_champion_v2/champion_model.joblib exists.")
        return

    # Define the sequence of balls
    # (Over, Ball, Runs, Wicket, Batsman1, Batsman2, Bowler)
    # Note: Total score and wickets will be calculated cumulatively
    balls = [
        # Over 0 (Ngidi)
        (0, 1, 2, 0, "Abhishek Sharma", "Shubman Gill", "Lungi Ngidi"),
        (0, 2, 0, 0, "Abhishek Sharma", "Shubman Gill", "Lungi Ngidi"),
        (0, 3, 6, 0, "Abhishek Sharma", "Shubman Gill", "Lungi Ngidi"),
        (0, 4, 1, 0, "Abhishek Sharma", "Shubman Gill", "Lungi Ngidi"),
        (0, 5, 0, 1, "Shubman Gill", "Abhishek Sharma", "Lungi Ngidi"), # WICKET (Gill)
        (0, 6, 0, 0, "Axar Patel", "Abhishek Sharma", "Lungi Ngidi"),
        
        # Over 1 (Jansen)
        (1, 1, 6, 0, "Abhishek Sharma", "Axar Patel", "Marco Jansen"),
        (1, 2, 1, 0, "Abhishek Sharma", "Axar Patel", "Marco Jansen"), # Bye (1 run added to total)
        (1, 3, 0, 0, "Axar Patel", "Abhishek Sharma", "Marco Jansen"),
        (1, 4, 1, 0, "Axar Patel", "Abhishek Sharma", "Marco Jansen"),
        (1, 5, 2, 0, "Abhishek Sharma", "Axar Patel", "Marco Jansen"),
        (1, 6, 0, 1, "Abhishek Sharma", "Axar Patel", "Marco Jansen"), # WICKET (Abhishek)
        
        # Over 2 (Ngidi)
        (2, 1, 0, 0, "Axar Patel", "Suryakumar Yadav", "Lungi Ngidi"),
        (2, 2, 0, 0, "Axar Patel", "Suryakumar Yadav", "Lungi Ngidi"),
        (2, 3, 0, 0, "Axar Patel", "Suryakumar Yadav", "Lungi Ngidi"),
        (2, 4, 2, 0, "Axar Patel", "Suryakumar Yadav", "Lungi Ngidi"),
        (2, 5, 0, 0, "Axar Patel", "Suryakumar Yadav", "Lungi Ngidi"),
        (2, 6, 4, 0, "Axar Patel", "Suryakumar Yadav", "Lungi Ngidi"),
    ]

    current_score = 0
    current_wickets = 0
    target = 214

    print(f"\n{'Over':<6} {'Ball':<6} {'Event':<10} {'Score':<10} {'RRR':<8} {'Win Prob':<10}")
    print("-" * 60)

    for over, ball, runs, is_wicket, bat1, bat2, bowler in balls:
        current_score += runs
        current_wickets += is_wicket
        
        # Construct scraped data dict
        scraped_data = {
            'match_id': 'test_match',
            'venue': 'Test Venue',
            'batting_team': 'India',
            'bowling_team': 'South Africa',
            'innings_num': 2,
            'over_number': over,
            'ball_number': ball,
            'total_score': current_score,
            'total_wickets': current_wickets,
            'target_score': target,
            'batsman1_name': bat1,
            'batsman2_name': bat2,
            'bowler1_name': bowler,
            # Approximate CRR/RRR
            'current_run_rate': current_score / (over + ball/6),
            'required_run_rate': (target - current_score) / ((20 - (over + ball/6))),
            'projected_score': (current_score / (over + ball/6)) * 20
        }

        # Generate features
        df_features = mapper.create_feature_dataframe(scraped_data)
        
        # Align columns for model
        if hasattr(model, 'feature_names_in_'):
            required_cols = model.feature_names_in_
            for col in required_cols:
                if col not in df_features.columns:
                    df_features[col] = 0.0
            df_features = df_features[required_cols]

        # Predict
        prob = model.predict_proba(df_features)[0][1]
        
        # Format event string
        event = f"{runs} runs"
        if is_wicket: event = "WICKET"
        
        print(f"{over}.{ball:<4} {event:<10} {current_score}/{current_wickets:<8} {scraped_data['required_run_rate']:.2f}     {prob*100:.1f}%")

if __name__ == "__main__":
    run_sequence()
