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


# ---------------------------------------------------------------------------
# Final-over empirical win-probability lookup (IPL-derived)
# Dimensions: runs_needed (0-25) × wickets_in_hand (0-10)
# Source: data/ipl_final_over_lookup.json
# ---------------------------------------------------------------------------
FINAL_OVER_WIN_PROB: Dict[int, Dict[int, float]] = {
    0:  {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.0, 8: 1.0, 9: 1.0, 10: 1.0},
    1:  {0: 0.0, 1: 0.2935, 2: 0.6038, 3: 0.927, 4: 0.9447, 5: 0.9589, 6: 1.0, 7: 1.0, 8: 1.0, 9: 1.0, 10: 1.0},
    2:  {0: 0.0, 1: 0.2786, 2: 0.5778, 3: 0.927, 4: 0.927, 5: 0.937, 6: 0.9529, 7: 0.9655, 8: 0.9752, 9: 0.9825, 10: 0.9879},
    3:  {0: 0.0, 1: 0.2596, 2: 0.5432, 3: 0.8484, 4: 0.8785, 5: 0.9047, 6: 0.9268, 7: 0.9449, 8: 0.9594, 9: 0.9706, 10: 0.9792},
    4:  {0: 0.0, 1: 0.2362, 2: 0.4992, 3: 0.7878, 4: 0.8246, 5: 0.8581, 6: 0.8878, 7: 0.9131, 8: 0.9341, 9: 0.9511, 10: 0.9644},
    5:  {0: 0.0, 1: 0.2089, 2: 0.4458, 3: 0.7114, 4: 0.7536, 5: 0.7941, 6: 0.8317, 7: 0.8655, 8: 0.8949, 9: 0.9197, 10: 0.9399},
    6:  {0: 0.0, 1: 0.179, 2: 0.3849, 3: 0.6206, 4: 0.6655, 5: 0.7109, 6: 0.7555, 7: 0.7977, 8: 0.8364, 9: 0.8708, 10: 0.9002},
    7:  {0: 0.0, 1: 0.1482, 2: 0.3203, 3: 0.5205, 4: 0.5641, 5: 0.6106, 6: 0.6588, 7: 0.7072, 8: 0.7544, 9: 0.7987, 10: 0.8389},
    8:  {0: 0.0, 1: 0.1187, 2: 0.2567, 3: 0.4187, 4: 0.4571, 5: 0.5, 6: 0.5469, 7: 0.5968, 8: 0.6484, 9: 0.7001, 10: 0.7503},
    9:  {0: 0.0, 1: 0.0922, 2: 0.1985, 3: 0.3234, 4: 0.3539, 5: 0.5, 6: 0.5, 7: 0.5, 8: 0.5255, 9: 0.5788, 10: 0.6341},
    10: {0: 0.0, 1: 0.0696, 2: 0.1487, 3: 0.2409, 4: 0.2627, 5: 0.2891, 6: 0.3204, 7: 0.3571, 8: 0.3994, 9: 0.4472, 10: 0.5},
    11: {0: 0.0, 1: 0.0514, 2: 0.1085, 3: 0.1085, 4: 0.1882, 5: 0.2059, 6: 0.2276, 7: 0.2539, 8: 0.2854, 9: 0.3226, 10: 0.3659},
    12: {0: 0.0, 1: 0.0373, 2: 0.0775, 3: 0.0775, 4: 0.131, 5: 0.1419, 6: 0.1555, 7: 0.1725, 8: 0.1934, 9: 0.2189, 10: 0.2497},
    13: {0: 0.0, 1: 0.0267, 2: 0.0545, 3: 0.0545, 4: 0.0545, 5: 0.0953, 6: 0.1032, 7: 0.1132, 8: 0.1259, 9: 0.1416, 10: 0.1611},
    14: {0: 0.0, 1: 0.0189, 2: 0.0379, 3: 0.0379, 4: 0.0379, 5: 0.063, 6: 0.0671, 7: 0.0726, 8: 0.0796, 9: 0.0885, 10: 0.0998},
    15: {0: 0.0, 1: 0.0133, 2: 0.0262, 3: 0.0262, 4: 0.0262, 5: 0.0411, 6: 0.043, 7: 0.0457, 8: 0.0494, 9: 0.0541, 10: 0.0601},
    16: {0: 0.0, 1: 0.0093, 2: 0.0179, 3: 0.0179, 4: 0.0179, 5: 0.0266, 6: 0.0273, 7: 0.0285, 8: 0.0302, 9: 0.0325, 10: 0.0356},
    17: {0: 0.0, 1: 0.0065, 2: 0.0123, 3: 0.0123, 4: 0.0123, 5: 0.0171, 6: 0.0173, 7: 0.0177, 8: 0.0184, 9: 0.0194, 10: 0.0208},
    18: {0: 0.0, 1: 0.0045, 2: 0.0083, 3: 0.0083, 4: 0.0083, 5: 0.011, 6: 0.011, 7: 0.011, 8: 0.0111, 9: 0.0115, 10: 0.0121},
    19: {0: 0.0, 1: 0.0031, 2: 0.0057, 3: 0.0057, 4: 0.0057, 5: 0.007, 6: 0.007, 7: 0.007, 8: 0.007, 9: 0.007, 10: 0.007},
    20: {0: 0.0, 1: 0.0022, 2: 0.0039, 3: 0.0039, 4: 0.0039, 5: 0.0045, 6: 0.0045, 7: 0.0045, 8: 0.0045, 9: 0.0045, 10: 0.0045},
    21: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0026, 4: 0.0026, 5: 0.0029, 6: 0.0029, 7: 0.0029, 8: 0.0029, 9: 0.0029, 10: 0.0029},
    22: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0018, 4: 0.0018, 5: 0.0018, 6: 0.0018, 7: 0.0018, 8: 0.0018, 9: 0.0018, 10: 0.0018},
    23: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0012, 4: 0.0012, 5: 0.0012, 6: 0.0012, 7: 0.0012, 8: 0.0012, 9: 0.0012, 10: 0.0012},
    24: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0008, 4: 0.0008, 5: 0.0008, 6: 0.0008, 7: 0.0008, 8: 0.0008, 9: 0.0008, 10: 0.0008},
    25: {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0006, 4: 0.0006, 5: 0.0006, 6: 0.0006, 7: 0.0006, 8: 0.0006, 9: 0.0006, 10: 0.0006},
}


