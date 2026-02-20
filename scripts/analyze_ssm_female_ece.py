#!/usr/bin/env python3
"""Analyze SSM Female ECE and Brier by innings x over to find best source."""

import pandas as pd
import numpy as np
import joblib


def ece(y_true, y_prob, n_bins=10):
    e = 0.0
    for i in range(n_bins):
        mask = (y_prob >= i/n_bins) & (y_prob < (i+1)/n_bins)
        if mask.sum() > 0:
            e += mask.mean() * abs(y_prob[mask].mean() - y_true[mask].mean())
    return e


def brier(y_true, y_prob):
    return np.mean((y_prob - y_true) ** 2)


def main():
    # Load data
    df = pd.read_parquet('data/ssm_female_features_v1/training.parquet')
    model = joblib.load('models/ssm_female_v1/champion_model.joblib')
    cal = joblib.load('models/ssm_female_v1/isotonic_calibrator.pkl')

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

    print('=' * 110)
    print('SSM FEMALE ECE & BRIER ANALYSIS BY INNINGS x OVER')
    print('=' * 110)
    print(f"Total samples: {len(df):,}")
    print()
    header = f"{'Inn':>3} {'Over':>4} {'N':>6} | {'ECE_Raw':>8} {'ECE_Cal':>8} {'ECE_Res':>8} | {'Brier_Raw':>10} {'Brier_Cal':>10} {'Brier_Res':>10} | Best_ECE Best_Brier"
    print(header)
    print('-' * 110)

    results = []
    for innings in [1, 2]:
        for over_num in range(1, 21):
            mask = (df['innings'] == innings) & (over == over_num)
            if mask.sum() < 50:  # Lower threshold for smaller dataset
                continue
            yp = y[mask]
            ece_raw = ece(yp, raw_prob[mask])
            ece_cal = ece(yp, cal_prob[mask])
            ece_res = ece(yp, resource_prob[mask])
            br_raw = brier(yp, raw_prob[mask])
            br_cal = brier(yp, cal_prob[mask])
            br_res = brier(yp, resource_prob[mask])
            
            # Best ECE
            if ece_raw <= ece_cal and ece_raw <= ece_res:
                best_ece = 'Raw'
            elif ece_cal <= ece_res:
                best_ece = 'Cal'
            else:
                best_ece = 'Res'
            
            # Best Brier
            if br_raw <= br_cal and br_raw <= br_res:
                best_brier = 'Raw'
            elif br_cal <= br_res:
                best_brier = 'Cal'
            else:
                best_brier = 'Res'
            
            results.append({
                'innings': innings, 'over': over_num, 'n': mask.sum(),
                'ece_raw': ece_raw, 'ece_cal': ece_cal, 'ece_res': ece_res,
                'br_raw': br_raw, 'br_cal': br_cal, 'br_res': br_res,
                'best_ece': best_ece, 'best_brier': best_brier
            })
            
            print(f"{innings:>3} {over_num:>4} {mask.sum():>6} | {ece_raw:>8.4f} {ece_cal:>8.4f} {ece_res:>8.4f} | {br_raw:>10.4f} {br_cal:>10.4f} {br_res:>10.4f} | {best_ece:>8} {best_brier:>10}")
        print()

    # Summary by phase
    print('=' * 110)
    print('SUMMARY: Best Source by Innings x Phase')
    print('=' * 110)
    
    phases = [
        ('Powerplay', 1, 6),
        ('Middle', 7, 15),
        ('Death', 16, 20)
    ]
    
    for innings in [1, 2]:
        print(f"\n{'='*50}")
        print(f"INNINGS {innings}")
        print(f"{'='*50}")
        
        for phase_name, start, end in phases:
            phase_results = [r for r in results if r['innings'] == innings and start <= r['over'] <= end]
            if not phase_results:
                continue
            
            # Count best sources
            ece_counts = {'Raw': 0, 'Cal': 0, 'Res': 0}
            brier_counts = {'Raw': 0, 'Cal': 0, 'Res': 0}
            
            # Weighted averages
            total_n = sum(r['n'] for r in phase_results)
            avg_ece_raw = sum(r['ece_raw'] * r['n'] for r in phase_results) / total_n
            avg_ece_cal = sum(r['ece_cal'] * r['n'] for r in phase_results) / total_n
            avg_ece_res = sum(r['ece_res'] * r['n'] for r in phase_results) / total_n
            avg_br_raw = sum(r['br_raw'] * r['n'] for r in phase_results) / total_n
            avg_br_cal = sum(r['br_cal'] * r['n'] for r in phase_results) / total_n
            avg_br_res = sum(r['br_res'] * r['n'] for r in phase_results) / total_n
            
            for r in phase_results:
                ece_counts[r['best_ece']] += 1
                brier_counts[r['best_brier']] += 1
            
            # Determine overall best for phase
            if avg_ece_raw <= avg_ece_cal and avg_ece_raw <= avg_ece_res:
                overall_ece = 'Raw'
            elif avg_ece_cal <= avg_ece_res:
                overall_ece = 'Cal'
            else:
                overall_ece = 'Res'
                
            if avg_br_raw <= avg_br_cal and avg_br_raw <= avg_br_res:
                overall_brier = 'Raw'
            elif avg_br_cal <= avg_br_res:
                overall_brier = 'Cal'
            else:
                overall_brier = 'Res'
            
            print(f"\n{phase_name} (Overs {start}-{end}): {total_n:,} samples")
            print(f"  ECE by over:    Raw={ece_counts['Raw']}, Cal={ece_counts['Cal']}, Res={ece_counts['Res']}")
            print(f"  Brier by over:  Raw={brier_counts['Raw']}, Cal={brier_counts['Cal']}, Res={brier_counts['Res']}")
            print(f"  Weighted Avg ECE:   Raw={avg_ece_raw:.4f}, Cal={avg_ece_cal:.4f}, Res={avg_ece_res:.4f} --> BEST: {overall_ece}")
            print(f"  Weighted Avg Brier: Raw={avg_br_raw:.4f}, Cal={avg_br_cal:.4f}, Res={avg_br_res:.4f} --> BEST: {overall_brier}")

    # Overall recommendation
    print('\n' + '=' * 110)
    print('RECOMMENDATIONS FOR SSM FEMALE')
    print('=' * 110)
    
    for innings in [1, 2]:
        print(f"\nInnings {innings}:")
        for phase_name, start, end in phases:
            phase_results = [r for r in results if r['innings'] == innings and start <= r['over'] <= end]
            if not phase_results:
                continue
            total_n = sum(r['n'] for r in phase_results)
            avg_ece_raw = sum(r['ece_raw'] * r['n'] for r in phase_results) / total_n
            avg_ece_cal = sum(r['ece_cal'] * r['n'] for r in phase_results) / total_n
            avg_ece_res = sum(r['ece_res'] * r['n'] for r in phase_results) / total_n
            
            if avg_ece_raw <= avg_ece_cal and avg_ece_raw <= avg_ece_res:
                rec = 'Raw'
            elif avg_ece_cal <= avg_ece_res:
                rec = 'Cal'
            else:
                rec = 'Res'
            print(f"  {phase_name:10s}: Use {rec} (ECE: Raw={avg_ece_raw:.4f}, Cal={avg_ece_cal:.4f}, Res={avg_ece_res:.4f})")


if __name__ == '__main__':
    main()
