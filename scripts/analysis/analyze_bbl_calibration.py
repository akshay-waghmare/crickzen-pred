"""BBL v10 Calibration Analysis Script."""
import pandas as pd
import numpy as np
import joblib

# Load data and model
df = pd.read_parquet('data/bbl_features_v2/training.parquet')
model = joblib.load('models/bbl_v10/champion_model.joblib')
calibrator = joblib.load('models/bbl_v10/isotonic_calibrator.pkl')

# Features - exclude target and metadata
exclude_cols = ['is_winner', 'innings']
feature_cols = [c for c in df.columns if c not in exclude_cols]
X = df[feature_cols]
y = df['is_winner'].values

# Get predictions
raw_prob = model.predict_proba(X)[:, 1]
resource_prob = df['resource_win_prob'].values

# Apply innings-specific calibrators
inn1_mask = df['innings'] == 1
inn2_mask = df['innings'] == 2

calibrated_prob = np.zeros_like(raw_prob)
calibrated_prob[inn1_mask] = calibrator['calibrator_innings1'].predict(raw_prob[inn1_mask])
calibrated_prob[inn2_mask] = calibrator['calibrator_innings2'].predict(raw_prob[inn2_mask])

# Metrics functions
def brier_score(y_true, y_pred):
    return np.mean((y_pred - y_true) ** 2)

def expected_calibration_error(y_true, y_pred, n_bins=10):
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        in_bin = (y_pred >= bin_boundaries[i]) & (y_pred < bin_boundaries[i + 1])
        prop_in_bin = in_bin.mean()
        if prop_in_bin > 0:
            avg_pred = y_pred[in_bin].mean()
            avg_true = y_true[in_bin].mean()
            ece += prop_in_bin * abs(avg_pred - avg_true)
    return ece

print('=' * 70)
print('BBL v10 MODEL CALIBRATION ANALYSIS')
print('=' * 70)

# Overall metrics
print(f'\n{"OVERALL":=^70}')
print(f'Total samples: {len(y):,}')
print(f'\n{"Metric":<25} {"Raw Model":<15} {"Calibrated":<15} {"Resource Prob":<15}')
print('-' * 70)
print(f'{"Brier Score":<25} {brier_score(y, raw_prob):<15.4f} {brier_score(y, calibrated_prob):<15.4f} {brier_score(y, resource_prob):<15.4f}')
print(f'{"ECE":<25} {expected_calibration_error(y, raw_prob):<15.4f} {expected_calibration_error(y, calibrated_prob):<15.4f} {expected_calibration_error(y, resource_prob):<15.4f}')

# Innings 1
print(f'\n{"INNINGS 1 (Batting Team Setting Target)":=^70}')
y1, raw1, cal1, res1 = y[inn1_mask], raw_prob[inn1_mask], calibrated_prob[inn1_mask], resource_prob[inn1_mask]
print(f'Samples: {len(y1):,}')
print(f'\n{"Metric":<25} {"Raw Model":<15} {"Calibrated":<15} {"Resource Prob":<15}')
print('-' * 70)
print(f'{"Brier Score":<25} {brier_score(y1, raw1):<15.4f} {brier_score(y1, cal1):<15.4f} {brier_score(y1, res1):<15.4f}')
print(f'{"ECE":<25} {expected_calibration_error(y1, raw1):<15.4f} {expected_calibration_error(y1, cal1):<15.4f} {expected_calibration_error(y1, res1):<15.4f}')

# Innings 2
print(f'\n{"INNINGS 2 (Batting Team Chasing)":=^70}')
y2, raw2, cal2, res2 = y[inn2_mask], raw_prob[inn2_mask], calibrated_prob[inn2_mask], resource_prob[inn2_mask]
print(f'Samples: {len(y2):,}')
print(f'\n{"Metric":<25} {"Raw Model":<15} {"Calibrated":<15} {"Resource Prob":<15}')
print('-' * 70)
print(f'{"Brier Score":<25} {brier_score(y2, raw2):<15.4f} {brier_score(y2, cal2):<15.4f} {brier_score(y2, res2):<15.4f}')
print(f'{"ECE":<25} {expected_calibration_error(y2, raw2):<15.4f} {expected_calibration_error(y2, cal2):<15.4f} {expected_calibration_error(y2, res2):<15.4f}')

# Phase analysis
print(f'\n{"PHASE ANALYSIS":=^70}')

# Need to get 'over' from somewhere - check if it's in original data
# Since we don't have 'over' column, we'll skip phase analysis or estimate based on row count
# Let's check the data
if 'over' in df.columns:
    for phase, (start, end) in [('Powerplay (1-6)', (1, 6)), ('Middle (7-15)', (7, 15)), ('Death (16-20)', (16, 20))]:
        phase_mask = (df['over'] >= start) & (df['over'] <= end)
        yp = y[phase_mask]
        rawp = raw_prob[phase_mask]
        calp = calibrated_prob[phase_mask]
        resp = resource_prob[phase_mask]
        print(f'\n{phase} - {len(yp):,} samples')
        print(f'  Brier: Raw={brier_score(yp, rawp):.4f}, Cal={brier_score(yp, calp):.4f}, Res={brier_score(yp, resp):.4f}')
        print(f'  ECE:   Raw={expected_calibration_error(yp, rawp):.4f}, Cal={expected_calibration_error(yp, calp):.4f}, Res={expected_calibration_error(yp, resp):.4f}')
else:
    # Derive phase from overs_remaining
    # Total overs = 20, overs_remaining tells us which over we're in
    overs_completed = 20 - df['overs_remaining']
    over = np.ceil(overs_completed).astype(int) + 1  # Convert to 1-indexed over number
    
    for phase, (start, end) in [('Powerplay (1-6)', (1, 6)), ('Middle (7-15)', (7, 15)), ('Death (16-20)', (16, 20))]:
        phase_mask = (over >= start) & (over <= end)
        yp = y[phase_mask]
        rawp = raw_prob[phase_mask]
        calp = calibrated_prob[phase_mask]
        resp = resource_prob[phase_mask]
        print(f'\n{phase} - {len(yp):,} samples')
        print(f'  Brier: Raw={brier_score(yp, rawp):.4f}, Cal={brier_score(yp, calp):.4f}, Res={brier_score(yp, resp):.4f}')
        print(f'  ECE:   Raw={expected_calibration_error(yp, rawp):.4f}, Cal={expected_calibration_error(yp, calp):.4f}, Res={expected_calibration_error(yp, resp):.4f}')

# Winner summary
print(f'\n{"WINNER BY METRIC":=^70}')
for name, yt, rawt, calt, rest in [('Overall', y, raw_prob, calibrated_prob, resource_prob),
                                    ('Innings 1', y1, raw1, cal1, res1),
                                    ('Innings 2', y2, raw2, cal2, res2)]:
    brier_raw = brier_score(yt, rawt)
    brier_cal = brier_score(yt, calt)
    brier_res = brier_score(yt, rest)
    ece_raw = expected_calibration_error(yt, rawt)
    ece_cal = expected_calibration_error(yt, calt)
    ece_res = expected_calibration_error(yt, rest)
    
    brier_best = 'Raw' if brier_raw <= brier_cal and brier_raw <= brier_res else ('Cal' if brier_cal <= brier_res else 'Res')
    ece_best = 'Raw' if ece_raw <= ece_cal and ece_raw <= ece_res else ('Cal' if ece_cal <= ece_res else 'Res')
    
    print(f'{name}: Brier winner={brier_best}, ECE winner={ece_best}')
