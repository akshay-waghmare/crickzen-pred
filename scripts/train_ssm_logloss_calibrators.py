#!/usr/bin/env python3
"""
SSM Male Log Loss-Optimized Per-Over Calibrator Training Script

Unlike ECE-optimized calibrators (per_over_calibrators.pkl), this creates
calibrators that select the BEST SOURCE for Log Loss per over.

Log Loss is more sensitive to overconfident predictions than Brier score,
making it ideal for betting/expected value calculations.

This script:
1. Analyzes Log Loss for all sources per over
2. Selects best Log Loss source per over  
3. Trains isotonic regression on that source
4. Result: Per-over calibrator optimized for Log Loss

Usage:
    python scripts/train_ssm_logloss_calibrators.py

Output:
    models/ssm_v1/logloss_calibrators.pkl
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import log_loss
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


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
    output_path = model_dir / "logloss_calibrators.pkl"
    
    print("=" * 80)
    print("SSM MALE LOG LOSS-OPTIMIZED PER-OVER CALIBRATOR TRAINING")
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
    
    # Load Brier calibrators if available
    brier_cal = None
    if (model_dir / "per_over_calibrators_brier.pkl").exists():
        brier_cal = joblib.load(model_dir / "per_over_calibrators_brier.pkl")
        print("Loaded per_over_calibrators_brier.pkl for comparison")
    
    # Prepare features
    feature_cols = list(model.selected_features_)
    X = df[feature_cols]
    y = df['is_winner'].values
    
    # Get raw probabilities
    raw_prob = model.predict_proba(X)[:, 1]
    resource_prob = df['resource_win_prob'].values
    
    # Get innings-specific calibrated probabilities
    iso_cal = joblib.load(model_dir / "isotonic_calibrator.pkl")
    cal_prob = np.zeros_like(raw_prob)
    for i, inn in enumerate(df['innings'].values):
        inn_key = f'calibrator_innings{int(inn)}'
        if inn_key in iso_cal:
            cal_prob[i] = iso_cal[inn_key].predict([[raw_prob[i]]])[0]
        else:
            cal_prob[i] = raw_prob[i]
    cal_prob = np.clip(cal_prob, 1e-7, 1 - 1e-7)
    
    # Calculate over
    over = np.ceil(20 - df['overs_remaining']).astype(int)
    over = np.clip(over, 1, 20)
    
    # Get per-over ECE calibrated probs
    per_over_prob = np.zeros_like(raw_prob)
    for innings in [1, 2]:
        for ov in range(1, 21):
            mask = (df['innings'] == innings) & (over == ov)
            if mask.sum() == 0:
                continue
            key = f'inn{innings}_over{ov}'
            if key in per_over_cal and per_over_cal[key] is not None and 'calibrator' in per_over_cal[key]:
                cal_info = per_over_cal[key]
                source = cal_info.get('source', 'raw')
                calibrator = cal_info['calibrator']
                
                if source == 'raw':
                    input_prob = raw_prob[mask]
                elif source == 'cal':
                    input_prob = cal_prob[mask]
                else:  # 'res'
                    input_prob = resource_prob[mask]
                
                per_over_prob[mask] = calibrator.predict(input_prob)
            else:
                per_over_prob[mask] = raw_prob[mask]
    per_over_prob = np.clip(per_over_prob, 1e-7, 1 - 1e-7)
    
    # Get Brier-optimized calibrated probs if available
    brier_prob = np.zeros_like(raw_prob)
    if brier_cal:
        for innings in [1, 2]:
            for ov in range(1, 21):
                mask = (df['innings'] == innings) & (over == ov)
                if mask.sum() == 0:
                    continue
                key = f'inn{innings}_over{ov}'
                if key in brier_cal and brier_cal[key] is not None and 'calibrator' in brier_cal[key]:
                    cal_info = brier_cal[key]
                    source = cal_info.get('source', 'raw')
                    calibrator = cal_info['calibrator']
                    method = cal_info.get('method', 'isotonic')
                    
                    if source == 'raw':
                        input_prob = raw_prob[mask]
                    elif source == 'cal':
                        input_prob = cal_prob[mask]
                    elif source == 'per':
                        input_prob = per_over_prob[mask]
                    else:  # 'res'
                        input_prob = resource_prob[mask]
                    
                    # Handle both isotonic and platt/logistic calibrators
                    if method == 'platt' or hasattr(calibrator, 'predict_proba'):
                        # Platt scaling (LogisticRegression) - needs 2D input
                        input_2d = input_prob.reshape(-1, 1)
                        brier_prob[mask] = calibrator.predict_proba(input_2d)[:, 1]
                    else:
                        # Isotonic regression - accepts 1D input
                        brier_prob[mask] = calibrator.predict(input_prob)
                else:
                    brier_prob[mask] = per_over_prob[mask]
    else:
        brier_prob = per_over_prob.copy()
    brier_prob = np.clip(brier_prob, 1e-7, 1 - 1e-7)
    
    print("\n" + "=" * 80)
    print("STEP 1: ANALYZE LOG LOSS-OPTIMAL SOURCE PER OVER")
    print("=" * 80)
    
    # Analyze per over
    analysis = []
    print(f"\n{'Inn':<4} {'Over':<5} {'N':<6} {'LL_Raw':<10} {'LL_Cal':<10} {'LL_Per':<10} {'LL_Bri':<10} {'LL_Res':<10} {'Best':<8}")
    print("-" * 90)
    
    for innings in [1, 2]:
        for ov in range(1, 21):
            mask = (df['innings'] == innings) & (over == ov)
            n = mask.sum()
            if n == 0:
                continue
            
            y_ov = y[mask]
            ll_raw = log_loss(y_ov, np.clip(raw_prob[mask], 1e-7, 1 - 1e-7))
            ll_cal = log_loss(y_ov, np.clip(cal_prob[mask], 1e-7, 1 - 1e-7))
            ll_per = log_loss(y_ov, np.clip(per_over_prob[mask], 1e-7, 1 - 1e-7))
            ll_bri = log_loss(y_ov, np.clip(brier_prob[mask], 1e-7, 1 - 1e-7))
            ll_res = log_loss(y_ov, np.clip(resource_prob[mask], 1e-7, 1 - 1e-7))
            
            # Determine best source for Log Loss
            lls = {'raw': ll_raw, 'cal': ll_cal, 'per': ll_per, 'bri': ll_bri, 'res': ll_res}
            best = min(lls, key=lls.get)
            best_ll = lls[best]
            
            analysis.append({
                'innings': innings,
                'over': ov,
                'n': n,
                'll_raw': ll_raw,
                'll_cal': ll_cal,
                'll_per': ll_per,
                'll_bri': ll_bri,
                'll_res': ll_res,
                'best': best,
                'best_ll': best_ll
            })
            
            markers = {'raw': '*', 'cal': '#', 'per': '^', 'bri': '@', 'res': '~'}
            marker = markers.get(best, '?')
            print(f"{innings:<4} {ov:<5} {n:<6} {ll_raw:<10.4f} {ll_cal:<10.4f} {ll_per:<10.4f} {ll_bri:<10.4f} {ll_res:<10.4f} {marker} {best}")
    
    # Summary
    raw_wins = sum(1 for a in analysis if a['best'] == 'raw')
    cal_wins = sum(1 for a in analysis if a['best'] == 'cal')
    per_wins = sum(1 for a in analysis if a['best'] == 'per')
    bri_wins = sum(1 for a in analysis if a['best'] == 'bri')
    res_wins = sum(1 for a in analysis if a['best'] == 'res')
    total = len(analysis)
    print("-" * 90)
    print(f"LOG LOSS WINNERS: Raw={raw_wins}/{total}, Cal={cal_wins}/{total}, Per-Over={per_wins}/{total}, Brier={bri_wins}/{total}, Resource={res_wins}/{total}")
    
    print("\n" + "=" * 80)
    print("STEP 2: TRAIN LOG LOSS-OPTIMIZED CALIBRATORS")
    print("=" * 80)
    
    logloss_calibrators = {}
    
    for a in analysis:
        innings = a['innings']
        ov = a['over']
        best = a['best']
        
        mask = (df['innings'] == innings) & (over == ov)
        y_ov = y[mask]
        
        # Select input based on Log Loss-optimal source
        if best == 'raw':
            input_prob = raw_prob[mask]
            source = 'raw'
        elif best == 'cal':
            input_prob = cal_prob[mask]
            source = 'cal'
        elif best == 'per':
            input_prob = per_over_prob[mask]
            source = 'per'
        elif best == 'bri':
            input_prob = brier_prob[mask]
            source = 'bri'
        else:  # res
            input_prob = resource_prob[mask]
            source = 'res'
        
        # Train isotonic calibrator on the best source
        iso = IsotonicRegression(out_of_bounds='clip')
        iso.fit(input_prob, y_ov)
        
        # Evaluate
        calibrated = iso.predict(input_prob)
        ll_before = log_loss(y_ov, np.clip(input_prob, 1e-7, 1 - 1e-7))
        ll_after = log_loss(y_ov, np.clip(calibrated, 1e-7, 1 - 1e-7))
        brier_before = brier_score(y_ov, input_prob)
        brier_after = brier_score(y_ov, calibrated)
        ece_before = expected_calibration_error(y_ov, input_prob)
        ece_after = expected_calibration_error(y_ov, calibrated)
        
        key = f'inn{innings}_over{ov}'
        logloss_calibrators[key] = {
            'calibrator': iso,
            'source': source,
            'method': 'isotonic',
            'll_before': ll_before,
            'll_after': ll_after,
            'brier_before': brier_before,
            'brier_after': brier_after,
            'ece_before': ece_before,
            'ece_after': ece_after,
            'n_samples': a['n']
        }
        
        print(f"{key}: src={source:3s} | LL: {ll_before:.4f} -> {ll_after:.4f} | Brier: {brier_before:.4f} -> {brier_after:.4f} | ECE: {ece_before:.4f} -> {ece_after:.4f}")
    
    # Save calibrators
    joblib.dump(logloss_calibrators, output_path)
    print(f"\n[OK] Saved Log Loss calibrators to {output_path}")
    
    # ==========================================================================
    # VALIDATION
    # ==========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE LOG LOSS CALIBRATORS")
    print("=" * 80)
    
    # Apply calibrators to all data
    ll_calibrated = np.zeros_like(raw_prob)
    for innings in [1, 2]:
        for ov in range(1, 21):
            mask = (df['innings'] == innings) & (over == ov)
            if mask.sum() == 0:
                continue
            key = f'inn{innings}_over{ov}'
            if key in logloss_calibrators:
                cal_info = logloss_calibrators[key]
                source = cal_info['source']
                calibrator = cal_info['calibrator']
                
                if source == 'raw':
                    input_prob = raw_prob[mask]
                elif source == 'cal':
                    input_prob = cal_prob[mask]
                elif source == 'per':
                    input_prob = per_over_prob[mask]
                elif source == 'bri':
                    input_prob = brier_prob[mask]
                else:  # 'res'
                    input_prob = resource_prob[mask]
                
                ll_calibrated[mask] = calibrator.predict(input_prob)
            else:
                ll_calibrated[mask] = per_over_prob[mask]
    ll_calibrated = np.clip(ll_calibrated, 1e-7, 1 - 1e-7)
    
    # Overall comparison
    print(f"\n{'Metric':<15} {'Raw':>12} {'Cal':>12} {'Per-Over':>12} {'Brier':>12} {'LL-Opt':>12}")
    print("-" * 75)
    print(f"{'Log Loss':<15} {log_loss(y, np.clip(raw_prob, 1e-7, 1-1e-7)):>12.4f} {log_loss(y, cal_prob):>12.4f} {log_loss(y, per_over_prob):>12.4f} {log_loss(y, brier_prob):>12.4f} {log_loss(y, ll_calibrated):>12.4f}")
    print(f"{'Brier':<15} {brier_score(y, raw_prob):>12.4f} {brier_score(y, cal_prob):>12.4f} {brier_score(y, per_over_prob):>12.4f} {brier_score(y, brier_prob):>12.4f} {brier_score(y, ll_calibrated):>12.4f}")
    print(f"{'ECE':<15} {expected_calibration_error(y, raw_prob):>12.4f} {expected_calibration_error(y, cal_prob):>12.4f} {expected_calibration_error(y, per_over_prob):>12.4f} {expected_calibration_error(y, brier_prob):>12.4f} {expected_calibration_error(y, ll_calibrated):>12.4f}")
    
    # By innings comparison
    print("\n" + "-" * 75)
    print("BY INNINGS:")
    for innings in [1, 2]:
        mask = df['innings'] == innings
        print(f"\nInnings {innings}:")
        print(f"  Log Loss: Raw={log_loss(y[mask], np.clip(raw_prob[mask], 1e-7, 1-1e-7)):.4f}, LL-Opt={log_loss(y[mask], ll_calibrated[mask]):.4f}")
        print(f"  Brier:    Raw={brier_score(y[mask], raw_prob[mask]):.4f}, LL-Opt={brier_score(y[mask], ll_calibrated[mask]):.4f}")
        print(f"  ECE:      Raw={expected_calibration_error(y[mask], raw_prob[mask]):.4f}, LL-Opt={expected_calibration_error(y[mask], ll_calibrated[mask]):.4f}")
    
    print("\n[OK] Training complete!")
    print(f"[OK] Log Loss calibrators saved to: {output_path}")


if __name__ == "__main__":
    main()
