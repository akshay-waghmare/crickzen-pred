"""
League-Specific Calibration Module

Implements the recommended approach:
1. Global model trained on all T20s (frozen)
2. League adaptation via Temperature/Platt scaling (not isotonic - too steppy)
3. Innings-wise calibrators for stability
4. Detailed logging by date/innings/phase for monitoring

Usage:
    from bbl_pipeline.training.league_calibrator import LeagueCalibrator
    
    calibrator = LeagueCalibrator(global_model, method='temperature')
    calibrator.fit(league_data, league='bbl')
    calibrated_probs = calibrator.predict(new_data)
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from scipy.optimize import minimize
from typing import Dict, Optional, Tuple, Any
import joblib
from pathlib import Path
import structlog
from datetime import datetime

logger = structlog.get_logger()


class TemperatureScaler:
    """
    Temperature scaling calibrator.
    Divides logits by temperature T before sigmoid.
    T > 1: softer predictions (move toward 0.5)
    T < 1: sharper predictions (move toward 0/1)
    """
    def __init__(self):
        self.temperature = 1.0
        
    def fit(self, probs: np.ndarray, y_true: np.ndarray) -> 'TemperatureScaler':
        """Fit temperature using NLL minimization."""
        # Convert probs to logits
        probs = np.clip(probs, 1e-7, 1 - 1e-7)
        logits = np.log(probs / (1 - probs))
        
        def nll_loss(T):
            scaled_logits = logits / T[0]
            scaled_probs = 1 / (1 + np.exp(-scaled_logits))
            scaled_probs = np.clip(scaled_probs, 1e-7, 1 - 1e-7)
            return -np.mean(y_true * np.log(scaled_probs) + (1 - y_true) * np.log(1 - scaled_probs))
        
        result = minimize(nll_loss, [1.0], bounds=[(0.1, 10.0)], method='L-BFGS-B')
        self.temperature = result.x[0]
        return self
        
    def predict(self, probs: np.ndarray) -> np.ndarray:
        """Apply temperature scaling."""
        probs = np.clip(probs, 1e-7, 1 - 1e-7)
        logits = np.log(probs / (1 - probs))
        scaled_logits = logits / self.temperature
        return 1 / (1 + np.exp(-scaled_logits))


class PlattScaler:
    """
    Platt scaling calibrator.
    Fits logistic regression: calibrated_p = sigmoid(a * logit(p) + b)
    """
    def __init__(self):
        self.model = LogisticRegression(solver='lbfgs', max_iter=1000)
        
    def fit(self, probs: np.ndarray, y_true: np.ndarray) -> 'PlattScaler':
        """Fit Platt scaling."""
        probs = np.clip(probs, 1e-7, 1 - 1e-7)
        logits = np.log(probs / (1 - probs)).reshape(-1, 1)
        self.model.fit(logits, y_true)
        return self
        
    def predict(self, probs: np.ndarray) -> np.ndarray:
        """Apply Platt scaling."""
        probs = np.clip(probs, 1e-7, 1 - 1e-7)
        logits = np.log(probs / (1 - probs)).reshape(-1, 1)
        return self.model.predict_proba(logits)[:, 1]


class LeagueCalibrator:
    """
    League-specific calibration using the global model.
    
    Architecture:
        Global Model (frozen) → Raw Predictions → League Calibrator → Final Predictions
    
    Recommended: Temperature/Platt scaling with innings-wise calibrators.
    """
    
    def __init__(
        self, 
        method: str = 'temperature',  # 'temperature', 'platt'
        innings_specific: bool = True,
        phase_specific: bool = False  # Only if enough data
    ):
        self.method = method
        self.innings_specific = innings_specific
        self.phase_specific = phase_specific
        
        self.calibrators: Dict[str, Any] = {}
        self.metrics_log: Dict[str, Any] = {}
        self.league = None
        self.fitted = False
        
    def _create_calibrator(self):
        """Factory for calibrator type."""
        if self.method == 'temperature':
            return TemperatureScaler()
        elif self.method == 'platt':
            return PlattScaler()
        else:
            raise ValueError(f"Unknown method: {self.method}")
    
    def fit(
        self, 
        df: pd.DataFrame, 
        raw_probs: np.ndarray,
        y_true: np.ndarray,
        league: str,
        min_samples: int = 500
    ) -> 'LeagueCalibrator':
        """
        Fit league-specific calibrators.
        
        Args:
            df: DataFrame with 'innings', 'phase', 'date' columns
            raw_probs: Raw predictions from global model
            y_true: True labels (is_winner)
            league: League identifier
            min_samples: Minimum samples per segment
        """
        self.league = league
        logger.info("fitting_league_calibrator", league=league, method=self.method, 
                   samples=len(df), innings_specific=self.innings_specific)
        
        if self.innings_specific:
            # Fit separate calibrators for each innings
            for innings in [1, 2]:
                mask = df['innings'] == innings
                if mask.sum() < min_samples:
                    logger.warning("insufficient_samples", innings=innings, samples=mask.sum())
                    # Use global calibrator as fallback
                    cal = self._create_calibrator()
                    cal.fit(raw_probs, y_true)
                    self.calibrators[f'innings_{innings}'] = cal
                else:
                    cal = self._create_calibrator()
                    cal.fit(raw_probs[mask], y_true[mask])
                    self.calibrators[f'innings_{innings}'] = cal
                    logger.info("fitted_innings_calibrator", innings=innings, 
                               samples=mask.sum(), 
                               temperature=getattr(cal, 'temperature', None))
                    
            if self.phase_specific:
                # Optional: phase-specific calibrators if enough data
                for innings in [1, 2]:
                    for phase in ['powerplay', 'middle', 'death']:
                        key = f'inn{innings}_{phase}'
                        mask = (df['innings'] == innings) & (df['phase'] == phase)
                        if mask.sum() >= min_samples:
                            cal = self._create_calibrator()
                            cal.fit(raw_probs[mask], y_true[mask])
                            self.calibrators[key] = cal
                            logger.info("fitted_phase_calibrator", key=key, samples=mask.sum())
        else:
            # Single calibrator for entire league
            cal = self._create_calibrator()
            cal.fit(raw_probs, y_true)
            self.calibrators['global'] = cal
            
        self.fitted = True
        
        # Log metrics
        self._log_metrics(df, raw_probs, y_true)
        
        return self
    
    def predict(self, df: pd.DataFrame, raw_probs: np.ndarray) -> np.ndarray:
        """
        Apply league calibration to raw predictions.
        
        Routing priority (when phase_specific=True):
            1. Phase-specific calibrator (e.g. inn1_powerplay)
            2. Innings-level calibrator (e.g. innings_1)
            3. Identity fallback (return raw probability)
        
        Args:
            df: DataFrame with 'innings' (and optionally 'phase') columns
            raw_probs: Raw predictions from global model
            
        Returns:
            Calibrated probabilities
        """
        if not self.fitted:
            raise RuntimeError("Calibrator not fitted. Call fit() first.")
            
        calibrated = raw_probs.copy()
        
        if self.innings_specific and self.phase_specific and 'phase' in df.columns:
            # Phase-specific routing (batched by unique innings×phase)
            for innings in [1, 2]:
                for phase in df['phase'].dropna().unique():
                    mask = (df['innings'] == innings) & (df['phase'] == phase)
                    if not mask.any():
                        continue
                    
                    phase_key = f"inn{innings}_{phase}"
                    innings_key = f"innings_{innings}"
                    
                    if phase_key in self.calibrators:
                        calibrated[mask] = self.calibrators[phase_key].predict(raw_probs[mask])
                    elif innings_key in self.calibrators:
                        calibrated[mask] = self.calibrators[innings_key].predict(raw_probs[mask])
                    # else: identity fallback (raw_probs already copied)
                
                # Handle rows with this innings but missing phase
                no_phase_mask = (df['innings'] == innings) & (df['phase'].isna())
                if no_phase_mask.any():
                    innings_key = f"innings_{innings}"
                    if innings_key in self.calibrators:
                        calibrated[no_phase_mask] = self.calibrators[innings_key].predict(
                            raw_probs[no_phase_mask]
                        )
        elif self.innings_specific:
            for innings in [1, 2]:
                mask = df['innings'] == innings
                if not mask.any():
                    continue
                    
                cal_key = f'innings_{innings}'
                if cal_key in self.calibrators:
                    calibrated[mask] = self.calibrators[cal_key].predict(raw_probs[mask])
        else:
            calibrated = self.calibrators['global'].predict(raw_probs)
            
        return calibrated
    
    def _log_metrics(self, df: pd.DataFrame, raw_probs: np.ndarray, y_true: np.ndarray):
        """
        Log detailed metrics by date/innings/phase for monitoring.
        This is the key to knowing if calibration is working.
        """
        from sklearn.metrics import brier_score_loss, log_loss
        
        metrics = {
            'league': self.league,
            'method': self.method,
            'fitted_at': datetime.now().isoformat(),
            'overall': {},
            'by_innings': {},
            'by_phase': {},
            'by_date': []
        }
        
        # Overall metrics
        calibrated = self.predict(df, raw_probs)
        metrics['overall'] = {
            'brier_raw': float(brier_score_loss(y_true, raw_probs)),
            'brier_calibrated': float(brier_score_loss(y_true, calibrated)),
            'logloss_raw': float(log_loss(y_true, np.clip(raw_probs, 1e-7, 1-1e-7))),
            'logloss_calibrated': float(log_loss(y_true, np.clip(calibrated, 1e-7, 1-1e-7))),
            'samples': len(y_true)
        }
        
        # By innings
        for innings in [1, 2]:
            mask = df['innings'] == innings
            if mask.sum() > 0:
                cal_probs = calibrated[mask]
                metrics['by_innings'][f'innings_{innings}'] = {
                    'brier_raw': float(brier_score_loss(y_true[mask], raw_probs[mask])),
                    'brier_calibrated': float(brier_score_loss(y_true[mask], cal_probs)),
                    'logloss_raw': float(log_loss(y_true[mask], np.clip(raw_probs[mask], 1e-7, 1-1e-7))),
                    'logloss_calibrated': float(log_loss(y_true[mask], np.clip(cal_probs, 1e-7, 1-1e-7))),
                    'samples': int(mask.sum())
                }
        
        # By phase
        if 'phase' in df.columns:
            for phase in df['phase'].dropna().unique():
                mask = df['phase'] == phase
                if mask.sum() > 100:
                    cal_probs = calibrated[mask]
                    metrics['by_phase'][phase] = {
                        'brier_raw': float(brier_score_loss(y_true[mask], raw_probs[mask])),
                        'brier_calibrated': float(brier_score_loss(y_true[mask], cal_probs)),
                        'logloss_raw': float(log_loss(y_true[mask], np.clip(raw_probs[mask], 1e-7, 1-1e-7))),
                        'logloss_calibrated': float(log_loss(y_true[mask], np.clip(cal_probs, 1e-7, 1-1e-7))),
                        'samples': int(mask.sum())
                    }
        
        # By date (for temporal monitoring)
        if 'date' in df.columns:
            df_with_preds = df.copy()
            df_with_preds['raw_prob'] = raw_probs
            df_with_preds['cal_prob'] = calibrated
            df_with_preds['y_true'] = y_true
            
            # Group by month for cleaner analysis
            df_with_preds['month'] = pd.to_datetime(df_with_preds['date']).dt.to_period('M')
            
            for month, group in df_with_preds.groupby('month'):
                if len(group) > 50:
                    metrics['by_date'].append({
                        'month': str(month),
                        'brier_raw': float(brier_score_loss(group['y_true'], group['raw_prob'])),
                        'brier_calibrated': float(brier_score_loss(group['y_true'], group['cal_prob'])),
                        'logloss_raw': float(log_loss(group['y_true'], np.clip(group['raw_prob'], 1e-7, 1-1e-7))),
                        'logloss_calibrated': float(log_loss(group['y_true'], np.clip(group['cal_prob'], 1e-7, 1-1e-7))),
                        'samples': len(group)
                    })
        
        self.metrics_log = metrics
        
        # Log summary
        logger.info("calibration_metrics",
                   league=self.league,
                   brier_improvement=f"{(1 - metrics['overall']['brier_calibrated']/metrics['overall']['brier_raw'])*100:.1f}%",
                   logloss_improvement=f"{(1 - metrics['overall']['logloss_calibrated']/metrics['overall']['logloss_raw'])*100:.1f}%")
    
    def save(self, path: Path):
        """Save calibrator and metrics."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        # Save calibrators
        joblib.dump({
            'method': self.method,
            'league': self.league,
            'innings_specific': self.innings_specific,
            'phase_specific': self.phase_specific,
            'calibrators': self.calibrators,
            'fitted': self.fitted
        }, path / 'league_calibrator.pkl')
        
        # Save metrics log as JSON
        import json
        with open(path / 'calibration_metrics.json', 'w') as f:
            json.dump(self.metrics_log, f, indent=2, default=str)
            
        logger.info("saved_league_calibrator", path=str(path))
    
    @classmethod
    def load(cls, path: Path) -> 'LeagueCalibrator':
        """Load calibrator from path."""
        path = Path(path)
        data = joblib.load(path / 'league_calibrator.pkl')
        
        cal = cls(
            method=data['method'],
            innings_specific=data['innings_specific'],
            phase_specific=data.get('phase_specific', False)
        )
        cal.league = data['league']
        cal.calibrators = data['calibrators']
        cal.fitted = data['fitted']
        
        # Load metrics if available
        metrics_path = path / 'calibration_metrics.json'
        if metrics_path.exists():
            import json
            with open(metrics_path) as f:
                cal.metrics_log = json.load(f)
                
        return cal
    
    def export_oof_format(self, model_dir: Path, feature_columns: list = None):
        """
        Export calibrators in OOF-compatible format for Streamlit app.
        
        Creates isotonic_calibrator.pkl with the same structure as generate-oof:
        - calibrator_innings1, calibrator_innings2
        - calibrator_combined
        - phase_calibrators (if phase_specific)
        - Metrics and metadata
        """
        from datetime import datetime
        
        model_dir = Path(model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Build OOF-compatible structure
        oof_data = {
            'type': f'league_{self.method}_innings_specific',
            'method': self.method,
            'league': self.league,
            'created_date': datetime.now().isoformat(),
            'n_features': len(feature_columns) if feature_columns else 25,
            'features': feature_columns or [],
        }
        
        # Add innings calibrators
        if 'innings_1' in self.calibrators:
            oof_data['calibrator_innings1'] = self.calibrators['innings_1']
        if 'innings_2' in self.calibrators:
            oof_data['calibrator_innings2'] = self.calibrators['innings_2']
        
        # Combined calibrator (use innings_1 as fallback)
        oof_data['calibrator_combined'] = self.calibrators.get('innings_1') or self.calibrators.get('global')
        
        # Add metrics from log
        if self.metrics_log:
            overall = self.metrics_log.get('overall', {})
            oof_data['oof_brier_raw'] = overall.get('brier_raw', 0)
            oof_data['oof_brier_calibrated'] = overall.get('brier_calibrated', 0)
            oof_data['oof_ece_raw'] = 0  # Not computed for temp/platt
            oof_data['oof_ece_calibrated'] = 0
            
            # Innings metrics
            by_innings = self.metrics_log.get('by_innings', {})
            if 'innings_1' in by_innings:
                oof_data['innings1_metrics'] = by_innings['innings_1']
            if 'innings_2' in by_innings:
                oof_data['innings2_metrics'] = by_innings['innings_2']
        
        # Phase calibrators (if available)
        phase_cals = {}
        for key, cal in self.calibrators.items():
            if key.startswith('inn'):
                phase_cals[key] = cal
        if phase_cals:
            oof_data['phase_calibrators'] = phase_cals
            oof_data['phase_metrics'] = self.metrics_log.get('by_phase', {})
        
        # Save in OOF format
        output_path = model_dir / 'isotonic_calibrator.pkl'
        joblib.dump(oof_data, output_path)
        
        logger.info("exported_oof_format", path=str(output_path), 
                   type=oof_data['type'], league=self.league)
        
        return output_path


def calibrate_for_league(
    global_model,
    training_data: pd.DataFrame,
    league: str,
    output_dir: Path,
    method: str = 'temperature',
    feature_columns: list = None
) -> Dict[str, Any]:
    """
    Convenience function to calibrate a global model for a specific league.
    
    This implements the recommended approach:
    1. Freeze global model
    2. Run predictions on league data
    3. Fit Temperature/Platt on that league only
    4. Save global+league calibrator
    
    Args:
        global_model: Trained XGBLogRegEnsemble or similar
        training_data: DataFrame with features, 'innings', 'is_winner', optionally 'phase', 'date', 'league'
        league: League to calibrate for (filters data if 'league' column exists)
        output_dir: Where to save calibrators
        method: 'temperature' or 'platt'
        feature_columns: List of feature columns for prediction
        
    Returns:
        Dict with calibrator and metrics
    """
    output_dir = Path(output_dir)
    
    # Filter to league if needed
    if 'league' in training_data.columns:
        league_data = training_data[training_data['league'] == league].copy()
    else:
        league_data = training_data.copy()
        
    if len(league_data) < 500:
        logger.warning("low_sample_count", league=league, samples=len(league_data),
                      message="Consider using more data or temperature dampening")
    
    # Get raw predictions from global model
    if feature_columns is None:
        # Use model's feature columns if available
        feature_columns = getattr(global_model, 'feature_columns_', None)
        if feature_columns is None:
            raise ValueError("Must provide feature_columns")
    
    X = league_data[feature_columns].values
    raw_probs = global_model.predict_proba(X)[:, 1]
    y_true = league_data['is_winner'].values
    
    # Fit league calibrator
    calibrator = LeagueCalibrator(method=method, innings_specific=True)
    calibrator.fit(league_data, raw_probs, y_true, league)
    
    # Save
    league_output = output_dir / f'{league}_calibrator'
    calibrator.save(league_output)
    
    return {
        'calibrator': calibrator,
        'metrics': calibrator.metrics_log,
        'path': league_output
    }
