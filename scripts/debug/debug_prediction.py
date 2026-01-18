import joblib
import pandas as pd
import json
import sys
import os
import numpy as np

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from bbl_pipeline.training.trainer import XGBLogRegEnsemble

def debug_prediction():
    # Load live state
    with open('data/live_state.json', 'r') as f:
        state = json.load(f)
    
    features = state['features']
    model_path = 'models/sat_v1/champion_model.joblib'
    
    print(f"Loading model from {model_path}")
    try:
        model = joblib.load(model_path)
    except FileNotFoundError:
        # Fallback to bbl_v8 if sat_v1 doesn't exist (as per instructions, but user used sat_v1)
        # The user command showed: --model-dir models/sat_v1
        # If that failed, maybe that's why? But the JSON exists.
        # Let's check if the file exists.
        if not os.path.exists(model_path):
            print(f"Model not found at {model_path}. Trying models/bbl_v8/champion_model.joblib")
            model_path = 'models/bbl_v8/champion_model.joblib'
            model = joblib.load(model_path)
        else:
            raise

    # Create DataFrame
    df = pd.DataFrame([features])
    
    # Predict
    if hasattr(model, 'predict_proba'):
        prob = model.predict_proba(df)[0][1]
    else:
        prob = float(model.predict(df)[0])
        
    print(f"Re-calculated Raw Probability: {prob}")
    print(f"JSON Raw Probability: {state['raw_win_prob']}")
    
    # Inspect contributions
    if isinstance(model, XGBLogRegEnsemble):
        # XGBoost part
        xgb_prob = model.xgb_model_.predict_proba(df[model.selected_features_])[0][1]
        print(f"XGBoost Probability: {xgb_prob}")
        
        # LogReg part
        # Handle pipeline
        if hasattr(model.logreg_model_, 'predict_proba'):
            lr_prob = model.logreg_model_.predict_proba(df[model.selected_features_])[0][1]
        else:
            lr_prob = model.logreg_model_.predict(df[model.selected_features_])[0]
        print(f"LogReg Probability: {lr_prob}")
        
        print(f"Weights: XGB={model.xgb_weight}, LogReg={1-model.xgb_weight}")
        
        # Feature contributions (approximate for LogReg)
        if hasattr(model.logreg_model_, 'named_steps'):
            if 'logisticregression' in model.logreg_model_.named_steps:
                lr = model.logreg_model_.named_steps['logisticregression']
            elif 'classifier' in model.logreg_model_.named_steps:
                lr = model.logreg_model_.named_steps['classifier']
            else:
                lr = model.logreg_model_.steps[-1][1]
                
            # We need scaled features for accurate contribution
            if 'scaler' in model.logreg_model_.named_steps:
                scaler = model.logreg_model_.named_steps['scaler']
                X_scaled = scaler.transform(df[model.selected_features_])
                
                coefs = lr.coef_[0]
                contributions = X_scaled[0] * coefs
                
                print("\nTop 5 LogReg Positive Contributors:")
                contrib_df = pd.DataFrame({'feature': model.selected_features_, 'contribution': contributions})
                print(contrib_df.sort_values('contribution', ascending=False).head(5))
                
                print("\nTop 5 LogReg Negative Contributors:")
                print(contrib_df.sort_values('contribution', ascending=True).head(5))

if __name__ == "__main__":
    debug_prediction()
