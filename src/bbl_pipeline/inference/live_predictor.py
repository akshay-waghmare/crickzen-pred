"""
Live Match Predictor
Orchestrates real-time scraping and win probability prediction.
"""
import time
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime
import structlog

from .predictor import Predictor
from .realtime_mapper import RealTimeFeatureMapper
from ..features.store import InMemoryFeatureStore

logger = structlog.get_logger()


class LiveMatchPredictor:
    """
    Orchestrates live match prediction by:
    1. Receiving scraped ball data
    2. Transforming to model features
    3. Making predictions
    4. Displaying results
    """
    
    def __init__(self, 
                 model_dir: str | Path,
                 feature_store: Optional[InMemoryFeatureStore] = None,
                 callback: Optional[Callable] = None):
        """
        Initialize the live predictor.
        
        Args:
            model_dir: Path to trained model directory
            feature_store: Pre-loaded feature store (optional)
            callback: Function to call with prediction results (for UI updates)
        """
        self.model_dir = Path(model_dir)
        self.callback = callback
        
        # Load predictor
        logger.info("Loading model and feature store...")
        self.predictor = Predictor.load(self.model_dir)
        
        # Use provided feature store or the one from predictor
        self.feature_store = feature_store or self.predictor.feature_store
        
        # Initialize mapper
        self.mapper = RealTimeFeatureMapper(
            self.feature_store,
            self.predictor.global_stats
        )
        
        # Track prediction history
        self.prediction_history = []
        self.current_innings = 1
        self.match_info = {}
        
        logger.info("Live predictor initialized successfully")
    
    def predict_ball(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make prediction for a single ball.
        
        Args:
            scraped_data: Dictionary containing ball data from scraper
            
        Returns:
            Dictionary with prediction results
        """
        try:
            # Extract match context
            ball_info = self._extract_ball_info(scraped_data)
            
            # Map to features
            features_df = self.mapper.create_feature_dataframe(scraped_data)
            
            # Get model's expected features
            if hasattr(self.predictor.model, 'feature_names_in_'):
                expected_features = self.predictor.model.feature_names_in_.tolist()
                features_df = self.mapper.validate_features(features_df, expected_features)
            
            # Make prediction
            win_prob = self.predictor.model.predict_proba(features_df)[0][1]
            
            # Create result dictionary
            result = {
                'timestamp': datetime.now().isoformat(),
                'ball': f"{ball_info['over']}.{ball_info['ball']}",
                'innings': ball_info['innings'],
                'batting_team': scraped_data.get('batting_team', 'Unknown'),
                'bowling_team': scraped_data.get('bowling_team', 'Unknown'),
                'score': f"{ball_info['score']}/{ball_info['wickets']}",
                'win_probability': float(win_prob),
                'resource_win_prob': float(features_df['resource_win_prob'].iloc[0]),
                'pressure_index': float(features_df['pressure_index'].iloc[0]),
                'current_run_rate': float(features_df['current_run_rate'].iloc[0]),
                'required_run_rate': float(features_df['required_run_rate'].iloc[0]) if ball_info['innings'] == 2 else None,
                'runs_required': int(scraped_data.get('runs_needed', 0)) if ball_info['innings'] == 2 else None,
                'balls_remaining': int(features_df['balls_remaining'].iloc[0]),
                'wickets_remaining': int(features_df['wickets_remaining'].iloc[0]),
                'expected_final_score': int(features_df['expected_final_score'].iloc[0]),
            }
            
            # Add to history
            self.prediction_history.append(result)
            
            # Call callback if provided (for UI updates)
            if self.callback:
                self.callback(result)
            
            logger.info(
                "Prediction made",
                ball=result['ball'],
                win_prob=f"{win_prob:.1%}",
                batting_team=result['batting_team']
            )
            
            return result
            
        except Exception as e:
            logger.error("Error making prediction", error=str(e), exc_info=True)
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _extract_ball_info(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key ball information for display."""
        return {
            'innings': scraped_data.get('innings_num', 1),
            'over': scraped_data.get('over_number', 0),
            'ball': scraped_data.get('ball_number', 0),
            'score': scraped_data.get('total_score', 0),
            'wickets': scraped_data.get('total_wickets', 0),
        }
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics from prediction history."""
        if not self.prediction_history:
            return {}
        
        df = pd.DataFrame(self.prediction_history)
        
        return {
            'total_balls': len(df),
            'current_win_prob': df['win_probability'].iloc[-1] if len(df) > 0 else 0.5,
            'avg_win_prob': df['win_probability'].mean(),
            'win_prob_std': df['win_probability'].std(),
            'max_win_prob': df['win_probability'].max(),
            'min_win_prob': df['win_probability'].min(),
            'pressure_avg': df['pressure_index'].mean() if 'pressure_index' in df.columns else 0,
        }
    
    def export_history(self, filepath: str | Path):
        """Export prediction history to CSV."""
        if not self.prediction_history:
            logger.warning("No predictions to export")
            return
        
        df = pd.DataFrame(self.prediction_history)
        df.to_csv(filepath, index=False)
        logger.info(f"Exported {len(df)} predictions to {filepath}")
    
    def reset(self):
        """Reset prediction history (for new match)."""
        self.prediction_history = []
        self.current_innings = 1
        self.match_info = {}
        logger.info("Predictor reset for new match")


class LiveMatchMonitor:
    """
    Monitors a live match and continuously makes predictions.
    Integrates with the real-time scraper.
    """
    
    def __init__(self, 
                 predictor: LiveMatchPredictor,
                 scraper_callback: Callable,
                 display_callback: Optional[Callable] = None):
        """
        Initialize the monitor.
        
        Args:
            predictor: LiveMatchPredictor instance
            scraper_callback: Function that returns scraped ball data
            display_callback: Optional function for custom display
        """
        self.predictor = predictor
        self.scraper_callback = scraper_callback
        self.display_callback = display_callback
        self.running = False
        self.last_ball_id = None
    
    def start(self, match_url: str, poll_interval: float = 2.0):
        """
        Start monitoring a match.
        
        Args:
            match_url: URL of the live match
            poll_interval: Seconds between checks for new balls
        """
        self.running = True
        logger.info(f"Starting live match monitoring: {match_url}")
        
        try:
            while self.running:
                # Get latest ball data from scraper
                ball_data = self.scraper_callback(match_url)
                
                if ball_data and self._is_new_ball(ball_data):
                    # Make prediction
                    result = self.predictor.predict_ball(ball_data)
                    
                    # Display result
                    if self.display_callback:
                        self.display_callback(result)
                    else:
                        self._default_display(result)
                    
                    # Update last ball
                    self.last_ball_id = self._get_ball_id(ball_data)
                
                # Wait before next poll
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            self.stop()
        except Exception as e:
            logger.error(f"Error during monitoring: {e}", exc_info=True)
            self.stop()
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
        logger.info("Live match monitoring stopped")
        
        # Export results
        if self.predictor.prediction_history:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = f"live_predictions_{timestamp}.csv"
            self.predictor.export_history(export_path)
    
    def _is_new_ball(self, ball_data: Dict[str, Any]) -> bool:
        """Check if this is a new ball."""
        current_ball_id = self._get_ball_id(ball_data)
        return current_ball_id != self.last_ball_id
    
    def _get_ball_id(self, ball_data: Dict[str, Any]) -> str:
        """Generate unique ID for a ball."""
        innings = ball_data.get('innings_num', 1)
        over = ball_data.get('over_number', 0)
        ball = ball_data.get('ball_number', 0)
        return f"{innings}.{over}.{ball}"
    
    def _default_display(self, result: Dict[str, Any]):
        """Default console display for predictions."""
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
            return
        
        print("\n" + "="*80)
        print(f"🏏 Ball {result['ball']} | Innings {result['innings']}")
        print(f"📊 {result['batting_team']}: {result['score']}")
        
        win_prob = result['win_probability']
        emoji = "🔥" if win_prob > 0.7 else "📈" if win_prob > 0.5 else "📉" if win_prob > 0.3 else "❄️"
        print(f"\n{emoji} Win Probability: {win_prob:.1%}")
        print(f"⚡ Pressure Index: {result['pressure_index']:.2f}")
        
        if result['innings'] == 2 and result['runs_required'] is not None:
            print(f"\n🎯 Target: {result['runs_required']} runs from {result['balls_remaining']} balls")
            print(f"📊 Required RR: {result['required_run_rate']:.2f} | Current RR: {result['current_run_rate']:.2f}")
        else:
            print(f"\n📈 Expected Final Score: {result['expected_final_score']}")
            print(f"📊 Current Run Rate: {result['current_run_rate']:.2f}")
        
        print("="*80)
