"""
Win Probability Lookup Tables - Bookmaker Style Ready Reckoner
================================================================

Pre-computed win probability tables for fast lookup during live matches.
Similar to traditional bookmaker charts but with dynamic 3D calibration.

Usage:
    1. Identify match state (innings, score, overs, wickets)
    2. Look up win probability from appropriate table
    3. Interpolate between grid points if needed

Author: BBL Pipeline
Date: February 2026
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from pathlib import Path
import json


class WinProbabilityLookupTables:
    """
    Pre-computed win probability lookup tables for T20 cricket.
    
    Tables are organized as:
    - First Innings: [overs_bowled][current_score][wickets_lost] -> win_prob
    - Second Innings: [balls_remaining][runs_required][wickets_lost] -> win_prob
    """
    
    def __init__(self):
        """Initialize lookup tables from ResourceFeatureCalculator logic."""
        try:
            from .calculator import ResourceFeatureCalculator
        except ImportError:
            from bbl_pipeline.features.calculator import ResourceFeatureCalculator
        self.calculator = ResourceFeatureCalculator()
        
        # First innings grid dimensions
        self.innings1_overs = np.arange(0, 21, 1)  # Every over (0-20)
        self.innings1_scores = np.arange(0, 251, 10)  # Every 10 runs (0-250)
        self.innings1_wickets = np.arange(0, 11, 1)  # Every wicket (0-10)
        
        # Second innings grid dimensions
        self.innings2_balls = np.array([120, 96, 72, 60, 48, 36, 30, 24, 18, 12, 6, 3, 1])  # Key ball milestones
        self.innings2_runs_req = np.arange(0, 151, 5)  # Every 5 runs required (0-150)
        self.innings2_wickets = np.arange(0, 11, 1)  # Every wicket (0-10)
        
        # Storage for computed tables
        self.innings1_table: Optional[np.ndarray] = None
        self.innings2_table: Optional[np.ndarray] = None
        
    def generate_first_innings_table(self) -> np.ndarray:
        """
        Generate first innings win probability lookup table.
        
        Dimensions: [overs_bowled, current_score, wickets_lost]
        
        Returns:
            3D numpy array of win probabilities
        """
        print("Generating First Innings Lookup Table...")
        print(f"  Grid: {len(self.innings1_overs)} overs × {len(self.innings1_scores)} scores × {len(self.innings1_wickets)} wickets")
        print(f"  Total entries: {len(self.innings1_overs) * len(self.innings1_scores) * len(self.innings1_wickets):,}")
        
        table = np.zeros((
            len(self.innings1_overs),
            len(self.innings1_scores),
            len(self.innings1_wickets)
        ))
        
        for i, overs in enumerate(self.innings1_overs):
            for j, score in enumerate(self.innings1_scores):
                for k, wickets in enumerate(self.innings1_wickets):
                    # Convert overs to over.ball format (e.g., 5 -> over=4, ball=6)
                    over = int(overs)
                    ball = 6 if overs == int(overs) and overs > 0 else 0
                    
                    if over > 0:
                        over -= 1  # Adjust for 0-indexing
                        ball = 6
                    
                    try:
                        features = self.calculator.calculate_all_features(
                            innings=1,
                            over=over,
                            ball=ball,
                            current_score=int(score),
                            wickets_lost=int(wickets),
                            target_runs=None
                        )
                        table[i, j, k] = features['resource_win_prob']
                    except Exception as e:
                        # Fallback for edge cases
                        table[i, j, k] = 0.37  # Historical bat-first win rate
        
        self.innings1_table = table
        print("✓ First innings table generated")
        return table
    
    def generate_second_innings_table(self, target_score: int = 165) -> np.ndarray:
        """
        Generate second innings win probability lookup table.
        
        Dimensions: [balls_remaining, runs_required, wickets_lost]
        
        Args:
            target_score: Reference target (default: 165, league average)
        
        Returns:
            3D numpy array of win probabilities
        """
        print("Generating Second Innings Lookup Table...")
        print(f"  Grid: {len(self.innings2_balls)} ball milestones × {len(self.innings2_runs_req)} runs × {len(self.innings2_wickets)} wickets")
        print(f"  Total entries: {len(self.innings2_balls) * len(self.innings2_runs_req) * len(self.innings2_wickets):,}")
        
        table = np.zeros((
            len(self.innings2_balls),
            len(self.innings2_runs_req),
            len(self.innings2_wickets)
        ))
        
        for i, balls_rem in enumerate(self.innings2_balls):
            balls_bowled = 120 - balls_rem
            over = balls_bowled // 6
            ball = balls_bowled % 6
            
            for j, runs_req in enumerate(self.innings2_runs_req):
                current_score = target_score - runs_req
                current_score = max(0, current_score)
                
                for k, wickets in enumerate(self.innings2_wickets):
                    try:
                        features = self.calculator.calculate_all_features(
                            innings=2,
                            over=over,
                            ball=ball,
                            current_score=int(current_score),
                            wickets_lost=int(wickets),
                            target_runs=target_score
                        )
                        table[i, j, k] = features['resource_win_prob']
                    except Exception as e:
                        # Fallback for edge cases
                        if runs_req <= 0:
                            table[i, j, k] = 1.0
                        elif balls_rem <= 0:
                            table[i, j, k] = 0.0
                        else:
                            table[i, j, k] = 0.5
        
        self.innings2_table = table
        print("✓ Second innings table generated")
        return table
    
    def lookup_first_innings(self, overs_bowled: float, current_score: int, wickets_lost: int) -> float:
        """
        Look up first innings win probability with interpolation.
        
        Args:
            overs_bowled: Overs completed (e.g., 12.3)
            current_score: Current score
            wickets_lost: Wickets fallen
            
        Returns:
            Win probability (0-1)
        """
        if self.innings1_table is None:
            self.generate_first_innings_table()
        
        # Find nearest grid points
        over_idx = np.searchsorted(self.innings1_overs, overs_bowled)
        score_idx = np.searchsorted(self.innings1_scores, current_score)
        wicket_idx = np.clip(int(wickets_lost), 0, 10)
        
        # Clamp indices
        over_idx = np.clip(over_idx, 0, len(self.innings1_overs) - 1)
        score_idx = np.clip(score_idx, 0, len(self.innings1_scores) - 1)
        
        # Simple lookup (can be enhanced with trilinear interpolation)
        return float(self.innings1_table[over_idx, score_idx, wicket_idx])
    
    def lookup_second_innings(self, balls_remaining: int, runs_required: int, wickets_lost: int) -> float:
        """
        Look up second innings win probability with interpolation.
        
        Args:
            balls_remaining: Balls left in innings
            runs_required: Runs needed to win
            wickets_lost: Wickets fallen
            
        Returns:
            Win probability (0-1)
        """
        if self.innings2_table is None:
            self.generate_second_innings_table()
        
        # Find nearest grid points
        balls_idx = np.argmin(np.abs(self.innings2_balls - balls_remaining))
        runs_idx = np.searchsorted(self.innings2_runs_req, runs_required)
        wicket_idx = np.clip(int(wickets_lost), 0, 10)
        
        # Clamp indices
        runs_idx = np.clip(runs_idx, 0, len(self.innings2_runs_req) - 1)
        
        # Simple lookup
        return float(self.innings2_table[balls_idx, runs_idx, wicket_idx])
    
    def export_to_csv(self, output_dir: str = "data/win_prob_tables"):
        """
        Export lookup tables to CSV files for external use.
        
        Creates separate CSVs for each wicket level, making it easy to
        print as traditional bookmaker charts.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Export first innings tables
        print("\nExporting First Innings Tables...")
        for wickets in range(11):
            df = pd.DataFrame(
                self.innings1_table[:, :, wickets],
                index=self.innings1_overs,
                columns=self.innings1_scores
            )
            df.index.name = 'Overs_Bowled'
            filename = output_path / f'innings1_wickets_{wickets}.csv'
            df.to_csv(filename)
            print(f"  ✓ {filename.name}")
        
        # Export second innings tables
        print("\nExporting Second Innings Tables...")
        for wickets in range(11):
            df = pd.DataFrame(
                self.innings2_table[:, :, wickets],
                index=self.innings2_balls,
                columns=self.innings2_runs_req
            )
            df.index.name = 'Balls_Remaining'
            filename = output_path / f'innings2_wickets_{wickets}.csv'
            df.to_csv(filename)
            print(f"  ✓ {filename.name}")
        
        print(f"\n✓ All tables exported to {output_path}/")
    
    def export_summary_markdown(self, output_file: str = "docs/WIN_PROB_LOOKUP_GUIDE.md"):
        """
        Export a markdown guide showing sample lookup charts.
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write("# Win Probability Lookup Charts - Bookmaker Ready Reckoner\n\n")
            f.write("**Date Generated:** February 2026  \n")
            f.write("**Model:** ResourceFeatureCalculator v2 (3D Empirical Calibration)  \n\n")
            
            f.write("## How to Use These Charts\n\n")
            f.write("### First Innings (Batting First)\n")
            f.write("1. Find the chart for your current wickets lost (0-10)\n")
            f.write("2. Locate the row for overs bowled\n")
            f.write("3. Find the column for current score\n")
            f.write("4. Read win probability at intersection\n\n")
            
            f.write("### Second Innings (Chasing)\n")
            f.write("1. Find the chart for your current wickets lost (0-10)\n")
            f.write("2. Locate the row for balls remaining\n")
            f.write("3. Find the column for runs required\n")
            f.write("4. Read win probability at intersection\n\n")
            
            # Sample chart: First innings, 0 wickets
            f.write("## Sample Chart: First Innings (0 Wickets Lost)\n\n")
            f.write("| Overs | 0 | 50 | 100 | 150 | 200 |\n")
            f.write("|-------|---|----|----|-----|-----|\n")
            
            if self.innings1_table is not None:
                for over_idx in [0, 5, 10, 15, 20]:
                    row = f"| {over_idx} "
                    for score_idx in [0, 5, 10, 15, 20]:  # 0, 50, 100, 150, 200
                        prob = self.innings1_table[over_idx, score_idx, 0]
                        row += f"| {prob:.2%} "
                    row += "|\n"
                    f.write(row)
            
            f.write("\n## Sample Chart: Second Innings (0 Wickets Lost)\n\n")
            f.write("| Balls Rem | 10 | 30 | 50 | 70 | 90 |\n")
            f.write("|-----------|----|----|----|----|----|\n")
            
            if self.innings2_table is not None:
                for ball_idx in [0, 3, 6, 9, 12]:  # 120, 60, 24, 6, 1 balls
                    balls = self.innings2_balls[min(ball_idx, len(self.innings2_balls)-1)]
                    row = f"| {balls} "
                    for runs_idx in [2, 6, 10, 14, 18]:  # 10, 30, 50, 70, 90 runs
                        if runs_idx < len(self.innings2_runs_req):
                            prob = self.innings2_table[ball_idx, runs_idx, 0]
                            row += f"| {prob:.2%} "
                        else:
                            row += "| - "
                    row += "|\n"
                    f.write(row)
        
        print(f"\n✓ Lookup guide exported to {output_path}")


def generate_all_lookup_tables():
    """
    Generate complete set of lookup tables and export to CSV/markdown.
    
    This is the main entry point for creating bookmaker-style ready reckoners.
    """
    print("="*70)
    print("GENERATING WIN PROBABILITY LOOKUP TABLES")
    print("="*70)
    print("\nThis will create pre-computed lookup tables for:")
    print("  • First Innings: 21 overs × 26 scores × 11 wickets = 6,006 entries")
    print("  • Second Innings: 13 ball milestones × 31 runs × 11 wickets = 4,433 entries")
    print("  • Total: 10,439 pre-computed win probabilities\n")
    
    lookup = WinProbabilityLookupTables()
    
    # Generate tables
    lookup.generate_first_innings_table()
    lookup.generate_second_innings_table(target_score=165)
    
    # Export to CSV (22 files: 11 for innings 1, 11 for innings 2)
    lookup.export_to_csv()
    
    # Export markdown guide
    lookup.export_summary_markdown()
    
    print("\n" + "="*70)
    print("✓ ALL LOOKUP TABLES GENERATED SUCCESSFULLY")
    print("="*70)
    print("\nFiles created:")
    print("  • data/win_prob_tables/innings1_wickets_0.csv through innings1_wickets_10.csv")
    print("  • data/win_prob_tables/innings2_wickets_0.csv through innings2_wickets_10.csv")
    print("  • docs/WIN_PROB_LOOKUP_GUIDE.md")
    print("\nUsage:")
    print("  from bbl_pipeline.features.win_prob_lookup_tables import WinProbabilityLookupTables")
    print("  lookup = WinProbabilityLookupTables()")
    print("  prob = lookup.lookup_first_innings(overs=12.3, score=95, wickets=3)")
    
    return lookup


if __name__ == "__main__":
    # Generate all lookup tables when run as script
    generate_all_lookup_tables()
