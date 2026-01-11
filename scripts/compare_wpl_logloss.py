"""Compare Log Loss of ECE-Optimized vs Brier-Optimized for WPL Female."""
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
phase_cals = joblib.load('models/wpl_female_v1/phase_calibrators.pkl')
brier_cals = joblib.load('models/wpl_female_v1/per_over_calibrators_brier.pkl')

features = model.selected_features_
df['over'] = (20 - df['overs_remaining']).clip(1, 20).astype(int)
df['phase'] = df['over'].apply(get_phase)

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

# ECE-optimized (phase calibrators on resource)
ece_probs = np.zeros_like(raw_probs)
for idx in range(len(df)):
    inn = int(df.iloc[idx]['innings'])
    phase = df.iloc[idx]['phase']
    key = f'inn{inn}_{phase}'
    if key in phase_cals:
        cal_info = phase_cals[key]
        if cal_info.get('source', 'resource') == 'resource':
            ece_probs[idx] = cal_info['calibrator'].predict([[resource_probs[idx]]])[0]
        else:
            ece_probs[idx] = cal_info['calibrator'].predict([[raw_probs[idx]]])[0]
    else:
        ece_probs[idx] = resource_probs[idx]

# Brier-optimized
brier_probs = np.zeros_like(raw_probs)
for idx in range(len(df)):
    inn = int(df.iloc[idx]['innings'])
    phase = df.iloc[idx]['phase']
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

print('='*100)
print('WPL FEMALE: ECE-OPTIMIZED vs BRIER-OPTIMIZED LOG LOSS COMPARISON')
print('='*100)
print()

# Overall comparison
ll_raw = calculate_logloss(y_true, raw_probs)
ll_ece = calculate_logloss(y_true, ece_probs)
ll_brier = calculate_logloss(y_true, brier_probs)

b_raw = calculate_brier(y_true, raw_probs)
b_ece = calculate_brier(y_true, ece_probs)
b_brier = calculate_brier(y_true, brier_probs)

e_raw = calculate_ece(y_true, raw_probs)
e_ece = calculate_ece(y_true, ece_probs)
e_brier = calculate_ece(y_true, brier_probs)

print(f"{'Method':<25} | {'Log Loss':<12} | {'Brier':<12} | {'ECE':<12} | Notes")
print('-'*100)
print(f"{'Raw Model':<25} | {ll_raw:<12.4f} | {b_raw:<12.4f} | {e_raw:<12.4f} | Baseline")
print(f"{'ECE-Optimized (Phase)':<25} | {ll_ece:<12.4f} | {b_ece:<12.4f} | {e_ece:<12.4f} | Best for calibration")
print(f"{'Brier-Optimized (Phase)':<25} | {ll_brier:<12.4f} | {b_brier:<12.4f} | {e_brier:<12.4f} | Best for accuracy")
print('='*100)

# Winner per metric
print()
print('WINNER BY METRIC:')
print('-'*60)

lls = {'Raw': ll_raw, 'ECE-Opt': ll_ece, 'Brier-Opt': ll_brier}
briers = {'Raw': b_raw, 'ECE-Opt': b_ece, 'Brier-Opt': b_brier}
eces = {'Raw': e_raw, 'ECE-Opt': e_ece, 'Brier-Opt': e_brier}

print(f"  LOG LOSS:  {min(lls, key=lls.get)} wins ({min(lls.values()):.4f})")
print(f"  BRIER:     {min(briers, key=briers.get)} wins ({min(briers.values()):.4f})")
print(f"  ECE:       {min(eces, key=eces.get)} wins ({min(eces.values()):.4f})")

# By innings
print()
print('='*100)
print('BY INNINGS BREAKDOWN:')
print('='*100)
for inn in [1, 2]:
    mask = df['innings'] == inn
    y = y_true[mask]
    
    ll_r = calculate_logloss(y, raw_probs[mask])
    ll_e = calculate_logloss(y, ece_probs[mask])
    ll_b = calculate_logloss(y, brier_probs[mask])
    
    b_r = calculate_brier(y, raw_probs[mask])
    b_e = calculate_brier(y, ece_probs[mask])
    b_b = calculate_brier(y, brier_probs[mask])
    
    print(f"\n  Innings {inn}:")
    print(f"    {'Method':<20} | {'Log Loss':<12} | {'Brier':<12}")
    print(f"    {'-'*50}")
    print(f"    {'Raw Model':<20} | {ll_r:<12.4f} | {b_r:<12.4f}")
    print(f"    {'ECE-Optimized':<20} | {ll_e:<12.4f} | {b_e:<12.4f}")
    print(f"    {'Brier-Optimized':<20} | {ll_b:<12.4f} | {b_b:<12.4f}")
    
    ll_winner = 'Raw' if ll_r <= ll_e and ll_r <= ll_b else ('ECE-Opt' if ll_e <= ll_b else 'Brier-Opt')
    b_winner = 'Raw' if b_r <= b_e and b_r <= b_b else ('ECE-Opt' if b_e <= b_b else 'Brier-Opt')
    print(f"    Winner: LL={ll_winner}, Brier={b_winner}")

# Key insight
print()
print('='*100)
print('KEY INSIGHT:')
print('='*100)

if ll_ece > ll_raw:
    print(f"  ⚠️  ECE-OPTIMIZED HURTS LOG LOSS!")
    print(f"      ECE-Opt: {ll_ece:.4f} vs Raw: {ll_raw:.4f} ({(ll_ece/ll_raw - 1)*100:.1f}% WORSE)")
    print()

if ll_brier < ll_raw:
    print(f"  ✅ BRIER-OPTIMIZED IMPROVES LOG LOSS!")
    print(f"      Brier-Opt: {ll_brier:.4f} vs Raw: {ll_raw:.4f} ({(1 - ll_brier/ll_raw)*100:.1f}% BETTER)")
    print()

print()
print('  ╔════════════════════════════════════════════════════════════════════════════════╗')
print('  ║  RECOMMENDATION FOR BLUE BOX:                                                  ║')
print('  ║                                                                                ║')
if ll_brier < ll_raw and b_brier < b_raw:
    print('  ║  🔵 USE BRIER-OPTIMIZED                                                        ║')
    print(f'  ║     - Log Loss: {ll_brier:.4f} ({(1 - ll_brier/ll_raw)*100:.1f}% better than Raw)                          ║')
    print(f'  ║     - Brier:    {b_brier:.4f} ({(1 - b_brier/b_raw)*100:.1f}% better than Raw)                          ║')
else:
    print('  ║  🟢 USE RAW MODEL                                                              ║')
    print(f'  ║     - Log Loss: {ll_raw:.4f}                                                   ║')
    print(f'  ║     - Brier:    {b_raw:.4f}                                                   ║')
print('  ╚════════════════════════════════════════════════════════════════════════════════╝')
