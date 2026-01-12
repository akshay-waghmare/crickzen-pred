#!/usr/bin/env python3
"""
SSM Brier-Optimized Per-Over Calibrator Training Script

Unlike ECE-optimized calibrators (per_over_calibrators.pkl), this creates
calibrators that select the BEST SOURCE for Brier score per over.

Analysis shows:
- Innings 1: Raw wins Brier ALL 20 overs
- Innings 2: Per-Over wins overs 1-4, 12-20 (13/20), Raw wins overs 5-11 (7/20)

This script trains calibrators that:
1. Select best Brier source per over
2. Train isotonic regression on that source
3. Result: Hybrid calibrator optimized for accuracy (Brier)

Usage:
    python scripts/train_ssm_brier_calibrators.py

Output:
    models/ssm_v1/brier_calibrators.pkl
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import log_loss
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


def main():
    # Paths
    model_dir = Path("models/ssm_v1")
    features_path = Path("data/ssm_features_v1/training.parquet")
    output_path = model_dir / "brier_calibrators.pkl"
    
    print("=" * 80)
    print("SSM BRIER-OPTIMIZED PER-OVER CALIBRATOR TRAINING")
    print("=" * 80)
    
    # Load data
    df = pd.read_parquet(features_path)
    print(f"Loaded {len(df):,} training samples")
    
    # Load model
    model = joblib.load(model_dir / "champion_model.joblib")
    print(f"Loaded model from {model_dir}")
    
    # Load existing per-over calibrators (for comparison)
    per_over_cal = joblib.load(model_dir / "per_over_calibrators.pkl")
    print("Loaded per_over_calibrators.pkl for comparison")
    
    # Prepare features
    exclude_cols = ['is_winner', 'innings']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols]
    y = df['is_winner'].values
    
    # Get raw probabilities
    raw_prob = model.predict_proba(X)[:, 1]
    resource_prob = df['resource_win_prob'].values
    
    # Get innings-specific calibrated probabilities (needed for source='cal')
    iso_cal = joblib.load(model_dir / "isotonic_calibrator.pkl")
    cal_prob = np.zeros_like(raw_prob)
    for i, inn in enumerate(df['innings'].values):
        inn_key = int(inn)
        if inn_key in iso_cal:
            cal_prob[i] = iso_cal[inn_key].predict([[raw_prob[i]]])[0]
        else:
            cal_prob[i] = raw_prob[i]
    cal_prob = np.clip(cal_prob, 1e-7, 1-1e-7)
    
    # Calculate over
    over = np.ceil(20 - df['overs_remaining']).astype(int) + 1
    over = np.clip(over, 1, 20)
    
    # Get per-over calibrated probs (applying CORRECT source for each calibrator)
    per_over_prob = np.zeros_like(raw_prob)
    for innings in [1, 2]:
        for ov in range(1, 21):
            mask = (df['innings'] == innings) & (over == ov)
            if mask.sum() == 0:
                continue
            key = f'inn{innings}_over{ov}'
            if key in per_over_cal and 'calibrator' in per_over_cal[key]:
                cal_info = per_over_cal[key]
                source = cal_info.get('source', 'raw')
                calibrator = cal_info['calibrator']
                
                # Select input based on ECE calibrator's source
                if source == 'raw':
                    input_prob = raw_prob[mask]
                elif source == 'cal':
                    input_prob = cal_prob[mask]
                else:  # 'res'
                    input_prob = resource_prob[mask]
                
                per_over_prob[mask] = calibrator.predict(input_prob)
            else:
                per_over_prob[mask] = raw_prob[mask]
    
    print("\n" + "=" * 80)
    print("STEP 1: ANALYZE BRIER-OPTIMAL SOURCE PER OVER")
    print("=" * 80)
    
    # Analyze per over
    analysis = []
    print(f"\n{'Inn':<4} {'Over':<5} {'N':<6} {'B_Raw':<8} {'B_Per':<8} {'B_Res':<8} {'Best':<6}")
    print("-" * 80)
    
    for innings in [1, 2]:
        for ov in range(1, 21):
            mask = (df['innings'] == innings) & (over == ov)
            n = mask.sum()
            if n == 0:
                continue
            
            y_ov = y[mask]
            b_raw = brier_score(y_ov, raw_prob[mask])
            b_per = brier_score(y_ov, per_over_prob[mask])
            b_res = brier_score(y_ov, resource_prob[mask])
            
            # Determine best source for Brier
            if b_raw <= b_per and b_raw <= b_res:
                best = 'raw'
                best_brier = b_raw
            elif b_per <= b_res:
                best = 'per'
                best_brier = b_per
            else:
                best = 'res'
                best_brier = b_res
            
            analysis.append({
                'innings': innings,
                'over': ov,
                'n': n,
                'b_raw': b_raw,
                'b_per': b_per,
                'b_res': b_res,
                'best': best,
                'best_brier': best_brier
            })
            
            marker = "*" if best == 'raw' else ("^" if best == 'per' else "~")
            print(f"{innings:<4} {ov:<5} {n:<6} {b_raw:<8.4f} {b_per:<8.4f} {b_res:<8.4f} {marker} {best}")
    
    # Summary
    raw_wins = sum(1 for a in analysis if a['best'] == 'raw')
    per_wins = sum(1 for a in analysis if a['best'] == 'per')
    res_wins = sum(1 for a in analysis if a['best'] == 'res')
    print("-" * 80)
    print(f"BRIER WINNERS: Raw={raw_wins}/40, Per-Over={per_wins}/40, Resource={res_wins}/40")
    
    print("\n" + "=" * 80)
    print("STEP 2: TRAIN BRIER-OPTIMIZED CALIBRATORS")
    print("=" * 80)
    
    brier_calibrators = {}
    
    for a in analysis:
        innings = a['innings']
        ov = a['over']
        best = a['best']
        
        mask = (df['innings'] == innings) & (over == ov)
        y_ov = y[mask]
        
        # Select input based on Brier-optimal source
        if best == 'raw':
            input_prob = raw_prob[mask]
            source = 'Raw'
        elif best == 'per':
            input_prob = per_over_prob[mask]
            source = 'PerOver'
        else:
            input_prob = resource_prob[mask]
            source = 'Resource'
        
        # Train isotonic calibrator on the best source
        iso = IsotonicRegression(out_of_bounds='clip')
        iso.fit(input_prob, y_ov)
        
        # Evaluate
        cal_prob = iso.predict(input_prob)
        b_before = brier_score(y_ov, input_prob)
        b_after = brier_score(y_ov, cal_prob)
        e_before = expected_calibration_error(y_ov, input_prob)
        e_after = expected_calibration_error(y_ov, cal_prob)
        
        key = f'inn{innings}_over{ov}'
        brier_calibrators[key] = {
            'calibrator': iso,
            'source': best,
            'b_before': b_before,
            'b_after': b_after,
            'e_before': e_before,
            'e_after': e_after,
        }
        
        print(f"{key}: Source={source:<8} Brier {b_before:.4f}→{b_after:.4f}, ECE {e_before:.4f}→{e_after:.4f}")
    
    # Save
    joblib.dump(brier_calibrators, output_path)
    print(f"\n✅ Saved Brier-optimized calibrators to {output_path}")
    
    print("\n" + "=" * 80)
    print("STEP 3: FINAL EVALUATION")
    print("=" * 80)
    
    # Calculate final calibrated probs using Brier-optimized calibrators
    brier_cal_prob = np.zeros_like(raw_prob)
    for innings in [1, 2]:
        for ov in range(1, 21):
            mask = (df['innings'] == innings) & (over == ov)
            if mask.sum() == 0:
                continue
            
            key = f'inn{innings}_over{ov}'
            if key not in brier_calibrators:
                brier_cal_prob[mask] = raw_prob[mask]
                continue
            
            cal_info = brier_calibrators[key]
            source = cal_info['source']
            
            # Get input based on source
            if source == 'raw':
                input_prob = raw_prob[mask]
            elif source == 'per':
                input_prob = per_over_prob[mask]
            else:
                input_prob = resource_prob[mask]
            
            # Apply calibrator
            brier_cal_prob[mask] = cal_info['calibrator'].predict(input_prob)
    
    # Final metrics
    print("\n" + "=" * 80)
    print("OVERALL COMPARISON")
    print("=" * 80)
    print(f"\n{'Method':<25} {'Brier':>10} {'ECE':>10} {'LogLoss':>10}")
    print("-" * 60)
    
    metrics = [
        ('Raw Model', raw_prob),
        ('Per-Over Cal (ECE opt)', per_over_prob),
        ('Brier-Optimized Cal', brier_cal_prob),
        ('Resource (DLS)', resource_prob),
    ]
    
    for name, prob in metrics:
        b = brier_score(y, prob)
        e = expected_calibration_error(y, prob)
        ll = log_loss(y, np.clip(prob, 1e-15, 1-1e-15))
        print(f"{name:<25} {b:>10.4f} {e:>10.4f} {ll:>10.4f}")
    
    print("\n" + "=" * 80)
    print("BY INNINGS COMPARISON")
    print("=" * 80)
    
    for innings in [1, 2]:
        mask = df['innings'] == innings
        print(f"\n--- Innings {innings} ---")
        print(f"{'Method':<25} {'Brier':>10} {'ECE':>10} {'LogLoss':>10}")
        print("-" * 60)
        
        for name, prob in metrics:
            b = brier_score(y[mask], prob[mask])
            e = expected_calibration_error(y[mask], prob[mask])
            ll = log_loss(y[mask], np.clip(prob[mask], 1e-15, 1-1e-15))
            print(f"{name:<25} {b:>10.4f} {e:>10.4f} {ll:>10.4f}")
    
    # Summary of what the calibrator does
    print("\n" + "=" * 80)
    print("BRIER CALIBRATOR STRATEGY")
    print("=" * 80)
    print("\nInnings 1 (all overs): Uses RAW MODEL as input (best Brier)")
    print("Innings 2 (overs 1-4, 12-20): Uses PER-OVER as input (best Brier)")
    print("Innings 2 (overs 5-11): Uses RAW MODEL as input (best Brier)")
    print("\nThis gives optimal accuracy (Brier) while still having isotonic calibration.")


if __name__ == "__main__":
    main()
