"""
Analyze model vs market prediction accuracy against actual T20 World Cup 2026 results.

Compares final recorded probabilities (model vs market) against actual match outcomes
to measure prediction calibration and market efficiency.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple

# Match results from T20 World Cup 2026
WORLD_CUP_RESULTS = {
    "nam-vs-nld-10th-match-t20-world-cup-2026": ("Namibia", "Netherlands", "Netherlands"),
    "uae-vs-nz-11th-match-t20-world-cup-2026": ("UAE", "New Zealand", "New Zealand"),
    "pak-vs-usa-12th-match-t20-world-cup-2026": ("Pakistan", "USA", "Pakistan"),
    "sa-vs-afg-13th-match-t20-world-cup-2026": ("South Africa", "Afghanistan", "South Africa"),  # Super over
    "aus-vs-ire-14th-match-t20-world-cup-2026": ("Australia", "Ireland", "Australia"),
    "wi-vs-eng-15th-match-t20-world-cup-2026": ("West Indies", "England", "West Indies"),
    "sl-vs-oman-16th-match-t20-world-cup-2026": ("Sri Lanka", "Oman", "Sri Lanka"),
    "nep-vs-ita-17th-match-t20-world-cup-2026": ("Nepal", "Italy", "Italy"),
    "ind-vs-nam-18th-match-t20-world-cup-2026": ("India", "Namibia", "India"),
    "zim-vs-aus-19th-match-t20-world-cup-2026": ("Zimbabwe", "Australia", "Zimbabwe"),
    "can-vs-uae-20th-match-t20-world-cup-2026": ("Canada", "UAE", "UAE"),
    "usa-vs-nld-21st-match-t20-world-cup-2026": ("USA", "Netherlands", "USA"),
    "ire-vs-oman-22nd-match-t20-world-cup-2026": ("Ireland", "Oman", "Ireland"),
    "sco-vs-eng-23rd-match-t20-world-cup-2026": ("Scotland", "England", "England"),
    "nz-vs-sa-24th-match-t20-world-cup-2026": ("New Zealand", "South Africa", "South Africa"),
    "nep-vs-wi-25th-match-t20-world-cup-2026": ("Nepal", "West Indies", "West Indies"),
    "usa-vs-nam-26th-match-t20-world-cup-2026": ("USA", "Namibia", "USA"),
    "ind-vs-pak-27th-match-t20-world-cup-2026": ("India", "Pakistan", "India"),
    "uae-vs-afg-28th-match-t20-world-cup-2026": ("UAE", "Afghanistan", "Afghanistan"),
    "eng-vs-ita-29th-match-t20-world-cup-2026": ("England", "Italy", "England"),
    "aus-vs-sl-30th-match-t20-world-cup-2026": ("Australia", "Sri Lanka", "Sri Lanka"),
    "can-vs-nz-31st-match-t20-world-cup-2026": ("Canada", "New Zealand", "New Zealand"),
    "ind-vs-nld-36th-match-t20-world-cup-2026": ("India", "Netherlands", "India"),
    "ita-vs-wi-37th-match-t20-world-cup-2026": ("Italy", "West Indies", "West Indies"),
    "sl-vs-zim-38th-match-t20-world-cup-2026": ("Sri Lanka", "Zimbabwe", "Zimbabwe"),
    "afg-vs-can-39th-match-t20-world-cup-2026": ("Afghanistan", "Canada", "Afghanistan"),
    "aus-vs-oma-40th-match-t20-world-cup-2026": ("Australia", "Oman", "Australia"),
    "eng-vs-sl-42nd-t20i--super-8-group-2nd-match-t20-world-cup-2026": ("England", "Sri Lanka", "England"),
    "ind-vs-sa-43rd-t20i--super-8-group-1st-match-t20-world-cup-2026": ("South Africa", "India", "South Africa"),
}

def load_recorded_match(match_id: str, league: str = "t20i") -> pd.DataFrame:
    """Load recorded match state file."""
    match_file = Path(f"data/match_states/{league}/{match_id}.parquet")
    if match_file.exists():
        return pd.read_parquet(match_file)
    return None

def get_final_prediction(df: pd.DataFrame, batting_team: str) -> Dict:
    """Get final recorded prediction for a match."""
    if df is None or len(df) == 0:
        return None
    
    # Get last ball state
    last_row = df.iloc[-1]
    
    return {
        'batting_team': last_row['batting_team'],
        'bowl_team': last_row['bowling_team'],
        'innings': int(last_row['innings']),
        'over': last_row['over_number'],
        'model_prob': float(last_row['model_final_prob']) if pd.notna(last_row['model_final_prob']) else None,
        'market_prob': float(last_row['market_batting_team_prob']) if pd.notna(last_row['market_batting_team_prob']) else None,
        'total_runs': int(last_row['total_runs']),
        'wickets': int(last_row['wickets']),
    }

def analyze_prediction_accuracy():
    """Analyze model vs market prediction accuracy against actual results."""
    
    results = []
    
    for match_id, (team1, team2, winner) in WORLD_CUP_RESULTS.items():
        df = load_recorded_match(match_id)
        
        if df is None:
            continue
        
        pred = get_final_prediction(df, team1)
        if pred is None:
            continue
        
        batting_team = pred['batting_team']
        innings = pred['innings']
        
        # Determine which team is batting (first occurrence in match)
        if innings == 1:
            # Innings 1 - batting team from match start
            batting_prob_for_match = pred['model_prob']  # Prob that batch team wins match
            market_prob_for_match = pred['market_prob']
        else:
            # Innings 2 - prob is for current batting team to win
            batting_prob_for_match = pred['model_prob']
            market_prob_for_match = pred['market_prob']
        
        # Did batting team actually win?
        batting_team_won = (winner == batting_team)
        
        # Calculate errors
        model_error = abs(batting_prob_for_match - (1.0 if batting_team_won else 0.0)) if batting_prob_for_match else None
        market_error = abs(market_prob_for_match - (1.0 if batting_team_won else 0.0)) if market_prob_for_match else None
        
        result = {
            'match_id': match_id,
            'match': f"{team1} vs {team2}",
            'batting_team': batting_team,
            'winner': winner,
            'batting_won': batting_team_won,
            'innings': innings,
            'model_prob': batting_prob_for_match,
            'market_prob': market_prob_for_match,
            'model_error': model_error,
            'market_error': market_error,
            'model_correct_direction': (batting_prob_for_match > 0.5) == batting_team_won if batting_prob_for_match else None,
            'market_correct_direction': (market_prob_for_match > 0.5) == batting_team_won if market_prob_for_match else None,
            'over': pred['over'],
            'state': f"{pred['total_runs']}/{pred['wickets']}"
        }
        results.append(result)
    
    return pd.DataFrame(results)

def print_analysis(df: pd.DataFrame):
    """Print comprehensive analysis results."""
    print("\n" + "="*100)
    print("MODEL vs MARKET PREDICTION ACCURACY: T20 WORLD CUP 2026 RESULTS")
    print("="*100)
    
    # Filter to rows with valid data
    valid_df = df[(df['model_prob'].notna()) | (df['market_prob'].notna())].copy()
    
    if len(valid_df) == 0:
        print("No recorded matches with probability data found.")
        return
    
    print(f"\nAnalyzed {len(valid_df)} recorded matches")
    
    # Overall accuracy
    print("\n1. OVERALL ACCURACY")
    print("-" * 100)
    
    # Model accuracy
    if valid_df['model_error'].notna().sum() > 0:
        model_mae = valid_df[valid_df['model_error'].notna()]['model_error'].mean()
        model_direction_acc = valid_df[valid_df['model_correct_direction'].notna()]['model_correct_direction'].sum() / valid_df[valid_df['model_correct_direction'].notna()].shape[0] if valid_df['model_correct_direction'].notna().sum() > 0 else 0
        
        print(f"Model Prediction:")
        print(f"  Mean Absolute Error: {model_mae:.4f}")
        print(f"  Directional Accuracy: {model_direction_acc:.1%} (correct side of 50%)")
        print(f"  Matches analyzed: {valid_df[valid_df['model_error'].notna()].shape[0]}")
    
    # Market accuracy
    if valid_df['market_error'].notna().sum() > 0:
        market_mae = valid_df[valid_df['market_error'].notna()]['market_error'].mean()
        market_direction_acc = valid_df[valid_df['market_correct_direction'].notna()]['market_correct_direction'].sum() / valid_df[valid_df['market_correct_direction'].notna()].shape[0] if valid_df['market_correct_direction'].notna().sum() > 0 else 0
        
        print(f"\nMarket Prediction:")
        print(f"  Mean Absolute Error: {market_mae:.4f}")
        print(f"  Directional Accuracy: {market_direction_acc:.1%} (correct side of 50%)")
        print(f"  Matches analyzed: {valid_df[valid_df['market_error'].notna()].shape[0]}")
    
    # Head-to-head comparison
    if (valid_df['model_error'].notna() & valid_df['market_error'].notna()).sum() > 0:
        comparable = valid_df[valid_df['model_error'].notna() & valid_df['market_error'].notna()]
        model_better = (comparable['model_error'] < comparable['market_error']).sum()
        market_better = (comparable['market_error'] < comparable['model_error']).sum()
        equal = (comparable['model_error'] == comparable['market_error']).sum()
        
        print(f"\nDirect Comparison (when both have probabilities):")
        print(f"  Model better: {model_better}/{len(comparable)} ({model_better/len(comparable):.1%})")
        print(f"  Market better: {market_better}/{len(comparable)} ({market_better/len(comparable):.1%})")
        print(f"  Equal: {equal}/{len(comparable)} ({equal/len(comparable):.1%})")
    
    # By innings
    print("\n2. BY INNINGS")
    print("-" * 100)
    for inn in [1, 2]:
        inn_df = valid_df[valid_df['innings'] == inn]
        if len(inn_df) > 0:
            if inn_df['model_error'].notna().sum() > 0:
                model_mae = inn_df[inn_df['model_error'].notna()]['model_error'].mean()
                print(f"Innings {inn}: Model MAE = {model_mae:.4f} ({inn_df['model_error'].notna().sum()} matches)")
    
    # Show predictions vs outcomes
    print("\n3. DETAILED PREDICTIONS vs OUTCOMES")
    print("-" * 100)
    
    display_cols = ['match', 'batting_team', 'winner', 'batting_won', 'model_prob', 'market_prob', 'model_error', 'market_error']
    
    print("\nMatches where MODEL was more confident than MARKET:")
    model_confident = valid_df[(valid_df['model_prob'].notna()) & (valid_df['market_prob'].notna())].copy()
    model_confident['model_gap'] = (model_confident['model_prob'] - 0.5).abs()
    model_confident['market_gap'] = (model_confident['market_prob'] - 0.5).abs()
    model_confident = model_confident[model_confident['model_gap'] > model_confident['market_gap']].head(10)
    
    if len(model_confident) > 0:
        for _, row in model_confident.iterrows():
            outcome = "✅ CORRECT" if row['batting_won'] else "❌ WRONG"
            print(f"  {row['match']:<40} | Model: {row['model_prob']:.1%} | Market: {row['market_prob']:.1%} | {outcome}")
    
    print("\nMatches where MARKET was more confident than MODEL:")
    market_confident = valid_df[(valid_df['model_prob'].notna()) & (valid_df['market_prob'].notna())].copy()
    market_confident['model_gap'] = (market_confident['model_prob'] - 0.5).abs()
    market_confident['market_gap'] = (market_confident['market_prob'] - 0.5).abs()
    market_confident = market_confident[market_confident['market_gap'] > market_confident['model_gap']].head(10)
    
    if len(market_confident) > 0:
        for _, row in market_confident.iterrows():
            outcome = "✅ CORRECT" if row['batting_won'] else "❌ WRONG"
            print(f"  {row['match']:<40} | Model: {row['model_prob']:.1%} | Market: {row['market_prob']:.1%} | {outcome}")
    
    # Save detailed results
    results_file = Path("data/model_vs_market_accuracy_vs_results.csv")
    valid_df.to_csv(results_file, index=False)
    print(f"\n✅ Detailed results saved to: {results_file}")

def main():
    df = analyze_prediction_accuracy()
    print_analysis(df)

if __name__ == "__main__":
    main()
