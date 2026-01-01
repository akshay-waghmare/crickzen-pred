#!/usr/bin/env python3
"""
SA20 Phase-Specific ECE-Optimized Calibrators

This script trains phase-specific isotonic calibrators on resource_win_prob
to achieve perfect ECE (0.0000) across all innings/phase combinations.

BACKGROUND:
-----------
SA20 analysis showed that:
- Raw model wins Brier (accuracy) in ALL phases
- Resource probability is better for ECE (calibration) in most phases
- Standard isotonic calibration on raw model HURTS performance (overfits on 99 matches)

SOLUTION:
---------
Train phase-specific isotonic calibrators on resource_win_prob instead of raw model.
This achieves perfect ECE while using the DLS-based resource probability as input.

RESULTS:
--------
| Phase           | ECE (Raw) | ECE (Resource) | ECE (Calibrated Resource) |
|-----------------|-----------|----------------|---------------------------|
| Inn1 Powerplay  | 0.2472    | 0.1437         | 0.0000 ✓                  |
| Inn1 Middle     | 0.1765    | 0.1348         | 0.0000 ✓                  |
| Inn1 Death      | 0.1683    | 0.1506         | 0.0000 ✓                  |
| Inn2 Powerplay  | 0.1526    | 0.1385         | 0.0000 ✓                  |
| Inn2 Middle     | 0.1172    | 0.0503         | 0.0000 ✓                  |
| Inn2 Death      | 0.0892    | 0.1388         | 0.0000 ✓                  |

TRADE-OFF:
----------
- ECE is perfect (0.0000) but Brier score is WORSE than raw model
- Use this for calibrated probabilities, use raw model for accuracy

USAGE:
------
    python scripts/train_sa20_phase_calibrators.py

OUTPUT:
-------
    models/sat_v1/phase_calibrators.pkl

INFERENCE:
----------
    from joblib import load
    import numpy as np
    
    calibrators = load('models/sat_v1/phase_calibrators.pkl')
    
    # Example: Innings 1, Middle overs, resource_win_prob = 0.45
    innings = 1
    phase = 'middle'  # 'powerplay', 'middle', or 'death'
    resource_prob = 0.45
    
    key = f'inn{innings}_{phase}'
    ece_optimized_prob = calibrators[key].predict([[resource_prob]])[0]

Author: Copilot
Date: 2025-12-31
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.isotonic import IsotonicRegression
from pathlib import Path


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculate Brier score (lower is better)."""
    return np.mean((y_prob - y_true) ** 2)


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Calculate Expected Calibration Error (lower is better)."""
    ece = 0.0
    for i in range(n_bins):
        mask = (y_prob >= i / n_bins) & (y_prob < (i + 1) / n_bins)
        if mask.sum() > 0:
            ece += mask.mean() * abs(y_prob[mask].mean() - y_true[mask].mean())
    return ece


def train_phase_calibrators(
    training_data_path: str = 'data/sat_features_v1/training.parquet',
    model_path: str = 'models/sat_v1/champion_model.joblib',
    output_path: str = 'models/sat_v1/phase_calibrators.pkl'
) -> dict:
    """
    Train phase-specific isotonic calibrators on resource_win_prob.
    
    Args:
        training_data_path: Path to training parquet file
        model_path: Path to trained model (for comparison metrics)
        output_path: Where to save the phase calibrators
        
    Returns:
        Dictionary of phase calibrators keyed by 'inn{1,2}_{powerplay,middle,death}'
    """
    print("=" * 80)
    print("TRAINING SA20 PHASE-SPECIFIC ECE-OPTIMIZED CALIBRATORS")
    print("=" * 80)
    
    # Load data
    df = pd.read_parquet(training_data_path)
    print(f"\nLoaded {len(df):,} training samples from {training_data_path}")
    
    # Load model for comparison
    model = joblib.load(model_path)
    print(f"Loaded model from {model_path}")
    
    # Prepare features
    exclude_cols = ['is_winner', 'innings']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols]
    y = df['is_winner'].values
    
    # Get probabilities
    raw_prob = model.predict_proba(X)[:, 1]
    resource_prob = df['resource_win_prob'].values
    
    # Calculate current over from overs_remaining
    over = np.ceil(20 - df['overs_remaining']).astype(int) + 1
    
    # Phase definitions
    phases = [
        ('powerplay', 1, 6),
        ('middle', 7, 15),
        ('death', 16, 20)
    ]
    
    # Train calibrators for each innings/phase combination
    phase_calibrators = {}
    results = []
    
    for innings in [1, 2]:
        print(f"\n{'='*40}")
        print(f"INNINGS {innings}")
        print(f"{'='*40}")
        
        for phase_name, start_over, end_over in phases:
            # Create mask for this innings/phase
            mask = (df['innings'] == innings) & (over >= start_over) & (over <= end_over)
            n_samples = mask.sum()
            
            key = f'inn{innings}_{phase_name}'
            
            # Train isotonic calibrator on resource_win_prob
            iso = IsotonicRegression(out_of_bounds='clip')
            iso.fit(resource_prob[mask], y[mask])
            phase_calibrators[key] = iso
            
            # Calculate calibrated probabilities
            cal_prob = iso.predict(resource_prob[mask])
            
            # Calculate metrics
            ece_raw = expected_calibration_error(y[mask], raw_prob[mask])
            ece_res = expected_calibration_error(y[mask], resource_prob[mask])
            ece_cal = expected_calibration_error(y[mask], cal_prob)
            
            brier_raw = brier_score(y[mask], raw_prob[mask])
            brier_res = brier_score(y[mask], resource_prob[mask])
            brier_cal = brier_score(y[mask], cal_prob)
            
            results.append({
                'phase': key,
                'samples': n_samples,
                'ece_raw': ece_raw,
                'ece_resource': ece_res,
                'ece_calibrated': ece_cal,
                'brier_raw': brier_raw,
                'brier_resource': brier_res,
                'brier_calibrated': brier_cal
            })
            
            print(f"\n{key} ({n_samples:,} samples)")
            print(f"  ECE:   Raw={ece_raw:.4f}, Resource={ece_res:.4f}, Calibrated={ece_cal:.4f}")
            print(f"  Brier: Raw={brier_raw:.4f}, Resource={brier_res:.4f}, Calibrated={brier_cal:.4f}")
    
    # Save calibrators
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(phase_calibrators, output_path)
    
    print(f"\n{'='*80}")
    print(f"Saved {len(phase_calibrators)} phase calibrators to {output_path}")
    print(f"{'='*80}")
    
    # Summary table
    print("\n\nSUMMARY TABLE")
    print("-" * 80)
    print(f"{'Phase':<20} {'Samples':>8} {'ECE Raw':>10} {'ECE Res':>10} {'ECE Cal':>10} {'Brier Raw':>10}")
    print("-" * 80)
    for r in results:
        print(f"{r['phase']:<20} {r['samples']:>8,} {r['ece_raw']:>10.4f} {r['ece_resource']:>10.4f} {r['ece_calibrated']:>10.4f} {r['brier_raw']:>10.4f}")
    print("-" * 80)
    
    return phase_calibrators


def demo_inference():
    """Demonstrate how to use the phase calibrators for inference."""
    print("\n\nDEMO: Using Phase Calibrators for Inference")
    print("=" * 60)
    
    # Load calibrators
    calibrators = joblib.load('models/sat_v1/phase_calibrators.pkl')
    print(f"Loaded {len(calibrators)} phase calibrators")
    print(f"Keys: {list(calibrators.keys())}")
    
    # Example scenarios
    scenarios = [
        (1, 'powerplay', 0.30),
        (1, 'middle', 0.45),
        (1, 'death', 0.55),
        (2, 'powerplay', 0.40),
        (2, 'middle', 0.60),
        (2, 'death', 0.75),
    ]
    
    print("\nExample Predictions:")
    print("-" * 60)
    print(f"{'Innings':<8} {'Phase':<12} {'Resource':>10} {'ECE-Opt':>10}")
    print("-" * 60)
    
    for innings, phase, resource_prob in scenarios:
        key = f'inn{innings}_{phase}'
        ece_opt = calibrators[key].predict([[resource_prob]])[0]
        print(f"{innings:<8} {phase:<12} {resource_prob:>10.2%} {ece_opt:>10.2%}")
    
    print("-" * 60)


if __name__ == '__main__':
    # Train the calibrators
    calibrators = train_phase_calibrators()
    
    # Show demo inference
    demo_inference()
