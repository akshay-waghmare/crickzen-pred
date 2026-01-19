"""
Extract Phase-Based Run Distributions from Ball-by-Ball Data.

This script analyzes ball-by-ball parquet files to derive:
1. Run distributions by phase (powerplay, middle, death)
2. Wicket probabilities by phase  
3. League-specific variations
4. Wicket multipliers by wickets down

Tasks: T040, T041 from Monte Carlo Engine spec

Usage:
    # Extract from all leagues
    python scripts/analysis/extract_phase_distributions.py
    
    # Extract for specific league
    python scripts/analysis/extract_phase_distributions.py --league bbl
    
    # Output to custom path
    python scripts/analysis/extract_phase_distributions.py --output data/phase_distributions.json
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, Optional
from collections import defaultdict

import pandas as pd
import numpy as np


def get_phase(balls_remaining: int) -> str:
    """Determine game phase based on balls remaining."""
    if balls_remaining <= 0:
        return "death"
    overs_completed = (120 - balls_remaining) / 6
    if overs_completed < 6:
        return "powerplay"
    elif overs_completed < 15:
        return "middle"
    else:
        return "death"


def extract_from_parquet(
    parquet_path: Path,
    league: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract run distributions and wicket probabilities from parquet file.
    
    Args:
        parquet_path: Path to ball-by-ball parquet file
        league: Optional league filter
        
    Returns:
        Dictionary with distributions by phase
    """
    df = pd.read_parquet(parquet_path)
    
    # Filter by league if specified
    if league and 'league' in df.columns:
        df = df[df['league'] == league]
    
    # Calculate balls remaining (approximate from over/ball columns)
    if 'balls_remaining' in df.columns:
        df['phase'] = df['balls_remaining'].apply(get_phase)
    elif 'over' in df.columns and 'ball' in df.columns:
        df['balls_remaining'] = (20 - df['over']) * 6 - df['ball']
        df['phase'] = df['balls_remaining'].apply(get_phase)
    else:
        print(f"Warning: Cannot determine balls_remaining from {parquet_path}")
        return {}
    
    results = {
        'total_balls': len(df),
        'run_dist': {},
        'wicket_prob': {},
        'wicket_multiplier': {},
        'boundary_pct': {},
    }
    
    # Run distributions by phase
    for phase in ['powerplay', 'middle', 'death']:
        phase_df = df[df['phase'] == phase]
        if len(phase_df) == 0:
            continue
            
        # Get run column (try different names)
        run_col = None
        for col in ['runs_off_bat', 'runs', 'runs_scored', 'batsman_runs']:
            if col in phase_df.columns:
                run_col = col
                break
        
        if run_col is None:
            print(f"Warning: Cannot find runs column in {parquet_path}")
            continue
        
        # Calculate run distribution
        run_counts = phase_df[run_col].value_counts()
        run_dist = {}
        for runs in range(7):  # 0-6
            count = run_counts.get(runs, 0)
            run_dist[runs] = count / len(phase_df)
        
        results['run_dist'][phase] = run_dist
        
        # Calculate boundary percentage
        boundaries = phase_df[phase_df[run_col] >= 4]
        results['boundary_pct'][phase] = len(boundaries) / len(phase_df)
        
        # Wicket probability
        wicket_col = None
        for col in ['is_wicket', 'wicket', 'player_dismissed']:
            if col in phase_df.columns:
                wicket_col = col
                break
        
        if wicket_col:
            wicket_count = phase_df[wicket_col].sum()
            results['wicket_prob'][phase] = wicket_count / len(phase_df)
    
    # Wicket multiplier by wickets down
    if 'wickets_lost' in df.columns:
        wicket_col = None
        for col in ['is_wicket', 'wicket', 'player_dismissed']:
            if col in df.columns:
                wicket_col = col
                break
        
        if wicket_col:
            base_rate = df[wicket_col].mean()
            for wickets in range(10):
                wickets_df = df[df['wickets_lost'] == wickets]
                if len(wickets_df) > 100:  # Minimum sample size
                    wicket_rate = wickets_df[wicket_col].mean()
                    multiplier = wicket_rate / base_rate if base_rate > 0 else 1.0
                    results['wicket_multiplier'][wickets] = round(multiplier, 2)
    
    return results


def merge_results(results_list: list) -> Dict[str, Any]:
    """Merge multiple extraction results with weighted averaging."""
    merged = {
        'total_balls': 0,
        'run_dist': defaultdict(lambda: defaultdict(float)),
        'wicket_prob': defaultdict(float),
        'wicket_multiplier': defaultdict(float),
        'boundary_pct': defaultdict(float),
    }
    
    phase_counts = defaultdict(int)
    
    for result in results_list:
        if not result:
            continue
        merged['total_balls'] += result.get('total_balls', 0)
        
        for phase, dist in result.get('run_dist', {}).items():
            n_balls = result['total_balls']  # Approximate
            for runs, prob in dist.items():
                merged['run_dist'][phase][runs] += prob * n_balls
            phase_counts[phase] += n_balls
        
        for phase, prob in result.get('wicket_prob', {}).items():
            merged['wicket_prob'][phase] += prob * result['total_balls']
        
        for phase, pct in result.get('boundary_pct', {}).items():
            merged['boundary_pct'][phase] += pct * result['total_balls']
    
    # Normalize
    for phase in merged['run_dist']:
        total = sum(merged['run_dist'][phase].values())
        if total > 0:
            for runs in merged['run_dist'][phase]:
                merged['run_dist'][phase][runs] /= total
    
    for phase in merged['wicket_prob']:
        if merged['total_balls'] > 0:
            merged['wicket_prob'][phase] /= merged['total_balls']
    
    for phase in merged['boundary_pct']:
        if merged['total_balls'] > 0:
            merged['boundary_pct'][phase] /= merged['total_balls']
    
    # Convert defaultdicts to regular dicts
    return {
        'total_balls': merged['total_balls'],
        'run_dist': {k: dict(v) for k, v in merged['run_dist'].items()},
        'wicket_prob': dict(merged['wicket_prob']),
        'wicket_multiplier': dict(merged['wicket_multiplier']),
        'boundary_pct': dict(merged['boundary_pct']),
    }


