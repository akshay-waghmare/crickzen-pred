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
    print("--- Running Commentary Sequence Prediction (Part 2) ---")
    print("Match: India vs South Africa (2nd T20I)")
    print("Innings: 1 (South Africa Batting)")
    
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
    balls = [
        # Over 9 (Axar)
        (9, 1, 6, 0, "Quinton de Kock", "Aiden Markram", "Axar Patel"),
        (9, 2, 2, 0, "Quinton de Kock", "Aiden Markram", "Axar Patel"),
        (9, 3, 1, 0, "Quinton de Kock", "Aiden Markram", "Axar Patel"),
        (9, 4, 0, 0, "Aiden Markram", "Quinton de Kock", "Axar Patel"),
        (9, 5, 1, 0, "Aiden Markram", "Quinton de Kock", "Axar Patel"),
        (9, 6, 1, 0, "Quinton de Kock", "Aiden Markram", "Axar Patel"),

        # Over 10 (Arshdeep)
        (10, 1, 6, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"),
        (10, 2, 1, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"), # Wide 1
        (10, 2, 1, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"), # Wide 2
        (10, 2, 1, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"), # Wide 3
        (10, 2, 0, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"), # Legal ball
        (10, 3, 1, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"), # Wide 1
        (10, 3, 1, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"), # Wide 2
        (10, 3, 1, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"), # Wide 3
        (10, 3, 1, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"), # Wide 4
        (10, 3, 1, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"), # Legal ball
        (10, 4, 2, 0, "Aiden Markram", "Quinton de Kock", "Arshdeep Singh"),
        (10, 5, 1, 0, "Aiden Markram", "Quinton de Kock", "Arshdeep Singh"),
        (10, 6, 1, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"), # Wide
        (10, 6, 1, 0, "Quinton de Kock", "Aiden Markram", "Arshdeep Singh"), # Legal ball

        # Over 11 (Varun)
        (11, 1, 1, 0, "Quinton de Kock", "Aiden Markram", "Varun Chakravarthy"),
        (11, 2, 6, 0, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"),
        (11, 3, 6, 0, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"),
        (11, 4, 0, 0, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"),
        (11, 5, 0, 0, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"),
        (11, 6, 0, 1, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"), # WICKET

        # Over 12 (Dube)
        (12, 1, 1, 0, "Quinton de Kock", "Dewald Brevis", "Shivam Dube"),
        (12, 2, 1, 0, "Dewald Brevis", "Quinton de Kock", "Shivam Dube"), # Wide
        (12, 2, 1, 0, "Dewald Brevis", "Quinton de Kock", "Shivam Dube"), # Legal
        (12, 3, 1, 0, "Quinton de Kock", "Dewald Brevis", "Shivam Dube"),
        (12, 4, 4, 0, "Dewald Brevis", "Quinton de Kock", "Shivam Dube"),
        (12, 5, 0, 0, "Dewald Brevis", "Quinton de Kock", "Shivam Dube"),
        (12, 6, 1, 0, "Dewald Brevis", "Quinton de Kock", "Shivam Dube"),

        # Over 13 (Hardik)
        (13, 1, 1, 0, "Dewald Brevis", "Quinton de Kock", "Hardik Pandya"), # Wide
        (13, 1, 1, 0, "Dewald Brevis", "Quinton de Kock", "Hardik Pandya"), # Legal
        (13, 2, 4, 0, "Quinton de Kock", "Dewald Brevis", "Hardik Pandya"),
        (13, 3, 2, 0, "Quinton de Kock", "Dewald Brevis", "Hardik Pandya"),
        (13, 4, 6, 0, "Quinton de Kock", "Dewald Brevis", "Hardik Pandya"),
        (13, 5, 2, 0, "Quinton de Kock", "Dewald Brevis", "Hardik Pandya"),
        (13, 6, 1, 0, "Quinton de Kock", "Dewald Brevis", "Hardik Pandya"),

        # Over 14 (Dube)
        (14, 1, 1, 0, "Quinton de Kock", "Dewald Brevis", "Shivam Dube"),
        (14, 2, 1, 0, "Dewald Brevis", "Quinton de Kock", "Shivam Dube"),
        (14, 3, 1, 0, "Quinton de Kock", "Dewald Brevis", "Shivam Dube"),
        (14, 4, 0, 0, "Dewald Brevis", "Quinton de Kock", "Shivam Dube"),
        (14, 5, 6, 0, "Dewald Brevis", "Quinton de Kock", "Shivam Dube"),
        (14, 6, 0, 0, "Dewald Brevis", "Quinton de Kock", "Shivam Dube"),

        # Over 15 (Varun)
        (15, 1, 0, 1, "Quinton de Kock", "Dewald Brevis", "Varun Chakravarthy"), # WICKET (Run Out)
        (15, 2, 0, 0, "Donovan Ferreira", "Dewald Brevis", "Varun Chakravarthy"),
        (15, 3, 0, 0, "Donovan Ferreira", "Dewald Brevis", "Varun Chakravarthy"),
        (15, 4, 0, 0, "Donovan Ferreira", "Dewald Brevis", "Varun Chakravarthy"),
        (15, 5, 0, 0, "Donovan Ferreira", "Dewald Brevis", "Varun Chakravarthy"),
        (15, 6, 4, 0, "Donovan Ferreira", "Dewald Brevis", "Varun Chakravarthy"),

        # Over 16 (Axar)
        (16, 1, 0, 1, "Dewald Brevis", "Donovan Ferreira", "Axar Patel"), # WICKET
        (16, 2, 1, 0, "David Miller", "Donovan Ferreira", "Axar Patel"),
        (16, 3, 1, 0, "Donovan Ferreira", "David Miller", "Axar Patel"),
        (16, 4, 0, 0, "David Miller", "Donovan Ferreira", "Axar Patel"),
        (16, 5, 1, 0, "David Miller", "Donovan Ferreira", "Axar Patel"),
        (16, 6, 1, 0, "Donovan Ferreira", "David Miller", "Axar Patel"),

        # Over 17 (Bumrah)
        (17, 1, 1, 0, "Donovan Ferreira", "David Miller", "Jasprit Bumrah"),
        (17, 2, 4, 0, "David Miller", "Donovan Ferreira", "Jasprit Bumrah"),
        (17, 3, 4, 0, "David Miller", "Donovan Ferreira", "Jasprit Bumrah"), # Leg byes
        (17, 4, 2, 0, "David Miller", "Donovan Ferreira", "Jasprit Bumrah"),
        (17, 5, 4, 0, "David Miller", "Donovan Ferreira", "Jasprit Bumrah"),
        (17, 6, 0, 0, "David Miller", "Donovan Ferreira", "Jasprit Bumrah"),

        # Over 18 (Arshdeep)
        (18, 1, 6, 0, "Donovan Ferreira", "David Miller", "Arshdeep Singh"),
        (18, 2, 0, 0, "Donovan Ferreira", "David Miller", "Arshdeep Singh"),
        (18, 3, 1, 0, "Donovan Ferreira", "David Miller", "Arshdeep Singh"), # Wide
        (18, 3, 1, 0, "Donovan Ferreira", "David Miller", "Arshdeep Singh"), # Wide
        (18, 3, 1, 0, "Donovan Ferreira", "David Miller", "Arshdeep Singh"), # Legal
        (18, 4, 6, 0, "David Miller", "Donovan Ferreira", "Arshdeep Singh"),
        (18, 5, 0, 0, "David Miller", "Donovan Ferreira", "Arshdeep Singh"),
        (18, 6, 1, 0, "David Miller", "Donovan Ferreira", "Arshdeep Singh"),

        # Over 19 (Bumrah)
        (19, 1, 1, 0, "David Miller", "Donovan Ferreira", "Jasprit Bumrah"),
        (19, 2, 6, 0, "Donovan Ferreira", "David Miller", "Jasprit Bumrah"),
        (19, 3, 2, 0, "Donovan Ferreira", "David Miller", "Jasprit Bumrah"),
        (19, 4, 6, 0, "Donovan Ferreira", "David Miller", "Jasprit Bumrah"),
        (19, 5, 2, 0, "Donovan Ferreira", "David Miller", "Jasprit Bumrah"),
        (19, 6, 1, 0, "Donovan Ferreira", "David Miller", "Jasprit Bumrah"), # Bye
    ]

    current_score = 79
    current_wickets = 1

    print(f"\n{'Over':<6} {'Ball':<6} {'Event':<10} {'Score':<10} {'Proj':<8} {'Win Prob (SA)':<10}")
    print("-" * 60)

    for over, ball, runs, is_wicket, bat1, bat2, bowler in balls:
        current_score += runs
        current_wickets += is_wicket
        
        # Construct scraped data dict
        scraped_data = {
            'match_id': 'test_match',
            'venue': 'Test Venue',
            'batting_team': 'South Africa',
            'bowling_team': 'India',
            'innings_num': 1,
            'over_number': over,
            'ball_number': ball,
            'total_score': current_score,
            'total_wickets': current_wickets,
            'target_score': None,
            'batsman1_name': bat1,
            'batsman2_name': bat2,
            'bowler1_name': bowler,
            # Approximate CRR
            'current_run_rate': current_score / (over + ball/6),
            'required_run_rate': 0.0,
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
        # Model predicts probability for Batting Team (SA)
        prob = model.predict_proba(df_features)[0][1]
        
        # Format event string
        event = f"{runs} runs"
        if is_wicket: event = "WICKET"
        
        print(f"{over}.{ball:<4} {event:<10} {current_score}/{current_wickets:<8} {scraped_data['projected_score']:.0f}     {prob*100:.1f}%")

if __name__ == "__main__":
    run_sequence()
