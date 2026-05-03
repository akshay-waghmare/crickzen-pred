import joblib
import json
import pickle
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, TYPE_CHECKING
import structlog

if TYPE_CHECKING:
    from ..simulation.feature_context import FeatureContext

from .schema import MatchState
from .realtime_mapper import RealTimeFeatureMapper
from ..features.store import InMemoryFeatureStore
from ..features.calculator import ResourceFeatureCalculator
from ..features.format_config import FormatConfig

logger = structlog.get_logger()


def _restore_simple_imputer_compatibility(root) -> int:
    """Restore sklearn 1.7 -> 1.8 SimpleImputer state for persisted models."""
    seen: set[int] = set()
    stack = [root]
    patched = 0

    while stack:
        current = stack.pop()
        current_id = id(current)
        if current is None or current_id in seen:
            continue
        seen.add(current_id)

        if type(current).__name__ == 'SimpleImputer':
            if hasattr(current, '_fit_dtype') and not hasattr(current, '_fill_dtype'):
                current._fill_dtype = current._fit_dtype
                patched += 1

        if isinstance(current, dict):
            stack.extend(current.values())
            continue

        if isinstance(current, (list, tuple, set)):
            stack.extend(current)
            continue

        if hasattr(current, '__dict__'):
            stack.extend(current.__dict__.values())

    return patched


def _coerce_probability_scalar(value: Any) -> float:
    """Convert scalar-like numpy/list outputs into a single float probability."""
    array = np.asarray(value)
    if array.size == 0:
        raise ValueError("Cannot coerce empty probability output to scalar")
    return float(array.reshape(-1)[0])


class DummyFeatureStore:
    """Fallback feature store that returns empty dicts (uses global defaults)."""
    
    def get_player_stats(self, player_name: str) -> Dict[str, Any]:
        return {}
    
    def get_venue_stats(self, venue: str) -> Dict[str, Any]:
        return {}

    def get_team_stats(self, team_name: str) -> Dict[str, Any]:
        return {}
    
    def load(self):
        pass


