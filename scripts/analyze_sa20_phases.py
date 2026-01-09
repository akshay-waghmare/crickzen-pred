"""Quick SA20 phase-by-phase calibration analysis."""
import pandas as pd
import numpy as np
import joblib

df = pd.read_parquet('data/sat_features_v1/training.parquet')
model = joblib.load('models/sat_v1/champion_model.joblib')
isotonic = joblib.load('models/sat_v1/isotonic_calibrator.pkl')

X = df[model.selected_features_]
raw_probs = model.predict_proba(X)[:, 1]
df['raw_prob'] = raw_probs

cal_inn1 = isotonic['calibrator_innings1']
cal_inn2 = isotonic['calibrator_innings2']
df['cal_prob'] = df.apply(lambda r: cal_inn1.predict([r['raw_prob']])[0] if r['innings']==1 else cal_inn2.predict([r['raw_prob']])[0], axis=1)
df['resource_prob'] = df['resource_win_prob']
df['over'] = (20 - df['overs_remaining']).clip(1, 20).astype(int)

def get_phase(o): 
    return 'powerplay' if o<=6 else ('middle_early' if o<=11 else ('middle_late' if o<=15 else 'death'))

df['phase'] = df['over'].apply(get_phase)

def brier(y,p): 
    return np.mean((y-p)**2)

def ece(y,p,n=10):
    bins = np.linspace(0,1,n+1)
    e=0.0
    for i in range(n):
        m=(p>=bins[i])&(p<bins[i+1])
        if m.sum()>0: 
            e+=m.sum()/len(y)*abs(y[m].mean()-p[m].mean())
    return e

print('\n' + '='*100)
print('SA20 CALIBRATION ANALYSIS BY INNINGS & PHASE')
print('='*100)
header = f"{'Inn':<4}| {'Phase':<13}| {'N':>5} | {'B_Raw':>7} | {'B_Cal':>7} | {'B_Res':>7} | {'E_Raw':>7} | {'E_Cal':>7} | {'E_Res':>7} | Best_B | Best_E"
print(header)
print('-'*100)

for inn in [1,2]:
    for ph in ['powerplay','middle_early','middle_late','death']:
        m = (df['innings']==inn) & (df['phase']==ph)
        s = df[m]
        n = len(s)
        if n > 0:
            y = s['is_winner'].values
            br = brier(y, s['raw_prob'].values)
            bc = brier(y, s['cal_prob'].values)
            bres = brier(y, s['resource_prob'].values)
            er = ece(y, s['raw_prob'].values)
            ec = ece(y, s['cal_prob'].values)
            eres = ece(y, s['resource_prob'].values)
            
            bb = 'Raw' if br == min(br,bc,bres) else ('Cal' if bc == min(br,bc,bres) else 'Res')
            be = 'Raw' if er == min(er,ec,eres) else ('Cal' if ec == min(er,ec,eres) else 'Res')
            
            row = f"{inn:<4}| {ph:<13}| {n:>5} | {br:>7.4f} | {bc:>7.4f} | {bres:>7.4f} | {er:>7.4f} | {ec:>7.4f} | {eres:>7.4f} | {bb:<6} | {be:<6}"
            print(row)

print('='*100)
print('\nLEGEND:')
print('  B_* = Brier Score (lower is better)')
print('  E_* = ECE Score (lower is better)')
print('  Raw = Raw model output')
print('  Cal = Innings-specific isotonic calibrated')
print('  Res = Resource-based probability')
