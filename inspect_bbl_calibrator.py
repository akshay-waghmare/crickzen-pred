import joblib

cal = joblib.load('models/t20_male_v1/league_calibrators/bbl/isotonic_calibrator.pkl')

print('=== BBL LEAGUE CALIBRATORS ===\n')
print(f"Method: {cal['method']}")
print(f"Type: {cal['type']}")
print(f"League: {cal['league']}")
print(f"Created: {cal['created_date']}")
print(f"Features: {cal['n_features']}")

print('\n1. INNINGS CALIBRATORS:')
print(f"  - calibrator_innings1: TemperatureScaler (T={cal['calibrator_innings1'].temperature:.4f})")
print(f"  - calibrator_innings2: TemperatureScaler (T={cal['calibrator_innings2'].temperature:.4f})")
print(f"  - calibrator_combined: TemperatureScaler (T={cal['calibrator_combined'].temperature:.4f})")

print('\n2. PHASE CALIBRATORS:')
for key in sorted(cal.get('phase_calibrators', {}).keys()):
    scaler = cal['phase_calibrators'][key]
    print(f"  - {key}: TemperatureScaler (T={scaler.temperature:.4f})")

print('\n3. METRICS:')
print(f"  Overall:")
print(f"    - Brier (raw):        {cal['oof_brier_raw']:.4f}")
print(f"    - Brier (calibrated): {cal['oof_brier_calibrated']:.4f}")
print(f"    - Improvement:        {(1 - cal['oof_brier_calibrated']/cal['oof_brier_raw'])*100:+.1f}%")

print(f"\n  Innings 1:")
inn1 = cal['innings1_metrics']
print(f"    - Brier (raw):        {inn1['brier_raw']:.4f}")
print(f"    - Brier (calibrated): {inn1['brier_calibrated']:.4f}")
print(f"    - LogLoss (raw):      {inn1['logloss_raw']:.4f}")
print(f"    - LogLoss (calibrated): {inn1['logloss_calibrated']:.4f}")

print(f"\n  Innings 2:")
inn2 = cal['innings2_metrics']
print(f"    - Brier (raw):        {inn2['brier_raw']:.4f}")
print(f"    - Brier (calibrated): {inn2['brier_calibrated']:.4f}")
print(f"    - LogLoss (raw):      {inn2['logloss_raw']:.4f}")
print(f"    - LogLoss (calibrated): {inn2['logloss_calibrated']:.4f}")

print('\n4. USAGE:')
print("  # Load calibrator")
print("  cal_data = joblib.load('models/t20_male_v1/league_calibrators/bbl/isotonic_calibrator.pkl')")
print("  ")
print("  # Apply to innings 1")
print("  calibrated = cal_data['calibrator_innings1'].predict(raw_probs)")
print("  ")
print("  # Apply to innings 2")
print("  calibrated = cal_data['calibrator_innings2'].predict(raw_probs)")
print("  ")
print("  # Or use combined (fallback)")
print("  calibrated = cal_data['calibrator_combined'].predict(raw_probs)")
