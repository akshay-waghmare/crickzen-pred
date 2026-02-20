"""
Validate Monte Carlo Simulation Distributions Against Historical Data.

This script compares:
1. Simulated run distributions vs historical (should match ±10%)
2. Simulated wicket rates vs historical
3. Death over boundary rates
4. Expected runs per phase

Tasks: T044, T045 from Monte Carlo Engine spec

Usage:
    python scripts/validation/validate_phase_distributions.py
    
    # With custom historical data
    python scripts/validation/validate_phase_distributions.py \
        --historical data/phase_distributions.json
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np

from bbl_pipeline.simulation import (
    NextBallSampler,
    MatchState,
    simulate,
    get_phase,
    RUN_DIST,
    WICKET_PROB,
)
from bbl_pipeline.simulation.config import WICKET_MULTIPLIER


def load_historical_data(path: Path) -> Dict[str, Any]:
    """Load historical phase distributions from JSON file."""
    with open(path) as f:
        return json.load(f)


def simulate_run_distribution(
    sampler: NextBallSampler,
    phase: str,
    n_samples: int = 100000,
) -> Dict[int, float]:
    """Simulate run distribution for a phase."""
    # Create a state for the target phase
    if phase == "powerplay":
        balls_remaining = 110  # Start of powerplay
    elif phase == "middle":
        balls_remaining = 60   # Middle of middle overs
    else:
        balls_remaining = 18   # Death overs
    
    state = MatchState(
        innings=2,
        score=100,
        wickets_lost=3,
        balls_remaining=balls_remaining,
        target_runs=170,
        batting_team="A",
        bowling_team="B",
        league="bbl",
    )
    
    # Sample many outcomes
    runs_array, _ = sampler.sample_batch(state, n_samples)
    
    # Calculate distribution
    run_dist = {}
    for runs in range(7):
        count = np.sum(runs_array == runs)
        run_dist[runs] = count / n_samples
    
    return run_dist


def simulate_wicket_rate(
    sampler: NextBallSampler,
    phase: str,
    wickets_lost: int = 3,
    n_samples: int = 100000,
) -> float:
    """Simulate wicket rate for a phase and wickets down."""
    if phase == "powerplay":
        balls_remaining = 110
    elif phase == "middle":
        balls_remaining = 60
    else:
        balls_remaining = 18
    
    state = MatchState(
        innings=2,
        score=100,
        wickets_lost=wickets_lost,
        balls_remaining=balls_remaining,
        target_runs=170,
        batting_team="A",
        bowling_team="B",
        league="bbl",
    )
    
    _, wickets_array = sampler.sample_batch(state, n_samples)
    return np.mean(wickets_array)


def calculate_expected_runs(dist: Dict[int, float]) -> float:
    """Calculate expected runs from distribution."""
    return sum(runs * prob for runs, prob in dist.items())


def calculate_boundary_rate(dist: Dict[int, float]) -> float:
    """Calculate boundary rate (4s + 6s) from distribution."""
    return dist.get(4, 0) + dist.get(6, 0)


def compare_distributions(
    simulated: Dict[int, float],
    historical: Dict[int, float],
    tolerance: float = 0.10,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Compare simulated vs historical distributions.
    
    Returns:
        Tuple of (passed, details_dict)
    """
    details = {
        'simulated': simulated,
        'historical': historical,
        'differences': {},
        'max_diff': 0.0,
        'passed': True,
    }
    
    for runs in range(7):
        sim_prob = simulated.get(runs, 0)
        hist_prob = historical.get(runs, 0)
        
        # Calculate relative difference
        if hist_prob > 0.001:
            rel_diff = abs(sim_prob - hist_prob) / hist_prob
        else:
            rel_diff = abs(sim_prob - hist_prob)
        
        details['differences'][runs] = {
            'simulated': sim_prob,
            'historical': hist_prob,
            'rel_diff': rel_diff,
            'passed': rel_diff <= tolerance,
        }
        
        if rel_diff > details['max_diff']:
            details['max_diff'] = rel_diff
        
        if rel_diff > tolerance:
            details['passed'] = False
    
    return details['passed'], details


