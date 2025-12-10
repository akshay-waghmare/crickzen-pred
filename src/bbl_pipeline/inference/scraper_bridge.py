"""
Scraper Integration Bridge
Adapts the existing ml_predictions/real_time_scraper.py to work with BBL pipeline.
"""
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import structlog

# Add ml_predictions to path
ml_predictions_path = Path(__file__).parent.parent.parent.parent / "ml_predictions"
sys.path.insert(0, str(ml_predictions_path))

logger = structlog.get_logger()


class ScraperBridge:
    """
    Bridges the existing real-time scraper with the BBL prediction pipeline.
    Provides a clean interface to get ball data without modifying the original scraper.
    """
    
    def __init__(self):
        """Initialize the bridge."""
        self.scraper = None
        self.current_match_url = None
        self.last_processed_ball = None
        
    def initialize_scraper(self, match_url: str):
        """
        Initialize the scraper for a specific match.
        
        Args:
            match_url: ESPN Cricinfo match URL
        """
        try:
            # Import the scraper (deferred to avoid import issues)
            from playwright.sync_api import sync_playwright
            
            self.current_match_url = match_url
            logger.info(f"Scraper bridge initialized for match: {match_url}")
            
        except ImportError as e:
            logger.error(f"Failed to import playwright: {e}")
            logger.info("Install with: pip install playwright && playwright install")
            raise
    
    def get_latest_ball_data(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest ball data from the scraper.
        This is called repeatedly to poll for new balls.
        
        Returns:
            Dictionary with ball data, or None if no new ball
        """
        # Note: This is a simplified version. The actual implementation
        # would integrate with wait_for_new_ball_update() from real_time_scraper.py
        # For now, returning a mock structure to show the interface
        
        logger.debug("Polling for new ball data...")
        
        # TODO: Actual implementation would call the scraper's
        # wait_for_new_ball_update and process the data
        return None
    
    def cleanup(self):
        """Clean up resources."""
        if self.scraper:
            # Close browser, etc.
            pass
        logger.info("Scraper bridge cleaned up")


# Helper function to extract ball data from scraper's enhanced_ball_data
def transform_scraper_output(enhanced_ball_data: Dict[str, Any], 
                             final_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform the scraper's output format to a standardized format
    that the RealTimeFeatureMapper expects.
    
    Args:
        enhanced_ball_data: The enhanced_ball_data dict from real_time_scraper
        final_data: The final_data dict from real_time_scraper
        
    Returns:
        Standardized ball data dictionary
    """
    return {
        # Core match state (renamed fields)
        'innings_num': final_data.get('innings_num', 1),
        'over_number': final_data.get('over_number', 0),
        'ball_number': final_data.get('ball_number', 0),
        'total_score': final_data.get('total_score', 0),
        'total_wickets': final_data.get('total_wickets', 0),
        
        # Teams
        'batting_team': final_data.get('batting_team', 'Unknown'),
        'bowling_team': enhanced_ball_data.get('bowling_team', 'Unknown'),
        
        # Players
        'batsman1_name': final_data.get('batsman1_name', 'Unknown'),
        'batsman2_name': final_data.get('batsman2_name', 'Unknown'),
        'bowler1_name': final_data.get('bowler1_name', 'Unknown'),
        
        # Player stats (current match)
        'batsman1_runs': final_data.get('batsman1_runs', 0),
        'batsman1_balls_faced': final_data.get('batsman1_balls_faced', 0),
        'batsman2_runs': final_data.get('batsman2_runs', 0),
        'batsman2_balls_faced': final_data.get('batsman2_balls_faced', 0),
        'bowler1_overs_bowled': final_data.get('bowler1_overs_bowled', 0),
        'bowler1_runs_conceded': final_data.get('bowler1_runs_conceded', 0),
        'bowler1_wickets_taken': final_data.get('bowler1_wickets_taken', 0),
        
        # Venue
        'venue': final_data.get('venue', 'Unknown Venue'),
        
        # Match situation
        'target_score': enhanced_ball_data.get('target_score') if final_data.get('innings_num') == 2 else None,
        'runs_needed': final_data.get('runs_needed', 0) if final_data.get('innings_num') == 2 else 0,
        'balls_remaining': enhanced_ball_data.get('balls_remaining', 120),
        
        # Rate features (from scraper if available)
        'current_run_rate': final_data.get('current_run_rate', 0),
        'required_run_rate': final_data.get('required_run_rate', 0),
        
        # Phase features
        'powerplay': final_data.get('powerplay', 0),
        'middle_overs': final_data.get('middle_overs', 0),
        'death_overs': final_data.get('death_overs', 0),
        
        # Projected score
        'projected_score': final_data.get('projected_score', 0),
        
        # Pressure
        'pressure_index': final_data.get('pressure_index', 0),
        
        # Match info
        'toss_winner': final_data.get('toss_winner', 'Unknown'),
        'toss_decision': final_data.get('toss_decision', ''),
        'favored_team': final_data.get('favored_team', ''),
        'win_percentage': final_data.get('win_percentage', 50.0),
        
        # Metadata
        'match_id': 'live_match',
        'timestamp': enhanced_ball_data.get('timestamp', ''),
    }
