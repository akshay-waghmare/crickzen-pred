"""Test that ECE and Brier calibrators produce different outputs."""
import joblib
import numpy as np

ece = joblib.load('models/bbl_v10/per_over_calibrators.pkl')
brier = joblib.load('models/bbl_v10/per_over_calibrators_brier.pkl')

test_prob = 0.62  # Sample raw probability

print("Testing with raw_prob = 0.62")
print("=" * 60)

keys = ['inn1_over1', 'inn1_over10', 'inn1_over14', 'inn2_over5', 'inn2_over15']
for key in keys:
    ece_cal = ece[key]
    brier_cal = brier[key]
    
    ece_result = ece_cal['calibrator'].predict([[test_prob]])[0]
    brier_result = brier_cal['calibrator'].predict([[test_prob]])[0]
    
    diff = abs(ece_result - brier_result)
    same = "SAME" if diff < 0.001 else "DIFFERENT"
    
    print(f"{key}:")
    print(f"  ECE source: {ece_cal['source']}, Brier source: {brier_cal['source']}")
    print(f"  ECE output: {ece_result:.4f}, Brier output: {brier_result:.4f}")
    print(f"  Difference: {diff:.4f} --> {same}")
    print()