# NOTE: S-curve correction was removed after temporal holdout validation showed it hurt performance.
# The per-over isotonic calibrators provide sufficient calibration.
# See analyze_temporal_holdout.py for details.


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
    Enhanced with resource-based features and innings-specific calibration.
    """
    def __init__(self, model, feature_store: InMemoryFeatureStore, global_stats: Dict[str, float], 
                 calibrator=None, calibrator_inn1=None, calibrator_inn2=None, phase_calibrators=None, 
                 per_over_calibrators=None, calibrator_type='none', league_calibrator=None, model_dir: str = None,
                 format_config: FormatConfig = None, phase_target_calibrators=None):
        # Wrap ensemble model dict if needed
        if isinstance(model, dict) and 'xgb_model' in model:
            self.model = EnsembleModelWrapper(model)
        else:
            self.model = model
        self.model_dir = model_dir  # Store model directory for reference
        self.format_config = format_config or FormatConfig.t20()
        self.feature_store = feature_store
        self.global_stats = global_stats
        self.calibrator = calibrator  # Single calibrator (legacy/backward compatible)
        self.calibrator_inn1 = calibrator_inn1  # Innings 1 calibrator
        self.calibrator_inn2 = calibrator_inn2  # Innings 2 calibrator
        self.phase_calibrators = phase_calibrators  # Innings×phase calibrators dict
        self.per_over_calibrators = per_over_calibrators  # Per-over (brier_optimized) calibrators dict
        self.phase_target_calibrators = phase_target_calibrators  # Inn2 9-segment phase×target calibrators
        self.calibrator_type = calibrator_type  # 'innings_phase_specific', 'innings_specific', 'single', 'legacy', or 'none'
        self.league_calibrator = league_calibrator  # League-specific temperature/platt calibrator
        self.resource_calculator = ResourceFeatureCalculator(config=self.format_config)
        # Use RealTimeFeatureMapper for proper feature generation
        self.feature_mapper = RealTimeFeatureMapper(feature_store, global_stats, format_config=self.format_config)
        
        # Innings transition smoothing: store inn1 final probability as prior for inn2 start
        self._inn1_final_prob = None  # P(batting_team wins) at end of innings 1
        self._inn1_batting_team = None  # Which team was batting in innings 1
        self.INNINGS_TRANSITION_OVERS = getattr(self.format_config, 'transition_blend_overs', 6)
        self.last_transition_alpha = None  # For debug/logging access
        self.last_terminal_clamp = None  # Final deterministic inn2 terminal override, if any
        self.last_calibrated_phase_target = None  # Phase×target calibrated probability
        self.last_shadow_prob = None  # Shadow: segment-specific T prediction (not production)
        self.last_t_applied = 1.0  # Production T actually used this prediction (1.0 = no-op)
    
    def reset_innings_prior(self):
        """Reset the inn1 prior (call when starting a new match)."""
        self._inn1_final_prob = None
        self._inn1_batting_team = None
        self.last_transition_alpha = None
        self.last_terminal_clamp = None

    def _second_innings_terminal_clamp(self, state: MatchState) -> Optional[Dict[str, Any]]:
        """Return deterministic batting-team win probability for decided chases."""
        if state.innings != 2 or not state.target_runs:
            return None

        runs_needed = state.target_runs - state.current_score
        balls_remaining = (self.format_config.total_overs - state.over) * 6 - state.ball

        if runs_needed <= 0:
            return {
                "applied": True,
                "reason": "chase_complete",
                "probability": 1.0,
                "runs_needed": int(runs_needed),
                "balls_remaining": int(max(0, balls_remaining)),
                "wickets_lost": int(state.wickets_lost),
            }

        if state.wickets_lost >= 10:
            return {
                "applied": True,
                "reason": "all_out",
                "probability": 0.0,
                "runs_needed": int(runs_needed),
                "balls_remaining": int(max(0, balls_remaining)),
                "wickets_lost": int(state.wickets_lost),
            }

        if balls_remaining <= 0:
            return {
                "applied": True,
                "reason": "no_balls_remaining",
                "probability": 0.0,
                "runs_needed": int(runs_needed),
                "balls_remaining": 0,
                "wickets_lost": int(state.wickets_lost),
            }

        if runs_needed > balls_remaining * 6:
            return {
                "applied": True,
                "reason": "mathematically_impossible",
                "probability": 0.0,
                "runs_needed": int(runs_needed),
                "balls_remaining": int(balls_remaining),
                "wickets_lost": int(state.wickets_lost),
            }

        return None

    @classmethod
    def load(cls, model_dir: str | Path, feature_store_dir: str | Path = None, league: str = None):
        """
        Loads the champion model and associated artifacts.
        
        Args:
            model_dir: Path to model directory containing champion_model.joblib
            feature_store_dir: Path to feature store directory (defaults to data/feature_store)
            league: Optional league code (e.g., 'ssm', 'bbl') to load league-specific calibrator
        """
        path = Path(model_dir)
        logger.info(f"Loading model from: {model_dir}")
        
        # Load model
        model_path = path / "champion_model.joblib"
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found at {model_path}")
        model = joblib.load(model_path)
        patched_imputers = _restore_simple_imputer_compatibility(model)
        if patched_imputers:
            logger.warning(
                "Patched sklearn SimpleImputer compatibility for persisted model",
                patched_imputers=patched_imputers,
                model_dir=str(path),
            )
        
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
                league_context = league
                if not league_context:
                    model_dir_lower = str(model_dir).lower()
                    if 't20_international' in model_dir_lower or 't20i' in model_dir_lower:
                        league_context = 't20_international'
                feature_store.league_context = league_context
                feature_store.load()
                logger.info(f"Feature store loaded successfully. Type: {type(feature_store)}")
                logger.info(f"Has get_team_stats: {hasattr(feature_store, 'get_team_stats')}")
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
        calibrator_inn1 = None
        calibrator_inn2 = None
        phase_calibrators = None
        calibrator_type = 'none'
        calibrator_path = path / "isotonic_calibrator.pkl"
        if calibrator_path.exists():
            try:
                # Try joblib first (newer models), then pickle (older models)
                try:
                    calibrator_data = joblib.load(calibrator_path)
                except Exception:
                    with open(calibrator_path, 'rb') as f:
                        calibrator_data = pickle.load(f)
                
                # Check calibrator type
                cal_type = calibrator_data.get('type', 'unknown') if isinstance(calibrator_data, dict) else 'legacy'
                
                # Load per-over calibrators if available (brier_optimized)
                per_over_calibrators = calibrator_data.get('per_over_calibrators', {}) if isinstance(calibrator_data, dict) else {}
                
                if cal_type == 'innings_phase_specific':
                    # Innings×phase specific calibrators (6 calibrators)
                    calibrator_inn1 = calibrator_data['calibrator_innings1']
                    calibrator_inn2 = calibrator_data['calibrator_innings2']
                    calibrator = calibrator_data.get('calibrator_combined', None)  # Optional combined for comparison
                    phase_calibrators = calibrator_data.get('phase_calibrators', {})
                    calibrator_type = 'innings_phase_specific'
                    logger.info(
                        "Loaded innings×phase specific calibrators",
                        created=calibrator_data.get('created_date', 'unknown'),
                        n_phase_calibrators=len(phase_calibrators),
                        n_per_over_calibrators=len(per_over_calibrators),
                        phase_keys=list(phase_calibrators.keys())
                    )
                    cal_features = calibrator_data.get('features', [])
                    cal_feature_hash = calibrator_data.get('feature_hash', '')
                elif cal_type == 'innings_specific':
                    # Innings-specific calibrators (2 calibrators)
                    calibrator_inn1 = calibrator_data['calibrator_innings1']
                    calibrator_inn2 = calibrator_data['calibrator_innings2']
                    calibrator = calibrator_data.get('calibrator_combined', None)  # Optional combined for comparison
                    calibrator_type = 'innings_specific'
                    logger.info(
                        "Loaded innings-specific calibrators",
                        created=calibrator_data.get('created_date', 'unknown'),
                        inn1_samples=calibrator_data.get('innings1_metrics', {}).get('samples', 0),
                        inn2_samples=calibrator_data.get('innings2_metrics', {}).get('samples', 0),
                        has_combined=calibrator is not None
                    )
                    cal_features = calibrator_data.get('features', [])
                    cal_feature_hash = calibrator_data.get('feature_hash', '')
                elif isinstance(calibrator_data, dict) and 'calibrator' in calibrator_data:
                    # Single calibrator with metadata (newer format)
                    calibrator = calibrator_data['calibrator']
                    calibrator_type = 'single'
                    cal_features = calibrator_data.get('features', [])
                    cal_feature_hash = calibrator_data.get('feature_hash', '')
                else:
                    # Legacy format (bare calibrator object)
                    calibrator = calibrator_data
                    calibrator_type = 'legacy'
                    cal_features = []
                    cal_feature_hash = ''
                    logger.warning("Loaded legacy calibrator format (no metadata)")
                
                # Validate compatibility with loaded model (only if we have metadata)
                if cal_features and calibrator_type != 'legacy':
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
                            calibrator_inn1 = None
                            calibrator_inn2 = None
                            phase_calibrators = None
                            calibrator_type = 'none'
                        else:
                            logger.info(
                                "Calibrator validated",
                                type=calibrator_type,
                                feature_hash=cal_feature_hash,
                                n_features=len(cal_features),
                                n_phase_calibrators=len(phase_calibrators) if phase_calibrators else 0,
                                created=calibrator_data.get('created_date', 'unknown')
                            )
                    else:
                        logger.warning("Could not validate calibrator - model has no feature list")
                
                if calibrator or calibrator_inn1 or calibrator_inn2 or phase_calibrators:
                    if calibrator_type == 'innings_phase_specific':
                        logger.info(f"Loaded innings×phase specific isotonic calibrators ({len(phase_calibrators)} calibrators)")
                    elif calibrator_type == 'innings_specific':
                        logger.info("Loaded innings-specific isotonic calibrators for probability calibration")
                    elif calibrator_type == 'single':
                        logger.info("Loaded isotonic calibrator for probability calibration")
                    elif calibrator_type == 'legacy':
                        logger.warning(
                            "⚠️  Using legacy calibrator format (no metadata).",
                            message="Cannot validate compatibility. Regenerate with: bbl-pipeline generate-oof"
                        )
            except Exception as e:
                logger.warning(f"Failed to load calibrator: {e}")
        
        # Load phase×target calibrators if available (inn2 9-segment calibration)
        phase_target_calibrators = None
        pt_cal_path = path / "phase_target_calibrators.pkl"
        if pt_cal_path.exists():
            try:
                pt_data = joblib.load(pt_cal_path)
                if isinstance(pt_data, dict) and 'calibrators' in pt_data:
                    phase_target_calibrators = pt_data
                    logger.info(
                        "Loaded phase×target calibrators (inn2 9-segment)",
                        n_segments=len(pt_data['calibrators']),
                        keys=list(pt_data['calibrators'].keys())
                    )
            except Exception as e:
                logger.warning(f"Failed to load phase_target_calibrators: {e}")
        
        # Load league-specific calibrator if league is specified
        league_calibrator = None
        if league:
            league_cal_path = path / "league_calibrators" / league / "league_calibrator.pkl"
            if league_cal_path.exists():
                try:
                    league_calibrator = joblib.load(league_cal_path)
                    cal_method = league_calibrator.get('method', 'unknown')
                    logger.info(
                        f"Loaded {league.upper()} league calibrator",
                        method=cal_method,
                        t1=league_calibrator.get('T1'),
                        t2=league_calibrator.get('T2'),
                        created=league_calibrator.get('created_date', 'unknown')
                    )
                except Exception as e:
                    logger.warning(f"Failed to load league calibrator for {league}: {e}")
            else:
                logger.warning(f"League calibrator not found at {league_cal_path}")
        
        # Resolve FormatConfig from league
        format_config = FormatConfig.from_league(league) if league else FormatConfig.t20()
        
        return cls(model, feature_store, global_stats, calibrator, calibrator_inn1, calibrator_inn2, phase_calibrators, per_over_calibrators, calibrator_type, league_calibrator, model_dir=str(path), format_config=format_config, phase_target_calibrators=phase_target_calibrators)

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
        
        venue_score = venue_stats.get('venue_avg_score', self.format_config.par_score)
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

    def build_feature_context(
        self,
        batting_team: str,
        bowling_team: str,
        venue: str,
        league: str,
        innings: int,
        # Optional season stats overrides (from Crex live scraper)
        batting_team_wr: float | None = None,
        bowling_team_wr: float | None = None,
        batting_situation_wr: float | None = None,
        bowling_situation_wr: float | None = None,
    ) -> "FeatureContext":
        """
        Build FeatureContext from InMemoryFeatureStore for MC terminal state evaluation.
        
        This method is called ONCE per Monte Carlo simulation to cache venue/team stats.
        The returned FeatureContext is then passed to predict_batch() for all 2000+
        terminal states, amortizing the feature store lookup cost.
        
        Hybrid Stats Approach (Option 3):
            If season stats are provided (batting_team_wr != 0.5), they override
            the historical stats from the feature store. This ensures MC predictions
            use the same stats as the baseline ML prediction.
        
        Args:
            batting_team: Canonical team name (e.g., "Perth Scorchers")
            bowling_team: Canonical team name (e.g., "Sydney Sixers")
            venue: Venue name (e.g., "Perth Stadium")
            league: League code (e.g., "bbl", "sa20")
            innings: 1 or 2 (affects situation-specific win rates)
            batting_team_wr: Optional season win rate for batting team (from Crex)
            bowling_team_wr: Optional season win rate for bowling team (from Crex)
            batting_situation_wr: Optional situation-specific WR for batting team
            bowling_situation_wr: Optional situation-specific WR for bowling team
            
        Returns:
            FeatureContext with venue/team stats (season if provided, else feature store)
            
        Raises:
            KeyError: If team/venue not found in feature store
            ValueError: If innings not in {1, 2}
            
        Performance:
            ~10ms for 5 feature store lookups (amortized across 2000 states)
        """
        from ..simulation.feature_context import FeatureContext
        
        if innings not in (1, 2):
            raise ValueError(f"innings must be 1 or 2, got {innings}")
        
        # Lookup venue stats
        venue_stats = self.feature_store.get_venue_stats(venue)
        if venue_stats:
            venue_avg_score = venue_stats.get('venue_avg_score', 165.0)
            venue_bat_first_wr = venue_stats.get('venue_bat_first_win_rate', 0.45)
        else:
            # Venue not found, use defaults
            venue_avg_score = 165.0
            venue_bat_first_wr = 0.45
        
        # Lookup team stats from feature store (historical)
        team_a_stats = self.feature_store.get_team_stats(batting_team)
        team_b_stats = self.feature_store.get_team_stats(bowling_team)
        
        # Use season stats if provided, else historical from feature store
        # Season stats come from Crex live scraper with current season win rates
        # Detect Crex data: if ANY of the 4 stats differs from 0.5 default, use season stats
        # (It's extremely unlikely Crex would report exactly 50% for all 4 values)
        has_season_stats = any([
            batting_team_wr is not None and batting_team_wr != 0.5,
            bowling_team_wr is not None and bowling_team_wr != 0.5,
            batting_situation_wr is not None and batting_situation_wr != 0.5,
            bowling_situation_wr is not None and bowling_situation_wr != 0.5,
        ])
        use_season_stats = has_season_stats
        
        if use_season_stats:
            # Use Crex season stats (same as baseline ML prediction)
            team_a_wr = batting_team_wr
            team_b_wr = bowling_team_wr if bowling_team_wr is not None else 0.5
            final_batting_situation_wr = batting_situation_wr if batting_situation_wr is not None else team_a_wr
            final_bowling_situation_wr = bowling_situation_wr if bowling_situation_wr is not None else team_b_wr
            logger.debug(
                "Using season stats from Crex",
                team_a_wr=team_a_wr,
                team_b_wr=team_b_wr,
                source="season"
            )
        else:
            # Use historical stats from feature store
            team_a_wr = team_a_stats.get('win_rate', 0.5)
            team_b_wr = team_b_stats.get('win_rate', 0.5)
            
            # Determine situation-specific win rates based on innings
            if innings == 1:
                # Batting first, bowling first
                final_batting_situation_wr = team_a_stats.get('bat_first_wr', team_a_wr)
                final_bowling_situation_wr = team_b_stats.get('bowl_first_wr', team_b_wr)
            else:
                # Chasing (team A bats second), defending (team B bowled first)
                final_batting_situation_wr = team_a_stats.get('bowl_first_wr', team_a_wr)
                final_bowling_situation_wr = team_b_stats.get('bat_first_wr', team_b_wr)
            logger.debug(
                "Using historical stats from feature store",
                team_a_wr=team_a_wr,
                team_b_wr=team_b_wr,
                source="feature_store"
            )
        
        logger.debug(
            "Built FeatureContext",
            batting_team=batting_team,
            bowling_team=bowling_team,
            venue=venue,
            venue_avg_score=venue_avg_score,
            team_a_wr=team_a_wr,
            team_b_wr=team_b_wr,
            innings=innings,
            stats_source="season" if use_season_stats else "feature_store"
        )
        
        return FeatureContext(
            venue_avg_score=venue_avg_score,
            venue_bat_first_wr=venue_bat_first_wr,
            team_a_wr=team_a_wr,
            team_b_wr=team_b_wr,
            batting_situation_wr=final_batting_situation_wr,
            bowling_situation_wr=final_bowling_situation_wr,
            league=league
        )

    def predict(self, state: MatchState, debug: bool = False, ball_history: list = None) -> float:
        """
        Returns the win probability for the batting team.
        Uses RealTimeFeatureMapper to generate all required features.
        
        Args:
            state: Current match state
            debug: If True, print all features being fed to the model
            ball_history: Optional list of ball data dicts for rolling stats
        """
        self.last_terminal_clamp = None

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
            # Inn1 carryover and toss info (for v6+ features)
            'first_innings_score': state.first_innings_score,
            'toss_winner': getattr(state, 'toss_winner', None),
            'toss_decision': getattr(state, 'toss_decision', None),
            'inn1_wickets_lost': getattr(state, 'inn1_wickets_lost', None),
            'inn1_pp_runs': getattr(state, 'inn1_pp_runs', None),
            'inn1_death_rr': getattr(state, 'inn1_death_rr', None),
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
                print("DEBUG: Features fed to model")
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
            
            # Apply innings-specific or single calibration if available
            model_prob = raw_prob
            
            # Store all probability types for external access
            self.last_raw_prob = raw_prob
            self.last_smoothed_prob = raw_prob
            self.last_league_calibrated = None  # Set later if league calibrator is applied
            self.last_calibrated_prob = raw_prob
            self.last_calibrated_combined = raw_prob  # For comparison when using innings-specific
            self.last_calibrated_phase = raw_prob  # For innings×phase specific
            self.last_calibrated_per_over = raw_prob  # For per-over (brier_optimized)
            
            # Select appropriate calibrator based on innings and phase
            active_calibrator = None
            combined_calibrator = None
            phase_calibrator = None
            per_over_calibrator = None
            
            # Determine phase and over
            current_over = int(state.over) + 1  # state.over is 0-indexed, we need 1-indexed
            thresholds = self.format_config.phase_thresholds
            phase_names = self.format_config.phase_names
            # Walk through phases in order; assign the first phase whose
            # upper boundary has not been reached yet, falling back to the last phase.
            phase = phase_names[-1]  # default to last phase
            for pname in phase_names:
                if current_over <= thresholds.get(pname, 999):
                    phase = pname
                    break
            
            phase_key = f'inn{state.innings}_{phase}'
            
            # Try per-over (brier_optimized) calibrator first if available
            over_key = f'inn{state.innings}_over{current_over}'
            if self.per_over_calibrators and over_key in self.per_over_calibrators:
                per_over_calibrator = self.per_over_calibrators[over_key]
            
            # Try innings×phase specific first (best performance)
            if self.calibrator_type == 'innings_phase_specific' and self.phase_calibrators:
                if phase_key in self.phase_calibrators:
                    phase_calibrator = self.phase_calibrators[phase_key]
                    # Also get innings-level calibrator for comparison
                    if state.innings == 1 and self.calibrator_inn1 is not None:
                        active_calibrator = self.calibrator_inn1
                    elif state.innings == 2 and self.calibrator_inn2 is not None:
                        active_calibrator = self.calibrator_inn2
                    combined_calibrator = self.calibrator
                else:
                    logger.warning(f"No phase calibrator for {phase_key}, falling back to innings-level")
                    # Fall back to innings-specific
                    if state.innings == 1 and self.calibrator_inn1 is not None:
                        active_calibrator = self.calibrator_inn1
                    elif state.innings == 2 and self.calibrator_inn2 is not None:
                        active_calibrator = self.calibrator_inn2
            elif self.calibrator_type == 'innings_specific':
                if state.innings == 1 and self.calibrator_inn1 is not None:
                    active_calibrator = self.calibrator_inn1
                elif state.innings == 2 and self.calibrator_inn2 is not None:
                    active_calibrator = self.calibrator_inn2
                else:
                    logger.warning(f"No calibrator for innings {state.innings}, using raw probability")
                # Also get combined calibrator for comparison
                combined_calibrator = self.calibrator
            elif self.calibrator_type in ['single', 'legacy'] and self.calibrator is not None:
                active_calibrator = self.calibrator
            
            if active_calibrator is not None:
                calibrated_prob = float(active_calibrator.predict([raw_prob])[0])
                # Calculate smoothed (what we would use if blending)
                CALIBRATOR_WEIGHT = 0.3
                MAX_CALIBRATION_SHIFT = 0.05
                smoothed_prob = CALIBRATOR_WEIGHT * calibrated_prob + (1 - CALIBRATOR_WEIGHT) * raw_prob
                if abs(smoothed_prob - raw_prob) > MAX_CALIBRATION_SHIFT:
                    smoothed_prob = raw_prob + (MAX_CALIBRATION_SHIFT if smoothed_prob > raw_prob else -MAX_CALIBRATION_SHIFT)
                
                # Store for external access
                self.last_smoothed_prob = smoothed_prob
                self.last_calibrated_prob = calibrated_prob
                
                # Calculate phase-specific calibration if available
                if phase_calibrator is not None:
                    calibrated_phase = float(phase_calibrator.predict([raw_prob])[0])
                    self.last_calibrated_phase = calibrated_phase
                
                # Calculate per-over (brier_optimized) calibration if available
                if per_over_calibrator is not None:
                    calibrated_per_over = float(per_over_calibrator.predict([raw_prob])[0])
                    self.last_calibrated_per_over = calibrated_per_over
                
                # Also calculate combined calibrator if available (for comparison)
                if combined_calibrator is not None:
                    calibrated_combined = float(combined_calibrator.predict([raw_prob])[0])
                    self.last_calibrated_combined = calibrated_combined
                
                if debug:
                    cal_label = f"Inn{state.innings}" if self.calibrator_type in ['innings_specific', 'innings_phase_specific'] else "Single"
                    if per_over_calibrator is not None:
                        print(f"[CAL] Raw: {raw_prob:.1%} | Phase ({phase_key}): {self.last_calibrated_phase:.1%} | PerOver ({over_key}): {self.last_calibrated_per_over:.1%}")
                    elif phase_calibrator is not None:
                        print(f"[CAL] Raw: {raw_prob:.1%} | Smoothed: {smoothed_prob:.1%} | Inn-Specific: {calibrated_prob:.1%} | Phase ({phase_key}): {self.last_calibrated_phase:.1%}")
                    elif self.calibrator_type in ['innings_specific', 'innings_phase_specific'] and combined_calibrator is not None:
                        print(f"[CAL] Raw: {raw_prob:.1%} | Smoothed: {smoothed_prob:.1%} | Combined: {calibrated_combined:.1%} | Inn-Specific ({cal_label}): {calibrated_prob:.1%}")
                    else:
                        print(f"[CAL] Raw: {raw_prob:.1%} | Smoothed: {smoothed_prob:.1%} | Calibrated ({cal_label}): {calibrated_prob:.1%}")
            else:
                # Still calculate per-over if available even without other calibrators
                if per_over_calibrator is not None:
                    calibrated_per_over = float(per_over_calibrator.predict([raw_prob])[0])
                    self.last_calibrated_per_over = calibrated_per_over
                if debug:
                    print(f"[CAL] Model probability: {model_prob:.1%}")
            
            # Get resource-based probability for constraint layer
            resource_prob = X['resource_win_prob'].iloc[0] if 'resource_win_prob' in X.columns else 0.5
            
            # Use calibrated model probability as the base (isotonic-calibrated = truth)
            # Per-over calibrator is most accurate, then phase, then innings-level
            if per_over_calibrator is not None:
                base_prob = self.last_calibrated_per_over
            elif phase_calibrator is not None:
                base_prob = self.last_calibrated_phase
            elif active_calibrator is not None:
                base_prob = calibrated_prob
            else:
                base_prob = raw_prob
            
            # --- PHASE×TARGET CALIBRATION (Inn2 only) ---
            # Chain: raw -> per-over isotonic -> phase×target isotonic
            # 9 segments: (PP/Mid/Death) × (below_par/on_par/above_par)
            self.last_calibrated_phase_target = base_prob
            if self.phase_target_calibrators and state.innings == 2:
                if current_over <= 6:
                    pt_phase = 'PP'
                elif current_over <= 15:
                    pt_phase = 'Mid'
                else:
                    pt_phase = 'Death'
                
                target_above_par = float(X['target_above_par'].iloc[0]) if 'target_above_par' in X.columns else 0.0
                if target_above_par < -15:
                    pt_tgt_cat = 'below_par'
                elif target_above_par <= 15:
                    pt_tgt_cat = 'on_par'
                else:
                    pt_tgt_cat = 'above_par'
                
                pt_key = f'{pt_phase}_{pt_tgt_cat}'
                calibrators_dict = self.phase_target_calibrators.get('calibrators', {})
                if pt_key in calibrators_dict:
                    pt_cal = calibrators_dict[pt_key]
                    calibrated_pt = float(pt_cal.predict([base_prob])[0])
                    self.last_calibrated_phase_target = calibrated_pt
                    if debug:
                        print(f"[PT_CAL] Phase×Target ({pt_key}): {base_prob:.1%} -> {calibrated_pt:.1%}")
                    base_prob = calibrated_pt
            
            # --- CONSTRAINT LAYER (Second Innings) ---
            # Principle: NEVER push probabilities upward beyond calibrated model output.
            # Only apply mathematical constraints and downward caps.
            # This preserves calibration integrity and makes evaluation straightforward.
            if state.innings == 2 and state.target_runs:
                runs_needed = state.target_runs - state.current_score
                balls_remaining = (self.format_config.total_overs - state.over) * 6 - state.ball
                wickets_remaining = 10 - state.wickets_lost
                rrr = runs_needed / (balls_remaining / 6) if balls_remaining > 0 else float('inf')
                
                # === MATHEMATICAL CONSTRAINTS (non-controversial) ===
                # Match already won
                if runs_needed <= 0:
                    prob = 1.0
                
                # Match already lost (no balls remaining)
                elif balls_remaining <= 0:
                    prob = 0.0

                # Match already lost (all out)
                elif wickets_remaining <= 0:
                    prob = 0.0
                
                # Mathematically impossible: Need more runs than max possible
                elif runs_needed > balls_remaining * 6:
                    prob = 0.0
                
                # === DOWNWARD CAPS ONLY (never boost) ===
                # Near-impossible: Need >5 runs per ball on average
                elif runs_needed > balls_remaining * 5:
                    prob = min(base_prob, 0.02)
                
                # Very difficult: Need >4 runs per ball on average  
                elif runs_needed > balls_remaining * 4:
                    prob = min(base_prob, 0.05)
                
                # Loss guardrails - cap optimism in bad situations
                elif resource_prob < 0.20:
                    # Game Over: No resources left = 0% win probability
                    if resource_prob == 0.0:
                        prob = 0.0
                    else:
                        # Cap: Model can't be much higher than resource_prob in dire situations
                        max_allowed = (resource_prob * 1.5) + 0.01
                        prob = min(base_prob, max_allowed)
                
                # Normal case: trust the calibrated model
                else:
                    prob = base_prob
            else:
                # First innings: trust the calibrated model
                prob = base_prob

            # --- SEGMENT-AWARE TEMPERATURE SHARPENING ---
            # Applied post-calibration. Only sharpen segments where T < 1.0 helps.
            # 16-match IPL 2026 holdout vs Betfair optimal T per segment:
            #   Inn1 PP=0.364, Inn1 Mid=1.06, Inn1 Death=0.97
            #   Inn2 PP=0.606, Inn2 Mid=0.327, Inn2 Death=1.07
            # Segments with optimal T ≥ 0.95 (Inn1 Mid/Death, Inn2 Death) left at T=1.0
            # to avoid sharpening where the model is already well-calibrated.
            # Segments needing sharpening use conservative T=0.75 (flat valley 0.65–0.90).
            _over_1b = state.over + 1
            _PROD_T = {
                'inn1_powerplay': 0.75,  # optimal 0.364 → conservative 0.75
                'inn1_middle':    1.00,  # optimal 1.06  → no sharpening (would hurt)
                'inn1_death':     1.00,  # optimal 0.97  → no sharpening
                'inn2_powerplay': 0.75,  # optimal 0.606 → conservative 0.75
                'inn2_middle':    0.75,  # optimal 0.327 → conservative 0.75
                'inn2_death':     1.00,  # optimal 1.07  → no sharpening (would hurt)
            }
            _SHADOW_T = {
                # Segment-specific T values — shadow mode only (tested on 16 matches).
                # Promote to production after ~30+ more matches confirm stability.
                'inn1_powerplay': 0.40,   # Only segment losing to market; strong sharpening
                'inn2_powerplay': 0.60,   # Stable across 12 & 16 match analyses
                'inn2_middle':    0.50,   # Conservative vs optimal 0.33–0.55 (noisy estimate)
            }
            # Determine segment
            if state.innings == 1:
                if _over_1b <= 6:
                    _seg = 'inn1_powerplay'
                elif _over_1b <= 15:
                    _seg = 'inn1_middle'
                else:
                    _seg = 'inn1_death'
            else:
                if _over_1b <= 6:
                    _seg = 'inn2_powerplay'
                elif _over_1b <= 15:
                    _seg = 'inn2_middle'
                else:
                    _seg = 'inn2_death'
            # Apply production T (no-op for segments where T=1.0)
            _prod_t = _PROD_T.get(_seg, 1.0)
            self.last_t_applied = _prod_t
            if _prod_t != 1.0 and 0.001 < prob < 0.999:
                _logit = np.log(prob / (1 - prob))
                prob = float(1 / (1 + np.exp(-_logit / _prod_t)))
            # Compute shadow prediction with aggressive segment-specific T (stored for logging only)
            _shadow_t_val = _SHADOW_T.get(_seg, 1.0)
            if _shadow_t_val != 1.0 and 0.001 < base_prob < 0.999:
                _sl = np.log(base_prob / (1 - base_prob))
                self.last_shadow_prob = float(1 / (1 + np.exp(-_sl / _shadow_t_val)))
            else:
                self.last_shadow_prob = prob  # Same as production for non-shadow segments

            # Apply league-specific calibrator if available
            # Chain: temperature scaling (sharpness) → logit bias (shift) 
            pre_league_prob = prob  # Save for debug output
            if self.league_calibrator:
                method = self.league_calibrator.get('method', 'temperature')
                calibrators = self.league_calibrator.get('calibrators', {})
                temperature_scalers = self.league_calibrator.get('temperature_scalers', {})
                innings_key = f'innings_{state.innings}'
                league_name = self.league_calibrator.get('league', 'unknown').upper()
                
                # Determine phase for phase-specific lookup
                phase_key = None
                over_1based = state.over + 1
                if over_1based <= 6:
                    phase = 'powerplay'
                elif over_1based <= 15:
                    phase = 'middle'
                else:
                    phase = 'death'
                if self.league_calibrator.get('phase_specific'):
                    phase_key = f'inn{state.innings}_{phase}'
                
                # Step 1: Phase-specific temperature scaling (adjusts sharpness)
                # T < 1 sharpens (more confident), T > 1 softens, T = 1 no change
                temp_key = f'inn{state.innings}_{phase}'
                T = temperature_scalers.get(temp_key, temperature_scalers.get(innings_key, None))
                if T is not None and T != 1.0 and prob > 0.001 and prob < 0.999:
                    pre_temp = prob
                    logit = np.log(prob / (1 - prob))
                    prob = float(1 / (1 + np.exp(-logit / T)))
                    if debug:
                        print(f"[LEAGUE] Temperature ({league_name}, {temp_key}, T={T:.2f}): {pre_temp:.1%} -> {prob:.1%}")
                
                # Step 2: LogitBias / scaler calibrators (adjusts mean/shift)
                scaler = None
                cal_label = None
                if calibrators and phase_key and phase_key in calibrators:
                    scaler = calibrators[phase_key]
                    cal_label = phase_key
                elif calibrators and innings_key in calibrators:
                    scaler = calibrators[innings_key]
                    cal_label = innings_key
                
                if scaler is not None and hasattr(scaler, 'predict'):
                    pre_bias = prob
                    prob = _coerce_probability_scalar(scaler.predict(np.array([[prob]])))
                    if debug:
                        print(f"[LEAGUE] LogitBias ({league_name}, {cal_label}): {pre_bias:.1%} -> {prob:.1%}")
                elif method == 'temperature' and not temperature_scalers:
                    # Legacy format: T1/T2 keys (only if no phase-specific T)
                    T = self.league_calibrator.get('T1' if state.innings == 1 else 'T2', 1.0)
                    if T and prob > 0.001 and prob < 0.999:
                        logit = np.log(prob / (1 - prob))
                        prob = 1 / (1 + np.exp(-logit / T))
                        if debug:
                            print(f"[LEAGUE] League ({league_name}, T={T:.2f}): {pre_league_prob:.1%} -> {prob:.1%}")
                elif method == 'platt':
                    # Legacy format: a1/b1/a2/b2 keys
                    a = self.league_calibrator.get('a1' if state.innings == 1 else 'a2', 1.0)
                    b = self.league_calibrator.get('b1' if state.innings == 1 else 'b2', 0.0)
                    if prob > 0.001 and prob < 0.999:
                        logit = np.log(prob / (1 - prob))
                        prob = 1 / (1 + np.exp(-(a * logit + b)))
                        if debug:
                            print(f"[LEAGUE] League ({league_name}, Platt): {pre_league_prob:.1%} -> {prob:.1%}")
            
            self.last_league_calibrated = float(prob) if self.league_calibrator else None
            
            # === INNINGS TRANSITION SMOOTHING ===
            # Store inn1 final probability for use as inn2 prior
            self.last_transition_alpha = None
            if state.innings == 1:
                self._inn1_final_prob = float(prob)
                self._inn1_batting_team = state.batting_team
            elif state.innings == 2 and self._inn1_final_prob is not None:
                overs_bowled = state.over + state.ball / 6.0
                if overs_bowled < self.INNINGS_TRANSITION_OVERS:
                    # Inn2 batting team is inn1 bowling team, so prior = 1 - inn1_prob
                    if self._inn1_batting_team == state.batting_team:
                        inn1_prior = self._inn1_final_prob
                    else:
                        inn1_prior = 1.0 - self._inn1_final_prob
                    
                    alpha = max(0.0, 1.0 - overs_bowled / self.INNINGS_TRANSITION_OVERS)
                    pre_blend = prob
                    prob = alpha * inn1_prior + (1.0 - alpha) * prob
                    self.last_transition_alpha = alpha
                    if debug:
                        print(f"[TRANSITION] Inn1 prior: {inn1_prior:.1%}, alpha: {alpha:.2f}, "
                              f"model: {pre_blend:.1%} -> blended: {prob:.1%}")

            terminal_clamp = self._second_innings_terminal_clamp(state)
            if terminal_clamp is not None:
                pre_clamp = prob
                prob = float(terminal_clamp["probability"])
                terminal_clamp["pre_clamp_probability"] = float(pre_clamp)
                self.last_terminal_clamp = terminal_clamp
                if debug:
                    print(
                        f"[TERMINAL] {terminal_clamp['reason']}: "
                        f"{pre_clamp:.1%} -> {prob:.1%}"
                    )
             
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

    def explain(self, state: MatchState) -> dict:
        """
        T020: Return per-feature contributions for a single prediction.

        Uses XGBoost's `predict(output_margin=True)` for the XGB component and
        LogReg coefficients × feature values for the LogReg component.
        Falls back to raw feature vector only if SHAP / XGBoost margin unavailable.

        Returns a dict with keys:
            win_probability  – final prediction
            features         – {name: value} dict of the feature vector
            contributions    – {name: contribution} sorted by abs value (XGB margin or LogReg)
            shap_values      – {name: shap_value} if the `shap` library is installed
        """
        import numpy as np

        # Hydrate features (reuse existing path)
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
            'runs_needed': (state.target_runs - state.current_score) if state.target_runs else 0,
        }
        X = self.feature_mapper.create_feature_dataframe(scraped_data)
        expected_features = None
        if hasattr(self.model, 'selected_features_'):
            expected_features = self.model.selected_features_
        elif hasattr(self.model, 'feature_names_in_'):
            expected_features = list(self.model.feature_names_in_)
        if expected_features:
            for feat in expected_features:
                if feat not in X.columns:
                    X[feat] = 0.0
            X = X[expected_features]

        win_prob = self.predict(state)
        feature_dict = {col: float(X[col].iloc[0]) for col in X.columns}

        contributions = {}
        shap_values = {}

        # Try XGBoost margin decomposition
        xgb_model = None
        if hasattr(self.model, 'xgb_model_'):
            xgb_model = self.model.xgb_model_
        elif hasattr(self.model, 'xgb_model'):
            xgb_model = self.model.xgb_model

        if xgb_model is not None:
            try:
                import xgboost as xgb
                dmat = xgb.DMatrix(X)
                margin = float(xgb_model.get_booster().predict(dmat, output_margin=True)[0])
                # Approximate per-feature contribution using XGBoost's predict_contribution
                contribs = xgb_model.get_booster().predict(dmat, pred_contribs=True)[0]
                feat_names = X.columns.tolist()
                contributions = {
                    feat_names[i]: round(float(contribs[i]), 5)
                    for i in range(len(feat_names))
                }
                # Sort by absolute contribution
                contributions = dict(
                    sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)
                )
            except Exception:
                pass

        # Try SHAP if installed
        try:
            import shap
            if xgb_model is not None:
                explainer = shap.TreeExplainer(xgb_model)
                sv = explainer.shap_values(X)
                feat_names = X.columns.tolist()
                shap_values = {feat_names[i]: round(float(sv[0][i]), 5) for i in range(len(feat_names))}
                shap_values = dict(sorted(shap_values.items(), key=lambda kv: abs(kv[1]), reverse=True))
        except Exception:
            pass

        return {
            "win_probability": round(win_prob, 4),
            "features": feature_dict,
            "contributions": contributions,
            "shap_values": shap_values,
        }

    def predict_batch(
        self, 
        states: list, 
        feature_context: Optional["FeatureContext"] = None,
        league: str = None
    ) -> np.ndarray:
        """
        Predict win probabilities for multiple MatchState objects in a single batch.
        
        This is optimized for Monte Carlo terminal state evaluation where we need
        to evaluate thousands of states efficiently. Uses fully vectorized feature
        generation and model prediction.
        
        CRITICAL: predict_batch() MUST NOT access FeatureStore directly; only via
        FeatureContext parameter. This prevents accidental re-introduction of slow
        per-state lookups.
        
        Supports both inference.schema.MatchState (with over/ball/current_score) and
        simulation.state.MatchState (with balls_remaining/score).
        
        Args:
            states: List of MatchState objects to evaluate
            feature_context: Optional FeatureContext with cached venue/team stats.
                If provided, uses real feature store values. If None, falls back to
                hardcoded defaults (simplified mode).
            league: Optional league code for league-specific calibration
            
        Returns:
            np.ndarray of win probabilities (one per state)
            
        Performance:
            ~100-170ms for 2000 states with FeatureContext (fully vectorized)
            ~50-100ms for 2000 states without FeatureContext (simplified mode)
        """
        if not states:
            return np.array([])
        
        # Determine feature mode for logging
        if feature_context:
            feature_mode = "full"
            logger.debug(
                "predict_batch using full features from FeatureContext",
                venue_avg_score=feature_context.venue_avg_score,
                team_a_wr=feature_context.team_a_wr,
                team_b_wr=feature_context.team_b_wr
            )
        else:
            feature_mode = "simplified"
            logger.warning(
                "predict_batch using simplified features (no FeatureContext provided)"
            )
        
        n = len(states)
        probs = np.zeros(n)
        
        # Extract state info into numpy arrays for vectorized processing
        scores = np.zeros(n, dtype=np.float64)
        wickets = np.zeros(n, dtype=np.int32)
        balls_remaining = np.zeros(n, dtype=np.int32)
        innings_arr = np.zeros(n, dtype=np.int32)
        targets = np.zeros(n, dtype=np.float64)
        overs = np.zeros(n, dtype=np.int32)
        balls = np.zeros(n, dtype=np.int32)
        
        for i, state in enumerate(states):
            innings_arr[i] = state.innings
            wickets[i] = state.wickets_lost
            targets[i] = state.target_runs if state.target_runs else 0
            
            if hasattr(state, 'current_score'):
                # Inference MatchState
                scores[i] = state.current_score
                overs[i] = state.over
                balls[i] = state.ball
                balls_remaining[i] = (self.format_config.total_overs - state.over) * 6 - state.ball
            else:
                # Simulation MatchState
                scores[i] = state.score
                balls_remaining[i] = state.balls_remaining
                balls_bowled = self.format_config.total_balls - state.balls_remaining
                overs[i] = balls_bowled // 6
                balls[i] = balls_bowled % 6
                if balls[i] == 0 and overs[i] > 0:
                    balls[i] = 6
                    overs[i] -= 1
                elif balls[i] == 0:
                    balls[i] = 1
        
        # Identify terminal states (vectorized)
        is_inn2 = innings_arr == 2
        runs_needed = targets - scores
        
        # Terminal conditions for innings 2
        already_won = is_inn2 & (runs_needed <= 0)
        no_resources = (balls_remaining <= 0) | (wickets >= 10)
        impossible = is_inn2 & (runs_needed > balls_remaining * 6)
        
        probs[already_won] = 1.0
        probs[is_inn2 & no_resources & (runs_needed > 0)] = 0.0
        probs[impossible] = 0.0
        
        # Terminal conditions for innings 1
        is_inn1 = innings_arr == 1
        inn1_terminal = is_inn1 & no_resources
        
        # For first innings terminal, use resource calculator (rare case)
        inn1_terminal_indices = np.where(inn1_terminal)[0]
        for i in inn1_terminal_indices:
            resource_features = self.resource_calculator.calculate_all_features(
                innings=int(innings_arr[i]),
                over=int(overs[i]),
                ball=int(balls[i]),
                current_score=int(scores[i]),
                wickets_lost=int(wickets[i]),
                target_runs=int(targets[i]) if targets[i] > 0 else None
            )
            probs[i] = resource_features['resource_win_prob']
        
        # Non-terminal states mask
        terminal_mask = already_won | (is_inn2 & no_resources) | impossible | inn1_terminal
        non_terminal_mask = ~terminal_mask
        non_terminal_indices = np.where(non_terminal_mask)[0]
        
        if len(non_terminal_indices) == 0:
            return probs
        
        # =========================================================================
        # FEATURE GENERATION USING ResourceFeatureCalculator
        # =========================================================================
        # CRITICAL: Use the same ResourceFeatureCalculator as predict() to ensure
        # feature consistency. This is slower than vectorized approximations but
        # guarantees identical features between predict() and predict_batch().
        #
        # The ~11pp gap was caused by simplified vectorized formulas that differed
        # from the calibrated DLS-based calculations in ResourceFeatureCalculator.
        # =========================================================================
        
        # Extract arrays for non-terminal states only
        nt_scores = scores[non_terminal_mask]
        nt_wickets = wickets[non_terminal_mask]
        nt_balls_remaining = balls_remaining[non_terminal_mask]
        nt_innings = innings_arr[non_terminal_mask]
        nt_targets = targets[non_terminal_mask]
        nt_overs = overs[non_terminal_mask]
        nt_balls = balls[non_terminal_mask]
        
        num_states = len(nt_scores)
        
        # Pre-allocate arrays for resource-based features (from ResourceFeatureCalculator)
        resource_win_prob = np.zeros(num_states)
        expected_final_score = np.zeros(num_states)
        resource_pct = np.zeros(num_states)
        pressure_index = np.zeros(num_states)
        is_powerplay = np.zeros(num_states)
        is_middle_overs = np.zeros(num_states)
        is_death_overs = np.zeros(num_states)
        current_run_rate = np.zeros(num_states)
        required_run_rate = np.zeros(num_states)
        overs_remaining = np.zeros(num_states)
        runs_required = np.zeros(num_states)
        
        # Calculate resource features using the same calculator as predict()
        for i in range(num_states):
            resource_features = self.resource_calculator.calculate_all_features(
                innings=int(nt_innings[i]),
                over=int(nt_overs[i]),
                ball=int(nt_balls[i]),
                current_score=int(nt_scores[i]),
                wickets_lost=int(nt_wickets[i]),
                target_runs=int(nt_targets[i]) if nt_targets[i] > 0 else None
            )
            
            # Extract all resource features to ensure consistency with predict()
            resource_win_prob[i] = resource_features['resource_win_prob']
            expected_final_score[i] = resource_features['expected_final_score']
            resource_pct[i] = resource_features['resource_pct']
            pressure_index[i] = resource_features['pressure_index']
            is_powerplay[i] = resource_features['is_powerplay']
            is_middle_overs[i] = resource_features['is_middle_overs']
            is_death_overs[i] = resource_features['is_death_overs']
            current_run_rate[i] = resource_features['current_run_rate']
            required_run_rate[i] = resource_features['required_run_rate']
            overs_remaining[i] = resource_features['overs_remaining']
            runs_required[i] = resource_features.get('runs_required', 0)
        
        # Derived features (can be vectorized since they use the calculator outputs)
        projected_score = expected_final_score  # alias
        wickets_remaining = 10 - nt_wickets
        dls_pressure_index = pressure_index  # alias
        
        # Run rate diff (vectorized from calculated run rates)
        # In innings 1, run_rate_diff = 0 (no target to compare to)
        run_rate_diff = np.where(nt_innings == 2, current_run_rate - required_run_rate, 0.0)
        # =========================================================================
        # VENUE STATS - Use FeatureContext if provided, else defaults
        # =========================================================================
        if feature_context:
            venue_avg_score = feature_context.venue_avg_score
            venue_bat_first_win_rate = feature_context.venue_bat_first_wr
        else:
            venue_avg_score = self.format_config.par_score
            venue_bat_first_win_rate = 0.45
        venue_avg_wickets = 6.5
        
        # Derived features (vectorized from calculator outputs)
        projected_vs_venue_avg = projected_score - venue_avg_score
        score_per_wicket = nt_scores / (nt_wickets + 1)
        wickets_times_balls = nt_wickets * (self.format_config.total_balls - nt_balls_remaining)
        rrr_times_wickets = required_run_rate * nt_wickets
        
        chase_difficulty = np.where(
            (nt_innings == 2) & (current_run_rate > 0.1),
            required_run_rate / (current_run_rate + 0.1),
            0.0
        )
        
        # Score vs par - use calculator-derived resource_pct for consistency
        resources_used = 100 - resource_pct
        par_at_point_inn2 = np.where(nt_targets > 0, nt_targets * (resources_used / 100.0), 0.0)
        score_vs_par_inn2 = nt_scores - par_at_point_inn2
        score_vs_par_inn1 = nt_scores - (venue_avg_score * (1 - resource_pct/100.0))
        score_vs_par = np.where(nt_innings == 2, score_vs_par_inn2, score_vs_par_inn1)
        
        # Computed resources
        crr_times_res = current_run_rate * resource_pct / 100.0
        resources_remaining = resource_pct / 100.0
        
        # =========================================================================
        # TEAM STATS - Use FeatureContext if provided, else fall back to state attrs/defaults
        # CRITICAL: predict_batch() MUST NOT access FeatureStore directly;
        # only via FeatureContext parameter.
        # =========================================================================
        batting_team_win_rates = np.zeros(num_states)
        bowling_team_win_rates = np.zeros(num_states)
        batting_team_situation_wrs = np.zeros(num_states)
        bowling_team_situation_wrs = np.zeros(num_states)
        
        if feature_context:
            # All states in batch have same teams (same MC call) - vectorized assignment
            batting_team_win_rates[:] = feature_context.team_a_wr
            bowling_team_win_rates[:] = feature_context.team_b_wr
            batting_team_situation_wrs[:] = feature_context.batting_situation_wr
            bowling_team_situation_wrs[:] = feature_context.bowling_situation_wr
        else:
            # Fallback to state attributes or defaults (simplified mode)
            for i, idx in enumerate(non_terminal_indices):
                state = states[idx]
                batting_team_win_rates[i] = getattr(state, 'batting_team_win_rate', 0.5)
                bowling_team_win_rates[i] = getattr(state, 'bowling_team_win_rate', 0.5)
                batting_team_situation_wrs[i] = getattr(state, 'batting_team_situation_wr', batting_team_win_rates[i])
                bowling_team_situation_wrs[i] = getattr(state, 'bowling_team_situation_wr', bowling_team_win_rates[i])
        
        team_strength_diff = batting_team_win_rates - bowling_team_win_rates
        situation_advantage = batting_team_situation_wrs - bowling_team_situation_wrs
        
        # Player rolling stats (defaults)
        batsman_rolling_avg = 25.0
        batsman_rolling_sr = 130.0
        bowler_rolling_econ = 8.0
        bowler_rolling_sr = 20.0
        
        # Player venue/vs-team stats (defaults)
        batsman_venue_avg = 38.0
        batsman_venue_sr = 61.0
        batsman_vs_team_avg = 31.5
        bowler_venue_econ = 4.2
        bowler_venue_sr = 516.0
        bowler_vs_team_econ = 5.7
        batting_pair_strength = 50.0
        
        # Recent form (defaults for Monte Carlo)
        runs_last_12 = 12.0
        runs_last_18 = 18.0
        wickets_last_12 = 0.5
        boundary_pct_last_18 = 0.15
        wickets_last_30 = 1.0
        dot_pct_last_12 = 0.35
        wickets_last_6 = 0.25
        set_batter_exposure = 20.0
        balls_since_wicket = 12.0
        acceleration_potential = 15.0
        score_vs_venue_over_par = 0.0  # MC simulates terminal state; 0.0 is neutral default
        batting_team_venue_wr = 0.5
        batting_recent_nrr_l5 = 0.0
        is_low_target = 0.0
        crr_times_res = current_run_rate * resource_pct / 100.0
        resources_remaining = resource_pct / 100.0
        
        # Build feature DataFrame (vectorized)
        feature_dict = {
            'expected_final_score': expected_final_score,
            'resource_win_prob': resource_win_prob,
            'score_vs_par': score_vs_par,
            'dls_pressure_index': dls_pressure_index,
            'projected_vs_venue_avg': projected_vs_venue_avg,
            'projected_score': projected_score,
            'is_powerplay': is_powerplay,
            'score_per_wicket': score_per_wicket,
            'run_rate_diff': run_rate_diff,
            'required_run_rate': required_run_rate,
            'chase_difficulty': chase_difficulty,
            'wickets_times_balls': wickets_times_balls,
            'pressure_index': pressure_index,
            'team_strength_diff': team_strength_diff,
            'rrr_times_wickets': rrr_times_wickets,
            'overs_remaining': overs_remaining,
            'batting_team_win_rate': batting_team_win_rates,
            'bowling_team_win_rate': bowling_team_win_rates,
            'batting_team_situation_wr': batting_team_situation_wrs,
            'situation_advantage': situation_advantage,
            'boundary_pct_last_18': np.full(num_states, boundary_pct_last_18),
            'bowling_team_situation_wr': bowling_team_situation_wrs,
            'runs_last_12': np.full(num_states, runs_last_12),
            'runs_last_18': np.full(num_states, runs_last_18),
            'wickets_last_12': np.full(num_states, wickets_last_12),
            'dot_pct_last_12': np.full(num_states, dot_pct_last_12),
            'set_batter_exposure': np.full(num_states, set_batter_exposure),
            'balls_since_wicket': np.full(num_states, balls_since_wicket),
            'wickets_last_6': np.full(num_states, wickets_last_6),
            'batsman_venue_avg': np.full(num_states, batsman_venue_avg),
            'batsman_venue_sr': np.full(num_states, batsman_venue_sr),
            'batsman_vs_team_avg': np.full(num_states, batsman_vs_team_avg),
            'bowler_venue_econ': np.full(num_states, bowler_venue_econ),
            'bowler_venue_sr': np.full(num_states, bowler_venue_sr),
            'bowler_vs_team_econ': np.full(num_states, bowler_vs_team_econ),
            'batting_pair_strength': np.full(num_states, batting_pair_strength),
            'acceleration_potential': np.full(num_states, acceleration_potential),
            'wickets_last_30': np.full(num_states, wickets_last_30),
            'crr_times_res': crr_times_res,
            'resources_remaining': resources_remaining,
            'innings': nt_innings.astype(float),
            'over': nt_overs.astype(float),
            'ball': nt_balls.astype(float),
            'current_score': nt_scores,
            'wickets_lost': nt_wickets.astype(float),
            'batsman_rolling_avg': np.full(num_states, batsman_rolling_avg),
            'batsman_rolling_sr': np.full(num_states, batsman_rolling_sr),
            'bowler_rolling_econ': np.full(num_states, bowler_rolling_econ),
            'bowler_rolling_sr': np.full(num_states, bowler_rolling_sr),
            'venue_avg_score': np.full(num_states, venue_avg_score),
            'venue_avg_wickets': np.full(num_states, venue_avg_wickets),
            'venue_bat_first_win_rate': np.full(num_states, venue_bat_first_win_rate),
            'balls_remaining': nt_balls_remaining.astype(float),
            'wickets_remaining': wickets_remaining.astype(float),
            'resource_pct': resource_pct,
            'current_run_rate': current_run_rate,
            'runs_required': runs_required,
            'is_middle_overs': is_middle_overs,
            'is_death_overs': is_death_overs,
            'score_vs_venue_over_par': np.full(num_states, score_vs_venue_over_par),
            'batting_team_venue_wr': np.full(num_states, batting_team_venue_wr),
            'batting_recent_nrr_l5': np.full(num_states, batting_recent_nrr_l5),
            'is_low_target': np.full(num_states, is_low_target),
        }
        
        X = pd.DataFrame(feature_dict)
        
        # Get expected features from model
        expected_features = None
        if hasattr(self.model, 'feature_names_in_'):
            expected_features = list(self.model.feature_names_in_)
        elif hasattr(self.model, 'selected_features_'):
            expected_features = self.model.selected_features_
        elif hasattr(self.model, 'get_booster'):
            try:
                expected_features = self.model.get_booster().feature_names
            except:
                pass
        
        # Align features
        if expected_features:
            for feat in expected_features:
                if feat not in X.columns:
                    if 'rate' in feat.lower() or 'avg' in feat.lower():
                        X[feat] = 0.0
                    elif 'is_' in feat:
                        X[feat] = 0
                    elif 'pct' in feat or 'prob' in feat:
                        X[feat] = 0.5
                    else:
                        X[feat] = 0.0
            X = X[expected_features]
        
        # =========================================================================
        # BATCH MODEL PREDICTION
        # =========================================================================
        raw_probs = self.model.predict_proba(X)[:, 1]
        
        # =========================================================================
        # VECTORIZED CALIBRATION
        # =========================================================================
        calibrated_probs = self._apply_calibration_batch(
            raw_probs, nt_innings, nt_overs, league
        )
        
        # =========================================================================
        # CONSTRAINT LAYER (Second Innings) - Match main predict() constraints
        # =========================================================================
        # Skip constraint layer for T20 International - use raw model output
        # The simplified batch features don't match main predictor's resource_win_prob
        is_t20i = league and league.lower() in ['t20i', 't20_international', 't20international']
        
        if not is_t20i:
            # Apply the same caps as main predictor to ensure consistent behavior
            # Only apply downward caps, never boost probabilities
            
            # Calculate runs per ball needed for each 2nd innings state
            is_inn2_nt = nt_innings == 2
            runs_needed_nt = nt_targets - nt_scores
            
            # Near-impossible: Need >5 runs per ball on average
            near_impossible = is_inn2_nt & (runs_needed_nt > nt_balls_remaining * 5)
            calibrated_probs[near_impossible] = np.minimum(calibrated_probs[near_impossible], 0.02)
            
            # Very difficult: Need >4 runs per ball on average
            very_difficult = is_inn2_nt & (runs_needed_nt > nt_balls_remaining * 4) & (~near_impossible)
            calibrated_probs[very_difficult] = np.minimum(calibrated_probs[very_difficult], 0.05)
            
            # Loss guardrails - cap optimism in high RRR situations
            # Use a more aggressive cap based on runs per ball needed
            runs_per_ball = np.where(nt_balls_remaining > 0, runs_needed_nt / nt_balls_remaining, 0)
            
            # RRR > 2 (need >12 per over): Apply significant cap
            high_rrr = is_inn2_nt & (runs_per_ball > 2.0) & (~near_impossible) & (~very_difficult)
            if np.any(high_rrr):
                # Cap at approximately what resource_win_prob would give
                # Formula: base_cap = max(0.02, 0.5 * (1 - (rrr - 6) / 10) * (1 - wickets/10))
                rpb = runs_per_ball[high_rrr]
                wkts = nt_wickets[high_rrr]
                rrr_factor = np.clip(1.0 - (rpb * 6 - 8.0) / 10.0, 0.0, 1.0)
                wicket_factor = 1.0 - 0.08 * wkts
                max_cap = np.clip(rrr_factor * wicket_factor * 0.2, 0.01, 0.15)  # Conservative cap
                calibrated_probs[high_rrr] = np.minimum(calibrated_probs[high_rrr], max_cap)
        
        # Assign results
        probs[non_terminal_mask] = calibrated_probs
        
        return probs
    
    def _apply_calibration_batch(
        self, 
        raw_probs: np.ndarray, 
        innings_arr: np.ndarray, 
        overs_arr: np.ndarray,
        league: str = None
    ) -> np.ndarray:
        """
        Apply calibration to batch of predictions (vectorized where possible).
        
        Args:
            raw_probs: Raw model probabilities
            innings_arr: Innings for each prediction
            overs_arr: Over number for each prediction (0-indexed)
            league: Optional league for league-specific calibration
            
        Returns:
            Calibrated probabilities
        """
        n = len(raw_probs)
        calibrated = raw_probs.copy()
        
        # T20 International: Skip calibration, use raw model output
        # The raw model is better calibrated for diverse international conditions
        if league and league.lower() in ['t20i', 't20_international', 't20international']:
            logger.debug(
                "Skipping calibration for T20 International",
                league=league,
                n_predictions=n,
                raw_mean=np.mean(raw_probs)
            )
            return calibrated
        
        # Determine phase for each prediction
        current_over_1based = overs_arr + 1
        
        # Group by calibrator key for efficient batch processing
        if self.per_over_calibrators:
            # Per-over calibration (most granular), with phase fallback
            # Track which predictions haven't been calibrated yet for phase fallback
            calibrated_mask = np.zeros(n, dtype=bool)
            
            for over in range(1, 21):
                for inn in [1, 2]:
                    key = f'inn{inn}_over{over}'
                    mask = (innings_arr == inn) & (current_over_1based == over)
                    if key in self.per_over_calibrators:
                        if np.any(mask):
                            calibrator = self.per_over_calibrators[key]
                            calibrated[mask] = calibrator.predict(raw_probs[mask])
                            calibrated_mask[mask] = True
                    elif self.phase_calibrators:
                        # Fallback to phase calibrator for missing per-over calibrators
                        if np.any(mask):
                            # Determine phase for this over
                            if over <= 6:
                                phase = 'powerplay'
                            elif over <= 15:
                                phase = 'middle'
                            else:
                                phase = 'death'
                            phase_key = f'inn{inn}_{phase}'
                            if phase_key in self.phase_calibrators:
                                phase_calibrator = self.phase_calibrators[phase_key]
                                calibrated[mask] = phase_calibrator.predict(raw_probs[mask])
                                calibrated_mask[mask] = True
        elif self.phase_calibrators:
            # Phase calibration
            for inn in [1, 2]:
                for phase, over_range in [('powerplay', (1, 6)), ('middle', (7, 15)), ('death', (16, 20))]:
                    key = f'inn{inn}_{phase}'
                    if key in self.phase_calibrators:
                        mask = (innings_arr == inn) & (current_over_1based >= over_range[0]) & (current_over_1based <= over_range[1])
                        if np.any(mask):
                            calibrator = self.phase_calibrators[key]
                            calibrated[mask] = calibrator.predict(raw_probs[mask])
        elif self.calibrator_inn1 is not None or self.calibrator_inn2 is not None:
            # Innings-specific calibration
            if self.calibrator_inn1 is not None:
                mask = innings_arr == 1
                if np.any(mask):
                    calibrated[mask] = self.calibrator_inn1.predict(raw_probs[mask])
            if self.calibrator_inn2 is not None:
                mask = innings_arr == 2
                if np.any(mask):
                    calibrated[mask] = self.calibrator_inn2.predict(raw_probs[mask])
        elif self.calibrator is not None:
            # Single calibrator
            calibrated = self.calibrator.predict(raw_probs)
        
        # Segment-aware temperature sharpening (before league calibration).
        # Only sharpen Inn1 PP, Inn2 PP, Inn2 Mid — segments with optimal T < 0.95.
        # Inn1 Mid (opt 1.06), Inn1 Death (opt 0.97), Inn2 Death (opt 1.07) left at T=1.0.
        _PROD_T_SEGS = [
            (1, 1,  6, 0.75),   # Inn1 PP
            (1, 7, 15, 1.00),   # Inn1 Mid  — no sharpening
            (1, 16, 20, 1.00),  # Inn1 Death — no sharpening
            (2, 1,  6, 0.75),   # Inn2 PP
            (2, 7, 15, 0.75),   # Inn2 Mid
            (2, 16, 20, 1.00),  # Inn2 Death — no sharpening
        ]
        for inn, ov_min, ov_max, t_val in _PROD_T_SEGS:
            if t_val == 1.0:
                continue
            mask = (
                (innings_arr == inn) &
                (current_over_1based >= ov_min) &
                (current_over_1based <= ov_max) &
                (calibrated > 0.001) & (calibrated < 0.999)
            )
            if np.any(mask):
                _logits = np.log(calibrated[mask] / (1 - calibrated[mask]))
                calibrated[mask] = 1 / (1 + np.exp(-_logits / t_val))

        if self.league_calibrator:
            method = self.league_calibrator.get('method', 'temperature')
            calibrators = self.league_calibrator.get('calibrators', {})
            is_phase_specific = self.league_calibrator.get('phase_specific', False)
            
            # Phase-specific Platt: apply per innings×phase segment
            if is_phase_specific and calibrators:
                for inn in [1, 2]:
                    for phase, over_range in [('powerplay', (1, 6)), ('middle', (7, 15)), ('death', (16, 20))]:
                        phase_key = f'inn{inn}_{phase}'
                        innings_key = f'innings_{inn}'
                        mask = (innings_arr == inn) & (current_over_1based >= over_range[0]) & (current_over_1based <= over_range[1])
                        if not np.any(mask):
                            continue
                        scaler = calibrators.get(phase_key) or calibrators.get(innings_key)
                        if scaler is not None and hasattr(scaler, 'predict'):
                            calibrated[mask] = scaler.predict(calibrated[mask].reshape(-1, 1)).flatten()
            else:
                for inn in [1, 2]:
                    mask = innings_arr == inn
                    if not np.any(mask):
                        continue
                    
                    innings_key = f'innings_{inn}'
                    
                    if calibrators and innings_key in calibrators:
                        scaler = calibrators[innings_key]
                        if hasattr(scaler, 'predict'):
                            calibrated[mask] = scaler.predict(calibrated[mask].reshape(-1, 1)).flatten()
                    elif method == 'temperature':
                        T = self.league_calibrator.get(f'T{inn}', 1.0)
                        if T and T != 1.0:
                            p = calibrated[mask]
                            p = np.clip(p, 0.001, 0.999)
                            logit = np.log(p / (1 - p))
                            calibrated[mask] = 1.0 / (1.0 + np.exp(-logit / T))
        
        return calibrated
