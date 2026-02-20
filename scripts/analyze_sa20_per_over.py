"""
SA20 Per-Over Brier & ECE Analysis (5-Fold CV)

Generates detailed per-over breakdown comparing:
- Raw model (XGBLogRegEnsemble output)
- Resource-based (DLS-style resource_win_prob)
- Phase calibrators (8 calibrators) on raw model
- Per-over calibrators (39 calibrators) on raw model
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.model_selection import StratifiedKFold
from sklearn.isotonic import IsotonicRegression

FEATURES_PATH = Path('data/sat_features_v1/training.parquet')
MODEL_PATH = Path('models/sat_v1/champion_model.joblib')

def calculate_brier(y_true, y_pred):
    return np.mean((y_true - y_pred) ** 2)

def calculate_ece(y_true, y_pred, n_bins=10):
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_pred >= bin_boundaries[i]) & (y_pred < bin_boundaries[i + 1])
        if mask.sum() > 0:
            bin_accuracy = y_true[mask].mean()
            bin_confidence = y_pred[mask].mean()
            bin_weight = mask.sum() / len(y_true)
            ece += bin_weight * abs(bin_accuracy - bin_confidence)
    return ece

def get_phase(over):
    if over <= 6: return 'powerplay'
    elif over <= 11: return 'middle_early'
    elif over <= 15: return 'middle_late'
    else: return 'death'

print('='*100)
print('SA20: PER-OVER BRIER & ECE ANALYSIS (5-Fold CV) - RAW MODEL vs RESOURCE vs CALIBRATORS')
print('='*100)

# Load data and model
df = pd.read_parquet(FEATURES_PATH)
model = joblib.load(MODEL_PATH)
features = model.selected_features_

df['over'] = (20 - df['overs_remaining']).clip(1, 20).astype(int)
df['phase'] = df['over'].apply(get_phase)

y_true = df['is_winner'].values
resource_probs = df['resource_win_prob'].values

# Generate raw model predictions
X = df[features]
raw_model_probs = model.predict_proba(X)[:, 1]

print(f"Loaded {len(df):,} rows")
print(f"Raw Model vs Resource correlation: {np.corrcoef(raw_model_probs, resource_probs)[0,1]:.4f}")

# 5-fold CV for calibrators (on raw model probs)
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
phase_cv_preds = np.zeros(len(df))
per_over_cv_preds = np.zeros(len(df))

for fold, (train_idx, val_idx) in enumerate(skf.split(df, y_true)):
    train_df = df.iloc[train_idx]
    train_raw = raw_model_probs[train_idx]
    train_y = y_true[train_idx]
    
    # Train phase calibrators on RAW MODEL probs
    fold_phase_cals = {}
    for innings in [1, 2]:
        for phase in ['powerplay', 'middle_early', 'middle_late', 'death']:
            mask = (train_df['innings'] == innings) & (train_df['phase'] == phase)
            if mask.sum() >= 50:
                ir = IsotonicRegression(out_of_bounds='clip')
                ir.fit(train_raw[mask.values], train_y[mask.values])
                fold_phase_cals[f'inn{innings}_{phase}'] = ir
    
    # Train per-over calibrators on RAW MODEL probs
    fold_over_cals = {}
    for innings in [1, 2]:
        for over in range(1, 21):
            mask = (train_df['innings'] == innings) & (train_df['over'] == over)
            if mask.sum() >= 30:
                ir = IsotonicRegression(out_of_bounds='clip')
                ir.fit(train_raw[mask.values], train_y[mask.values])
                fold_over_cals[f'inn{innings}_over{over}'] = ir
    
    # Apply to validation fold
    for idx in val_idx:
        row = df.iloc[idx]
        inn = int(row['innings'])
        over = int(row['over'])
        phase = row['phase']
        prob = raw_model_probs[idx]
        
        phase_key = f'inn{inn}_{phase}'
        if phase_key in fold_phase_cals:
            phase_cv_preds[idx] = fold_phase_cals[phase_key].predict([[prob]])[0]
        else:
            phase_cv_preds[idx] = prob
        
        over_key = f'inn{inn}_over{over}'
        if over_key in fold_over_cals:
            per_over_cv_preds[idx] = fold_over_cals[over_key].predict([[prob]])[0]
        else:
            per_over_cv_preds[idx] = prob

print()
print('OVERALL SUMMARY (5-fold CV):')
print('='*70)
print(f"{'Method':<25} | {'Brier':<12} | {'ECE':<12} | {'Notes':<20}")
print('-'*70)

raw_brier = calculate_brier(y_true, raw_model_probs)
raw_ece = calculate_ece(y_true, raw_model_probs)
res_brier = calculate_brier(y_true, resource_probs)
res_ece = calculate_ece(y_true, resource_probs)
phase_brier = calculate_brier(y_true, phase_cv_preds)
phase_ece = calculate_ece(y_true, phase_cv_preds)
per_over_brier = calculate_brier(y_true, per_over_cv_preds)
per_over_ece = calculate_ece(y_true, per_over_cv_preds)

print(f"{'Raw Model (Ensemble)':<25} | {raw_brier:.4f}       | {raw_ece:.4f}       | XGBLogRegEnsemble")
print(f"{'Resource (DLS-style)':<25} | {res_brier:.4f}       | {res_ece:.4f}       | resource_win_prob")
print(f"{'Phase Calibrated':<25} | {phase_brier:.4f}       | {phase_ece:.4f}       | 8 isotonic cals")
print(f"{'Per-Over Calibrated':<25} | {per_over_brier:.4f}       | {per_over_ece:.4f}       | 39 isotonic cals")
print('='*70)

print()
print('WINNER BY METRIC:')
print('-'*50)
all_briers = {'Raw Model': raw_brier, 'Resource': res_brier, 'Phase': phase_brier, 'Per-Over': per_over_brier}
all_eces = {'Raw Model': raw_ece, 'Resource': res_ece, 'Phase': phase_ece, 'Per-Over': per_over_ece}
print(f"   BRIER: {min(all_briers, key=all_briers.get)} wins ({min(all_briers.values()):.4f})")
print(f"   ECE:   {min(all_eces, key=all_eces.get)} wins ({min(all_eces.values()):.4f})")

print()
print('='*100)
print('INNINGS 1 - PER-OVER BREAKDOWN')
print('='*100)
print(f"{'Over':<5} | {'N':<6} | {'Brier_Raw':<11} | {'Brier_Res':<11} | {'Brier_Phase':<13} | {'Brier_PerOv':<12} | {'ECE_Raw':<9} | {'ECE_Res':<9} | {'ECE_Phase':<11} | {'ECE_PerOv':<10}")
print('-'*120)

for over in range(1, 21):
    mask = (df['innings'] == 1) & (df['over'] == over)
    if mask.sum() == 0:
        continue
    
    n = mask.sum()
    y = y_true[mask]
    raw = raw_model_probs[mask]
    res = resource_probs[mask]
    phase = phase_cv_preds[mask]
    per_ov = per_over_cv_preds[mask]
    
    brier_raw = calculate_brier(y, raw)
    brier_res = calculate_brier(y, res)
    brier_phase = calculate_brier(y, phase)
    brier_per_ov = calculate_brier(y, per_ov)
    
    ece_raw = calculate_ece(y, raw)
    ece_res = calculate_ece(y, res)
    ece_phase = calculate_ece(y, phase)
    ece_per_ov = calculate_ece(y, per_ov)
    
    print(f"{over:<5} | {n:<6} | {brier_raw:<11.4f} | {brier_res:<11.4f} | {brier_phase:<13.4f} | {brier_per_ov:<12.4f} | {ece_raw:<9.4f} | {ece_res:<9.4f} | {ece_phase:<11.4f} | {ece_per_ov:<10.4f}")

print()
print('='*100)
print('INNINGS 2 - PER-OVER BREAKDOWN')
print('='*100)
print(f"{'Over':<5} | {'N':<6} | {'Brier_Raw':<11} | {'Brier_Res':<11} | {'Brier_Phase':<13} | {'Brier_PerOv':<12} | {'ECE_Raw':<9} | {'ECE_Res':<9} | {'ECE_Phase':<11} | {'ECE_PerOv':<10}")
print('-'*120)

for over in range(1, 21):
    mask = (df['innings'] == 2) & (df['over'] == over)
    if mask.sum() == 0:
        continue
    
    n = mask.sum()
    y = y_true[mask]
    raw = raw_model_probs[mask]
    res = resource_probs[mask]
    phase = phase_cv_preds[mask]
    per_ov = per_over_cv_preds[mask]
    
    brier_raw = calculate_brier(y, raw)
    brier_res = calculate_brier(y, res)
    brier_phase = calculate_brier(y, phase)
    brier_per_ov = calculate_brier(y, per_ov)
    
    ece_raw = calculate_ece(y, raw)
    ece_res = calculate_ece(y, res)
    ece_phase = calculate_ece(y, phase)
    ece_per_ov = calculate_ece(y, per_ov)
    
    print(f"{over:<5} | {n:<6} | {brier_raw:<11.4f} | {brier_res:<11.4f} | {brier_phase:<13.4f} | {brier_per_ov:<12.4f} | {ece_raw:<9.4f} | {ece_res:<9.4f} | {ece_phase:<11.4f} | {ece_per_ov:<10.4f}")

# By innings summary
print()
print('='*100)
print('BY INNINGS SUMMARY:')
print('='*100)
for inn in [1, 2]:
    mask = df['innings'] == inn
    y = y_true[mask]
    
    raw_b = calculate_brier(y, raw_model_probs[mask])
    raw_e = calculate_ece(y, raw_model_probs[mask])
    res_b = calculate_brier(y, resource_probs[mask])
    res_e = calculate_ece(y, resource_probs[mask])
    phase_b = calculate_brier(y, phase_cv_preds[mask])
    phase_e = calculate_ece(y, phase_cv_preds[mask])
    per_ov_b = calculate_brier(y, per_over_cv_preds[mask])
    per_ov_e = calculate_ece(y, per_over_cv_preds[mask])
    
    print(f"  Innings {inn}:")
    print(f"    Raw Model:  Brier={raw_b:.4f}, ECE={raw_e:.4f}")
    print(f"    Resource:   Brier={res_b:.4f}, ECE={res_e:.4f}")
    print(f"    Phase:      Brier={phase_b:.4f}, ECE={phase_e:.4f}")
    print(f"    Per-Over:   Brier={per_ov_b:.4f}, ECE={per_ov_e:.4f}")
    
    briers = {'Raw': raw_b, 'Resource': res_b, 'Phase': phase_b, 'Per-Over': per_ov_b}
    eces = {'Raw': raw_e, 'Resource': res_e, 'Phase': phase_e, 'Per-Over': per_ov_e}
    print(f"    Winner: Brier={min(briers, key=briers.get)}, ECE={min(eces, key=eces.get)}")
    print()

print('='*100)
print('RECOMMENDATION:')
print('='*100)
print('  Compare Raw Model (ensemble) vs Resource (DLS-style) to see which base is better.')
print('  Then calibrators improve whichever base you choose.')
print('='*100)
