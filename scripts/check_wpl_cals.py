"""Check WPL phase calibrators structure."""
import joblib

phase_cals = joblib.load('models/wpl_female_v1/phase_calibrators.pkl')

print("WPL Phase Calibrators:")
print("="*60)

for key, val in phase_cals.items():
    if isinstance(val, dict):
        source = val.get('source', 'unknown')
        print(f"  {key}: source={source}")
    else:
        print(f"  {key}: legacy format (direct calibrator)")

print()
print(f"Total: {len(phase_cals)} phase calibrators")

# Also check Brier calibrators
print()
print("="*60)
print("WPL Brier-Optimized Calibrators:")
print("="*60)

brier_cals = joblib.load('models/wpl_female_v1/per_over_calibrators_brier.pkl')

for key, val in brier_cals.items():
    if isinstance(val, dict):
        source = val.get('source', 'unknown')
        print(f"  {key}: source={source}")
    else:
        print(f"  {key}: legacy format")

print()
print(f"Total: {len(brier_cals)} phase calibrators")
