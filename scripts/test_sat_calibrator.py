"""Test SAT v1 per-over calibrator behavior."""
import joblib
import numpy as np

cal = joblib.load('models/sat_v1/per_over_calibrators.pkl')

print("=== SAT v1 Per-Over Calibrator Analysis ===\n")

# Check all calibrators for extreme behavior
print("Checking for extreme calibrators (>20% adjustment at 60% input):\n")
extreme_cals = []

for key in sorted(cal.keys()):
    cal_info = cal[key]
    source = cal_info['source']
    method = cal_info.get('method', 'isotonic')
    
    # Test with 60% input
    input_prob = 0.60
    if method == 'platt':
        p_clipped = np.clip(input_prob, 0.001, 0.999)
        logit = np.log(p_clipped / (1 - p_clipped))
        out = cal_info['calibrator'].predict_proba([[logit]])[0, 1]
    else:
        out = cal_info['calibrator'].predict([[input_prob]])[0]
    
    diff = (out - input_prob) * 100
    if abs(diff) > 20:
        extreme_cals.append((key, source, method, input_prob * 100, out * 100, diff))
        print(f"  {key}: {input_prob*100:.0f}% -> {out*100:.1f}% ({diff:+.1f}%) [src={source}, method={method}]")

if not extreme_cals:
    print("  None found - all calibrators are reasonable!")

print("\n=== Sample Calibrator Mappings ===\n")

# Test a few specific ones
test_keys = ['inn1_over3', 'inn1_over10', 'inn2_over10', 'inn2_over19']
test_probs = [0.40, 0.50, 0.60, 0.70, 0.80]

for key in test_keys:
    if key in cal:
        cal_info = cal[key]
        source = cal_info['source']
        method = cal_info.get('method', 'isotonic')
        print(f"{key} (source={source}, method={method}):")
        for p in test_probs:
            if method == 'platt':
                p_clipped = np.clip(p, 0.001, 0.999)
                logit = np.log(p_clipped / (1 - p_clipped))
                out = cal_info['calibrator'].predict_proba([[logit]])[0, 1]
            else:
                out = cal_info['calibrator'].predict([[p]])[0]
            diff = (out - p) * 100
            print(f"  {p*100:.0f}% -> {out*100:.1f}% ({diff:+.1f}%)")
        print()
