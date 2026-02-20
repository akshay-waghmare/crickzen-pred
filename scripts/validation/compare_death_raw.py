#!/usr/bin/env python3
"""Compare death over RAW Brier scores between v10 and v11."""
import pandas as pd

v10 = pd.read_csv('models/bbl_v10/oof_calibration_results.csv')
v11 = pd.read_csv('models/bbl_v11/oof_calibration_results.csv')

print('='*80)
print('DEATH OVER RAW BRIER COMPARISON (v10 vs v11)')
print('='*80)

# Get raw method, death phase segments
segments = ['inn1_death', 'inn2_death']

for seg in segments:
    v10_raw = v10[(v10['segment'] == seg) & (v10['method'] == 'raw')]
    v11_raw = v11[(v11['segment'] == seg) & (v11['method'] == 'raw')]
    
    if len(v10_raw) > 0 and len(v11_raw) > 0:
        for metric in ['brier', 'ece', 'logloss']:
            v10_val = v10_raw[metric].values[0]
            v11_val = v11_raw[metric].values[0]
            pct = (v11_val - v10_val) / v10_val * 100
            direction = '✅' if pct < 0 else '❌' if pct > 0 else '='
            print(f'{seg} {metric}: v10={v10_val:.4f} -> v11={v11_val:.4f} ({pct:+.2f}%) {direction}')
        print()

# Also show all phases for raw
print('='*80)
print('ALL PHASES - RAW METHOD')
print('='*80)

phases = ['inn1_powerplay', 'inn1_middle', 'inn1_death', 'inn2_powerplay', 'inn2_middle', 'inn2_death']

header = f"{'Segment':<18} {'Metric':<8} {'v10':>10} {'v11':>10} {'Change':>10} {'%':>8}"
print(header)
print('-'*70)

for seg in phases:
    v10_raw = v10[(v10['segment'] == seg) & (v10['method'] == 'raw')]
    v11_raw = v11[(v11['segment'] == seg) & (v11['method'] == 'raw')]
    
    if len(v10_raw) > 0 and len(v11_raw) > 0:
        for metric in ['brier', 'ece', 'logloss']:
            v10_val = v10_raw[metric].values[0]
            v11_val = v11_raw[metric].values[0]
            change = v11_val - v10_val
            pct = (change / v10_val) * 100
            direction = '✅' if change < 0 else '❌' if change > 0 else '='
            print(f'{seg:<18} {metric:<8} {v10_val:>10.4f} {v11_val:>10.4f} {change:>+10.4f} {pct:>+7.2f}% {direction}')
