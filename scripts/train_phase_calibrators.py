#!/usr/bin/env python3
"""
Generic Phase Calibrator Training Script

Train phase-specific isotonic calibrators for ECE optimization on ANY league model.
This script automatically determines the best probability source for each phase
and trains calibrators to achieve ECE ≈ 0.0000.

Usage:
    python scripts/train_phase_calibrators.py \
        --model-dir models/bbl_v10 \
        --features data/bbl_features_v2/training.parquet

    python scripts/train_phase_calibrators.py \
        --model-dir models/sat_v1 \
        --features data/sat_features_v1/training.parquet

Output:
    {model-dir}/phase_calibrators.pkl

Author: Copilot
Date: 2026-01-01
"""

import argparse
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


def analyze_best_sources(df, y, raw_prob, calibrated_prob, resource_prob, over):
    """Analyze which probability source is best for ECE in each phase."""
    phases = [
        (1, 'powerplay', 1, 6),
        (1, 'middle', 7, 15),
        (1, 'death', 16, 20),
        (2, 'powerplay', 1, 6),
        (2, 'middle', 7, 15),
        (2, 'death', 16, 20),
    ]
    
    results = []
    for innings, phase_name, start_over, end_over in phases:
        mask = (df['innings'] == innings) & (over >= start_over) & (over <= end_over)
        
        if mask.sum() == 0:
            continue
            
        yp = y[mask]
        
        ece_raw = expected_calibration_error(yp, raw_prob[mask])
        ece_cal = expected_calibration_error(yp, calibrated_prob[mask])
        ece_res = expected_calibration_error(yp, resource_prob[mask])
        
        # Determine best source
        if ece_raw <= ece_cal and ece_raw <= ece_res:
            best = 'raw'
            best_ece = ece_raw
        elif ece_cal <= ece_res:
            best = 'cal'
            best_ece = ece_cal
        else:
            best = 'res'
            best_ece = ece_res
        
        results.append({
            'innings': innings,
            'phase': phase_name,
            'start': start_over,
            'end': end_over,
            'key': f'inn{innings}_{phase_name}',
            'ece_raw': ece_raw,
            'ece_cal': ece_cal,
            'ece_res': ece_res,
            'best_source': best,
            'best_ece': best_ece,
            'samples': mask.sum()
        })
    
    return results


def train_phase_calibrators(model_dir: str, features_path: str, output_path: str = None):
    """
    Train phase-specific ECE-optimized calibrators.
    
    Args:
        model_dir: Path to model directory (contains champion_model.joblib, isotonic_calibrator.pkl)
        features_path: Path to training.parquet
        output_path: Where to save phase_calibrators.pkl (default: {model_dir}/phase_calibrators.pkl)
    """
    model_dir = Path(model_dir)
    features_path = Path(features_path)
    
    if output_path is None:
        output_path = model_dir / 'phase_calibrators.pkl'
    else:
        output_path = Path(output_path)
    
    print("=" * 70)
    print("PHASE-SPECIFIC ECE CALIBRATOR TRAINING")
    print("=" * 70)
    print(f"Model directory: {model_dir}")
    print(f"Features: {features_path}")
    print(f"Output: {output_path}")
    
    # Load data
    df = pd.read_parquet(features_path)
    print(f"\nLoaded {len(df):,} training samples")
    
    # Load model
    model = joblib.load(model_dir / 'champion_model.joblib')
    print(f"Loaded model from {model_dir / 'champion_model.joblib'}")
    
    # Try to load existing calibrator
    calibrator_path = model_dir / 'isotonic_calibrator.pkl'
    if calibrator_path.exists():
        existing_calibrator = joblib.load(calibrator_path)
        has_calibrator = True
        print(f"Loaded existing calibrator from {calibrator_path}")
    else:
        has_calibrator = False
        print("No existing isotonic_calibrator.pkl found - will only use raw and resource")
    
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
        calibrated_prob = raw_prob.copy()  # Fallback to raw
    
    # Calculate current over
    over = np.ceil(20 - df['overs_remaining']).astype(int) + 1
    
    # Step 1: Analyze best sources
    print("\n" + "=" * 70)
    print("STEP 1: ANALYZING BEST ECE SOURCE PER PHASE")
    print("=" * 70)
    
    analysis = analyze_best_sources(df, y, raw_prob, calibrated_prob, resource_prob, over)
    
    print(f"\n{'Phase':<20} {'Samples':>8} {'ECE Raw':>10} {'ECE Cal':>10} {'ECE Res':>10} {'Best':>8}")
    print("-" * 70)
    for r in analysis:
        print(f"{r['key']:<20} {r['samples']:>8,} {r['ece_raw']:>10.4f} {r['ece_cal']:>10.4f} {r['ece_res']:>10.4f} {r['best_source']:>8}")
    
    # Step 2: Train calibrators
    print("\n" + "=" * 70)
    print("STEP 2: TRAINING PHASE CALIBRATORS")
    print("=" * 70)
    
    phase_calibrators = {}
    training_results = []
    
    for r in analysis:
        mask = (df['innings'] == r['innings']) & (over >= r['start']) & (over <= r['end'])
        
        # Select input based on best source
        if r['best_source'] == 'raw':
            input_prob = raw_prob[mask]
            source_name = 'Raw'
        elif r['best_source'] == 'cal':
            input_prob = calibrated_prob[mask]
            source_name = 'Calibrated'
        else:
            input_prob = resource_prob[mask]
            source_name = 'Resource'
        
        # Train isotonic calibrator
        iso = IsotonicRegression(out_of_bounds='clip')
        iso.fit(input_prob, y[mask])
        
        # Store with source info
        phase_calibrators[r['key']] = {
            'calibrator': iso,
            'source': r['best_source']
        }
        
        # Calculate ECE after
        cal_output = iso.predict(input_prob)
        ece_after = expected_calibration_error(y[mask], cal_output)
        brier_before = brier_score(y[mask], input_prob)
        brier_after = brier_score(y[mask], cal_output)
        
        training_results.append({
            'key': r['key'],
            'source': source_name,
            'samples': r['samples'],
            'ece_before': r['best_ece'],
            'ece_after': ece_after,
            'brier_before': brier_before,
            'brier_after': brier_after
        })
        
        print(f"\n{r['key']} ({r['samples']:,} samples)")
        print(f"  Source: {source_name}")
        print(f"  ECE:   {r['best_ece']:.4f} --> {ece_after:.4f}")
        print(f"  Brier: {brier_before:.4f} --> {brier_after:.4f}")
    
    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(phase_calibrators, output_path)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n{'Phase':<20} {'Source':<12} {'ECE Before':>12} {'ECE After':>12}")
    print("-" * 60)
    for tr in training_results:
        print(f"{tr['key']:<20} {tr['source']:<12} {tr['ece_before']:>12.4f} {tr['ece_after']:>12.4f}")
    
    print(f"\n✅ Saved {len(phase_calibrators)} phase calibrators to {output_path}")
    
    return phase_calibrators


def main():
    parser = argparse.ArgumentParser(description='Train phase-specific ECE-optimized calibrators')
    parser.add_argument('--model-dir', required=True, help='Path to model directory')
    parser.add_argument('--features', required=True, help='Path to training.parquet')
    parser.add_argument('--output', default=None, help='Output path for phase_calibrators.pkl')
    
    args = parser.parse_args()
    train_phase_calibrators(args.model_dir, args.features, args.output)


if __name__ == '__main__':
    main()
