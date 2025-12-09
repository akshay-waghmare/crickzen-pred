import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

class RunsPredictor:
    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        self.model = None
        
    def load(self):
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found at {self.model_path}")
        self.model = joblib.load(self.model_path)
        
    def predict(self, features: Dict[str, Any]) -> float:
        """
        Predict final score based on current match state.
        Expected features:
        - current_score
        - wickets_lost
        - balls_remaining
        - wickets_remaining
        - current_run_rate
        - innings_num
        - batsman1_historical_average
        - batsman1_historical_strike_rate
        - batsman2_historical_average
        - batsman2_historical_strike_rate
        - bowler1_historical_economy
        - bowler1_historical_average
        - average_runs_per_over
        """
        if self.model is None:
            self.load()
            
        # Convert dict to DataFrame
        df = pd.DataFrame([features])
        
        # Ensure numeric types
        numeric_cols = [
            'batsman1_historical_average', 'batsman1_historical_strike_rate',
            'batsman2_historical_average', 'batsman2_historical_strike_rate',
            'bowler1_historical_economy', 'bowler1_historical_average',
            'average_runs_per_over'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Predict
        pred = self.model.predict(df)[0]
        return float(pred)
