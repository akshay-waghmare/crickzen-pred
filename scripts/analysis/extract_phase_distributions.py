"""
Extract Phase-Based Run Distributions from Ball-by-Ball Data.

This script analyzes ball-by-ball parquet files to derive:
1. Run distributions by phase (powerplay, middle, death)
2. Wicket probabilities by phase  
3. League-specific variations
4. Wicket multipliers by wickets down

Output format matches NextBallSampler expectations:
{
  "run_dist": {
    "powerplay": {"0": 0.53, "1": 0.26, ...},
    "middle": {...},
    "death": {...}
  },
  "wicket_prob": {
    "powerplay": 0.044,
    "middle": 0.045,
    "death": 0.091
  },
  "boundary_pct": {...},
  "wicket_multiplier": {...}
}

Usage:
    # Extract from JSON files (recommended for new leagues)
    python scripts/analysis/extract_phase_distributions.py --json-dir wssm_female_json --league wssm
    
    # Extract from parquet (legacy, for leagues with processed features)
    python scripts/analysis/extract_phase_distributions.py --league bbl
    
    # Output to custom path
    python scripts/analysis/extract_phase_distributions.py --json-dir wpl_female_json --output data/phase_distributions_wpl.json
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, Optional
from collections import defaultdict, Counter

import pandas as pd
import numpy as np


def get_phase(balls_remaining: int) -> str:
    """
    Determine game phase based on balls remaining.
    
    Phases:
    - Powerplay: Overs 0-6 (120-84 balls remaining)
    - Middle: Overs 6-15 (84-36 balls remaining)  
    - Death: Overs 15-20 (36-0 balls remaining)
    """
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
        Dictionary with distributions by phase in sampler-compatible format
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
    elif 'overs_remaining' in df.columns:
        # Calculate from overs_remaining (e.g., 19.83 overs = 119 balls)
        df['balls_remaining'] = (df['overs_remaining'] * 6).round().astype(int)
        df['phase'] = df['balls_remaining'].apply(get_phase)
    else:
        print(f"Warning: Cannot determine balls_remaining from {parquet_path}")
        return {}
    
    # Initialize with sampler-compatible structure: data[key][phase]
    results = {
        'total_balls': len(df),
        'run_dist': {},      # Will be: {"powerplay": {"0": 0.53, ...}, ...}
        'wicket_prob': {},   # Will be: {"powerplay": 0.044, ...}
        'boundary_pct': {},  # Will be: {"powerplay": 0.137, ...}
        'wicket_multiplier': {},  # Will be: {"powerplay": 1.0, ...}
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
        
        # Calculate run distribution - output as string keys for JSON
        run_counts = phase_df[run_col].value_counts()
        run_dist = {}
        for runs in range(8):  # 0-7
            count = run_counts.get(runs, 0)
            run_dist[str(runs)] = count / len(phase_df)
        
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
        
        # Set wicket multiplier to 1.0 by default (phase-level)
        results['wicket_multiplier'][phase] = 1.0
    
    return results


def extract_from_json_dir(
    json_dir: Path,
    league: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract run distributions from Cricsheet JSON files.
    
    This is the recommended method for new leagues as it processes raw JSON
    directly without requiring processed feature parquet files.
    
    Args:
        json_dir: Directory containing Cricsheet JSON files
        league: Optional league code (for metadata only)
        
    Returns:
        Dictionary with distributions by phase in sampler-compatible format
    """
    json_files = list(json_dir.glob('*.json'))
    print(f'Processing {len(json_files)} JSON files from {json_dir}...')
    
    # Collect all balls by phase
    phase_balls = defaultdict(list)
    
    for json_file in json_files:
        try:
            with open(json_file) as f:
                match_data = json.load(f)
            
            for innings in match_data.get('innings', []):
                overs = innings.get('overs', [])
                for over_data in overs:
                    over_num = over_data.get('over', 0)
                    for delivery in over_data.get('deliveries', []):
                        # Skip wides/noballs for distribution accuracy
                        if 'extras' in delivery and any(k in delivery['extras'] for k in ['wides', 'noballs']):
                            continue
                        
                        runs = delivery.get('runs', {}).get('total', 0)
                        is_wicket = 'wickets' in delivery and len(delivery['wickets']) > 0
                        
                        # Calculate balls remaining
                        balls_bowled = int(over_num * 6)
                        balls_remaining = 120 - balls_bowled
                        
                        phase = get_phase(balls_remaining)
                        phase_balls[phase].append({
                            'runs': runs,
                            'is_wicket': is_wicket,
                            'is_boundary': runs >= 4
                        })
        except Exception as e:
            print(f'Error processing {json_file.name}: {e}')
    
    total_balls = sum(len(balls) for balls in phase_balls.values())
    print(f'Processed {len(json_files)} files')
    print(f'Total balls: {total_balls:,}')
    
    # Calculate distributions in sampler-compatible format
    results = {
        'total_balls': total_balls,
        'run_dist': {},
        'wicket_prob': {},
        'boundary_pct': {},
        'wicket_multiplier': {},
    }
    
    for phase in ['powerplay', 'middle', 'death']:
        balls = phase_balls[phase]
        if not balls:
            continue
        
        runs_list = [b['runs'] for b in balls]
        wickets = sum(1 for b in balls if b['is_wicket'])
        boundaries = sum(1 for b in balls if b['is_boundary'])
        
        # Run distribution with string keys for JSON
        run_counts = Counter(runs_list)
        total = len(runs_list)
        run_dist = {str(r): run_counts.get(r, 0) / total for r in range(8)}
        
        results['run_dist'][phase] = run_dist
        results['wicket_prob'][phase] = wickets / total if total > 0 else 0
        results['boundary_pct'][phase] = boundaries / total if total > 0 else 0
        results['wicket_multiplier'][phase] = 1.0
        
        # Print phase summary
        expected_runs = sum(runs_list) / total if total > 0 else 0
        print(f'\n{phase.upper()}:')
        print(f'  Balls: {total:,}')
        print(f'  Expected runs/ball: {expected_runs:.3f}')
        print(f'  Boundary %: {results["boundary_pct"][phase]:.1%}')
        print(f'  Wicket prob: {results["wicket_prob"][phase]:.2%}')
    
    return results


