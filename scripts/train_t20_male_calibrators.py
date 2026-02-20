#!/usr/bin/env python3
"""
Train Per-Over Calibrators for T20 Male Model

This script trains two sets of per-over calibrators:
1. Brier-optimized: Uses the best source per over for accuracy
2. ECE-optimized: Uses the best source per over for calibration

Based on analysis from analyze_t20_male_model.py:
- Innings 1: Raw model wins for both Brier and ECE
- Innings 2: Innings-calibrated wins for both Brier and ECE

Usage:
    python scripts/train_t20_male_calibrators.py

Output:
    models/t20_male_v1/per_over_calibrators_brier.pkl
    models/t20_male_v1/per_over_calibrators_ece.pkl

Author: Copilot
Date: 2026-01-11
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.isotonic import IsotonicRegression
from pathlib import Path
import json


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


def train_per_over_calibrators():
    """Train per-over calibrators for T20 Male model."""
    
    model_dir = Path('models/t20_male_v1')
    features_path = Path('data/t20_male_features_v1/training.parquet')
    
    print("=" * 80)
    print("T20 MALE PER-OVER CALIBRATOR TRAINING")
    print("=" * 80)
    print(f"Model directory: {model_dir}")
    print(f"Features: {features_path}")
    
    # Load data
    df = pd.read_parquet(features_path)
    print(f"\nLoaded {len(df):,} training samples")
    
    # Load model and existing calibrator
    model = joblib.load(model_dir / 'champion_model.joblib')
    isotonic_cal = joblib.load(model_dir / 'isotonic_calibrator.pkl')
    print(f"Loaded model and isotonic calibrator")
    
    # Prepare features
    exclude_cols = ['is_winner', 'overs_completed', 'match_id', 'ball_id']
    feature_cols = [col for col in df.columns if col not in exclude_cols and not col.startswith('_')]
    X = df[feature_cols].fillna(0)
    y = df['is_winner'].values
    
    # Get probabilities
    raw_probs = model.predict_proba(X)[:, 1]
    
    # Innings-specific calibrated probabilities
    innings_cal_probs = np.zeros_like(raw_probs)
    for innings in [1, 2]:
        mask = df['innings'] == innings
        if mask.sum() > 0:
            calibrator = isotonic_cal[f'calibrator_innings{innings}']
            innings_cal_probs[mask] = calibrator.predict(raw_probs[mask].reshape(-1, 1)).ravel()
    
    resource_probs = df['resource_win_prob'].values
    
    # Calculate current over from overs_remaining
    # overs_remaining = 19.5 means we're in over 1, overs_remaining = 0.5 means we're in over 20
    df['current_over'] = np.ceil(20 - df['overs_remaining']).astype(int).clip(1, 20)
    
    print("\n" + "=" * 80)
    print("TRAINING BRIER-OPTIMIZED CALIBRATORS")
    print("=" * 80)
    
    brier_calibrators = {}
    brier_results = []
    
    for innings in [1, 2]:
        for over in range(1, 21):
            mask = (df['innings'] == innings) & (df['current_over'] == over)
            
            if mask.sum() < 100:
                print(f"  Inn{innings}_Over{over}: Skipped (only {mask.sum()} samples)")
                continue
            
            y_subset = y[mask]
            raw_subset = raw_probs[mask]
            cal_subset = innings_cal_probs[mask]
            res_subset = resource_probs[mask]
            
            # Calculate Brier for each source
            brier_raw = brier_score(y_subset, raw_subset)
            brier_cal = brier_score(y_subset, cal_subset)
            brier_res = brier_score(y_subset, res_subset)
            
            # Find best source
            if brier_raw <= brier_cal and brier_raw <= brier_res:
                best_source = 'raw'
                input_probs = raw_subset
            elif brier_cal <= brier_res:
                best_source = 'cal'
                input_probs = cal_subset
            else:
                best_source = 'res'
                input_probs = res_subset
            
            # Train isotonic calibrator
            iso = IsotonicRegression(out_of_bounds='clip')
            iso.fit(input_probs, y_subset)
            
            # Calculate metrics after calibration
            calibrated_out = iso.predict(input_probs)
            brier_after = brier_score(y_subset, calibrated_out)
            ece_after = expected_calibration_error(y_subset, calibrated_out)
            
            key = f'inn{innings}_over{over}'
            brier_calibrators[key] = {
                'calibrator': iso,
                'source': best_source,
                'samples': int(mask.sum()),
                'brier_before': float(min(brier_raw, brier_cal, brier_res)),
                'brier_after': float(brier_after)
            }
            
            brier_results.append({
                'key': key,
                'source': best_source,
                'samples': mask.sum(),
                'brier_before': min(brier_raw, brier_cal, brier_res),
                'brier_after': brier_after
            })
            
            print(f"  {key}: {best_source} ({mask.sum():,} samples) Brier: {min(brier_raw, brier_cal, brier_res):.4f} -> {brier_after:.4f}")
    
    # Save Brier calibrators
    brier_output = model_dir / 'per_over_calibrators_brier.pkl'
    joblib.dump(brier_calibrators, brier_output)
    print(f"\n✅ Saved {len(brier_calibrators)} Brier calibrators to {brier_output}")
    
    print("\n" + "=" * 80)
    print("TRAINING ECE-OPTIMIZED CALIBRATORS")
    print("=" * 80)
    
    ece_calibrators = {}
    ece_results = []
    
    for innings in [1, 2]:
        for over in range(1, 21):
            mask = (df['innings'] == innings) & (df['current_over'] == over)
            
            if mask.sum() < 100:
                continue
            
            y_subset = y[mask]
            raw_subset = raw_probs[mask]
            cal_subset = innings_cal_probs[mask]
            res_subset = resource_probs[mask]
            
            # Calculate ECE for each source
            ece_raw = expected_calibration_error(y_subset, raw_subset)
            ece_cal = expected_calibration_error(y_subset, cal_subset)
            ece_res = expected_calibration_error(y_subset, res_subset)
            
            # Find best source
            if ece_raw <= ece_cal and ece_raw <= ece_res:
                best_source = 'raw'
                input_probs = raw_subset
            elif ece_cal <= ece_res:
                best_source = 'cal'
                input_probs = cal_subset
            else:
                best_source = 'res'
                input_probs = res_subset
            
            # Train isotonic calibrator
            iso = IsotonicRegression(out_of_bounds='clip')
            iso.fit(input_probs, y_subset)
            
            # Calculate metrics after calibration
            calibrated_out = iso.predict(input_probs)
            ece_after = expected_calibration_error(y_subset, calibrated_out)
            brier_after = brier_score(y_subset, calibrated_out)
            
            key = f'inn{innings}_over{over}'
            ece_calibrators[key] = {
                'calibrator': iso,
                'source': best_source,
                'samples': int(mask.sum()),
                'ece_before': float(min(ece_raw, ece_cal, ece_res)),
                'ece_after': float(ece_after)
            }
            
            ece_results.append({
                'key': key,
                'source': best_source,
                'samples': mask.sum(),
                'ece_before': min(ece_raw, ece_cal, ece_res),
                'ece_after': ece_after
            })
            
            print(f"  {key}: {best_source} ({mask.sum():,} samples) ECE: {min(ece_raw, ece_cal, ece_res):.4f} -> {ece_after:.4f}")
    
    # Save ECE calibrators
    ece_output = model_dir / 'per_over_calibrators_ece.pkl'
    joblib.dump(ece_calibrators, ece_output)
    print(f"\n✅ Saved {len(ece_calibrators)} ECE calibrators to {ece_output}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    # Brier summary
    brier_df = pd.DataFrame(brier_results)
    print("\nBrier-Optimized Source Distribution:")
    for innings in [1, 2]:
        inn_df = brier_df[brier_df['key'].str.startswith(f'inn{innings}')]
        counts = inn_df['source'].value_counts()
        print(f"  Innings {innings}: {dict(counts)}")
    
    avg_brier_before = brier_df['brier_before'].mean()
    avg_brier_after = brier_df['brier_after'].mean()
    print(f"\n  Average Brier: {avg_brier_before:.4f} -> {avg_brier_after:.4f}")
    
    # ECE summary
    ece_df = pd.DataFrame(ece_results)
    print("\nECE-Optimized Source Distribution:")
    for innings in [1, 2]:
        inn_df = ece_df[ece_df['key'].str.startswith(f'inn{innings}')]
        counts = inn_df['source'].value_counts()
        print(f"  Innings {innings}: {dict(counts)}")
    
    avg_ece_before = ece_df['ece_before'].mean()
    avg_ece_after = ece_df['ece_after'].mean()
    print(f"\n  Average ECE: {avg_ece_before:.4f} -> {avg_ece_after:.4f}")
    
    print("\n" + "=" * 80)
    print("CALIBRATOR FILES CREATED:")
    print("=" * 80)
    print(f"  1. {brier_output} - Use for best accuracy (Brier)")
    print(f"  2. {ece_output} - Use for best calibration (ECE)")
    
    return brier_calibrators, ece_calibrators


if __name__ == '__main__':
    train_per_over_calibrators()
