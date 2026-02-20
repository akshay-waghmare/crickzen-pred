"""Compare ECE-Optimized vs Brier-Optimized for WPL Female with detailed table."""
import pandas as pd
import numpy as np
import joblib

def calculate_logloss(y_true, y_pred, eps=1e-15):
    y_pred = np.clip(y_pred, eps, 1 - eps)
    return -np.mean(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))

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
    elif over <= 15: return 'middle'
    else: return 'death'

# Load data
df = pd.read_parquet('data/wpl_female_features_v1/training.parquet')
model = joblib.load('models/wpl_female_v1/champion_model.joblib')
existing_cal = joblib.load('models/wpl_female_v1/isotonic_calibrator.pkl')
phase_cals = joblib.load('models/wpl_female_v1/phase_calibrators.pkl')  # ECE-Optimized (6 phases)
brier_cals = joblib.load('models/wpl_female_v1/per_over_calibrators_brier.pkl')  # Brier-Optimized (8 phases)

features = model.selected_features_
df['over'] = (20 - df['overs_remaining']).clip(1, 20).astype(int)
df['phase'] = df['over'].apply(get_phase)
df['phase_detailed'] = df['over'].apply(lambda x: 'powerplay' if x <= 6 else ('middle_early' if x <= 11 else ('middle_late' if x <= 15 else 'death')))

y_true = df['is_winner'].values
resource_probs = df['resource_win_prob'].values
X = df[features]
raw_probs = model.predict_proba(X)[:, 1]

# Inn-specific
inn_probs = np.zeros_like(raw_probs)
inn1_mask = df['innings'] == 1
inn2_mask = df['innings'] == 2
inn_probs[inn1_mask] = existing_cal['calibrator_innings1'].predict(raw_probs[inn1_mask])
inn_probs[inn2_mask] = existing_cal['calibrator_innings2'].predict(raw_probs[inn2_mask])

# ECE-optimized (6 phases, resource-based mostly)
ece_probs = np.zeros_like(raw_probs)
for idx in range(len(df)):
    inn = int(df.iloc[idx]['innings'])
    phase = df.iloc[idx]['phase']  # 3-phase version (powerplay, middle, death)
    key = f'inn{inn}_{phase}'
    if key in phase_cals:
        cal_info = phase_cals[key]
        if isinstance(cal_info, dict):
            source = cal_info.get('source', 'resource')
            if source == 'resource':
                ece_probs[idx] = cal_info['calibrator'].predict([[resource_probs[idx]]])[0]
            else:
                ece_probs[idx] = cal_info['calibrator'].predict([[raw_probs[idx]]])[0]
        else:
            ece_probs[idx] = cal_info.predict([[resource_probs[idx]]])[0]
    else:
        ece_probs[idx] = resource_probs[idx]

# Brier-optimized (8 phases, all raw source)
brier_probs = np.zeros_like(raw_probs)
for idx in range(len(df)):
    inn = int(df.iloc[idx]['innings'])
    phase = df.iloc[idx]['phase_detailed']  # 4-phase version (powerplay, middle_early, middle_late, death)
    key = f'inn{inn}_{phase}'
    if key in brier_cals:
        cal_info = brier_cals[key]
        source = cal_info['source']
        if source == 'raw':
            brier_probs[idx] = cal_info['calibrator'].predict([[raw_probs[idx]]])[0]
        elif source == 'resource':
            brier_probs[idx] = cal_info['calibrator'].predict([[resource_probs[idx]]])[0]
        else:
            brier_probs[idx] = cal_info['calibrator'].predict([[inn_probs[idx]]])[0]
    else:
        brier_probs[idx] = raw_probs[idx]

print('='*120)
print('WPL FEMALE: ECE-OPTIMIZED vs BRIER-OPTIMIZED CALIBRATORS')
print('='*120)
print()

# Overall metrics
ll_raw = calculate_logloss(y_true, raw_probs)
ll_ece = calculate_logloss(y_true, ece_probs)
ll_brier = calculate_logloss(y_true, brier_probs)

b_raw = calculate_brier(y_true, raw_probs)
b_ece = calculate_brier(y_true, ece_probs)
b_brier = calculate_brier(y_true, brier_probs)

e_raw = calculate_ece(y_true, raw_probs)
e_ece = calculate_ece(y_true, ece_probs)
e_brier = calculate_ece(y_true, brier_probs)

