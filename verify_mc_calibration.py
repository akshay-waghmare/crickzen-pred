
import os
import joblib
import numpy as np
from bbl_pipeline.calibration.mc_calibrator import MCCalibrator, InningsMCCalibrators

model_dir = "models/t20_international_male_v1"
cal_path = os.path.join(model_dir, "mc_calibrators_innings.pkl")

if not os.path.exists(cal_path):
    print(f"ERROR: {cal_path} not found")
    exit(1)

calibrators = InningsMCCalibrators.load(cal_path)
print("="*60)
print("INNINGS-SPECIFIC MC CALIBRATOR VERIFICATION")
print("="*60)
print(calibrators.summary())
print()

test_probs = [0.1, 0.3, 0.5, 0.7, 0.9]

print(f"{'Raw Prob':<10} | {'Inn 1 Cal':<12} | {'Inn 2 Cal':<12} | {'Shift 1':<10} | {'Shift 2':<10}")
print("-" * 65)

for p in test_probs:
    c1 = calibrators.calibrate(p, innings=1)
    c2 = calibrators.calibrate(p, innings=2)
    s1 = c1 - p
    s2 = c2 - p
    print(f"{p:<10.2f} | {c1:<12.4f} | {c2:<12.4f} | {s1:<+10.4f} | {s2:<+10.4f}")

print("\nConclusion:")
if abs(calibrators.calibrate(0.5, 1) - 0.5) > 0.0001 or abs(calibrators.calibrate(0.5, 2) - 0.5) > 0.0001:
    print("✓ Calibrators ARE providing distinct, calibrated output.")
else:
    print("! Calibrators might be identity (near-zero shift).")

if abs(calibrators.calibrate(0.5, 1) - calibrators.calibrate(0.5, 2)) > 0.0001:
    print("✓ Innings-specific calibration is DIFFERENT for Inn 1 vs Inn 2.")
else:
    print("! Innings-specific calibration is IDENTICAL (or very similar).")
