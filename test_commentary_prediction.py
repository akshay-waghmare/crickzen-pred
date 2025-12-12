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

def test_prediction():
    print("--- Setting up Prediction Test ---")
    
    # 1. Setup Mapper
    feature_store = MockFeatureStore()
    global_stats = {
        'global_batting_avg': 25.0,
        'global_batting_sr': 135.0,
        'global_bowling_econ': 8.0,
        'global_bowling_sr': 20.0
    }
    mapper = RealTimeFeatureMapper(feature_store, global_stats)
    
    # 2. Create Scraped Data Dictionary from Commentary
    # "end of over 2", "IND: 19/2", "Target: 214"
    scraped_data = {
        'match_id': 'test_match_ind_sa',
        'venue': 'Test Venue',
        'batting_team': 'India',
        'bowling_team': 'South Africa',
        'innings_num': 2,
        'over_number': 2, # Start of 3rd over
        'ball_number': 0,
        'total_score': 19,
        'total_wickets': 2,
        'target_score': 214,
        'batsman1_name': 'Axar Patel',
        'batsman2_name': 'Suryakumar Yadav',
        'bowler1_name': 'Unknown Bowler',
        'current_run_rate': 9.5,
        'required_run_rate': 10.83,
        'projected_score': 190 # Rough guess based on CRR
    }
    
    print(f"Input State: {scraped_data['batting_team']} {scraped_data['total_score']}/{scraped_data['total_wickets']} ({scraped_data['over_number']}.{scraped_data['ball_number']}) chasing {scraped_data['target_score']}")
    
    # 3. Create Feature DataFrame
    print("\nGenerating features...")
    df_features = mapper.create_feature_dataframe(scraped_data)
    
    # Print key features
    print("\n--- Key Calculated Features ---")
    cols_to_show = [
        'resource_pct', 'max_gettable', 'resource_win_prob', 
        'pressure_index', 'run_rate_diff', 'required_run_rate'
    ]
    # Note: max_gettable is internal to calculator, not in df usually, but resource_win_prob is.
    for col in cols_to_show:
        if col in df_features.columns:
            print(f"{col}: {df_features[col].iloc[0]:.4f}")
            
    # 4. Load Model and Predict
    print("\n--- Running Model Prediction ---")
    try:
        model_path = "models/t20i_champion_v2/champion_model.joblib"
        model = joblib.load(model_path)
        
        # Align columns
        if hasattr(model, 'feature_names_in_'):
            required_cols = model.feature_names_in_
            # Add missing columns with 0
            for col in required_cols:
                if col not in df_features.columns:
                    df_features[col] = 0.0
            # Select and reorder
            df_features = df_features[required_cols]
            
        prob = model.predict_proba(df_features)[0][1]
        print(f"\n🏆 PREDICTED WIN PROBABILITY (India): {prob*100:.2f}%")
        
    except Exception as e:
        print(f"Model prediction failed: {e}")
        # Print available columns for debugging
        # print("Available columns:", df_features.columns.tolist())

if __name__ == "__main__":
    test_prediction()