def merge_results(results_list: list) -> Dict[str, Any]:
    """
    Merge multiple extraction results with weighted averaging.
    
    Maintains sampler-compatible format: data[key][phase]
    """
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
            for runs_str, prob in dist.items():
                merged['run_dist'][phase][runs_str] += prob * n_balls
            phase_counts[phase] += n_balls
        
        for phase, prob in result.get('wicket_prob', {}).items():
            merged['wicket_prob'][phase] += prob * result['total_balls']
        
        for phase, pct in result.get('boundary_pct', {}).items():
            merged['boundary_pct'][phase] += pct * result['total_balls']
    
    # Normalize
    for phase in merged['run_dist']:
        total = sum(merged['run_dist'][phase].values())
        if total > 0:
            for runs_str in merged['run_dist'][phase]:
                merged['run_dist'][phase][runs_str] /= total
    
    for phase in merged['wicket_prob']:
        if merged['total_balls'] > 0:
            merged['wicket_prob'][phase] /= merged['total_balls']
    
    for phase in merged['boundary_pct']:
        if merged['total_balls'] > 0:
            merged['boundary_pct'][phase] /= merged['total_balls']
    
    # Set default wicket multipliers
    for phase in ['powerplay', 'middle', 'death']:
        if phase in merged['run_dist']:
            merged['wicket_multiplier'][phase] = 1.0
    
    # Convert defaultdicts to regular dicts (maintain sampler structure)
    return {
        'run_dist': {k: dict(v) for k, v in merged['run_dist'].items()},
        'wicket_prob': dict(merged['wicket_prob']),
        'boundary_pct': dict(merged['boundary_pct']),
        'wicket_multiplier': dict(merged['wicket_multiplier']),
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
    parser = argparse.ArgumentParser(
        description="Extract phase distributions from ball-by-ball data",
        epilog="Example: python extract_phase_distributions.py --json-dir wssm_female_json --league wssm"
    )
    parser.add_argument("--league", type=str, default=None, help="League code (bbl, sa20, ssm, wpl, etc.)")
    parser.add_argument("--json-dir", type=str, default=None, help="Directory containing Cricsheet JSON files (recommended)")
    parser.add_argument("--input-dir", type=str, default="data", help="Input data directory for parquet files")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    parser.add_argument("--format", choices=["json"], default="json", help="Output format (only JSON supported for sampler)")
    args = parser.parse_args()
    
    # Determine extraction method
    if args.json_dir:
        # Extract from JSON files (recommended)
        json_dir = Path(args.json_dir)
        if not json_dir.exists():
            print(f"Error: JSON directory not found: {json_dir}")
            return
        
        print(f"Extracting from JSON files in {json_dir}")
        merged = extract_from_json_dir(json_dir, league=args.league)
        
    else:
        # Extract from parquet files (legacy)
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
            print("Try using --json-dir to extract from Cricsheet JSON files instead.")
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
    
    if not merged.get('run_dist'):
        print("No distribution data extracted")
        return
    
    # Calculate total balls for summary
    total_balls = sum(
        len([k for k in dist.keys()]) * sum(dist.values()) * 1000  # Rough estimate
        for dist in merged['run_dist'].values()
    )
    
    # Output path
    output_path = args.output
    if output_path is None:
        league_suffix = f"_{args.league}" if args.league else ""
        output_path = f"data/phase_distributions{league_suffix}.json"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save JSON in sampler-compatible format
    with open(output_path, 'w') as f:
        json.dump(merged, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✓ Saved sampler-compatible distributions to {output_path}")
    print(f"{'='*60}")
    
    # Print summary
    print("\nSUMMARY")
    print("=" * 60)
    
    for phase in ['powerplay', 'middle', 'death']:
        if phase in merged['run_dist']:
            dist = merged['run_dist'][phase]
            # Convert string keys back to int for calculation
            expected_runs = sum(int(r) * p for r, p in dist.items())
            boundary_pct = merged['boundary_pct'].get(phase, 0)
            wicket_prob = merged['wicket_prob'].get(phase, 0)
            dot_pct = dist.get('0', 0)
            
            print(f"\n{phase.upper()}:")
            print(f"  Expected runs/ball: {expected_runs:.3f}")
            print(f"  Boundary %: {boundary_pct:.1%}")
            print(f"  Wicket prob: {wicket_prob:.2%}")
            print(f"  Dot ball %: {dot_pct:.1%}")
    
    print(f"\n{'='*60}")
    print("USAGE:")
    print(f"  sampler = NextBallSampler(seed=42, league='{args.league or 'custom'}')")
    print(f"  # Sampler will load from: {output_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