def get_final_over_win_prob(
    runs_needed: int,
    wickets_in_hand: int,
    lookup_table: Dict[int, Dict[int, float]] = None,
) -> float:
    """Return chasing-team win probability for the final over from an empirical lookup.

    Contract:
        1. runs_needed <= 0  → 1.0 (already won)
        2. wickets_in_hand <= 0 → 0.0 (all out)
        3. Direct table hit → return value
        4. runs_needed > max key → 0.01 (near-impossible)
        5. Missing cell → interpolate from nearest keys, preserving monotonicity
        6. Result clamped to [0.0, 1.0]
    """
    if runs_needed <= 0:
        return 1.0
    if wickets_in_hand <= 0:
        return 0.0

    table = lookup_table if lookup_table is not None else FINAL_OVER_WIN_PROB

    # Direct hit
    if runs_needed in table and wickets_in_hand in table[runs_needed]:
        return float(max(0.0, min(1.0, table[runs_needed][wickets_in_hand])))

    # Beyond maximum runs row → near-impossible
    max_runs_key = max(table.keys())
    if runs_needed > max_runs_key:
        return 0.01

    # Interpolate from nearest cells
    all_runs = sorted(table.keys())
    all_wkts = sorted({w for row in table.values() for w in row.keys()})

    # Find bracketing runs keys
    lower_r = max((r for r in all_runs if r <= runs_needed), default=all_runs[0])
    upper_r = min((r for r in all_runs if r >= runs_needed), default=all_runs[-1])

    # Find bracketing wicket keys
    lower_w = max((w for w in all_wkts if w <= wickets_in_hand), default=all_wkts[0])
    upper_w = min((w for w in all_wkts if w >= wickets_in_hand), default=all_wkts[-1])

    def _safe_get(r: int, w: int) -> Optional[float]:
        return table.get(r, {}).get(w)

    # Gather corner values for bilinear interpolation
    v_ll = _safe_get(lower_r, lower_w)
    v_lu = _safe_get(lower_r, upper_w)
    v_ul = _safe_get(upper_r, lower_w)
    v_uu = _safe_get(upper_r, upper_w)

    corners = [v for v in (v_ll, v_lu, v_ul, v_uu) if v is not None]
    if not corners:
        return 0.01

    # If the bracket collapses on one axis, do linear interpolation on the other
    if lower_r == upper_r and lower_w == upper_w:
        result = corners[0]
    elif lower_r == upper_r:
        # Interpolate along wickets only
        if v_ll is not None and v_lu is not None and upper_w != lower_w:
            t = (wickets_in_hand - lower_w) / (upper_w - lower_w)
            result = v_ll + t * (v_lu - v_ll)
        else:
            result = sum(corners) / len(corners)
    elif lower_w == upper_w:
        # Interpolate along runs only
        if v_ll is not None and v_ul is not None and upper_r != lower_r:
            t = (runs_needed - lower_r) / (upper_r - lower_r)
            result = v_ll + t * (v_ul - v_ll)
        else:
            result = sum(corners) / len(corners)
    else:
        # Bilinear interpolation
        t_r = (runs_needed - lower_r) / (upper_r - lower_r)
        t_w = (wickets_in_hand - lower_w) / (upper_w - lower_w)
        nones = [v_ll, v_lu, v_ul, v_uu]
        if all(v is not None for v in nones):
            top = v_ll * (1 - t_w) + v_lu * t_w
            bot = v_ul * (1 - t_w) + v_uu * t_w
            result = top * (1 - t_r) + bot * t_r
        else:
            result = sum(corners) / len(corners)

    return float(max(0.0, min(1.0, result)))


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
