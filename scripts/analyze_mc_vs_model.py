"""
Analyze Monte Carlo vs ML Model Win Probabilities for BBL.

Compares predictions against ACTUAL OUTCOMES (is_winner column):
1. ML Model predictions (direct) - Uses full features from training data
2. MC predictions (resource evaluator) - Simulates forward, evaluates with resource_win_prob
3. Resource win prob baseline - Direct resource_win_prob from features

IMPORTANT: All methods are evaluated against ACTUAL match outcomes (is_winner).
This is the correct way to measure predictive accuracy.

Previous analysis was flawed because it compared MC to resource_win_prob directly,
but MC USES resource_win_prob as its evaluator - creating a circular comparison.

Metrics: Log Loss, Brier Score, ECE (all measured against actual outcomes)
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import time
from typing import List, Dict, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.simulation.engine import simulate
from bbl_pipeline.simulation.state import MatchState as SimMatchState
from bbl_pipeline.inference.schema import MatchState
from bbl_pipeline.features.calculator import ResourceFeatureCalculator


# ============================================================================
# METRICS (from your requirements)
# ============================================================================

def logloss(p: np.ndarray, y: np.ndarray, eps: float = 1e-7) -> np.ndarray:
    """Per-sample log loss."""
    p = np.clip(p, eps, 1 - eps)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def brier(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Per-sample Brier score."""
    return (p - y) ** 2


def ece(p: np.ndarray, y: np.ndarray, n_bins: int = 15) -> float:
    """Expected Calibration Error."""
    p = np.asarray(p)
    y = np.asarray(y)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.digitize(p, bins) - 1
    idx = np.clip(idx, 0, n_bins - 1)

    ece_val = 0.0
    n = len(p)
    for b in range(n_bins):
        mask = idx == b
        if not np.any(mask):
            continue
        conf = p[mask].mean()
        acc = y[mask].mean()
        ece_val += (mask.sum() / n) * abs(acc - conf)
    return ece_val


# ============================================================================
# CHECKPOINT SELECTION
# ============================================================================

