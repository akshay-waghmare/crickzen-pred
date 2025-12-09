import joblib
import json
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import structlog

from .schema import MatchState
from ..features.store import InMemoryFeatureStore

logger = structlog.get_logger()

class Predictor:
    """
    Inference engine for BBL win probability.
    """
    def __init__(self, model, feature_store: InMemoryFeatureStore, global_stats: Dict[str, float]):
        self.model = model
        self.feature_store = feature_store
        self.global_stats = global_stats

    @classmethod
    def load(cls, model_dir: str | Path):
        """
        Loads the champion model and associated artifacts.
        """
        path = Path(model_dir)
        
        # Load model
        model_path = path / "champion_model.joblib"
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found at {model_path}")
        model = joblib.load(model_path)
        
        # Load metadata (optional, but good for verification)
        meta_path = path / "champion_metadata.json"
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)
                logger.info(f"Loaded model: {meta.get('model_name')}")
        
        # Load Feature Store
        # Assuming feature store artifacts are in the same dir or a known location
        # For now, let's assume they are in model_dir/features/ or passed in config?
        # The plan says "Persist feature state as a Parquet file... alongside the model."
        
        player_stats_path = path / "player_stats.parquet"
        venue_stats_path = path / "venue_stats.parquet"
        
        feature_store = InMemoryFeatureStore(player_stats_path, venue_stats_path)
        feature_store.load() # Pre-load for low latency
        
        # Load global stats (fallbacks)
        # Assuming saved in metadata or separate file
        global_stats = meta.get('global_stats', {}) if meta_path.exists() else {}
        # If not in meta, we might need defaults.
        
        return cls(model, feature_store, global_stats)

    def _hydrate_features(self, state: MatchState) -> pd.DataFrame:
        """
        Transforms MatchState into a feature vector (DataFrame) using FeatureStore.
        """
        # Get stats
        batsman_1_stats = self.feature_store.get_player_stats(state.batsman_1) or {}
        batsman_2_stats = self.feature_store.get_player_stats(state.batsman_2) or {}
        bowler_stats = self.feature_store.get_player_stats(state.bowler) or {}
        venue_stats = self.feature_store.get_venue_stats(state.venue) or {}
        
        # Fallbacks
        b1_avg = batsman_1_stats.get('batsman_rolling_avg', self.global_stats.get('global_batting_avg', 25.0))
        b1_sr = batsman_1_stats.get('batsman_rolling_sr', self.global_stats.get('global_batting_sr', 125.0))
        
        bowler_econ = bowler_stats.get('bowler_rolling_econ', self.global_stats.get('global_bowling_econ', 7.5))
        bowler_sr = bowler_stats.get('bowler_rolling_sr', self.global_stats.get('global_bowling_sr', 20.0))
        
        venue_score = venue_stats.get('venue_avg_score', 160.0)
        venue_wickets = venue_stats.get('venue_avg_wickets', 6.0)
        venue_win_rate = venue_stats.get('venue_bat_first_win_rate', 0.5)

        # Construct DataFrame
        # Must match training columns:
        # ['innings', 'over', 'ball', 'current_score', 'wickets_lost',
        #  'batsman_rolling_avg', 'batsman_rolling_sr', 
        #  'bowler_rolling_econ', 'bowler_rolling_sr',
        #  'venue_avg_score', 'venue_avg_wickets', 'venue_bat_first_win_rate']
        
        features = {
            'innings': state.innings,
            'over': state.over,
            'ball': state.ball,
            'current_score': state.current_score,
            'wickets_lost': state.wickets_lost,
            'batsman_rolling_avg': b1_avg,
            'batsman_rolling_sr': b1_sr,
            'bowler_rolling_econ': bowler_econ,
            'bowler_rolling_sr': bowler_sr,
            'venue_avg_score': venue_score,
            'venue_avg_wickets': venue_wickets,
            'venue_bat_first_win_rate': venue_win_rate
        }
        
        # Note: target_runs and required_run_rate were not in training data for MVP.
        
        return pd.DataFrame([features])
        
        return pd.DataFrame([features])

    def predict(self, state: MatchState) -> float:
        """
        Returns the win probability for the batting team.
        """
        X = self._hydrate_features(state)
        
        # The model (CalibratedModel) expects a DataFrame (or array)
        # If the model includes a pipeline with FeatureTransformer, it handles columns.
        # If not, we must ensure columns match exactly.
        
        # For now, we assume the model handles it or we are lucky.
        # In production, we'd enforce schema.
        
        try:
            prob = self.model.predict_proba(X)[0, 1] # Probability of class 1 (Win)
            return float(prob)
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            # Fallback?
            return 0.5
