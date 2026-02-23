import joblib
import numpy as np
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.bbl_pipeline.calibration.mc_calibrator import InningsMCCalibrators

def inspect():
    path = "models/t20_international_male_v1/mc_calibrators_innings.pkl"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
        
    try:
        # Try loading with joblib directly to see the type
        raw_obj = joblib.load(path)
        print(f"Object type: {type(raw_obj)}")
        print(f"Object module: {type(raw_obj).__module__}")
        
        cal = raw_obj
        # Summary
        print(f"\nSummary:\n{cal.summary()}\n")
        
        test_probs = [0.1, 0.3, 0.5, 0.7, 0.9]
        print(f"{'Prob':<10} | {'Inn1 Output':<15} | {'Inn2 Output':<15} | {'Diff'}")
        print("-" * 55)
        for p in test_probs:
            p1 = cal.calibrate(p, 1)
            p2 = cal.calibrate(p, 2)
            print(f"{p:<10.2f} | {p1:<15.4f} | {p2:<15.4f} | {p1-p:.4f}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect()
