#!/usr/bin/env python3
"""
SSM Female Per-Over ECE-Optimized Calibrators

Based on analysis from analyze_ssm_female_ece.py:
- Innings 1: ALL phases use Raw
- Innings 2 Powerplay (1-6): Use Cal
- Innings 2 Middle (7-15): Use Raw (ECE 0.0972 vs Cal 0.0975)
- Innings 2 Death (16-20): Use Raw

This is different from SSM Male where Resource was useful in Inn2 Middle!

Usage:
    python scripts/train_ssm_female_per_over_calibrators.py

Output:
    models/ssm_female_v1/per_over_calibrators.pkl
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.isotonic import IsotonicRegression
from pathlib import Path


def ece(y_true, y_prob, n_bins=10):
    e = 0.0
    for i in range(n_bins):
        mask = (y_prob >= i/n_bins) & (y_prob < (i+1)/n_bins)
        if mask.sum() > 0:
            e += mask.mean() * abs(y_prob[mask].mean() - y_true[mask].mean())
    return e


def get_best_source_ssm_female(innings, over_num):
    """
    SSM Female-specific best ECE source based on analysis.
    
    Key differences from SSM Male:
    - Resource is NEVER useful (always higher ECE/Brier)
    - Inn 2 Middle uses Raw, not Res
    """
    if innings == 1:
        # All phases: Raw is best
        return 'raw'
    else:  # innings == 2
        if over_num <= 6:
            # Powerplay: Calibrated is best
            return 'cal'
        elif over_num <= 15:
            # Middle: Raw is marginally better (0.0972 vs 0.0975)
            return 'raw'
        else:
            # Death: Raw is best
            return 'raw'


def main():
    model_dir = Path('models/ssm_female_v1')
    features_path = Path('data/ssm_female_features_v1/training.parquet')
    output_path = model_dir / 'per_over_calibrators.pkl'
    min_samples = 300  # Lower threshold for smaller dataset

    print("=" * 80)
    print("SSM FEMALE PER-OVER ECE-OPTIMIZED CALIBRATOR TRAINING")
    print("=" * 80)
    print(f"Model directory: {model_dir}")
    print(f"Features: {features_path}")
    print(f"Output: {output_path}")
    print(f"Min samples per over: {min_samples}")
    print()
    print("Source strategy (based on ECE analysis):")
    print("  Innings 1 ALL overs: Raw")
    print("  Innings 2 Overs 1-6 (PP): Cal")
    print("  Innings 2 Overs 7-15 (Mid): Raw")
    print("  Innings 2 Overs 16-20 (Death): Raw")
    
    # Load data
    df = pd.read_parquet(features_path)
    print(f"\nLoaded {len(df):,} training samples")
    
    # Load model and calibrator
    model = joblib.load(model_dir / 'champion_model.joblib')
    cal = joblib.load(model_dir / 'isotonic_calibrator.pkl')
    
    # Prepare features
    exclude_cols = ['is_winner', 'innings']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols]
    y = df['is_winner'].values
    
    # Get probabilities
    raw_prob = model.predict_proba(X)[:, 1]
    resource_prob = df['resource_win_prob'].values
    
    # Apply existing calibration
    inn1_mask = df['innings'] == 1
    inn2_mask = df['innings'] == 2
    cal_prob = np.zeros_like(raw_prob)
    cal_prob[inn1_mask] = cal['calibrator_innings1'].predict(raw_prob[inn1_mask])
    cal_prob[inn2_mask] = cal['calibrator_innings2'].predict(raw_prob[inn2_mask])
    
    # Calculate current over (1-20)
    over = np.ceil(20 - df['overs_remaining']).astype(int).clip(1, 20)
    
    # Train calibrators for each innings × over
    per_over_calibrators = {}
    results = []
    
    for innings in [1, 2]:
        print(f"\n{'='*80}")
        print(f"INNINGS {innings}")
        print(f"{'='*80}")
        
        for over_num in range(1, 21):
            mask = (df['innings'] == innings) & (over == over_num)
            n_samples = mask.sum()
            key = f'inn{innings}_over{over_num}'
            
            if n_samples < min_samples:
                print(f"  Over {over_num:2d}: {n_samples:5,} samples - SKIPPED (< {min_samples})")
                per_over_calibrators[key] = None
                continue
            
            # Get SSM Female-specific best source
            best_source = get_best_source_ssm_female(innings, over_num)
            
            if best_source == 'raw':
                input_prob = raw_prob[mask]
                source_name = 'Raw'
            elif best_source == 'cal':
                input_prob = cal_prob[mask]
                source_name = 'Cal'
            else:
                input_prob = resource_prob[mask]
                source_name = 'Res'
            
            # Train isotonic calibrator
            iso = IsotonicRegression(out_of_bounds='clip')
            iso.fit(input_prob, y[mask])
            cal_output = iso.predict(input_prob)
            
            per_over_calibrators[key] = {
                'calibrator': iso,
                'source': best_source,
                'method': 'isotonic'
            }
            
            ece_before = ece(y[mask], input_prob)
            ece_after = ece(y[mask], cal_output)
            
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
    joblib.dump(per_over_calibrators, output_path)
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    # Group by source
    raw_results = [r for r in results if r['source'] == 'Raw']
    cal_results = [r for r in results if r['source'] == 'Cal']
    
    print(f"\nBy Source:")
    if raw_results:
        print(f"  Raw: {len(raw_results)} overs, Avg ECE {np.mean([r['ece_before'] for r in raw_results]):.4f} -> {np.mean([r['ece_after'] for r in raw_results]):.4f}")
    if cal_results:
        print(f"  Cal: {len(cal_results)} overs, Avg ECE {np.mean([r['ece_before'] for r in cal_results]):.4f} -> {np.mean([r['ece_after'] for r in cal_results]):.4f}")
    
    total_ece_before = np.mean([r['ece_before'] for r in results])
    total_ece_after = np.mean([r['ece_after'] for r in results])
    print(f"\nOverall Average ECE: {total_ece_before:.4f} -> {total_ece_after:.4f}")
    print(f"\n✅ Saved {len(per_over_calibrators)} per-over calibrators to {output_path}")


if __name__ == '__main__':
    main()
