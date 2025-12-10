#!/usr/bin/env python3
"""
Live Match Prediction Runner
Main script to run real-time match predictions with live display.

Usage:
    python run_live_prediction.py --match-url <ESPN_URL> --model-dir <MODEL_PATH>
    
Example:
    python run_live_prediction.py \\
        --match-url "https://www.espncricinfo.com/series/..." \\
        --model-dir "./models/champion"
"""
import argparse
import sys
from pathlib import Path
import structlog

# Add src to path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

from bbl_pipeline.inference.live_predictor import LiveMatchPredictor, LiveMatchMonitor
from bbl_pipeline.inference.display import LiveMatchDisplay
from bbl_pipeline.inference.scraper_bridge import ScraperBridge, transform_scraper_output

# Configure logging
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
)
logger = structlog.get_logger()


def main():
    parser = argparse.ArgumentParser(
        description="Live Cricket Match Win Probability Predictor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run prediction for a live match
  python run_live_prediction.py \\
      --match-url "https://www.espncricinfo.com/series/big-bash-league-2024-25/..." \\
      --model-dir "./models/champion"
  
  # With custom polling interval
  python run_live_prediction.py \\
      --match-url "https://..." \\
      --model-dir "./models/champion" \\
      --poll-interval 3.0
        """
    )
    
    parser.add_argument(
        '--match-url',
        type=str,
        required=True,
        help='ESPN Cricinfo live match URL'
    )
    
    parser.add_argument(
        '--model-dir',
        type=str,
        required=True,
        help='Path to trained model directory (containing champion_model.joblib)'
    )
    
    parser.add_argument(
        '--poll-interval',
        type=float,
        default=2.0,
        help='Seconds between checks for new balls (default: 2.0)'
    )
    
    parser.add_argument(
        '--no-clear',
        action='store_true',
        help='Do not clear screen between updates'
    )
    
    parser.add_argument(
        '--export',
        type=str,
        help='Export predictions to CSV file (default: auto-generated filename)'
    )
    
    args = parser.parse_args()
    
    # Validate model directory
    model_dir = Path(args.model_dir)
    if not model_dir.exists():
        logger.error(f"Model directory not found: {model_dir}")
        sys.exit(1)
    
    model_path = model_dir / "champion_model.joblib"
    if not model_path.exists():
        logger.error(f"Model file not found: {model_path}")
        sys.exit(1)
    
    print("\n" + "="*100)
    print(" 🏏 BBL LIVE MATCH PREDICTOR ".center(100))
    print("="*100 + "\n")
    
    try:
        # Initialize display
        display = LiveMatchDisplay(clear_screen=not args.no_clear)
        
        # Initialize predictor
        print("📦 Loading model and feature store...")
        predictor = LiveMatchPredictor(
            model_dir=model_dir,
            callback=display.display_prediction
        )
        print("✅ Model loaded successfully!\n")
        
        # Initialize scraper bridge
        print("🌐 Initializing scraper...")
        scraper = ScraperBridge()
        scraper.initialize_scraper(args.match_url)
        print("✅ Scraper initialized!\n")
        
        # Create scraper callback function
        def get_ball_data(url: str):
            """Callback to get latest ball data from scraper."""
            return scraper.get_latest_ball_data()
        
        # Initialize monitor
        monitor = LiveMatchMonitor(
            predictor=predictor,
            scraper_callback=get_ball_data,
            display_callback=display.display_prediction
        )
        
        print(f"🎯 Starting live monitoring for: {args.match_url}")
        print(f"⏱️  Polling every {args.poll_interval} seconds")
        print(f"⌨️  Press Ctrl+C to stop\n")
        
        # Start monitoring
        monitor.start(args.match_url, poll_interval=args.poll_interval)
        
    except KeyboardInterrupt:
        print("\n\n✋ Stopped by user")
    except Exception as e:
        logger.error(f"Error during execution: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        if 'scraper' in locals():
            scraper.cleanup()
        
        # Export results
        if 'predictor' in locals() and predictor.prediction_history:
            export_path = args.export or f"live_predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            predictor.export_history(export_path)
            print(f"\n💾 Predictions exported to: {export_path}")
        
        print("\n👋 Goodbye!\n")


if __name__ == "__main__":
    from datetime import datetime
    import logging
    main()