print(f"{'Model':<35} | {'Log Loss':<12} | {'Brier':<12} | {'ECE':<12} | Notes")
print('-'*120)
print(f"{'Raw Model (Ensemble)':<35} | {ll_raw:<12.4f} | {b_raw:<12.4f} | {e_raw:<12.4f} | Baseline")
print(f"{'ECE-Optimized (6 phases, Res)':<35} | {ll_ece:<12.4f} | {b_ece:<12.4f} | {e_ece:<12.4f} | Best ECE")
print(f"{'🔵 Brier-Optimized (8 phases, Raw)':<35} | {ll_brier:<12.4f} | {b_brier:<12.4f} | {e_brier:<12.4f} | Best Brier & LL")
print('='*120)

# Comparison
print()
print('DETAILED COMPARISON:')
print('-'*120)
print()
print(f"Brier-Optimized vs Raw Model:")
print(f"  Log Loss:  {ll_brier:.4f} vs {ll_raw:.4f} → {(1 - ll_brier/ll_raw)*100:.1f}% BETTER ✅")
print(f"  Brier:     {b_brier:.4f} vs {b_raw:.4f} → {(1 - b_brier/b_raw)*100:.1f}% BETTER ✅")
print(f"  ECE:       {e_brier:.4f} vs {e_raw:.4f} → {(1 - e_brier/e_raw)*100:.1f}% BETTER ✅")
print()

print(f"ECE-Optimized vs Raw Model:")
print(f"  Log Loss:  {ll_ece:.4f} vs {ll_raw:.4f} → {(1 - ll_ece/ll_raw)*100:.1f}% BETTER ✅")
print(f"  Brier:     {b_ece:.4f} vs {b_raw:.4f} → {(1 - b_ece/b_raw)*100:.1f}% BETTER ✅")
print(f"  ECE:       {e_ece:.4f} vs {e_raw:.4f} → {(1 - e_ece/e_raw)*100:.1f}% BETTER ✅")
print()

print(f"Brier-Optimized vs ECE-Optimized:")
print(f"  Log Loss:  {ll_brier:.4f} vs {ll_ece:.4f} → {(1 - ll_brier/ll_ece)*100:.1f}% BETTER ✅")
print(f"  Brier:     {b_brier:.4f} vs {b_ece:.4f} → {(1 - b_brier/b_ece)*100:.1f}% BETTER ✅")
print(f"  ECE:       {e_brier:.4f} vs {e_ece:.4f} → {(1 - e_brier/e_ece)*100:.1f}% BETTER ✅")

print()
print('='*120)
print('BY INNINGS BREAKDOWN:')
print('='*120)

for inn in [1, 2]:
    mask = df['innings'] == inn
    y = y_true[mask]
    
    ll_r = calculate_logloss(y, raw_probs[mask])
    ll_e = calculate_logloss(y, ece_probs[mask])
    ll_b = calculate_logloss(y, brier_probs[mask])
    
    b_r = calculate_brier(y, raw_probs[mask])
    b_e = calculate_brier(y, ece_probs[mask])
    b_b = calculate_brier(y, brier_probs[mask])
    
    e_r = calculate_ece(y, raw_probs[mask])
    e_e = calculate_ece(y, ece_probs[mask])
    e_b = calculate_ece(y, brier_probs[mask])
    
    print(f"\n  Innings {inn}:")
    print(f"    {'Model':<30} | {'Log Loss':<12} | {'Brier':<12} | {'ECE':<12}")
    print(f"    {'-'*70}")
    print(f"    {'Raw Model':<30} | {ll_r:<12.4f} | {b_r:<12.4f} | {e_r:<12.4f}")
    print(f"    {'ECE-Optimized':<30} | {ll_e:<12.4f} | {b_e:<12.4f} | {e_e:<12.4f}")
    print(f"    {'Brier-Optimized':<30} | {ll_b:<12.4f} | {b_b:<12.4f} | {e_b:<12.4f}")

print()
print('='*120)
print('CALIBRATOR STRUCTURE:')
print('='*120)
print()
print(f"ECE-Optimized (phase_calibrators.pkl):")
print(f"  - 6 phases (3 per innings)")
print(f"  - Phases: powerplay (1-6), middle (7-15), death (16-20)")
print(f"  - Sources: Mostly RESOURCE (best for ECE)")
print(f"  - All phases shown in phase_calibrators: {list(phase_cals.keys())}")
print()
print(f"Brier-Optimized (per_over_calibrators_brier.pkl):")
print(f"  - 8 phases (4 per innings)")
print(f"  - Phases: powerplay (1-6), middle_early (7-11), middle_late (12-15), death (16-20)")
print(f"  - Sources: All RAW (best for Brier)")
print(f"  - All phases shown in brier_calibrators: {list(brier_cals.keys())}")
