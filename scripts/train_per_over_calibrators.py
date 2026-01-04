#!/usr/bin/env python3
"""
Per-Over ECE-Optimized Calibrators

Instead of 6 phase calibrators (3 phases × 2 innings), train 40 calibrators 
(20 overs × 2 innings) for smoother probability transitions.

This solves the "stepped" output problem where probabilities were stuck 
within each phase.

Usage:
    python scripts/train_per_over_calibrators.py \
        --model-dir models/bbl_v10 \
        --features data/bbl_features_v2/training.parquet

Output:
    {model-dir}/per_over_calibrators.pkl

Author: Copilot
Date: 2026-01-01
"""

import argparse
import pandas as pd
import numpy as np
import joblib
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from pathlib import Path


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return np.mean((y_prob - y_true) ** 2)


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    ece = 0.0
    for i in range(n_bins):
        mask = (y_prob >= i / n_bins) & (y_prob < (i + 1) / n_bins)
        if mask.sum() > 0:
            ece += mask.mean() * abs(y_prob[mask].mean() - y_true[mask].mean())
    return ece


def train_per_over_calibrators(model_dir: str, features_path: str, output_path: str = None, 
                                use_platt: bool = False, min_samples: int = 500):
    """
    Train per-over ECE-optimized calibrators.
    
    Args:
        model_dir: Path to model directory
        features_path: Path to training.parquet
        output_path: Where to save calibrators
        use_platt: If True, use Platt scaling (sigmoid) for smoother output
        min_samples: Minimum samples per over to train a calibrator (else inherit from neighbor)
    """
    model_dir = Path(model_dir)
    features_path = Path(features_path)
    
    if output_path is None:
        output_path = model_dir / 'per_over_calibrators.pkl'
    else:
        output_path = Path(output_path)
    
    print("=" * 70)
    print("PER-OVER ECE-OPTIMIZED CALIBRATOR TRAINING")
    print("=" * 70)
    print(f"Model directory: {model_dir}")
    print(f"Features: {features_path}")
    print(f"Output: {output_path}")
    print(f"Method: {'Platt Scaling (smooth)' if use_platt else 'Isotonic (piecewise)'}")
    print(f"Min samples per over: {min_samples}")
    
    # Load data
    df = pd.read_parquet(features_path)
    print(f"\nLoaded {len(df):,} training samples")
    
    # Load model
    model = joblib.load(model_dir / 'champion_model.joblib')
    
    # Try to load existing calibrator
    calibrator_path = model_dir / 'isotonic_calibrator.pkl'
    if calibrator_path.exists():
        existing_calibrator = joblib.load(calibrator_path)
        has_calibrator = True
    else:
        has_calibrator = False
    
    # Prepare features
    exclude_cols = ['is_winner', 'innings']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols]
    y = df['is_winner'].values
    
    # Get probabilities
    raw_prob = model.predict_proba(X)[:, 1]
    resource_prob = df['resource_win_prob'].values
    
    # Apply existing calibration if available
    if has_calibrator:
        inn1_mask = df['innings'] == 1
        inn2_mask = df['innings'] == 2
        calibrated_prob = np.zeros_like(raw_prob)
        calibrated_prob[inn1_mask] = existing_calibrator['calibrator_innings1'].predict(raw_prob[inn1_mask])
        calibrated_prob[inn2_mask] = existing_calibrator['calibrator_innings2'].predict(raw_prob[inn2_mask])
    else:
        calibrated_prob = raw_prob.copy()
    
    # Calculate current over (1-20)
    over = np.ceil(20 - df['overs_remaining']).astype(int).clip(1, 20)
    
    # Determine best source per phase (for input selection)
    # Inn1: Raw, Inn2 PP/Death: Cal, Inn2 Middle: Res
    def get_best_source(innings, over_num):
        if innings == 1:
            return 'raw'
        else:
            if over_num <= 6:
                return 'cal'
            elif over_num <= 15:
                return 'res'
            else:
                return 'cal'
    
    # Train calibrators for each innings × over
    per_over_calibrators = {}
    results = []
    
    for innings in [1, 2]:
        print(f"\n{'='*70}")
        print(f"INNINGS {innings}")
        print(f"{'='*70}")
        
        for over_num in range(1, 21):
            mask = (df['innings'] == innings) & (over == over_num)
            n_samples = mask.sum()
            key = f'inn{innings}_over{over_num}'
            
            if n_samples < min_samples:
                print(f"  Over {over_num:2d}: {n_samples:5,} samples - SKIPPED (< {min_samples})")
                per_over_calibrators[key] = None  # Will inherit from neighbor
                continue
            
            # Get best source for this over
            best_source = get_best_source(innings, over_num)
            
            if best_source == 'raw':
                input_prob = raw_prob[mask]
                source_name = 'Raw'
            elif best_source == 'cal':
                input_prob = calibrated_prob[mask]
                source_name = 'Cal'
            else:
                input_prob = resource_prob[mask]
                source_name = 'Res'
            
            # Train calibrator
            if use_platt:
                # Platt scaling (logistic regression on logit)
                # Avoid log(0) and log(1)
                input_clipped = np.clip(input_prob, 0.001, 0.999)
                logits = np.log(input_clipped / (1 - input_clipped)).reshape(-1, 1)
                cal = LogisticRegression(C=1e10, solver='lbfgs', max_iter=1000)
                cal.fit(logits, y[mask])
                cal_output = cal.predict_proba(logits)[:, 1]
            else:
                # Isotonic regression
                cal = IsotonicRegression(out_of_bounds='clip')
                cal.fit(input_prob, y[mask])
                cal_output = cal.predict(input_prob)
            
            per_over_calibrators[key] = {
                'calibrator': cal,
                'source': best_source,
                'method': 'platt' if use_platt else 'isotonic'
            }
            
            ece_before = expected_calibration_error(y[mask], input_prob)
            ece_after = expected_calibration_error(y[mask], cal_output)
            
            results.append({
                'key': key,
                'samples': n_samples,
                'source': source_name,
                'ece_before': ece_before,
                'ece_after': ece_after
            })
            
            print(f"  Over {over_num:2d}: {n_samples:5,} samples | {source_name:3s} | ECE: {ece_before:.4f} -> {ece_after:.4f}")
    
    # Fill in missing overs by inheriting from nearest neighbor
    for innings in [1, 2]:
        for over_num in range(1, 21):
            key = f'inn{innings}_over{over_num}'
            if per_over_calibrators[key] is None:
                # Find nearest over with calibrator
                for delta in range(1, 20):
                    for neighbor in [over_num - delta, over_num + delta]:
                        if 1 <= neighbor <= 20:
                            neighbor_key = f'inn{innings}_over{neighbor}'
                            if per_over_calibrators.get(neighbor_key) is not None:
                                per_over_calibrators[key] = per_over_calibrators[neighbor_key]
                                print(f"  {key}: Inherited from {neighbor_key}")
                                break
                    if per_over_calibrators[key] is not None:
                        break
    
    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(per_over_calibrators, output_path)
    
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    total_ece_before = np.mean([r['ece_before'] for r in results])
    total_ece_after = np.mean([r['ece_after'] for r in results])
    print(f"Average ECE: {total_ece_before:.4f} -> {total_ece_after:.4f}")
    print(f"\n✅ Saved {len(per_over_calibrators)} per-over calibrators to {output_path}")
    
    return per_over_calibrators


