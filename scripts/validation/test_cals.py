import joblib
import numpy as np

per_over_cals = joblib.load('models/sat_v1/per_over_calibrators.pkl')
phase_cals = joblib.load('models/sat_v1/phase_calibrators.pkl')

print('='*60)
print('SA20 CALIBRATOR DEBUG')
print('='*60)

# Check source field
cal_info = per_over_cals['inn1_over5']
print('Per-Over source:', cal_info.get('source'))
print('Per-Over method:', cal_info.get('method'))

# Test with different input probabilities
print()
print('='*60)
print('TESTING CALIBRATORS - Per-Over (Platt) vs Phase (Isotonic)')
print('='*60)

for test_p in [0.45, 0.50, 0.52, 0.55, 0.58, 0.60, 0.70, 0.80, 0.86]:
    # Per-over: Platt scaling (logistic)
    cal = cal_info['calibrator']
    input_clipped = np.clip(test_p, 0.001, 0.999)
    logit = np.log(input_clipped / (1 - input_clipped))
    brier_out = cal.predict_proba([[logit]])[0, 1]
    
    # Phase: Isotonic
    ece_out = phase_cals['inn1_powerplay'].predict([[test_p]])[0]
    
    print(f'  Input: {test_p:.2f} -> Per-Over: {brier_out:.4f}, Phase: {ece_out:.4f}')

print()
print('='*60)
print('ISSUE IDENTIFIED:')
print('='*60)
print('Calibrators are trained on source="raw" (raw model output)')
print('But the raw model outputs ~0.86 for this match state')
print('And the calibrators output 1.0 for anything > 0.6')
print()
print('This means calibrators were trained on DIFFERENT data distribution!')
print('Need to check what the training data looked like.')
