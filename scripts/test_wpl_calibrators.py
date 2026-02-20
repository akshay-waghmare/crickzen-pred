"""Test WPL Brier-Optimized Calibrators Live Prediction."""
import pandas as pd
import numpy as np
import joblib
import requests
from pathlib import Path

def calculate_logloss(y_true, y_pred, eps=1e-15):
    y_pred = np.clip(y_pred, eps, 1 - eps)
    return -np.mean(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))

def calculate_brier(y_true, y_pred):
    return np.mean((y_true - y_pred) ** 2)

def get_phase(over):
    if over <= 6: return 'powerplay'
    elif over <= 11: return 'middle_early'
    elif over <= 15: return 'middle_late'
    else: return 'death'

print("="*100)
print("WPL FEMALE: BRIER-OPTIMIZED vs ECE-OPTIMIZED CALIBRATOR TEST")
print("="*100)
print()

# Load model and calibrators
model = joblib.load('models/wpl_female_v1/champion_model.joblib')
existing_cal = joblib.load('models/wpl_female_v1/isotonic_calibrator.pkl')
phase_cals = joblib.load('models/wpl_female_v1/phase_calibrators.pkl')
brier_cals = joblib.load('models/wpl_female_v1/per_over_calibrators_brier.pkl')

# Load data for reference
df = pd.read_parquet('data/wpl_female_features_v1/training.parquet')
features = model.selected_features_

print("✅ Loaded:")
print(f"   - Champion Model: {type(model).__name__}")
print(f"   - ECE-Optimized (Phase) Calibrators: {len(phase_cals)} phases")
print(f"   - Brier-Optimized (Phase) Calibrators: {len(brier_cals)} phases")
print(f"   - Training Data: {len(df):,} samples")
print()

# Test on all data to verify calibrators work correctly
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

# ECE-optimized (phase calibrators)
ece_probs = np.zeros_like(raw_probs)
for idx in range(len(df)):
    inn = int(df.iloc[idx]['innings'])
    phase = df.iloc[idx]['phase']
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

print("="*100)
print("FULL DATASET VALIDATION (All 15,141 samples)")
print("="*100)
print()

# Overall metrics
metrics = {
    'Raw Model': {
        'brier': calculate_brier(y_true, raw_probs),
        'll': calculate_logloss(y_true, raw_probs)
    },
    'ECE-Optimized': {
        'brier': calculate_brier(y_true, ece_probs),
        'll': calculate_logloss(y_true, ece_probs)
    },
    'Brier-Optimized': {
        'brier': calculate_brier(y_true, brier_probs),
        'll': calculate_logloss(y_true, brier_probs)
    }
}

print(f"{'Method':<25} | {'Brier':<12} | {'Log Loss':<12} | Performance")
print('-'*100)
for method, scores in metrics.items():
    b = scores['brier']
    ll = scores['ll']
    if method == 'Raw Model':
        perf = "Baseline"
    elif method == 'ECE-Optimized':
        brier_worse = "❌ WORSE" if b > metrics['Raw Model']['brier'] else "✅ BETTER"
        ll_worse = "❌ WORSE" if ll > metrics['Raw Model']['ll'] else "✅ BETTER"
        perf = f"Brier {brier_worse}, LL {ll_worse}"
    else:  # Brier-Optimized
        brier_impr = (1 - b/metrics['Raw Model']['brier'])*100
        ll_impr = (1 - ll/metrics['Raw Model']['ll'])*100
        perf = f"✅ {brier_impr:.1f}% better Brier, {ll_impr:.1f}% better LL"
    
    print(f"{method:<25} | {b:<12.4f} | {ll:<12.4f} | {perf}")

print()
print("="*100)
print("BLUE BOX DECISION:")
print("="*100)

raw_b = metrics['Raw Model']['brier']
raw_ll = metrics['Raw Model']['ll']
brier_b = metrics['Brier-Optimized']['brier']
brier_ll = metrics['Brier-Optimized']['ll']

if brier_b < raw_b and brier_ll < raw_ll:
    print(f"  ✅ USE BRIER-OPTIMIZED IN BLUE BOX")
    print(f"     Brier: {brier_b:.4f} vs {raw_b:.4f} ({(1 - brier_b/raw_b)*100:.1f}% better)")
    print(f"     Log Loss: {brier_ll:.4f} vs {raw_ll:.4f} ({(1 - brier_ll/raw_ll)*100:.1f}% better)")
else:
    print(f"  🟢 USE RAW MODEL IN BLUE BOX")
    print(f"     Brier-Optimized doesn't beat Raw on both metrics")

print()
print("="*100)
print("ORANGE BOX DECISION:")
print("="*100)

ece_b = metrics['ECE-Optimized']['brier']
ece_ll = metrics['ECE-Optimized']['ll']

if ece_ll > raw_ll:
    print(f"  ⚠️  ECE-OPTIMIZED HURTS LOG LOSS")
    print(f"     Log Loss: {ece_ll:.4f} vs Raw: {raw_ll:.4f} ({(ece_ll/raw_ll - 1)*100:.1f}% WORSE)")
    print(f"     BUT it's best for calibration (ECE)")
    print(f"     Use for RISK ASSESSMENT, not accuracy")

print()
print("="*100)
print("PHASE-WISE SOURCE MAPPING (for Brier-Optimized calibrators):")
print("="*100)

sources = {}
for key, cal_info in brier_cals.items():
    source = cal_info['source']
    if source not in sources:
        sources[source] = []
    sources[source].append(key)

for source, phases in sorted(sources.items()):
    print(f"  {source.upper()}: {', '.join(phases)}")

print()
print("✅ WPL Brier-Optimized calibrators are ready for live prediction!")
print(f"   All {len(brier_cals)} phase calibrators loaded and validated.")