def get_checkpoint_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Select checkpoint timepoints for evaluation.
    
    Checkpoints (Protocol 2):
    - Start of innings (over 0-1)
    - After powerplay (over 6)
    - 10 overs
    - 15 overs
    - 18 overs
    """
    # Infer over from overs_remaining
    if 'overs_remaining' in df.columns:
        df = df.copy()
        df['over'] = 20 - df['overs_remaining'].round().astype(int)
    elif 'over' not in df.columns:
        raise ValueError("Need 'over' or 'overs_remaining' column")
    
    # Select checkpoints
    checkpoint_overs = [1, 6, 10, 15, 18]
    mask = df['over'].isin(checkpoint_overs)
    
    return df[mask].copy()


# ============================================================================
# MC EVALUATION
# ============================================================================

def run_mc_for_state(
    predictor: Predictor,
    row: pd.Series,
    n_simulations: int = 500,
    horizon: int = 6,
    use_ml_evaluator: bool = False,  # NEW: Whether to use ML model for terminal evaluation
) -> float:
    """
    Run Monte Carlo simulation for a single state and return mean win prob.
    
    Args:
        predictor: Loaded predictor (used if use_ml_evaluator=True)
        row: DataFrame row with match state info
        n_simulations: Number of MC paths
        horizon: Balls to simulate forward
        use_ml_evaluator: If True, use ML model for terminal states (slower, but
                         NOTE: this uses default features so not comparable to
                         direct ML model with full features). If False, use
                         resource_win_prob (fast, fair comparison).
        
    Returns:
        MC estimated win probability
    """
    # Build simulation state from row
    innings = int(row.get('innings', 2))
    
    # Get over/ball from features
    if 'overs_remaining' in row:
        overs_bowled = 20 - row['overs_remaining']
        over = int(overs_bowled)
        ball = int((overs_bowled - over) * 6) + 1
    else:
        over = int(row.get('over', 10))
        ball = int(row.get('ball', 1))
    
    balls_remaining = (20 - over) * 6 - ball + 1
    balls_remaining = max(1, min(120, balls_remaining))  # Clamp to valid range
    
    # Get overs info for deriving score/target
    overs_remaining = row.get('overs_remaining', balls_remaining / 6)
    overs_bowled = 20 - overs_remaining
    
    # Get score - derive from CRR if not directly available
    if 'current_score' in row:
        score = int(row['current_score'])
    elif 'score' in row:
        score = int(row['score'])
    elif 'total_score' in row:
        score = int(row['total_score'])
    elif 'current_run_rate' in row and overs_bowled > 0:
        # Derive: score = CRR * overs_bowled
        score = int(row['current_run_rate'] * overs_bowled)
    else:
        score = 100  # Fallback
    
    wickets = int(row.get('wickets_lost', row.get('wickets', row.get('total_wickets', 3))))
    
    # For innings 2, need target - derive from RRR if not directly available
    target = None
    if innings == 2:
        if 'target_runs' in row:
            target = int(row['target_runs'])
        elif 'target' in row:
            target = int(row['target'])
        elif 'target_score' in row:
            target = int(row['target_score'])
        elif 'required_run_rate' in row and overs_remaining > 0:
            # Derive: runs_needed = RRR * overs_remaining, target = score + runs_needed
            runs_needed = row['required_run_rate'] * overs_remaining
            target = int(score + runs_needed)
        else:
            target = 160  # Fallback
    
    # Build state - use dummy team names (simulation doesn't use them for batch prediction)
    state = SimMatchState(
        innings=innings,
        score=score,
        wickets_lost=wickets,
        balls_remaining=balls_remaining,
        target_runs=target,
        league='bbl',
        batting_team='Team A',  # Dummy - batch prediction doesn't use team names
        bowling_team='Team B',  # Dummy - batch prediction doesn't use team names
    )
    
    # Run MC with the appropriate evaluator
    # If use_ml_evaluator=False, pass predictor=None to use resource_win_prob
    result = simulate(
        state=state,
        horizon=horizon,
        n_simulations=n_simulations,
        predictor=predictor if use_ml_evaluator else None,
        apply_temp=False,  # Predictor handles calibration
    )
    
    return result.mean_prob


def evaluate_sample(
    df: pd.DataFrame,
    predictor: Predictor,
    calculator: ResourceFeatureCalculator,
    sample_size: int = 500,
    n_mc_sims: int = 500,
    mc_horizon: int = 6,
    use_ml_evaluator: bool = False,  # NEW: Whether to use ML model for MC terminal evaluation
) -> Dict[str, Dict[str, float]]:
    """
    Evaluate a sample of states with ML model, MC, and resource baseline.
    
    Args:
        df: DataFrame with training data (must have is_winner column)
        predictor: Loaded predictor
        calculator: Resource calculator for baseline
        sample_size: Number of states to evaluate
        n_mc_sims: MC simulations per state
        mc_horizon: Balls to simulate forward
        use_ml_evaluator: If True, MC uses ML model for terminal states.
                         If False (default), MC uses resource_win_prob.
                         NOTE: use_ml_evaluator=True is NOT a fair comparison
                         to ML Model because MC generates features with defaults.
        
    Returns:
        Dict with metrics for each method
    """
    # Get checkpoints
    checkpoints = get_checkpoint_rows(df)
    print(f"Total checkpoint rows: {len(checkpoints):,}")
    
    # Sample for speed
    if len(checkpoints) > sample_size:
        sample = checkpoints.sample(n=sample_size, random_state=42)
    else:
        sample = checkpoints
    
    print(f"Evaluating {len(sample):,} sampled states...")
    
    # Storage
    y_true = sample['is_winner'].values
    p_model = np.zeros(len(sample))
    p_mc = np.zeros(len(sample))
    p_resource = np.zeros(len(sample))
    
    # Get model's expected features
    expected_features = None
    if hasattr(predictor.model, 'selected_features_'):
        expected_features = predictor.model.selected_features_
    elif hasattr(predictor.model, 'feature_names_in_'):
        expected_features = list(predictor.model.feature_names_in_)
    
    print(f"Model expects {len(expected_features) if expected_features else 0} features")
    
    # Verify features exist in sample
    if expected_features:
        missing = [f for f in expected_features if f not in sample.columns]
        if missing:
            print(f"  ⚠ Missing features in data: {missing[:5]}...")
        else:
            print(f"  ✓ All features present in data")
    
    start_time = time.time()
    
    # Vectorized ML Model prediction for all samples at once
    if expected_features:
        X_all = sample[expected_features].fillna(0)  # Keep as DataFrame for XGBLogRegEnsemble
        try:
            p_model = predictor.model.predict_proba(X_all)[:, 1]
            print(f"  ✓ Batch model prediction successful")
        except Exception as e:
            print(f"  ✗ Batch model prediction failed: {e}")
            p_model = np.full(len(sample), 0.5)
    else:
        p_model = np.full(len(sample), 0.5)
    
    # Resource baseline (vectorized)
    if 'resource_win_prob' in sample.columns:
        p_resource = sample['resource_win_prob'].fillna(0.5).values
    else:
        p_resource = np.full(len(sample), 0.5)
    
    # MC predictions (loop - each state runs N simulations)
    p_mc = np.zeros(len(sample))
    
    for i, (idx, row) in enumerate(sample.iterrows()):
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            eta = (len(sample) - i - 1) / rate
            print(f"  [{i+1}/{len(sample)}] {rate:.1f} states/sec, ETA: {eta:.0f}s")
        
        # MC prediction (with ML evaluator)
        try:
            p_mc[i] = run_mc_for_state(
                predictor=predictor,
                row=row,
                n_simulations=n_mc_sims,
                horizon=mc_horizon,
                use_ml_evaluator=use_ml_evaluator,  # Pass through
            )
        except Exception as e:
            # Fallback to model prediction
            p_mc[i] = p_model[i]
    
    elapsed = time.time() - start_time
    print(f"\nEvaluation complete in {elapsed:.1f}s ({len(sample)/elapsed:.1f} states/sec)")
    
    # Compute metrics
    results = {}
    
    for name, probs in [('ML Model', p_model), ('Monte Carlo', p_mc), ('Resource', p_resource)]:
        ll = logloss(probs, y_true).mean()
        br = brier(probs, y_true).mean()
        ec = ece(probs, y_true)
        
        results[name] = {
            'logloss': ll,
            'brier': br,
            'ece': ec,
            'mean_prob': probs.mean(),
            'std_prob': probs.std(),
        }
    
    return results, {
        'y_true': y_true,
        'p_model': p_model,
        'p_mc': p_mc,
        'p_resource': p_resource,
    }


def print_results(results: Dict[str, Dict[str, float]]):
    """Pretty print evaluation results."""
    print("\n" + "=" * 70)
    print("MONTE CARLO vs ML MODEL vs RESOURCE BASELINE")
    print("=" * 70)
    
    print(f"\n{'Method':<15} | {'LogLoss':<10} | {'Brier':<10} | {'ECE':<10} | {'Mean P':<10}")
    print("-" * 70)
    
    for name, metrics in results.items():
        print(f"{name:<15} | {metrics['logloss']:.4f}     | {metrics['brier']:.4f}     | {metrics['ece']:.4f}     | {metrics['mean_prob']:.3f}")
    
    print("-" * 70)
    
    # Relative improvements
    if 'ML Model' in results and 'Monte Carlo' in results:
        ml_ll = results['ML Model']['logloss']
        mc_ll = results['Monte Carlo']['logloss']
        diff = mc_ll - ml_ll
        pct = (diff / ml_ll) * 100
        
        print(f"\nMC vs ML Model:")
        print(f"  LogLoss diff: {diff:+.4f} ({pct:+.1f}%)")
        print(f"  {'✓ MC is better' if diff < 0 else '✗ ML Model is better'}")
    
    if 'Resource' in results and 'ML Model' in results:
        res_ll = results['Resource']['logloss']
        ml_ll = results['ML Model']['logloss']
        diff = ml_ll - res_ll
        pct = (diff / res_ll) * 100
        
        print(f"\nML Model vs Resource baseline:")
        print(f"  LogLoss diff: {diff:+.4f} ({pct:+.1f}%)")
        print(f"  {'✓ ML is better' if diff < 0 else '✗ Resource is better'}")


def analyze_by_phase(
    probs_dict: Dict[str, np.ndarray],
    df_sample: pd.DataFrame,
):
    """Analyze metrics by game phase."""
    y_true = probs_dict['y_true']
    
    # Infer phase from overs
    if 'overs_remaining' in df_sample.columns:
        over = 20 - df_sample['overs_remaining'].round().astype(int)
    else:
        over = df_sample['over']
    
    # Get innings column
    innings = df_sample['innings'].values if 'innings' in df_sample.columns else np.ones(len(df_sample))
    
    phases = {
        'Powerplay (1-6)': (over >= 1) & (over <= 6),
        'Middle (7-15)': (over >= 7) & (over <= 15),
        'Death (16-20)': (over >= 16),
    }
    
    print("\n" + "=" * 70)
    print("PHASE-WISE ANALYSIS")
    print("=" * 70)
    
    for phase_name, mask in phases.items():
        mask_arr = mask.values if hasattr(mask, 'values') else mask
        n_samples = mask_arr.sum()
        
        if n_samples < 10:
            continue
        
        print(f"\n{phase_name} (n={n_samples}):")
        print(f"  {'Method':<15} | {'LogLoss':<10} | {'Brier':<10} | {'ECE':<10}")
        print(f"  " + "-" * 55)
        
        for name, key in [('ML Model', 'p_model'), ('Monte Carlo', 'p_mc'), ('Resource', 'p_resource')]:
            p = probs_dict[key][mask_arr]
            y = y_true[mask_arr]
            
            ll = logloss(p, y).mean()
            br = brier(p, y).mean()
            ec = ece(p, y)
            
            print(f"  {name:<15} | {ll:.4f}     | {br:.4f}     | {ec:.4f}")
    
    # Innings × Phase analysis
    print("\n" + "=" * 70)
    print("INNINGS × PHASE ANALYSIS")
    print("=" * 70)
    
    innings_phases = {
        'inn1_powerplay': (innings == 1) & (over >= 1) & (over <= 6),
        'inn1_middle': (innings == 1) & (over >= 7) & (over <= 15),
        'inn1_death': (innings == 1) & (over >= 16),
        'inn2_powerplay': (innings == 2) & (over >= 1) & (over <= 6),
        'inn2_middle': (innings == 2) & (over >= 7) & (over <= 15),
        'inn2_death': (innings == 2) & (over >= 16),
    }
    
    for phase_name, mask in innings_phases.items():
        mask_arr = mask.values if hasattr(mask, 'values') else mask
        n_samples = mask_arr.sum()
        
        if n_samples < 5:
            print(f"\n{phase_name}: (n={n_samples}) - skipped (too few samples)")
            continue
        
        print(f"\n{phase_name} (n={n_samples}):")
        print(f"  {'Method':<15} | {'LogLoss':<10} | {'Brier':<10} | {'ECE':<10}")
        print(f"  " + "-" * 55)
        
        for name, key in [('ML Model', 'p_model'), ('Monte Carlo', 'p_mc'), ('Resource', 'p_resource')]:
            p = probs_dict[key][mask_arr]
            y = y_true[mask_arr]
            
            ll = logloss(p, y).mean()
            br = brier(p, y).mean()
            ec = ece(p, y)
            
            print(f"  {name:<15} | {ll:.4f}     | {br:.4f}     | {ec:.4f}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze MC vs ML Model for BBL")
    parser.add_argument('--model-dir', default='models/t20_male_v2', help='Model directory')
    parser.add_argument('--feature-store', default='data/t20_male_feature_store_v2', help='Feature store')
    parser.add_argument('--data', default='data/bbl_features_v4/training.parquet', help='Training data')
    parser.add_argument('--sample-size', type=int, default=200, help='Number of states to evaluate')
    parser.add_argument('--mc-sims', type=int, default=500, help='MC simulations per state')
    parser.add_argument('--mc-horizon', type=int, default=6, help='Balls to simulate forward')
    parser.add_argument('--league', default='bbl', help='League for calibration')
    parser.add_argument('--use-ml-evaluator', action='store_true', 
                       help='Use ML model for MC terminal evaluation (not recommended - unfair comparison)')
    args = parser.parse_args()
    
    print("=" * 70)
    print("BBL MONTE CARLO vs ML MODEL ANALYSIS")
    print("=" * 70)
    print(f"Model: {args.model_dir}")
    print(f"Data: {args.data}")
    print(f"Sample size: {args.sample_size}")
    print(f"MC simulations: {args.mc_sims}")
    print(f"MC horizon: {args.mc_horizon} balls")
    print(f"MC evaluator: {'ML Model (unfair)' if args.use_ml_evaluator else 'Resource (fair)'}")
    print("=" * 70)
    
    # Load data
    print("\nLoading data...")
    df = pd.read_parquet(args.data)
    print(f"Loaded {len(df):,} rows")
    
    # Load predictor
    print("\nLoading predictor...")
    predictor = Predictor.load(args.model_dir, args.feature_store, league=args.league)
    print("Predictor loaded")
    
    # Create calculator
    calculator = ResourceFeatureCalculator()
    
    # Run evaluation
    print("\nRunning evaluation...")
    results, probs_dict = evaluate_sample(
        df=df,
        predictor=predictor,
        calculator=calculator,
        sample_size=args.sample_size,
        n_mc_sims=args.mc_sims,
        mc_horizon=args.mc_horizon,
        use_ml_evaluator=args.use_ml_evaluator,
    )
    
    # Print results
    print_results(results)
    
    # Phase analysis
    checkpoints = get_checkpoint_rows(df)
    if len(checkpoints) > args.sample_size:
        sample = checkpoints.sample(n=args.sample_size, random_state=42)
    else:
        sample = checkpoints
    
    analyze_by_phase(probs_dict, sample)
    
    print("\n" + "=" * 70)
    print("INTERPRETATION")
    print("=" * 70)
    print("""
If MC LogLoss < ML Model LogLoss:
  → Your simulator+evaluator is IMPROVING predictiveness
  → MC is capturing game dynamics that static model misses

If MC ECE > ML Model ECE:
  → MC probabilities are miscalibrated
  → Consider temperature-calibrating the MC output

If MC ≈ ML Model:
  → Simulation adds uncertainty estimation (σ) without hurting accuracy
  → Good for betting confidence intervals
""")


if __name__ == "__main__":
    main()
