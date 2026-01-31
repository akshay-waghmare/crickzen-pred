"""
Interactive Win Probability Chart Viewer - Bookmaker Style

View pre-computed win probability lookup charts in your terminal.
Similar to old bookmaker ready-reckoners.

Usage:
    python scripts/view_win_prob_chart.py --innings 1 --wickets 0
    python scripts/view_win_prob_chart.py --innings 2 --wickets 5
    python scripts/view_win_prob_chart.py --lookup 12.3 95 3  # Find specific probability
"""

import pandas as pd
import numpy as np
from pathlib import Path
import argparse
import sys


def format_prob(prob: float) -> str:
    """Format probability as percentage with color coding."""
    pct = prob * 100
    if pct >= 75:
        return f"\033[92m{pct:5.1f}%\033[0m"  # Green
    elif pct >= 50:
        return f"\033[93m{pct:5.1f}%\033[0m"  # Yellow
    elif pct >= 25:
        return f"\033[91m{pct:5.1f}%\033[0m"  # Red
    else:
        return f"\033[90m{pct:5.1f}%\033[0m"  # Gray


def view_first_innings_chart(wickets: int, data_dir: str = "data/win_prob_tables"):
    """Display first innings win probability chart."""
    filepath = Path(data_dir) / f"innings1_wickets_{wickets}.csv"
    
    if not filepath.exists():
        print(f"❌ Chart not found: {filepath}")
        print("Run: python -m src.bbl_pipeline.features.win_prob_lookup_tables")
        return
    
    df = pd.read_csv(filepath, index_col=0)
    
    print("\n" + "="*100)
    print(f"📊 FIRST INNINGS WIN PROBABILITY CHART - {wickets} WICKETS DOWN")
    print("="*100)
    print("\n📖 How to read: Find your overs bowled (rows) and current score (columns)")
    print("   Win probability shows batting team's chance to win the match\n")
    
    # Select key columns for display (every 20 runs)
    display_scores = [0, 20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240]
    display_scores = [s for s in display_scores if s in df.columns]
    
    # Select key rows (every 2 overs)
    display_overs = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
    display_overs = [o for o in display_overs if o in df.index]
    
    # Create display table
    display_df = df.loc[display_overs, display_scores]
    
    # Print header
    print("Overs | ", end="")
    for score in display_scores:
        print(f"{score:>7}", end="")
    print("\n" + "-"*100)
    
    # Print data rows
    for over in display_overs:
        print(f"{over:5.0f} | ", end="")
        for score in display_scores:
            prob = display_df.loc[over, score]
            print(f"{format_prob(prob)}", end="")
        print()
    
    print("\n" + "="*100)
    print("Legend: 🟢 >75%  🟡 50-75%  🔴 25-50%  ⚫ <25%")
    print("="*100 + "\n")


def view_second_innings_chart(wickets: int, data_dir: str = "data/win_prob_tables"):
    """Display second innings win probability chart."""
    filepath = Path(data_dir) / f"innings2_wickets_{wickets}.csv"
    
    if not filepath.exists():
        print(f"❌ Chart not found: {filepath}")
        print("Run: python -m src.bbl_pipeline.features.win_prob_lookup_tables")
        return
    
    df = pd.read_csv(filepath, index_col=0)
    
    print("\n" + "="*100)
    print(f"📊 SECOND INNINGS WIN PROBABILITY CHART - {wickets} WICKETS DOWN")
    print("="*100)
    print("\n📖 How to read: Find your balls remaining (rows) and runs required (columns)")
    print("   Win probability shows chasing team's chance to win the match\n")
    
    # Select key columns for display (every 10 runs)
    display_runs = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 140]
    display_runs = [r for r in display_runs if r in df.columns]
    
    # Select all ball milestones (they're already sparse)
    display_balls = df.index.tolist()
    
    # Print header
    print("Balls | ", end="")
    for runs in display_runs:
        print(f"{runs:>7}", end="")
    print("\n" + "-"*100)
    
    # Print data rows
    for balls in display_balls:
        # Format balls remaining with overs.balls notation
        overs = balls // 6
        balls_in_over = balls % 6
        print(f"{overs:2.0f}.{balls_in_over:1.0f} | ", end="")
        for runs in display_runs:
            prob = df.loc[balls, runs]
            print(f"{format_prob(prob)}", end="")
        print()
    
    print("\n" + "="*100)
    print("Legend: 🟢 >75%  🟡 50-75%  🔴 25-50%  ⚫ <25%")
    print("="*100 + "\n")


