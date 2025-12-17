import joblib
import json
import pickle
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


class EnsembleModelWrapper:
    """Wrapper to make ensemble model dict behave like a sklearn model."""
    
    def __init__(self, model_dict):
        self.model_dict = model_dict
        self.xgb_model = model_dict['xgb_model']
        self.lr_model = model_dict['lr_model']
        self.scaler = model_dict['scaler']
        self.features = model_dict.get('features', [])
        weights = model_dict.get('ensemble_weights', [0.5, 0.5])
        self.xgb_weight = weights[0]
        self.lr_weight = weights[1]
    
    def predict_proba(self, X):
        """Return ensemble probability predictions."""
        # Scale for LogReg
        X_scaled = self.scaler.transform(X)
        
        # Get probabilities from both models
        xgb_probs = self.xgb_model.predict_proba(X)
        lr_probs = self.lr_model.predict_proba(X_scaled)
        
        # Weighted average
        ensemble_probs = self.xgb_weight * xgb_probs + self.lr_weight * lr_probs
        return ensemble_probs
    
    @property
    def feature_names_in_(self):
        """Return feature names for compatibility."""
        return self.features if self.features else None


class Predictor:
    """
    Inference engine for BBL win probability.
    Enhanced with resource-based features for improved calibration.
    """
    def __init__(self, model, feature_store: InMemoryFeatureStore, global_stats: Dict[str, float], calibrator=None):
        # Wrap ensemble model dict if needed
        if isinstance(model, dict) and 'xgb_model' in model:
            self.model = EnsembleModelWrapper(model)
        else:
            self.model = model
        self.feature_store = feature_store
        self.global_stats = global_stats
        self.calibrator = calibrator  # Isotonic calibrator for probability calibration
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
        
        # Load isotonic calibrator if available
        calibrator = None
        calibrator_path = path / "isotonic_calibrator.pkl"
        if calibrator_path.exists():
            try:
                # Try joblib first (newer models), then pickle (older models)
                try:
                    calibrator_data = joblib.load(calibrator_path)
                except Exception:
                    with open(calibrator_path, 'rb') as f:
                        calibrator_data = pickle.load(f)
                
                # Check if calibrator has metadata (newer format)
                if isinstance(calibrator_data, dict) and 'calibrator' in calibrator_data:
                    # Extract actual calibrator and metadata
                    calibrator = calibrator_data['calibrator']
                    cal_features = calibrator_data.get('features', [])
                    cal_feature_hash = calibrator_data.get('feature_hash', '')
                    cal_model_path = calibrator_data.get('model_path', '')
                    
                    # Validate compatibility with loaded model
                    import hashlib
                    
                    # Get model's feature list
                    model_features = None
                    if hasattr(model, 'selected_features_'):
                        model_features = model.selected_features_
                    elif hasattr(model, 'feature_names_in_'):
                        model_features = list(model.feature_names_in_) if model.feature_names_in_ is not None else None
                    elif isinstance(model, dict) and 'features' in model:
                        model_features = model['features']
                    
                    # Calculate model feature hash
                    if model_features:
                        model_feature_hash = hashlib.md5('_'.join(sorted(model_features)).encode()).hexdigest()
                        
                        # Warn if feature mismatch
                        if cal_feature_hash != model_feature_hash:
                            logger.warning(
                                "⚠️  CALIBRATOR-MODEL MISMATCH DETECTED!",
                                calibrator_features=len(cal_features),
                                model_features=len(model_features),
                                calibrator_hash=cal_feature_hash,
                                model_hash=model_feature_hash,
                                message="Calibrator was trained on different features. Regenerate with: bbl-pipeline generate-oof"
                            )
                            # Don't load mismatched calibrator - safer to use uncalibrated model
                            calibrator = None
                        else:
                            logger.info(
                                "✓ Calibrator validated",
                                feature_hash=cal_feature_hash,
                                n_features=len(cal_features),
                                created=calibrator_data.get('created_date', 'unknown')
                            )
                    else:
                        logger.warning("Could not validate calibrator - model has no feature list")
                else:
                    # Old format (just the calibrator object) - load but warn
                    calibrator = calibrator_data
                    logger.warning(
                        "⚠️  Using legacy calibrator format (no metadata).",
                        message="Cannot validate compatibility. Regenerate with: bbl-pipeline generate-oof"
                    )
                
                if calibrator:
                    logger.info("Loaded isotonic calibrator for probability calibration")
            except Exception as e:
                logger.warning(f"Failed to load calibrator: {e}")
        
        return cls(model, feature_store, global_stats, calibrator)

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

    def predict(self, state: MatchState, debug: bool = False, ball_history: list = None) -> float:
        """
        Returns the win probability for the batting team.
        Uses RealTimeFeatureMapper to generate all required features.
        
        Args:
            state: Current match state
            debug: If True, print all features being fed to the model
            ball_history: Optional list of ball data dicts for rolling stats
        """
        # Feed ball history to mapper if provided
        if ball_history:
            self.feature_mapper.ball_history = ball_history
        
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
            
            # Get expected features from model
            expected_features = None
            if hasattr(self.model, 'feature_names_in_'):
                expected_features = list(self.model.feature_names_in_)
            elif hasattr(self.model, 'selected_features_'):
                expected_features = self.model.selected_features_
            elif hasattr(self.model, 'get_booster'):
                # XGBoost: get feature names from booster
                try:
                    expected_features = self.model.get_booster().feature_names
                except:
                    pass
            
            # Filter to expected features if we know them
            if expected_features:
                # Ensure all required features exist (fill missing with appropriate defaults)
                for feat in expected_features:
                    if feat not in X.columns:
                        # Use appropriate default based on feature name
                        if 'rate' in feat.lower() or 'avg' in feat.lower():
                            X[feat] = 0.0
                        elif 'is_' in feat:
                            X[feat] = 0
                        elif 'pct' in feat or 'prob' in feat:
                            X[feat] = 0.5
                        else:
                            X[feat] = 0.0
                # Select only the required features in the correct order
                X = X[expected_features]
            
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
            
            raw_prob = self.model.predict_proba(X)[0, 1]  # Probability of class 1 (Win)
            
            # Apply isotonic calibration if available with smoothing to prevent cliff effects
            # Use raw model probability but show all three for comparison
            model_prob = raw_prob
            
            # Store all probability types for external access
            self.last_raw_prob = raw_prob
            self.last_smoothed_prob = raw_prob
            self.last_calibrated_prob = raw_prob
            
            if self.calibrator is not None:
                calibrated_prob = float(self.calibrator.predict([raw_prob])[0])
                # Calculate smoothed (what we would use if blending)
                CALIBRATOR_WEIGHT = 0.3
                MAX_CALIBRATION_SHIFT = 0.05
                smoothed_prob = CALIBRATOR_WEIGHT * calibrated_prob + (1 - CALIBRATOR_WEIGHT) * raw_prob
                if abs(smoothed_prob - raw_prob) > MAX_CALIBRATION_SHIFT:
                    smoothed_prob = raw_prob + (MAX_CALIBRATION_SHIFT if smoothed_prob > raw_prob else -MAX_CALIBRATION_SHIFT)
                
                # Store for external access
                self.last_smoothed_prob = smoothed_prob
                self.last_calibrated_prob = calibrated_prob
                
                if debug:
                    print(f"📊 Raw: {raw_prob:.1%} | Smoothed: {smoothed_prob:.1%} | Calibrated: {calibrated_prob:.1%}")
            else:
                if debug:
                    print(f"📊 Model probability: {model_prob:.1%}")
            
            # Get resource-based probability for extreme edge case guardrail
            resource_prob = X['resource_win_prob'].iloc[0] if 'resource_win_prob' in X.columns else 0.5
            
            # Minimal guardrail: Only apply in extreme edge cases (>97% or <3%)
            # The Brier score analysis shows model is better calibrated than DLS-based
            # in all phases, so we only override for near-certain outcomes
            if state.innings == 2 and state.target_runs:
                runs_needed = state.target_runs - state.current_score
                balls_remaining = (20 - state.over) * 6 - state.ball
                wickets_remaining = 10 - state.wickets_lost
                
                # Match already won
                if runs_needed <= 0:
                    prob = 1.0
                
                # Match already lost (no balls remaining)
                elif balls_remaining <= 0:
                    prob = 0.0
                
                # Mathematically impossible: Need more runs than max possible
                # Max possible = 6 runs per ball (all sixes, no wides/noballs considered)
                elif runs_needed > balls_remaining * 6:
                    prob = 0.0
                
                # Near-impossible: Need >5 runs per ball on average
                elif runs_needed > balls_remaining * 5:
                    # e.g. 22 off 4 balls = 5.5 per ball, very unlikely
                    prob = min(model_prob, 0.02)
                
                # Very difficult: Need >4 runs per ball on average  
                elif runs_needed > balls_remaining * 4:
                    # e.g. 20 off 4 balls = 5 per ball
                    prob = min(model_prob, 0.05)
                
                # --- ENDGAME GUARDRAILS ---
                # Only apply these in late-game situations (after 10 overs)
                # Early innings have too much variance to apply resource-based floors
                
                # 1. "Victory Lap" Scenarios: Explicitly handle obvious wins
                # The model can be conservative (e.g. 92%) due to calibration bins, but
                # humans know these are 99%+ situations.
                elif runs_needed <= 6 and wickets_remaining >= 3:
                    # One hit away with wickets in hand -> 99%
                    prob = max(model_prob, 0.99)
                    
                elif runs_needed <= 12 and runs_needed < balls_remaining and wickets_remaining >= 4:
                    # Two hits away, run-a-ball, plenty of wickets -> 98%
                    prob = max(model_prob, 0.98)

                # 2. Resource-based Guardrails (ONLY in late game - after 10 overs)
                # Early innings have too much variance - trust the model
                elif state.over >= 10 and resource_prob > 0.99:
                    # Very late game with near-certain DLS position
                    prob = max(model_prob, 0.95)
                    
                elif state.over >= 15 and resource_prob > 0.97:
                    # Death overs with strong DLS position  
                    prob = max(model_prob, 0.90)

                # 3. Loss Guardrails - Smooth continuous capping
                # If resource_prob is low, the model shouldn't be too optimistic
                elif resource_prob < 0.20:
                    # Game Over: No resources left = 0% win probability
                    if resource_prob == 0.0:
                        prob = 0.0
                    else:
                        # Smooth cap: Allow model to be slightly higher than resource_prob, but not much
                        # e.g. res=0.01 -> cap=0.025
                        #      res=0.05 -> cap=0.085
                        #      res=0.10 -> cap=0.16
                        #      res=0.15 -> cap=0.235
                        max_allowed = (resource_prob * 1.5) + 0.01
                        prob = min(model_prob, max_allowed)
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
