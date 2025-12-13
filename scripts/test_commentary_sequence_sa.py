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
    print("Innings: 1 (South Africa Batting)")
    
    # Setup
    feature_store = MockFeatureStore()
    global_stats = {
        'global_batting_avg': 25.0, 'global_batting_sr': 135.0,
        'global_bowling_econ': 8.0, 'global_bowling_sr': 20.0
    }
    mapper = RealTimeFeatureMapper(feature_store, global_stats)
    
    try:
        model = joblib.load("models/t20i_champion_v3/champion_model.joblib")
    except:
        print("Error: Could not load model. Make sure models/t20i_champion_v3/champion_model.joblib exists.")
        return

    importance_df = None
    top_features_ranked = []
    if hasattr(model, "get_feature_importance"):
        try:
            importance_df = model.get_feature_importance().sort_values("importance", ascending=False)
            top_features_ranked = importance_df["feature"].head(8).tolist()
        except Exception:
            importance_df = None
            top_features_ranked = []

    # Define the sequence of balls
    # (Over, Ball, Runs, Wicket, Batsman1, Batsman2, Bowler)
    # Note: Total score and wickets will be calculated cumulatively
    balls = [
        # Over 0 (Arshdeep)
        (0, 1, 0, 0, "Quinton de Kock", "Reeza Hendricks", "Arshdeep Singh"),
        (0, 2, 0, 0, "Quinton de Kock", "Reeza Hendricks", "Arshdeep Singh"),
        (0, 3, 0, 0, "Quinton de Kock", "Reeza Hendricks", "Arshdeep Singh"),
        (0, 4, 2, 0, "Quinton de Kock", "Reeza Hendricks", "Arshdeep Singh"),
        (0, 5, 6, 0, "Quinton de Kock", "Reeza Hendricks", "Arshdeep Singh"),
        (0, 6, 0, 0, "Quinton de Kock", "Reeza Hendricks", "Arshdeep Singh"),
        
        # Over 1 (Bumrah)
        (1, 1, 0, 0, "Reeza Hendricks", "Quinton de Kock", "Jasprit Bumrah"),
        (1, 2, 0, 0, "Reeza Hendricks", "Quinton de Kock", "Jasprit Bumrah"),
        (1, 3, 1, 0, "Reeza Hendricks", "Quinton de Kock", "Jasprit Bumrah"), # Leg bye
        (1, 4, 0, 0, "Quinton de Kock", "Reeza Hendricks", "Jasprit Bumrah"),
        (1, 5, 0, 0, "Quinton de Kock", "Reeza Hendricks", "Jasprit Bumrah"),
        (1, 6, 1, 0, "Quinton de Kock", "Reeza Hendricks", "Jasprit Bumrah"),
        
        # Over 2 (Arshdeep)
        (2, 1, 4, 0, "Quinton de Kock", "Reeza Hendricks", "Arshdeep Singh"),
        (2, 2, 0, 0, "Quinton de Kock", "Reeza Hendricks", "Arshdeep Singh"),
        (2, 3, 6, 0, "Quinton de Kock", "Reeza Hendricks", "Arshdeep Singh"),
        (2, 4, 1, 0, "Quinton de Kock", "Reeza Hendricks", "Arshdeep Singh"),
        (2, 5, 0, 0, "Reeza Hendricks", "Quinton de Kock", "Arshdeep Singh"),
        (2, 6, 1, 0, "Reeza Hendricks", "Quinton de Kock", "Arshdeep Singh"),
        
        # Over 3 (Bumrah)
        (3, 1, 0, 0, "Reeza Hendricks", "Quinton de Kock", "Jasprit Bumrah"),
        (3, 2, 0, 0, "Reeza Hendricks", "Quinton de Kock", "Jasprit Bumrah"),
        (3, 3, 6, 0, "Reeza Hendricks", "Quinton de Kock", "Jasprit Bumrah"),
        (3, 4, 2, 0, "Reeza Hendricks", "Quinton de Kock", "Jasprit Bumrah"), # 2 Wides
        (3, 4, 1, 0, "Quinton de Kock", "Reeza Hendricks", "Jasprit Bumrah"), # Ball 3.4 re-bowled
        (3, 5, 1, 0, "Reeza Hendricks", "Quinton de Kock", "Jasprit Bumrah"),
        (3, 6, 6, 0, "Quinton de Kock", "Reeza Hendricks", "Jasprit Bumrah"),
        
        # Over 4 (Varun)
        (4, 1, 0, 1, "Reeza Hendricks", "Quinton de Kock", "Varun Chakravarthy"), # WICKET
        (4, 2, 0, 0, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"),
        (4, 3, 0, 0, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"),
        (4, 4, 1, 0, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"),
        (4, 5, 1, 0, "Quinton de Kock", "Aiden Markram", "Varun Chakravarthy"),
        (4, 6, 1, 0, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"),
        
        # Over 5 (Axar)
        (5, 1, 0, 0, "Aiden Markram", "Quinton de Kock", "Axar Patel"),
        (5, 2, 0, 0, "Aiden Markram", "Quinton de Kock", "Axar Patel"),
        (5, 3, 4, 0, "Aiden Markram", "Quinton de Kock", "Axar Patel"),
        (5, 4, 1, 0, "Aiden Markram", "Quinton de Kock", "Axar Patel"),
        (5, 5, 6, 0, "Quinton de Kock", "Aiden Markram", "Axar Patel"),
        (5, 6, 1, 0, "Quinton de Kock", "Aiden Markram", "Axar Patel"), # Wide
        (5, 6, 0, 0, "Quinton de Kock", "Aiden Markram", "Axar Patel"), # Re-bowled
        
        # Over 6 (Hardik)
        (6, 1, 0, 0, "Aiden Markram", "Quinton de Kock", "Hardik Pandya"),
        (6, 2, 1, 0, "Aiden Markram", "Quinton de Kock", "Hardik Pandya"),
        (6, 3, 0, 0, "Quinton de Kock", "Aiden Markram", "Hardik Pandya"),
        (6, 4, 4, 0, "Quinton de Kock", "Aiden Markram", "Hardik Pandya"),
        (6, 5, 2, 0, "Quinton de Kock", "Aiden Markram", "Hardik Pandya"),
        (6, 6, 1, 0, "Quinton de Kock", "Aiden Markram", "Hardik Pandya"), # Wide
        (6, 6, 0, 0, "Quinton de Kock", "Aiden Markram", "Hardik Pandya"), # Re-bowled
        
        # Over 7 (Varun)
        (7, 1, 1, 0, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"),
        (7, 2, 2, 0, "Quinton de Kock", "Aiden Markram", "Varun Chakravarthy"),
        (7, 3, 1, 0, "Quinton de Kock", "Aiden Markram", "Varun Chakravarthy"),
        (7, 4, 0, 0, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"),
        (7, 5, 1, 0, "Aiden Markram", "Quinton de Kock", "Varun Chakravarthy"),
        (7, 6, 4, 0, "Quinton de Kock", "Aiden Markram", "Varun Chakravarthy"),
        
        # Over 8 (Hardik)
        (8, 1, 0, 0, "Aiden Markram", "Quinton de Kock", "Hardik Pandya"),
        (8, 2, 1, 0, "Aiden Markram", "Quinton de Kock", "Hardik Pandya"),
        (8, 3, 4, 0, "Quinton de Kock", "Aiden Markram", "Hardik Pandya"),
        (8, 4, 1, 0, "Quinton de Kock", "Aiden Markram", "Hardik Pandya"),
        (8, 5, 1, 0, "Aiden Markram", "Quinton de Kock", "Hardik Pandya"), # Wide
        (8, 5, 0, 0, "Aiden Markram", "Quinton de Kock", "Hardik Pandya"), # Re-bowled
        (8, 6, 2, 0, "Aiden Markram", "Quinton de Kock", "Hardik Pandya"),
    ]

    current_score = 0
    current_wickets = 0

    feature_cols_to_show = None
    prev_prob = None

    print(
        f"\n{'Ov.B':<6} {'Event':<8} {'Score':<8} {'Proj(i)':<7} {'Proj(f)':<7} {'ExpFinal':<8} {'P(SA)':<7} {'Δpp':<6} {'Top features (value)':<0}"
    )
    print("-" * 120)

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

        # Generate features (keep a copy before alignment so we can inspect feature values)
        df_features_full = mapper.create_feature_dataframe(scraped_data)

        if feature_cols_to_show is None:
            ranked_present = [c for c in top_features_ranked if c in df_features_full.columns]
            if ranked_present:
                feature_cols_to_show = ranked_present[:5]
            else:
                # Fallbacks if importance names don't match inference-time columns
                fallback = [
                    "resource_team_adjusted",
                    "score_adjusted_by_team",
                    "resource_win_prob",
                    "resource_win_probability",
                    "score_vs_par",
                    "dls_pressure_index",
                    "projected_adjusted",
                    "projected_score",
                    "expected_final_score",
                    "required_run_rate",
                ]
                feature_cols_to_show = [c for c in fallback if c in df_features_full.columns][:5]

        df_features = df_features_full
        
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
        
        proj_in = float(scraped_data["projected_score"])
        proj_feat = None
        if "projected_score" in df_features_full.columns:
            try:
                proj_feat = float(df_features_full["projected_score"].iloc[0])
            except Exception:
                proj_feat = None

        exp_final = None
        if "expected_final_score" in df_features_full.columns:
            try:
                exp_final = float(df_features_full["expected_final_score"].iloc[0])
            except Exception:
                exp_final = None

        proj_feat_str = f"{proj_feat:.0f}" if proj_feat is not None else "NA"
        exp_final_str = f"{exp_final:.0f}" if exp_final is not None else "NA"

        delta_pp = ""
        if prev_prob is not None:
            delta_pp = f"{(prob - prev_prob) * 100:+.1f}"
        prev_prob = prob

        # Show the top feature values that are actually moving
        parts = []
        for col in (feature_cols_to_show or []):
            try:
                val = float(df_features_full[col].iloc[0])
                parts.append(f"{col}={val:.3f}")
            except Exception:
                parts.append(f"{col}=NA")
        feat_str = " | ".join(parts)

        print(
            f"{over}.{ball:<3} {event:<8} {current_score}/{current_wickets:<6} "
            f"{proj_in:>6.0f}  {proj_feat_str:>6}  {exp_final_str:>7}  {prob*100:>6.1f}% {delta_pp:>6} {feat_str}"
        )

if __name__ == "__main__":
    run_sequence()