def lookup_probability(overs_or_balls: float, score_or_runs: int, wickets: int, 
                       innings: int = 1, data_dir: str = "data/win_prob_tables"):
    """
    Look up a specific win probability from the charts.
    
    Args:
        overs_or_balls: Overs bowled (innings 1) or balls remaining (innings 2)
        score_or_runs: Current score (innings 1) or runs required (innings 2)
        wickets: Wickets lost
        innings: 1 or 2
    """
    if innings == 1:
        filepath = Path(data_dir) / f"innings1_wickets_{wickets}.csv"
        df = pd.read_csv(filepath, index_col=0)
        
        # Convert columns to int
        df.columns = df.columns.astype(int)
        
        # Find nearest over
        nearest_over = min(df.index, key=lambda x: abs(x - overs_or_balls))
        
        # Find nearest score
        nearest_score = min(df.columns, key=lambda x: abs(x - score_or_runs))
        
        prob = df.loc[nearest_over, nearest_score]
        
        print("\n" + "="*80)
        print("🔍 WIN PROBABILITY LOOKUP")
        print("="*80)
        print(f"\nMatch State:")
        print(f"  Innings:        1st (Batting First)")
        print(f"  Overs Bowled:   {overs_or_balls:.1f} (using {nearest_over:.0f})")
        print(f"  Current Score:  {score_or_runs} (using {nearest_score})")
        print(f"  Wickets Lost:   {wickets}")
        print(f"\n📈 Win Probability: {format_prob(prob)}")
        print("="*80 + "\n")
        
    else:
        filepath = Path(data_dir) / f"innings2_wickets_{wickets}.csv"
        df = pd.read_csv(filepath, index_col=0)
        
        # Convert columns to int
        df.columns = df.columns.astype(int)
        
        # Find nearest balls remaining
        balls_remaining = int(overs_or_balls)
        nearest_balls = min(df.index, key=lambda x: abs(x - balls_remaining))
        
        # Find nearest runs required
        nearest_runs = min(df.columns, key=lambda x: abs(x - score_or_runs))
        
        prob = df.loc[nearest_balls, nearest_runs]
        
        overs = balls_remaining // 6
        balls_in_over = balls_remaining % 6
        
        print("\n" + "="*80)
        print("🔍 WIN PROBABILITY LOOKUP")
        print("="*80)
        print(f"\nMatch State:")
        print(f"  Innings:         2nd (Chasing)")
        print(f"  Balls Remaining: {balls_remaining} ({overs}.{balls_in_over} overs)")
        print(f"  Runs Required:   {score_or_runs} (using {nearest_runs})")
        print(f"  Wickets Lost:    {wickets}")
        print(f"\n📈 Win Probability: {format_prob(prob)}")
        print("="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="View win probability lookup charts (bookmaker style)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View first innings chart for 0 wickets down
  python scripts/view_win_prob_chart.py --innings 1 --wickets 0
  
  # View second innings chart for 5 wickets down  
  python scripts/view_win_prob_chart.py --innings 2 --wickets 5
  
  # Look up specific probability (innings 1: 12.3 overs, 95 runs, 3 wickets)
  python scripts/view_win_prob_chart.py --innings 1 --lookup 12.3 95 3
  
  # Look up specific probability (innings 2: 42 balls left, 38 runs needed, 2 wickets)
  python scripts/view_win_prob_chart.py --innings 2 --lookup 42 38 2
        """
    )
    
    parser.add_argument('--innings', type=int, choices=[1, 2], required=True,
                       help='Innings number (1 or 2)')
    parser.add_argument('--wickets', type=int, choices=range(0, 11),
                       help='Wickets lost (0-10) - required if not using --lookup')
    parser.add_argument('--lookup', nargs=3, metavar=('OVERS/BALLS', 'SCORE/RUNS', 'WICKETS'),
                       help='Look up specific probability instead of viewing full chart')
    parser.add_argument('--data-dir', default='data/win_prob_tables',
                       help='Directory containing lookup tables')
    
    args = parser.parse_args()
    
    # Check if lookup tables exist
    data_path = Path(args.data_dir)
    if not data_path.exists():
        print("❌ Lookup tables not found!")
        print(f"   Expected directory: {data_path}")
        print("\nGenerate tables with:")
        print("   python -m src.bbl_pipeline.features.win_prob_lookup_tables")
        sys.exit(1)
    
    if args.lookup:
        # Lookup mode
        overs_or_balls = float(args.lookup[0])
        score_or_runs = int(args.lookup[1])
        wickets = int(args.lookup[2])
        
        lookup_probability(overs_or_balls, score_or_runs, wickets, 
                          innings=args.innings, data_dir=args.data_dir)
    else:
        # Chart view mode
        if args.wickets is None:
            parser.error("--wickets is required when not using --lookup")
        
        if args.innings == 1:
            view_first_innings_chart(args.wickets, data_dir=args.data_dir)
        else:
            view_second_innings_chart(args.wickets, data_dir=args.data_dir)


if __name__ == "__main__":
    main()
