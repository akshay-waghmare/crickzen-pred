"""Check per-over calibrator performance."""
import json
import joblib
import numpy as np
import math

# Load current state
d = json.load(open('data/live_state.json'))
print('=== CURRENT MATCH STATE ===')
print(f"Score: {d.get('score', '?')} ({d.get('overs', 0)} overs)")
print(f"Innings: {2 if d.get('is_second_innings') else 1}")
print(f"Batting Team: {d.get('batting_team')}")
print()

# Get probabilities
raw_prob = d.get('raw_win_prob', 0.5)
inn_specific = d.get('inn_specific_prob', raw_prob)
resource_prob = d.get('features', {}).get('resource_win_prob', 0.5)
print('=== MODEL PROBABILITIES ===')
print(f'Raw Model: {raw_prob*100:.1f}%')
print(f'Inn-Specific Calibrated: {inn_specific*100:.1f}%')
print(f'Resource (DLS): {resource_prob*100:.1f}%')
print()

# Check per-over calibrator
overs_float = d.get('overs', 0.0)
current_over = max(1, min(20, math.ceil(overs_float) if overs_float > 0 else 1))
is_inn2 = d.get('is_second_innings', False)
inn_num = 2 if is_inn2 else 1
calibrator_key = f'inn{inn_num}_over{current_over}'

print(f'=== PER-OVER CALIBRATOR ({calibrator_key}) ===')
cal = joblib.load('models/bbl_v10/per_over_calibrators.pkl')
if calibrator_key in cal:
    cal_info = cal[calibrator_key]
    source = cal_info['source']
    print(f'Source: {source}')
    
    if source == 'raw':
        input_prob = raw_prob
    elif source == 'cal':
        input_prob = inn_specific
    else:
        input_prob = resource_prob
    
    print(f'Input probability ({source}): {input_prob*100:.1f}%')
    
    # Apply calibrator correctly based on method
    method = cal_info.get('method', 'isotonic')
    if method == 'platt':
        # Platt scaling expects logits
        input_clipped = np.clip(input_prob, 0.001, 0.999)
        logit = np.log(input_clipped / (1 - input_clipped))
        ece_prob = cal_info['calibrator'].predict_proba([[logit]])[0, 1]
    else:
        # Isotonic expects probabilities directly
        ece_prob = cal_info['calibrator'].predict([[input_prob]])[0]
    
    print(f'Method: {method}')
    print(f'ECE-Optimized output: {ece_prob*100:.1f}%')
    print()
    
    # Test range of inputs to see calibrator behavior
    print('=== CALIBRATOR MAPPING ===')
    test_probs = [0.3, 0.4, 0.5, 0.6, 0.65, 0.7, 0.8, 0.9]
    for p in test_probs:
        if method == 'platt':
            p_clipped = np.clip(p, 0.001, 0.999)
            logit = np.log(p_clipped / (1 - p_clipped))
            out = cal_info['calibrator'].predict_proba([[logit]])[0, 1]
        else:
            out = cal_info['calibrator'].predict([[p]])[0]
        print(f'  {p*100:.0f}% -> {out*100:.1f}%')
    
    print()
    print('=== ANALYSIS ===')
    # Check the gap between input and output
    gap = (ece_prob - input_prob) * 100
    print(f'Gap between input and ECE output: {gap:+.1f}%')
    
    # Check if isotonic calibrator has extreme behavior
    calibrator = cal_info['calibrator']
    print(f'Calibrator type: {type(calibrator).__name__}')
    if hasattr(calibrator, 'X_thresholds_'):
        print(f'X thresholds: {calibrator.X_thresholds_[:5]}...{calibrator.X_thresholds_[-5:]}')
        print(f'Y thresholds: {calibrator.y_thresholds_[:5]}...{calibrator.y_thresholds_[-5:]}')
