"""Compare v11 vs v12 death over RAW metrics"""

import pandas as pd

v11 = pd.read_csv('models/bbl_v11/oof_calibration_results.csv')
v12 = pd.read_csv('models/bbl_v12/oof_calibration_results.csv')

print('='*80)
print('DEATH OVER RAW BRIER COMPARISON: v11 vs v12')
print('='*80)
print()

for seg in ['inn1_death', 'inn2_death']:
    v11_seg = v11[(v11['method'] == 'raw') & (v11['segment'] == seg)]
    v12_seg = v12[(v12['method'] == 'raw') & (v12['segment'] == seg)]
    
    if len(v11_seg) > 0 and len(v12_seg) > 0:
        v11_brier = v11_seg['brier'].values[0]
        v12_brier = v12_seg['brier'].values[0]
        v11_ece = v11_seg['ece'].values[0]
        v12_ece = v12_seg['ece'].values[0]
        v11_ll = v11_seg['logloss'].values[0]
        v12_ll = v12_seg['logloss'].values[0]
        
        brier_pct = (v12_brier - v11_brier) / v11_brier * 100
        ece_pct = (v12_ece - v11_ece) / v11_ece * 100 if v11_ece > 0 else 0
        ll_pct = (v12_ll - v11_ll) / v11_ll * 100
        
        brier_ok = "✅" if brier_pct < 0 else "❌"
        ece_ok = "✅" if ece_pct < 0 else "❌"
        ll_ok = "✅" if ll_pct < 0 else "❌"
        
        print(f'{seg}:')
        print(f'  Brier:   v11={v11_brier:.4f} -> v12={v12_brier:.4f} ({brier_pct:+.2f}%) {brier_ok}')
        print(f'  ECE:     v11={v11_ece:.4f} -> v12={v12_ece:.4f} ({ece_pct:+.2f}%) {ece_ok}')
        print(f'  LogLoss: v11={v11_ll:.4f} -> v12={v12_ll:.4f} ({ll_pct:+.2f}%) {ll_ok}')
        print()

print('='*80)
print('OVERALL RAW METRICS COMPARISON')
print('='*80)
print()

v11_overall = v11[(v11['method'] == 'raw') & (v11['segment'] == 'overall')]
v12_overall = v12[(v12['method'] == 'raw') & (v12['segment'] == 'overall')]

v11_b = v11_overall['brier'].values[0]
v12_b = v12_overall['brier'].values[0]
v11_e = v11_overall['ece'].values[0]
v12_e = v12_overall['ece'].values[0]

print(f"Overall RAW Brier: v11={v11_b:.4f} -> v12={v12_b:.4f} ({(v12_b-v11_b)/v11_b*100:+.2f}%)")
print(f"Overall RAW ECE:   v11={v11_e:.4f} -> v12={v12_e:.4f} ({(v12_e-v11_e)/v11_e*100:+.2f}%)")

# Also compare middle phase
print()
print('='*80)
print('MIDDLE OVER RAW BRIER COMPARISON: v11 vs v12')
print('='*80)
print()

for seg in ['inn1_middle', 'inn2_middle']:
    v11_seg = v11[(v11['method'] == 'raw') & (v11['segment'] == seg)]
    v12_seg = v12[(v12['method'] == 'raw') & (v12['segment'] == seg)]
    
    if len(v11_seg) > 0 and len(v12_seg) > 0:
        v11_brier = v11_seg['brier'].values[0]
        v12_brier = v12_seg['brier'].values[0]
        brier_pct = (v12_brier - v11_brier) / v11_brier * 100
        brier_ok = "✅" if brier_pct < 0 else "❌"
        print(f'{seg}: v11={v11_brier:.4f} -> v12={v12_brier:.4f} ({brier_pct:+.2f}%) {brier_ok}')
