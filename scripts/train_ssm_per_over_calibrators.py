#!/usr/bin/env python3
"""
SSM-Specific Per-Over Calibrators

Based on analysis:
- Innings 1: Resource wins ALL 20 overs for ECE
- Innings 2: Mixed - Raw wins most, Res wins middle overs (5-11), Cal wins 1-2

Usage:
    python scripts/train_ssm_per_over_calibrators.py

Output:
    models/ssm_v1/per_over_calibrators.pkl
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


def brier(y_true, y_prob):
    return np.mean((y_prob - y_true) ** 2)


def get_best_source_ssm(innings, over_num):
    """
    SSM-specific best ECE source based on analysis.
    
    Inn 1: Resource wins ALL overs
    Inn 2: 
        - Overs 1-2: Cal
        - Overs 3-4, 12-20: Raw
        - Overs 5-11: Res
    """
    if innings == 1:
        return 'res'  # Resource wins all 20 overs in Inn 1
    else:
        if over_num <= 2:
            return 'cal'
        elif over_num <= 4:
            return 'raw'
        elif over_num <= 11:
            return 'res'
        else:
            return 'raw'


def main():
    model_dir = Path('models/ssm_v1')
    features_path = Path('data/ssm_features_v1/training.parquet')
    output_path = model_dir / 'per_over_calibrators.pkl'
    
    print("=" * 80)
    print("SSM PER-OVER ECE-OPTIMIZED CALIBRATOR TRAINING")
    print("=" * 80)
    print(f"Based on analysis: Inn1=Resource for all, Inn2=Mixed")
    
    # Load data
    df = pd.read_parquet(features_path)
    model = joblib.load(model_dir / 'champion_model.joblib')
    cal = joblib.load(model_dir / 'isotonic_calibrator.pkl')
    
    print(f"\nLoaded {len(df):,} training samples")
    
    exclude_cols = ['is_winner', 'innings']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols]
    y = df['is_winner'].values
    
    raw_prob = model.predict_proba(X)[:, 1]
    resource_prob = df['resource_win_prob'].values
    
    inn1_mask = df['innings'] == 1
    inn2_mask = df['innings'] == 2
    cal_prob = np.zeros_like(raw_prob)
    cal_prob[inn1_mask] = cal['calibrator_innings1'].predict(raw_prob[inn1_mask])
    cal_prob[inn2_mask] = cal['calibrator_innings2'].predict(raw_prob[inn2_mask])
    
    over = np.ceil(20 - df['overs_remaining']).astype(int).clip(1, 20)
    
    per_over_calibrators = {}
    
    print(f"\n{'Inn':>3} {'Over':>4} {'N':>6} {'Source':>6} | {'ECE_Before':>10} {'ECE_After':>10} | {'Brier_Before':>12} {'Brier_After':>12}")
    print("-" * 80)
    
    for innings in [1, 2]:
        for over_num in range(1, 21):
            mask = (df['innings'] == innings) & (over == over_num)
            n_samples = mask.sum()
            key = f'inn{innings}_over{over_num}'
            
            if n_samples < 100:
                per_over_calibrators[key] = None
                continue
            
            # Get SSM-specific best source
            best_source = get_best_source_ssm(innings, over_num)
            
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
            brier_before = brier(y[mask], input_prob)
            brier_after = brier(y[mask], cal_output)
            
            print(f"{innings:>3} {over_num:>4} {n_samples:>6} {source_name:>6} | {ece_before:>10.4f} {ece_after:>10.4f} | {brier_before:>12.4f} {brier_after:>12.4f}")
        print()
    
    # Fill missing overs
    for innings in [1, 2]:
        for over_num in range(1, 21):
            key = f'inn{innings}_over{over_num}'
            if per_over_calibrators.get(key) is None:
                for delta in range(1, 20):
                    for neighbor in [over_num - delta, over_num + delta]:
                        if 1 <= neighbor <= 20:
                            neighbor_key = f'inn{innings}_over{neighbor}'
                            if per_over_calibrators.get(neighbor_key) is not None:
                                per_over_calibrators[key] = per_over_calibrators[neighbor_key]
                                print(f"  {key}: Inherited from {neighbor_key}")
                                break
                    if per_over_calibrators.get(key) is not None:
                        break
    
    # Save
    joblib.dump(per_over_calibrators, output_path)
    print(f"\n✅ Saved {len(per_over_calibrators)} per-over calibrators to {output_path}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SSM CALIBRATOR SOURCE SUMMARY")
    print("=" * 80)
    print("\nInnings 1: Resource for all 20 overs (best ECE)")
    print("Innings 2: Cal (1-2), Raw (3-4, 12-20), Res (5-11)")
    print("\nNote: Raw wins Brier in ALL overs - use raw for accuracy, ECE-cal for calibration")


if __name__ == '__main__':
    main()