def generate_python_config(results: Dict[str, Any], league: Optional[str] = None) -> str:
    """Generate Python config file content for simulation."""
    league_name = league.upper() if league else "GLOBAL"
    
    lines = [
        f'"""',
        f'Phase distributions for {league_name}.',
        f'Generated from {results["total_balls"]:,} balls.',
        f'"""',
        '',
        'from typing import Dict',
        '',
        f'# {league_name} Run Distribution by Phase',
        f'RUN_DIST_{league_name}: Dict[str, Dict[int, float]] = {{',
    ]
    
    for phase in ['powerplay', 'middle', 'death']:
        if phase in results['run_dist']:
            lines.append(f'    "{phase}": {{')
            for runs in range(7):
                prob = results['run_dist'][phase].get(runs, 0)
                lines.append(f'        {runs}: {prob:.4f},')
            lines.append('    },')
    
    lines.append('}')
    lines.append('')
    
    lines.append(f'# {league_name} Wicket Probability by Phase')
    lines.append(f'WICKET_PROB_{league_name}: Dict[str, float] = {{')
    for phase in ['powerplay', 'middle', 'death']:
        if phase in results['wicket_prob']:
            prob = results['wicket_prob'][phase]
            lines.append(f'    "{phase}": {prob:.4f},')
    lines.append('}')
    lines.append('')
    
    lines.append(f'# {league_name} Boundary Percentage by Phase')
    lines.append(f'BOUNDARY_PCT_{league_name}: Dict[str, float] = {{')
    for phase in ['powerplay', 'middle', 'death']:
        if phase in results['boundary_pct']:
            pct = results['boundary_pct'][phase]
            lines.append(f'    "{phase}": {pct:.4f},')
    lines.append('}')
    
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="Extract phase distributions from ball-by-ball data")
    parser.add_argument("--league", type=str, default=None, help="Specific league to extract (bbl, sa20, etc.)")
    parser.add_argument("--input-dir", type=str, default="data", help="Input data directory")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    parser.add_argument("--format", choices=["json", "python"], default="json", help="Output format")
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    
    # Find all relevant parquet files
    parquet_files = []
    
    # Look for ball-by-ball data in common locations
    patterns = [
        "**/training.parquet",
        "**/ball_by_ball.parquet",
        "**/matches/*.parquet",
    ]
    
    for pattern in patterns:
        parquet_files.extend(input_dir.glob(pattern))
    
    if not parquet_files:
        print(f"No parquet files found in {input_dir}")
        print("Looking for feature parquet files instead...")
        parquet_files = list(input_dir.glob("*_features*/training.parquet"))
    
    if not parquet_files:
        print("No suitable parquet files found.")
        return
    
    print(f"Found {len(parquet_files)} parquet files")
    
    # Extract from each file
    all_results = []
    for pf in parquet_files:
        print(f"Processing: {pf}")
        try:
            result = extract_from_parquet(pf, league=args.league)
            if result.get('total_balls', 0) > 0:
                all_results.append(result)
                print(f"  - {result['total_balls']:,} balls extracted")
        except Exception as e:
            print(f"  - Error: {e}")
    
    if not all_results:
        print("No data extracted")
        return
    
    # Merge results
    merged = merge_results(all_results)
    print(f"\nTotal balls analyzed: {merged['total_balls']:,}")
    
    # Output
    output_path = args.output
    if output_path is None:
        league_suffix = f"_{args.league}" if args.league else ""
        output_path = f"data/phase_distributions{league_suffix}.{args.format}"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if args.format == "json":
        with open(output_path, 'w') as f:
            json.dump(merged, f, indent=2)
        print(f"\nSaved to: {output_path}")
    else:
        content = generate_python_config(merged, args.league)
        with open(output_path, 'w') as f:
            f.write(content)
        print(f"\nSaved to: {output_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for phase in ['powerplay', 'middle', 'death']:
        if phase in merged['run_dist']:
            dist = merged['run_dist'][phase]
            expected_runs = sum(r * p for r, p in dist.items())
            boundary_pct = merged['boundary_pct'].get(phase, 0)
            wicket_prob = merged['wicket_prob'].get(phase, 0)
            
            print(f"\n{phase.upper()}:")
            print(f"  Expected runs/ball: {expected_runs:.2f}")
            print(f"  Boundary %: {boundary_pct:.1%}")
            print(f"  Wicket prob: {wicket_prob:.2%}")
            print(f"  Dot ball %: {dist.get(0, 0):.1%}")


if __name__ == "__main__":
    main()
