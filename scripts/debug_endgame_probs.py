import pandas as pd
import numpy as np
import joblib
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

def debug_endgame():
    print("Loading model and predictor...")
    predictor = Predictor.load('models/ilt_champion_v2', 'data/ilt_feature_store_v2')
    model = predictor.model
    
    scenarios = [
        (156, 4, 19, 3, 158, 'Need 2 from 3 balls'),
        (157, 4, 19, 4, 158, 'Need 1 from 2 balls'),
    ]
    
    print("\nAnalyzing Scenarios:")
    print("="*80)
    
    for score, wkts, over, ball, target, desc in scenarios:
        state = MatchState(
            match_id='test',
            venue='Dubai International Cricket Stadium',
            batting_team='GG', bowling_team='SW',
            innings=2, over=over, ball=ball,
            current_score=score, wickets_lost=wkts,
            batsman_1='Unknown', batsman_2='Unknown', bowler='Unknown',
            target_runs=target,
        )
        
        # 1. Get Features
        scraped_data = {
            'innings_num': state.innings,
            'over_number': state.over,
            'ball_number': state.ball,
            'total_score': state.current_score,
            'total_wickets': state.wickets_lost,
            'current_batsman': state.batsman_1,
            'non_striker': state.batsman_2,
            'current_bowler': state.bowler,
            'batting_team': state.batting_team,
            'bowling_team': state.bowling_team,
            'venue': state.venue,
            'target_score': state.target_runs,
            'runs_needed': (state.target_runs - state.current_score)
        }
        
        X = predictor.feature_mapper.create_feature_dataframe(scraped_data)
        
        # Filter features
        if hasattr(model, 'selected_features_'):
            for feat in model.selected_features_:
                if feat not in X.columns:
                    X[feat] = 0.0
            X = X[model.selected_features_]
            
        # 2. Get Prediction
        prob = model.predict_proba(X)[0, 1]
        
        print(f"\nScenario: {desc}")
        print(f"Score: {score}/{wkts}, Over: {over}.{ball}")
        print(f"Final Probability: {prob:.6f}")
        
        # 3. Inspect underlying base estimators (if CalibratedClassifierCV)
        if hasattr(model, 'calibrated_classifiers_'):
            print("Individual Calibrated Classifiers outputs:")
            raw_probs = []
            for i, calibrated_classifier in enumerate(model.calibrated_classifiers_):
                # calibrated_classifier is a CalibratedClassifierCV._CalibratedClassifier
                # It has a .predict_proba method
                p = calibrated_classifier.predict_proba(X)[0, 1]
                raw_probs.append(p)
                print(f"  Model {i}: {p:.6f}")
            print(f"  Average: {np.mean(raw_probs):.6f}")
            
            # Try to get raw uncalibrated score if possible
            # The base_estimator inside calibrated_classifier is the XGBClassifier
            print("Raw Base Estimator (XGBoost) outputs (Uncalibrated):")
            base_probs = []
            for i, calibrated_classifier in enumerate(model.calibrated_classifiers_):
                if hasattr(calibrated_classifier, 'base_estimator'):
                    # predict_proba on XGBClassifier returns probability
                    base_p = calibrated_classifier.base_estimator.predict_proba(X)[0, 1]
                    base_probs.append(base_p)
                    print(f"  Base Model {i}: {base_p:.6f}")
            print(f"  Average Raw: {np.mean(base_probs):.6f}")

        # 4. Key Features
        print("Key Features:")
        cols_of_interest = ['resource_win_prob', 'runs_required', 'balls_remaining', 'wickets_remaining', 'dls_pressure_index']
        for col in cols_of_interest:
            if col in X.columns:
                print(f"  {col}: {X[col].iloc[0]}")

if __name__ == "__main__":
    debug_endgame()