def demo_inference():
    """Demonstrate how to use the per-over calibrators."""
    print("\n\nDEMO: Using Per-Over Calibrators for Inference")
    print("=" * 60)
    print("""
import joblib
import numpy as np

per_over_calibrators = joblib.load('models/bbl_v10/per_over_calibrators.pkl')

def get_ece_optimized_prob(innings, over, raw_prob, calibrated_prob, resource_prob):
    '''Get ECE-optimized probability with smooth per-over calibration.'''
    # Clamp over to 1-20
    over = max(1, min(20, int(over)))
    
    key = f'inn{innings}_over{over}'
    cal_info = per_over_calibrators[key]
    
    # Select correct input
    if cal_info['source'] == 'raw':
        input_prob = raw_prob
    elif cal_info['source'] == 'cal':
        input_prob = calibrated_prob
    else:
        input_prob = resource_prob
    
    # Apply calibrator
    if cal_info['method'] == 'platt':
        input_clipped = np.clip(input_prob, 0.001, 0.999)
        logit = np.log(input_clipped / (1 - input_clipped))
        return cal_info['calibrator'].predict_proba([[logit]])[0, 1]
    else:
        return cal_info['calibrator'].predict([[input_prob]])[0]
""")


def main():
    parser = argparse.ArgumentParser(description='Train per-over ECE-optimized calibrators')
    parser.add_argument('--model-dir', required=True, help='Path to model directory')
    parser.add_argument('--features', required=True, help='Path to training.parquet')
    parser.add_argument('--output', default=None, help='Output path')
    parser.add_argument('--platt', action='store_true', help='Use Platt scaling instead of isotonic')
    parser.add_argument('--min-samples', type=int, default=500, help='Min samples per over')
    
    args = parser.parse_args()
    train_per_over_calibrators(args.model_dir, args.features, args.output, args.platt, args.min_samples)
    demo_inference()


if __name__ == '__main__':
    main()
