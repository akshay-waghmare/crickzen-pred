#!/usr/bin/env python3
"""Analyze SSM ECE and Brier by innings x over to find best source."""

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
    df = pd.read_parquet('data/ssm_features_v1/training.parquet')
    model = joblib.load('models/ssm_v1/champion_model.joblib')
    cal = joblib.load('models/ssm_v1/isotonic_calibrator.pkl')

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

    print('=' * 100)
    print('SSM ECE & BRIER ANALYSIS BY INNINGS x OVER')
    print('=' * 100)
    header = f"{'Inn':>3} {'Over':>4} {'N':>6} | {'ECE_Raw':>8} {'ECE_Cal':>8} {'ECE_Res':>8} | {'Brier_Raw':>10} {'Brier_Cal':>10} {'Brier_Res':>10} | Best_ECE Best_Brier"
    print(header)
    print('-' * 100)

    results = []
    for innings in [1, 2]:
        for over_num in range(1, 21):
            mask = (df['innings'] == innings) & (over == over_num)
            if mask.sum() < 100:
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

    # Summary
    print('=' * 100)
    print('SUMMARY: Best Source by Innings')
    print('=' * 100)
    
    for innings in [1, 2]:
        inn_results = [r for r in results if r['innings'] == innings]
        ece_counts = {'Raw': 0, 'Cal': 0, 'Res': 0}
        brier_counts = {'Raw': 0, 'Cal': 0, 'Res': 0}
        for r in inn_results:
            ece_counts[r['best_ece']] += 1
            brier_counts[r['best_brier']] += 1
        print(f"\nInnings {innings}:")
        print(f"  Best ECE:   Raw={ece_counts['Raw']}, Cal={ece_counts['Cal']}, Res={ece_counts['Res']}")
        print(f"  Best Brier: Raw={brier_counts['Raw']}, Cal={brier_counts['Cal']}, Res={brier_counts['Res']}")


if __name__ == '__main__':
    main()