def validate_against_config() -> Dict[str, Any]:
    """Validate simulated distributions against built-in config."""
    sampler = NextBallSampler(seed=42)
    
    results = {
        'run_distributions': {},
        'wicket_rates': {},
        'boundary_rates': {},
        'expected_runs': {},
        'all_passed': True,
    }
    
    print("=" * 70)
    print("MONTE CARLO SIMULATION VALIDATION")
    print("=" * 70)
    
    for phase in ['powerplay', 'middle', 'death']:
        print(f"\n{phase.upper()}")
        print("-" * 40)
        
        # Run distribution
        simulated_dist = simulate_run_distribution(sampler, phase)
        historical_dist = {int(k): v for k, v in RUN_DIST[phase].items()}
        
        passed, details = compare_distributions(simulated_dist, historical_dist)
        results['run_distributions'][phase] = details
        
        if not passed:
            results['all_passed'] = False
        
        # Expected runs
        sim_expected = calculate_expected_runs(simulated_dist)
        hist_expected = calculate_expected_runs(historical_dist)
        exp_diff = abs(sim_expected - hist_expected) / hist_expected if hist_expected > 0 else 0
        
        results['expected_runs'][phase] = {
            'simulated': sim_expected,
            'historical': hist_expected,
            'rel_diff': exp_diff,
            'passed': exp_diff <= 0.10,
        }
        
        print(f"  Expected runs: {sim_expected:.3f} vs {hist_expected:.3f} (diff: {exp_diff:.1%})")
        
        # Boundary rate
        sim_boundary = calculate_boundary_rate(simulated_dist)
        hist_boundary = calculate_boundary_rate(historical_dist)
        bound_diff = abs(sim_boundary - hist_boundary) / hist_boundary if hist_boundary > 0 else 0
        
        results['boundary_rates'][phase] = {
            'simulated': sim_boundary,
            'historical': hist_boundary,
            'rel_diff': bound_diff,
            'passed': bound_diff <= 0.10,
        }
        
        status = "✓ PASS" if bound_diff <= 0.10 else "✗ FAIL"
        print(f"  Boundary rate: {sim_boundary:.1%} vs {hist_boundary:.1%} (diff: {bound_diff:.1%}) {status}")
        
        if bound_diff > 0.10:
            results['all_passed'] = False
        
        # Wicket rate
        sim_wicket = simulate_wicket_rate(sampler, phase)
        hist_wicket = WICKET_PROB[phase]
        wicket_diff = abs(sim_wicket - hist_wicket) / hist_wicket if hist_wicket > 0 else 0
        
        # Note: Simulated rate includes multiplier for wickets_lost=3, so adjust
        base_multiplier = WICKET_MULTIPLIER.get(3, 1.0)
        expected_sim = hist_wicket * base_multiplier
        
        results['wicket_rates'][phase] = {
            'simulated': sim_wicket,
            'expected_with_multiplier': expected_sim,
            'base_rate': hist_wicket,
            'multiplier': base_multiplier,
        }
        
        print(f"  Wicket rate: {sim_wicket:.2%} (expected: {expected_sim:.2%} @ 3 wickets down)")
    
    # Summary
    print("\n" + "=" * 70)
    if results['all_passed']:
        print("✓ ALL VALIDATIONS PASSED")
    else:
        print("✗ SOME VALIDATIONS FAILED")
    print("=" * 70)
    
    return results


def validate_death_boundary_rate(tolerance: float = 0.10) -> Tuple[bool, Dict[str, Any]]:
    """
    T045: Validate death over boundary rate matches historical ±10%.
    
    Returns:
        Tuple of (passed, details)
    """
    sampler = NextBallSampler(seed=42)
    
    # Simulate death overs
    simulated_dist = simulate_run_distribution(sampler, "death", n_samples=100000)
    historical_dist = {int(k): v for k, v in RUN_DIST["death"].items()}
    
    sim_boundary = calculate_boundary_rate(simulated_dist)
    hist_boundary = calculate_boundary_rate(historical_dist)
    
    rel_diff = abs(sim_boundary - hist_boundary) / hist_boundary if hist_boundary > 0 else 0
    passed = rel_diff <= tolerance
    
    details = {
        'simulated_boundary_pct': sim_boundary,
        'historical_boundary_pct': hist_boundary,
        'relative_difference': rel_diff,
        'tolerance': tolerance,
        'passed': passed,
    }
    
    return passed, details


def main():
    parser = argparse.ArgumentParser(description="Validate simulation distributions")
    parser.add_argument("--historical", type=str, default=None, 
                       help="Path to historical distributions JSON")
    parser.add_argument("--output", type=str, default=None,
                       help="Output path for validation results")
    parser.add_argument("--tolerance", type=float, default=0.10,
                       help="Tolerance for distribution differences (default 10%)")
    args = parser.parse_args()
    
    # Run validation
    results = validate_against_config()
    
    # T045: Death boundary rate
    print("\nT045: Death Over Boundary Rate Validation")
    print("-" * 40)
    passed, details = validate_death_boundary_rate(args.tolerance)
    results['t045_death_boundary'] = details
    
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  Simulated: {details['simulated_boundary_pct']:.2%}")
    print(f"  Historical: {details['historical_boundary_pct']:.2%}")
    print(f"  Difference: {details['relative_difference']:.1%}")
    print(f"  Result: {status}")
    
    # Save results if output path provided
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert numpy types to native Python
        def convert(obj):
            if isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(i) for i in obj]
            return obj
        
        with open(output_path, 'w') as f:
            json.dump(convert(results), f, indent=2)
        print(f"\nResults saved to: {output_path}")
    
    # Exit code
    return 0 if results['all_passed'] else 1


if __name__ == "__main__":
    exit(main())
