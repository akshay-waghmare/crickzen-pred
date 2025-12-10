"""
Standalone Live Match Predictor
Integrates directly with ml_predictions/real_time_scraper.py for seamless operation.
This version modifies the scraper's callback to inject predictions.
"""
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Add paths
src_path = Path(__file__).parent
ml_pred_path = src_path.parent / "ml_predictions"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(ml_pred_path))

from bbl_pipeline.inference.live_predictor import LiveMatchPredictor
from bbl_pipeline.inference.display import LiveMatchDisplay
from bbl_pipeline.inference.scraper_bridge import transform_scraper_output


class IntegratedLivePredictor:
    """
    Integrated predictor that works directly with the existing scraper.
    Hooks into the scraper's ball processing pipeline.
    """
    
    def __init__(self, model_dir: str):
        """
        Initialize the integrated predictor.
        
        Args:
            model_dir: Path to model directory
        """
        self.model_dir = Path(model_dir)
        self.display = LiveMatchDisplay(clear_screen=True)
        self.predictor = None
        self.ball_count = 0
        
    def initialize(self):
        """Initialize the predictor."""
        print("\n" + "="*100)
        print(" 🏏 INITIALIZING BBL LIVE PREDICTOR ".center(100))
        print("="*100 + "\n")
        
        print("📦 Loading model and feature store...")
        self.predictor = LiveMatchPredictor(
            model_dir=self.model_dir,
            callback=self.display.display_prediction
        )
        print("✅ Model loaded successfully!\n")
    
    def process_ball(self, enhanced_ball_data: Dict[str, Any], 
                     final_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a ball and make prediction.
        This is called from the scraper after it processes each ball.
        
        Args:
            enhanced_ball_data: Enhanced ball data from scraper
            final_data: Final processed data from scraper
            
        Returns:
            Prediction result
        """
        try:
            # Transform scraper output to standard format
            standardized_data = transform_scraper_output(enhanced_ball_data, final_data)
            
            # Make prediction
            result = self.predictor.predict_ball(standardized_data)
            
            self.ball_count += 1
            
            return result
            
        except Exception as e:
            print(f"❌ Error processing ball: {e}")
            return {'error': str(e)}
    
    def get_summary(self):
        """Print summary statistics."""
        if self.ball_count == 0:
            print("\nNo balls processed yet.")
            return
        
        print("\n" + "="*100)
        print(" 📊 PREDICTION SUMMARY ".center(100))
        print("="*100 + "\n")
        
        stats = self.predictor.get_summary_stats()
        
        print(f"{'Total Balls Predicted':<40}: {stats.get('total_balls', 0)}")
        print(f"{'Current Win Probability':<40}: {stats.get('current_win_prob', 0):.1%}")
        print(f"{'Average Win Probability':<40}: {stats.get('avg_win_prob', 0):.1%}")
        print(f"{'Win Probability Range':<40}: {stats.get('min_win_prob', 0):.1%} - {stats.get('max_win_prob', 0):.1%}")
        print(f"{'Average Pressure Index':<40}: {stats.get('pressure_avg', 0):.2f}")
        
        print("\n" + "="*100 + "\n")


def run_with_scraper(match_url: str, model_dir: str):
    """
    Run live prediction integrated with the scraper.
    
    Args:
        match_url: ESPN Cricinfo match URL
        model_dir: Path to model directory
    """
    # Initialize predictor
    predictor = IntegratedLivePredictor(model_dir)
    predictor.initialize()
    
    print(f"🌐 Starting scraper for: {match_url}\n")
    print("⏱️  Waiting for balls to be bowled...")
    print("⌨️  Press Ctrl+C to stop\n")
    
    try:
        # Import the scraper components
        from playwright.sync_api import sync_playwright
        from real_time_scraper import (
            wait_for_new_ball_update,
            extract_match_info,
            extract_scorecard_data,
            parse_ball_details,
            calculate_rolling_averages,
            calculate_pressure_index,
            fuzzy_match_team,
            get_venue_stats
        )
        
        import re
        
        from playwright_stealth import Stealth

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            stealth = Stealth()
            page = stealth.use_sync(context.new_page())
            
            print(f"🌐 Opening match page: {match_url}")
            page.goto(match_url, timeout=60000)
            time.sleep(5)
            
            # Initialize match state
            match_state = {
                'current_innings': 1,
                'current_over': 0,
                'total_score': 0,
                'total_wickets': 0,
                'over_summaries': {},
                'player_stats': {}
            }
            
            # Extract match info
            match_info = extract_match_info(page)
            print(f"✅ Match loaded: {match_info.get('venue', 'Unknown Venue')}\n")
            
            # Get venue stats if available
            if 'venue_link' in match_info and match_info['venue_link']:
                venue_id_match = re.search(r'(\d+)$', match_info['venue_link'])
                if venue_id_match:
                    venue_id = venue_id_match.group(1)
                    try:
                        venue_stats = get_venue_stats(context, venue_id)
                        match_state['venue_stats'] = venue_stats
                    except:
                        match_state['venue_stats'] = {}
            
            player_stats_cache = {}
            
            # Main loop
            while True:
                # Wait for new ball
                ball_update = wait_for_new_ball_update(page, match_state)
                
                # Extract scorecard
                scorecard_data = extract_scorecard_data(page, player_stats_cache)
                
                # Parse ball details
                ball_data = parse_ball_details(
                    ball_update['ball_number'],
                    ball_update['runs_or_event'],
                    ball_update['short_commentary']
                )
                
                # Build enhanced ball data (following scraper's logic)
                enhanced_ball_data = {}
                enhanced_ball_data.update(ball_data)
                
                # Add scorecard data
                if scorecard_data:
                    for batsman in scorecard_data.get('batsmen', []):
                        if batsman.get('is_on_strike'):
                            enhanced_ball_data['batsman1_name'] = batsman['name']
                            enhanced_ball_data['batsman1_runs'] = batsman['runs']
                            enhanced_ball_data['batsman1_balls_faced'] = batsman['balls']
                        else:
                            enhanced_ball_data['batsman2_name'] = batsman['name']
                            enhanced_ball_data['batsman2_runs'] = batsman['runs']
                            enhanced_ball_data['batsman2_balls_faced'] = batsman['balls']
                    
                    for bowler in scorecard_data.get('bowlers', []):
                        if 'bowler1_name' not in enhanced_ball_data:
                            enhanced_ball_data['bowler1_name'] = bowler['name']
                            enhanced_ball_data['bowler1_overs_bowled'] = bowler['overs']
                            enhanced_ball_data['bowler1_runs_conceded'] = bowler['runs']
                            enhanced_ball_data['bowler1_wickets_taken'] = bowler['wickets']
                
                # Add match context
                enhanced_ball_data['batting_team'] = ball_update.get('batting_team', '')
                enhanced_ball_data['bowling_team'] = ball_update.get('bowling_team', '')
                enhanced_ball_data['venue'] = match_info.get('venue', '')
                enhanced_ball_data['toss_winner'] = match_info.get('toss_winner', '')
                enhanced_ball_data['toss_decision'] = match_info.get('toss_decision', '')
                
                # Build final data structure
                final_data = {
                    'innings_num': 2 if ball_update['is_second_innings'] else 1,
                    'batting_team': fuzzy_match_team(enhanced_ball_data['batting_team']),
                    'over_number': enhanced_ball_data['over_number'],
                    'ball_number': enhanced_ball_data['ball_in_over'],
                    'total_score': int(ball_update['batting_team_score'].split('/')[0]),
                    'total_wickets': int(ball_update['batting_team_score'].split('/')[1]),
                    'batsman1_name': enhanced_ball_data.get('batsman1_name', 'Unknown'),
                    'batsman1_runs': enhanced_ball_data.get('batsman1_runs', 0),
                    'batsman1_balls_faced': enhanced_ball_data.get('batsman1_balls_faced', 0),
                    'batsman2_name': enhanced_ball_data.get('batsman2_name', 'Unknown'),
                    'batsman2_runs': enhanced_ball_data.get('batsman2_runs', 0),
                    'batsman2_balls_faced': enhanced_ball_data.get('batsman2_balls_faced', 0),
                    'bowler1_name': enhanced_ball_data.get('bowler1_name', 'Unknown'),
                    'bowler1_overs_bowled': enhanced_ball_data.get('bowler1_overs_bowled', 0),
                    'bowler1_runs_conceded': enhanced_ball_data.get('bowler1_runs_conceded', 0),
                    'bowler1_wickets_taken': enhanced_ball_data.get('bowler1_wickets_taken', 0),
                    'venue': enhanced_ball_data.get('venue', 'Unknown'),
                    'current_run_rate': ball_update.get('current_run_rate', 0),
                    'required_run_rate': ball_update.get('required_run_rate', 0),
                    'powerplay': int(enhanced_ball_data['over_number'] < 6),
                    'middle_overs': int(6 <= enhanced_ball_data['over_number'] < 16),
                    'death_overs': int(enhanced_ball_data['over_number'] >= 16),
                }
                
                # Add 2nd innings specific data
                if ball_update['is_second_innings'] and 'target' in ball_update:
                    final_data['target_score'] = ball_update['target']
                    final_data['runs_needed'] = ball_update['target'] - final_data['total_score']
                    
                    if 'over_info' in ball_update and ball_update['over_info']:
                        over_num = ball_update['over_info']['over_number']
                        ball_num = ball_update['over_info']['ball_number']
                        balls_completed = over_num * 6 + ball_num
                        final_data['balls_remaining'] = 120 - balls_completed
                
                # Calculate rolling averages
                rolling_stats = calculate_rolling_averages(enhanced_ball_data, match_state)
                final_data.update(rolling_stats)
                
                # Calculate pressure
                if ball_update['is_second_innings']:
                    final_data['pressure_index'] = calculate_pressure_index(enhanced_ball_data, match_state)
                else:
                    final_data['pressure_index'] = 0
                
                # ✨ MAKE PREDICTION ✨
                prediction_result = predictor.process_ball(enhanced_ball_data, final_data)
                
                # Small delay before next poll
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n\n✋ Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'browser' in locals():
            browser.close()
        
        # Print summary
        predictor.get_summary()
        
        # Export results
        if predictor.predictor and predictor.predictor.prediction_history:
            export_path = f"live_predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            predictor.predictor.export_history(export_path)
            print(f"💾 Predictions exported to: {export_path}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrated Live Match Predictor")
    parser.add_argument('--match-url', required=True, help='ESPN Cricinfo match URL')
    parser.add_argument('--model-dir', required=True, help='Path to model directory')
    
    args = parser.parse_args()
    
    run_with_scraper(args.match_url, args.model_dir)
