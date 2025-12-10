import joblib
import json
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import structlog

from .schema import MatchState
from .realtime_mapper import RealTimeFeatureMapper
from ..features.store import InMemoryFeatureStore
from ..features.calculator import ResourceFeatureCalculator

logger = structlog.get_logger()


class DummyFeatureStore:
    """Fallback feature store that returns empty dicts (uses global defaults)."""
    
    def get_player_stats(self, player_name: str) -> Dict[str, Any]:
        return {}
    
    def get_venue_stats(self, venue: str) -> Dict[str, Any]:
        return {}
    
    def load(self):
        pass


class Predictor:
    """
    Inference engine for BBL win probability.
    Enhanced with resource-based features for improved calibration.
    """
    def __init__(self, model, feature_store: InMemoryFeatureStore, global_stats: Dict[str, float]):
        self.model = model
        self.feature_store = feature_store
        self.global_stats = global_stats
        self.resource_calculator = ResourceFeatureCalculator()
        # Use RealTimeFeatureMapper for proper feature generation
        self.feature_mapper = RealTimeFeatureMapper(feature_store, global_stats)

    @classmethod
    def load(cls, model_dir: str | Path, feature_store_dir: str | Path = None):
        """
        Loads the champion model and associated artifacts.
        
        Args:
            model_dir: Path to model directory containing champion_model.joblib
            feature_store_dir: Path to feature store directory (defaults to data/feature_store)
        """
        path = Path(model_dir)
        
        # Load model
        model_path = path / "champion_model.joblib"
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found at {model_path}")
        model = joblib.load(model_path)
        
        # Load metadata (optional, but good for verification)
        meta = {}
        meta_path = path / "champion_metadata.json"
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)
                logger.info(f"Loaded model: {meta.get('model_name')}")
        
        # Load Feature Store
        # Look in multiple locations: model_dir, feature_store_dir, or default data/feature_store
        feature_store = None
        
        # Determine feature store paths
        if feature_store_dir:
            fs_path = Path(feature_store_dir)
        else:
            # Try model dir first, then default location
            fs_path = path
            
        player_stats_path = fs_path / "player_stats.parquet"
        venue_stats_path = fs_path / "venue_stats.parquet"
        
        # If not in model dir, try default feature_store location
        if not player_stats_path.exists():
            # Try relative to project root
            default_fs_path = Path(__file__).parent.parent.parent.parent / "data" / "feature_store"
            if default_fs_path.exists():
                player_stats_path = default_fs_path / "player_stats.parquet"
                venue_stats_path = default_fs_path / "venue_stats.parquet"
                logger.info(f"Using feature store from: {default_fs_path}")
        
        if player_stats_path.exists() and venue_stats_path.exists():
            try:
                feature_store = InMemoryFeatureStore(player_stats_path, venue_stats_path)
                feature_store.load()
                logger.info("Feature store loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load feature store: {e}")
                feature_store = None
        else:
            logger.warning("Feature store files not found, using defaults")
        
        # Create dummy feature store if not loaded
        if feature_store is None:
            feature_store = DummyFeatureStore()
        
        # Load global stats (fallbacks)
        global_stats = meta.get('global_stats', {})
        if not global_stats:
            # Provide sensible defaults
            global_stats = {
                'global_batting_avg': 25.0,
                'global_batting_sr': 130.0,
                'global_bowling_econ': 8.0,
                'global_bowling_sr': 18.0,
            }
        
        return cls(model, feature_store, global_stats)

    def _hydrate_features(self, state: MatchState) -> pd.DataFrame:
        """
        Transforms MatchState into a feature vector (DataFrame) using FeatureStore.
        Enhanced with resource-based features for better calibration.
        """
        # Get player/venue stats
        batsman_1_stats = self.feature_store.get_player_stats(state.batsman_1) or {}
        batsman_2_stats = self.feature_store.get_player_stats(state.batsman_2) or {}
        bowler_stats = self.feature_store.get_player_stats(state.bowler) or {}
        venue_stats = self.feature_store.get_venue_stats(state.venue) or {}
        
        # Fallbacks for player/venue stats
        b1_avg = batsman_1_stats.get('batsman_rolling_avg', self.global_stats.get('global_batting_avg', 25.0))
        b1_sr = batsman_1_stats.get('batsman_rolling_sr', self.global_stats.get('global_batting_sr', 125.0))
        
        bowler_econ = bowler_stats.get('bowler_rolling_econ', self.global_stats.get('global_bowling_econ', 7.5))
        bowler_sr = bowler_stats.get('bowler_rolling_sr', self.global_stats.get('global_bowling_sr', 20.0))
        
        venue_score = venue_stats.get('venue_avg_score', 160.0)
        venue_wickets = venue_stats.get('venue_avg_wickets', 6.0)
        venue_win_rate = venue_stats.get('venue_bat_first_win_rate', 0.5)

        # Calculate resource-based features
        resource_features = self.resource_calculator.calculate_all_features(
            innings=state.innings,
            over=state.over,
            ball=state.ball,
            current_score=state.current_score,
            wickets_lost=state.wickets_lost,
            target_runs=state.target_runs
        )

        # Construct DataFrame with all features
        features = {
            # Basic match state
            'innings': state.innings,
            'over': state.over,
            'ball': state.ball,
            'current_score': state.current_score,
            'wickets_lost': state.wickets_lost,
            
            # Player rolling stats
            'batsman_rolling_avg': b1_avg,
            'batsman_rolling_sr': b1_sr,
            'bowler_rolling_econ': bowler_econ,
            'bowler_rolling_sr': bowler_sr,
            
            # Venue stats
            'venue_avg_score': venue_score,
            'venue_avg_wickets': venue_wickets,
            'venue_bat_first_win_rate': venue_win_rate,
            
            # Resource-based features (hybrid cricket domain knowledge)
            'overs_remaining': resource_features['overs_remaining'],
            'balls_remaining': resource_features['balls_remaining'],
            'wickets_remaining': resource_features['wickets_remaining'],
            'resource_pct': resource_features['resource_pct'],
            'current_run_rate': resource_features['current_run_rate'],
            'required_run_rate': resource_features['required_run_rate'],
            'run_rate_differential': resource_features['run_rate_differential'],
            'expected_final_score': resource_features['expected_final_score'],
            'runs_required': resource_features['runs_required'],
            'is_powerplay': resource_features['is_powerplay'],
            'is_middle_overs': resource_features['is_middle_overs'],
            'is_death_overs': resource_features['is_death_overs'],
            'pressure_index': resource_features['pressure_index'],
            'resource_win_prob': resource_features['resource_win_prob'],
        }
        
        return pd.DataFrame([features])

    def predict(self, state: MatchState, debug: bool = False) -> float:
        """
        Returns the win probability for the batting team.
        Uses RealTimeFeatureMapper to generate all required features.
        
        Args:
            state: Current match state
            debug: If True, print all features being fed to the model
        """
        # Convert MatchState to scraped_data format for the mapper
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
            # Calculate runs_needed for 2nd innings
            'runs_needed': (state.target_runs - state.current_score) if state.target_runs else 0,
        }
        
        try:
            # Use RealTimeFeatureMapper to generate all features
            X = self.feature_mapper.create_feature_dataframe(scraped_data)
            
            if debug:
                print("\n" + "="*70)
                print("🔍 DEBUG: Features fed to model")
                print("="*70)
                print(f"Input MatchState:")
                print(f"  innings={state.innings}, over={state.over}, ball={state.ball}")
                print(f"  score={state.current_score}/{state.wickets_lost}")
                print(f"  batting_team={state.batting_team}, bowling_team={state.bowling_team}")
                print(f"  batsman_1={state.batsman_1}, batsman_2={state.batsman_2}")
                print(f"  bowler={state.bowler}, venue={state.venue}")
                print(f"  target_runs={state.target_runs}")
                print("-"*70)
                print("Generated Features:")
                for col in sorted(X.columns):
                    val = X[col].iloc[0]
                    if isinstance(val, float):
                        print(f"  {col}: {val:.4f}")
                    else:
                        print(f"  {col}: {val}")
                print("="*70 + "\n")
            
            model_prob = self.model.predict_proba(X)[0, 1]  # Probability of class 1 (Win)
            
            # Get resource-based probability for extreme edge case guardrail
            resource_prob = X['resource_win_prob'].iloc[0] if 'resource_win_prob' in X.columns else 0.5
            
            # Minimal guardrail: Only apply in extreme edge cases (>97% or <3%)
            # The Brier score analysis shows model is better calibrated than DLS-based
            # in all phases, so we only override for near-certain outcomes
            if state.innings == 2 and state.target_runs:
                runs_needed = state.target_runs - state.current_score
                
                # Match already won
                if runs_needed <= 0:
                    prob = 1.0
                # Near-certain win (resource > 97%) - ensure model doesn't underestimate
                elif resource_prob > 0.97:
                    prob = max(model_prob, 0.92)
                # Near-certain loss (resource < 3%) - ensure model doesn't overestimate
                elif resource_prob < 0.03:
                    prob = min(model_prob, 0.08)
                else:
                    prob = model_prob
            else:
                prob = model_prob
            
            return float(prob)
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            # Fallback: Use resource-based win probability
            resource_features = self.resource_calculator.calculate_all_features(
                innings=state.innings,
                over=state.over,
                ball=state.ball,
                current_score=state.current_score,
                wickets_lost=state.wickets_lost,
                target_runs=state.target_runs
            )
            return resource_features['resource_win_prob']
