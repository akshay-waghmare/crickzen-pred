#!/usr/bin/env python3
"""Compare BBL v10 vs v11 OOF calibration metrics."""
import pandas as pd

# Load both OOF results
v10 = pd.read_csv('models/bbl_v10/oof_calibration_results.csv')
v11 = pd.read_csv('models/bbl_v11/oof_calibration_results.csv')

# Get overall metrics
v10_overall = v10[v10['segment'] == 'overall'].set_index('method')
v11_overall = v11[v11['segment'] == 'overall'].set_index('method')

print('='*80)
print('BBL MODEL COMPARISON: v10 vs v11 (Dynamic Wicket Penalty)')
print('='*80)

print('\nOVERALL METRICS')
print('-'*60)

metrics = ['brier', 'ece', 'logloss']
methods = ['raw', 'combined', 'innings_specific', 'innings_phase', 'brier_optimized', 'ece_optimized', 'logloss_optimized']

header = f"{'Method':<20} {'Metric':<10} {'v10':>10} {'v11':>10} {'Change':>10} {'%':>8}"
print(header)
print('-'*70)

for method in methods:
    for metric in metrics:
        if method in v10_overall.index and method in v11_overall.index:
            v10_val = v10_overall.loc[method, metric]
            v11_val = v11_overall.loc[method, metric]
            change = v11_val - v10_val
            pct = (change / v10_val) * 100 if v10_val != 0 else 0
            direction = '✅' if change < 0 else '❌' if change > 0 else '='
            print(f'{method:<20} {metric:<10} {v10_val:>10.4f} {v11_val:>10.4f} {change:>+10.4f} {pct:>+7.2f}% {direction}')
    print()

print('\n' + '='*80)
print('SUMMARY - Best Overall (brier_optimized method)')
print('='*80)
v10_best = v10_overall.loc['brier_optimized']
v11_best = v11_overall.loc['brier_optimized']
brier_pct = (v11_best['brier']-v10_best['brier'])/v10_best['brier']*100
logloss_pct = (v11_best['logloss']-v10_best['logloss'])/v10_best['logloss']*100
print(f"Brier:   v10={v10_best['brier']:.4f} -> v11={v11_best['brier']:.4f} ({brier_pct:+.2f}%)")
print(f"ECE:     v10={v10_best['ece']:.4f} -> v11={v11_best['ece']:.4f}")
print(f"LogLoss: v10={v10_best['logloss']:.4f} -> v11={v11_best['logloss']:.4f} ({logloss_pct:+.2f}%)")

# Per-innings comparison
print('\n' + '='*80)
print('PER-INNINGS COMPARISON (brier_optimized)')
print('='*80)

for inn in [1, 2]:
    segment = f'innings_{inn}'
    v10_inn = v10[(v10['segment'] == segment) & (v10['method'] == 'brier_optimized')]
    v11_inn = v11[(v11['segment'] == segment) & (v11['method'] == 'brier_optimized')]
    
    if len(v10_inn) > 0 and len(v11_inn) > 0:
        print(f"\nInnings {inn}:")
        for metric in ['brier', 'ece', 'logloss']:
            v10_val = v10_inn[metric].values[0]
            v11_val = v11_inn[metric].values[0]
            change = v11_val - v10_val
            pct = (change / v10_val) * 100 if v10_val != 0 else 0
            direction = '✅' if change < 0 else '❌' if change > 0 else '='
            print(f"  {metric:<8}: v10={v10_val:.4f} -> v11={v11_val:.4f} ({pct:+.2f}%) {direction}")
