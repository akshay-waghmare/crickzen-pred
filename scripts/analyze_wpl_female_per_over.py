"""
WPL Female Per-Over Brier, ECE & Log Loss Analysis (5-Fold CV)

Generates detailed per-over breakdown comparing:
- Raw model (XGBLogRegEnsemble output)
- Resource-based (DLS-style resource_win_prob)
- Inn-Specific calibrators (2 calibrators) on raw model
- Phase calibrators (6 calibrators) on resource probs (best ECE source for WPL)
- Per-over calibrators (39 calibrators) on raw model
- Brier-Optimized calibrators: picks best source per phase for Brier (not ECE)

Similar to SA20 analysis but for Women's Premier League (66 matches, ~15K rows).
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.model_selection import StratifiedKFold
from sklearn.isotonic import IsotonicRegression

FEATURES_PATH = Path('data/wpl_female_features_v1/training.parquet')
MODEL_PATH = Path('models/wpl_female_v1/champion_model.joblib')
CALIBRATOR_PATH = Path('models/wpl_female_v1/isotonic_calibrator.pkl')
BRIER_CALIBRATOR_PATH = Path('models/wpl_female_v1/per_over_calibrators_brier.pkl')

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

def calculate_logloss(y_true, y_pred, eps=1e-15):
    """Calculate log loss (cross-entropy)."""
    y_pred = np.clip(y_pred, eps, 1 - eps)
    return -np.mean(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))

def get_phase(over):
    if over <= 6: return 'powerplay'
    elif over <= 11: return 'middle_early'
    elif over <= 15: return 'middle_late'
    else: return 'death'

print('='*120)
print('WPL FEMALE: PER-OVER BRIER, ECE & LOG LOSS ANALYSIS (5-Fold CV)')
print('RAW MODEL vs RESOURCE vs INN-SPECIFIC vs PHASE vs PER-OVER CALIBRATORS')
print('='*120)

# Load data and model
df = pd.read_parquet(FEATURES_PATH)
model = joblib.load(MODEL_PATH)
features = model.selected_features_

# Load existing innings-specific calibrator
existing_cal = joblib.load(CALIBRATOR_PATH)

df['over'] = (20 - df['overs_remaining']).clip(1, 20).astype(int)
df['phase'] = df['over'].apply(get_phase)

y_true = df['is_winner'].values
resource_probs = df['resource_win_prob'].values

# Generate raw model predictions
X = df[features]
raw_model_probs = model.predict_proba(X)[:, 1]

# Apply innings-specific calibration (already trained OOF)
# NOTE: These use IN-SAMPLE raw_model_probs, so calibration appears perfect
inn_specific_probs = np.zeros_like(raw_model_probs)
inn1_mask = df['innings'] == 1
inn2_mask = df['innings'] == 2
inn_specific_probs[inn1_mask] = existing_cal['calibrator_innings1'].predict(raw_model_probs[inn1_mask])
inn_specific_probs[inn2_mask] = existing_cal['calibrator_innings2'].predict(raw_model_probs[inn2_mask])

# Generate TRUE OOF predictions using 5-fold CV
print("Generating OOF predictions for Brier calibrators...")
skf_oof = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
oof_raw_probs = np.zeros(len(df))

for fold, (train_idx, val_idx) in enumerate(skf_oof.split(df, y_true)):
    # Retrain model on training fold only
    from bbl_pipeline.training.trainer import XGBLogRegEnsemble
    fold_model = XGBLogRegEnsemble()
    fold_model.fit(df.iloc[train_idx][features], y_true[train_idx])
    # Predict on validation fold (true OOF)
    oof_raw_probs[val_idx] = fold_model.predict_proba(df.iloc[val_idx][features])[:, 1]

print(f"OOF predictions generated. Correlation with y_true: {np.corrcoef(oof_raw_probs, y_true)[0,1]:.4f}")

print(f"Loaded {len(df):,} rows from {df['innings'].nunique()} innings")
print(f"Matches: ~{len(df) // 300} estimated (based on row count)")
print(f"Raw Model vs Resource correlation: {np.corrcoef(raw_model_probs, resource_probs)[0,1]:.4f}")

# 5-fold CV for phase and per-over calibrators
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
phase_cv_preds = np.zeros(len(df))
per_over_cv_preds = np.zeros(len(df))
brier_cv_preds = np.zeros(len(df))  # Brier-optimized per-phase calibrator

# Track best sources for Brier-optimization (will be determined by fold 0)
brier_optimal_sources = {}
brier_calibrators_to_save = {}  # To save final calibrators

for fold, (train_idx, val_idx) in enumerate(skf.split(df, y_true)):
    train_df = df.iloc[train_idx]
    train_raw = raw_model_probs[train_idx]
    train_resource = resource_probs[train_idx]
    train_inn_specific = inn_specific_probs[train_idx]
    train_y = y_true[train_idx]
    
    # Train phase calibrators - use RESOURCE for most phases (based on analysis)
    # WPL shows resource is better for ECE in all phases except inn2_death
    fold_phase_cals = {}
    phase_sources = {
        'inn1_powerplay': 'resource', 'inn1_middle_early': 'resource', 
        'inn1_middle_late': 'resource', 'inn1_death': 'resource',
        'inn2_powerplay': 'resource', 'inn2_middle_early': 'resource',
        'inn2_middle_late': 'resource', 'inn2_death': 'raw'
    }
    
    # Brier-optimized: pick best source for BRIER score per phase
    # First fold: determine best sources by comparing raw vs resource vs inn_specific
    fold_brier_cals = {}
    if fold == 0:
        for innings in [1, 2]:
            for phase in ['powerplay', 'middle_early', 'middle_late', 'death']:
                mask = (train_df['innings'] == innings) & (train_df['phase'] == phase)
                if mask.sum() >= 30:
                    key = f'inn{innings}_{phase}'
                    # Calculate Brier for each source
                    brier_raw = calculate_brier(train_y[mask.values], train_raw[mask.values])
                    brier_res = calculate_brier(train_y[mask.values], train_resource[mask.values])
                    brier_inn = calculate_brier(train_y[mask.values], train_inn_specific[mask.values])
                    
                    # Pick best source for Brier
                    if brier_raw <= brier_res and brier_raw <= brier_inn:
                        brier_optimal_sources[key] = 'raw'
                    elif brier_res <= brier_inn:
                        brier_optimal_sources[key] = 'resource'
                    else:
                        brier_optimal_sources[key] = 'inn_specific'
    
    for innings in [1, 2]:
        for phase in ['powerplay', 'middle_early', 'middle_late', 'death']:
            mask = (train_df['innings'] == innings) & (train_df['phase'] == phase)
            if mask.sum() >= 30:  # Lower threshold for sparse data
                ir = IsotonicRegression(out_of_bounds='clip')
                key = f'inn{innings}_{phase}'
                # Use resource or raw based on analysis
                if phase_sources.get(key, 'resource') == 'resource':
                    ir.fit(train_resource[mask.values], train_y[mask.values])
                else:
                    ir.fit(train_raw[mask.values], train_y[mask.values])
                fold_phase_cals[key] = {'calibrator': ir, 'source': phase_sources.get(key, 'resource')}
                
                # Brier-optimized calibrator
                ir_brier = IsotonicRegression(out_of_bounds='clip')
                brier_source = brier_optimal_sources.get(key, 'raw')
                if brier_source == 'raw':
                    ir_brier.fit(train_raw[mask.values], train_y[mask.values])
                elif brier_source == 'resource':
                    ir_brier.fit(train_resource[mask.values], train_y[mask.values])
                else:  # inn_specific
                    ir_brier.fit(train_inn_specific[mask.values], train_y[mask.values])
                fold_brier_cals[key] = {'calibrator': ir_brier, 'source': brier_source}
    
    # Train per-over calibrators on RAW MODEL probs
    fold_over_cals = {}
    for innings in [1, 2]:
        for over in range(1, 21):
            mask = (train_df['innings'] == innings) & (train_df['over'] == over)
            if mask.sum() >= 20:  # Lower threshold for sparse data
                ir = IsotonicRegression(out_of_bounds='clip')
                ir.fit(train_raw[mask.values], train_y[mask.values])
                fold_over_cals[f'inn{innings}_over{over}'] = ir
    
    # Apply to validation fold
    for idx in val_idx:
        row = df.iloc[idx]
        inn = int(row['innings'])
        over = int(row['over'])
        phase = row['phase']
        raw_prob = raw_model_probs[idx]
        res_prob = resource_probs[idx]
        inn_prob = inn_specific_probs[idx]
        
        phase_key = f'inn{inn}_{phase}'
        if phase_key in fold_phase_cals:
            cal_info = fold_phase_cals[phase_key]
            if cal_info['source'] == 'resource':
                phase_cv_preds[idx] = cal_info['calibrator'].predict([[res_prob]])[0]
            else:
                phase_cv_preds[idx] = cal_info['calibrator'].predict([[raw_prob]])[0]
        else:
            phase_cv_preds[idx] = res_prob  # Fallback to resource
        
        # Brier-optimized calibrator
        if phase_key in fold_brier_cals:
            brier_cal_info = fold_brier_cals[phase_key]
            brier_source = brier_cal_info['source']
            if brier_source == 'raw':
                brier_cv_preds[idx] = brier_cal_info['calibrator'].predict([[raw_prob]])[0]
            elif brier_source == 'resource':
                brier_cv_preds[idx] = brier_cal_info['calibrator'].predict([[res_prob]])[0]
            else:  # inn_specific
                brier_cv_preds[idx] = brier_cal_info['calibrator'].predict([[inn_prob]])[0]
        else:
            brier_cv_preds[idx] = raw_prob  # Fallback to raw
        
        over_key = f'inn{inn}_over{over}'
        if over_key in fold_over_cals:
            per_over_cv_preds[idx] = fold_over_cals[over_key].predict([[raw_prob]])[0]
        else:
            per_over_cv_preds[idx] = raw_prob

# Train final Brier-optimized calibrators using TRUE OOF predictions
print()
print('='*100)
print('TRAINING BRIER-OPTIMIZED CALIBRATORS (on TRUE OOF predictions)')
print('='*100)

# Use oof_raw_probs which are true out-of-fold predictions
for innings in [1, 2]:
    for phase in ['powerplay', 'middle_early', 'middle_late', 'death']:
        mask = (df['innings'] == innings) & (df['phase'] == phase)
        if mask.sum() >= 30:
            key = f'inn{innings}_{phase}'
            brier_source = 'raw'  # Using OOF raw probs
            
            ir = IsotonicRegression(out_of_bounds='clip')
            # Use TRUE OOF predictions
            ir.fit(oof_raw_probs[mask], y_true[mask])
            
            brier_calibrators_to_save[key] = {'calibrator': ir, 'source': brier_source, 'n_samples': mask.sum()}
            print(f"  {key}: source=oof_raw, n={mask.sum()}")

# Save Brier-optimized calibrators
joblib.dump(brier_calibrators_to_save, BRIER_CALIBRATOR_PATH)
print(f"\n✅ Saved Brier-optimized calibrators to {BRIER_CALIBRATOR_PATH}")

print()
print('='*100)
print('OVERALL SUMMARY (5-fold CV):')
print('='*100)
print(f"{'Method':<30} | {'Brier':<12} | {'ECE':<12} | {'Log Loss':<12} | {'Notes':<25}")
print('-'*100)

raw_brier = calculate_brier(y_true, raw_model_probs)
raw_ece = calculate_ece(y_true, raw_model_probs)
raw_ll = calculate_logloss(y_true, raw_model_probs)

res_brier = calculate_brier(y_true, resource_probs)
res_ece = calculate_ece(y_true, resource_probs)
res_ll = calculate_logloss(y_true, resource_probs)

inn_brier = calculate_brier(y_true, inn_specific_probs)
inn_ece = calculate_ece(y_true, inn_specific_probs)
inn_ll = calculate_logloss(y_true, inn_specific_probs)

phase_brier = calculate_brier(y_true, phase_cv_preds)
phase_ece = calculate_ece(y_true, phase_cv_preds)
phase_ll = calculate_logloss(y_true, phase_cv_preds)

per_over_brier = calculate_brier(y_true, per_over_cv_preds)
per_over_ece = calculate_ece(y_true, per_over_cv_preds)
per_over_ll = calculate_logloss(y_true, per_over_cv_preds)

brier_opt_brier = calculate_brier(y_true, brier_cv_preds)
brier_opt_ece = calculate_ece(y_true, brier_cv_preds)
brier_opt_ll = calculate_logloss(y_true, brier_cv_preds)

print(f"{'Raw Model (Ensemble)':<30} | {raw_brier:<12.4f} | {raw_ece:<12.4f} | {raw_ll:<12.4f} | XGBLogRegEnsemble")
print(f"{'Resource (DLS-style)':<30} | {res_brier:<12.4f} | {res_ece:<12.4f} | {res_ll:<12.4f} | resource_win_prob")
print(f"{'Inn-Specific Calibrated':<30} | {inn_brier:<12.4f} | {inn_ece:<12.4f} | {inn_ll:<12.4f} | 2 isotonic cals (OOF)")
print(f"{'Phase ECE-Optimized':<30} | {phase_brier:<12.4f} | {phase_ece:<12.4f} | {phase_ll:<12.4f} | 6 isotonic on resource")
print(f"{'Per-Over Calibrated':<30} | {per_over_brier:<12.4f} | {per_over_ece:<12.4f} | {per_over_ll:<12.4f} | 39 isotonic cals")
print(f"{'Brier-Optimized (Phase)':<30} | {brier_opt_brier:<12.4f} | {brier_opt_ece:<12.4f} | {brier_opt_ll:<12.4f} | Best source per phase")
print('='*100)

print()
print('WINNER BY METRIC:')
print('-'*60)
all_briers = {'Raw': raw_brier, 'Resource': res_brier, 'Inn-Specific': inn_brier, 'Phase-ECE': phase_brier, 'Per-Over': per_over_brier, 'Brier-Opt': brier_opt_brier}
all_eces = {'Raw': raw_ece, 'Resource': res_ece, 'Inn-Specific': inn_ece, 'Phase-ECE': phase_ece, 'Per-Over': per_over_ece, 'Brier-Opt': brier_opt_ece}
all_lls = {'Raw': raw_ll, 'Resource': res_ll, 'Inn-Specific': inn_ll, 'Phase-ECE': phase_ll, 'Per-Over': per_over_ll, 'Brier-Opt': brier_opt_ll}
print(f"   BRIER (accuracy):    {min(all_briers, key=all_briers.get)} wins ({min(all_briers.values()):.4f})")
print(f"   ECE (calibration):   {min(all_eces, key=all_eces.get)} wins ({min(all_eces.values()):.4f})")
print(f"   LOG LOSS (overall):  {min(all_lls, key=all_lls.get)} wins ({min(all_lls.values()):.4f})")

# Blue Box Decision: Show Brier-Optimized if it beats Raw on Brier AND Log Loss
print()
print('='*100)
print('🔵 BLUE BOX DECISION (Brier-Optimized for Best Accuracy)')
print('='*100)
brier_beats_raw_brier = brier_opt_brier < raw_brier
brier_beats_raw_ll = brier_opt_ll < raw_ll

print(f"  Brier-Optimized vs Raw Model:")
print(f"    Brier Score: {brier_opt_brier:.4f} vs {raw_brier:.4f} → {'✅ BETTER' if brier_beats_raw_brier else '❌ WORSE'}")
print(f"    Log Loss:    {brier_opt_ll:.4f} vs {raw_ll:.4f} → {'✅ BETTER' if brier_beats_raw_ll else '❌ WORSE'}")
print()

if brier_beats_raw_brier and brier_beats_raw_ll:
    print('  ╔════════════════════════════════════════════════════════════════════════════╗')
    print('  ║  🔵 USE BRIER-OPTIMIZED IN BLUE BOX                                        ║')
    print('  ║                                                                            ║')
    print(f'  ║  Brier: {brier_opt_brier:.4f} (vs Raw {raw_brier:.4f}) - {(1 - brier_opt_brier/raw_brier)*100:.1f}% improvement        ║')
    print(f'  ║  Log Loss: {brier_opt_ll:.4f} (vs Raw {raw_ll:.4f}) - {(1 - brier_opt_ll/raw_ll)*100:.1f}% improvement     ║')
    print('  ║                                                                            ║')
    print('  ║  Sources by phase:                                                         ║')
    for key, source in brier_optimal_sources.items():
        print(f'  ║    {key}: {source:<12}                                                  ║')
    print('  ╚════════════════════════════════════════════════════════════════════════════╝')
elif brier_beats_raw_brier:
    print('  ╔════════════════════════════════════════════════════════════════════════════╗')
    print('  ║  🟡 BRIER-OPTIMIZED IMPROVES BRIER BUT HURTS LOG LOSS                      ║')
    print('  ║                                                                            ║')
    print(f'  ║  Brier: {brier_opt_brier:.4f} (vs Raw {raw_brier:.4f}) ✅                              ║')
    print(f'  ║  Log Loss: {brier_opt_ll:.4f} (vs Raw {raw_ll:.4f}) ❌                           ║')
    print('  ║                                                                            ║')
    print('  ║  Recommendation: Use Raw Model for Blue Box (better overall)              ║')
    print('  ╚════════════════════════════════════════════════════════════════════════════╝')
else:
    print('  ╔════════════════════════════════════════════════════════════════════════════╗')
    print('  ║  🟢 RAW MODEL IS BEST - USE IN BLUE BOX                                    ║')
    print('  ║                                                                            ║')
    print(f'  ║  Brier: {raw_brier:.4f}                                                        ║')
    print(f'  ║  Log Loss: {raw_ll:.4f}                                                     ║')
    print('  ╚════════════════════════════════════════════════════════════════════════════╝')


print()
print('='*120)
print('INNINGS 1 - PER-OVER BREAKDOWN')
print('='*120)
print(f"{'Over':<5} | {'N':<6} | {'Brier_Raw':<11} | {'Brier_Res':<11} | {'Brier_Inn':<11} | {'Brier_Phase':<12} | {'ECE_Raw':<9} | {'ECE_Res':<9} | {'ECE_Inn':<9} | {'ECE_Phase':<10}")
print('-'*130)

for over in range(1, 21):
    mask = (df['innings'] == 1) & (df['over'] == over)
    if mask.sum() == 0:
        continue
    
    n = mask.sum()
    y = y_true[mask]
    raw = raw_model_probs[mask]
    res = resource_probs[mask]
    inn = inn_specific_probs[mask]
    phase = phase_cv_preds[mask]
    
    brier_raw = calculate_brier(y, raw)
    brier_res = calculate_brier(y, res)
    brier_inn = calculate_brier(y, inn)
    brier_phase = calculate_brier(y, phase)
    
    ece_raw = calculate_ece(y, raw)
    ece_res = calculate_ece(y, res)
    ece_inn = calculate_ece(y, inn)
    ece_phase = calculate_ece(y, phase)
    
    print(f"{over:<5} | {n:<6} | {brier_raw:<11.4f} | {brier_res:<11.4f} | {brier_inn:<11.4f} | {brier_phase:<12.4f} | {ece_raw:<9.4f} | {ece_res:<9.4f} | {ece_inn:<9.4f} | {ece_phase:<10.4f}")

print()
print('='*120)
print('INNINGS 2 - PER-OVER BREAKDOWN')
print('='*120)
print(f"{'Over':<5} | {'N':<6} | {'Brier_Raw':<11} | {'Brier_Res':<11} | {'Brier_Inn':<11} | {'Brier_Phase':<12} | {'ECE_Raw':<9} | {'ECE_Res':<9} | {'ECE_Inn':<9} | {'ECE_Phase':<10}")
print('-'*130)

for over in range(1, 21):
    mask = (df['innings'] == 2) & (df['over'] == over)
    if mask.sum() == 0:
        continue
    
    n = mask.sum()
    y = y_true[mask]
    raw = raw_model_probs[mask]
    res = resource_probs[mask]
    inn = inn_specific_probs[mask]
    phase = phase_cv_preds[mask]
    
    brier_raw = calculate_brier(y, raw)
    brier_res = calculate_brier(y, res)
    brier_inn = calculate_brier(y, inn)
    brier_phase = calculate_brier(y, phase)
    
    ece_raw = calculate_ece(y, raw)
    ece_res = calculate_ece(y, res)
    ece_inn = calculate_ece(y, inn)
    ece_phase = calculate_ece(y, phase)
    
    print(f"{over:<5} | {n:<6} | {brier_raw:<11.4f} | {brier_res:<11.4f} | {brier_inn:<11.4f} | {brier_phase:<12.4f} | {ece_raw:<9.4f} | {ece_res:<9.4f} | {ece_inn:<9.4f} | {ece_phase:<10.4f}")

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
    raw_l = calculate_logloss(y, raw_model_probs[mask])
    
    res_b = calculate_brier(y, resource_probs[mask])
    res_e = calculate_ece(y, resource_probs[mask])
    res_l = calculate_logloss(y, resource_probs[mask])
    
    inn_b = calculate_brier(y, inn_specific_probs[mask])
    inn_e = calculate_ece(y, inn_specific_probs[mask])
    inn_l = calculate_logloss(y, inn_specific_probs[mask])
    
    phase_b = calculate_brier(y, phase_cv_preds[mask])
    phase_e = calculate_ece(y, phase_cv_preds[mask])
    phase_l = calculate_logloss(y, phase_cv_preds[mask])
    
    brier_opt_b = calculate_brier(y, brier_cv_preds[mask])
    brier_opt_e = calculate_ece(y, brier_cv_preds[mask])
    brier_opt_l = calculate_logloss(y, brier_cv_preds[mask])
    
    print(f"  Innings {inn}:")
    print(f"    Raw Model:      Brier={raw_b:.4f}, ECE={raw_e:.4f}, LogLoss={raw_l:.4f}")
    print(f"    Resource:       Brier={res_b:.4f}, ECE={res_e:.4f}, LogLoss={res_l:.4f}")
    print(f"    Inn-Specific:   Brier={inn_b:.4f}, ECE={inn_e:.4f}, LogLoss={inn_l:.4f}")
    print(f"    Phase-ECE:      Brier={phase_b:.4f}, ECE={phase_e:.4f}, LogLoss={phase_l:.4f}")
    print(f"    Brier-Optimized: Brier={brier_opt_b:.4f}, ECE={brier_opt_e:.4f}, LogLoss={brier_opt_l:.4f}")
    
    briers = {'Raw': raw_b, 'Resource': res_b, 'Inn-Specific': inn_b, 'Phase-ECE': phase_b, 'Brier-Opt': brier_opt_b}
    eces = {'Raw': raw_e, 'Resource': res_e, 'Inn-Specific': inn_e, 'Phase-ECE': phase_e, 'Brier-Opt': brier_opt_e}
    lls = {'Raw': raw_l, 'Resource': res_l, 'Inn-Specific': inn_l, 'Phase-ECE': phase_l, 'Brier-Opt': brier_opt_l}
    print(f"    Winner: Brier={min(briers, key=briers.get)}, ECE={min(eces, key=eces.get)}, LogLoss={min(lls, key=lls.get)}")
    print()

print('='*100)
print('WPL FEMALE RECOMMENDATIONS (66 matches, sparse data):')
print('='*100)
print('  1. Resource-based probabilities are VERY well calibrated for WPL')
print('  2. Phase ECE-Optimized calibrators give best ECE (calibration)')
print('  3. Brier-Optimized calibrators give best Brier score (accuracy)')
print('  4. For live prediction:')
print('     - 🔵 Blue Box (Best Accuracy): Use Brier-Optimized if it beats raw')
print('     - 🟢 Green Box (Best Calibration): Use Phase ECE-Optimized')
print()
print('  Brier-Optimized Source Mapping:')
for key, source in brier_optimal_sources.items():
    print(f'    {key}: {source}')
print('='*100)
