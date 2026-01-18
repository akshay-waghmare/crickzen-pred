"""
Performance benchmark for Monte Carlo simulation engine.

Measures execution time for various simulation configurations
and validates against performance targets.

Performance targets (from spec.md):
- 1-ball simulation (1000 sims): < 200ms
- 6-ball simulation (2000 sims): < 500ms
"""

import time
import numpy as np
import argparse
from typing import List, Dict, Any
import json

from bbl_pipeline.simulation import (
    MatchState,
    simulate,
    simulate_vectorized,
    simulate_single_ball,
    simulate_one_over,
)


def create_test_state(
    innings: int = 2,
    score: int = 100,
    wickets_lost: int = 3,
    balls_remaining: int = 48,
    target_runs: int = 170,
    league: str = "bbl",
) -> MatchState:
    """Create a test match state."""
    return MatchState(
        innings=innings,
        score=score,
        wickets_lost=wickets_lost,
        balls_remaining=balls_remaining,
        target_runs=target_runs if innings == 2 else None,
        batting_team="Melbourne Stars",
        bowling_team="Sydney Sixers",
        league=league,
    )


def benchmark_single_ball(
    n_runs: int = 10,
    n_simulations: int = 1000,
) -> Dict[str, Any]:
    """Benchmark 1-ball simulation."""
    state = create_test_state()
    times = []
    
    for _ in range(n_runs):
        start = time.perf_counter()
        result = simulate_single_ball(state, n_simulations=n_simulations)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
    
    return {
        "name": f"1-ball ({n_simulations} sims)",
        "target_ms": 200,
        "mean_ms": np.mean(times),
        "std_ms": np.std(times),
        "min_ms": np.min(times),
        "max_ms": np.max(times),
        "p95_ms": np.percentile(times, 95),
        "passed": np.mean(times) < 200,
    }


def benchmark_six_ball_naive(
    n_runs: int = 10,
    n_simulations: int = 2000,
) -> Dict[str, Any]:
    """Benchmark 6-ball simulation (naive loop)."""
    state = create_test_state()
    times = []
    
    for _ in range(n_runs):
        start = time.perf_counter()
        result = simulate(state, horizon=6, n_simulations=n_simulations)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
    
    return {
        "name": f"6-ball naive ({n_simulations} sims)",
        "target_ms": 1000,  # Relaxed for naive
        "mean_ms": np.mean(times),
        "std_ms": np.std(times),
        "min_ms": np.min(times),
        "max_ms": np.max(times),
        "p95_ms": np.percentile(times, 95),
        "passed": np.mean(times) < 1000,
    }


def benchmark_six_ball_vectorized(
    n_runs: int = 10,
    n_simulations: int = 2000,
) -> Dict[str, Any]:
    """Benchmark 6-ball simulation (vectorized)."""
    state = create_test_state()
    times = []
    
    for _ in range(n_runs):
        start = time.perf_counter()
        result = simulate_vectorized(state, horizon=6, n_simulations=n_simulations)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
    
    return {
        "name": f"6-ball vectorized ({n_simulations} sims)",
        "target_ms": 500,
        "mean_ms": np.mean(times),
        "std_ms": np.std(times),
        "min_ms": np.min(times),
        "max_ms": np.max(times),
        "p95_ms": np.percentile(times, 95),
        "passed": np.mean(times) < 500,
    }


def benchmark_one_over(
    n_runs: int = 10,
    n_simulations: int = 5000,
) -> Dict[str, Any]:
    """Benchmark 1-over (6-ball) convenience function."""
    state = create_test_state()
    times = []
    
    for _ in range(n_runs):
        start = time.perf_counter()
        result = simulate_one_over(state, n_simulations=n_simulations)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
    
    return {
        "name": f"1-over ({n_simulations} sims)",
        "target_ms": 1000,
        "mean_ms": np.mean(times),
        "std_ms": np.std(times),
        "min_ms": np.min(times),
        "max_ms": np.max(times),
        "p95_ms": np.percentile(times, 95),
        "passed": np.mean(times) < 1000,
    }


def print_results(results: List[Dict[str, Any]]) -> None:
    """Print benchmark results as a table."""
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)
    print(f"{'Benchmark':<35} {'Mean':<10} {'Std':<10} {'P95':<10} {'Target':<10} {'Status':<8}")
    print("-" * 80)
    
    all_passed = True
    for r in results:
        status = "✓ PASS" if r["passed"] else "✗ FAIL"
        if not r["passed"]:
            all_passed = False
        
        print(
            f"{r['name']:<35} "
            f"{r['mean_ms']:<10.1f} "
            f"{r['std_ms']:<10.1f} "
            f"{r['p95_ms']:<10.1f} "
            f"{r['target_ms']:<10} "
            f"{status:<8}"
        )
    
    print("-" * 80)
    overall = "✓ ALL PASSED" if all_passed else "✗ SOME FAILED"
    print(f"Overall: {overall}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Benchmark Monte Carlo simulation")
    parser.add_argument("--runs", type=int, default=10, help="Number of benchmark runs")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    print("Running benchmarks...")
    
    results = [
        benchmark_single_ball(n_runs=args.runs),
        benchmark_six_ball_naive(n_runs=args.runs),
        benchmark_six_ball_vectorized(n_runs=args.runs),
        benchmark_one_over(n_runs=args.runs),
    ]
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_results(results)
    
    # Return exit code based on pass/fail
    all_passed = all(r["passed"] for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
