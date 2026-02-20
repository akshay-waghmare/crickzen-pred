#!/usr/bin/env python3
"""
BBL Phase-Specific ECE-Optimized Calibrators

Train phase-specific isotonic calibrators on the BEST source for each phase
to achieve near-zero ECE across all innings/phase combinations.

Based on BBL v10 analysis:
- Inn1 (all phases): Raw model is already best for ECE
- Inn2 Powerplay/Death: Calibrated is best
- Inn2 Middle: Resource is best

Strategy: Train isotonic on the best source for each phase.
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.isotonic import IsotonicRegression
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


def train_bbl_phase_calibrators():
    print("=" * 70)
    print("TRAINING BBL PHASE-SPECIFIC ECE-OPTIMIZED CALIBRATORS")
    print("=" * 70)
    
    # Load data and models
    df = pd.read_parquet('data/bbl_features_v2/training.parquet')
    model = joblib.load('models/bbl_v10/champion_model.joblib')
    existing_calibrator = joblib.load('models/bbl_v10/isotonic_calibrator.pkl')
    
    print(f"\nLoaded {len(df):,} training samples")
    
    # Prepare features and get probabilities
    exclude_cols = ['is_winner', 'innings']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols]
    y = df['is_winner'].values
    
    raw_prob = model.predict_proba(X)[:, 1]
    resource_prob = df['resource_win_prob'].values
    
    # Apply existing innings-specific calibration
    inn1_mask = df['innings'] == 1
    inn2_mask = df['innings'] == 2
    calibrated_prob = np.zeros_like(raw_prob)
    calibrated_prob[inn1_mask] = existing_calibrator['calibrator_innings1'].predict(raw_prob[inn1_mask])
    calibrated_prob[inn2_mask] = existing_calibrator['calibrator_innings2'].predict(raw_prob[inn2_mask])
    
    # Calculate current over
    over = np.ceil(20 - df['overs_remaining']).astype(int) + 1
    
    # Phase definitions with best source
    # Based on our analysis: Inn1=Raw, Inn2 PP/Death=Cal, Inn2 Middle=Res
    phase_configs = [
        (1, 'powerplay', 1, 6, 'raw'),
        (1, 'middle', 7, 15, 'raw'),
        (1, 'death', 16, 20, 'raw'),
        (2, 'powerplay', 1, 6, 'cal'),
        (2, 'middle', 7, 15, 'res'),
        (2, 'death', 16, 20, 'cal'),
    ]
    
    phase_calibrators = {}
    results = []
    
    for innings, phase_name, start_over, end_over, best_source in phase_configs:
        mask = (df['innings'] == innings) & (over >= start_over) & (over <= end_over)
        n_samples = mask.sum()
        key = f'inn{innings}_{phase_name}'
        
        # Select the best input source
        if best_source == 'raw':
            input_prob = raw_prob[mask]
            source_name = 'Raw Model'
        elif best_source == 'cal':
            input_prob = calibrated_prob[mask]
            source_name = 'Calibrated'
        else:  # res
            input_prob = resource_prob[mask]
            source_name = 'Resource'
        
        # Train isotonic calibrator
        iso = IsotonicRegression(out_of_bounds='clip')
        iso.fit(input_prob, y[mask])
        
        # Store calibrator with its source info
        phase_calibrators[key] = {
            'calibrator': iso,
            'source': best_source
        }
        
        # Calculate ECE after calibration
        cal_output = iso.predict(input_prob)
        ece_before = expected_calibration_error(y[mask], input_prob)
        ece_after = expected_calibration_error(y[mask], cal_output)
        brier_before = brier_score(y[mask], input_prob)
        brier_after = brier_score(y[mask], cal_output)
        
        results.append({
            'phase': key,
            'samples': n_samples,
            'source': source_name,
            'ece_before': ece_before,
            'ece_after': ece_after,
            'brier_before': brier_before,
            'brier_after': brier_after
        })
        
        print(f"\n{key} ({n_samples:,} samples) - Source: {source_name}")
        print(f"  ECE:   Before={ece_before:.4f} --> After={ece_after:.4f}")
        print(f"  Brier: Before={brier_before:.4f} --> After={brier_after:.4f}")
    
    # Save calibrators
    output_path = Path('models/bbl_v10/phase_calibrators.pkl')
    joblib.dump(phase_calibrators, output_path)
    
    print(f"\n{'='*70}")
    print(f"Saved {len(phase_calibrators)} phase calibrators to {output_path}")
    print(f"{'='*70}")
    
    # Summary table
    print("\n\nSUMMARY TABLE")
    print("-" * 80)
    print(f"{'Phase':<20} {'Samples':>8} {'Source':<12} {'ECE Before':>12} {'ECE After':>12}")
    print("-" * 80)
    for r in results:
        print(f"{r['phase']:<20} {r['samples']:>8,} {r['source']:<12} {r['ece_before']:>12.4f} {r['ece_after']:>12.4f}")
    print("-" * 80)
    
    return phase_calibrators


def demo_inference():
    """Demonstrate how to use the phase calibrators for inference."""
    print("\n\nDEMO: Using BBL Phase Calibrators for Inference")
    print("=" * 60)
    
    # Load models
    model = joblib.load('models/bbl_v10/champion_model.joblib')
    existing_calibrator = joblib.load('models/bbl_v10/isotonic_calibrator.pkl')
    phase_calibrators = joblib.load('models/bbl_v10/phase_calibrators.pkl')
    
    print(f"Loaded phase calibrators: {list(phase_calibrators.keys())}")
    print("\nEach calibrator entry contains:")
    print("  - 'calibrator': IsotonicRegression model")
    print("  - 'source': 'raw', 'cal', or 'res'")
    
    print("\n" + "-"*60)
    print("USAGE PATTERN:")
    print("-"*60)
    print("""
def get_bbl_ece_optimized_prob(innings, over, raw_prob, calibrated_prob, resource_prob):
    # Determine phase
    if over <= 6:
        phase = 'powerplay'
    elif over <= 15:
        phase = 'middle'
    else:
        phase = 'death'
    
    key = f'inn{innings}_{phase}'
    cal_info = phase_calibrators[key]
    
    # Select correct input based on source
    if cal_info['source'] == 'raw':
        input_prob = raw_prob
    elif cal_info['source'] == 'cal':
        input_prob = calibrated_prob
    else:  # 'res'
        input_prob = resource_prob
    
    # Apply phase calibrator
    return cal_info['calibrator'].predict([[input_prob]])[0]
""")


if __name__ == '__main__':
    calibrators = train_bbl_phase_calibrators()
    demo_inference()
