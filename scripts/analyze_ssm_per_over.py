"""
Analyze SSM model per-over: Brier, ECE, and Log Loss for all 40 overs.
Output detailed tables for streamlit integration.
"""
import joblib
import pandas as pd
import numpy as np
from pathlib import Path

def log_loss(y_true: np.ndarray, y_prob: np.ndarray, clip: float = 0.01) -> float:
    """Calculate log loss (cross-entropy) with confidence clipping."""
    y_prob = np.clip(y_prob, clip, 1 - clip)
    loss = -(y_true * np.log(y_prob) + (1 - y_true) * np.log(1 - y_prob))
    return float(np.mean(loss))

def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculate Brier score."""
    return float(np.mean((y_prob - y_true) ** 2))

def ece_score(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Calculate Expected Calibration Error."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        in_bin = (y_prob >= bin_boundaries[i]) & (y_prob < bin_boundaries[i + 1])
        prop_in_bin = in_bin.mean()
        if prop_in_bin > 0:
            avg_confidence = y_prob[in_bin].mean()
            avg_accuracy = y_true[in_bin].mean()
            ece += prop_in_bin * abs(avg_accuracy - avg_confidence)
    return float(ece)

# Load model and data
print("Loading SSM v1 model and training data...")
model = joblib.load('models/ssm_v1/champion_model.joblib')
isotonic_cal = joblib.load('models/ssm_v1/isotonic_calibrator.pkl')
per_over_cal = joblib.load('models/ssm_v1/per_over_calibrators.pkl')
df = pd.read_parquet('data/ssm_features_v1/training.parquet')

print(f"Total samples: {len(df):,}")

# Use actual feature columns
exclude_cols = ['is_winner', 'overs_completed', 'match_id', 'ball_id']
feature_cols = [col for col in df.columns if col not in exclude_cols and not col.startswith('_')]

# Get predictions
X = df[feature_cols].fillna(0)
y_true = df['is_winner'].values

# Raw model probabilities
raw_probs = model.predict_proba(X)[:, 1]

# Innings-specific calibrated probabilities
innings_cal_probs = np.zeros_like(raw_probs)
for innings in [1, 2]:
    mask = df['innings'] == innings
    if mask.sum() > 0:
        calibrator = isotonic_cal[f'calibrator_innings{innings}']
        innings_cal_probs[mask] = calibrator.predict(raw_probs[mask].reshape(-1, 1)).ravel()

# Resource-based probabilities
resource_probs = df['resource_win_prob'].values
valid_resource_mask = df['resource_win_prob'].notna()

# Calculate over from overs_remaining
df['over'] = (20 - df['overs_remaining']).astype(int).clip(1, 20)

# Per-over analysis
print("\n" + "="*150)
print("SSM v1 MODEL - PER-OVER ANALYSIS (Brier, ECE, Log Loss)")
print("="*150)

results = []

for innings in [1, 2]:
    print(f"\n{'='*150}")
    print(f"INNINGS {innings}")
    print(f"{'='*150}")
    print(f"{'Over':<6} {'N':<7} {'B_Raw':<8} {'B_Cal':<8} {'B_Res':<8} {'E_Raw':<8} {'E_Cal':<8} {'E_Res':<8} {'LL_Raw':<8} {'LL_Cal':<8} {'LL_Res':<8} {'Best_B':<8} {'Best_E':<8}")
    print("-"*150)
    
    for over in range(1, 21):
        mask = (df['innings'] == innings) & (df['over'] == over) & valid_resource_mask
        
        if mask.sum() < 50:
            continue
        
        y_sub = y_true[mask]
        raw_sub = raw_probs[mask]
        cal_sub = innings_cal_probs[mask]
        res_sub = resource_probs[mask]
        
        # Apply per-over calibrator
        per_over_sub = np.zeros_like(raw_sub)
        over_key = f'inn{innings}_over{over}'
        if over_key in per_over_cal and 'calibrator' in per_over_cal[over_key]:
            cal_info = per_over_cal[over_key]
            source = cal_info.get('source', 'raw')
            if source == 'raw':
                input_prob = raw_sub
            elif source == 'cal':
                input_prob = cal_sub
            else:
                input_prob = res_sub
            per_over_sub = cal_info['calibrator'].predict(input_prob.reshape(-1, 1)).ravel()
        else:
            per_over_sub = raw_sub
        
        # Calculate metrics
        b_raw = brier_score(y_sub, raw_sub)
        b_cal = brier_score(y_sub, cal_sub)
        b_res = brier_score(y_sub, res_sub)
        b_per = brier_score(y_sub, per_over_sub)
        
        e_raw = ece_score(y_sub, raw_sub)
        e_cal = ece_score(y_sub, cal_sub)
        e_res = ece_score(y_sub, res_sub)
        e_per = ece_score(y_sub, per_over_sub)
        
        ll_raw = log_loss(y_sub, raw_sub)
        ll_cal = log_loss(y_sub, cal_sub)
        ll_res = log_loss(y_sub, res_sub)
        ll_per = log_loss(y_sub, per_over_sub)
        
        # Determine winners
        brier_vals = [('Raw', b_raw), ('Cal', b_cal), ('Res', b_res), ('Per', b_per)]
        ece_vals = [('Raw', e_raw), ('Cal', e_cal), ('Res', e_res), ('Per', e_per)]
        ll_vals = [('Raw', ll_raw), ('Cal', ll_cal), ('Res', ll_res), ('Per', ll_per)]
        
        best_b = min(brier_vals, key=lambda x: x[1])[0]
        best_e = min(ece_vals, key=lambda x: x[1])[0]
        best_ll = min(ll_vals, key=lambda x: x[1])[0]
        
        results.append({
            'innings': innings,
            'over': over,
            'n': mask.sum(),
            'brier_raw': b_raw, 'brier_cal': b_cal, 'brier_res': b_res, 'brier_per': b_per,
            'ece_raw': e_raw, 'ece_cal': e_cal, 'ece_res': e_res, 'ece_per': e_per,
            'logloss_raw': ll_raw, 'logloss_cal': ll_cal, 'logloss_res': ll_res, 'logloss_per': ll_per,
            'best_brier': best_b, 'best_ece': best_e, 'best_logloss': best_ll
        })
        
        print(f"{over:<6} {mask.sum():<7} {b_raw:<8.4f} {b_cal:<8.4f} {b_res:<8.4f} {e_raw:<8.4f} {e_cal:<8.4f} {e_res:<8.4f} {ll_raw:<8.4f} {ll_cal:<8.4f} {ll_res:<8.4f} {best_b:<8} {best_e:<8}")

# Summary by phase
print("\n" + "="*150)
print("SUMMARY BY PHASE")
print("="*150)

def get_phase(over):
    if over <= 6:
        return 'Powerplay'
    elif over <= 15:
        return 'Middle'
    else:
        return 'Death'

results_df = pd.DataFrame(results)
results_df['phase'] = results_df['over'].apply(get_phase)

for innings in [1, 2]:
    print(f"\nINNINGS {innings}:")
    print(f"{'Phase':<12} {'N':<8} {'B_Raw':<8} {'B_Cal':<8} {'B_Per':<8} {'B_Res':<8} {'E_Raw':<8} {'E_Cal':<8} {'E_Per':<8} {'E_Res':<8} {'Best_B':<8} {'Best_E':<8}")
    print("-"*130)
    
    for phase in ['Powerplay', 'Middle', 'Death']:
        phase_df = results_df[(results_df['innings'] == innings) & (results_df['phase'] == phase)]
        if len(phase_df) == 0:
            continue
        
        # Weighted average by sample size
        n_total = phase_df['n'].sum()
        
        b_raw = (phase_df['brier_raw'] * phase_df['n']).sum() / n_total
        b_cal = (phase_df['brier_cal'] * phase_df['n']).sum() / n_total
        b_per = (phase_df['brier_per'] * phase_df['n']).sum() / n_total
        b_res = (phase_df['brier_res'] * phase_df['n']).sum() / n_total
        
        e_raw = (phase_df['ece_raw'] * phase_df['n']).sum() / n_total
        e_cal = (phase_df['ece_cal'] * phase_df['n']).sum() / n_total
        e_per = (phase_df['ece_per'] * phase_df['n']).sum() / n_total
        e_res = (phase_df['ece_res'] * phase_df['n']).sum() / n_total
        
        best_b = min([('Raw', b_raw), ('Cal', b_cal), ('Per', b_per), ('Res', b_res)], key=lambda x: x[1])[0]
        best_e = min([('Raw', e_raw), ('Cal', e_cal), ('Per', e_per), ('Res', e_res)], key=lambda x: x[1])[0]
        
        print(f"{phase:<12} {n_total:<8} {b_raw:<8.4f} {b_cal:<8.4f} {b_per:<8.4f} {b_res:<8.4f} {e_raw:<8.4f} {e_cal:<8.4f} {e_per:<8.4f} {e_res:<8.4f} {best_b:<8} {best_e:<8}")

# Winner counts
print("\n" + "="*150)
print("WINNER SUMMARY (40 overs total)")
print("="*150)

brier_counts = results_df['best_brier'].value_counts()
ece_counts = results_df['best_ece'].value_counts()
ll_counts = results_df['best_logloss'].value_counts()

print("\nBrier Score Winners:")
for winner in ['Raw', 'Cal', 'Per', 'Res']:
    count = brier_counts.get(winner, 0)
    print(f"  {winner}: {count}/40 overs")

print("\nECE Winners:")
for winner in ['Raw', 'Cal', 'Per', 'Res']:
    count = ece_counts.get(winner, 0)
    print(f"  {winner}: {count}/40 overs")

print("\nLog Loss Winners:")
for winner in ['Raw', 'Cal', 'Per', 'Res']:
    count = ll_counts.get(winner, 0)
    print(f"  {winner}: {count}/40 overs")

# Generate markdown table for streamlit
print("\n" + "="*150)
print("MARKDOWN TABLE FOR STREAMLIT (copy-paste ready)")
print("="*150)

print("\n#### Innings 1 - Per-Over Analysis")
print("| Over | N | B_Raw | B_Cal | B_Per | B_Res | E_Raw | E_Cal | E_Per | E_Res | Best Brier | Best ECE |")
print("|------|---|-------|-------|-------|-------|-------|-------|-------|-------|------------|----------|")
for _, row in results_df[results_df['innings'] == 1].iterrows():
    b_raw_str = f"**{row['brier_raw']:.4f}**" if row['best_brier'] == 'Raw' else f"{row['brier_raw']:.4f}"
    b_cal_str = f"**{row['brier_cal']:.4f}**" if row['best_brier'] == 'Cal' else f"{row['brier_cal']:.4f}"
    b_per_str = f"**{row['brier_per']:.4f}**" if row['best_brier'] == 'Per' else f"{row['brier_per']:.4f}"
    b_res_str = f"**{row['brier_res']:.4f}**" if row['best_brier'] == 'Res' else f"{row['brier_res']:.4f}"
    e_raw_str = f"**{row['ece_raw']:.4f}**" if row['best_ece'] == 'Raw' else f"{row['ece_raw']:.4f}"
    e_cal_str = f"**{row['ece_cal']:.4f}**" if row['best_ece'] == 'Cal' else f"{row['ece_cal']:.4f}"
    e_per_str = f"**{row['ece_per']:.4f}**" if row['best_ece'] == 'Per' else f"{row['ece_per']:.4f}"
    e_res_str = f"**{row['ece_res']:.4f}**" if row['best_ece'] == 'Res' else f"{row['ece_res']:.4f}"
    print(f"| {int(row['over'])} | {int(row['n'])} | {b_raw_str} | {b_cal_str} | {b_per_str} | {b_res_str} | {e_raw_str} | {e_cal_str} | {e_per_str} | {e_res_str} | 🏆 {row['best_brier']} | 🏆 {row['best_ece']} |")

print("\n#### Innings 2 - Per-Over Analysis")
print("| Over | N | B_Raw | B_Cal | B_Per | B_Res | E_Raw | E_Cal | E_Per | E_Res | Best Brier | Best ECE |")
print("|------|---|-------|-------|-------|-------|-------|-------|-------|-------|------------|----------|")
for _, row in results_df[results_df['innings'] == 2].iterrows():
    b_raw_str = f"**{row['brier_raw']:.4f}**" if row['best_brier'] == 'Raw' else f"{row['brier_raw']:.4f}"
    b_cal_str = f"**{row['brier_cal']:.4f}**" if row['best_brier'] == 'Cal' else f"{row['brier_cal']:.4f}"
    b_per_str = f"**{row['brier_per']:.4f}**" if row['best_brier'] == 'Per' else f"{row['brier_per']:.4f}"
    b_res_str = f"**{row['brier_res']:.4f}**" if row['best_brier'] == 'Res' else f"{row['brier_res']:.4f}"
    e_raw_str = f"**{row['ece_raw']:.4f}**" if row['best_ece'] == 'Raw' else f"{row['ece_raw']:.4f}"
    e_cal_str = f"**{row['ece_cal']:.4f}**" if row['best_ece'] == 'Cal' else f"{row['ece_cal']:.4f}"
    e_per_str = f"**{row['ece_per']:.4f}**" if row['best_ece'] == 'Per' else f"{row['ece_per']:.4f}"
    e_res_str = f"**{row['ece_res']:.4f}**" if row['best_ece'] == 'Res' else f"{row['ece_res']:.4f}"
    print(f"| {int(row['over'])} | {int(row['n'])} | {b_raw_str} | {b_cal_str} | {b_per_str} | {b_res_str} | {e_raw_str} | {e_cal_str} | {e_per_str} | {e_res_str} | 🏆 {row['best_brier']} | 🏆 {row['best_ece']} |")

print("\n" + "="*150)
